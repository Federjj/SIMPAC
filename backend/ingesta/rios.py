"""
Avisos hidrológicos de SENAMHI para los ríos vigilados -> tabla aviso_hidrologico (vistas
aviso_hidrologico_vigente y rio_senal para el frontend).

La tarea 'rios' (cada hora) llama a actualizar(), que:
  1. Lee las estaciones SENAMHI de rio_vigilado (hoy solo el Mashcón, '220213') y qué avisos
     ya tienen el detalle guardado (inicio no nulo), con su fin y su nivel.
  2. Baja la lista de avisos de los últimos 12 meses de todo el país (una petición de ~700 KB;
     backend/connectors/senamhi_avisos_hidro.py) y la valida: con menos de MIN_FILAS filas la
     página cambió o vino cortada y no se escribe nada.
  3. Baja el detalle (hora, caudal, áreas que podrían verse afectadas, umbral rojo) solo de
     los avisos vigentes de las estaciones vigiladas que aún no lo tienen, o cuyo fin o nivel
     cambió en la lista desde que se leyó (SENAMHI corrigió o extendió el aviso): MAX_DETALLES
     como máximo, en serie y con pausa (cada detalle pesa lo mismo que la lista). Un dato que
     no cuadra con la lista (fin de otro día, valor más de 10 veces el umbral) no se guarda.
     Todo antes de abrir la transacción.
  4. En una transacción (con un candado para que dos corridas no se pisen): upsert de todas
     las filas de la lista (sin pisar las columnas del detalle, con visto_en = now()), marca
     como no vigentes los que ya no figuran como vigentes (salvo que la vigencia sea ambigua),
     guarda los detalles y purga los avisos que terminaron hace más de DIAS_PURGA días.

La tarea no crea filas en `alerta`: el contador y el badge no cambian (decisión del 03-10-2026).
El aviso hidrológico solo enciende la zona del río en el frontend (lib/zonaRio.js, vía rio_senal).

Regla de "no borrar": con la lista caída o rara no se escribe ni se borra nada, y la vista
aviso_hidrologico_vigente sigue mostrando un aviso con fin conocido hasta ese fin aunque SENAMHI
no responda (sin fin conocido, hasta 3 h después de la última lectura de la lista). Si el texto
"(vigente)" y la marca de la fila no coinciden, no se apaga ningún aviso. Un detalle que falla
no frena al resto ni a la lista, y se vuelve a pedir en la próxima corrida.

Resumen del latido 'rios':
  filas       avisos legibles de la lista (None si no se pudo bajar)
  vigentes    de ellos, cuántos dicen "(vigente)" (de todo el país)
  vigilados   [{ce, numero, nivel, vigente, fin_dia}] de las estaciones vigiladas: los vigentes
              y el último de cada estación
  detalles    ca de los avisos cuyo detalle se leyó y guardó en esta corrida
  purgados    avisos borrados por antigüedad
  fallas      'migracion' (faltan las tablas), 'lista' (caída), 'lista_rara' (menos de
              MIN_FILAS filas: no se escribe), 'vigente_ambiguo' (el texto y la marca de
              vigencia no coinciden: no se apagó ningún aviso), 'detalle:<ca>' (ese detalle
              no se pudo leer)
  avisos      detalle: errores, detalles pendientes, campos que no se encontraron o que no
              cuadran con la lista...
  atribucion  leyenda literal que exigen los términos de uso de SENAMHI

Si falla la lista, el latido lo registra y la tarea termina con excepción (Celery la marca
como fallida); si falla un detalle, sigue con los demás.

Corrida suelta, dentro del contenedor worker:
    docker compose run --rm worker python -m backend.ingesta.rios
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone

from backend.connectors import senamhi_avisos_hidro as fuente
from backend.connectors.senamhi import HORA_PERU
from backend.connectors.senamhi_avisos import ATRIBUCION
from backend.db import conectar
from backend.ingesta.guardar import SQL_LATIDO

log = logging.getLogger(__name__)

SERVICIO = "rios"
MIN_FILAS = 500         # la lista trae ~1680 avisos (12 meses de todo el país): con menos vino cortada
MAX_DETALLES = 10       # detalles por corrida: cada uno pesa ~700 KB
DIAS_PURGA = 400        # la lista trae 12 meses: lo que terminó hace más ya no vuelve
MAX_AVISOS = 20
# No se pide otro detalle pasados estos segundos desde el inicio de la tarea: con SENAMHI
# colgado un pedido tarda hasta ~96 s (3 intentos de 30 s, _http.con_reintentos) y la tarea
# tiene 240 s (celery_app); así el latido se escribe siempre.
PLAZO_S = 100
# Sin estos campos el detalle no se entendió (no se guarda); sin alguno, se guarda con un aviso.
CAMPOS_DETALLE = ("inicio", "fin", "valor", "umbral_rojo")
# Un valor registrado más de estas veces el umbral rojo es un error de lectura (coma decimal,
# otra unidad...): el récord del Mashcón es 79,31 m3/s con umbral 18 (4,4 veces).
MAX_VECES_UMBRAL = 10

# La migración puede no estar aplicada todavía (el worker se despliega aparte).
SQL_HAY_TABLA = ("select to_regclass('public.aviso_hidrologico') is not null "
                 "and to_regclass('public.rio_vigilado') is not null")
AVISO_SIN_TABLA = ("aviso_hidrologico / rio_vigilado: faltan las tablas (migración pendiente); "
                   "no se consultó ni se guardó nada")
SQL_VIGILADAS = "select distinct estacion_senamhi from rio_vigilado where estacion_senamhi is not null"
# Avisos con detalle: su fin (día de Lima) y su nivel, para volver a leerlo si la lista los cambia.
SQL_CON_DETALLE = ("select ca, (fin at time zone 'America/Lima')::date, nivel from aviso_hidrologico "
                   "where inicio is not null")
# Primera sentencia de la transacción de escritura: pone en serie el beat y una corrida suelta.
SQL_CANDADO = "select pg_advisory_xact_lock(hashtext('rios'))"
# Solo las columnas de la lista: el detalle (emision ... significado_rojo) no se pisa. Una fila
# sin nivel (pasa) no borra el que vino del detalle.
SQL_AVISO = """
insert into aviso_hidrologico (ca, ce, numero, titulo, nivel, sentido, inicio_dia, fin_dia, duracion_h,
                               vigente, url, visto_en)
values (%(ca)s, %(ce)s, %(numero)s, %(titulo)s, %(nivel)s, %(sentido)s, %(inicio_dia)s, %(fin_dia)s,
        %(duracion_h)s, %(vigente)s, %(url)s, now())
on conflict (ca) do update set
  ce = excluded.ce, numero = excluded.numero, titulo = excluded.titulo,
  nivel = coalesce(excluded.nivel, aviso_hidrologico.nivel),
  sentido = excluded.sentido, inicio_dia = excluded.inicio_dia, fin_dia = excluded.fin_dia,
  duracion_h = excluded.duracion_h, vigente = excluded.vigente, url = excluded.url,
  visto_en = now(), ts_captura = now()
"""
# Los que ya no figuran como vigentes (también los que salieron de la lista de 12 meses).
SQL_NO_VIGENTES = "update aviso_hidrologico set vigente = false where vigente and not (ca = any(%s::int[]))"
# El nivel del detalle ("Aviso N°1169 ROJO") solo completa el de la lista si esta no lo trae.
SQL_DETALLE = """
update aviso_hidrologico set
  nivel = coalesce(nivel, %(nivel)s),
  emision = %(emision)s, inicio = %(inicio)s, fin = %(fin)s, valor = %(valor)s, unidad = %(unidad)s,
  umbral_rojo = %(umbral_rojo)s, areas = %(areas)s, significado_rojo = %(significado_rojo)s, ts_captura = now()
where ca = %(ca)s
"""
SQL_PURGA = "delete from aviso_hidrologico where fin_dia < %s"


def _error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _recortar(lista: list[str], maximo: int) -> list[str]:
    if len(lista) <= maximo:
        return lista
    return lista[:maximo] + [f"... y {len(lista) - maximo} más"]


def _resumen(fallas: list[str], avisos: list[str], **datos) -> dict:
    base = {"filas": None, "vigentes": None, "vigilados": [], "detalles": [], "purgados": None}
    return {**base, **datos, "fallas": fallas, "avisos": _recortar(avisos, MAX_AVISOS), "atribucion": ATRIBUCION}


def _latido(resumen: dict) -> None:
    """Latido en su propia transacción (cuando no hay nada más que escribir)."""
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_LATIDO, (SERVICIO, json.dumps(resumen)))


def _previos() -> tuple[set[str], dict[int, tuple]] | None:
    """
    (estaciones SENAMHI vigiladas, {ca: (día de Lima de su fin o None, nivel)} de los avisos con
    detalle); None si faltan las tablas.
    """
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_HAY_TABLA)
        fila = cur.fetchone()
        if not (fila and fila[0]):
            return None
        cur.execute(SQL_VIGILADAS)
        vigiladas = {str(ce) for (ce,) in cur.fetchall()}
        cur.execute(SQL_CON_DETALLE)
        return vigiladas, {ca: (fin_dia, nivel) for (ca, fin_dia, nivel) in cur.fetchall()}


def _params(f: fuente.FilaAviso) -> dict:
    return {"ca": f.ca, "ce": f.ce, "numero": f.numero, "titulo": f.titulo, "nivel": f.nivel,
            "sentido": f.sentido, "inicio_dia": f.inicio_dia, "fin_dia": f.fin_dia,
            "duracion_h": f.duracion_h, "vigente": f.vigente, "url": f.url}


def vigilados(filas: list[fuente.FilaAviso], vigiladas: set[str]) -> list[dict]:
    """Para el latido: los avisos vigentes de cada estación vigilada y su último aviso."""
    out: list[dict] = []
    for ce in sorted(vigiladas):
        suyas = sorted((f for f in filas if f.ce == ce), key=lambda f: (f.fin_dia, f.ca), reverse=True)
        out += [{"ce": f.ce, "numero": f.numero, "nivel": f.nivel, "vigente": f.vigente,
                 "fin_dia": f.fin_dia.isoformat()} for i, f in enumerate(suyas) if f.vigente or i == 0]
    return out


def _detalle_viejo(f: fuente.FilaAviso, con_detalle: dict[int, tuple]) -> bool:
    """¿La lista cambió el fin o el nivel del aviso desde que se leyó su detalle? (lo corrigió o extendió)"""
    fin_dia, nivel = con_detalle[f.ca]
    return ((fin_dia is not None and fin_dia != f.fin_dia)
            or (f.nivel is not None and nivel is not None and f.nivel != nivel))


def _cuadrar(f: fuente.FilaAviso, d: dict, avisos: list[str]) -> None:
    """Quita del detalle lo que no cuadra con la lista: mejor sin el dato que con uno equivocado."""
    fin = d.get("fin")
    if fin is not None and fin.astimezone(HORA_PERU).date() != f.fin_dia:
        avisos.append(f"detalle {f.ca} (aviso {f.numero}): su fin ({fin.astimezone(HORA_PERU):%d-%m-%Y %H:%M}) "
                      f"no es del día que da la lista ({f.fin_dia:%d-%m-%Y}); no se guardó el fin")
        d["fin"] = None
    valor, umbral = d.get("valor"), d.get("umbral_rojo")
    if valor is not None and umbral and valor / umbral > MAX_VECES_UMBRAL:
        avisos.append(f"detalle {f.ca} (aviso {f.numero}): el valor {valor:g} es más de {MAX_VECES_UMBRAL} veces "
                      f"el umbral rojo {umbral:g} (¿lectura equivocada?); no se guardaron")
        d["valor"] = d["umbral_rojo"] = None


def _bajar_detalles(filas: list[fuente.FilaAviso], vigiladas: set[str], con_detalle: dict[int, tuple],
                    inicio: float, fallas: list[str], avisos: list[str]) -> dict[int, dict]:
    """
    {ca: parámetros de SQL_DETALLE} de los avisos vigentes de las estaciones vigiladas que aún
    no tienen detalle o cuyo detalle quedó viejo (primero los más nuevos), en serie y con pausa.
    inicio: time.monotonic().
    """
    pedir = sorted((f for f in filas if f.vigente and f.ce in vigiladas
                    and (f.ca not in con_detalle or _detalle_viejo(f, con_detalle))),
                   key=lambda f: (f.inicio_dia, f.ca), reverse=True)
    if len(pedir) > MAX_DETALLES:
        avisos.append(f"{len(pedir) - MAX_DETALLES} avisos vigilados sin detalle quedan para la próxima corrida "
                      f"(máximo {MAX_DETALLES} por corrida)")
    detalles: dict[int, dict] = {}
    for f in pedir[:MAX_DETALLES]:
        if time.monotonic() - inicio > PLAZO_S:
            avisos.append(f"detalle {f.ca}: no se pidió (la tarea ya lleva más de {PLAZO_S} s: SENAMHI responde "
                          "lento); queda para la próxima corrida")
            continue
        if f.ca in con_detalle:
            avisos.append(f"detalle {f.ca} (aviso {f.numero}): se vuelve a leer (la lista cambió su fin o su nivel)")
        fuente.pausa()   # también después de la lista: un pedido a la vez
        try:
            d = fuente.parsear_detalle(fuente.bajar_detalle(f.ca, f.ce))
        except Exception as e:
            log.warning("Avisos hidrológicos SENAMHI: detalle %s: %s", f.ca, _error(e))
            fallas.append(f"detalle:{f.ca}")
            avisos.append(f"detalle {f.ca} (aviso {f.numero}): {_error(e)}")
            continue
        if d.get("numero") is not None and d["numero"] != f.numero:
            fallas.append(f"detalle:{f.ca}")
            avisos.append(f"detalle {f.ca}: la página es del aviso {d['numero']}, no del {f.numero}; no se guardó")
            continue
        faltan = [k for k in CAMPOS_DETALLE if d.get(k) is None]
        if len(faltan) == len(CAMPOS_DETALLE):
            fallas.append(f"detalle:{f.ca}")
            avisos.append(f"detalle {f.ca} (aviso {f.numero}): no se entendió la página; no se guardó")
            continue
        if faltan:
            otra_vez = " (se vuelve a pedir en la próxima corrida)" if "inicio" in faltan else ""
            avisos.append(f"detalle {f.ca} (aviso {f.numero}): no se encontró {', '.join(faltan)}{otra_vez}")
        _cuadrar(f, d, avisos)
        detalles[f.ca] = {"ca": f.ca, "nivel": d.get("nivel"), "emision": d.get("emision"),
                          "inicio": d.get("inicio"), "fin": d.get("fin"), "valor": d.get("valor"),
                          "unidad": d.get("unidad"), "umbral_rojo": d.get("umbral_rojo"), "areas": d.get("areas"),
                          "significado_rojo": d.get("significado_rojo")}
    return detalles


def actualizar(ahora: datetime | None = None) -> dict:
    """Tarea 'rios' (Celery la llama sin argumentos; `ahora` (UTC) es para las pruebas)."""
    ahora = ahora or datetime.now(timezone.utc)
    hoy = ahora.astimezone(HORA_PERU).date()
    inicio = time.monotonic()
    fallas: list[str] = []
    avisos: list[str] = []
    previos = _previos()
    if previos is None:
        resumen = _resumen(["migracion"], [AVISO_SIN_TABLA])
        _latido(resumen)
        log.warning("Avisos hidrológicos SENAMHI: %s", AVISO_SIN_TABLA)
        return resumen
    vigiladas, con_detalle = previos
    if not vigiladas:
        avisos.append("rio_vigilado no tiene estaciones SENAMHI: no se lee ningún detalle")

    # 1) Lista (descargas antes de abrir la transacción: no se deja una transacción esperando la red).
    try:
        pagina = fuente.bajar_lista()
    except Exception as e:
        log.error("Avisos hidrológicos SENAMHI: no se pudo bajar la lista: %s", _error(e))
        _latido(_resumen(["lista"], avisos + [f"lista: {_error(e)}"]))
        raise
    filas = fuente.parsear_lista(pagina)
    if len(filas) < MIN_FILAS:
        motivo = (f"la lista trae {len(filas)} avisos legibles (se esperan ~1680, mínimo {MIN_FILAS}): "
                  "la página cambió o vino cortada; no se guardó nada")
        _latido(_resumen(["lista_rara"], avisos + [f"lista: {motivo}"], filas=len(filas)))
        raise ValueError(f"Avisos hidrológicos SENAMHI: {motivo}")

    # Si el texto "(vigente)" y la marca de la fila no coinciden (SENAMHI cambió la página), no se
    # apaga ningún aviso: mejor uno encendido de más que uno vigente apagado sin aviso.
    ambiguos = [f for f in filas if f.ambiguo]
    if ambiguos:
        fallas.append("vigente_ambiguo")
        numeros = ", ".join(str(f.numero) for f in ambiguos[:5]) + (" ..." if len(ambiguos) > 5 else "")
        avisos.append(f"vigencia ambigua en {len(ambiguos)} avisos (N.º {numeros}): el texto \"(vigente)\" y la marca "
                      "de la fila no coinciden; se toman como vigentes y no se apagó ningún aviso")

    # 2) Detalles de los vigilados vigentes que aún no lo tienen (o cuyo detalle quedó viejo).
    detalles = _bajar_detalles(filas, vigiladas, con_detalle, inicio, fallas, avisos)

    # 3) Escritura y latido en una sola transacción, con el candado.
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_CANDADO)
        cur.executemany(SQL_AVISO, [_params(f) for f in filas])
        if not ambiguos:
            cur.execute(SQL_NO_VIGENTES, ([f.ca for f in filas if f.vigente],))
        if detalles:
            cur.executemany(SQL_DETALLE, list(detalles.values()))
        cur.execute(SQL_PURGA, (hoy - timedelta(days=DIAS_PURGA),))
        purgados = cur.rowcount
        resumen = _resumen(fallas, avisos, filas=len(filas), vigentes=sum(f.vigente for f in filas),
                           vigilados=vigilados(filas, vigiladas), detalles=list(detalles), purgados=purgados)
        cur.execute(SQL_LATIDO, (SERVICIO, json.dumps(resumen)))

    if fallas:
        log.warning("Avisos hidrológicos SENAMHI con fallas parciales: %s", resumen)
    else:
        log.info("Avisos hidrológicos SENAMHI: %s", resumen)
    return resumen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    actualizar()
