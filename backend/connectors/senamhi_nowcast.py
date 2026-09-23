"""
Conector SENAMHI — nowcasting de lluvia: manchas de lluvia para ahora, +1 h y +2 h.

Producto (verificado en vivo el 22-09-2026; SENAMHI no lo documenta):
  - Visor oficial URL_VISOR: trae el último fichero en `var fichero = "nowcasting_20260922-
    2040_forecast_20260922-2140_web"` y los del día en enlaces data-fichero="...". El nombre va
    en HORA DE LIMA (2040 = 20:40 de Lima = 01:40Z). La emisión T es la más nueva de los dos.
  - GeoServer de IDESEP, capa CAPA (WFS). Es una vista SQL que exige viewparams=fichero:<nombre>
    (sin él devuelve 0 elementos). Tres ficheros por emisión T (ver ficheros()):
      nowcasting_{T}_analysis_{T}_web         ahora (análisis)
      nowcasting_{T}_forecast_{T+1h}_web      +1 h
      nowcasting_{T}_forecast_{T+2h}_web      +2 h
  - Campos: nivel (0 = sin color; 1, 2 y 3 = lluvia moderada, fuerte y extrema según la
    leyenda del visor), fecha1 / fecha2 (validez, en UTC: [T, T] en el análisis, [T, T+1h] en
    el +1 h y [T, T+2h] en el +2 h), fichero, producto, gid y ppmin / ppmax (sin unidad
    documentada: no se leen).
  - Polígonos de celdas de ~2 km para el Perú y los países vecinos (x de -90 a -60, y de -20
    a 5): el recorte al Perú se hace en SQL (backend/ingesta/nowcast.py).

Trampas verificadas:
  - Sale cada 10 min, pero con huecos: el 22-09 hubo 90 emisiones de 124 posibles hasta las
    20:40 y ninguna más hasta pasadas las 23:25. La tarea mide la edad de la emisión.
  - En WFS 2.0 el BBOX del CQL va en orden lat,lon, y en el orden inverso devuelve 0 elementos
    sin error: no se usa BBOX (se recorta en SQL) y se controla el orden de ejes del primer
    vértice (con los ejes invertidos cae fuera del dominio).
  - Si la GeoServer falla responde un XML de excepción con HTTP 200: es falla, no "sin
    manchas". Una respuesta filtrada (nivel>0) vacía se confirma con una consulta sin filtro
    de un solo elemento; si esa también viene vacía, el fichero aún no existe
    (ProductoNoPublicado).
  - Con 6 peticiones en paralelo la GeoServer cortó la conexión: todo en serie y con PAUSA_S.
  - Es EXPERIMENTAL: "Este producto es referencial y aún se encuentra en etapa de calibración"
    (?p=reportes-nowcasting). El texto por nivel del visor es la plantilla del aviso de 24 h
    ("acumuladas en 24 horas", "descargas eléctricas"): no es un dato de rayos.

Licencia: la de SENAMHI (leyenda literal ATRIBUCION de senamhi_avisos.py en todo soporte).
"""
from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import _http
from .senamhi import HORA_PERU

URL_VISOR = "https://www.senamhi.gob.pe/mapas/mapa-nowcasting/nowcasting-pronostico-1h.php"
WFS = "https://idesep.senamhi.gob.pe/geoserver/ows"
CAPA = "g_nowcasting:view_nowcasting"
PERU = (-81.4, -18.4, -68.6, 0.1)           # lon_min, lat_min, lon_max, lat_max (recorte y conteo)
# El visor pesa ~48 KB; una respuesta filtrada, de 0,1 a 0,7 MB (256 elementos el 22-09 20:40).
MAX_VISOR_BYTES, MAX_WFS_BYTES, MAX_FEATURES, PAUSA_S = 1 << 20, 10 << 20, 3000, 1.5
# Intentos por pedido al WFS: el producto se renueva cada 10 min y la tarea tiene 240 s, así
# que un pedido colgado no se reintenta tanto como en las demás fuentes (~1 min como máximo).
INTENTOS_WFS = 2

_VAR = re.compile(r'var\s+fichero\s*=\s*"nowcasting_(\d{8}-\d{4})_(?:analysis|forecast)_\d{8}-\d{4}_web"')
_DATA = re.compile(r'data-fichero="nowcasting_(\d{8}-\d{4})_forecast_')
# El mismo formato que exige el CHECK de nowcast_producto.fichero (va dentro de viewparams).
_FICHERO = re.compile(r"nowcasting_\d{8}-\d{4}_(analysis|forecast)_\d{8}-\d{4}_web")   # con fullmatch
# Dominio del producto con margen: con los ejes invertidos (lat, lon) el primer vértice cae fuera.
_EJE_X, _EJE_Y = (-95.0, -55.0), (-30.0, 15.0)


class ProductoNoPublicado(ValueError):
    """El fichero no existe (todavía) en la GeoServer: vacío con filtro y sin filtro."""


@dataclass
class Producto:
    horizonte: int            # 0, 60 o 120
    fichero: str
    emision: datetime         # T, hora de Lima
    desde: datetime           # fecha1 (UTC)
    hasta: datetime           # fecha2 (UTC)
    por_nivel: dict[int, list[dict]] = field(default_factory=dict)   # geometrías que tocan PERU
    manchas: int = 0          # elementos de nivel 1 a 3 cuya caja toca PERU
    descartados: int = 0      # otro fichero, nivel fuera de 1-3 o geometría inválida


def pausa() -> None:
    """Espera entre pedidos a la GeoServer (las pruebas la reemplazan)."""
    time.sleep(PAUSA_S)


# ---------------------------------------------------------------------------------------
# Visor: cuál es la última emisión
# ---------------------------------------------------------------------------------------
def _hora_lima(valor: str) -> datetime | None:
    """'20260922-2040' -> 2026-09-22 20:40 en hora de Lima; None si no es una fecha válida."""
    try:
        return datetime.strptime(valor, "%Y%m%d-%H%M").replace(tzinfo=HORA_PERU)
    except ValueError:
        return None


def ultima_emision(html: str) -> datetime:
    """La emisión más nueva que nombra el visor (var fichero y data-fichero), en hora de Lima."""
    horas = [h for h in map(_hora_lima, _VAR.findall(html) + _DATA.findall(html)) if h]
    if not horas:
        raise ValueError("No se encontró el fichero del nowcasting en el visor de SENAMHI")
    return max(horas)


def emision_visor() -> datetime:
    """Última emisión publicada (una petición al visor, ~48 KB)."""
    datos = _http.con_reintentos(_http.get_bytes, URL_VISOR, MAX_VISOR_BYTES)
    return ultima_emision(datos.decode("utf-8", "replace"))


def ficheros(T: datetime) -> dict[int, str]:
    """Nombre del fichero de cada horizonte de la emisión T (el +1 h y el +2 h cruzan la medianoche)."""
    t = T.astimezone(HORA_PERU)
    base = f"nowcasting_{t:%Y%m%d-%H%M}"
    return {0: f"{base}_analysis_{t:%Y%m%d-%H%M}_web",
            60: f"{base}_forecast_{t + timedelta(minutes=60):%Y%m%d-%H%M}_web",
            120: f"{base}_forecast_{t + timedelta(minutes=120):%Y%m%d-%H%M}_web"}


# ---------------------------------------------------------------------------------------
# WFS
# ---------------------------------------------------------------------------------------
def url_wfs(fichero: str, filtrado: bool = True) -> str:
    """
    GetFeature (WFS 2.0, GeoJSON) de un fichero. Filtrada: solo nivel > 0, con la geometría.
    Sin filtro: un solo elemento y sin geometría (~1 kB), para saber si el fichero existe.
    Sin BBOX a propósito (ver el docstring del módulo).
    """
    if not _FICHERO.fullmatch(fichero):
        raise ValueError(f"Nombre de fichero de nowcasting inesperado: {fichero!r}")
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": CAPA,
              "outputFormat": "application/json", "viewparams": f"fichero:{fichero}"}
    if filtrado:
        params |= {"CQL_FILTER": "nivel>0", "propertyName": "nivel,fecha1,fecha2,fichero,geom"}
    else:
        params |= {"count": "1", "propertyName": "nivel,fecha1,fecha2,fichero"}
    return WFS + "?" + urllib.parse.urlencode(params)


def _coleccion(url: str) -> dict:
    datos = _http.con_reintentos(_http.get_bytes, url, MAX_WFS_BYTES, intentos=INTENTOS_WFS)
    try:
        return json.loads(datos.decode("utf-8", "replace"))
    except ValueError as e:   # excepción XML de GeoServer (llega con HTTP 200)
        raise ValueError(f"El WFS del nowcasting no devolvió GeoJSON: {datos[:200]!r}") from e


def _fecha_utc(valor) -> datetime | None:
    """'2026-09-23T01:40:00Z' -> datetime en UTC; None si no se entiende."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    try:
        dt = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _nivel(valor) -> int | None:
    """1, 2 o 3 (también como texto); None para el 0 (sin color) y lo demás."""
    if isinstance(valor, str) and valor.strip().isdigit():
        valor = int(valor)
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor if 1 <= valor <= 3 else None


def _anillo_valido(anillo) -> bool:
    """Lista cerrada de 4 o más vértices [x, y(, z)] finitos (si no, st_geomfromgeojson falla)."""
    if not isinstance(anillo, list) or len(anillo) < 4:
        return False
    for v in anillo:
        if not isinstance(v, list) or len(v) < 2 or not all(
                isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in v[:2]):
            return False
    return anillo[0][:2] == anillo[-1][:2]


def _geometria(feature: dict) -> dict | None:
    """
    Polygon o MultiPolygon bien formado; None si no. Se valida aquí porque una sola geometría
    rota haría fallar el SQL y, con él, toda la transacción (los tres horizontes).
    """
    g = feature.get("geometry")
    if not isinstance(g, dict) or g.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    c = g.get("coordinates")
    poligonos = c if g["type"] == "MultiPolygon" else [c]
    if not isinstance(poligonos, list) or not poligonos:
        return None
    for poligono in poligonos:
        if not isinstance(poligono, list) or not poligono or not all(map(_anillo_valido, poligono)):
            return None
    return g


def _vertices(g: dict):
    poligonos = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    for poligono in poligonos:
        for anillo in poligono:
            yield from anillo


def _toca_peru(g: dict) -> bool:
    """La caja de la geometría toca el recuadro PERU (el recorte fino lo hace el SQL)."""
    xs, ys = zip(*((v[0], v[1]) for v in _vertices(g)))
    return max(xs) >= PERU[0] and min(xs) <= PERU[2] and max(ys) >= PERU[1] and min(ys) <= PERU[3]


def parse_features(fc: dict, fichero: str) -> tuple[dict[int, list[dict]], datetime | None, datetime | None, int]:
    """
    ({nivel: [geometrías]}, fecha1, fecha2, descartados) de una respuesta del WFS. Se descartan
    (y se cuentan) los elementos de otro fichero, de nivel fuera de 1-3 o sin un Polygon o
    MultiPolygon válido. Las fechas salen de los elementos del fichero (la menor fecha1 y la
    mayor fecha2), también de los descartados por nivel o geometría. ValueError si no es una
    FeatureCollection, si trae más de MAX_FEATURES elementos o si el primer vértice aceptado
    no cae en el dominio del producto (ejes invertidos).
    """
    if not isinstance(fc, dict) or fc.get("type") != "FeatureCollection" or not isinstance(fc.get("features"), list):
        raise ValueError("El WFS del nowcasting no devolvió una FeatureCollection")
    if len(fc["features"]) > MAX_FEATURES:
        raise ValueError(f"El WFS del nowcasting trajo {len(fc['features'])} elementos (máximo {MAX_FEATURES})")
    por_nivel: dict[int, list[dict]] = {}
    desde = hasta = None
    descartados = 0
    for f in fc["features"]:
        f = f if isinstance(f, dict) else {}
        p = f.get("properties") or {}
        if p.get("fichero") != fichero:
            descartados += 1
            continue
        f1, f2 = _fecha_utc(p.get("fecha1")), _fecha_utc(p.get("fecha2"))
        desde = f1 if desde is None or (f1 and f1 < desde) else desde
        hasta = f2 if hasta is None or (f2 and f2 > hasta) else hasta
        nivel, g = _nivel(p.get("nivel")), _geometria(f)
        if nivel is None or g is None:
            descartados += 1
            continue
        if not por_nivel:
            x, y = next(_vertices(g))[:2]
            if not (_EJE_X[0] <= x <= _EJE_X[1] and _EJE_Y[0] <= y <= _EJE_Y[1]):
                raise ValueError(f"orden de ejes inesperado (primer vértice {x}, {y})")
        por_nivel.setdefault(nivel, []).append(g)
    return por_nivel, desde, hasta, descartados


def producto(T: datetime, h: int) -> Producto:
    """
    Manchas de nivel 1 a 3 del horizonte h (0, 60 o 120 min) de la emisión T. Una o dos
    peticiones, en serie. ProductoNoPublicado si el fichero no existe; ValueError si la
    respuesta no se entiende o faltan fecha1 / fecha2 (en h=60 se usa [T, T+60]).
    """
    fichero = ficheros(T)[h]
    por_nivel, desde, hasta, descartados = parse_features(_coleccion(url_wfs(fichero)), fichero)
    if not por_nivel:
        # Vacía con filtro: sin lluvia moderada o más fuerte, o el fichero aún no existe.
        pausa()
        fc = _coleccion(url_wfs(fichero, filtrado=False))
        _, desde, hasta, _ = parse_features(fc, fichero)
        if not any(isinstance(f, dict) and (f.get("properties") or {}).get("fichero") == fichero
                   for f in fc["features"]):
            raise ProductoNoPublicado(f"SENAMHI aún no publica {fichero}")
    if desde is None or hasta is None:
        if h != 60:
            raise ValueError(f"{fichero}: faltan fecha1 / fecha2")
        desde = T.astimezone(timezone.utc)
        hasta = desde + timedelta(minutes=60)
    if hasta < desde:
        raise ValueError(f"{fichero}: fecha2 ({hasta:%H:%M}Z) es anterior a fecha1 ({desde:%H:%M}Z)")
    # Solo lo que puede tocar el Perú (el SQL recorta con la geometría real).
    en_peru = {n: [g for g in gs if _toca_peru(g)] for n, gs in por_nivel.items()}
    en_peru = {n: gs for n, gs in sorted(en_peru.items()) if gs}
    return Producto(horizonte=h, fichero=fichero, emision=T.astimezone(HORA_PERU), desde=desde, hasta=hasta,
                    por_nivel=en_peru, manchas=sum(map(len, en_peru.values())), descartados=descartados)
