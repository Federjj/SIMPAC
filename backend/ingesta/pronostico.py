"""
Pronóstico oficial de SENAMHI por localidad -> tabla pronostico_localidad (vista
pronostico_vigente para el frontend).

La tarea 'pronostico' (cada hora) llama a actualizar(), que:
  1. Baja la página del país (backend/connectors/senamhi_pronostico.py): ~277 localidades con
     3 a 5 días cada una. SENAMHI la renueva una vez por día hábil, de noche, así que casi
     todas las corridas reescriben lo mismo; cada hora basta para tomar la nueva a tiempo.
  2. Ubica cada localidad con el catálogo revisado backend/data/localidades_senamhi.json (la
     página no trae coordenadas; lo arma backend/mapas/semilla_localidades.py). Un punto
     fuera del Perú se descarta con un aviso. La que no está en el catálogo se guarda con
     lat/lon null: la vista no la muestra y el latido la lista en sin_ubicacion.
  3. Clasifica cada día con backend/ingesta/lectura_pronostico.py (el texto manda; el ícono
     de SENAMHI solo suma o pone en duda).
  4. En una transacción, con un candado: upsert por (codigo, fecha) desde hoy (hora de Perú)
     y purga de las fechas pasadas. Una emisión más vieja (una copia atrasada de la página)
     no pisa una más nueva; la misma sí se reescribe.

Regla de "no borrar lo que no se pudo consultar": con la página caída o ilegible, o con el
catálogo ilegible (una coma de más al revisarlo a mano: las filas irían sin punto y pisarían
los guardados), no se escribe ni se borra nada (ni siquiera la purga); el latido lo registra y
la tarea termina con excepción. La vista deja de mostrar una emisión de más de 5 días.

Resumen del latido 'pronostico':
  emision        fecha de la emisión leída (None si la página falló)
  localidades    localidades legibles de la página
  filas          días enviados al upsert (desde hoy)
  escritas       filas insertadas o actualizadas (menos que filas si la BD ya tenía una
                 emisión más nueva)
  purgadas       filas de fechas pasadas borradas
  sin_ubicacion  localidades sin punto en el catálogo (se guardan, no se muestran)
  problemas      bloques o días de la página que no se entendieron
  cajamarca      {fecha: {lluvia, posible, tormenta, nieve, sin_lluvia}} del departamento foco
                 (posible = "puede llover"; tormenta y nieve cuentan también las posibles)
  pais           lo mismo, de todo el país
  fallas         'pagina' (caída o ilegible), 'catalogo' (no se pudo leer; no se escribe
                 nada), 'migracion' (falta la tabla)
  avisos         detalle: errores, puntos descartados, emisión atrasada...

Corrida suelta, dentro del contenedor worker:
    docker compose run --rm worker python -m backend.ingesta.pronostico
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend.connectors import senamhi_pronostico as fuente
from backend.connectors.senamhi import HORA_PERU
from backend.db import conectar
from backend.ingesta.departamentos import nombre_departamento
from backend.ingesta.guardar import SQL_LATIDO
from backend.ingesta.lectura_pronostico import clasificar, nombre_legible

log = logging.getLogger(__name__)

SERVICIO = "pronostico"
CATALOGO = Path(__file__).resolve().parents[1] / "data" / "localidades_senamhi.json"
DP_CAJAMARCA = "06"
DIAS_ATRASO = 3                 # sin emisión nueva hace más de esto: aviso (fin de semana largo)
MAX_SIN_UBICACION, MAX_PROBLEMAS, MAX_AVISOS = 30, 20, 20
# Recuadro del Perú para los puntos del catálogo (el mismo del check de report.geom).
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = -18.5, 0.2, -81.5, -68.5
CATEGORIAS = ("lluvia", "posible", "tormenta", "nieve", "sin_lluvia")

# La migración puede no estar aplicada todavía (el worker se despliega aparte).
SQL_HAY_TABLA = "select to_regclass('public.pronostico_localidad') is not null"
AVISO_SIN_TABLA = "pronostico_localidad: falta la tabla (migración pendiente); no se guardó nada"
# Pone en serie el beat y una corrida suelta. Se suelta al commit.
SQL_CANDADO = "select pg_advisory_xact_lock(hashtext('pronostico'))"
SQL_PRONOSTICO = (
    "insert into pronostico_localidad (codigo,fecha,dp,localidad,nombre,nombre_senamhi,departamento,emision,"
    "icono_senamhi,tmax,tmin,texto,tipo,posible,por,lluvia_segura,granizo,intensidad,momento,cielo,lat,lon,"
    "ubicacion) "
    "values (%(codigo)s,%(fecha)s,%(dp)s,%(localidad)s,%(nombre)s,%(nombre_senamhi)s,%(departamento)s,"
    "%(emision)s,%(icono_senamhi)s,%(tmax)s,%(tmin)s,%(texto)s,%(tipo)s,%(posible)s,%(por)s,"
    "%(lluvia_segura)s,%(granizo)s,%(intensidad)s,%(momento)s,%(cielo)s,%(lat)s,%(lon)s,%(ubicacion)s) "
    "on conflict (codigo, fecha) do update set dp=excluded.dp, localidad=excluded.localidad, "
    "nombre=excluded.nombre, nombre_senamhi=excluded.nombre_senamhi, departamento=excluded.departamento, "
    "emision=excluded.emision, icono_senamhi=excluded.icono_senamhi, tmax=excluded.tmax, tmin=excluded.tmin, "
    "texto=excluded.texto, tipo=excluded.tipo, posible=excluded.posible, por=excluded.por, "
    "lluvia_segura=excluded.lluvia_segura, granizo=excluded.granizo, intensidad=excluded.intensidad, "
    "momento=excluded.momento, cielo=excluded.cielo, lat=excluded.lat, lon=excluded.lon, "
    "ubicacion=excluded.ubicacion, ts_captura = now() "
    # la misma emisión sí se reescribe (el catálogo o la lectura pueden cambiar); una más vieja no pisa
    "where excluded.emision >= pronostico_localidad.emision"
)
# Hoy se conserva todo el día: "hoy" viene de la emisión de anoche.
SQL_PURGA = "delete from pronostico_localidad where fecha < %s"


def _error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _recortar(lista: list[str], maximo: int) -> list[str]:
    if len(lista) <= maximo:
        return lista
    return lista[:maximo] + [f"... y {len(lista) - maximo} más"]


def _nombre_plano(nombre: str | None) -> str:
    """'CHANCAY BAÑOS - CAJAMARCA' -> 'CHANCAYBANOSCAJAMARCA' (para comparar con el catálogo)."""
    sin_tildes = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z]", "", sin_tildes.upper())


def cargar_catalogo(ruta: Path | None = None) -> tuple[dict[str, dict], list[str]]:
    """
    {codigo: {lat, lon, ubicacion, nombre_senamhi}} del catálogo (por defecto CATALOGO) y los
    avisos de los puntos descartados (sin coordenadas legibles o fuera del Perú). Falla si el
    archivo no se puede leer.
    """
    ruta = Path(ruta or CATALOGO)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    entradas = datos.get("localidades") if isinstance(datos, dict) else None
    if not isinstance(entradas, dict):
        raise ValueError(f"{ruta.name} no trae 'localidades'")
    catalogo: dict[str, dict] = {}
    avisos: list[str] = []
    for codigo, e in entradas.items():
        try:
            lat, lon = float(e["lat"]), float(e["lon"])
        except (TypeError, KeyError, ValueError):
            avisos.append(f"catálogo: {codigo} sin coordenadas legibles: queda sin ubicar")
            continue
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            avisos.append(f"catálogo: {codigo} fuera del Perú ({lat}, {lon}): queda sin ubicar")
            continue
        catalogo[codigo] = {"lat": lat, "lon": lon, "ubicacion": e.get("ubicacion"),
                            "nombre_senamhi": e.get("nombre_senamhi")}
    return catalogo, avisos


def _departamento(nombre_senamhi: str) -> str | None:
    """'MOYOBAMBA - SAN MARTIN' -> 'San Martín' (nombre canónico)."""
    partes = nombre_senamhi.rsplit(" - ", 1)
    return nombre_departamento(partes[1]) if len(partes) == 2 else None


def filas(pron: fuente.Pronostico, catalogo: dict[str, dict], hoy: date) -> tuple[list[dict], list[str], list[str]]:
    """
    Parámetros de SQL_PRONOSTICO (solo los días desde hoy), las localidades sin ubicar y los
    avisos de las que cambiaron de nombre respecto del catálogo (el punto se usa igual: el
    código es el de SENAMHI; el aviso es para revisar el catálogo).
    """
    out: list[dict] = []
    sin_ubicacion: list[str] = []
    avisos: list[str] = []
    for loc in pron.localidades:
        punto = catalogo.get(loc.codigo)
        if punto is None:
            sin_ubicacion.append(f"{loc.codigo} {loc.nombre_senamhi}")
            punto = {"lat": None, "lon": None, "ubicacion": None}
        elif punto.get("nombre_senamhi") and _nombre_plano(punto["nombre_senamhi"]) != _nombre_plano(loc.nombre_senamhi):
            avisos.append(f"catálogo: {loc.codigo} ahora es '{loc.nombre_senamhi}' "
                          f"(el catálogo dice '{punto['nombre_senamhi']}'): revisar el punto")
        base = {"codigo": loc.codigo, "dp": loc.dp, "localidad": loc.localidad,
                "nombre": nombre_legible(loc.nombre_senamhi), "nombre_senamhi": loc.nombre_senamhi,
                "departamento": _departamento(loc.nombre_senamhi), "emision": pron.emision,
                "lat": punto["lat"], "lon": punto["lon"], "ubicacion": punto["ubicacion"]}
        for d in loc.dias:
            if d.fecha < hoy:   # la página a veces trae el día de la emisión, que ya pasó
                continue
            out.append({**base, "fecha": d.fecha, "icono_senamhi": d.icono, "tmax": d.tmax, "tmin": d.tmin,
                        "texto": d.texto, **clasificar(d.icono, d.texto)})
    return out, sin_ubicacion, avisos


def categoria(fila: dict) -> str:
    """Para los conteos del latido: 'posible' es la lluvia posible ("puede llover")."""
    return "posible" if fila["tipo"] == "lluvia" and fila["posible"] else fila["tipo"]


def conteo(filas_: list[dict], dp: str | None = None) -> dict[str, dict[str, int]]:
    """{'2026-09-23': {'lluvia': 7, 'posible': 6, ...}} por fecha, de un departamento o del país."""
    out: dict[str, dict[str, int]] = {}
    for f in sorted(filas_, key=lambda f: f["fecha"]):
        if dp is None or f["dp"] == dp:
            out.setdefault(f["fecha"].isoformat(), dict.fromkeys(CATEGORIAS, 0))[categoria(f)] += 1
    return out


def actualizar(ahora: datetime | None = None) -> dict:
    """Tarea 'pronostico' (Celery la llama sin argumentos; `ahora` (UTC) es para las pruebas)."""
    ahora = ahora or datetime.now(timezone.utc)
    hoy = ahora.astimezone(HORA_PERU).date()
    fallas: list[str] = []
    avisos: list[str] = []

    # 1) Descarga, antes de abrir la conexión (no se deja una transacción esperando la red).
    pron = None
    try:
        pron = fuente.pronostico_pais(hoy)
    except Exception as e:
        log.error("Pronóstico SENAMHI: no se pudo leer la página: %s", _error(e))
        fallas.append("pagina")
        avisos.append(f"página: {_error(e)}")

    # 2) Catálogo de coordenadas y lectura de cada día. Sin catálogo no se escribe nada: las
    # filas irían con lat/lon null y el upsert (la misma emisión se reescribe) borraría los
    # puntos guardados.
    catalogo: dict[str, dict] | None = None
    try:
        catalogo, avisos_catalogo = cargar_catalogo()
        avisos += avisos_catalogo
    except Exception as e:
        log.error("Pronóstico SENAMHI: no se pudo leer el catálogo de localidades: %s", _error(e))
        fallas.append("catalogo")
        avisos.append(f"catálogo: {_error(e)}")
    nuevas, sin_ubicacion = [], []
    if pron is not None:
        if catalogo is not None:
            nuevas, sin_ubicacion, avisos_nombres = filas(pron, catalogo, hoy)
            avisos += avisos_nombres
        if pron.emision < hoy - timedelta(days=DIAS_ATRASO):
            avisos.append(f"SENAMHI no publica un pronóstico nuevo desde el {pron.emision.isoformat()}")

    # 3) Escritura y latido en una sola transacción.
    escritas = purgadas = None
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_HAY_TABLA)
        fila = cur.fetchone()
        if not (fila and fila[0]):
            fallas.append("migracion")
            avisos.append(AVISO_SIN_TABLA)
        else:
            cur.execute(SQL_CANDADO)
            if pron is not None and catalogo is not None:   # una fuente caída no escribe ni borra nada
                if nuevas:
                    cur.executemany(SQL_PRONOSTICO, nuevas)
                    escritas = cur.rowcount
                cur.execute(SQL_PURGA, (hoy,))
                purgadas = cur.rowcount
        resumen = {
            "emision": pron.emision.isoformat() if pron else None,
            "localidades": len(pron.localidades) if pron else None,
            "filas": len(nuevas),
            "escritas": escritas,
            "purgadas": purgadas,
            "sin_ubicacion": _recortar(sin_ubicacion, MAX_SIN_UBICACION),
            "problemas": _recortar(pron.problemas if pron else [], MAX_PROBLEMAS),
            "cajamarca": conteo(nuevas, DP_CAJAMARCA),
            "pais": conteo(nuevas),
            "fallas": fallas,
            "avisos": _recortar(avisos, MAX_AVISOS),
        }
        cur.execute(SQL_LATIDO, (SERVICIO, json.dumps(resumen)))

    if "pagina" in fallas or "catalogo" in fallas:
        # El latido ya lo registró; la excepción hace que Celery marque la tarea como fallida.
        que = "la página de pronóstico" if "pagina" in fallas else "el catálogo de localidades"
        raise RuntimeError(f"Pronóstico SENAMHI: no se pudo leer {que}; no se guardó nada: " + " | ".join(avisos))
    if fallas or avisos:
        log.warning("Pronóstico SENAMHI con fallas o avisos: %s", resumen)
    else:
        log.info("Pronóstico SENAMHI: %s", resumen)
    return resumen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    actualizar()
