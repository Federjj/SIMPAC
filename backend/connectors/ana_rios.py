"""
ANA - GeoSNIRH: el trazo (cauce) de los ríos del Perú, dos capas ArcGIS REST de solo lectura.

  RJ056   Red hidrográfica oficial (R.J. N.º 056-2018-ANA): 1224 cursos de agua con código
          Pfafstetter, UNA línea central por tramo (el Huallaga son 10 tramos; el Jequetepeque, 4).
          Público/Rios/MapServer/37 'RiosQuebradas'. maxRecordCount 5000. Elaborada el 30-01-2018.
  IGN     Ríos y quebradas de la Carta Nacional 1:100 000 del IGN publicada por la ANA: 34 061
          cursos con nombre, un registro por río (sin partir en tramos). En ríos anchos de selva
          dibuja las dos orillas (el doble de km): para ríos grandes se prefiere RJ056.
          ONRH/Rios_Quebradas_Carta_Nacional_IGN/FeatureServer/0. maxRecordCount 2000.

Las dos aceptan f=geojson, outSR=4326, geometryPrecision y maxAllowableOffset (simplifican en el
servidor), paginan con resultOffset (exceededTransferLimit) y filtran por punto + distancia.
Verificado el 14-10-2026 (HTTP 200 en 0,2-4 s). No publican licencia: se tratan como dato público
del Estado con atribución obligatoria, igual que las capas 127 y 107 (docs/README-tecnico.md 5.2).

Trampa del nombre: el servidor compara CON tilde ('Río Rímac') y la BD de ANA la trae a veces sí y
a veces no ('Rio Mashcon'). Por eso el LIKE lleva un comodín por letra acentuable ([AEIOUN] -> '_':
'rimac' -> '%R_M_C') y el nombre se confirma en el cliente con nombre_normalizado() (sin tildes).

Solo librería estándar; no importa backend.config (convención de los conectores).
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from backend.connectors._http import con_reintentos, get_bytes

_BASE = "https://geosnirh.ana.gob.pe/server/rest/services/"
MAX_BYTES = 15_000_000       # un río completo pesa 2-11 MB sin simplificar; con offset, mucho menos
PAUSA_S = 0.4                # entre pedidos: es un ArcGIS Server del Estado sin SLA
OFFSET_CERCA = 0.00005       # ~6 m: lo que se guarda en la BD (geom)
PRECISION = 5                # decimales (~1 m)


@dataclass(frozen=True)
class Capa:
    clave: str               # rio_cauce.capa
    url: str                 # .../query
    campo_nombre: str
    campo_codigo: str
    campo_km: str
    campos: tuple[str, ...]  # outFields
    max_registros: int
    fuente: str
    fuente_url: str
    atribucion: str
    fecha_fuente: str


RJ056 = Capa(
    clave="ana_rj056",
    url=_BASE + "P%C3%BAblico/Rios/MapServer/37/query",
    campo_nombre="NOMBRE_CA", campo_codigo="CODIGO_CA", campo_km="LONG_KM",
    campos=("OBJECTID_1", "CODIGO_CA", "NOMBRE_CA", "CATEGORIA", "TIPO_CA", "LONG_KM",
            "NOMBRE_UH", "CODIGO_UH", "NOMBRE_RH"),
    max_registros=5000,
    fuente="ANA - GeoSNIRH, red hidrográfica R.J. N.º 056-2018-ANA (capa RiosQuebradas)",
    fuente_url="https://geosnirh.ana.gob.pe/server/rest/services/P%C3%BAblico/Rios/MapServer/37",
    atribucion="Autoridad Nacional del Agua (ANA) - GeoSNIRH. Red hidrográfica R.J. N.º 056-2018-ANA (DCERH, 2018)",
    fecha_fuente="2018-01-30",
)
IGN = Capa(
    clave="ana_ign",
    url=_BASE + "ONRH/Rios_Quebradas_Carta_Nacional_IGN/FeatureServer/0/query",
    campo_nombre="NOMBRE_COMPLETO", campo_codigo="IDE_CUERPO_AGUA", campo_km="NUM_LONGITUD",
    campos=("OBJECTID", "IDE_CUERPO_AGUA", "NOMBRE_COMPLETO", "TIPO_CUERPO_AGUA", "NOM_CUENCA",
            "COD_CUENCA", "NUM_LONGITUD", "jerarquia"),
    max_registros=2000,
    fuente="ANA - GeoSNIRH, ríos y quebradas de la Carta Nacional 1:100 000 del IGN",
    fuente_url="https://geosnirh.ana.gob.pe/server/rest/services/ONRH/Rios_Quebradas_Carta_Nacional_IGN/FeatureServer/0",
    atribucion="Carta Nacional 1:100 000 del Instituto Geográfico Nacional (IGN), publicada por la ANA en GeoSNIRH",
    fecha_fuente="2026-04",
)
CAPAS = {c.clave: c for c in (RJ056, IGN)}
LICENCIA = ("Información pública del Estado peruano publicada por la ANA (GeoSNIRH) sin texto de licencia; "
            "se cita la fuente y no se presenta como propia")

_PREFIJOS = re.compile(r"^(rio|quebrada|qda\.?|q\.)\s+")


def nombre_normalizado(nombre: str | None) -> str:
    """'Río Jequetepeque' -> 'jequetepeque'; 'Quebrada Ingenio' -> 'ingenio'; 'Mashcon' -> 'mashcon'."""
    if not nombre:
        return ""
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\s+", " ", s).strip()
    return _PREFIJOS.sub("", s)


def patron_like(nombre: str) -> str:
    """
    Comodín para el LIKE del servidor: cada letra acentuable pasa a '_' (una letra cualquiera),
    porque ANA a veces escribe la tilde y a veces no. 'Rímac' -> 'R_M_C'; 'Marañón' -> 'M_R___N'.
    Va anclado al final ('% R_M_C') para no traer 'Río Santa Rosa' por 'Santa'; el nombre se
    confirma después en el cliente (nombre_normalizado), el LIKE solo prefiltra.
    """
    s = nombre_normalizado(nombre).upper().replace("'", "''")
    return "% " + "".join("_" if ch in "AEIOUN" else ch for ch in s)


def where_nombre(capa: Capa, nombre: str) -> str:
    return f"UPPER({capa.campo_nombre}) LIKE '{patron_like(nombre)}'"


def url_consulta(capa: Capa, where: str, *, punto: tuple[float, float] | None = None, radio_m: int = 2000,
                 offset: float | None = OFFSET_CERCA, result_offset: int = 0, geometria: bool = True) -> str:
    """URL GET de la consulta (sirve también para citarla en la BD). punto = (lat, lon)."""
    params: dict[str, Any] = {
        "where": where, "outFields": ",".join(capa.campos), "f": "geojson", "outSR": 4326,
        "returnGeometry": "true" if geometria else "false", "geometryPrecision": PRECISION,
        "orderByFields": capa.campo_codigo, "resultOffset": result_offset,
        "resultRecordCount": capa.max_registros,
    }
    if offset:
        params["maxAllowableOffset"] = offset
    if punto is not None:
        lat, lon = punto
        params.update({"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                       "distance": radio_m, "units": "esriSRUnit_Meter", "spatialRel": "esriSpatialRelIntersects"})
    return capa.url + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


@dataclass
class Tramo:
    capa: str
    id: int
    codigo: str
    nombre: str                       # literal de la capa ('Río Jequetepeque')
    km_declarado: float | None
    lineas: list[list[list[float]]]   # [[ [lon, lat], ... ], ...] (MultiLineString)
    props: dict = field(default_factory=dict)

    @property
    def vertices(self) -> int:
        return sum(len(l) for l in self.lineas)


def parsear(texto: bytes | str, capa: Capa) -> tuple[list[Tramo], bool]:
    """
    (tramos, exceededTransferLimit) de una respuesta f=geojson. ArcGIS devuelve HTTP 200 con
    {"error": {...}} cuando la consulta está mal: se lanza ValueError con su mensaje.
    """
    datos = json.loads(texto.decode("utf-8") if isinstance(texto, bytes) else texto)
    if "error" in datos:
        e = datos["error"]
        raise ValueError(f"GeoSNIRH respondió error {e.get('code')}: {e.get('message')} {e.get('details') or ''}".strip())
    if datos.get("type") != "FeatureCollection":
        raise ValueError("GeoSNIRH no devolvió un FeatureCollection")
    tramos = []
    for f in datos.get("features", []):
        p = f.get("properties") or {}
        g = f.get("geometry")
        if not g:
            continue
        if g["type"] == "LineString":
            lineas = [g["coordinates"]]
        elif g["type"] == "MultiLineString":
            lineas = list(g["coordinates"])
        else:
            raise ValueError(f"geometría {g['type']} inesperada (se esperaba una línea)")
        lineas = [[[float(x), float(y)] for x, y, *_ in l] for l in lineas if len(l) >= 2]
        if not lineas:
            continue
        km = p.get(capa.campo_km)
        tramos.append(Tramo(capa=capa.clave, id=int(f.get("id") or p.get(capa.campos[0]) or 0),
                            codigo=str(p.get(capa.campo_codigo) or ""), nombre=(p.get(capa.campo_nombre) or "").strip(),
                            km_declarado=float(km) if km is not None else None, lineas=lineas, props=p))
    excedido = bool(datos.get("exceededTransferLimit") or (datos.get("properties") or {}).get("exceededTransferLimit"))
    return tramos, excedido


def _bajar(url: str) -> bytes:
    return con_reintentos(get_bytes, url, MAX_BYTES)


def consultar(capa: Capa, where: str, *, punto: tuple[float, float] | None = None, radio_m: int = 2000,
              offset: float | None = OFFSET_CERCA, descargar=_bajar) -> tuple[list[Tramo], str, int]:
    """
    Todos los tramos que cumplen el where (y, si hay punto, que pasan a radio_m del punto), paginando
    si el servidor corta. (tramos, url de la primera página, bytes totales). descargar(url) -> bytes
    se reemplaza en las pruebas.
    """
    tramos: list[Tramo] = []
    primera, total, desde = "", 0, 0
    while True:
        url = url_consulta(capa, where, punto=punto, radio_m=radio_m, offset=offset, result_offset=desde)
        primera = primera or url
        crudo = descargar(url)
        total += len(crudo)
        pagina, excedido = parsear(crudo, capa)
        tramos.extend(pagina)
        if not excedido or not pagina:
            return tramos, primera, total
        desde += len(pagina)
        time.sleep(PAUSA_S)


def buscar_cerca(capa: Capa, nombre: str, punto: tuple[float, float], radio_m: int = 2000,
                 descargar=_bajar) -> tuple[list[Tramo], str, int]:
    """Tramos con ese nombre (confirmado sin tildes) que pasan a radio_m de la estación."""
    objetivo = nombre_normalizado(nombre)
    tramos, url, nbytes = consultar(capa, where_nombre(capa, nombre), punto=punto, radio_m=radio_m,
                                    descargar=descargar)
    return [t for t in tramos if nombre_normalizado(t.nombre) == objetivo], url, nbytes


def bajar_rio(capa: Capa, nombre_capa: str, descargar=_bajar) -> tuple[list[Tramo], str, int]:
    """Todos los tramos del país con ese nombre literal de la capa (los homónimos se separan después)."""
    objetivo = nombre_normalizado(nombre_capa)
    tramos, url, nbytes = consultar(capa, where_nombre(capa, nombre_capa), descargar=descargar)
    return [t for t in tramos if nombre_normalizado(t.nombre) == objetivo], url, nbytes
