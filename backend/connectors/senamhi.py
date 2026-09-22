"""
Conector SENAMHI — red de estaciones hidrometeorológicas.

Dos productos:
  1. inventario_estaciones(dp)  -> lista de estaciones de un departamento.
  2. datos_horarios(est)        -> serie horaria (precip/temp) de una estación,
                                   de las últimas ~48 h (tiempo real, sin CAPTCHA).

Origen de los datos (ver docs/README-tecnico.md):
  - Inventario:  https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/?dp=<dp>
                 (array JS `PruebaTest` embebido en el HTML)
  - Serie:       https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php
                 (config de Highcharts embebida en el HTML)
"""
from __future__ import annotations

import json
import re
import os
import tempfile
from dataclasses import dataclass, field

import requests
import geopandas as gpd
from bs4 import BeautifulSoup

from . import _http

BASE = "https://www.senamhi.gob.pe/mapas/mapa-estaciones-2"


@dataclass
class Estacion:
    cod: str
    nombre: str
    lat: float
    lon: float
    tipo: str          # "M" meteorológica | "H" hidrológica
    categoria: str     # CO, PLU, EMA, EHA, MAP, HLG, ...
    estado: str        # REAL | DIFERIDO | AUTOMATICA
    cod_old: str = ""

    @property
    def es_automatica(self) -> bool:
        return self.estado == "AUTOMATICA"


@dataclass
class SerieHoraria:
    estacion: str
    codigo: str
    timestamps: list[str] = field(default_factory=list)   # "YYYY/MM/DD - HH"
    precip_mm: list[float | None] = field(default_factory=list)
    temp_c: list[float | None] = field(default_factory=list)

    @property
    def ultimo(self) -> dict | None:
        if not self.timestamps:
            return None
        return {
            "ts": self.timestamps[-1],
            "precip_mm": self.precip_mm[-1] if self.precip_mm else None,
            "temp_c": self.temp_c[-1] if self.temp_c else None,
        }

    def precip_acumulada(self, horas: int = 24) -> float:
        vals = [v for v in self.precip_mm[-horas:] if isinstance(v, (int, float))]
        return round(sum(vals), 2)


def inventario_estaciones(dp: str = "cajamarca") -> list[Estacion]:
    """Estaciones de un departamento (por defecto Cajamarca)."""
    html = _http.get(f"{BASE}/?dp={dp}")
    m = re.search(r"var\s+PruebaTest\s*=\s*(\[.*?\]);", html, re.S)
    if not m:
        raise RuntimeError("No se encontró el array PruebaTest en el HTML de SENAMHI")
    registros = json.loads(m.group(1))
    out: list[Estacion] = []
    for r in registros:
        out.append(Estacion(
            cod=str(r.get("cod", "")),
            nombre=str(r.get("nom", "")).strip(),
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            tipo=str(r.get("ico", "")),
            categoria=str(r.get("cate", "")),
            estado=str(r.get("estado", "")),
            cod_old=str(r.get("cod_old", "")),
        ))
    return out


def _parse_num_array(texto: str) -> list[float | None]:
    vals: list[float | None] = []
    for tok in texto.split(","):
        tok = tok.strip()
        if not tok:
            continue
        vals.append(None if tok == "null" else float(tok))
    return vals


def _serie_por_nombre(html: str, palabra_clave: str) -> list[float | None]:
    m = re.search(
        r"name:\s*'[^']*" + re.escape(palabra_clave) + r"[^']*'.*?data:\s*\[([^\]]*)\]",
        html, re.S,
    )
    return _parse_num_array(m.group(1)) if m else []


def datos_horarios(est: Estacion) -> SerieHoraria:
    """Serie horaria (últimas ~48 h) de una estación. Gratis, sin CAPTCHA."""
    html = _http.get(
        f"{BASE}/map_red_graf.php",
        {
            "cod": est.cod,
            "estado": est.estado,
            "tipo_esta": est.tipo,
            "cate": est.categoria,
            "cod_old": est.cod_old,
        },
    )
    mcat = re.search(r"categories:\s*\[([^\]]+)\]", html)
    cats = re.findall(r"'([^']+)'", mcat.group(1)) if mcat else []
    return SerieHoraria(
        estacion=est.nombre,
        codigo=est.cod,
        timestamps=cats,
        precip_mm=_serie_por_nombre(html, "Precipitaci"),
        temp_c=_serie_por_nombre(html, "Temperatura"),
    )


def estaciones_automaticas(dp: str = "cajamarca") -> list[Estacion]:
    """Solo las estaciones con telemetría horaria (las útiles para alertas)."""
    return [e for e in inventario_estaciones(dp) if e.es_automatica]


@dataclass
class MapaFEN:
    """Mapa de eventos El Niño con geojson."""
    uuid: str
    titulo: str
    variable: str = "FEN"
    periodo: str = ""
    geojson: str = ""


def mapas_fen(map_subjects: dict) -> list[MapaFEN]:
    """
    Busca todos los mapas FEN en GeoNetwork y obtiene sus GeoJSON.

    Args:
        map_subjects: dict con {titulo: [keywords], ...}

    Returns:
        lista de MapaFEN con uuid, titulo y geojson
    """
    import xml.etree.ElementTree as ET

    mapas = []

    for titulo, keywords in map_subjects.items():
        # Construir constraint de búsqueda
        constraint_str = " AND ".join([f"Subject = '{kw}'" for kw in keywords])

        url = "https://idesep.senamhi.gob.pe/geonetwork/srv/eng/csw"
        params = {
            "service": "CSW",
            "version": "2.0.2",
            "request": "GetRecords",
            "resultType": "results",
            "elementSetName": "summary",
            "typeNames": "csw:Record",
            "maxRecords": "10",
            "constraintLanguage": "CQL_TEXT",
            "constraint_language_version": "1.1.0",
            "constraint": constraint_str
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            namespaces = {
                'csw': 'http://www.opengis.net/cat/csw/2.0.2',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }

            identificadores = root.findall('.//dc:identifier', namespaces)

            if not identificadores:
                print(f"⚠ No se encontraron mapas para: {titulo}")
                continue

            for ident_elem in identificadores:
                uuid = ident_elem.text
                if not uuid:
                    continue

                # Obtener GeoJSON del UUID
                try:
                    geojson = _obtener_geojson_por_uuid(uuid)

                    # Extraer período del título (ej: "2023 - 2024" -> "2023-01", "Costero 2017" -> "2017-01")
                    periodo = ""
                    # Busca un año (2-4 dígitos), opcionalmente seguido de guión y otro año
                    match = re.search(r"(\d{2,4})(?:\s*-\s*\d{2,4})?", titulo)
                    if match:
                        ano_str = match.group(1)
                        # Si es año de 2 dígitos (82, 97), asumir siglo XX
                        ano = int(ano_str)
                        if ano < 100:
                            ano += 1900
                        periodo = f"{ano}-01"

                    mapas.append(MapaFEN(
                        uuid=uuid,
                        titulo=titulo,
                        periodo=periodo,
                        geojson=geojson
                    ))
                    print(f"✓ Mapa cargado: {titulo}")
                    break  # Solo el primer resultado por título

                except Exception as e:
                    print(f"✗ Error obteniendo GeoJSON para {uuid}: {e}")
                    continue

        except Exception as e:
            print(f"✗ Error buscando mapas para {titulo}: {e}")
            continue

    return mapas


def _obtener_geojson_por_uuid(uuid: str) -> str:
    """Obtiene GeoJSON de un shapefile alojado en GeoNetwork."""
    url_base = f"https://idesep.senamhi.gob.pe/geonetwork/srv/api/0.1/records/{uuid}"

    respuesta_html = requests.get(url_base, timeout=30)
    respuesta_html.raise_for_status()

    enlace_zip = None
    soup = BeautifulSoup(respuesta_html.text, 'html.parser')

    for a in soup.find_all('a', href=True):
        if a['href'].endswith('.zip') and '/attachments/' in a['href']:
            enlace_zip = a['href']
            break

    if not enlace_zip:
        match = re.search(r'(https?://[^"\']+/attachments/[^"\']+\.zip)', respuesta_html.text)
        if match:
            enlace_zip = match.group(1)

    if not enlace_zip:
        raise ValueError(f"No se encontró archivo .zip para UUID: {uuid}")

    respuesta_zip = requests.get(enlace_zip, timeout=30)
    respuesta_zip.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
        tmp.write(respuesta_zip.content)
        ruta_temporal = tmp.name

    try:
        gdf = gpd.read_file(f"zip://{ruta_temporal}")

        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        geojson_str = gdf.to_json()
        return geojson_str

    finally:
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
