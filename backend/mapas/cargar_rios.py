"""
Cargador de los ríos vigilados (primero el Mashcón, Cajamarca) a Supabase: trazo del río, cuenca,
zonas que podría afectar si se desborda e incidentes pasados documentados.

Son datos estáticos revisados a mano (backend/data/rios/<id>/), por eso no van en la ingesta
horaria: se cargan a mano cuando cambian. Es la única vía que escribe rio_vigilado, rio_zona y
rio_incidente (los avisos hidrológicos los escribe la tarea 'rios').

  rio.json          id, nombre, departamento, estaciones (ANA y SENAMHI), centro del mapa y
                    lugares_aviso (centros poblados que SENAMHI nombra en sus avisos del río)
  cauce.geojson     LineString por parte: 'tronco' (el río resaltado), 'afluente' y 'rotulo'
                    (tronco simplificado: guía para escribir el nombre sobre la línea)
  cuenca.geojson    un MultiPolygon: no se dibuja, decide qué avisos y estaciones de lluvia cuentan
  zonas.geojson     zonas 'estimada' (relieve) y 'estudio' (INDECI-PNUD 2005), MultiPolygon
  faja.geojson      límites de la faja marginal de ANA ('faja'), MultiLineString
  incidentes.json   {"incidentes": [...]} con su fuente; lat/lon null si no se dibujan

Por defecto es una prueba en seco: valida los archivos y muestra el resumen, sin escribir.
Con --aplicar escribe en UNA transacción y es idempotente: upsert por clave/id y borra las zonas
e incidentes de ese río que ya no están en los archivos (correrlo dos veces deja lo mismo).
Guardas contra un archivo vacío o recortado: validar() exige al menos una zona estimada o de
estudio y un incidente, y --aplicar no borra más de la mitad de las zonas o de los incidentes
que el río tiene en la BD salvo con --podar. Un id de incidente que ya es de otro río no se
pisa: la carga se cancela (los ids no llevan el río delante).

Se corre dentro del contenedor worker, que tiene SUPABASE_DB_URL:
    docker compose run --rm worker python -m backend.mapas.cargar_rios
    docker compose run --rm worker python -m backend.mapas.cargar_rios --aplicar
Opciones:
    --rio mashcon     id del río (carpeta backend/data/rios/<rio>; debe coincidir con rio.json)
    --datos DIR       lee los archivos de otra carpeta
    --podar           permite borrar más de la mitad de las zonas o incidentes del río
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

if __package__ in (None, ""):   # permite también: python backend/mapas/cargar_rios.py
    sys.path.insert(0, __file__.rsplit("backend", 1)[0])

from backend.db import conectar
from backend.ingesta.departamentos import nombre_departamento

log = logging.getLogger("cargar_rios")

DATOS = Path(__file__).resolve().parents[1] / "data" / "rios"
ARCHIVOS = ("rio.json", "cauce.geojson", "cuenca.geojson", "zonas.geojson", "faja.geojson", "incidentes.json")

# Lo mismo que exigen los CHECK de la migración rios_vigilados: mejor un error claro aquí que
# una transacción a medias que la BD rechaza.
CAMPOS_ZONA = ("clave", "tipo", "subtipo", "orden", "nombre", "texto", "fuente", "licencia", "atribucion", "metodo")
TIPOS_ZONA = {"estimada": "MultiPolygon", "estudio": "MultiPolygon", "faja": "MultiLineString"}
CAMPOS_INCIDENTE = ("id", "fecha_texto", "tipo", "titulo", "lugar", "precision", "precision_texto",
                    "fuente_tipo", "fuente", "fuente_url")
OPCIONES_INCIDENTE = {
    "tipo": ("desborde", "erosion", "puente", "infraestructura", "crecida"),
    "precision": ("punto", "sector", "distrito", "estacion"),
    "fuente_tipo": ("oficial", "prensa", "academica", "base_historica"),
}
# Recuadro del Perú: atrapa una lat/lon invertida en un archivo editado a mano.
LAT_PERU, LON_PERU = (-18.5, 0.1), (-81.5, -68.5)


def leer(carpeta: Path) -> dict:
    faltan = [a for a in ARCHIVOS if not (carpeta / a).is_file()]
    if faltan:
        raise ValueError(f"faltan archivos: {', '.join(faltan)}")
    return {a: json.loads((carpeta / a).read_text(encoding="utf-8")) for a in ARCHIVOS}


def _https(url, donde: str) -> None:
    if url is not None and not (isinstance(url, str) and url.startswith("https://")):
        raise ValueError(f"{donde}: la URL debe ser https ({url!r})")


def _punto(lat, lon, donde: str) -> None:
    """lat y lon van juntos y caen en el Perú (o los dos son null)."""
    if (lat is None) != (lon is None):
        raise ValueError(f"{donde}: lat y lon van juntos (lat={lat}, lon={lon})")
    if lat is not None and not (LAT_PERU[0] <= lat <= LAT_PERU[1] and LON_PERU[0] <= lon <= LON_PERU[1]):
        raise ValueError(f"{donde}: ({lat}, {lon}) cae fuera del Perú (¿lat y lon invertidas?)")


def _geom(features: list[dict], parte: str, tipo: str) -> dict | None:
    """Une las LineString de una parte del cauce en un MultiLineString (o una LineString)."""
    lineas = [f["geometry"]["coordinates"] for f in features if f["properties"].get("parte") == parte]
    if not lineas:
        return None
    if tipo == "LineString":
        if len(lineas) != 1:
            raise ValueError(f"cauce.geojson: se esperaba una sola línea '{parte}'")
        return {"type": "LineString", "coordinates": lineas[0]}
    return {"type": "MultiLineString", "coordinates": lineas}


def _fila_rio(d: dict, rio_pedido: str | None) -> dict:
    rio = d["rio.json"]
    rid = rio.get("id") or ""
    if not re.fullmatch(r"[a-z0-9_]+", rid):
        raise ValueError(f"rio.json: id inválido ({rid!r}); solo minúsculas, números y _")
    if rio_pedido and rid != rio_pedido:
        raise ValueError(f"rio.json es del río '{rid}', no de '{rio_pedido}' (revisa --rio y --datos)")
    for c in ("nombre", "departamento"):
        if not rio.get(c):
            raise ValueError(f"rio.json: falta {c}")
    if nombre_departamento(rio["departamento"]) != rio["departamento"]:
        raise ValueError(f"rio.json: departamento no canónico ({rio['departamento']!r}, "
                         f"se espera {nombre_departamento(rio['departamento'])!r})")
    centro = rio.get("centro") or {}
    if centro.get("lat") is None or centro.get("zoom") is None:
        raise ValueError("rio.json: centro necesita lat, lon y zoom")
    _punto(centro["lat"], centro.get("lon"), "rio.json centro")
    lugares = rio.get("lugares_aviso", [])
    for l in lugares:
        donde = f"lugar_aviso {l.get('nombre')!r}"
        if not l.get("nombre"):
            raise ValueError("rio.json: un lugar_aviso sin nombre")
        _punto(l.get("lat"), l.get("lon"), donde)
        if l.get("mapa") and l.get("lat") is None:
            raise ValueError(f"{donde}: mapa=true necesita lat y lon")
        _https(l.get("fuente_coord"), donde)

    cauce = d["cauce.geojson"]["features"]
    if any(f["geometry"]["type"] != "LineString" for f in cauce):
        raise ValueError("cauce.geojson: todas las partes deben ser LineString")
    cuenca = d["cuenca.geojson"]["features"]
    if len(cuenca) != 1 or cuenca[0]["geometry"]["type"] != "MultiPolygon":
        raise ValueError("cuenca.geojson: un solo MultiPolygon")
    tronco = _geom(cauce, "tronco", "Multi")
    if tronco is None:
        raise ValueError("cauce.geojson: falta la parte 'tronco'")
    afluentes = _geom(cauce, "afluente", "Multi")
    guia = _geom(cauce, "rotulo", "LineString")
    return {
        "id": rid, "nombre": rio["nombre"], "departamento": rio["departamento"],
        "estacion_ana": rio.get("estacion_ana"), "rio_ana": rio.get("rio_ana"),
        "estacion_senamhi": rio.get("estacion_senamhi"),
        "centro_lat": centro["lat"], "centro_lon": centro["lon"], "zoom": centro["zoom"],
        "cauce": json.dumps(tronco),
        "afluentes": json.dumps(afluentes) if afluentes else None,
        "guia_rotulo": json.dumps(guia) if guia else None,
        "cuenca": json.dumps(cuenca[0]["geometry"]),
        "lugares_aviso": json.dumps(lugares, ensure_ascii=False),
        "fuentes": json.dumps(rio.get("fuentes", {}), ensure_ascii=False),
    }


def _zonas(d: dict, rid: str) -> list[dict]:
    zonas = []
    for f in d["zonas.geojson"]["features"] + d["faja.geojson"]["features"]:
        p = f["properties"]
        falta = [c for c in CAMPOS_ZONA if p.get(c) in (None, "")]
        if falta:
            raise ValueError(f"zona {p.get('clave')}: faltan {falta}")
        if not p["clave"].startswith(f"{rid}:"):
            raise ValueError(f"zona {p['clave']}: la clave debe empezar con '{rid}:'")
        if TIPOS_ZONA.get(p["tipo"]) != f["geometry"]["type"]:
            raise ValueError(f"zona {p['clave']}: tipo {p['tipo']} con geometría {f['geometry']['type']}")
        _https(p.get("fuente_url"), f"zona {p['clave']}")
        zonas.append({**{c: p[c] for c in CAMPOS_ZONA}, "rio": rid, "fuente_url": p.get("fuente_url"),
                      "fecha_fuente": p.get("fecha_fuente"), "area_km2": p.get("area_km2"),
                      "geom": json.dumps(f["geometry"])})
    claves = [z["clave"] for z in zonas]
    repetidas = sorted({c for c in claves if claves.count(c) > 1})
    if repetidas:
        raise ValueError(f"zonas: claves repetidas {repetidas}")
    return zonas


def _incidentes(d: dict, rid: str) -> list[dict]:
    datos = d["incidentes.json"]
    if datos.get("rio", rid) != rid:
        raise ValueError(f"incidentes.json es del río '{datos['rio']}', no de '{rid}'")
    incidentes = []
    for i in datos["incidentes"]:
        donde = f"incidente {i.get('id')}"
        falta = [c for c in CAMPOS_INCIDENTE if i.get(c) in (None, "")]
        if falta:
            raise ValueError(f"{donde}: faltan {falta}")
        for c, opciones in OPCIONES_INCIDENTE.items():
            if i[c] not in opciones:
                raise ValueError(f"{donde}: {c} {i[c]!r} no es uno de {opciones}")
        if i.get("fecha") is not None:
            try:
                date.fromisoformat(i["fecha"])
            except (TypeError, ValueError):
                raise ValueError(f"{donde}: fecha {i['fecha']!r} no es AAAA-MM-DD (o null)") from None
        _https(i["fuente_url"], donde)
        for o in i.get("otras_fuentes", []):
            _https(o.get("url"), f"{donde} (otras_fuentes)")
        _punto(i.get("lat"), i.get("lon"), donde)
        if i["precision"] in ("punto", "sector") and i.get("lat") is None:
            raise ValueError(f"{donde}: precisión {i['precision']} necesita lat y lon")
        incidentes.append({**{c: i[c] for c in CAMPOS_INCIDENTE}, "rio": rid,
                           "fecha": i.get("fecha"), "detalle": i.get("detalle"), "caudal_m3s": i.get("caudal_m3s"),
                           "otras_fuentes": json.dumps(i.get("otras_fuentes", []), ensure_ascii=False),
                           "lat": i.get("lat"), "lon": i.get("lon")})
    ids = [i["id"] for i in incidentes]
    repetidos = sorted({x for x in ids if ids.count(x) > 1})
    if repetidos:
        raise ValueError(f"incidentes: ids repetidos {repetidos}")
    return incidentes


def validar(d: dict, rio: str | None = None) -> tuple[dict, list[dict], list[dict]]:
    """(fila de rio_vigilado, zonas, incidentes). Lanza ValueError con lo que esté mal."""
    fila = _fila_rio(d, rio)
    zonas, incidentes = _zonas(d, fila["id"]), _incidentes(d, fila["id"])
    # Un archivo vacío o mal filtrado borraría con --aplicar todo lo del río (la poda).
    if not any(z["tipo"] in ("estimada", "estudio") for z in zonas):
        raise ValueError("zonas.geojson no tiene ninguna zona estimada ni de estudio: un río vigilado necesita "
                         "su mapa de zonas (¿archivo vacío o mal generado?)")
    if not incidentes:
        raise ValueError("incidentes.json no tiene incidentes (¿archivo vacío o mal generado?)")
    return fila, zonas, incidentes


def resumen(fila: dict, zonas: list[dict], incidentes: list[dict]) -> str:
    """'Río mashcon: 13 zonas {estimada 3, estudio 4, faja 6}, 14 incidentes (10 en el mapa)'."""
    tipos: dict[str, int] = {}
    for z in zonas:
        tipos[z["tipo"]] = tipos.get(z["tipo"], 0) + 1
    por_tipo = ", ".join(f"{t} {n}" for t, n in sorted(tipos.items()))
    en_mapa = sum(1 for i in incidentes if i["lat"] is not None)
    return f"Río {fila['id']}: {len(zonas)} zonas {{{por_tipo}}}, {len(incidentes)} incidentes ({en_mapa} en el mapa)"


SQL_RIO = """
insert into rio_vigilado (id, nombre, departamento, estacion_ana, rio_ana, estacion_senamhi, centro_lat, centro_lon,
                          zoom, cauce, afluentes, guia_rotulo, cuenca, lugares_aviso, fuentes)
values (%(id)s, %(nombre)s, %(departamento)s, %(estacion_ana)s, %(rio_ana)s, %(estacion_senamhi)s, %(centro_lat)s,
        %(centro_lon)s, %(zoom)s, st_setsrid(st_geomfromgeojson(%(cauce)s), 4326),
        st_setsrid(st_geomfromgeojson(%(afluentes)s), 4326), st_setsrid(st_geomfromgeojson(%(guia_rotulo)s), 4326),
        st_setsrid(st_geomfromgeojson(%(cuenca)s), 4326), %(lugares_aviso)s::jsonb, %(fuentes)s::jsonb)
on conflict (id) do update set
  nombre = excluded.nombre, departamento = excluded.departamento, estacion_ana = excluded.estacion_ana,
  rio_ana = excluded.rio_ana, estacion_senamhi = excluded.estacion_senamhi, centro_lat = excluded.centro_lat,
  centro_lon = excluded.centro_lon, zoom = excluded.zoom, cauce = excluded.cauce, afluentes = excluded.afluentes,
  guia_rotulo = excluded.guia_rotulo, cuenca = excluded.cuenca, lugares_aviso = excluded.lugares_aviso,
  fuentes = excluded.fuentes, ts_carga = now()
"""
SQL_ZONA = """
insert into rio_zona (clave, rio, tipo, subtipo, orden, nombre, texto, fuente, fuente_url, licencia, atribucion,
                      metodo, fecha_fuente, area_km2, geom)
values (%(clave)s, %(rio)s, %(tipo)s, %(subtipo)s, %(orden)s, %(nombre)s, %(texto)s, %(fuente)s, %(fuente_url)s,
        %(licencia)s, %(atribucion)s, %(metodo)s, %(fecha_fuente)s, %(area_km2)s,
        st_setsrid(st_geomfromgeojson(%(geom)s), 4326))
on conflict (clave) do update set
  rio = excluded.rio, tipo = excluded.tipo, subtipo = excluded.subtipo, orden = excluded.orden,
  nombre = excluded.nombre, texto = excluded.texto, fuente = excluded.fuente, fuente_url = excluded.fuente_url,
  licencia = excluded.licencia, atribucion = excluded.atribucion, metodo = excluded.metodo,
  fecha_fuente = excluded.fecha_fuente, area_km2 = excluded.area_km2, geom = excluded.geom, ts_carga = now()
"""
SQL_INCIDENTE = """
insert into rio_incidente (id, rio, fecha, fecha_texto, tipo, titulo, lugar, detalle, precision, precision_texto,
                           caudal_m3s, fuente_tipo, fuente, fuente_url, otras_fuentes, lat, lon)
values (%(id)s, %(rio)s, %(fecha)s, %(fecha_texto)s, %(tipo)s, %(titulo)s, %(lugar)s, %(detalle)s, %(precision)s,
        %(precision_texto)s, %(caudal_m3s)s, %(fuente_tipo)s, %(fuente)s, %(fuente_url)s, %(otras_fuentes)s::jsonb,
        %(lat)s, %(lon)s)
on conflict (id) do update set
  fecha = excluded.fecha, fecha_texto = excluded.fecha_texto, tipo = excluded.tipo,
  titulo = excluded.titulo, lugar = excluded.lugar, detalle = excluded.detalle, precision = excluded.precision,
  precision_texto = excluded.precision_texto, caudal_m3s = excluded.caudal_m3s, fuente_tipo = excluded.fuente_tipo,
  fuente = excluded.fuente, fuente_url = excluded.fuente_url, otras_fuentes = excluded.otras_fuentes,
  lat = excluded.lat, lon = excluded.lon, ts_carga = now()
where rio_incidente.rio = excluded.rio
"""
SQL_PODAR_ZONAS = "delete from rio_zona where rio = %s and not (clave = any(%s))"
SQL_PODAR_INCIDENTES = "delete from rio_incidente where rio = %s and not (id = any(%s))"
# Cuánto hay del río y cuánto borraría la poda: (zonas, zonas a borrar, incidentes, incidentes a borrar).
SQL_CONTAR = """
select (select count(*) from rio_zona where rio = %(rio)s),
       (select count(*) from rio_zona where rio = %(rio)s and not (clave = any(%(claves)s))),
       (select count(*) from rio_incidente where rio = %(rio)s),
       (select count(*) from rio_incidente where rio = %(rio)s and not (id = any(%(ids)s)))
"""
# Ids de incidente que ya son de otro río (el upsert no los pisa: se cancela la carga).
SQL_INCIDENTES_AJENOS = "select id, rio from rio_incidente where id = any(%s) and rio <> %s order by id"
SQL_HAY_TABLAS = ("select to_regclass('public.rio_vigilado') is not null and to_regclass('public.rio_zona') is not null "
                  "and to_regclass('public.rio_incidente') is not null")


def hay_tablas(conn) -> bool:
    """¿Ya se aplicó la migración rios_vigilados?"""
    with conn.cursor() as cur:
        cur.execute(SQL_HAY_TABLAS)
        return bool(cur.fetchone()[0])


class PodaGrande(ValueError):
    """La carga borraría más de la mitad de lo que el río tiene en la BD (sin --podar)."""


def aplicar(conn, fila: dict, zonas: list[dict], incidentes: list[dict], podar: bool = False) -> tuple[int, int]:
    """
    Escribe el río en la transacción de conn (no hace commit). (zonas, incidentes) que se borraron.
    Antes de escribir nada lanza PodaGrande si borraría más de la mitad de las zonas o de los
    incidentes del río (salvo podar=True) y ValueError si un id de incidente ya es de otro río.
    """
    claves, ids = [z["clave"] for z in zonas], [i["id"] for i in incidentes]
    with conn.cursor() as cur:
        cur.execute(SQL_CONTAR, {"rio": fila["id"], "claves": claves, "ids": ids})
        n_zonas, borrar_zonas, n_incidentes, borrar_incidentes = cur.fetchone()
        if not podar and (2 * borrar_zonas > n_zonas or 2 * borrar_incidentes > n_incidentes):
            raise PodaGrande(f"la carga borraría {borrar_zonas} de {n_zonas} zonas y {borrar_incidentes} de "
                             f"{n_incidentes} incidentes del río '{fila['id']}' (más de la mitad): revisa los "
                             "archivos o, si es lo que quieres, agrega --podar")
        cur.execute(SQL_INCIDENTES_AJENOS, (ids, fila["id"]))
        ajenos = cur.fetchall()
        if ajenos:
            raise ValueError("estos incidentes ya son de otro río (usa otro id): "
                             + ", ".join(f"{i} ({r})" for i, r in ajenos))
        cur.execute(SQL_RIO, fila)
        cur.execute(SQL_PODAR_ZONAS, (fila["id"], claves))
        zonas_borradas = cur.rowcount
        cur.executemany(SQL_ZONA, zonas)
        cur.execute(SQL_PODAR_INCIDENTES, (fila["id"], ids))
        incidentes_borrados = cur.rowcount
        cur.executemany(SQL_INCIDENTE, incidentes)
    return zonas_borradas, incidentes_borrados


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Carga los ríos vigilados (trazo, zonas e incidentes) a Supabase.")
    ap.add_argument("--rio", default="mashcon", help="id del río (por defecto mashcon)")
    ap.add_argument("--datos", type=Path, default=None, metavar="DIR",
                    help="carpeta con los archivos (por defecto backend/data/rios/<rio>)")
    ap.add_argument("--aplicar", action="store_true", help="escribe en la BD (sin esto es prueba en seco)")
    ap.add_argument("--podar", action="store_true",
                    help="con --aplicar, permite borrar más de la mitad de las zonas o incidentes del río")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    carpeta = args.datos or DATOS / args.rio
    try:
        fila, zonas, incidentes = validar(leer(carpeta), args.rio)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        log.error("Datos inválidos en %s: %s", carpeta, e)
        return 1
    log.info("%s", resumen(fila, zonas, incidentes))
    if not args.aplicar:
        log.info("Prueba en seco: no se escribió nada. Usa --aplicar para guardar.")
        return 0

    try:
        with conectar() as conn:   # una sola transacción: commit al salir, rollback si algo falla
            if not hay_tablas(conn):
                log.error("Faltan las tablas de los ríos vigilados: aplica antes la migración rios_vigilados "
                          "(supabase/migrations/).")
                return 2
            zonas_borradas, incidentes_borrados = aplicar(conn, fila, zonas, incidentes, podar=args.podar)
    except RuntimeError as e:      # falta SUPABASE_DB_URL o psycopg
        log.error("%s Corre el cargador dentro del contenedor worker.", e)
        return 2
    except ValueError as e:        # PodaGrande o incidente de otro río: rollback, no se escribió nada
        log.error("No se guardó nada: %s", e)
        return 1
    log.info("Guardado: rio_vigilado=%s, %d zonas y %d incidentes (se borraron %d zonas y %d incidentes "
             "que ya no están en los archivos).", fila["id"], len(zonas), len(incidentes),
             zonas_borradas, incidentes_borrados)
    return 0


if __name__ == "__main__":
    sys.exit(main())
