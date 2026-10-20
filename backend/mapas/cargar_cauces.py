"""
Cargador del trazo (cauce) de los ríos con estación de caudal de ANA (vista caudal_actual) y de los
ríos con avisos hidrológicos de SENAMHI, a la tabla rio_cauce: la web los resalta como ya hace con
el Mashcón (rio_vigilado). Fuente: ANA - GeoSNIRH (backend/connectors/ana_rios.py), dos capas:
RJ056 (red hidrográfica oficial de 2018, línea central por tramo) e IGN (Carta Nacional 1:100 000).

Carga ÚNICA, a mano (como cargar_rios.py y cargar_fen.py): la capa RJ056 es de 2018 y la IGN
cambió por última vez en abril de 2026; la web nunca consulta a ANA en vivo. Se repite cuando
caudal_actual gana estaciones (la prueba en seco lista los ríos que aún no tienen fila).

Emparejamiento (regla verificada en vivo el 14-10-2026, docs/README-tecnico.md):
  1. El nombre de ANA se normaliza (sin tildes, minúsculas, sin 'Río'/'Quebrada' delante) y se busca
     en la capa con un comodín por letra acentuable ('rimac' -> LIKE '% R_M_C'), porque ANA escribe
     la tilde a veces sí y a veces no.
  2. Solo cuentan los tramos con ese nombre que pasan a 2000 m de alguna estación del río (ANA o
     SENAMHI): así se separan los homónimos (los dos 'San Pedro', el Chancay de Lambayeque y el de
     Huaral, las seis quebradas 'Chonta').
  3. Con el tramo encontrado se baja el río completo (todos los tramos del país con ese nombre) y se
     queda solo con los CONECTADOS al tramo de la estación (extremos a menos de 200 m): el Huallaga
     son 10 tramos Pfafstetter; el Chancay de Huaral no toca al de Lambayeque.
  4. Orden de preferencia: RJ056 (oficial, línea central) y, si no tiene el río, IGN. El Mashcón y
     cualquier río que ya esté en rio_vigilado (OSM curado a mano) no se carga aquí.
  5. Los 15 casos que no coinciden por nombre están en backend/data/rios/cauces_alias.json (nombre
     en la capa, capa forzada, radio mayor cuando la coordenada de la estación de ANA está
     desplazada, o 'sin_trazo' para el lago Titicaca y el canal Canopampa).
  Se guarda el río completo: las capas no traen el sentido del flujo ni tramos anclados a la
  estación, así que no se recorta aguas arriba/abajo por defecto. --recorte KM deja solo lo que
  está a menos de KM km (en línea recta) de alguna estación del río.

Validación (la prueba en seco la muestra por río; nada se escribe si falla):
  - alguna estación a menos de 300 m del trazo (si no: alias con radio_m o --forzar; las demás
    estaciones lejos se avisan, p. ej. Jesús Túnel a 865 m: coordenada del túnel, no del cauce);
  - km del trazo entre el 50 % y el 150 % de lo declarado por la capa (más del 150 %: la capa IGN
    dibujó las dos orillas, no se guarda);
  - ninguna coordenada fuera del Perú.
  Un río sin trazo no se inventa: la fila no se crea y la web sigue dibujando la estación como disco.

Se corre dentro del contenedor worker (tiene SUPABASE_DB_URL) o con la variable exportada:
    docker compose run --rm worker python -m backend.mapas.cargar_cauces              # prueba en seco
    docker compose run --rm worker python -m backend.mapas.cargar_cauces --aplicar    # escribe
Opciones:
    --rio NOMBRE      solo ese río (rio_ana o el nombre literal de caudal_actual)
    --forzar          guarda también los ríos con estación a más de 300 m o km fuera de rango
    --recorte KM      recorta el trazo a KM km de las estaciones (por defecto, el río completo)
    --desde-copia     lee las copias de backend/data/cauces/ en vez de consultar a GeoSNIRH
    --sin-copia       no guarda copias en backend/data/cauces/
    --podar           con --aplicar, borra de rio_cauce los ríos que ya no están en caudal_actual
                      ni en los avisos (sin esto nada se borra: un río que no se pudo bajar se queda)
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):   # permite también: python backend/mapas/cargar_cauces.py
    sys.path.insert(0, __file__.rsplit("backend", 1)[0])

from backend.connectors import ana_rios
from backend.connectors.ana_rios import Capa, Tramo, nombre_normalizado
from backend.db import conectar

log = logging.getLogger("cargar_cauces")

RAIZ = Path(__file__).resolve().parents[1]
ALIAS_ARCHIVO = RAIZ / "data" / "rios" / "cauces_alias.json"
COPIAS = RAIZ / "data" / "cauces"

RADIO_M = 2000          # a qué distancia de la estación debe pasar el río para darlo por encontrado
DIST_OK_M = 300         # alguna estación debe quedar a menos de esto del trazo elegido
DIST_SENAMHI_M = 5000   # una estación SENAMHI emparejada solo por nombre debe pasar a menos de esto
TOL_CONEXION_M = 200    # dos tramos se consideran unidos si un extremo queda a menos de esto del otro
KM_MIN, KM_MAX = 0.5, 1.5   # km del trazo frente a lo declarado por la capa
LAT_PERU, LON_PERU = (-18.5, 0.1), (-81.5, -68.5)
TITULO_AVISO = re.compile(r"R[IÍ]O\s+(.+?)\s+-\s+ESTACI[OÓ]N\s+(.+?)\s*$", re.IGNORECASE)


# ----------------------------------------------------------------------------- geometría (stdlib)
def _metros(lat: float) -> tuple[float, float]:
    """Metros por grado de longitud y de latitud a esa latitud (equirectangular: sobra para < 50 km)."""
    return 111_320.0 * math.cos(math.radians(lat)), 111_320.0


def haversine_km(a: list[float], b: list[float]) -> float:
    """a y b son [lon, lat]."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def longitud_km(lineas: list[list[list[float]]]) -> float:
    return sum(haversine_km(l[i], l[i + 1]) for l in lineas for i in range(len(l) - 1))


def distancia_m(lat: float, lon: float, lineas: list[list[list[float]]]) -> float:
    """Distancia mínima (m) del punto a la polilínea (proyección sobre cada segmento)."""
    mx, my = _metros(lat)
    px, py = lon * mx, lat * my
    mejor = math.inf
    for l in lineas:
        for i in range(len(l) - 1):
            ax, ay = l[i][0] * mx, l[i][1] * my
            bx, by = l[i + 1][0] * mx, l[i + 1][1] * my
            dx, dy = bx - ax, by - ay
            t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
            d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d < mejor:
                mejor = d
    return mejor


def en_peru(lineas: list[list[list[float]]]) -> bool:
    return all(LAT_PERU[0] <= y <= LAT_PERU[1] and LON_PERU[0] <= x <= LON_PERU[1] for l in lineas for x, y in l)


def _extremos(t: Tramo) -> list[list[float]]:
    return [p for l in t.lineas for p in (l[0], l[-1])]


def unir_tramos(tramos: list[Tramo], semillas: list[Tramo], tol_m: float = TOL_CONEXION_M) -> list[Tramo]:
    """
    Los tramos unidos (directa o indirectamente) a las semillas: un tramo entra si uno de sus
    extremos queda a menos de tol_m de algún vértice de un tramo ya aceptado. Separa homónimos
    lejanos (los dos 'Río Chancay') y arma el río completo a partir del tramo de la estación.
    """
    ids_semilla = {(t.capa, t.id) for t in semillas}
    aceptados = [t for t in tramos if (t.capa, t.id) in ids_semilla] or list(semillas)
    pendientes = [t for t in tramos if (t.capa, t.id) not in ids_semilla]
    cambio = True
    while cambio and pendientes:
        cambio = False
        for t in list(pendientes):
            if any(distancia_m(p[1], p[0], a.lineas) <= tol_m for p in _extremos(t) for a in aceptados):
                aceptados.append(t)
                pendientes.remove(t)
                cambio = True
    return sorted(aceptados, key=lambda t: (t.codigo, t.id))


def recortar(lineas: list[list[list[float]]], anclas: list[tuple[float, float]], km: float) -> list[list[list[float]]]:
    """Se queda con las partes de la línea a menos de km de alguna ancla (lat, lon), partiéndola si hace falta."""
    salida: list[list[list[float]]] = []
    for l in lineas:
        actual: list[list[float]] = []
        for p in l:
            if any(haversine_km(p, [lon, lat]) <= km for lat, lon in anclas):
                actual.append(p)
            elif len(actual) >= 2:
                salida.append(actual)
                actual = []
            else:
                actual = []
        if len(actual) >= 2:
            salida.append(actual)
    return salida


# ----------------------------------------------------------------------------- qué ríos buscar
def slug(rio: str) -> str:
    """'Chancay Lambayeque' -> 'chancay_lambayeque'; 'Río Santiago' -> 'santiago'."""
    return re.sub(r"[^a-z0-9]+", "_", nombre_normalizado(rio)).strip("_")


@dataclass
class Ancla:
    nombre: str
    lat: float | None
    lon: float | None
    origen: str          # 'ana' | 'senamhi'
    codigo: str = ""     # ce de SENAMHI


@dataclass
class Objetivo:
    rio_ana: str                     # slug
    rio: str                         # literal de caudal_actual.rio (o del título de SENAMHI)
    departamentos: set[str] = field(default_factory=set)
    anclas: list[Ancla] = field(default_factory=list)
    ces: list[str] = field(default_factory=list)
    solo_senamhi: bool = False

    @property
    def estaciones(self) -> list[str]:
        return [a.nombre for a in self.anclas if a.origen == "ana"]

    @property
    def con_coordenada(self) -> list[Ancla]:
        return [a for a in self.anclas if a.lat is not None and a.lon is not None]


def leer_alias(ruta: Path = ALIAS_ARCHIVO) -> dict:
    datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    return {"rios": datos.get("rios", {}), "senamhi": datos.get("senamhi", {})}


def titulo_aviso(titulo: str) -> tuple[str, str] | None:
    """'INCREMENTO DEL CAUDAL DEL RÍO MASHCÓN - ESTACIÓN MASHCÓN' -> ('MASHCÓN', 'MASHCÓN')."""
    m = TITULO_AVISO.search(titulo or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else None


def armar_objetivos(caudal: list[dict], avisos: list[dict], vigilados: list[dict], alias: dict) -> tuple[list[Objetivo], list[str]]:
    """
    caudal: filas de caudal_actual {rio, departamento, estacion, lat, lon}; avisos: {ce, titulo, n, nombre,
    departamento, lat, lon} (una por ce y título); vigilados: rio_vigilado {rio_ana, estacion_ana}.
    Devuelve (objetivos, avisos de texto). Un ce de SENAMHI se une al río por el nombre de su estación
    (igual a una de ANA) o, si no, por el nombre del río del título; si no hay río de ANA, es un
    objetivo solo de SENAMHI (necesita la coordenada de la estación en la tabla estacion).
    """
    notas: list[str] = []
    por_rio: dict[str, Objetivo] = {}
    for f in caudal:
        o = por_rio.setdefault(slug(f["rio"]), Objetivo(rio_ana=slug(f["rio"]), rio=f["rio"]))
        if f.get("departamento"):
            o.departamentos.add(f["departamento"])
        o.anclas.append(Ancla(f["estacion"], f.get("lat"), f.get("lon"), "ana"))
    estaciones_ana = {nombre_normalizado(a.nombre): o for o in por_rio.values() for a in o.anclas}

    # título más frecuente por estación SENAMHI (varían: 'RÍO SALCCA' 26 veces, 'RÍO VILCANOTA' 9)
    conteo: dict[str, Counter] = {}
    datos_ce: dict[str, dict] = {}
    for f in avisos:
        partes = titulo_aviso(f["titulo"])
        if not partes:
            continue
        conteo.setdefault(f["ce"], Counter())[partes] += int(f.get("n") or 1)
        datos_ce[f["ce"]] = f
    for ce in sorted(conteo):
        (rio_t, est_t), _ = conteo[ce].most_common(1)[0]
        d = datos_ce[ce]
        ancla = Ancla(d.get("nombre") or est_t.title(), d.get("lat"), d.get("lon"), "senamhi", ce)
        nombre_rio = alias["senamhi"].get(nombre_normalizado(rio_t), nombre_normalizado(rio_t))
        o = estaciones_ana.get(nombre_normalizado(est_t)) or por_rio.get(slug(nombre_rio))
        if o is None:
            if ancla.lat is None:
                notas.append(f"SENAMHI {ce} ('{rio_t} - {est_t}'): río sin estación de ANA y sin coordenada en "
                             "la tabla estacion: no se busca")
                continue
            o = por_rio.setdefault(slug(nombre_rio), Objetivo(rio_ana=slug(nombre_rio), rio=nombre_rio.title(),
                                                            solo_senamhi=True))
        if d.get("departamento"):
            o.departamentos.add(d["departamento"])
        o.ces.append(ce)
        o.anclas.append(ancla)

    # el Mashcón (y cualquier río vigilado) ya tiene su trazo revisado a mano: no se duplica
    ya = {slug(v["rio_ana"]) for v in vigilados if v.get("rio_ana")}
    ya |= {o.rio_ana for o in por_rio.values()
           for v in vigilados if v.get("estacion_ana") and nombre_normalizado(v["estacion_ana"]) in
           {nombre_normalizado(e) for e in o.estaciones}}
    objetivos = []
    for o in por_rio.values():
        if o.rio_ana in ya:
            notas.append(f"{o.rio_ana}: ya está en rio_vigilado (trazo OSM revisado a mano): no se carga aquí")
            continue
        objetivos.append(o)
    return sorted(objetivos, key=lambda o: o.rio_ana), notas


# ----------------------------------------------------------------------------- emparejar y validar
@dataclass
class Resultado:
    objetivo: Objetivo
    capa: Capa | None = None
    tramos: list[Tramo] = field(default_factory=list)
    lineas: list[list[list[float]]] = field(default_factory=list)
    km: float = 0.0
    km_declarado: float | None = None
    distancias: list[dict] = field(default_factory=list)   # [{estacion, origen, m}]
    avisos: list[str] = field(default_factory=list)
    motivo: str | None = None                               # por qué queda sin trazo
    alias: dict = field(default_factory=dict)
    url_consulta: str = ""
    bytes: int = 0
    desde_copia: bool = False

    @property
    def ok(self) -> bool:
        return self.motivo is None and bool(self.lineas)

    @property
    def nombre_capa(self) -> str:
        return self.tramos[0].nombre if self.tramos else ""

    @property
    def nombre(self) -> str:
        return self.alias.get("mostrar") or self.nombre_capa

    @property
    def dist_min_m(self) -> float | None:
        return min((d["m"] for d in self.distancias), default=None)


def _capas_para(alias: dict) -> list[Capa]:
    if alias.get("capa"):
        return [ana_rios.CAPAS[alias["capa"]]]
    return [ana_rios.RJ056, ana_rios.IGN]


def emparejar(o: Objetivo, alias_rios: dict, descargar=ana_rios._bajar, pausa: float = ana_rios.PAUSA_S,
              recorte_km: float | None = None, forzar: bool = False) -> Resultado:
    """Busca el río en las capas (RJ056 y luego IGN) a partir de sus estaciones y baja el río completo."""
    r = Resultado(objetivo=o, alias=alias_rios.get(o.rio_ana, {}))
    if r.alias.get("sin_trazo"):
        r.motivo = r.alias["sin_trazo"]
        return r
    anclas = sorted(o.con_coordenada, key=lambda a: a.origen != "ana")   # primero las de ANA
    if not anclas:
        r.motivo = "ninguna estación con coordenada: no hay dónde buscar"
        return r
    nombre = r.alias.get("nombre") or o.rio
    radio = int(r.alias.get("radio_m") or RADIO_M)
    for capa in _capas_para(r.alias):
        for a in anclas:
            semillas, url, nbytes = ana_rios.buscar_cerca(capa, nombre, (a.lat, a.lon), radio, descargar=descargar)
            r.bytes += nbytes
            time.sleep(pausa)
            if not semillas:
                continue
            todos, url, nbytes = ana_rios.bajar_rio(capa, semillas[0].nombre, descargar=descargar)
            r.bytes += nbytes
            r.capa, r.url_consulta = capa, url
            r.tramos = unir_tramos(todos, semillas)
            time.sleep(pausa)
            return completar(r, nombre, radio, recorte_km, forzar)
    r.motivo = (f"sin línea llamada '{nombre}' a {radio} m de sus estaciones en RJ056 ni en IGN "
                "(revisa backend/data/rios/cauces_alias.json)")
    return r


def completar(r: Resultado, nombre: str, radio: int, recorte_km: float | None = None, forzar: bool = False) -> Resultado:
    """Une los tramos, mide, calcula distancias a las estaciones y valida. Deja motivo si no pasa."""
    o = r.objetivo
    r.lineas = [l for t in r.tramos for l in t.lineas]
    if recorte_km:
        r.lineas = recortar(r.lineas, [(a.lat, a.lon) for a in o.con_coordenada], recorte_km)
    r.km = round(longitud_km(r.lineas), 2)
    declarados = [t.km_declarado for t in r.tramos if t.km_declarado]
    r.km_declarado = round(sum(declarados), 2) if declarados else None
    r.distancias = [{"estacion": a.nombre, "origen": a.origen, "codigo": a.codigo,
                     "m": round(distancia_m(a.lat, a.lon, r.lineas), 1)} for a in o.con_coordenada] if r.lineas else []
    if nombre_normalizado(nombre) != nombre_normalizado(o.rio):
        r.avisos.append(f"alias: ANA lo llama '{o.rio}', en la capa es '{r.nombre_capa}'")
    if not r.lineas:
        r.motivo = "sin geometría" + (" a esa distancia de las estaciones (--recorte)" if recorte_km else " en la capa")
        return r
    if not en_peru(r.lineas):
        r.motivo = "coordenadas fuera del Perú (¿lat y lon invertidas?)"
        return r
    if r.capa is ana_rios.IGN and len(r.tramos) > 1:
        r.avisos.append(f"IGN con {len(r.tramos)} registros unidos (en ríos anchos puede ser la otra orilla)")
    # estaciones de ANA que quedan lejos: se avisa (la coordenada de ANA puede ser la del túnel o la bocatoma)
    for d in r.distancias:
        if d["origen"] == "ana" and d["m"] > DIST_OK_M:
            r.avisos.append(f"estación {d['estacion']} a {d['m']:.0f} m del trazo")
    # una estación SENAMHI unida solo por el nombre del río no puede estar a 5 km: es otro río homónimo
    for d in list(r.distancias):
        if d["origen"] == "senamhi" and d["m"] > DIST_SENAMHI_M and d["codigo"] in o.ces:
            r.avisos.append(f"SENAMHI {d['codigo']} ({d['estacion']}) a {d['m'] / 1000:.1f} km: no se une a este río")
            o.ces.remove(d["codigo"])
            r.distancias.remove(d)
    dmin = r.dist_min_m
    if dmin is None or dmin > max(DIST_OK_M, radio if r.alias.get("radio_m") else 0):
        msg = f"ninguna estación a menos de {DIST_OK_M} m del trazo (la más cercana a {dmin:.0f} m)"
        if forzar:
            r.avisos.append(msg + " [forzado]")
        else:
            r.motivo = msg + ": agrega radio_m en cauces_alias.json o usa --forzar"
            return r
    elif dmin > DIST_OK_M:          # aceptado por el radio_m del alias: queda dicho en la nota
        cercana = min(r.distancias, key=lambda d: d["m"])
        r.avisos.append(f"la estación más cercana ({cercana['estacion']}) queda a {dmin:.0f} m del trazo "
                        f"(aceptado por radio_m del alias)")
    if r.km_declarado:
        razon = r.km / r.km_declarado
        if razon > KM_MAX:
            msg = f"{r.km} km frente a {r.km_declarado} km declarados ({razon:.0%}): parece doble línea (orillas)"
            if forzar:
                r.avisos.append(msg + " [forzado]")
            else:
                r.motivo = msg
                return r
        if razon < KM_MIN and not recorte_km:
            r.avisos.append(f"{r.km} km frente a {r.km_declarado} km declarados ({razon:.0%})")
    return r


# ----------------------------------------------------------------------------- copias en disco
def guardar_copia(r: Resultado, carpeta: Path = COPIAS) -> Path:
    """FeatureCollection con los tramos elegidos (geometría tal como se guarda) y los datos de la consulta."""
    carpeta.mkdir(parents=True, exist_ok=True)
    fc = {
        "type": "FeatureCollection",
        "rio_ana": r.objetivo.rio_ana, "rio": r.objetivo.rio, "capa": r.capa.clave, "nombre_capa": r.nombre_capa,
        "fuente": r.capa.fuente, "fuente_url": r.capa.fuente_url, "atribucion": r.capa.atribucion,
        "licencia": ana_rios.LICENCIA, "url_consulta": r.url_consulta, "bytes_descargados": r.bytes,
        "descargado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features": [{"type": "Feature", "id": t.id,
                      "properties": {**t.props, "capa": t.capa},
                      "geometry": {"type": "MultiLineString", "coordinates": t.lineas}} for t in r.tramos],
    }
    ruta = carpeta / f"{r.objetivo.rio_ana}.geojson"
    ruta.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return ruta


def leer_copia(o: Objetivo, alias_rios: dict, carpeta: Path = COPIAS) -> Resultado | None:
    ruta = carpeta / f"{o.rio_ana}.geojson"
    if not ruta.is_file():
        return None
    fc = json.loads(ruta.read_text(encoding="utf-8"))
    capa = ana_rios.CAPAS[fc["capa"]]
    r = Resultado(objetivo=o, capa=capa, alias=alias_rios.get(o.rio_ana, {}), url_consulta=fc.get("url_consulta", ""),
                  bytes=int(fc.get("bytes_descargados") or 0), desde_copia=True)
    for f in fc["features"]:
        p = f["properties"]
        km = p.get(capa.campo_km)
        r.tramos.append(Tramo(capa=capa.clave, id=int(f["id"]), codigo=str(p.get(capa.campo_codigo) or ""),
                              nombre=p.get(capa.campo_nombre) or "", km_declarado=float(km) if km else None,
                              lineas=f["geometry"]["coordinates"], props=p))
    return r


# ----------------------------------------------------------------------------- BD
SQL_CAUDAL = """
select rio, departamento, estacion, lat, lon from caudal_actual where rio is not null order by rio, estacion
"""
SQL_AVISOS = """
select a.ce, a.titulo, count(*) as n, e.nombre, e.departamento, e.lat, e.lon
from aviso_hidrologico a left join estacion e on e.cod = a.ce
group by a.ce, a.titulo, e.nombre, e.departamento, e.lat, e.lon
"""
SQL_VIGILADOS = "select id, rio_ana, estacion_ana from rio_vigilado"
SQL_EXISTENTES = "select rio_ana, capa, km from rio_cauce order by rio_ana"
SQL_HAY_TABLA = "select to_regclass('public.rio_cauce') is not null"
SQL_UPSERT = """
insert into rio_cauce (rio_ana, rio, nombre, departamento, estaciones, estaciones_senamhi, capa, nombre_capa, codigos,
                       tramos, km, km_declarado, dist_estacion_m, distancias, alias, nota, geom, geom_lejos,
                       fuente, fuente_url, licencia, atribucion, fecha_fuente, url_consulta, bytes)
values (%(rio_ana)s, %(rio)s, %(nombre)s, %(departamento)s, %(estaciones)s, %(estaciones_senamhi)s, %(capa)s,
        %(nombre_capa)s, %(codigos)s, %(tramos)s, %(km)s, %(km_declarado)s, %(dist_estacion_m)s, %(distancias)s::jsonb,
        %(alias)s, %(nota)s,
        st_multi(st_setsrid(st_geomfromgeojson(%(geom)s), 4326)),
        st_multi(st_simplifypreservetopology(st_setsrid(st_geomfromgeojson(%(geom)s), 4326), 0.00045)),
        %(fuente)s, %(fuente_url)s, %(licencia)s, %(atribucion)s, %(fecha_fuente)s, %(url_consulta)s, %(bytes)s)
on conflict (rio_ana) do update set
  rio = excluded.rio, nombre = excluded.nombre, departamento = excluded.departamento, estaciones = excluded.estaciones,
  estaciones_senamhi = excluded.estaciones_senamhi, capa = excluded.capa, nombre_capa = excluded.nombre_capa,
  codigos = excluded.codigos, tramos = excluded.tramos, km = excluded.km, km_declarado = excluded.km_declarado,
  dist_estacion_m = excluded.dist_estacion_m, distancias = excluded.distancias, alias = excluded.alias,
  nota = excluded.nota, geom = excluded.geom, geom_lejos = excluded.geom_lejos, fuente = excluded.fuente,
  fuente_url = excluded.fuente_url, licencia = excluded.licencia, atribucion = excluded.atribucion,
  fecha_fuente = excluded.fecha_fuente, url_consulta = excluded.url_consulta, bytes = excluded.bytes, ts_carga = now()
"""
SQL_PODAR = "delete from rio_cauce where not (rio_ana = any(%s))"


def _dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, fila)) for fila in cur.fetchall()]


def leer_bd(conn) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """(caudal_actual, avisos por estación y título, rio_vigilado, filas que ya hay en rio_cauce)."""
    with conn.cursor() as cur:
        cur.execute(SQL_CAUDAL)
        caudal = _dicts(cur)
        cur.execute(SQL_AVISOS)
        avisos = _dicts(cur)
        cur.execute(SQL_VIGILADOS)
        vigilados = _dicts(cur)
        cur.execute(SQL_HAY_TABLA)
        existentes = []
        if cur.fetchone()[0]:
            cur.execute(SQL_EXISTENTES)
            existentes = _dicts(cur)
    return caudal, avisos, vigilados, existentes


def fila(r: Resultado) -> dict:
    """La fila de rio_cauce (geometrías como GeoJSON para st_geomfromgeojson)."""
    o = r.objetivo
    return {
        "rio_ana": o.rio_ana, "rio": o.rio, "nombre": r.nombre,
        "departamento": ", ".join(sorted(o.departamentos)) or "s.d.",
        "estaciones": o.estaciones, "estaciones_senamhi": sorted(set(o.ces)),
        "capa": r.capa.clave, "nombre_capa": r.nombre_capa, "codigos": [t.codigo for t in r.tramos],
        "tramos": len(r.tramos), "km": r.km, "km_declarado": r.km_declarado, "dist_estacion_m": r.dist_min_m,
        "distancias": json.dumps(r.distancias, ensure_ascii=False),
        "alias": r.alias.get("nombre"), "nota": "; ".join(r.avisos) or None,
        "geom": json.dumps({"type": "MultiLineString", "coordinates": r.lineas}),
        "fuente": r.capa.fuente, "fuente_url": r.capa.fuente_url, "licencia": ana_rios.LICENCIA,
        "atribucion": r.capa.atribucion, "fecha_fuente": r.capa.fecha_fuente,
        "url_consulta": r.url_consulta, "bytes": r.bytes,
    }


def aplicar(conn, filas: list[dict], conservar: list[str], podar: bool = False) -> int:
    """Upsert de las filas en la transacción de conn (sin commit). Con podar borra lo que no esté en conservar."""
    with conn.cursor() as cur:
        cur.executemany(SQL_UPSERT, filas)
        borrados = 0
        if podar:
            cur.execute(SQL_PODAR, (conservar,))
            borrados = cur.rowcount
    return borrados


# ----------------------------------------------------------------------------- resumen
def linea_resumen(r: Resultado) -> str:
    o = r.objetivo
    if r.motivo:
        return f"SIN TRAZO  {o.rio_ana:<22} {r.motivo}"
    dist = ", ".join(f"{d['estacion']} {d['m']:.0f} m" for d in sorted(r.distancias, key=lambda d: d["m"])[:3])
    decl = f" (decl. {r.km_declarado})" if r.km_declarado else ""
    estado = "AVISO" if r.avisos else "OK"
    origen = " [copia]" if r.desde_copia else ""
    texto = (f"{estado:<10} {o.rio_ana:<22} {r.capa.clave:<9} '{r.nombre_capa}' {len(r.tramos)} tramos "
             f"{r.km} km{decl} | {dist}{origen}")
    return texto + "".join(f"\n{'':11}- {a}" for a in r.avisos)


def resumen(resultados: list[Resultado], existentes: list[dict]) -> str:
    ok = [r for r in resultados if r.ok and not r.avisos]
    con_aviso = [r for r in resultados if r.ok and r.avisos]
    sin = [r for r in resultados if not r.ok]
    en_bd = {e["rio_ana"] for e in existentes}
    nuevos = [r.objetivo.rio_ana for r in resultados if r.ok and r.objetivo.rio_ana not in en_bd]
    sobran = sorted(en_bd - {r.objetivo.rio_ana for r in resultados})
    partes = [f"{len(resultados)} ríos buscados: {len(ok)} bien, {len(con_aviso)} con aviso, {len(sin)} sin trazo",
              f"km totales: {round(sum(r.km for r in resultados if r.ok), 1)}; "
              f"vértices: {sum(sum(len(l) for l in r.lineas) for r in resultados if r.ok)}"]
    if sin:
        partes.append("sin trazo: " + ", ".join(r.objetivo.rio_ana for r in sin))
    if nuevos:
        partes.append(f"sin fila todavía en rio_cauce ({len(nuevos)}): " + ", ".join(nuevos))
    if sobran:
        partes.append(f"en rio_cauce pero ya sin estación ni aviso ({len(sobran)}; se borran solo con --podar): "
                      + ", ".join(sobran))
    return "\n".join(partes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Carga el trazo de los ríos con estación de ANA o aviso de SENAMHI (rio_cauce).")
    ap.add_argument("--rio", default=None, help="solo ese río (rio_ana o nombre literal de caudal_actual)")
    ap.add_argument("--aplicar", action="store_true", help="escribe en la BD (sin esto es prueba en seco)")
    ap.add_argument("--forzar", action="store_true", help="guarda también los ríos que no pasan la validación de distancia o km")
    ap.add_argument("--recorte", type=float, default=None, metavar="KM", help="recorta el trazo a KM km de las estaciones")
    ap.add_argument("--desde-copia", action="store_true", help="usa las copias de backend/data/cauces/ en vez de GeoSNIRH")
    ap.add_argument("--sin-copia", action="store_true", help="no guarda copias en backend/data/cauces/")
    ap.add_argument("--copias", type=Path, default=COPIAS, metavar="DIR", help="carpeta de las copias")
    ap.add_argument("--podar", action="store_true", help="con --aplicar, borra los ríos que ya no se buscan")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):          # nombres con tilde en la consola de Windows
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.podar and args.rio:
        log.error("--podar no se combina con --rio: borraría todos los demás ríos.")
        return 1

    try:
        with conectar() as conn:
            caudal, avisos, vigilados, existentes = leer_bd(conn)
    except RuntimeError as e:
        log.error("%s Corre el cargador dentro del contenedor worker.", e)
        return 2
    alias = leer_alias()
    objetivos, notas = armar_objetivos(caudal, avisos, vigilados, alias)
    for n in notas:
        log.info("%s", n)
    if args.rio:
        pedido = slug(args.rio)
        objetivos = [o for o in objetivos if o.rio_ana == pedido or o.rio == args.rio]
        if not objetivos:
            log.error("No hay ningún río '%s' en caudal_actual ni en los avisos", args.rio)
            return 1
    log.info("%d ríos por buscar (%d estaciones de ANA, %d de SENAMHI)", len(objetivos),
             sum(len(o.estaciones) for o in objetivos), sum(len(o.ces) for o in objetivos))

    resultados: list[Resultado] = []
    for o in objetivos:
        r = leer_copia(o, alias["rios"], args.copias) if args.desde_copia else None
        if r is not None:
            r = completar(r, r.alias.get("nombre") or o.rio, int(r.alias.get("radio_m") or RADIO_M),
                          args.recorte, args.forzar)
        else:
            try:
                r = emparejar(o, alias["rios"], recorte_km=args.recorte, forzar=args.forzar)
            except (OSError, ValueError) as e:
                r = Resultado(objetivo=o, alias=alias["rios"].get(o.rio_ana, {}), motivo=f"GeoSNIRH falló: {e}")
            if r.ok and not args.sin_copia:
                guardar_copia(r, args.copias)
        resultados.append(r)
        print(linea_resumen(r), flush=True)
    print(resumen(resultados, existentes), flush=True)
    if not args.aplicar:
        log.info("Prueba en seco: no se escribió nada. Usa --aplicar para guardar.")
        return 0

    filas = [fila(r) for r in resultados if r.ok]
    conservar = [o.rio_ana for o in objetivos]
    try:
        with conectar() as conn:   # una sola transacción: commit al salir, rollback si algo falla
            with conn.cursor() as cur:
                cur.execute(SQL_HAY_TABLA)
                if not cur.fetchone()[0]:
                    log.error("Falta la tabla rio_cauce: aplica antes la migración rio_cauce (supabase/migrations/).")
                    return 2
            borrados = aplicar(conn, filas, conservar, podar=args.podar)
    except RuntimeError as e:
        log.error("%s", e)
        return 2
    log.info("Guardado: %d ríos en rio_cauce (%d borrados por --podar); %d quedaron sin trazo y no se tocaron.",
             len(filas), borrados, sum(1 for r in resultados if not r.ok))
    return 0


if __name__ == "__main__":
    sys.exit(main())
