"""
Nowcasting de lluvia de SENAMHI (EXPERIMENTAL) -> tablas nowcast_producto y nowcast_mancha.

La tarea 'nowcast' (cada 10 min, como sale el producto) llama a actualizar(), que:
  1. Lee qué emisión tiene guardada cada horizonte (0 = análisis de ahora, 60 = +1 h,
     120 = +2 h).
  2. Lee en el visor oficial la última emisión T (backend/connectors/senamhi_nowcast.py).
  3. Por horizonte (primero el +1 h, que es el que se muestra por defecto), en serie y con
     pausas (con peticiones en paralelo la GeoServer corta): si ya tiene T guardado se reusa;
     si no, se bajan por WFS las manchas de nivel 1 a 3. Todo antes de abrir la transacción.
  4. En una transacción (con un candado para que dos corridas no se pisen): por producto
     bajado, upsert en nowcast_producto (una emisión más vieja no pisa una más nueva) y, si
     se escribió, se reemplazan sus manchas: una fila por nivel con la unión de las manchas
     que tocan el Perú, simplificada (~330 m).

Regla de "no borrar": un horizonte que falla no se toca (su fila y sus manchas se quedan), y
con el visor caído no se toca nada. Tampoco se borra por antigüedad: las vistas nowcast_estado
y nowcast_vigente dejan de mostrar una emisión de más de 30 min (el umbral vive solo en la
migración; DETENIDO_MIN es el mismo número, para el latido). Así, cuando SENAMHI se detiene (el
22-09 no publicó nada desde las 20:40), el mapa se vacía solo y el panel dice desde cuándo.

Resumen del latido 'nowcast':
  emision       T según el visor (ISO, hora de Perú); None si el visor no respondió
  edad_min      minutos entre T y ahora
  bajados       horizontes bajados y escritos en esta corrida
  reusados      horizontes que ya tenían T (o una emisión más nueva) guardada
  manchas       {"60": 34}: elementos de nivel 1 a 3 que tocan el recuadro del Perú, de los bajados
  retraso_min   edad_min si se bajó algo: cuánto tarda SENAMHI en publicar (para calibrar los
                30 min); None si no se bajó nada
  detenido      pasaron más de DETENIDO_MIN min desde T (no es falla si el visor respondió:
                va a avisos como "SENAMHI no publica el nowcasting desde las HH:MM")
  fallas        'visor' (caído, sin fichero o con una hora en el futuro), 'h0' / 'h60' /
                'h120' (ese horizonte no se pudo bajar), 'migracion' (faltan las tablas)
  avisos        detalle: errores, elementos descartados, nowcasting detenido...

Si falla el visor, el latido lo registra y la tarea termina con excepción (Celery la marca
como fallida); si falla un horizonte, sigue con los demás.

Corrida suelta, dentro del contenedor worker:
    docker compose run --rm worker python -m backend.ingesta.nowcast
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone

from backend.connectors import senamhi_nowcast as fuente
from backend.connectors.senamhi import HORA_PERU
from backend.db import conectar
from backend.ingesta.guardar import SQL_LATIDO

log = logging.getLogger(__name__)

SERVICIO = "nowcast"
TOLERANCIA_GRADOS = 0.003     # simplificación de las manchas (~330 m; las celdas miden ~2 km)
ORDEN = (60, 120, 0)          # el +1 h primero: es el que el mapa muestra por defecto
DETENIDO_MIN = 30             # el mismo umbral de las vistas nowcast_estado y nowcast_vigente
FUTURO_MIN = 5                # una emisión más adelantada que esto respecto del reloj es un error
# No se empieza a bajar otro horizonte pasados estos segundos desde el inicio de la tarea:
# con la GeoServer colgada un producto tarda hasta ~2 min (2 pedidos de 2 intentos de 30 s,
# fuente.INTENTOS_WFS) y la tarea tiene 240 s (celery_app); así el latido se escribe siempre.
PLAZO_S = 90

# La migración del nowcasting puede no estar aplicada todavía (el worker se despliega aparte).
SQL_HAY_TABLA = "select to_regclass('public.nowcast_producto') is not null"
AVISO_SIN_TABLA = "nowcast_producto: falta la tabla (migración pendiente); no se consultó ni se guardó nada"
SQL_PREVIOS = "select horizonte_min, emision from nowcast_producto"
# Primera sentencia de la transacción de escritura: pone en serie el beat y una corrida suelta.
SQL_CANDADO = "select pg_advisory_xact_lock(hashtext('nowcast'))"
# Una emisión más vieja no pisa (returning vacío): la misma sí se reescribe.
SQL_PRODUCTO = """
insert into nowcast_producto (horizonte_min, fichero, emision, valido_desde, valido_hasta, manchas)
values (%(h)s::smallint, %(fichero)s::text, %(emision)s::timestamptz, %(desde)s::timestamptz,
        %(hasta)s::timestamptz, %(manchas)s::int)
on conflict (horizonte_min) do update set
  fichero = excluded.fichero, emision = excluded.emision, valido_desde = excluded.valido_desde,
  valido_hasta = excluded.valido_hasta, manchas = excluded.manchas, ts_captura = now()
where excluded.emision >= nowcast_producto.emision
returning horizonte_min
"""
SQL_BORRAR_MANCHAS = "delete from nowcast_mancha where horizonte_min = %s"
# Une las manchas de un nivel que tocan el recuadro del Perú (fuente.PERU) y las simplifica.
# Una mancha que cruza la frontera se guarda entera (no se corta). Un nivel sin nada dentro
# del recuadro no deja fila.
_RECUADRO = ", ".join(map(str, fuente.PERU))
SQL_MANCHA = f"""
insert into nowcast_mancha (horizonte_min, nivel, geom)
select %(h)s::smallint, %(nivel)s::smallint, g.geom from (
  select st_multi(st_collectionextract(st_makevalid(st_simplifypreservetopology(st_union(p.geom),
           %(tolerancia)s::float8)), 3)) as geom
  from (select st_makevalid(st_force2d(st_setsrid(st_geomfromgeojson(e.valor), 4326))) as geom
        from jsonb_array_elements_text(%(geometrias)s::jsonb) as e(valor)) p
  where st_intersects(p.geom, st_makeenvelope({_RECUADRO}, 4326))
) g
where g.geom is not null and not st_isempty(g.geom)
"""


def _error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _hhmm(T: datetime, ahora: datetime) -> str:
    """'20:40', o '20:40 del 22-09' si no es de hoy (hora de Perú)."""
    t = T.astimezone(HORA_PERU)
    return f"{t:%H:%M}" if t.date() == ahora.astimezone(HORA_PERU).date() else f"{t:%H:%M} del {t:%d-%m}"


def _previos() -> dict[int, datetime] | None:
    """{horizonte: emisión guardada}; None si la tabla aún no existe."""
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_HAY_TABLA)
        fila = cur.fetchone()
        if not (fila and fila[0]):
            return None
        cur.execute(SQL_PREVIOS)
        return {h: emision for h, emision in cur.fetchall()}


def _resumen(fallas: list[str], avisos: list[str], **datos) -> dict:
    base = {"emision": None, "edad_min": None, "bajados": [], "reusados": [], "manchas": {},
            "retraso_min": None, "detenido": None}
    return {**base, **datos, "fallas": fallas, "avisos": avisos}


def _bajar(T: datetime, previos: dict[int, datetime], inicio: float, fallas: list[str],
           avisos: list[str]) -> tuple[list[fuente.Producto], list[int]]:
    """Productos nuevos de la emisión T, en serie -> (bajados, reusados). inicio: time.monotonic()."""
    bajados: list[fuente.Producto] = []
    reusados: list[int] = []
    pedidos = 0
    for h in ORDEN:
        previo = previos.get(h)
        if previo is not None and previo >= T:
            reusados.append(h)
            if previo > T:
                avisos.append(f"h{h}: ya hay guardada una emisión más nueva ({previo.astimezone(HORA_PERU):%H:%M}) "
                              f"que la del visor ({T.astimezone(HORA_PERU):%H:%M}); no se baja")
            continue
        if time.monotonic() - inicio > PLAZO_S:
            fallas.append(f"h{h}")
            avisos.append(f"h{h}: no se pidió (la tarea ya lleva más de {PLAZO_S} s: SENAMHI responde lento)")
            continue
        if pedidos:
            fuente.pausa()
        pedidos += 1
        try:
            p = fuente.producto(T, h)
        except Exception as e:
            log.warning("Nowcasting SENAMHI: h%s: %s", h, _error(e))
            fallas.append(f"h{h}")
            avisos.append(f"h{h}: {_error(e)}")
            continue
        if p.descartados:
            avisos.append(f"h{h}: {p.descartados} elementos descartados (otro fichero, nivel fuera de 1-3 "
                          "o geometría inválida)")
        bajados.append(p)
    return bajados, reusados


def actualizar(ahora: datetime | None = None) -> dict:
    """Tarea 'nowcast' (Celery la llama sin argumentos; `ahora` (UTC) es para las pruebas)."""
    ahora = ahora or datetime.now(timezone.utc)
    inicio = time.monotonic()
    fallas: list[str] = []
    avisos: list[str] = []
    previos = _previos()
    if previos is None:
        resumen = _resumen(["migracion"], [AVISO_SIN_TABLA])
        with conectar() as conn, conn.cursor() as cur:
            cur.execute(SQL_LATIDO, (SERVICIO, json.dumps(resumen)))
        log.warning("Nowcasting SENAMHI: %s", AVISO_SIN_TABLA)
        return resumen

    # 1) Última emisión según el visor, y 2) los productos que falten (descargas antes de
    #    abrir la transacción: no se deja una transacción esperando la red).
    T = None
    try:
        T = fuente.emision_visor()
        if T > ahora + timedelta(minutes=FUTURO_MIN):
            raise ValueError(f"la última emisión del visor ({T.isoformat()}) es posterior a ahora")
    except Exception as e:
        log.error("Nowcasting SENAMHI: no se pudo leer el visor: %s", _error(e))
        fallas.append("visor")
        avisos.append(f"visor: {_error(e)}")
        T = None
    productos, reusados = _bajar(T, previos, inicio, fallas, avisos) if T else ([], [])

    # 3) Escritura y latido, en una sola transacción, con el candado (también sin nada que
    #    escribir: el latido se escribe siempre).
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_CANDADO)
        escritos: list[fuente.Producto] = []
        for p in productos:
            cur.execute(SQL_PRODUCTO, {"h": p.horizonte, "fichero": p.fichero, "emision": p.emision,
                                       "desde": p.desde, "hasta": p.hasta, "manchas": p.manchas})
            if cur.fetchone() is None:   # otra corrida guardó una emisión más nueva
                reusados.append(p.horizonte)
                avisos.append(f"h{p.horizonte}: ya hay guardada una emisión más nueva que {p.fichero}; no se pisa")
                continue
            cur.execute(SQL_BORRAR_MANCHAS, (p.horizonte,))
            for nivel, geometrias in p.por_nivel.items():
                cur.execute(SQL_MANCHA, {"h": p.horizonte, "nivel": nivel, "geometrias": json.dumps(geometrias),
                                         "tolerancia": TOLERANCIA_GRADOS})
            escritos.append(p)
        datos = {}
        if T is not None:
            edad = (ahora - T) // timedelta(minutes=1)
            # como las vistas: deja de mostrarse pasados los 30 min exactos, no al minuto 31
            detenido = ahora - T > timedelta(minutes=DETENIDO_MIN)
            datos = {"emision": T.astimezone(HORA_PERU).isoformat(), "edad_min": edad,
                     "bajados": [p.horizonte for p in escritos], "reusados": reusados,
                     "manchas": {str(p.horizonte): p.manchas for p in escritos},
                     "retraso_min": edad if escritos else None, "detenido": detenido}
            if detenido:
                avisos.append(f"SENAMHI no publica el nowcasting desde las {_hhmm(T, ahora)}")
        resumen = _resumen(fallas, avisos, **datos)
        cur.execute(SQL_LATIDO, (SERVICIO, json.dumps(resumen)))

    if "visor" in fallas:
        # El latido ya lo registró; la excepción hace que Celery marque la tarea como fallida.
        raise RuntimeError("Nowcasting SENAMHI: no se pudo leer el visor: " + " | ".join(avisos))
    if fallas:
        log.warning("Nowcasting SENAMHI con fallas parciales: %s", resumen)
    else:
        log.info("Nowcasting SENAMHI: %s", resumen)
    return resumen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    actualizar()
