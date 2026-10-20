"""
Titular interpretado por departamento (HU-16): tarea Celery 'titular', cada 30 min.

Para cada uno de los 24 departamentos y el Callao escribe en la tabla titular_zona UNA frase en
lenguaje claro (240 caracteres como mucho) que resume lo que dicen HOY las fuentes oficiales:
alertas vigentes (alerta_actual: avisos de SENAMHI, ríos de ANA, lluvia medida sobre la
referencia), caudales (caudal_actual), lluvia de la última hora (lluvia_senamhi_actual), avisos
vigentes (aviso_vigente), el río vigilado (rio_senal) y el estado ENFEN (comunicado_enfen).
Además escribe titular_corto (MAX_CORTO = 110 caracteres, siempre por reglas: titular_corto()),
que es lo que la tarjeta "Tu zona ahora" del inicio puede mostrar en dos líneas
(frontend/src/hooks/useZonaAhora.js TITULAR_MAX): solo la frase principal (qué hay vigente, de
quién), sin El Niño, sin el río vigilado ni las fuentes, que van en titular y en detalle.

Cómo se arma (plan de seguridad del informe):
  1. Python calcula los INSUMOS: el nivel del semáforo (la misma regla que frontend/src/lib/nivel.js:
     la lluvia medida y un río muy bajo (vaciante) nunca pasan de 'aviso'; 'sin_dato' si no hay
     nada que revisar), cuántas alertas
     oficiales hay, qué ríos pasaron su nivel, cuánta lluvia se midió, qué señales tiene el río
     vigilado (lib/zonaRio.js) y el estado ENFEN (lib/lenguaje.js). El modelo NO calcula ni decide
     nada: solo redacta con esas cifras.
  2. Con clave de API (SIMPAC_LLM_KEY o ANTHROPIC_API_KEY) se pide la redacción a la API HTTP de
     Anthropic con temperature 0 y max_tokens 200, un pedido por departamento y SOLO si cambiaron
     sus insumos desde el titular guardado (huella = hash de los insumos sin las horas).
  3. La respuesta se valida: texto plano de una línea, sin URL ni emojis ni caracteres raros, 240
     caracteres como mucho, empieza con el nombre del departamento, cada número que trae aparece en
     los insumos, no afirma emergencia, desborde o inundación que las fuentes no indiquen ni
     "normal" o "tranquilo" cuando no hay datos. Si falla una sola regla se descarta y entra el
     respaldo.
  4. Respaldo determinista (origen 'reglas'): el titular lo arma Python con las mismas frases del
     frontend (nivel más alto vigente, cuántas alertas, el río vigilado si tiene señales, la lluvia
     medida como "atentos", El Niño en una frase corta). Es lo que sale sin clave.

Nunca borra: si la API falla y los insumos no cambiaron, el titular anterior se queda (solo se
anota la falla en el latido); si cambiaron, se escribe el de reglas (un titular viejo con datos
nuevos sería mentir). Las escrituras van en una sola transacción, después de todas las llamadas.

Resumen del latido 'titular':
  departamentos  cuántos se evaluaron (25)
  llm            titulares redactados por el modelo en esta corrida
  reglas         titulares escritos por reglas en esta corrida
  sin_cambio     insumos iguales: se conservó el titular (solo se refrescaron detalle, insumos y revisado_en)
  conservados    la API falló y los insumos no cambiaron: titular anterior intacto
  descartados    [{departamento, motivo}] textos del modelo que no pasaron la validación
  modelo         id del modelo usado (null sin clave)
  fallas         'migracion' (falta la tabla), 'llm' (alguna llamada falló)
  avisos         detalle de las fallas

Corrida suelta, dentro del contenedor worker:
    docker compose run --rm worker python -m backend.ingesta.titular
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone

from backend.config import ajustes
from backend.connectors.senamhi import HORA_PERU
from backend.db import conectar
from backend.ingesta.departamentos import DEPARTAMENTOS, clave, nombre_departamento
from backend.ingesta.guardar import SQL_LATIDO

log = logging.getLogger(__name__)

SERVICIO = "titular"
MAX_CARACTERES = 240
# titular_corto: lo que cabe en dos líneas de la tarjeta "Tu zona ahora" (useZonaAhora.js TITULAR_MAX).
MAX_CORTO = 110
# API HTTP de Anthropic (POST /v1/messages). La versión de la API es fija; el modelo viene de
# config.llm_modelo. temperature 0 para que la misma entrada dé el mismo texto.
API_URL = "https://api.anthropic.com/v1/messages"
VERSION_API = "2023-06-01"
MAX_TOKENS = 200
TEMPERATURA = 0
TIMEOUT_S = 20
# No se pide otro titular pasados estos segundos desde el inicio: la tarea tiene 120 s de soft
# limit (celery_app) y los departamentos que queden salen por reglas o conservan el anterior.
PLAZO_S = 90
# Tras estas fallas seguidas de la API (red caída, clave inválida, 429) no se insiste en la corrida.
MAX_FALLAS_SEGUIDAS = 3
MAX_AVISOS = 20
ZONAS = (*DEPARTAMENTOS.values(), "Callao")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic")
COLOR_AVISO = {"aviso": "amarillo", "alerta": "naranja", "emergencia": "rojo"}
ORDEN_NIVEL = ("sin_dato", "normal", "aviso", "alerta", "emergencia")
ORDEN_RIO = ("sin_senales", "atentos", "alerta", "emergencia")
DE_AVISO_HIDRO = {2: "atentos", 3: "alerta", 4: "emergencia"}
COLOR_HIDRO = {2: "amarillo", 3: "naranja", 4: "rojo"}
# Comunicados cada ~2 semanas: pasados 16 días el estado ENFEN se da con su fecha (puede haber uno nuevo).
ENFEN_ATRASADO_DIAS = 16

SQL_HAY_TABLA = "select to_regclass('public.titular_zona') is not null"
AVISO_SIN_TABLA = "titular_zona: falta la tabla (migración pendiente); no se escribió ningún titular"
SQL_CANDADO = "select pg_advisory_xact_lock(hashtext('titular'))"
SQL_ALERTAS = ("select tipo, referencia, zona, nivel, detalle, valor, umbral, ventana_h, ts "
               "from alerta_actual")
SQL_CAUDAL = ("select estacion, rio, departamento, fecha, hora, valor, unidad, umbral_alerta, "
              "umbral_emergencia, tendencia, estado from caudal_actual")
SQL_LLUVIA = ("select nombre, departamento, pp_1h, umbral_1h, pp_6h, umbral_6h, medido_en "
              "from lluvia_senamhi_actual")
SQL_AVISOS = ("select id, tipo, numero, nivel, titulo, tema, inicio, fin, en_curso, departamentos, ts_captura "
              "from aviso_vigente")
SQL_ENFEN = ("select anio, numero, extraordinario, fecha, estado, proximo from comunicado_enfen "
             "order by fecha desc, numero desc limit 1")
SQL_RIOS_VIGILADOS = ("select v.id, v.nombre, v.departamento, v.estacion_ana, v.rio_ana, "
                      "s.avisos_lluvia, s.lluvia_cuenca, s.avisos_hidro "
                      "from rio_vigilado v join rio_senal s on s.rio = v.id")
SQL_PREVIOS = ("select departamento, titular, origen, insumos->>'huella' as huella, "
               "insumos->>'llm_descartado' as llm_descartado from titular_zona")
SQL_TITULAR = """
insert into titular_zona (departamento, titular, titular_corto, detalle, nivel, generado_en, revisado_en, modelo, origen,
                          insumos)
values (%(departamento)s, %(titular)s, %(titular_corto)s, %(detalle)s, %(nivel)s, now(), now(), %(modelo)s, %(origen)s,
        %(insumos)s::jsonb)
on conflict (departamento) do update set
  titular = excluded.titular, titular_corto = excluded.titular_corto, detalle = excluded.detalle, nivel = excluded.nivel,
  generado_en = now(), revisado_en = now(), modelo = excluded.modelo, origen = excluded.origen, insumos = excluded.insumos
"""
# Insumos iguales: el titular y su generado_en se quedan; se refrescan las horas de las fuentes (y el
# corto, que sale de los insumos y puede faltar en filas escritas antes de la columna).
SQL_SIN_CAMBIO = ("update titular_zona set titular_corto = %(titular_corto)s, detalle = %(detalle)s, "
                  "insumos = %(insumos)s::jsonb, revisado_en = now() where departamento = %(departamento)s")


class RespuestaInvalida(ValueError):
    """El modelo respondió, pero el texto no sirve (se descarta y entra el respaldo)."""


def _error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _recortar(lista: list, maximo: int) -> list:
    if len(lista) <= maximo:
        return lista
    return lista[:maximo] + [f"... y {len(lista) - maximo} más"]


def _num(v) -> str:
    """12.0 -> '12'; 0.5 -> '0,5'; 86.18 -> '86,18' (coma decimal, como el frontend en es-PE)."""
    if v is None:
        return ""
    v = round(float(v), 2)
    return str(int(v)) if v == int(v) else f"{v:g}".replace(".", ",")


def _plural(k: int, uno: str, varios: str) -> str:
    return f"{k} {uno if k == 1 else varios}"


def _dia(d) -> str:
    """'14 oct' de un date, un datetime o un texto ISO ('2026-10-14')."""
    if isinstance(d, str):
        d = datetime.fromisoformat(d)
    return f"{d.day} {MESES[d.month - 1]}"


def _fecha(v) -> datetime | None:
    """Fecha de la BD (datetime) o de un JSON de PostGIS ('2026-10-03T06:30:00+00:00'); None si no se entiende."""
    if v is None or isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _hora_peru(v) -> str | None:
    """'14 oct 05:00' en hora de Perú (lo que se dice en el detalle); None sin fecha."""
    d = _fecha(v)
    if d is None:
        return None
    if d.tzinfo is not None:
        d = d.astimezone(HORA_PERU)
    return f"{_dia(d)} {d:%H:%M}"


def _sin_tildes(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def _filas(cur) -> list[dict]:
    columnas = [c[0] for c in cur.description]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


# ---------------------------------------------------------------------------------------
# Insumos: lo que Python calcula y el redactor (modelo o reglas) solo pone en palabras
# ---------------------------------------------------------------------------------------
def leer_crudo() -> dict | None:
    """Todo lo de la BD de una vez (una conexión, sin transacción abierta durante la red). None sin tabla."""
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_HAY_TABLA)
        if not cur.fetchone()[0]:
            return None
        crudo = {}
        for nombre, sql in (("alertas", SQL_ALERTAS), ("caudales", SQL_CAUDAL), ("lluvia", SQL_LLUVIA),
                            ("avisos", SQL_AVISOS), ("rios", SQL_RIOS_VIGILADOS), ("previos", SQL_PREVIOS)):
            cur.execute(sql)
            crudo[nombre] = _filas(cur)
        cur.execute(SQL_ENFEN)
        enfen = _filas(cur)
        crudo["enfen"] = enfen[0] if enfen else None
    crudo["previos"] = {p["departamento"]: p for p in crudo["previos"]}
    return crudo


def _nivel_efectivo(a: dict) -> str:
    """
    Como nivelEfectivo (lib/nivel.js): la lluvia medida es siempre 'aviso' (no es aviso oficial) y un
    río muy bajo (tipo nivel_bajo, vaciante de ANA) también, aunque ANA lo publique como alerta o
    emergencia: un río muy bajo no es una crecida ni pide evacuar, así que no puede mandar el color
    del semáforo ni encender el modo emergencia del inicio.
    """
    return "aviso" if a["tipo"] in ("lluvia", "nivel_bajo") else a["nivel"]


def nivel_de_alertas(alertas: list[dict]) -> str:
    """Como nivelDeAlertas (lib/nivel.js): el nivel efectivo más alto de las alertas vigentes."""
    efectivos = {_nivel_efectivo(a) for a in alertas}
    for nivel in ("emergencia", "alerta", "aviso"):
        if nivel in efectivos:
            return nivel
    return "normal"


def _estado_crecida(c: dict) -> str | None:
    """
    Estado de una estación de ANA con umbrales de crecida, como textoRio (lib/lenguaje.js):
    emergencia | alerta | atento (80 % del caudal de alerta o a menos de 50 cm del nivel; criterio
    SIMPAC) | normal. None si no se puede evaluar (sin dato, sin umbral) o si vigila nivel bajo.
    """
    v, ua, ue = c.get("valor"), c.get("umbral_alerta"), c.get("umbral_emergencia")
    if v is None or ua is None or (ue is not None and ue < ua):
        return None
    if ue is not None and v >= ue:
        return "emergencia"
    if v >= ua:
        return "alerta"
    if c.get("unidad") == "m³/s":
        return "atento" if v / ua >= 0.8 else "normal"
    return "atento" if ua - v <= 0.5 and c.get("rio") != "Titicaca" else "normal"


def _pasa_referencia(e: dict) -> tuple[bool, str | None]:
    """Misma regla que referenciaLluvia (lib/lenguaje.js) y backend/alerts.py: mayor estricto, referencia > 0."""
    p1, u1, p6, u6 = e.get("pp_1h"), e.get("umbral_1h"), e.get("pp_6h"), e.get("umbral_6h")
    evaluable = p1 is not None and u1 is not None and u1 > 0
    if evaluable and p1 > u1:
        return True, f"{e['nombre']}: {_num(p1)} mm en la última hora (referencia de SENAMHI: {_num(u1)} mm)"
    if evaluable and p6 is not None and u6 is not None and u6 > 0 and p6 > u6:
        return True, f"{e['nombre']}: {_num(p6)} mm en 6 horas (referencia de SENAMHI: {_num(u6)} mm)"
    return False, None


def _rio_vigilado(rio: dict, caudales: list[dict], ahora: datetime) -> dict:
    """Señales del río vigilado, como estadoZona (lib/zonaRio.js); solo lo que sube de nivel."""
    senales: list[tuple[str, str]] = []
    caudal = next((c for c in caudales if clave(c["estacion"] or "") == clave(rio.get("estacion_ana") or "")
                   and clave(c["rio"] or "") == clave(rio.get("rio_ana") or "")), None)
    if caudal:
        estado = _estado_crecida(caudal)
        medida = f"{_num(caudal['valor'])} {caudal['unidad']}"
        if estado == "emergencia":
            senales.append(("emergencia", f"pasó su nivel de emergencia según ANA: lleva {medida} y el nivel de "
                                          f"emergencia es {_num(caudal['umbral_emergencia'])} {caudal['unidad']}"))
        elif estado == "alerta":
            senales.append(("alerta", f"pasó su nivel de alerta según ANA: lleva {medida} y el nivel de alerta es "
                                      f"{_num(caudal['umbral_alerta'])} {caudal['unidad']}"))
        elif estado == "atento":
            senales.append(("atentos", f"está cerca de su nivel de alerta (lleva {medida}; el nivel de alerta de ANA es "
                                       f"{_num(caudal['umbral_alerta'])} {caudal['unidad']}; 'cerca' es un criterio de SIMPAC)"))
    hidros = [h for h in (rio.get("avisos_hidro") or [])
              if h.get("sentido") == "crecida" and h.get("nivel") in DE_AVISO_HIDRO
              and not (_fecha(h.get("fin")) and _fecha(h["fin"]) <= ahora)]
    if hidros:
        h = max(hidros, key=lambda x: x["nivel"])
        senales.append((DE_AVISO_HIDRO[h["nivel"]],
                        f"tiene aviso hidrológico {COLOR_HIDRO[h['nivel']]} de SENAMHI (N.º {h.get('numero')})"))
    fuertes = [a for a in (rio.get("avisos_lluvia") or []) if a.get("en_curso") and (a.get("nivel") or 0) >= 3]
    if fuertes:
        a = max(fuertes, key=lambda x: x["nivel"])
        senales.append(("atentos", f"hay aviso {COLOR_HIDRO[a['nivel']]} de SENAMHI por lluvias sobre su cuenca"))
    pasan = [txt for e in (rio.get("lluvia_cuenca") or []) for ok, txt in [_pasa_referencia(e)] if ok]
    if pasan:
        senales.append(("atentos", "se midió lluvia por encima de la referencia de SENAMHI en su cuenca ("
                                   + "; ".join(pasan[:2]) + (f" y {len(pasan) - 2} más" if len(pasan) > 2 else "")
                                   + "); no es un aviso oficial"))
    senales.sort(key=lambda s: -ORDEN_RIO.index(s[0]))
    nivel = senales[0][0] if senales else "sin_senales"
    return {"nombre": rio["nombre"], "nivel": nivel, "senales": [s[1] for s in senales],
            "medicion_ana": bool(caudal)}


def _enfen(c: dict | None, ahora: datetime) -> dict | None:
    """Estado ENFEN como textoEnfen (lib/lenguaje.js): corto, quién y la fecha del comunicado."""
    if not c:
        return None
    e = (c.get("estado") or "").lower()
    quien = "La Niña costera" if "niña" in e else "El Niño costero"
    if "no activo" in e:
        corto, frase = "sin alerta", "el sistema de alerta del ENFEN no está activo"
    elif "alerta" in e:
        corto, frase = "alerta", f"{quien} está en curso o es inminente"
    elif "vigilancia" in e:
        corto, frase = "vigilancia", f"{quien} podría desarrollarse en los próximos meses"
    else:
        corto, frase = c["estado"], c["estado"]
    fecha = c.get("fecha")
    dias = (ahora.astimezone(HORA_PERU).date() - fecha).days if fecha else None
    return {
        "estado": c["estado"], "corto": corto, "quien": quien, "frase": frase,
        "comunicado": f"{'CE' if c.get('extraordinario') else 'CO'} {c['numero']}-{c['anio']}",
        "fecha": fecha.isoformat() if fecha else None,
        "fecha_legible": _dia(fecha) if fecha else None,
        "atrasado": dias is not None and dias > ENFEN_ATRASADO_DIAS,
    }


def armar_insumos(depto: str, crudo: dict, ahora: datetime | None = None) -> dict:
    """
    Cifras y niveles de un departamento, listos para redactar. Función pura (sin BD): recibe las
    filas crudas (listas de dict por tabla) y devuelve el dict que se guarda en titular_zona.insumos
    (sin la huella, que se agrega al final). Lo que lleva hora va en 'horas', fuera de la huella.
    """
    ahora = ahora or datetime.now(timezone.utc)
    alertas = [a for a in crudo.get("alertas", []) if a.get("zona") == depto]
    caudales = [c for c in crudo.get("caudales", []) if nombre_departamento(c.get("departamento")) == depto]
    lluvia = [e for e in crudo.get("lluvia", []) if nombre_departamento(e.get("departamento")) == depto]

    # Avisos de SENAMHI: una alerta por aviso y departamento; aquí uno por referencia, con su nivel.
    avisos: dict[str, dict] = {}
    for a in alertas:
        if a["tipo"] != "aviso":
            continue
        previo = avisos.get(a["referencia"])
        if previo is None or ORDEN_NIVEL.index(a["nivel"]) > ORDEN_NIVEL.index(previo["nivel"]):
            avisos[a["referencia"]] = {"referencia": a["referencia"], "nivel": a["nivel"],
                                       "color": COLOR_AVISO.get(a["nivel"], a["nivel"]), "detalle": a.get("detalle")}
    rios_crecida = [{"referencia": a["referencia"], "nivel": a["nivel"], "detalle": a.get("detalle"),
                     "valor": a.get("valor"), "umbral": a.get("umbral")} for a in alertas if a["tipo"] == "caudal"]
    rios_bajos = [{"referencia": a["referencia"], "nivel": a["nivel"], "detalle": a.get("detalle"),
                   "valor": a.get("valor"), "umbral": a.get("umbral")} for a in alertas if a["tipo"] == "nivel_bajo"]
    sobre_ref: dict[str, dict] = {}
    for a in alertas:
        if a["tipo"] == "lluvia" and a["referencia"] not in sobre_ref:
            sobre_ref[a["referencia"]] = {"estacion": (a["referencia"] or "").split("@")[0], "detalle": a.get("detalle"),
                                          "valor": a.get("valor"), "umbral": a.get("umbral"), "ventana_h": a.get("ventana_h")}

    # Cobertura: ríos con nivel de alerta de ANA y estaciones de lluvia con dato de las últimas 3 h.
    estados = {c["estacion"]: _estado_crecida(c) for c in caudales}
    con_umbral = [c for c in caudales if c.get("umbral_alerta") is not None and c.get("valor") is not None]
    rios = {
        "estaciones": len(caudales),
        "con_nivel_de_alerta": len(con_umbral),
        "pasan_su_nivel": sum(1 for e in estados.values() if e in ("alerta", "emergencia")),
        "cerca_de_su_nivel": sum(1 for e in estados.values() if e == "atento"),
        "muy_bajos": len(rios_bajos),
    }
    con_dato = [e for e in lluvia if e.get("pp_1h") is not None]
    mas = max(con_dato, key=lambda e: e["pp_1h"], default=None)
    lluvia_resumen = {
        "estaciones": len(con_dato),
        "con_lluvia": sum(1 for e in con_dato if e["pp_1h"] > 0),
        "max_mm_hora": round(mas["pp_1h"], 1) if mas else None,
        "estacion_max": mas["nombre"] if mas and mas["pp_1h"] > 0 else None,
        "sobre_referencia": len(sobre_ref),
    }
    vigilados = [_rio_vigilado(r, caudales, ahora) for r in crudo.get("rios", []) if r.get("departamento") == depto]
    rio_vigilado = max(vigilados, key=lambda r: ORDEN_RIO.index(r["nivel"]), default=None)

    sin_cobertura = not rios["con_nivel_de_alerta"] and not lluvia_resumen["estaciones"]
    nivel = nivel_de_alertas(alertas) if alertas else ("sin_dato" if sin_cobertura else "normal")

    def ultima(filas, campo):
        fechas = [f for f in (_fecha(x.get(campo)) for x in filas) if f]
        return _hora_peru(max(fechas)) if fechas else None

    # la última lectura real de caudal_actual (fecha y hora de ANA, ya en hora de Perú)
    ultimo_caudal = max((c for c in caudales if c.get("fecha") and c.get("hora")),
                        key=lambda c: (str(c["fecha"]), c["hora"]), default=None)
    horas = {
        "alertas": ultima(alertas, "ts"),
        "caudal": f"{_dia(ultimo_caudal['fecha'])} {ultimo_caudal['hora']}" if ultimo_caudal else None,
        "lluvia": ultima(lluvia, "medido_en"),
        "avisos_leidos": ultima(crudo.get("avisos", []), "ts_captura"),
        "revisado": _hora_peru(ahora),
    }
    return {
        "departamento": depto,
        "nivel": nivel,
        "etiqueta": etiqueta(nivel, alertas),
        "alertas_oficiales": len(avisos) + len(rios_crecida) + len(rios_bajos),
        "avisos_senamhi": sorted(avisos.values(), key=lambda a: a["referencia"]),
        "rios_crecida": rios_crecida,
        "rios_bajos": rios_bajos,
        "lluvia_sobre_referencia": list(sobre_ref.values()),
        "rios": rios,
        "lluvia": lluvia_resumen,
        "rio_vigilado": rio_vigilado,
        "enfen": _enfen(crudo.get("enfen"), ahora),
        "horas": horas,
    }


def etiqueta(nivel: str, alertas: list[dict]) -> str:
    """
    Rótulo del nivel, como etiqueta (lib/nivel.js): 'Aviso naranja', 'Atentos a la lluvia', 'Río muy
    bajo' (si el nivel sale solo de ríos en vaciante) o el del semáforo.
    """
    nombres = {"normal": "Normal", "aviso": "Aviso", "alerta": "Alerta", "emergencia": "Emergencia", "sin_dato": "Sin datos"}
    de_ese = [a for a in alertas if _nivel_efectivo(a) == nivel]
    if not de_ese:
        return nombres[nivel]
    if all(a["tipo"] == "nivel_bajo" for a in de_ese):
        return "Río muy bajo" if len(de_ese) == 1 else "Ríos muy bajos"
    if any(a["tipo"] not in ("aviso", "lluvia") for a in de_ese):
        return nombres[nivel]
    if any(a["tipo"] == "aviso" for a in de_ese):
        return f"Aviso {COLOR_AVISO[nivel]}"
    return "Atentos a la lluvia"


# Lo que NO entra en la huella: las horas de las fuentes (cambian en cada corrida sin que cambie
# nada de fondo) y lo que la propia tarea anota (la huella y el motivo de un descarte del modelo).
FUERA_DE_HUELLA = ("horas", "huella", "llm_descartado")


def huella(insumos: dict) -> str:
    """Hash de los insumos sin las horas: si no cambia, no se vuelve a redactar (ni se llama al modelo)."""
    estables = {k: v for k, v in insumos.items() if k not in FUERA_DE_HUELLA}
    return hashlib.sha256(json.dumps(estables, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------------------
# Respaldo determinista (origen 'reglas'): las mismas frases que el frontend
# ---------------------------------------------------------------------------------------
def _describir(i: dict) -> str:
    """Como describir (lib/nivel.js): 'aviso amarillo de SENAMHI por lluvias, 1 río en emergencia y ...'."""
    partes = []
    avisos = i["avisos_senamhi"]
    if avisos:
        peor = max((a["nivel"] for a in avisos), key=ORDEN_NIVEL.index)
        partes.append(f"aviso {COLOR_AVISO[peor]} de SENAMHI por lluvias, vigente o por empezar" if len(avisos) == 1
                      else f"{len(avisos)} avisos de SENAMHI por lluvias, vigentes o por empezar (el más alto, {COLOR_AVISO[peor]})")
    for nivel in ("emergencia", "alerta"):
        k = sum(1 for r in i["rios_crecida"] if r["nivel"] == nivel)
        if k:
            partes.append(f"{_plural(k, 'río', 'ríos')} en {nivel} según ANA")
    if i["rios_bajos"]:
        partes.append(_plural(len(i["rios_bajos"]), "río muy bajo", "ríos muy bajos") + " según ANA")
    k = len(i["lluvia_sobre_referencia"])
    if k:
        partes.append(f"lluvia por encima de la referencia de SENAMHI en {_plural(k, 'estación', 'estaciones')}")
    if len(partes) > 1:
        return ", ".join(partes[:-1]) + " y " + partes[-1]
    return partes[0] if partes else ""


def _frase_principal(i: dict) -> str:
    d = i["departamento"]
    if i["alertas_oficiales"] or i["lluvia_sobre_referencia"]:
        return f"{d}: {_describir(i)}."
    r, l = i["rios"], i["lluvia"]
    if i["nivel"] == "sin_dato":
        return (f"{d}: sin avisos de SENAMHI vigentes. SIMPAC no tiene aquí ríos con nivel de alerta de ANA "
                "ni estaciones de SENAMHI con lluvia reciente que pueda revisar.")
    partes = []
    if r["con_nivel_de_alerta"]:
        partes.append("su río con nivel de alerta de ANA no lo pasa" if r["con_nivel_de_alerta"] == 1
                      else f"ninguno de sus {r['con_nivel_de_alerta']} ríos con nivel de alerta de ANA lo pasa")
    if l["estaciones"]:
        partes.append("su estación de lluvia con dato reciente no pasa la referencia de SENAMHI" if l["estaciones"] == 1
                      else f"ninguna de sus {l['estaciones']} estaciones de lluvia con dato reciente pasa la referencia de SENAMHI")
    return f"{d}: sin avisos de SENAMHI; {', y '.join(partes)}."


def _frase_rio(i: dict) -> str | None:
    rio = i.get("rio_vigilado")
    if not rio or rio["nivel"] == "sin_senales":
        return None
    return f"{rio['nombre']}: {rio['senales'][0]}."


def _frase_cerca(i: dict) -> str | None:
    k = i["rios"]["cerca_de_su_nivel"]
    if not k or i["rios_crecida"]:
        return None
    return f"{_plural(k, 'río está cerca', 'ríos están cerca')} de su nivel de alerta de ANA (criterio de SIMPAC)."


def _frase_lluvia(i: dict) -> str | None:
    l = i["lluvia"]
    if not l["estaciones"]:
        return None
    if not l["con_lluvia"]:
        return f"En la última hora no llovió en ninguna de sus {l['estaciones']} estaciones de SENAMHI con dato."
    return (f"En la última hora llovió en {l['con_lluvia']} de sus {l['estaciones']} estaciones de SENAMHI "
            f"(lo más: {_num(l['max_mm_hora'])} mm en {l['estacion_max']}).")


def _frase_enfen(i: dict) -> str:
    e = i.get("enfen")
    if not e:
        return "ENFEN: sin comunicado leído."
    fecha = f" del {e['fecha_legible']}" if e["atrasado"] and e.get("fecha_legible") else ""
    if e["corto"] == "sin alerta":
        return f"ENFEN: sin alerta de El Niño ni La Niña (comunicado{fecha})."
    return f"{e['quien']}: {e['corto']} según el ENFEN (comunicado{fecha})."


def _frase_fuentes(i: dict) -> str:
    h = i["horas"]
    partes = []
    if h.get("avisos_leidos") or h.get("alertas"):
        partes.append(f"avisos de SENAMHI leídos el {h.get('avisos_leidos') or h.get('alertas')}")
    if h.get("caudal"):
        partes.append(f"caudales de ANA del {h['caudal']}")
    if h.get("lluvia"):
        partes.append(f"lluvia de SENAMHI hasta las {h['lluvia'].split(' ')[-1]} del {h['lluvia'].split(' ')[0]} {h['lluvia'].split(' ')[1]}")
    e = i.get("enfen")
    if e:
        partes.append(f"comunicado ENFEN {e['comunicado']} del {e['fecha_legible']}")
    return "Fuentes (hora de Perú): " + "; ".join(partes) + "." if partes else "Fuentes: sin datos recientes."


def _acortar(texto: str, maximo: int = MAX_CARACTERES) -> str:
    if len(texto) <= maximo:
        return texto
    corte = texto[: maximo - 1].rsplit(" ", 1)[0]
    return corte.rstrip(" ,;:") + "…"


def titular_reglas(i: dict) -> tuple[str, str]:
    """
    (titular, detalle) deterministas. El titular junta la frase principal, el río vigilado si tiene
    señales y El Niño en corto; si no cabe en 240 caracteres se quitan frases desde el final (la
    principal nunca). El detalle lleva todo, más la lluvia medida y las fuentes con su hora.
    """
    principal = _frase_principal(i)
    opcionales = [f for f in (_frase_rio(i), _frase_cerca(i), _frase_enfen(i)) if f]
    frases = [principal, *opcionales]
    while len(" ".join(frases)) > MAX_CARACTERES and len(frases) > 1:
        frases.pop()
    titular = _acortar(" ".join(frases))
    detalle = " ".join(f for f in (principal, _frase_rio(i), _frase_cerca(i), _frase_lluvia(i), _frase_enfen(i),
                                   _frase_fuentes(i)) if f)
    return titular, detalle


def _unir(partes: list[str]) -> str:
    return ", ".join(partes[:-1]) + " y " + partes[-1] if len(partes) > 1 else partes[0]


def _partes_cortas(i: dict) -> list[tuple[str, str]]:
    """[(nivel, frase)] de lo vigente, en las palabras más cortas que no pierden la fuente; de mayor a menor nivel."""
    partes: list[tuple[str, str]] = []
    avisos = i["avisos_senamhi"]
    if avisos:
        peor = max((a["nivel"] for a in avisos), key=ORDEN_NIVEL.index)
        partes.append((peor, f"aviso {COLOR_AVISO[peor]} de SENAMHI por lluvias" if len(avisos) == 1
                       else f"{len(avisos)} avisos de SENAMHI por lluvias (el más alto, {COLOR_AVISO[peor]})"))
    for nivel in ("emergencia", "alerta"):
        k = sum(1 for r in i["rios_crecida"] if r["nivel"] == nivel)
        if k:
            partes.append((nivel, f"{_plural(k, 'río', 'ríos')} en {nivel} según ANA"))
    if i["rios_bajos"]:
        partes.append(("aviso", _plural(len(i["rios_bajos"]), "río muy bajo", "ríos muy bajos") + " según ANA"))
    k = len(i["lluvia_sobre_referencia"])
    if k:
        partes.append(("aviso", f"lluvia sobre la referencia de SENAMHI en {_plural(k, 'estación', 'estaciones')}"))
    return sorted(partes, key=lambda p: -ORDEN_NIVEL.index(p[0]))


def titular_corto(i: dict) -> str:
    """
    La frase principal en MAX_CORTO caracteres como mucho, siempre por reglas (el modelo no la
    redacta): qué hay vigente y de quién, sin El Niño, sin el río vigilado ni las fuentes (están en
    titular y detalle). Con alertas, lo más grave primero; si no cabe todo, se quitan las partes de
    menor nivel desde el final (el semáforo y el contador de la tarjeta no dependen de este texto).
    Sin alertas dice qué se revisó; sin nada que revisar lo dice (nunca "normal" por lo no medido).
    """
    d = i["departamento"]
    partes = [frase for _, frase in _partes_cortas(i)]
    if partes:
        texto = f"{d}: {_unir(partes)}."
        while len(texto) > MAX_CORTO and len(partes) > 1:
            partes.pop()
            texto = f"{d}: {_unir(partes)}."
        return _acortar(texto, MAX_CORTO)
    if i["nivel"] == "sin_dato":
        return _acortar(f"{d}: sin avisos de SENAMHI; SIMPAC no tiene aquí ríos ni estaciones de lluvia que pueda revisar.",
                        MAX_CORTO)
    r, l = i["rios"]["con_nivel_de_alerta"], i["lluvia"]["estaciones"]
    if r and l:
        que = f"{_plural(r, 'río', 'ríos')} de ANA y {_plural(l, 'estación', 'estaciones')} de lluvia sin pasar su nivel"
    elif r:
        que = "su río de ANA no pasa su nivel de alerta" if r == 1 else f"ninguno de sus {r} ríos de ANA pasa su nivel de alerta"
    else:
        que = ("su estación de lluvia no pasa la referencia de SENAMHI" if l == 1
               else f"ninguna de sus {l} estaciones de lluvia pasa la referencia de SENAMHI")
    return _acortar(f"{d}: sin avisos de SENAMHI; {que}.", MAX_CORTO)


# ---------------------------------------------------------------------------------------
# Redacción con el modelo: prompt con las cifras fijadas y validación de la salida
# ---------------------------------------------------------------------------------------
SISTEMA = (
    "Eres el redactor de SIMPAC, un servicio público del Perú que resume el estado hidrometeorológico de cada "
    "departamento para personas sin formación técnica. Escribe UN solo titular en español del Perú, en lenguaje "
    "claro y directo, de 240 caracteres como máximo, en un solo párrafo, sin emojis, sin enlaces, sin comillas, "
    "sin listas ni saltos de línea. Usa SOLO los hechos que recibes: no calcules, no agregues cifras, lugares, "
    "causas, pronósticos ni consecuencias que no estén en los hechos; cada número que escribas tiene que aparecer "
    "tal cual en los hechos (escribe los decimales con coma). No digas que hay peligro, emergencia, desborde o "
    "inundación si los hechos no lo dicen. Si los hechos dicen que no hay datos, no digas que todo está normal "
    "ni tranquilo. Empieza con el nombre del departamento seguido de dos puntos y nombra la fuente de cada hecho "
    "(SENAMHI, ANA, ENFEN). Responde solo con el titular, nada más."
)


def hechos(i: dict) -> str:
    """Los insumos como líneas en español: es lo único que el modelo puede poner en palabras."""
    lineas = [f"Departamento: {i['departamento']}",
              f"Nivel general calculado por SIMPAC: {i['nivel']} (rótulo: {i['etiqueta']})",
              f"Alertas y avisos oficiales vigentes: {i['alertas_oficiales']}"]
    for a in i["avisos_senamhi"]:
        lineas.append(f"Aviso de SENAMHI ({a['referencia']}), color {a['color']}: {a['detalle']}")
    for r in i["rios_crecida"]:
        lineas.append(f"Río que pasó su nivel de {r['nivel']} según ANA ({r['referencia']}): {r['detalle']}")
    for r in i["rios_bajos"]:
        # sin la palabra del nivel de ANA (alerta/emergencia): un río muy bajo no es una emergencia de crecida
        lineas.append(f"Río muy bajo (vaciante) según ANA ({r['referencia']}): {r['detalle']}")
    for e in i["lluvia_sobre_referencia"]:
        lineas.append(f"Estación de SENAMHI que midió más lluvia que su referencia (no es aviso oficial): {e['detalle']}")
    r, l = i["rios"], i["lluvia"]
    lineas.append(f"Ríos de ANA en el departamento: {r['estaciones']} estaciones, {r['con_nivel_de_alerta']} con nivel "
                  f"de alerta; {r['pasan_su_nivel']} lo pasan; {r['cerca_de_su_nivel']} cerca de su nivel (criterio SIMPAC)")
    if l["estaciones"]:
        lineas.append(f"Lluvia de SENAMHI en la última hora: {l['con_lluvia']} de {l['estaciones']} estaciones con lluvia; "
                      f"máximo {_num(l['max_mm_hora'])} mm" + (f" en {l['estacion_max']}" if l["estacion_max"] else "")
                      + f"; {l['sobre_referencia']} pasan su referencia")
    else:
        lineas.append("Lluvia de SENAMHI en la última hora: sin estaciones con dato reciente en el departamento")
    rio = i.get("rio_vigilado")
    if rio:
        lineas.append(f"Río vigilado {rio['nombre']}: nivel {rio['nivel']}"
                      + (": " + "; ".join(rio["senales"]) if rio["senales"] else " (sin señales de crecida ahora)"))
    e = i.get("enfen")
    lineas.append(f"ENFEN: {e['estado']} ({e['frase']}), comunicado {e['comunicado']} del {e['fecha_legible']}"
                  + (" (puede haber uno más nuevo)" if e["atrasado"] else "") if e else "ENFEN: sin comunicado leído")
    lineas.append(f"Titular de referencia escrito por reglas (puedes mejorarlo sin cambiar ningún hecho): {titular_reglas(i)[0]}")
    return "\n".join("- " + x for x in lineas)


def cuerpo_pedido(i: dict, modelo: str) -> dict:
    return {
        "model": modelo,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURA,
        "system": SISTEMA,
        "messages": [{"role": "user", "content": f"Hechos de hoy:\n{hechos(i)}\n\nEscribe el titular."}],
    }


def pedir_llm(i: dict, clave_api: str, modelo: str, abrir=urllib.request.urlopen) -> str:
    """
    Un pedido a la API de mensajes de Anthropic (urllib, sin SDK). Devuelve el texto tal cual; las
    fallas de red o HTTP salen como excepción (RuntimeError con el estado y el inicio del cuerpo).
    """
    datos = json.dumps(cuerpo_pedido(i, modelo), ensure_ascii=False).encode("utf-8")
    pedido = urllib.request.Request(API_URL, data=datos, method="POST", headers={
        "x-api-key": clave_api,
        "anthropic-version": VERSION_API,
        "content-type": "application/json",
        "User-Agent": "SIMPAC-titular/1.0 (+https://github.com/Federjj/SIMPAC)",
    })
    try:
        with abrir(pedido, timeout=TIMEOUT_S) as r:
            respuesta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        cuerpo = e.read()[:300].decode("utf-8", "replace") if e.fp else ""
        e.close()
        raise RuntimeError(f"HTTP {e.code} de la API: {cuerpo}") from e
    return texto_de_respuesta(respuesta)


def texto_de_respuesta(respuesta: dict) -> str:
    """El texto de la respuesta; RespuestaInvalida si vino cortada, rechazada o sin texto."""
    parada = respuesta.get("stop_reason")
    if parada != "end_turn":
        raise RespuestaInvalida(f"stop_reason {parada!r} (se esperaba end_turn)")
    textos = [b.get("text", "") for b in respuesta.get("content", []) if b.get("type") == "text"]
    if not any(t.strip() for t in textos):
        raise RespuestaInvalida("la respuesta no trae texto")
    return "\n".join(textos)


_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")
_URL = re.compile(r"(https?://|www\.|\.(com|pe|org|gob|net)\b)", re.I)
# Letras (con tildes y ñ), dígitos, espacios y la puntuación de un titular; fuera emojis, símbolos y marcas.
_PERMITIDO = re.compile(r"^[\w\s.,;:()¿?¡!%°º/'\"“”‘’«»\-–—+ª³…]*$", re.UNICODE)
# Palabras que afirman un peligro mayor que el nivel calculado.
_GRAVES = re.compile(r"\b(emergencia|desbord\w*|inunda\w*|evacu\w*|huai?co\w*|damnificad\w*|muert\w*|fallecid\w*)\b", re.I)
_PELIGRO = re.compile(r"\b(peligro\w*|riesgo\w*|alarma\w*|catástrofe|catastrof\w*)\b", re.I)
_TRANQUILO = re.compile(r"\b(normal\w*|tranquil\w*|calma|sin novedad\w*|sin alertas?|sin peligro|sin riesgo)\b", re.I)


def _numeros(texto: str) -> set[str]:
    """{'0.5', '14', '86.18'} de un texto, con el mismo formato en los dos lados de la comparación."""
    salida = set()
    for m in _NUMERO.findall(texto or ""):
        v = float(m.replace(",", "."))
        salida.add(str(int(v)) if v == int(v) else repr(v))
    return salida


def validar(texto: str, i: dict) -> str:
    """
    Titular del modelo limpio (espacios colapsados) si pasa todas las reglas; RespuestaInvalida con el
    motivo si no. Las reglas: texto plano de una línea, 240 caracteres como mucho, sin URL ni caracteres
    fuera de los de un titular, empieza con el departamento, cada número aparece en los insumos, no
    afirma emergencia, desborde o inundación que el nivel no respalde, no dice "normal" sin datos ni
    "sin alertas" con alertas.
    """
    limpio = re.sub(r"\s+", " ", (texto or "")).strip().strip("\"“”")
    if not limpio:
        raise RespuestaInvalida("texto vacío")
    if len(limpio) > MAX_CARACTERES:
        raise RespuestaInvalida(f"{len(limpio)} caracteres (máximo {MAX_CARACTERES})")
    if _URL.search(limpio):
        raise RespuestaInvalida("trae una URL o un dominio")
    if not _PERMITIDO.match(limpio):
        raise RespuestaInvalida("trae emojis, símbolos o marcas de formato")
    if not _sin_tildes(limpio).startswith(_sin_tildes(i["departamento"])):
        raise RespuestaInvalida("no empieza con el nombre del departamento")
    # la huella (hex) y el motivo de un descarte previo no son cifras de las fuentes
    cifras = {k: v for k, v in i.items() if k not in ("huella", "llm_descartado")}
    permitidos = _numeros(json.dumps(cifras, ensure_ascii=False, default=str)) | _numeros(hechos(i))
    sobran = sorted(_numeros(limpio) - permitidos)
    if sobran:
        raise RespuestaInvalida(f"cifras que no están en los insumos: {', '.join(sobran)}")
    nivel = i["nivel"]
    rio = i.get("rio_vigilado") or {}
    peor = max([nivel, {"emergencia": "emergencia", "alerta": "alerta", "atentos": "aviso"}.get(rio.get("nivel"), "normal")],
               key=ORDEN_NIVEL.index)
    if peor != "emergencia" and _GRAVES.search(limpio):
        raise RespuestaInvalida(f"afirma algo grave que las fuentes no indican: {_GRAVES.search(limpio).group(0)}")
    if peor in ("normal", "sin_dato") and _PELIGRO.search(limpio):
        raise RespuestaInvalida(f"habla de peligro sin ninguna alerta: {_PELIGRO.search(limpio).group(0)}")
    # "sin alerta de El Niño ni La Niña" es el estado del ENFEN, no una afirmación sobre la zona
    sin_enfen = re.sub(r"\bsin alerta de El Niño[^.;]*", "", limpio, flags=re.I)
    if nivel == "sin_dato" and _TRANQUILO.search(sin_enfen):
        raise RespuestaInvalida(f"dice '{_TRANQUILO.search(sin_enfen).group(0)}' sin datos para afirmarlo")
    if nivel in ("aviso", "alerta", "emergencia") and re.search(r"\bsin (alertas?|avisos?)\b", sin_enfen, re.I):
        raise RespuestaInvalida("dice que no hay alertas o avisos y sí los hay")
    return limpio


# ---------------------------------------------------------------------------------------
# Tarea
# ---------------------------------------------------------------------------------------
def _latido(resumen: dict) -> None:
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_LATIDO, (SERVICIO, json.dumps(resumen, ensure_ascii=False)))


def _resumen(fallas: list[str], avisos: list[str], **datos) -> dict:
    base = {"departamentos": 0, "llm": 0, "reglas": 0, "sin_cambio": 0, "conservados": 0, "descartados": [], "modelo": None}
    return {**base, **datos, "fallas": fallas, "avisos": _recortar(avisos, MAX_AVISOS)}


def redactar(insumos: dict, previo: dict | None, clave_api: str, modelo: str, estado: dict,
             abrir=urllib.request.urlopen) -> dict | None:
    """
    Qué escribir para un departamento: dict con titular, titular_corto, detalle, nivel, origen, modelo
    e insumos (para SQL_TITULAR), dict con solo titular_corto, detalle e insumos y 'sin_cambio' True
    (para SQL_SIN_CAMBIO), o None si la API falló y el titular anterior se conserva intacto. `estado` acumula fallas seguidas,
    descartados y avisos entre departamentos; `abrir` se reemplaza en las pruebas.
    """
    insumos = {**insumos, "huella": huella(insumos)}
    titular, detalle = titular_reglas(insumos)
    corto = titular_corto(insumos)
    igual = previo is not None and previo.get("huella") == insumos["huella"]
    datos = {"departamento": insumos["departamento"], "titular": titular, "titular_corto": corto, "detalle": detalle,
             "nivel": insumos["nivel"], "origen": "reglas", "modelo": None,
             "insumos": json.dumps(insumos, ensure_ascii=False, default=str)}
    # Con clave: se llama si cambiaron los insumos, o si el titular guardado salió por reglas sin que
    # el modelo lo haya intentado con estos mismos insumos (no había clave o la API falló). Un texto
    # descartado NO se vuelve a pedir hasta que cambien los insumos: con temperature 0 la misma
    # entrada da el mismo texto, y repetirlo cada 30 min solo gastaría.
    reintentar = igual and previo.get("origen") != "llm" and not previo.get("llm_descartado")
    llamar = bool(clave_api) and (not igual or reintentar) \
        and estado["fallas_seguidas"] < MAX_FALLAS_SEGUIDAS and time.monotonic() - estado["inicio"] < PLAZO_S
    if llamar:
        try:
            texto = validar(pedir_llm(insumos, clave_api, modelo, abrir), insumos)
        except RespuestaInvalida as e:
            estado["fallas_seguidas"] = 0
            estado["descartados"].append({"departamento": insumos["departamento"], "motivo": str(e)})
            insumos["llm_descartado"] = str(e)
            datos["insumos"] = json.dumps(insumos, ensure_ascii=False, default=str)
            log.warning("Titular %s: texto del modelo descartado (%s); se usa el de reglas", insumos["departamento"], e)
        except Exception as e:
            estado["fallas_seguidas"] += 1
            estado["avisos"].append(f"{insumos['departamento']}: {_error(e)}")
            log.warning("Titular %s: falló la API (%s)", insumos["departamento"], _error(e))
            if igual:
                return None   # se conserva el anterior tal cual
        else:
            estado["fallas_seguidas"] = 0
            return {**datos, "titular": texto, "origen": "llm", "modelo": modelo}
    if igual:
        return {"departamento": insumos["departamento"], "titular_corto": corto, "detalle": detalle,
                "insumos": datos["insumos"], "sin_cambio": True}
    return datos


def actualizar(ahora: datetime | None = None, abrir=urllib.request.urlopen) -> dict:
    """Tarea 'titular' (Celery la llama sin argumentos; `ahora` y `abrir` son para las pruebas)."""
    ahora = ahora or datetime.now(timezone.utc)
    cfg = ajustes()
    clave_api, modelo = cfg.llm_key, cfg.llm_modelo
    crudo = leer_crudo()
    if crudo is None:
        resumen = _resumen(["migracion"], [AVISO_SIN_TABLA])
        _latido(resumen)
        log.warning("Titular: %s", AVISO_SIN_TABLA)
        return resumen

    estado = {"inicio": time.monotonic(), "fallas_seguidas": 0, "descartados": [], "avisos": []}
    nuevos, sin_cambio, conservados = [], [], []
    for depto in ZONAS:
        r = redactar(armar_insumos(depto, crudo, ahora), crudo["previos"].get(depto), clave_api, modelo, estado, abrir)
        if r is None:
            conservados.append(depto)
        elif r.get("sin_cambio"):
            sin_cambio.append(r)
        else:
            nuevos.append(r)

    fallas = ["llm"] if estado["avisos"] else []
    if not clave_api:
        estado["avisos"].append("sin clave de API (SIMPAC_LLM_KEY): titulares por reglas")
    if estado["fallas_seguidas"] >= MAX_FALLAS_SEGUIDAS:
        estado["avisos"].append(f"la API falló {MAX_FALLAS_SEGUIDAS} veces seguidas: el resto salió por reglas o conservó el anterior")
    resumen = _resumen(fallas, estado["avisos"], departamentos=len(ZONAS),
                       llm=sum(1 for r in nuevos if r["origen"] == "llm"),
                       reglas=sum(1 for r in nuevos if r["origen"] == "reglas"),
                       sin_cambio=len(sin_cambio), conservados=len(conservados),
                       descartados=estado["descartados"], modelo=modelo if clave_api else None)
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_CANDADO)
        if nuevos:
            cur.executemany(SQL_TITULAR, nuevos)
        if sin_cambio:
            cur.executemany(SQL_SIN_CAMBIO, sin_cambio)
        cur.execute(SQL_LATIDO, (SERVICIO, json.dumps(resumen, ensure_ascii=False)))
    if fallas:
        log.warning("Titular con fallas: %s", resumen)
    else:
        log.info("Titular: %s", resumen)
    return resumen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    actualizar()
