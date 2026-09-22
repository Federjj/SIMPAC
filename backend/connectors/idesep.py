"""
Conector IDESEP (SENAMHI) — catálogo GeoNetwork de mapas en shapefile.

IDESEP es la infraestructura de datos espaciales de SENAMHI. Publica, entre
otros, los mapas de anomalías de precipitación de los eventos El Niño históricos.

Tres operaciones:
  1. listar_registros()        -> catálogo (uuid + título) vía CSW GetRecords.
  2. buscar_uuid(titulo)       -> uuid de un registro por título (comparación
                                  normalizada: sin distinguir mayúsculas, tipo de
                                  guion ni espacios repetidos).
  3. geojson_de_registro(uuid) -> GeoJSON (texto, EPSG:4326) del shapefile adjunto.

El HTTP usa solo la librería estándar (vía _http). La conversión shapefile ->
GeoJSON necesita geopandas, que se importa dentro de geojson_de_registro(): importar
este módulo no exige dependencias extra. Además NO se importa desde
connectors/__init__.py, para que el resto de conectores siga sin dependencias.

Origen de los datos:
  - Catálogo:  https://idesep.senamhi.gob.pe/geonetwork/srv/eng/csw
  - Registro:  https://idesep.senamhi.gob.pe/geonetwork/srv/api/0.1/records/<uuid>
               (página con el enlace al .zip del shapefile en /attachments/)
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


def enlace_shapefile(uuid: str) -> str:
    """URL del .zip del shapefile adjunto a un registro."""
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
    for enlace in candidatos:
        if _es_enlace_valido(enlace):
            return enlace
    raise ValueError(f"No se encontró el .zip del shapefile en IDESEP para el registro {uuid}")


def geojson_de_registro(uuid: str, simplificar: float | None = None, decimales: int | None = None) -> str:
    """
    GeoJSON (texto, EPSG:4326) del shapefile de un registro.

    simplificar: tolerancia en grados para aligerar geometrías (p. ej. 0.005 ~ 550 m).
    decimales:   redondea las coordenadas a esa cantidad de decimales.
    Las geometrías que quedan vacías al simplificar o redondear se descartan.
    """
    try:
        import geopandas as gpd
    except ImportError as e:
        raise RuntimeError(
            "Falta geopandas (solo lo usa el cargador de mapas). Corre el cargador "
            "dentro del contenedor worker o instala backend/requirements-mapas.txt."
        ) from e

    enlace = _http.con_reintentos(enlace_shapefile, uuid)
    datos = _http.con_reintentos(_http.get_bytes, enlace, MAX_ZIP_BYTES)
    fd, ruta = tempfile.mkstemp(suffix=".zip")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
        gdf = gpd.read_file(f"zip://{ruta}")
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
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)
