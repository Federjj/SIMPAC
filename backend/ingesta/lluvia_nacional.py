"""
Lluvia 'ahora' en todo el Perú: la capa de umbrales de SENAMHI -> tabla lluvia_senamhi.

La ingesta horaria (lectura_lluvia) baja la serie de cada estación de los departamentos de
SIMPAC_LLUVIA_DEPTS (hoy solo las 14 de Cajamarca). Esta tarea, que corre cada 30 min
(celery_app; las estaciones reportan cada hora pero no todas a la misma hora), trae con UNA
petición WFS la última hora de ~216 estaciones automáticas de 24 departamentos (25 en
Cajamarca), con el umbral de referencia de SENAMHI de cada una. Ver
backend/connectors/senamhi_umbrales.py. Entre ellas hay hidrológicas automáticas que la
ingesta no tiene porque solo baja las de tipo M: map_red_graf.php sí les da lluvia horaria
si se pide con tipo_esta=M (con tipo_esta=H la serie viene vacía).

Regla de escritura (la misma idea que las alertas de guardar.py): cada corrida reemplaza
solo las estaciones que vinieron; las que no vienen NO se borran, se quedan con su
medido_en viejo y la vista lluvia_senamhi_actual (y el frontend) las ignoran pasadas
VIGENCIA_HORAS. Una lectura más vieja que la guardada no la pisa. Solo se purgan las que la
capa dejó de publicar hace PURGA_DIAS (estaciones renombradas o dadas de baja), y solo en
una corrida en la que la capa respondió: una fuente caída no borra nada.

Alertas de lluvia (tipo 'lluvia'; esta tarea es la única que las escribe): en la misma
transacción, después del upsert, se evalúan DESDE LA BD todas las estaciones de
lluvia_senamhi con dato de las últimas VIGENCIA_HORAS (también las que no vinieron en esta
corrida; si la BD guarda una lectura más nueva que la de la capa, manda la de la BD) con la
referencia de SENAMHI de cada una (backend/alerts.py: pp_1h > umbral_1h o pp_6h > umbral_6h,
nivel siempre 'aviso'; no es un aviso oficial). Se borran todas las de tipo 'lluvia' y se
insertan las que pasan, una por estación, con ts = hora de la medición: la vista
alerta_actual las deja de mostrar pasadas VIGENCIA_HORAS aunque el worker se detenga. Con la
capa caída, vacía o sin lecturas vigentes, sin ninguna estación evaluable o sin la migración
(alerta.ventana_h), no se toca ninguna. Un candado (SQL_CANDADO) pone en serie las corridas.

Emparejamiento con nuestra tabla estacion (la capa no trae código): la estación más
parecida a menos de RADIO_PAREJA_KM cuyo nombre coincide sin los sufijos GORE, M, H,
EMA... ('CUTERVO GORE' = 'CUTERVO'), o una AUTOMÁTICA en el mismo punto (MISMO_PUNTO_KM) aunque
el nombre cambie ('OLMOS' = 'PASABAR', mismas coordenadas). Entre varias gana la de nombre
coincidente, luego la automática (la que tiene serie horaria), luego la del mismo tipo si el
nombre lo dice ('... H GORE' -> hidrológica) y al final la más cercana. Una estación de la
tabla no se asigna a dos puntos de la capa.

Resumen del latido 'lluvia_nacional':
  estaciones      puntos distintos que trajo la capa
  vigentes        de esos, con dato de las últimas VIGENCIA_HORAS
  lloviendo       vigentes con lluvia en su última hora (pp_1h > 0)
  sobre_umbral    vigentes del lote cuya lluvia de la hora superó umbral_1h (pp_1h >
                  umbral_1h, solo 1 h; el mapa y las alertas también miran las 6 h)
  evaluadas       estaciones vigentes en la BD, después del upsert, con pp_1h y referencia
                  mayor que 0 (None si no se evaluó)
  alertas         filas tipo 'lluvia' escritas (None = no se tocaron)
  alertas_6h      de esas, las que pasaron solo por las 6 h
  cajamarca       {"estaciones", "vigentes", "lloviendo"} del departamento foco
  sin_pareja      puntos sin estación emparejada en nuestra tabla
  hora            medido_en más reciente de la capa (hora de Perú)
  purgadas        filas borradas por no aparecer hace PURGA_DIAS
  prec_1, prec_1_ac07d, prec_1_ac07d_desde   fechas (AAAA-MM-DD) de las capas WMS de
                  lluvia observada: 'Lluvia del 21 set' (de las 07:00 del 21 a las 07:00 del
                  22, hora de Perú) y '15 al 21 set'. Ver resolver_fechas: si el visor cae
                  se conservan las de la corrida anterior; None solo si nunca se leyeron.
  prec_1_pendiente   fecha que el visor ya anuncia pero que no se usa porque los datos de
                  prec_1 no cambiaron (o no se pudo comprobar); None si no hay
  fechas_leidas_en   cuándo mostró el visor por última vez las fechas guardadas (ISO, hora
                  de Perú); con el visor caído dice de cuándo son
  prec_1_huella   huella de prec_1_all_points que corresponde a prec_1 (para la próxima)
  atribucion      leyenda literal que exige SENAMHI (para mostrarla tal cual)
  fallas          "umbrales" (capa caída, vacía o sin ninguna lectura vigente) y/o "fechas"
                  (visor o huella sin respuesta)
  avisos          detalle: fuentes caídas, puntos descartados, capa desactualizada, alertas
                  que no se evaluaron (migración pendiente, ninguna estación evaluable)...

Si falla la capa de umbrales, el latido lo registra y la tarea termina con excepción (Celery
la marca como fallida); si solo fallan las fechas, sigue con aviso.

Corrida suelta, dentro del contenedor worker:
    docker compose run --rm worker python -m backend.ingesta.lluvia_nacional
"""
from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from backend import alerts
from backend.connectors import senamhi_umbrales
from backend.connectors.senamhi import HORA_PERU
from backend.connectors.senamhi_umbrales import FechasLluviaObservada, LecturaUmbral
from backend.db import conectar
from backend.ingesta.departamentos import nombre_departamento
from backend.ingesta.guardar import SQL_LATIDO

log = logging.getLogger(__name__)

SERVICIO = "lluvia_nacional"
RADIO_PAREJA_KM = 1.5          # las dos tablas de SENAMHI difieren hasta ~1,3 km en coordenadas
MISMO_PUNTO_KM = 0.05          # una automática aquí es la misma estación aunque cambie el nombre
RADIO_DEPARTAMENTO_KM = 100.0  # solo si la capa no trae departamento
VIGENCIA_HORAS = 3             # igual que la vista lluvia_senamhi_actual
PURGA_DIAS = 30
MAX_AVISOS = 20

# Sufijos que las dos tablas de SENAMHI ponen o quitan al mismo nombre de estación.
_SUFIJOS = {"GORE", "M", "H", "EMA", "EAMA", "EHA", "EHMA", "PLU", "PSI", "ANA"}

SQL_ESTACIONES = "select cod, nombre, tipo, estado, departamento, lat, lon from estacion where geom is not null"
SQL_LLUVIA_SENAMHI = (
    "insert into lluvia_senamhi (clave,nombre,cod,departamento,provincia,distrito,cuenca,altitud_m,"
    "pp_1h,umbral_1h,pp_6h,umbral_6h,medido_en,geom) "
    "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326)) "
    "on conflict (clave) do update set nombre=excluded.nombre, cod=excluded.cod, "
    "departamento=excluded.departamento, provincia=excluded.provincia, distrito=excluded.distrito, "
    "cuenca=excluded.cuenca, altitud_m=excluded.altitud_m, pp_1h=excluded.pp_1h, "
    "umbral_1h=excluded.umbral_1h, pp_6h=excluded.pp_6h, umbral_6h=excluded.umbral_6h, "
    "medido_en=excluded.medido_en, geom=excluded.geom, ts_captura=now() "
    # la misma hora sí se reescribe (SENAMHI corrige la última); una más vieja no pisa
    "where excluded.medido_en >= lluvia_senamhi.medido_en"
)
SQL_PURGA = "delete from lluvia_senamhi where ts_captura < now() - make_interval(days => %s)"
SQL_LATIDO_PREVIO = "select resumen from latido where servicio = %s"
# Primera sentencia de la transacción, siempre: pone en serie el beat y una corrida suelta
# (alertas de lluvia y lectura y escritura del latido). Se suelta al commit.
SQL_CANDADO = "select pg_advisory_xact_lock(hashtext('lluvia_nacional'))"
# La migración de las alertas de lluvia puede no estar aplicada todavía (el worker se
# despliega aparte): sin ella el INSERT tumbaría la transacción entera, lluvia_senamhi incluida.
SQL_HAY_ALERTA_LLUVIA = "select to_regclass('public.alerta_lluvia_referencia_key') is not null"
AVISO_SIN_MIGRACION = "alertas: falta la migración de alertas de lluvia (alerta.ventana_h); no se evaluaron"
AVISO_SIN_EVALUABLES = "alertas: ninguna estación vigente trae lluvia de la hora y referencia; no se tocaron"
# Lo que se evalúa: la BD después del upsert (puede guardar una lectura más nueva que la de
# la capa, y trae también las vigentes que no vinieron en esta corrida).
SQL_LLUVIA_VIGENTE = (
    "select clave, nombre, departamento, provincia, pp_1h, umbral_1h, pp_6h, umbral_6h, medido_en, lon, lat "
    "from lluvia_senamhi where medido_en >= %s order by clave"
)
SQL_BORRAR_ALERTAS_LLUVIA = "delete from alerta where tipo = 'lluvia'"
# Propio (SQL_ALERTA de guardar.py lo comparten avisos.py y test_avisos): tipo y nivel fijos,
# ts = hora de la medición y el punto de la estación.
SQL_ALERTA_LLUVIA = (
    "insert into alerta (tipo,referencia,zona,nivel,detalle,valor,umbral,ventana_h,ts,geom) "
    "values ('lluvia',%s,%s,'aviso',%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326))"
)
# Lo que se arrastra de una corrida a la siguiente (ver resolver_fechas).
CAMPOS_FECHAS = ("prec_1", "prec_1_ac07d", "prec_1_ac07d_desde", "fechas_leidas_en", "prec_1_huella")


@dataclass
class EstacionRef:
    """Fila de nuestra tabla estacion (la llena la ingesta con el inventario de SENAMHI)."""
    cod: str
    nombre: str
    tipo: str | None
    estado: str | None
    departamento: str | None
    lat: float
    lon: float


@dataclass
class Pareja:
    cod: str | None                # estación de nuestra tabla (None = sin pareja)
    departamento: str | None       # canónico: el de la capa, o el de la estación más cercana


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia sobre la esfera (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0088 * math.asin(math.sqrt(min(1.0, h)))


def _palabras(nombre: str) -> list[str]:
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", " ", sin_tildes.upper()).split()


def palabras_nombre(nombre: str) -> tuple[str, ...]:
    """'Cutervo GORE' -> ('CUTERVO',); 'EMA-ANTONIO RAIMONDI' -> ('ANTONIO', 'RAIMONDI')."""
    return tuple(p for p in _palabras(nombre) if p not in _SUFIJOS)


def _tipo_indicado(nombre: str) -> str | None:
    """'BAMBAMARCA H GORE' -> 'H': el nombre dice si es hidrológica o meteorológica."""
    palabras = set(_palabras(nombre))
    h = bool(palabras & {"H", "EHA", "EHMA"})
    m = bool(palabras & {"M", "EMA", "EAMA"})
    return "H" if h and not m else "M" if m and not h else None


def _contiene(largo: tuple[str, ...], corto: tuple[str, ...]) -> bool:
    n = len(corto)
    return any(largo[i:i + n] == corto for i in range(len(largo) - n + 1))


def mismo_nombre(a: str, b: str) -> tuple[bool, bool]:
    """
    (coinciden, exacto). Coinciden si son iguales sin sufijos ni espacios ('CASA GRANDE' =
    'CASAGRANDE') o si uno está contenido palabra por palabra en el otro ('CRISNEJAS' y
    'PUENTE CRISNEJAS'), siempre que la parte común tenga al menos 4 letras.
    """
    pa, pb = palabras_nombre(a), palabras_nombre(b)
    ja, jb = "".join(pa), "".join(pb)
    if not ja or not jb:
        return False, False
    if ja == jb:
        return True, True
    corto, largo = (pa, pb) if len(ja) < len(jb) else (pb, pa)
    return len("".join(corto)) >= 4 and _contiene(largo, corto), False


def emparejar(lecturas: list[LecturaUmbral], estaciones: list[EstacionRef]) -> dict[str, Pareja]:
    """clave de cada lectura -> Pareja (código de nuestra tabla y departamento canónico)."""
    candidatos: dict[str, list[tuple[tuple, EstacionRef]]] = {}
    cercana: dict[str, tuple[float, EstacionRef]] = {}
    for lec in lecturas:
        tipo = _tipo_indicado(lec.nombre)
        lista = []
        for e in estaciones:
            d = distancia_km(lec.lat, lec.lon, e.lat, e.lon)
            if lec.clave not in cercana or d < cercana[lec.clave][0]:
                cercana[lec.clave] = (d, e)
            if d > RADIO_PAREJA_KM:
                continue
            coincide, exacto = mismo_nombre(lec.nombre, e.nombre)
            automatica = e.estado == "AUTOMATICA"
            if not coincide and not (automatica and d <= MISMO_PUNTO_KM):
                continue
            orden = (not coincide, not automatica, not exacto, tipo is not None and e.tipo != tipo, d)
            lista.append((orden, e))
        candidatos[lec.clave] = sorted(lista, key=lambda x: x[0])

    # Cada estación de la tabla va a un solo punto: primero los emparejamientos más seguros.
    tomadas: set[str] = set()
    cod: dict[str, str | None] = {}
    peor = (True, True, True, True, math.inf)
    for clave in sorted(candidatos, key=lambda c: candidatos[c][0][0] if candidatos[c] else peor):
        libre = next((e for _, e in candidatos[clave] if e.cod not in tomadas), None)
        cod[clave] = libre.cod if libre else None
        if libre:
            tomadas.add(libre.cod)

    por_cod = {e.cod: e for e in estaciones}
    out: dict[str, Pareja] = {}
    for lec in lecturas:
        depto = nombre_departamento(lec.departamento)
        if depto is None and cod[lec.clave]:
            depto = nombre_departamento(por_cod[cod[lec.clave]].departamento)
        if depto is None and lec.clave in cercana and cercana[lec.clave][0] <= RADIO_DEPARTAMENTO_KM:
            depto = nombre_departamento(cercana[lec.clave][1].departamento)
        out[lec.clave] = Pareja(cod=cod[lec.clave], departamento=depto)
    return out


def sin_repetidos(lecturas: list[LecturaUmbral]) -> list[LecturaUmbral]:
    """Un punto por clave (el más reciente): la capa podría repetir una fila."""
    por_clave: dict[str, LecturaUmbral] = {}
    for lec in lecturas:
        previa = por_clave.get(lec.clave)
        if previa is None or lec.medido_en > previa.medido_en:
            por_clave[lec.clave] = lec
    return list(por_clave.values())


def filas(lecturas: list[LecturaUmbral], parejas: dict[str, Pareja]) -> list[tuple]:
    """Parámetros de SQL_LLUVIA_SENAMHI, en el orden de sus columnas."""
    return [(lec.clave, lec.nombre, parejas[lec.clave].cod, parejas[lec.clave].departamento,
             lec.provincia, lec.distrito, lec.cuenca, lec.altitud_m,
             lec.pp_1h, lec.umbral_1h, lec.pp_6h, lec.umbral_6h, lec.medido_en, lec.lon, lec.lat)
            for lec in lecturas]


def _vigente(lec: LecturaUmbral, ahora: datetime) -> bool:
    return ahora - lec.medido_en <= timedelta(hours=VIGENCIA_HORAS)


def conteo(lecturas: list[LecturaUmbral], parejas: dict[str, Pareja], ahora: datetime) -> dict:
    vigentes = [lec for lec in lecturas if _vigente(lec, ahora)]
    llueve = [lec for lec in vigentes if (lec.pp_1h or 0) > 0]
    caj = [lec for lec in lecturas if parejas[lec.clave].departamento == "Cajamarca"]
    caj_vig = [lec for lec in caj if _vigente(lec, ahora)]
    hora = max((lec.medido_en for lec in lecturas), default=None)
    return {
        "estaciones": len(lecturas),
        "vigentes": len(vigentes),
        "lloviendo": len(llueve),
        # estrictamente mayor, como el mapa (lluviaAhora.js) y el visor de SENAMHI ("supera")
        "sobre_umbral": sum(1 for lec in llueve if lec.umbral_1h is not None and lec.pp_1h > lec.umbral_1h),
        "cajamarca": {"estaciones": len(caj), "vigentes": len(caj_vig),
                      "lloviendo": sum(1 for lec in caj_vig if (lec.pp_1h or 0) > 0)},
        "sin_pareja": sum(1 for p in parejas.values() if p.cod is None),
        "hora": hora.astimezone(HORA_PERU).isoformat() if hora else None,
    }


def _dia(valor) -> date | None:
    """date de un 'AAAA-MM-DD' del latido; None si falta o no se entiende."""
    if not isinstance(valor, str):
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def fechas_previas(previo: dict) -> dict:
    """Los CAMPOS_FECHAS del latido anterior; todos None si su prec_1 falta o está dañado."""
    guardado = {k: previo.get(k) if isinstance(previo.get(k), str) else None for k in CAMPOS_FECHAS}
    return guardado if _dia(guardado["prec_1"]) else dict.fromkeys(CAMPOS_FECHAS)


def resolver_fechas(previo: dict, fechas: FechasLluviaObservada | None, huella: str | None,
                    ahora: datetime) -> tuple[dict, list[str]]:
    """
    Qué fechas de prec_1 / prec_1_ac07d quedan en el latido -> (CAMPOS_FECHAS +
    prec_1_pendiente, avisos).

    La fecha del visor sale del reloj de SENAMHI: pasada la medianoche ya anuncia el día
    nuevo aunque la capa siga con el anterior hasta el proceso de la mañana (el dato del 21
    termina a las 07:00 del 22). Por eso una fecha que AVANZA solo se acepta si la huella de
    prec_1_all_points es distinta de la guardada con la fecha anterior; si es igual, o no se
    pudo leer, se conserva la anterior y la nueva queda en prec_1_pendiente. La misma fecha
    se acepta siempre y renueva la huella (SENAMHI corrige el día en curso). Sin fecha o sin
    huella anteriores no hay con qué comparar y se acepta la del visor.

    Visor caído (fechas None): se conserva todo lo del latido anterior; fechas_leidas_en dice
    de cuándo es. Una fecha posterior a ayer o anterior a la guardada no se usa.
    """
    guardado = fechas_previas(previo)
    campos = {**guardado, "prec_1_pendiente": None}
    avisos: list[str] = []
    ayer = ahora.astimezone(HORA_PERU).date() - timedelta(days=1)
    if fechas is not None:
        anterior, nueva = _dia(guardado["prec_1"]), fechas.prec_1
        leidas = {**fechas.a_json(), "fechas_leidas_en": ahora.astimezone(HORA_PERU).isoformat(timespec="seconds"),
                  "prec_1_huella": huella or guardado["prec_1_huella"]}
        if nueva > ayer:
            avisos.append(f"fechas: el visor dice que prec_1 es del {nueva}, posterior a ayer ({ayer}): no se usa")
        elif anterior is None or nueva == anterior:
            campos.update(leidas)
        elif nueva < anterior:
            avisos.append(f"fechas: el visor volvió al {nueva} (ya se había leído el {anterior}): no se usa")
        elif huella is not None and huella != guardado["prec_1_huella"]:
            campos.update(leidas)   # avanzó y los datos cambiaron: SENAMHI ya procesó el día
        else:
            campos["prec_1_pendiente"] = nueva.isoformat()
            motivo = ("no se pudo comprobar si los datos de prec_1 cambiaron" if huella is None
                      else "los datos de prec_1 siguen siendo los mismos")
            avisos.append(f"fechas: el visor ya anuncia el {nueva}, pero {motivo}: se mantiene el {anterior}")
    # Con la fecha que se va a mostrar, no con la del visor (que siempre dice "ayer").
    mostrada = _dia(campos["prec_1"])
    if mostrada and mostrada < ayer - timedelta(days=1):
        avisos.append(f"fechas: SENAMHI no ha actualizado la lluvia observada (prec_1 es del {mostrada})")
    return campos, avisos


_SIN_EVALUAR = ("evaluadas", "alertas", "alertas_6h")


def escribir_alertas(cur, ahora: datetime) -> tuple[dict, list[str]]:
    """
    Reemplaza las alertas de lluvia con las estaciones vigentes de la BD (ver el docstring
    del módulo) -> ({"evaluadas", "alertas", "alertas_6h"}, avisos). None = no se tocaron.
    Va dentro de la transacción de actualizar(), con el candado tomado y después del upsert.
    """
    nada = dict.fromkeys(_SIN_EVALUAR)
    cur.execute(SQL_HAY_ALERTA_LLUVIA)
    fila = cur.fetchone()
    if not (fila and fila[0]):
        return nada, [AVISO_SIN_MIGRACION]
    cur.execute(SQL_LLUVIA_VIGENTE, (ahora - timedelta(hours=VIGENCIA_HORAS),))
    evaluadas, nuevas = 0, []
    for clave, nombre, depto, prov, pp1, u1, pp6, u6, medido, lon, lat in cur.fetchall():
        if not alerts.lluvia_evaluable(pp1, u1):
            continue
        evaluadas += 1
        if a := alerts.evaluar_lluvia_referencia(clave, nombre, prov, depto, pp1, u1, pp6, u6, medido):
            nuevas.append((a, lon, lat))
    # Sin ninguna evaluable no se sabe si "no pasa ninguna": se quedan las que había.
    if not evaluadas:
        return {**nada, "evaluadas": 0}, [AVISO_SIN_EVALUABLES]
    cur.execute(SQL_BORRAR_ALERTAS_LLUVIA)
    if nuevas:
        cur.executemany(SQL_ALERTA_LLUVIA, [
            (a["referencia"], a["zona"], a["detalle"], a["valor"], a["umbral"], a["ventana_h"], a["ts"], lon, lat)
            for a, lon, lat in nuevas
        ])
    return {"evaluadas": evaluadas, "alertas": len(nuevas),
            "alertas_6h": sum(a["ventana_h"] == 6 for a, _, _ in nuevas)}, []


def _error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _recortar(avisos: list[str]) -> list[str]:
    if len(avisos) <= MAX_AVISOS:
        return avisos
    return avisos[:MAX_AVISOS] + [f"... y {len(avisos) - MAX_AVISOS} avisos más"]


def actualizar(ahora: datetime | None = None) -> dict:
    """Tarea 'lluvia_nacional' (Celery la llama sin argumentos; `ahora` es para las pruebas)."""
    ahora = ahora or datetime.now(timezone.utc)
    fallas: list[str] = []
    avisos: list[str] = []

    # 1) Descargas antes de abrir la conexión (no se deja una transacción esperando la red).
    lecturas: list[LecturaUmbral] = []
    try:
        lecturas, descartes = senamhi_umbrales.lecturas(ahora)
        lecturas = sin_repetidos(lecturas)
        avisos += [f"umbrales: {a}" for a in descartes]
        if not lecturas:
            fallas.append("umbrales")
            avisos.append("umbrales: la capa no trajo ninguna estación válida")
    except Exception as e:
        log.error("Lluvia nacional: no se pudo leer la capa de umbrales: %s", _error(e))
        fallas.append("umbrales")
        avisos.append(f"umbrales: {_error(e)}")

    fechas = None
    try:
        fechas = senamhi_umbrales.fechas_lluvia_observada()
    except Exception as e:
        log.warning("Lluvia nacional: sin fecha de la lluvia observada: %s", _error(e))
        fallas.append("fechas")
        avisos.append(f"fechas: {_error(e)}")

    # Huella de los datos de prec_1: sin fecha del visor no se usa y no se baja.
    huella = None
    if fechas is not None:
        try:
            huella = senamhi_umbrales.huella_prec_1()
        except Exception as e:
            log.warning("Lluvia nacional: sin huella de prec_1 (no se puede comprobar la fecha): %s", _error(e))
            fallas.append("fechas")
            avisos.append(f"fechas: huella de prec_1_all_points: {_error(e)}")

    # 2) Escritura, alertas y latido en una sola transacción, con el candado (también con la
    #    capa caída: el latido se lee y se escribe igual).
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_CANDADO)
        numeros: dict = {}
        purgadas = None
        evaluacion = dict.fromkeys(_SIN_EVALUAR)
        if lecturas:
            cur.execute(SQL_ESTACIONES)
            estaciones = [EstacionRef(cod, nombre, tipo, estado, depto, float(lat), float(lon))
                          for cod, nombre, tipo, estado, depto, lat, lon in cur.fetchall()]
            parejas = emparejar(lecturas, estaciones)
            cur.executemany(SQL_LLUVIA_SENAMHI, filas(lecturas, parejas))
            cur.execute(SQL_PURGA, (PURGA_DIAS,))
            purgadas = cur.rowcount
            numeros = conteo(lecturas, parejas, ahora)
            # La capa respondió, pero con todo viejo es como si no: el monitoreo se tiene que enterar.
            if numeros["vigentes"] == 0:
                fallas.append("umbrales")
                avisos.append(f"umbrales: ninguna estación tiene dato de las últimas {VIGENCIA_HORAS} h")
            elif numeros["vigentes"] * 2 < numeros["estaciones"]:
                avisos.append(f"umbrales: solo {numeros['vigentes']} de {numeros['estaciones']} estaciones "
                              f"tienen dato de las últimas {VIGENCIA_HORAS} h")
            # Alertas de lluvia: solo si la capa trajo algo vigente (una fuente caída no borra nada).
            if numeros["vigentes"] > 0:
                evaluacion, avisos_alertas = escribir_alertas(cur, ahora)
                avisos += avisos_alertas

        # Fechas de la lluvia observada frente a las de la corrida anterior (mismo latido).
        cur.execute(SQL_LATIDO_PREVIO, (SERVICIO,))
        fila = cur.fetchone()
        previo = fila[0] if fila and isinstance(fila[0], dict) else {}
        campos_fechas, avisos_fechas = resolver_fechas(previo, fechas, huella, ahora)
        avisos += avisos_fechas

        resumen = {
            **{k: numeros.get(k) for k in ("estaciones", "vigentes", "lloviendo", "sobre_umbral")},
            **evaluacion,   # siempre las tres claves (el frontend sabe así que el worker es nuevo)
            **{k: numeros.get(k) for k in ("cajamarca", "sin_pareja", "hora")},
            "purgadas": purgadas,
            **campos_fechas,
            "atribucion": senamhi_umbrales.ATRIBUCION,
            "fallas": fallas,
            "avisos": _recortar(avisos),
        }
        cur.execute(SQL_LATIDO, (SERVICIO, json.dumps(resumen)))

    if "umbrales" in fallas:
        # El latido ya lo registró; la excepción hace que Celery marque la tarea como fallida.
        raise RuntimeError("Lluvia nacional: la capa de umbrales de SENAMHI no respondió o no trae "
                           "lecturas recientes: " + " | ".join(avisos))
    if fallas or avisos:
        log.warning("Lluvia nacional con fallas o avisos: %s", resumen)
    else:
        log.info("Lluvia nacional: %s", resumen)
    return resumen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    actualizar()
