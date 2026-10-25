"""
Zonas que podrían inundarse junto a los ríos del país, estimadas con el relieve (HAND), como se hizo
a mano para el Mashcón (docs/README-tecnico.md 5.6.7 "Método"). Este módulo deja el cálculo
reproducible: lee el trazo de ANA (backend/data/cauces/<rio>.geojson, el mismo que rio_cauce.geom),
baja las teselas públicas del Copernicus DEM GLO-30 (AWS, sin autenticación) y escribe
backend/data/cauces_zonas/<rio>.geojson, que carga backend/mapas/cargar_cauces_zonas.py a la tabla
rio_cauce_zona.

Es una ESTIMACIÓN hecha con el relieve, no un mapa oficial de inundación: no considera muros, puentes,
defensas ribereñas ni drenajes, y el error vertical del modelo (2 a 3 m) es del orden de los umbrales.
Por eso las zonas se rotulan por lo que significan ("Zona que podría inundarse si el río se desborda",
"Zona que también podría inundarse"), nunca en metros hacia el usuario.

Método (por río):
  1. Tramo útil: el trazo de ANA se une (linemerge) y se recorta a TRAMO_KM (60 km) centrados en la
     estación de ANA o en la ciudad principal que cruza (TRAMOS); el corredor es una franja de
     CORREDOR_M (2,5 km) a cada lado. Así el cálculo cabe en memoria con celdas de 30 m.
  2. Relieve: teselas Copernicus GLO-30 (1 arcosegundo, EPSG:4326, PixelIsPoint) leídas con tifffile y
     georreferenciadas con ModelTiepoint/ModelPixelScale (sin GDAL ni rasterio); se remuestrean con
     interpolación bilineal a una malla UTM de CELDA_M (30 m).
  3. Cauce grabado: las celdas que cruza el trazo toman la cota del río (mínimo 3x3, mediana móvil a
     lo largo del tramo y mínimo acumulado aguas abajo, para quitar puentes y árboles del modelo de
     superficie) menos QUEMA_M, para que el agua del modelo llegue al río.
  4. Relleno de depresiones por inundación con prioridad (Barnes 2014) con epsilon, sembrado en el
     cauce y en el borde del corredor; dirección de flujo D8 sobre el relleno; cada celda se sigue hasta
     el río (salto de punteros). HAND = cota original de la celda - cota del río donde drena.
  5. Zonas: HAND <= ~2 m (subtipo bajo_2m, la web la dibuja rayada) y HAND <= ~3 m (bajo_3m, lisa y
     tenue), solo celdas que drenan al río, a menos de DIST_MAX_M (1,5 km) y conectadas en el mapa con
     el cauce; filtro de mayoría 3x3, sin manchas ni huecos menores de MIN_CELDAS; polígonos suavizados
     (cierre y apertura de SUAVIZAR_M) y simplificados a SIMPLIFICAR_M (8 m; la vista los deja a ~6 m), 5 decimales.
  6. Control de calidad: área por umbral, que la zona toque el cauce y que la de 2 m no supere
     MAX_FRACCION_2M (25 %) del corredor (si pasa, el relieve no distingue nada: el río se marca con nota
     y no se carga). Los ríos de selva baja muy plana (DESCARTADOS) no se calculan.

Se corre con un entorno propio (backend/requirements-relieve.txt), fuera del contenedor:
    python -m backend.mapas.zonas_relieve --rio rimac --dem-dir /ruta/teselas          # un río
    python -m backend.mapas.zonas_relieve --todos --dem-dir /ruta/teselas              # los de TRAMOS
    python -m backend.mapas.zonas_relieve --rio otro --centro -7.15,-78.5 --etiqueta "ciudad X"
Opciones:
    --rio NOMBRE      rio_ana (archivo backend/data/cauces/<rio>.geojson); se puede repetir
    --todos           todos los ríos de TRAMOS en orden de prioridad
    --centro LAT,LON  centro del tramo (si no, el de TRAMOS o la primera estación del archivo)
    --etiqueta TEXTO  cómo se llama el centro en el método ("estación Chosica")
    --tramo-km KM     largo del tramo (60 por defecto)
    --dem-dir DIR     carpeta donde se guardan las teselas (~43 MB cada una; fuera del repo)
    --salida DIR      carpeta de salida (backend/data/cauces_zonas por defecto)
    --descartes DIR   dónde dejar el GeoJSON de los ríos que no pasan el control (para mirarlos)
    --visor           escribe además <salida>/_visor_<rio>.html con la zona y el cauce para revisarlos
"""
from __future__ import annotations

import argparse
import heapq
import json
import logging
import math
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

if __package__ in (None, ""):   # permite también: python backend/mapas/zonas_relieve.py
    sys.path.insert(0, __file__.rsplit("backend", 1)[0])

log = logging.getLogger("zonas_relieve")

RAIZ = Path(__file__).resolve().parents[1]
CAUCES = RAIZ / "data" / "cauces"
SALIDA = RAIZ / "data" / "cauces_zonas"
INDICE = "_indice.json"       # resumen por río (hecho o descartado, km, km2, segundos) en la carpeta de salida

CELDA_M = 30.0                # celda de la malla UTM (el GLO-30 tiene 1 arcosegundo, ~30 m)
TRAMO_KM = 60.0               # largo máximo del tramo que se calcula
CORREDOR_M = 2500.0           # a cada lado del cauce
DIST_MAX_M = 1500.0           # una zona nunca se aleja más que esto del cauce
UMBRALES = (("bajo_2m", 2.0, 2), ("bajo_3m", 3.0, 3))   # (subtipo, metros sobre el cauce, n de la clave)
QUEMA_M = 20.0                # cuánto se hunde el cauce para que el flujo del modelo llegue a él
EPSILON_M = 0.001             # pendiente mínima del relleno (para que D8 no tenga planicies)
MEDIANA_CELDAS = 21           # ventana de la mediana a lo largo del cauce (~630 m)
MIN_CELDAS = 12               # manchas o huecos más chicos se quitan (~1 ha)
SUAVIZAR_M = 12.0             # radio del cierre y la apertura de los polígonos (< CELDA_M / 2: no borra franjas de una celda)
SIMPLIFICAR_M = 8.0           # con 6 m los 20 ríos pasaban de 3 MB; sobre celdas de 30 m no se nota (la vista simplifica a ~6 m)
DECIMALES = 5
MAX_FRACCION_2M = 0.25        # si la zona de 2 m cubre más que esto del corredor, el relieve no distingue nada
MAX_DESCARGA = 80_000_000     # bytes por tesela (pesan ~43 MB)

URL_TESELA = "https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif"
FUENTE = ("Estimación SIMPAC: altura sobre el cauce (HAND) con el modelo de elevación Copernicus DEM GLO-30 "
          "(https://registry.opendata.aws/copernicus-dem/) y el trazo del río de ANA - GeoSNIRH")
LICENCIA = "Aviso Copernicus (uso libre citando la atribución); trazo del río: información pública de la ANA"
ATRIBUCION = ("Elaborado con Copernicus WorldDEM-30 © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH "
              "2014-2018, provisto bajo COPERNICUS por la Unión Europea y la ESA; todos los derechos reservados. "
              "Trazo del río: Autoridad Nacional del Agua (ANA) - GeoSNIRH")
FECHA_FUENTE = "2026-10-20"   # cuándo se bajaron las teselas (el GLO-30 público es la edición 2021-2023)
NOTA_ESTIMACION = ("Estimación hecha con el relieve: no considera muros, puentes, defensas ni drenajes y no es un "
                   "mapa oficial. El error vertical del modelo (2 a 3 m) es del orden de los umbrales: se lee como "
                   "'bajo' y 'algo bajo' junto al río, no como metros exactos. En zonas con edificios o árboles se "
                   "queda corta (es un modelo de superficie).")

# Dónde se centra el tramo de cada río (lat, lon) y cómo se llama ese centro en el método. Sin centro,
# se usa la primera estación de ANA que trae el archivo de cauces (o hay que dar --centro). El orden
# es el de prioridad de --todos.
TRAMOS: dict[str, dict] = {
    "rimac": {"centro": (-12.02, -76.93), "etiqueta": "la ciudad de Lima (de Chosica al mar)"},
    "chillon": {"centro": (-11.83, -77.02), "etiqueta": "Lima Norte (de Puente Magdalena al mar)"},
    "piura": {"centro": (-5.19, -80.63), "etiqueta": "la ciudad de Piura"},
    "chira": {"centro": (-4.8801, -81.0216), "etiqueta": "la estación Pte. Simón Rodríguez (Sullana)"},
    "tumbes": {"centro": (-3.65, -80.45), "etiqueta": "la ciudad de Tumbes y la estación El Tigre"},
    "cajamarca": {"centro": (-7.2294, -78.4131), "etiqueta": "la estación Jesús Túnel (Baños del Inca y Jesús)"},
    "jequetepeque": {"centro": (-7.25592, -79.09909), "etiqueta": "la estación Yónan Gore"},
    "santa": {"centro": (-8.80, -78.45), "etiqueta": "el valle bajo del Santa (de Condorcerro al mar)"},
    "ica": {"centro": (-14.00, -75.71), "etiqueta": "la ciudad de Ica y la estación Los Molinos"},
    "chili": {"centro": (-16.42679, -71.67503), "etiqueta": "la estación Puente del Diablo (Arequipa)"},
    "mayo": {"centro": (-6.04, -76.96), "etiqueta": "la ciudad de Moyobamba"},
    "utcubamba": {"centro": (-5.7557, -78.4316), "etiqueta": "la estación Los Naranjos (Bagua Grande)"},
    "huallaga": {"centro": (-9.29601, -76.00207), "etiqueta": "la estación Tingo María"},
    "cumbaza": {"centro": (-6.4667, -76.3833), "etiqueta": "la estación Cumbaza (Tarapoto)"},
    "chancay_lambayeque": {"centro": (-6.625398, -79.305331), "etiqueta": "la estación Racarumi"},
    "la_leche": {"centro": (-6.37353, -79.46673), "etiqueta": "la estación Puchaca"},
    "zana": {"centro": (-6.803592, -79.289322), "etiqueta": "la estación Batan"},
    "chicama": {"centro": (-7.66069, -78.96109), "etiqueta": "la estación Salinar"},
    "tambo": {"centro": (-16.990456, -71.63873), "etiqueta": "la estación La Pascana"},
    "vilcanota": {"centro": (-13.42264, -71.85388), "etiqueta": "la estación Pisac"},
}
# Ríos de selva baja muy plana: la altura sobre el drenaje no distingue nada (la llanura entera queda a
# menos de 3 m del río en el modelo) y la orilla cambia cada año. No se calculan y quedan con nota.
DESCARTADOS: dict[str, str] = {
    "amazonas": "selva baja muy plana: el HAND no distingue la llanura de inundación del resto",
    "ucayali": "selva baja muy plana: el HAND no distingue la llanura de inundación del resto",
    "napo": "selva baja muy plana: el HAND no distingue la llanura de inundación del resto",
    "nanay": "selva baja muy plana: el HAND no distingue la llanura de inundación del resto",
    "itaya": "selva baja muy plana: el HAND no distingue la llanura de inundación del resto",
    "maranon": "la fila es un solo río de 1723 km y sus estaciones de Loreto (Nauta, San Regis, Borja) están en selva baja "
               "muy plana; el tramo alto (Balsas, Corral Quemado) queda pendiente como río aparte",
}


# ----------------------------------------------------------------------------- teselas Copernicus
def nombre_tesela(lat: float, lon: float) -> str:
    """Nombre de la tesela GLO-30 que contiene el punto: la esquina es floor(lat), floor(lon) ('S07_00_W079_00')."""
    la, lo = math.floor(lat), math.floor(lon)
    ns = f"{'N' if la >= 0 else 'S'}{abs(la):02d}_00"
    ew = f"{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00"
    return f"Copernicus_DSM_COG_10_{ns}_{ew}_DEM"


def teselas_para(lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> list[str]:
    nombres = []
    for la in range(math.floor(lat_min), math.floor(lat_max) + 1):
        for lo in range(math.floor(lon_min), math.floor(lon_max) + 1):
            nombres.append(nombre_tesela(la + 0.5, lo + 0.5))
    return nombres


def descargar_tesela(nombre: str, carpeta: Path, descargar=None) -> Path:
    """Baja la tesela a carpeta si no está (archivo parcial: se escribe con .parte y se renombra al final)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{nombre}.tif"
    if ruta.is_file() and ruta.stat().st_size > 0:
        return ruta
    url = URL_TESELA.format(n=nombre)
    log.info("Bajando %s", url)
    if descargar is None:
        with urllib.request.urlopen(url, timeout=120) as resp:
            datos = resp.read(MAX_DESCARGA + 1)
    else:
        datos = descargar(url)
    if len(datos) > MAX_DESCARGA:
        raise ValueError(f"La tesela {nombre} pesa más de {MAX_DESCARGA} bytes")
    parcial = ruta.with_suffix(".parte")
    parcial.write_bytes(datos)
    parcial.replace(ruta)
    return ruta


@dataclass
class Tesela:
    """Una tesela ya leída: cotas (filas de norte a sur) y el centro del píxel (0, 0) en grados."""
    datos: np.ndarray
    lon0: float          # longitud del centro del primer píxel
    lat0: float          # latitud del centro del primer píxel (la más alta)
    paso: float          # grados por píxel (igual en lat y lon)

    @property
    def filas(self) -> int:
        return self.datos.shape[0]

    @property
    def columnas(self) -> int:
        return self.datos.shape[1]


def leer_tesela(ruta: Path) -> Tesela:
    """GeoTIFF con tifffile: la georreferencia sale de ModelTiepoint, ModelPixelScale y GTRasterType (punto o área)."""
    import tifffile

    with tifffile.TiffFile(ruta) as tif:
        pagina = tif.pages[0]
        etiquetas = pagina.tags
        datos = pagina.asarray().astype(np.float32, copy=False)
        tie = etiquetas["ModelTiepointTag"].value
        escala = etiquetas["ModelPixelScaleTag"].value
        claves = etiquetas["GeoKeyDirectoryTag"].value if "GeoKeyDirectoryTag" in etiquetas else ()
    return tesela_desde_etiquetas(datos, tie, escala, claves)


def tesela_desde_etiquetas(datos: np.ndarray, tie, escala, claves=()) -> Tesela:
    """Arma la Tesela con las etiquetas GeoTIFF (separado de la lectura para poder probarlo sin archivos)."""
    i, j, _, x, y, _ = tie[:6]
    paso_x, paso_y = float(escala[0]), float(escala[1])
    if abs(paso_x - paso_y) > 1e-9:
        raise ValueError("La tesela no tiene píxeles cuadrados")
    tipo_pixel = _geokey(claves, 1025) or 1      # 1 = PixelIsArea, 2 = PixelIsPoint
    lon0 = float(x) - float(i) * paso_x
    lat0 = float(y) + float(j) * paso_y
    if tipo_pixel == 1:                           # el tiepoint es la esquina: el centro está medio píxel adentro
        lon0 += paso_x / 2
        lat0 -= paso_y / 2
    crs = _geokey(claves, 2048)
    if crs not in (None, 4326):
        raise ValueError(f"La tesela no está en EPSG:4326 (GeographicTypeGeoKey {crs})")
    return Tesela(datos=datos, lon0=lon0, lat0=lat0, paso=paso_x)


def _geokey(claves, clave: int):
    """Valor corto de una GeoKey del GeoKeyDirectoryTag (solo las que caben en el propio directorio)."""
    if not claves or len(claves) < 4:
        return None
    n = claves[3]
    for k in range(n):
        id_, lugar, cuenta, valor = claves[4 + 4 * k: 8 + 4 * k]
        if id_ == clave and lugar == 0 and cuenta == 1:
            return valor
    return None


def muestrear(teselas: list[Tesela], lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Cota en cada (lat, lon) por interpolación bilineal dentro de la tesela que lo contiene; NaN fuera de todas."""
    from scipy.ndimage import map_coordinates

    salida = np.full(lats.shape, np.nan, dtype=np.float32)
    pendiente = np.ones(lats.shape, dtype=bool)
    for t in teselas:
        filas = (t.lat0 - lats) / t.paso
        cols = (lons - t.lon0) / t.paso
        dentro = pendiente & (filas >= -0.5) & (filas <= t.filas - 0.5) & (cols >= -0.5) & (cols <= t.columnas - 0.5)
        if not dentro.any():
            continue
        valores = map_coordinates(t.datos, [filas[dentro], cols[dentro]], order=1, mode="nearest")
        salida[dentro] = valores
        pendiente &= ~dentro
    return salida


# ----------------------------------------------------------------------------- malla UTM
def epsg_utm(lon: float) -> int:
    """Zona UTM sur para el Perú (17S, 18S o 19S): 32717, 32718, 32719."""
    return 32700 + int(math.floor((lon + 180) / 6) + 1)


@dataclass
class Malla:
    """Malla regular en metros (UTM): esquina superior izquierda (x0, y1), nx columnas, ny filas."""
    epsg: int
    x0: float
    y1: float
    nx: int
    ny: int
    celda: float = CELDA_M

    def centros(self) -> tuple[np.ndarray, np.ndarray]:
        xs = self.x0 + (np.arange(self.nx) + 0.5) * self.celda
        ys = self.y1 - (np.arange(self.ny) + 0.5) * self.celda
        return np.meshgrid(xs, ys)

    def fila_col(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return np.floor((self.y1 - y) / self.celda).astype(int), np.floor((x - self.x0) / self.celda).astype(int)

    def caja(self, fila: int, col: int):
        import shapely
        x = self.x0 + col * self.celda
        y = self.y1 - (fila + 1) * self.celda
        return shapely.box(x, y, x + self.celda, y + self.celda)


def malla_para(limites: tuple[float, float, float, float], epsg: int, celda: float = CELDA_M, margen_m: float = 300.0) -> Malla:
    xmin, ymin, xmax, ymax = limites
    x0 = math.floor((xmin - margen_m) / celda) * celda
    y1 = math.ceil((ymax + margen_m) / celda) * celda
    nx = int(math.ceil((xmax + margen_m - x0) / celda))
    ny = int(math.ceil((y1 - (ymin - margen_m)) / celda))
    return Malla(epsg=epsg, x0=x0, y1=y1, nx=nx, ny=ny, celda=celda)


# ----------------------------------------------------------------------------- cauce
def leer_cauce(rio_ana: str, carpeta: Path = CAUCES) -> dict:
    ruta = carpeta / f"{rio_ana}.geojson"
    if not ruta.is_file():
        raise FileNotFoundError(f"No hay copia del trazo en {ruta} (backend/mapas/cargar_cauces.py la guarda)")
    return json.loads(ruta.read_text(encoding="utf-8"))


def lineas_del_cauce(fc: dict) -> list[list[list[float]]]:
    """Todas las líneas [lon, lat] del FeatureCollection (MultiLineString o LineString)."""
    lineas = []
    for f in fc.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") == "MultiLineString":
            lineas.extend(g["coordinates"])
        elif g.get("type") == "LineString":
            lineas.append(g["coordinates"])
    return [l for l in lineas if len(l) >= 2]


def tramo_util(lineas_m, centro_m: tuple[float, float], largo_m: float):
    """
    (tramo, todo): el tramo del río de largo_m centrado en el punto del cauce más cercano a centro_m y la
    unión de todas las líneas. Se unen los tramos de ANA (linemerge) y se toma la pieza más cercana al
    centro; si el río es más corto, el tramo es toda la pieza.
    """
    import shapely
    from shapely.ops import linemerge, substring

    todo = shapely.MultiLineString(lineas_m)
    unido = linemerge(todo)
    piezas = list(unido.geoms) if unido.geom_type == "MultiLineString" else [unido]
    p = shapely.Point(centro_m)
    pieza = encadenar(piezas, min(piezas, key=lambda g: g.distance(p)))
    d = pieza.project(p)
    ini, fin = max(0.0, d - largo_m / 2), min(pieza.length, d + largo_m / 2)
    if fin - ini < largo_m and pieza.length > largo_m:      # el centro está cerca de un extremo: corre la ventana
        if ini == 0.0:
            fin = largo_m
        else:
            ini = pieza.length - largo_m
    return substring(pieza, ini, fin), todo


TOL_UNION_M = 200.0   # dos piezas del trazo se encadenan si sus extremos quedan a menos de esto (como cargar_cauces)


def encadenar(piezas: list, inicial, tol_m: float = TOL_UNION_M):
    """
    Une a la pieza inicial, por sus dos extremos y de a una, las piezas cuyo extremo queda a menos de
    tol_m (los tramos de ANA, sobre todo los de la Carta Nacional IGN, no siempre se tocan). Si de un
    extremo salen varias (un afluente), se sigue por la más larga. Devuelve una LineString.
    """
    import shapely

    coords = list(inicial.coords)
    sueltas = [g for g in piezas if g is not inicial]
    cambio = True
    while cambio and sueltas:
        cambio = False
        for extremo in (0, -1):
            punta = shapely.Point(coords[extremo])
            candidatas = []
            for g in sueltas:
                c = list(g.coords)
                d0, d1 = punta.distance(shapely.Point(c[0])), punta.distance(shapely.Point(c[-1]))
                if min(d0, d1) <= tol_m:
                    candidatas.append((g.length, g, c if d0 <= d1 else c[::-1]))
            if not candidatas:
                continue
            _, g, c = max(candidatas, key=lambda t: t[0])
            sueltas.remove(g)
            coords = coords + c if extremo == -1 else c[::-1] + coords
            cambio = True
    return shapely.LineString(coords)


def rasterizar_lineas(geom, malla: Malla, paso_m: float | None = None) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """
    Celdas que cruza la geometría (líneas densificadas a paso_m) y el orden en que las cruza (para la
    mediana a lo largo del cauce). Las diagonales D8 bastan para la conectividad del cauce.
    """
    import shapely

    paso = paso_m or malla.celda / 2
    denso = shapely.segmentize(geom, paso)
    partes = list(denso.geoms) if hasattr(denso, "geoms") else [denso]
    mascara = np.zeros((malla.ny, malla.nx), dtype=bool)
    orden: list[tuple[int, int]] = []
    vistos = set()
    for parte in partes:
        xy = np.asarray(parte.coords)
        filas, cols = malla.fila_col(xy[:, 0], xy[:, 1])
        for f, c in zip(filas.tolist(), cols.tolist()):
            if 0 <= f < malla.ny and 0 <= c < malla.nx:
                mascara[f, c] = True
                if (f, c) not in vistos:
                    vistos.add((f, c))
                    orden.append((f, c))
    return mascara, orden


def cota_del_rio(dem: np.ndarray, rio: np.ndarray, orden: list[tuple[int, int]]) -> np.ndarray:
    """
    Cota del agua en las celdas del cauce: mínimo 3x3 (toma la lámina, no la orilla) y, a lo largo del
    tramo principal, mediana móvil y mínimo acumulado aguas abajo (el sentido es el de la cota: de más
    alto a más bajo). Quita puentes, árboles y edificios que el modelo de superficie pone sobre el río.
    """
    from scipy.ndimage import median_filter, minimum_filter

    minimo = minimum_filter(np.nan_to_num(dem, nan=np.inf), size=3, mode="nearest")
    cota = np.where(rio, minimo, np.nan).astype(np.float64)
    if len(orden) >= 3:
        f = np.array([o[0] for o in orden])
        c = np.array([o[1] for o in orden])
        v = cota[f, c]
        ok = np.isfinite(v)
        if ok.sum() >= 3:
            if (~ok).any():                      # celdas sin cota: se interpolan entre las vecinas con cota
                v = v.copy()
                v[~ok] = np.interp(np.flatnonzero(~ok), np.flatnonzero(ok), v[ok])
            ventana = min(MEDIANA_CELDAS, (len(v) // 2) * 2 - 1)
            if ventana >= 3:
                v = median_filter(v, size=ventana, mode="nearest")   # (signal.medfilt rellena con ceros los extremos)
            if v[0] < v[-1]:                     # el orden del trazo iba aguas arriba: se da vuelta
                v = np.minimum.accumulate(v[::-1])[::-1]
            else:
                v = np.minimum.accumulate(v)
            cota[f, c] = v
    return cota


# ----------------------------------------------------------------------------- hidrología de la malla
def rellenar(dem_quemado: np.ndarray, semillas: np.ndarray, valido: np.ndarray, eps: float = EPSILON_M) -> np.ndarray:
    """
    Relleno de depresiones por inundación con prioridad (Barnes, Lehman y Mulla 2014) con epsilon: desde las
    semillas (cauce y borde del corredor) se visita siempre la celda más baja pendiente y cada vecina
    toma max(su cota, cota de quien la alcanza + eps). Fuera de 'valido' no se entra. Devuelve inf donde
    no se llegó.
    """
    ny, nx = dem_quemado.shape
    plano = np.pad(dem_quemado.astype(np.float64), 1, constant_values=np.inf).ravel().tolist()
    cerrado = bytearray(np.pad(~valido, 1, constant_values=True).ravel().tobytes())
    relleno = plano[:]                       # las celdas no visitadas se sobreescriben al visitarlas
    ancho = nx + 2
    vecinos = (-ancho - 1, -ancho, -ancho + 1, -1, 1, ancho - 1, ancho, ancho + 1)
    cola: list[tuple[float, int]] = []
    sem = np.pad(semillas & valido, 1, constant_values=False).ravel()
    for i in np.flatnonzero(sem).tolist():
        cerrado[i] = 1
        heapq.heappush(cola, (plano[i], i))
    while cola:
        z, i = heapq.heappop(cola)
        for d in vecinos:
            j = i + d
            if cerrado[j]:
                continue
            cerrado[j] = 1
            zj = plano[j]
            if zj < z + eps:
                zj = z + eps
            relleno[j] = zj
            heapq.heappush(cola, (zj, j))
    salida = np.asarray(relleno, dtype=np.float64).reshape(ny + 2, nx + 2)[1:-1, 1:-1]
    salida[~valido] = np.inf
    return salida


_D8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


def direccion_d8(relleno: np.ndarray, celda: float = CELDA_M) -> np.ndarray:
    """
    Índice plano de la celda a la que baja cada celda (la de mayor pendiente entre las 8 vecinas), o -1
    si ninguna vecina es más baja (semillas y salidas del corredor).
    """
    ny, nx = relleno.shape
    z = np.pad(relleno, 1, constant_values=np.inf)
    mejor = np.zeros((ny, nx), dtype=np.float64)
    destino = np.full((ny, nx), -1, dtype=np.int64)
    base = np.arange(ny * nx, dtype=np.int64).reshape(ny, nx)
    for df, dc in _D8:
        vecino = z[1 + df: 1 + df + ny, 1 + dc: 1 + dc + nx]
        dist = celda * (math.sqrt(2) if df and dc else 1.0)
        with np.errstate(invalid="ignore"):
            pendiente = (relleno - vecino) / dist
        gana = np.isfinite(pendiente) & (pendiente > mejor)
        mejor = np.where(gana, pendiente, mejor)
        destino = np.where(gana, base + df * nx + dc, destino)
    destino[~np.isfinite(relleno)] = -1
    return destino


def drenaje(destino: np.ndarray, rio: np.ndarray) -> np.ndarray:
    """
    Para cada celda, el índice plano de la celda del cauce a la que llega siguiendo D8 (salto de punteros),
    o -1 si termina fuera del cauce (borde del corredor). Las celdas del cauce apuntan a sí mismas.
    """
    n = destino.size
    punt = destino.ravel().astype(np.int64).copy()
    idx = np.arange(n, dtype=np.int64)
    rio_plano = rio.ravel()
    punt[rio_plano] = idx[rio_plano]
    sumidero = n                                   # centinela: fuera del cauce
    punt = np.where(punt < 0, sumidero, punt)
    punt = np.append(punt, sumidero)
    for _ in range(64):
        nuevo = punt[punt]
        if np.array_equal(nuevo, punt):
            break
        punt = nuevo
    salida = punt[:n]
    salida = np.where(salida == sumidero, -1, salida)
    return salida.reshape(destino.shape)


def hand(dem: np.ndarray, cota_rio: np.ndarray, drena: np.ndarray) -> np.ndarray:
    """Altura sobre el drenaje más cercano: cota original de la celda menos la cota del río donde drena; inf si no drena al río."""
    salida = np.full(dem.shape, np.inf, dtype=np.float64)
    ok = drena >= 0
    cotas = cota_rio.ravel()[drena[ok]]
    salida[ok] = dem[ok] - cotas
    return salida


def zona(hand_m: np.ndarray, dist_m: np.ndarray, rio: np.ndarray, umbral_m: float, valido: np.ndarray,
         dist_max_m: float | None = None, min_celdas: int | None = None) -> np.ndarray:
    """
    Máscara de la zona: HAND <= umbral, a menos de dist_max del cauce, dentro del corredor; filtro de
    mayoría 3x3 (quita celdas sueltas), sin manchas ni huecos menores de min_celdas y solo las manchas
    unidas al cauce.
    """
    from scipy.ndimage import binary_fill_holes, label, uniform_filter

    dist_max_m = DIST_MAX_M if dist_max_m is None else dist_max_m
    min_celdas = MIN_CELDAS if min_celdas is None else min_celdas
    m = valido & (hand_m <= umbral_m) & (dist_m <= dist_max_m)
    m |= rio & valido
    suav = uniform_filter(m.astype(np.float32), size=3, mode="constant") * 9.0
    m = (suav >= 4.5) | (rio & valido)
    m = _sin_manchas(m, min_celdas)
    huecos = binary_fill_holes(m) & ~m
    etiquetas, n = label(huecos, structure=np.ones((3, 3)))
    if n:
        tam = np.bincount(etiquetas.ravel())
        chicos = np.flatnonzero(tam < min_celdas)
        chicos = chicos[chicos > 0]
        m |= np.isin(etiquetas, chicos)
    etiquetas, n = label(m, structure=np.ones((3, 3)))
    if n == 0:
        return m
    tocan = np.unique(etiquetas[rio & m])
    tocan = tocan[tocan > 0]
    return np.isin(etiquetas, tocan)


def _sin_manchas(m: np.ndarray, min_celdas: int) -> np.ndarray:
    from scipy.ndimage import label
    etiquetas, n = label(m, structure=np.ones((3, 3)))
    if n == 0:
        return m
    tam = np.bincount(etiquetas.ravel())
    grandes = np.flatnonzero(tam >= min_celdas)
    grandes = grandes[grandes > 0]
    return np.isin(etiquetas, grandes)


# ----------------------------------------------------------------------------- polígonos
def poligonizar(m: np.ndarray, malla: Malla, suavizar_m: float | None = None, simplificar_m: float | None = None):
    """
    Une las celdas de la máscara en polígonos (en metros): cierre y apertura de suavizar_m para quitar
    los escalones de la malla y simplificación a simplificar_m. Devuelve un MultiPolygon (vacío si no hay celdas).
    """
    import shapely

    suavizar_m = SUAVIZAR_M if suavizar_m is None else suavizar_m
    simplificar_m = SIMPLIFICAR_M if simplificar_m is None else simplificar_m
    filas, cols = np.nonzero(m)
    if len(filas) == 0:
        return shapely.MultiPolygon()
    x = malla.x0 + cols * malla.celda
    y = malla.y1 - (filas + 1) * malla.celda
    cajas = shapely.box(x, y, x + malla.celda, y + malla.celda)
    try:
        union = shapely.coverage_union_all(cajas)
    except Exception:  # noqa: BLE001 - shapely vieja o cobertura inválida: la unión general es más lenta pero igual
        union = shapely.unary_union(cajas)
    if suavizar_m > 0:
        union = union.buffer(suavizar_m, join_style="round").buffer(-2 * suavizar_m, join_style="round").buffer(suavizar_m, join_style="round")
    union = shapely.make_valid(union)
    if simplificar_m > 0:
        union = shapely.simplify(union, simplificar_m, preserve_topology=True)
    return como_multipoligono(union)


def como_multipoligono(g):
    import shapely
    if g.is_empty:
        return shapely.MultiPolygon()
    if g.geom_type == "Polygon":
        return shapely.MultiPolygon([g])
    if g.geom_type == "MultiPolygon":
        return g
    polis = [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon" and not p.is_empty]
    for p in getattr(g, "geoms", []):
        if p.geom_type == "MultiPolygon":
            polis.extend(p.geoms)
    return shapely.MultiPolygon(polis)


def a_wgs84(geom, epsg: int, decimales: int = DECIMALES):
    import shapely
    from pyproj import Transformer

    tr = Transformer.from_crs(epsg, 4326, always_xy=True)

    def f(xy):
        lon, lat = tr.transform(xy[:, 0], xy[:, 1])
        return np.column_stack([np.round(lon, decimales), np.round(lat, decimales)])

    g = shapely.make_valid(shapely.transform(geom, f))
    return como_multipoligono(g)


# ----------------------------------------------------------------------------- cálculo de un río
@dataclass
class ZonaCalculada:
    subtipo: str
    n: int
    umbral_m: float
    area_km2: float
    toca_cauce: bool
    geom_wgs84: object           # shapely MultiPolygon en EPSG:4326


@dataclass
class Resultado:
    rio_ana: str
    centro: tuple[float, float]
    etiqueta: str
    tramo_km: float = 0.0
    corredor_km2: float = 0.0
    teselas: list[str] = field(default_factory=list)
    celdas: tuple[int, int] = (0, 0)
    zonas: list[ZonaCalculada] = field(default_factory=list)
    segundos: float = 0.0
    notas: list[str] = field(default_factory=list)
    descartado: str | None = None

    @property
    def ok(self) -> bool:
        return self.descartado is None

    def area(self, subtipo: str) -> float:
        return next((z.area_km2 for z in self.zonas if z.subtipo == subtipo), 0.0)

    @property
    def fraccion_2m(self) -> float:
        return self.area("bajo_2m") / self.corredor_km2 if self.corredor_km2 else 0.0


def controlar(r: Resultado, max_fraccion: float = MAX_FRACCION_2M) -> Resultado:
    """Control de calidad: zona vacía, zona que no toca el cauce o zona de 2 m demasiado grande descartan el río."""
    if not r.zonas or r.area("bajo_2m") <= 0:
        r.descartado = "el relieve no deja ninguna zona baja junto al cauce (valle encajonado o trazo lejos del río)"
    elif not all(z.toca_cauce for z in r.zonas):
        r.descartado = "alguna zona no toca el cauce"
    elif r.fraccion_2m > max_fraccion:
        r.descartado = (f"la zona de 2 m cubre el {r.fraccion_2m:.0%} del corredor (más del {max_fraccion:.0%}): "
                        "terreno muy plano, el relieve no distingue nada")
    return r


def calcular(rio_ana: str, fc: dict, centro: tuple[float, float], etiqueta: str, dem_dir: Path,
             tramo_km: float = TRAMO_KM, descargar=None) -> Resultado:
    """Todo el método para un río. centro es (lat, lon)."""
    import shapely
    from pyproj import Transformer
    from scipy.ndimage import distance_transform_edt

    t0 = time.perf_counter()
    r = Resultado(rio_ana=rio_ana, centro=centro, etiqueta=etiqueta)
    lineas = lineas_del_cauce(fc)
    if not lineas:
        r.descartado = "el archivo del cauce no trae líneas"
        return r
    epsg = epsg_utm(centro[1])
    a_m = Transformer.from_crs(4326, epsg, always_xy=True)
    lineas_m = [list(zip(*a_m.transform([p[0] for p in l], [p[1] for p in l]))) for l in lineas]
    cx, cy = a_m.transform(centro[1], centro[0])
    tramo, todo = tramo_util(lineas_m, (cx, cy), tramo_km * 1000)
    r.tramo_km = round(tramo.length / 1000, 1)
    corredor = tramo.buffer(CORREDOR_M)
    r.corredor_km2 = round(corredor.area / 1e6, 1)
    cauce_cerca = todo.intersection(corredor.buffer(CELDA_M))
    malla = malla_para(corredor.bounds, epsg)
    r.celdas = (malla.ny, malla.nx)
    log.info("%s: tramo de %.1f km, corredor %.0f km2, malla %d x %d", rio_ana, r.tramo_km, r.corredor_km2, malla.ny, malla.nx)

    # relieve
    xs, ys = malla.centros()
    a_geo = Transformer.from_crs(epsg, 4326, always_xy=True)
    lons, lats = a_geo.transform(xs, ys)
    r.teselas = teselas_para(float(lats.min()), float(lats.max()), float(lons.min()), float(lons.max()))
    teselas = [leer_tesela(descargar_tesela(n, dem_dir, descargar)) for n in r.teselas]
    dem = muestrear(teselas, lats, lons).astype(np.float64)
    del teselas
    sin_dato = ~np.isfinite(dem)
    if sin_dato.any():
        r.notas.append(f"{int(sin_dato.sum())} celdas sin cota en el modelo")
    dem = np.where(sin_dato, np.inf, dem)

    # corredor, cauce y cota del río
    valido = rasterizar_poligono(corredor, malla) & ~sin_dato
    rio, orden = rasterizar_lineas(cauce_cerca, malla)
    _, orden_tramo = rasterizar_lineas(tramo, malla)
    rio &= valido
    if not rio.any():
        r.descartado = "el cauce no cae dentro del corredor"
        return r
    cota_rio = cota_del_rio(dem, rio, [o for o in orden_tramo if rio[o]])
    sin_cota = rio & ~np.isfinite(cota_rio)
    if sin_cota.any():
        cota_rio[sin_cota] = dem[sin_cota]
    dem_quemado = dem.copy()
    dem_quemado[rio] = cota_rio[rio] - QUEMA_M

    # hidrología
    borde = valido & ~_erosionar(valido)
    relleno = rellenar(dem_quemado, rio | borde, valido)
    destino = direccion_d8(relleno, malla.celda)
    drena = drenaje(destino, rio)
    h = hand(dem, cota_rio, drena)
    dist = distance_transform_edt(~rio) * malla.celda

    # zonas
    r.zonas = []
    for subtipo, umbral, n in UMBRALES:
        m = zona(h, dist, rio, umbral, valido)
        poli = poligonizar(m, malla)
        area = poli.area / 1e6
        toca = (not poli.is_empty) and poli.intersects(cauce_cerca.buffer(1.5 * malla.celda))
        r.zonas.append(ZonaCalculada(subtipo=subtipo, n=n, umbral_m=umbral, area_km2=round(area, 3), toca_cauce=toca,
                                     geom_wgs84=a_wgs84(poli, epsg) if not poli.is_empty else shapely.MultiPolygon()))
    r.segundos = round(time.perf_counter() - t0, 1)
    return controlar(r)


def rasterizar_poligono(poligono, malla: Malla) -> np.ndarray:
    """Celdas cuyo centro cae dentro del polígono (shapely vectorizado)."""
    import shapely
    xs, ys = malla.centros()
    puntos = shapely.points(xs.ravel(), ys.ravel())
    return shapely.contains(poligono, puntos).reshape(malla.ny, malla.nx)


def _erosionar(m: np.ndarray) -> np.ndarray:
    from scipy.ndimage import binary_erosion
    return binary_erosion(m, structure=np.ones((3, 3)), border_value=0)


# ----------------------------------------------------------------------------- salida
def metodo(r: Resultado) -> str:
    return (f"HAND sobre Copernicus GLO-30, umbral ~2 m / ~3 m, tramo de {r.tramo_km:g} km alrededor de {r.etiqueta}. "
            f"Trazo de ANA grabado en el relieve (30 m), relleno de depresiones y D8; solo celdas que drenan al río, "
            f"a menos de 1,5 km y unidas al cauce; suavizado.")


def feature(r: Resultado, z: ZonaCalculada) -> dict:
    import shapely
    return {
        "type": "Feature",
        "properties": {
            "clave": f"{r.rio_ana}:relieve:{z.n}",
            "rio_ana": r.rio_ana,
            "subtipo": z.subtipo,
            "area_km2": z.area_km2,
            "metodo": metodo(r),
            "fuente": FUENTE,
            "licencia": LICENCIA,
            "atribucion": ATRIBUCION,
            "fecha_fuente": FECHA_FUENTE,
            "nota": NOTA_ESTIMACION + ("" if not r.notas else " " + "; ".join(r.notas) + "."),
        },
        "geometry": json.loads(shapely.to_geojson(z.geom_wgs84)),
    }


def coleccion(r: Resultado) -> dict:
    return {
        "type": "FeatureCollection",
        "rio_ana": r.rio_ana,
        "centro": {"lat": r.centro[0], "lon": r.centro[1], "etiqueta": r.etiqueta},
        "tramo_km": r.tramo_km, "corredor_km2": r.corredor_km2, "celda_m": CELDA_M,
        "teselas": r.teselas, "segundos": r.segundos,
        "descartado": r.descartado,
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features": [feature(r, z) for z in r.zonas],
    }


def escribir(r: Resultado, carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{r.rio_ana}.geojson"
    ruta.write_text(json.dumps(coleccion(r), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return ruta


def anotar_indice(carpeta: Path, r: Resultado) -> None:
    """Resumen por río en <carpeta>/_indice.json (se actualiza la entrada del río, las demás se conservan)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / INDICE
    indice = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    indice[r.rio_ana] = {
        "estado": "hecho" if r.ok else "descartado", "motivo": r.descartado,
        "centro": {"lat": r.centro[0], "lon": r.centro[1], "etiqueta": r.etiqueta},
        "tramo_km": r.tramo_km, "corredor_km2": r.corredor_km2,
        "km2": {z.subtipo: z.area_km2 for z in r.zonas}, "fraccion_2m": round(r.fraccion_2m, 3),
        "segundos": r.segundos, "teselas": r.teselas, "notas": r.notas, "fecha": date.today().isoformat(),
    }
    ruta.write_text(json.dumps(dict(sorted(indice.items())), ensure_ascii=False, indent=1), encoding="utf-8")


def linea_resumen(r: Resultado) -> str:
    if r.descartado and not r.zonas:
        return f"{r.rio_ana}: DESCARTADO ({r.descartado})"
    areas = ", ".join(f"{z.subtipo} {z.area_km2:.2f} km2" for z in r.zonas)
    estado = "hecho" if r.ok else f"DESCARTADO ({r.descartado})"
    return (f"{r.rio_ana}: {estado}; tramo {r.tramo_km:g} km, corredor {r.corredor_km2:g} km2, {areas}, "
            f"2 m = {r.fraccion_2m:.0%} del corredor, {r.segundos:g} s, teselas {len(r.teselas)}")


def visor_html(r: Resultado, fc_cauce: dict, ruta: Path) -> Path:
    """Página suelta con Leaflet para mirar la zona y el cauce (misma idea que visor_geojson.html, sin subir archivos)."""
    zonas = json.dumps(coleccion(r), ensure_ascii=False)
    cauce = json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": {"type": "MultiLineString", "coordinates": lineas_del_cauce(fc_cauce)}}]})
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>Zonas {r.rio_ana}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>html,body,#map{{height:100%;margin:0}} .nota{{position:absolute;top:8px;left:50px;z-index:1000;background:#fff;padding:6px 10px;font:13px system-ui}}</style>
</head><body><div class="nota">{linea_resumen(r)}</div><div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map = L.map('map');
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{attribution: '&copy; OpenStreetMap'}}).addTo(map);
const zonas = {zonas};
const cauce = {cauce};
const capa = L.geoJSON(zonas, {{style: f => f.properties.subtipo === 'bajo_2m'
  ? {{color: '#b91c1c', weight: 1, fillColor: '#ef4444', fillOpacity: 0.45}}
  : {{color: '#1d4ed8', weight: 1, fillColor: '#60a5fa', fillOpacity: 0.3}}}}).addTo(map);
L.geoJSON(cauce, {{style: {{color: '#0f172a', weight: 2}}}}).addTo(map);
function encuadrar() {{ map.invalidateSize(); if (capa.getLayers().length) map.fitBounds(capa.getBounds()); else map.setView([{r.centro[0]}, {r.centro[1]}], 11); }}
encuadrar(); setTimeout(encuadrar, 500);
</script></body></html>"""
    ruta.write_text(html, encoding="utf-8")
    return ruta


# ----------------------------------------------------------------------------- main
def centro_por_defecto(rio_ana: str, fc: dict) -> tuple[tuple[float, float] | None, str]:
    cfg = TRAMOS.get(rio_ana)
    if cfg and cfg.get("centro"):
        return tuple(cfg["centro"]), cfg.get("etiqueta") or "la estación de ANA"
    return None, "la estación de ANA"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Zonas que podrían inundarse junto a los ríos del país, estimadas con el relieve (HAND).")
    ap.add_argument("--rio", action="append", default=[], help="rio_ana (archivo backend/data/cauces/<rio>.geojson); se puede repetir")
    ap.add_argument("--todos", action="store_true", help="todos los ríos de TRAMOS, en orden de prioridad")
    ap.add_argument("--centro", default=None, metavar="LAT,LON", help="centro del tramo (solo con un --rio)")
    ap.add_argument("--etiqueta", default=None, help="cómo se llama el centro en el método")
    ap.add_argument("--tramo-km", type=float, default=TRAMO_KM, metavar="KM")
    ap.add_argument("--dem-dir", type=Path, required=True, metavar="DIR", help="carpeta de las teselas (fuera del repo)")
    ap.add_argument("--cauces", type=Path, default=CAUCES, metavar="DIR")
    ap.add_argument("--salida", type=Path, default=SALIDA, metavar="DIR")
    ap.add_argument("--descartes", type=Path, default=None, metavar="DIR", help="dónde dejar los GeoJSON descartados")
    ap.add_argument("--visor", action="store_true", help="escribe <salida>/_visor_<rio>.html para revisar")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rios = list(args.rio) + (list(TRAMOS) if args.todos else [])
    if not rios:
        ap.error("di --rio NOMBRE o --todos")
    if args.centro and len(rios) != 1:
        ap.error("--centro es para un solo río")

    salida_total = 0
    for rio_ana in rios:
        if rio_ana in DESCARTADOS and not args.centro:
            r = Resultado(rio_ana=rio_ana, centro=(0.0, 0.0), etiqueta="", descartado=DESCARTADOS[rio_ana])
            anotar_indice(args.salida, r)
            print(linea_resumen(r), flush=True)
            continue
        try:
            fc = leer_cauce(rio_ana, args.cauces)
        except FileNotFoundError as e:
            log.error("%s", e)
            salida_total = 1
            continue
        centro, etiqueta = centro_por_defecto(rio_ana, fc)
        if args.centro:
            lat, lon = (float(v) for v in args.centro.split(","))
            centro, etiqueta = (lat, lon), args.etiqueta or etiqueta
        elif args.etiqueta:
            etiqueta = args.etiqueta
        if centro is None:
            log.error("%s: no está en TRAMOS; da --centro LAT,LON (la estación de ANA o la ciudad que cruza)", rio_ana)
            salida_total = 1
            continue
        try:
            r = calcular(rio_ana, fc, centro, etiqueta, args.dem_dir, args.tramo_km)
        except (OSError, ValueError) as e:
            log.error("%s: no se pudo calcular: %s", rio_ana, e)
            salida_total = 1
            continue
        print(linea_resumen(r), flush=True)
        anotar_indice(args.salida, r)
        if r.ok:
            ruta = escribir(r, args.salida)
        else:
            ruta = escribir(r, args.descartes) if args.descartes else None
            viejo = args.salida / f"{rio_ana}.geojson"
            if viejo.is_file():
                log.warning("%s: queda el archivo anterior %s; bórralo a mano si ya no vale", rio_ana, viejo)
        if ruta:
            log.info("%s: %s (%d KB)", rio_ana, ruta, ruta.stat().st_size // 1024)
        if args.visor:
            visor_html(r, fc, (args.salida if r.ok else (args.descartes or args.salida)) / f"_visor_{rio_ana}.html")
    return salida_total


if __name__ == "__main__":
    sys.exit(main())
