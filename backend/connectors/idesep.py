"""
Conector IDESEP (SENAMHI) — catálogo GeoNetwork de mapas en shapefile.

IDESEP es la infraestructura de datos espaciales de SENAMHI. Publica, entre
otros, los mapas de anomalías de precipitación de los eventos El Niño históricos.

Operaciones:
  1. listar_registros()        -> catálogo (uuid + título) vía CSW GetRecords.
  2. buscar_uuid(titulo)       -> uuid de un registro por título (comparación
                                  normalizada: sin distinguir mayúsculas, tipo de
                                  guion ni espacios repetidos).
  3. enlaces_shapefile(uuid)   -> URLs de TODOS los .zip adjuntos a un registro (los
                                  mapas FEN traen uno por trimestre: _DEF, _EFM, _FMA).
  4. capas_de_registro(uuid)   -> [(trimestre, enlace, GeoJSON)] de cada .zip y de cada
                                  capa que traiga (los de IDESEP traen una sola por .zip).
  5. geojson_de_registro(uuid) -> GeoJSON (texto, EPSG:4326) del primer shapefile adjunto
                                  (compatibilidad; el cargador FEN usa capas_de_registro).

El HTTP usa solo la librería estándar (vía _http). La conversión shapefile ->
GeoJSON necesita geopandas, que se importa dentro de las funciones que lo usan:
importar este módulo no exige dependencias extra. Además NO se importa desde
connectors/__init__.py, para que el resto de conectores siga sin dependencias.

Origen de los datos:
  - Catálogo:  https://idesep.senamhi.gob.pe/geonetwork/srv/eng/csw
  - Registro:  https://idesep.senamhi.gob.pe/geonetwork/srv/api/0.1/records/<uuid>
               (página con los enlaces a los .zip de shapefile en /attachments/)
"""
from __future__ import annotations

import html
import logging
import os
import re
import tempfile
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import _http

log = logging.getLogger(__name__)

BASE = "https://idesep.senamhi.gob.pe/geonetwork"
CSW = f"{BASE}/srv/eng/csw"
_HOST = urllib.parse.urlparse(BASE).netloc
_CSW_NS = "http://www.opengis.net/cat/csw/2.0.2"
_NS = {"csw": _CSW_NS, "dc": "http://purl.org/dc/elements/1.1/"}

MAX_ZIP_BYTES = 80 * 1024 * 1024   # tope de descarga por shapefile

# Trimestres como los nombra SENAMHI (inicial de cada mes; diciembre = D). El orden sirve
# para ordenar las capas de un evento (el verano primero) y para calcular los meses legibles.
TRIMESTRES = ["DEF", "EFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDE"]
_RE_TRIMESTRE = re.compile(r"(?:^|[_\-. ])(" + "|".join(TRIMESTRES) + r")(?=$|[_\-. ])", re.I)


@dataclass
class Registro:
    uuid: str
    titulo: str


def listar_registros(por_pagina: int = 100, max_paginas: int = 50) -> list[Registro]:
    """Catálogo completo (uuid + título) del GeoNetwork de IDESEP, paginado."""
    out: list[Registro] = []
    inicio = 1
    for _ in range(max_paginas):
        xml = _http.get(CSW, {
            "service": "CSW",
            "version": "2.0.2",
            "request": "GetRecords",
            "resultType": "results",
            "elementSetName": "summary",
            "typeNames": "csw:Record",
            "maxRecords": str(por_pagina),
            "startPosition": str(inicio),
        })
        root = ET.fromstring(xml)
        res = root.find(f"{{{_CSW_NS}}}SearchResults")
        if res is None:   # p. ej. un ows:ExceptionReport: no es "fin del catálogo"
            raise RuntimeError(f"El CSW de IDESEP no devolvió resultados: {xml[:200]}")
        for rec in res.iter(f"{{{_CSW_NS}}}SummaryRecord"):
            uuid = (rec.findtext("dc:identifier", default="", namespaces=_NS) or "").strip()
            titulo = (rec.findtext("dc:title", default="", namespaces=_NS) or "").strip()
            if uuid:
                out.append(Registro(uuid=uuid, titulo=titulo))
        siguiente = int(res.get("nextRecord", "0"))
        if siguiente <= inicio:   # 0 = no hay más páginas
            break
        inicio = siguiente
    return out


def _normalizar(titulo: str) -> str:
    # Compara títulos sin depender del tipo de guion ni de espacios repetidos.
    t = unicodedata.normalize("NFC", titulo).replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", t).strip().casefold()


def buscar_uuid(titulo: str, registros: list[Registro] | None = None) -> str | None:
    """uuid del registro con ese título (comparación normalizada); None si no existe."""
    registros = registros if registros is not None else listar_registros()
    objetivo = _normalizar(titulo)
    hallados = [r.uuid for r in registros if _normalizar(r.titulo) == objetivo]
    if len(hallados) > 1:
        log.warning("Varios registros con el título %r; se usa el primero (%s)", titulo, hallados[0])
    return hallados[0] if hallados else None


def _es_enlace_valido(url: str) -> bool:
    # Solo se descargan adjuntos del propio IDESEP por HTTPS (nada de otros hosts,
    # http:// ni file://).
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and p.netloc == _HOST and "/attachments/" in p.path


def enlaces_shapefile(uuid: str) -> list[str]:
    """
    URLs de todos los .zip de shapefile adjuntos a un registro, sin repetir y en el orden
    de la página. Los mapas FEN traen uno por trimestre (p. ej. ..._DEF.zip, ..._EFM.zip,
    ..._FMA.zip); hasta el 24-10-2026 el cargador tomaba solo el primero.
    """
    url = f"{BASE}/srv/api/0.1/records/{uuid}"
    pagina = _http.get(url)
    candidatos = [
        # 1) Enlaces <a href="...zip"> (absolutos o relativos).
        *(urllib.parse.urljoin(url, html.unescape(h))
          for h in re.findall(r"""href=["']([^"']+?\.zip)["']""", pagina, re.I)),
        # 2) URLs absolutas sueltas (scripts o metadatos embebidos).
        *(html.unescape(u)
          for u in re.findall(r"""(https?://[^"'\s<>]+/attachments/[^"'\s<>]+\.zip)""", pagina, re.I)),
    ]
    enlaces: list[str] = []
    for enlace in candidatos:
        if _es_enlace_valido(enlace) and enlace not in enlaces:
            enlaces.append(enlace)
    if not enlaces:
        raise ValueError(f"No se encontró el .zip del shapefile en IDESEP para el registro {uuid}")
    return enlaces


def enlace_shapefile(uuid: str) -> str:
    """URL del primer .zip del shapefile adjunto a un registro (compatibilidad)."""
    return enlaces_shapefile(uuid)[0]


def trimestre_de_nombre(nombre: str) -> str | None:
    """
    Trimestre (DEF, EFM, FMA, ...) que nombra un archivo, una URL o una capa de IDESEP; None
    si no lo dice. "Anom_Pp_Ninio_97_98_DEF.zip" -> "DEF"; "Precipitacion_EFM_Ninio_2023" -> "EFM".
    """
    base = urllib.parse.urlparse(nombre).path.rsplit("/", 1)[-1]
    base = re.sub(r"\.(zip|shp)$", "", base, flags=re.I)
    m = _RE_TRIMESTRE.search(base)
    return m.group(1).upper() if m else None


def _geopandas():
    try:
        import geopandas as gpd
    except ImportError as e:
        raise RuntimeError(
            "Falta geopandas (solo lo usa el cargador de mapas). Corre el cargador "
            "dentro del contenedor worker o instala backend/requirements-mapas.txt."
        ) from e
    return gpd


def _a_geojson(gdf, simplificar: float | None, decimales: int | None) -> str:
    # GeoJSON exige WGS84; si el shapefile viene en otra proyección se reproyecta.
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    if simplificar:
        gdf["geometry"] = gdf.geometry.simplify(simplificar, preserve_topology=True)
    if decimales is not None:
        import shapely  # viene con geopandas (>=1.0 exige shapely 2)
        gdf["geometry"] = shapely.set_precision(gdf.geometry.values, 10 ** -decimales)
    if simplificar or decimales is not None:
        vacias = gdf.geometry.isna() | gdf.geometry.is_empty
        if vacias.any():
            log.warning("Se descartan %d geometrías vacías tras simplificar", int(vacias.sum()))
            gdf = gdf[~vacias]
    return gdf.to_json()


def _nombres_de_capas(ruta: str) -> list[str]:
    # geopandas >= 1 lee con pyogrio; si no está (o el zip es raro) se lee la capa por defecto.
    try:
        import pyogrio
        return [str(c[0]) for c in pyogrio.list_layers(f"zip://{ruta}")]
    except Exception:
        return []


def capas_del_zip(enlace: str, simplificar: float | None = None, decimales: int | None = None) -> list[tuple[str | None, str]]:
    """
    [(trimestre, GeoJSON)] de cada capa del .zip de un enlace (los de IDESEP traen una sola).
    El trimestre sale del nombre de la capa o, si no lo dice, del nombre del .zip.
    """
    gpd = _geopandas()
    datos = _http.con_reintentos(_http.get_bytes, enlace, MAX_ZIP_BYTES)
    fd, ruta = tempfile.mkstemp(suffix=".zip")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
        out = []
        for nombre in _nombres_de_capas(ruta) or [None]:
            gdf = gpd.read_file(f"zip://{ruta}", layer=nombre) if nombre else gpd.read_file(f"zip://{ruta}")
            trimestre = trimestre_de_nombre(nombre or "") or trimestre_de_nombre(enlace)
            out.append((trimestre, _a_geojson(gdf, simplificar, decimales)))
        return out
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def capas_de_registro(uuid: str, simplificar: float | None = None, decimales: int | None = None) -> list[tuple[str | None, str, str]]:
    """
    Todas las capas de un registro: [(trimestre, enlace del .zip, GeoJSON)], una por cada
    .zip adjunto y por cada capa que traiga, ordenadas por trimestre (DEF, EFM, FMA, ...).
    trimestre es None si ningún nombre lo dice.

    simplificar: tolerancia en grados para aligerar geometrías (p. ej. 0.005 ~ 550 m).
    decimales:   redondea las coordenadas a esa cantidad de decimales.
    Las geometrías que quedan vacías al simplificar o redondear se descartan.
    """
    out: list[tuple[str | None, str, str]] = []
    for enlace in _http.con_reintentos(enlaces_shapefile, uuid):
        for trimestre, geojson in capas_del_zip(enlace, simplificar, decimales):
            out.append((trimestre, enlace, geojson))
    orden = {t: i for i, t in enumerate(TRIMESTRES)}
    out.sort(key=lambda c: orden.get(c[0], len(orden)))
    return out


def geojson_de_registro(uuid: str, simplificar: float | None = None, decimales: int | None = None) -> str:
    """GeoJSON (texto, EPSG:4326) del primer shapefile de un registro (compatibilidad)."""
    enlace = _http.con_reintentos(enlace_shapefile, uuid)
    return capas_del_zip(enlace, simplificar, decimales)[0][1]
