"""
Conector SENAMHI — avisos oficiales como áreas sombreadas (polígonos por nivel).

Dos productos, los dos servidos por la GeoServer de IDESEP (WFS, GeoJSON, sin key):
  1. Avisos meteorológicos (lluvia, temperatura, viento...): g_aviso:view_aviso. El WFS pide
     viewparams=qry:{nro}_{mapa}_{año} (un mapa por día de vigencia), así que primero hay que
     saber qué números están emitidos o vigentes: se leen de la tabla HTML de la web de
     SENAMHI (tabla_avisos). La página de detalle trae el párrafo oficial de cada aviso
     (descripciones), del que sale la intensidad ("de ligera a moderada intensidad").
  2. Aviso de lluvia acumulada en 24 h: g_prono_pp_24h:view_aviso24h, sin parámetros (siempre
     el último). Rige 24 h desde las 13:00 de Lima de su 'fecha' (Aviso N°265 del 22-09-2026:
     "Fecha de inicio: ... 13:00 horas", "Duración: 24 hrs").

Niveles: Nivel 1 = sin aviso (cubre el resto del país: se excluye con cql_filter, pesa ~2 MB),
Nivel 2 = amarillo, Nivel 3 = naranja, Nivel 4 = rojo.

Trampas verificadas (22-09-2026):
  - El WFS de un aviso puede traer registros duplicados con fechas erróneas (el 374 trae su
    juego de septiembre y otro igual con fechas de agosto y el mismo fecha_emi): se filtra por
    fech_ini contra las fechas de Inicio y Fin de la tabla.
  - Las fechas del WFS vienen en UTC (05:00Z = 00:00 en Lima; fech_fin 04:59:59Z = 23:59:59).
  - El año en viewparams hace falta: los números se reinician cada año.
  - La GeoServer es intermitente y a veces lenta (de 1 a 16 s por petición): con_reintentos.
  - Si la GeoServer falla, responde un XML de excepción con HTTP 200: no es JSON y se trata
    como falla (ValueError), no como "sin polígonos". Un mapa de un aviso vigente sin
    polígonos válidos también es falla: no se sabe si el aviso terminó o si el WFS aún no lo
    publica.
  - Solo las filas activas llevan etiqueta ("376 (emitido)", "374 (vigente)"); el histórico
    (~2050 filas) no. Si la etiqueta o la cabecera cambian, la tabla no debe leerse como "no
    hay avisos": se valida la cabecera y toda fila sin etiqueta que aún no termina (y no está
    cancelada) va a `problemas`.
  - Una actualización ("... (ACTUALIZACIÓN DEL AVISO 373)") sale con otro número y el
    original puede seguir listado como vigente a la vez (32 casos en el histórico, todos
    solapados): Aviso.actualiza dice a cuál reemplaza. Las extensiones ("EXTENSIÓN DEL AVISO
    N") continúan al original, no lo reemplazan.
  - La vista de 24 h sin filtro siempre trae el Nivel 1 (el resto del país): la respuesta
    filtrada vacía se confirma con una consulta liviana (solo nivel y fecha, ~1 kB).

Licencia (https://www.senamhi.gob.pe/?p=terminos-condiciones): uso libre, con o sin fines de
lucro, sin comercializar la información, y con la leyenda literal ATRIBUCION en todo soporte.
Los polígonos simplificados y los textos en lenguaje claro deben rotularse como "basado en el
aviso de SENAMHI" (con enlace al original), no como el aviso oficial.
"""
from __future__ import annotations

import html
import json
import logging
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from . import _http
from .senamhi import HORA_PERU

log = logging.getLogger(__name__)

# Leyenda literal que exigen los términos de uso de SENAMHI "en todo tipo de soporte".
ATRIBUCION = (
    "Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología "
    "del Perú. El uso que se le da a esta información es de mi (nuestra) entera responsabilidad"
)

WEB = "https://www.senamhi.gob.pe/"
URL_TABLA = f"{WEB}?p=aviso-meteorologico"
URL_AVISO_24H = f"{WEB}?p=aviso-24H"
_HOST_WEB = urllib.parse.urlparse(WEB).netloc

GEOSERVER = "https://idesep.senamhi.gob.pe/geoserver"
WFS_AVISO = f"{GEOSERVER}/g_aviso/ows"
WFS_24H = f"{GEOSERVER}/g_prono_pp_24h/ows"
CAPA_AVISO = "g_aviso:view_aviso"
CAPA_24H = "g_prono_pp_24h:view_aviso24h"
SIN_NIVEL_1 = "nivel<>'Nivel 1'"

MAX_HTML_BYTES = 10 * 1024 * 1024    # la tabla con todo el histórico pesa ~1,2 MB
MAX_WFS_BYTES = 30 * 1024 * 1024     # un mapa filtrado pesa de 0,1 a 1,4 MB
MAX_LIVIANO_BYTES = 1024 * 1024      # la vista de 24 h con solo nivel y fecha pesa ~1 kB
MAX_MAPAS = 5                        # un mapa por día; los avisos duran de 1 a 4 días
HORA_INICIO_24H = time(13, 0)        # el aviso de 24 h rige desde las 13:00 de Lima

NIVEL_COLOR = {2: "amarillo", 3: "naranja", 4: "rojo"}
_COLOR_NIVEL = {"AMARILLO": 2, "NARANJA": 3, "ROJO": 4}
# Columnas de la tabla, en mayúsculas y solo letras ('Nro.' -> 'NRO', 'Emisi&oacute;n' -> 'EMISION').
_CABECERA = ({"AVISO"}, {"NRO", "NUMERO", "N"}, {"EMISION"}, {"INICIO"}, {"FIN"}, {"DURACION"}, {"NIVEL"})
_ETIQUETA = re.compile(r"0*(\d+)\s*\((emitido|vigente)\)", re.I)
_ACTUALIZACION = re.compile(r"\(ACTUALIZACION DEL AVISO\D*0*(\d+)\)")   # sobre plano(titulo)


@dataclass
class Aviso:
    """Una fila emitida o vigente de la tabla de avisos meteorológicos."""
    numero: int
    anio: int
    titulo: str
    estado: str          # 'emitido' | 'vigente'
    emision: date
    inicio: date         # fecha de Perú
    fin: date            # fecha de Perú (inclusive: el aviso termina a las 23:59 de ese día)
    nivel: int | None    # nivel máximo del aviso según la tabla (2, 3 o 4)
    url: str | None = None   # página oficial del aviso

    @property
    def tema(self) -> str:
        return tema_de_titulo(self.titulo)

    @property
    def cancelado(self) -> bool:
        return "CANCELAD" in plano(self.titulo)

    @property
    def actualiza(self) -> tuple[int, int] | None:
        """
        (año, número) del aviso que esta actualización reemplaza: '(ACTUALIZACIÓN DEL AVISO
        373)' -> (2026, 373). Los números se reinician cada año y una actualización siempre
        lleva un número mayor que su original: si no es así, el original es del año anterior.
        """
        m = _ACTUALIZACION.search(plano(self.titulo))
        n = int(m.group(1)) if m else None
        if n is None or n == self.numero:
            return None
        return (self.anio if n < self.numero else self.anio - 1, n)

    @property
    def inicio_utc(self) -> datetime:
        return datetime.combine(self.inicio, time(0, 0), HORA_PERU).astimezone(timezone.utc)

    @property
    def fin_utc(self) -> datetime:
        return datetime.combine(self.fin + timedelta(days=1), time(0, 0), HORA_PERU).astimezone(timezone.utc)

    @property
    def mapas(self) -> int:
        """Un mapa por día de vigencia (el 376, del 23 al 24, tiene los mapas 1 y 2)."""
        return max(1, min(MAX_MAPAS, (self.fin - self.inicio).days + 1))


@dataclass
class TablaAvisos:
    avisos: list[Aviso]            # emitidos y vigentes
    filas: int                     # filas leídas, con el histórico
    problemas: list[str] = field(default_factory=list)   # filas activas que no se entendieron


@dataclass
class Area:
    """Polígonos de un mismo nivel en un mismo mapa (día) de un aviso."""
    tipo: str                  # 'meteorologico' | 'lluvia24h'
    anio: int
    numero: int | None         # None en lluvia24h
    mapa: int
    nivel: int                 # 2, 3 o 4
    inicio: datetime           # UTC
    fin: datetime              # UTC
    geometrias: list[dict] = field(default_factory=list)   # geometrías GeoJSON (EPSG:4326)


# ---------------------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------------------
def plano(texto: str) -> str:
    """Mayúsculas sin tildes: 'Nevada, precipitación' -> 'NEVADA, PRECIPITACION'."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.upper()


def tema_de_titulo(titulo: str) -> str:
    """'lluvia' | 'temperatura' | 'viento' | 'otro', según el título del aviso."""
    t = plano(titulo)
    if re.search(r"PRECIPITAC|LLUVIA|LLOVIZNA|NIEVE|NEVADA|GRANIZ", t):
        return "lluvia"
    if re.search(r"TEMPERATURA|FRIAJE|HELADA|CALOR", t):
        return "temperatura"
    if "VIENTO" in t:
        return "viento"
    return "otro"


def _texto(fragmento: str) -> str:
    sin_etiquetas = re.sub(r"<[^>]+>", " ", fragmento)
    return re.sub(r"\s+", " ", html.unescape(sin_etiquetas)).strip()


def _fecha_utc(valor) -> datetime | None:
    """'2026-09-23T05:00:00Z' -> datetime en UTC; None si no se entiende."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    try:
        dt = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _fecha(valor) -> date | None:
    """'2026-09-22Z' (fecha de GeoServer) -> date; None si no se entiende."""
    if not isinstance(valor, str):
        return None
    try:
        return date.fromisoformat(valor.strip()[:10])
    except ValueError:
        return None


def _nivel(valor) -> int | None:
    """'Nivel 3' -> 3; None si no es 2, 3 o 4."""
    m = re.search(r"(\d)", str(valor or ""))
    n = int(m.group(1)) if m else None
    return n if n in NIVEL_COLOR else None


def _es_enlace_web(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and p.netloc == _HOST_WEB


def _bajar_texto(url: str) -> str:
    return _http.get_bytes(url, MAX_HTML_BYTES).decode("utf-8", "replace")


# ---------------------------------------------------------------------------------------
# 1) Qué avisos están emitidos o vigentes (tabla HTML)
# ---------------------------------------------------------------------------------------
def _cabecera(pagina: str, ini_tbody: int) -> list[str]:
    """Títulos de columna del <thead> que precede al <tbody>, en mayúsculas y solo letras."""
    ini = pagina.rfind("<thead", 0, ini_tbody)
    fin = pagina.find("</thead>", ini)
    if ini < 0 or not ini < fin < ini_tbody:
        return []
    titulos = re.findall(r"<th\b[^>]*>(.*?)</th>", pagina[ini:fin], re.S | re.I)
    return [re.sub(r"[^A-Z]", "", plano(_texto(t))) for t in titulos]


def _url_fila(fila: str) -> str | None:
    enlace = re.search(r"""href=["']([^"']+)["']""", fila)
    # el href viene con '&' sueltos (&a=2026&b=...): solo se decodifica '&amp;'
    url = urllib.parse.urljoin(WEB, enlace.group(1).replace("&amp;", "&")) if enlace else None
    return url if url and _es_enlace_web(url) else None


def _anio(url: str | None, emision: date) -> int:
    """Año del aviso: el del enlace (&a=2026) o, si no trae, el de la emisión."""
    m = re.search(r"[?&]a=(\d{4})\b", url or "")
    return int(m.group(1)) if m else emision.year


def _sin_etiqueta_activas(filas: list[tuple[str, list[str], str]], avisos: list[Aviso], hoy: date) -> list[str]:
    """
    Filas sin etiqueta (emitido)/(vigente) que aún no terminan (Fin >= hoy): si SENAMHI cambia
    o quita la etiqueta, un aviso en curso no debe leerse como "ya no está". No cuentan las
    canceladas ni los originales de una actualización vigente (sigue la actualización). Las
    fechas de Fin ilegibles se cuentan juntas: el histórico no se puede descartar sin ellas.
    """
    reemplazados = {a.actualiza for a in avisos if a.actualiza and not a.cancelado and a.fin >= hoy}
    problemas: list[str] = []
    ilegibles = 0
    for nro, celdas, fila in filas:
        if "CANCELAD" in plano(_texto(celdas[0])):
            continue
        try:
            fin = date.fromisoformat(_texto(celdas[4]))
        except ValueError:
            ilegibles += 1
            continue
        if fin < hoy:
            continue   # histórico
        m = re.match(r"0*(\d+)", nro)
        try:
            anio = _anio(_url_fila(fila), date.fromisoformat(_texto(celdas[2])))
        except ValueError:
            anio = fin.year
        if m and (anio, int(m.group(1))) in reemplazados:
            continue
        problemas.append(f"fila '{nro}': sin etiqueta (emitido)/(vigente) y termina el {fin}")
    if ilegibles:
        problemas.append(f"filas sin etiqueta con la fecha de fin ilegible: {ilegibles}")
    return problemas


def parse_tabla(pagina: str, hoy: date | None = None) -> TablaAvisos:
    """
    Filas emitidas o vigentes de la tabla ?p=aviso-meteorologico (columnas Aviso, Nro.,
    Emisión, Inicio, Fin, Duración, Nivel). `hoy` es la fecha de Perú (por defecto, la actual).
    Falla (ValueError) si la tabla no aparece, si cambió la cabecera o si ninguna fila trae
    las 7 columnas: una página cambiada no se confunde con "no hay avisos". Las filas activas
    que no se entienden, y las que no traen etiqueta pero aún no terminan, van a `problemas`.
    """
    hoy = hoy or datetime.now(HORA_PERU).date()
    ini, fin = pagina.find("<tbody"), pagina.find("</tbody>")
    if ini < 0 or fin < ini:
        raise ValueError("No se encontró la tabla de avisos en la página de SENAMHI")
    cabecera = _cabecera(pagina, ini)
    if len(cabecera) < len(_CABECERA) or any(c not in validos for c, validos in zip(cabecera, _CABECERA)):
        raise ValueError(f"Cambió la cabecera de la tabla de avisos de SENAMHI: {cabecera}")
    filas = re.findall(r"<tr[^>]*>(.*?)</tr>", pagina[ini:fin], re.S | re.I)
    if not filas:
        raise ValueError("La tabla de avisos de SENAMHI vino vacía")
    avisos: list[Aviso] = []
    problemas: list[str] = []
    sin_etiqueta: list[tuple[str, list[str], str]] = []
    completas = 0
    for fila in filas:
        celdas = re.findall(r"<td[^>]*>(.*?)</td>", fila, re.S | re.I)
        if len(celdas) < 7:
            if _ETIQUETA.search(_texto(fila)):   # una fila activa con otra forma
                problemas.append(f"fila '{_texto(fila)[:80]}': trae {len(celdas)} columnas")
            continue
        completas += 1
        nro = _texto(celdas[1])
        m = _ETIQUETA.match(nro)
        if not m:
            sin_etiqueta.append((nro, celdas, fila))
            continue
        try:
            url = _url_fila(fila)
            emision = date.fromisoformat(_texto(celdas[2]))
            avisos.append(Aviso(
                numero=int(m.group(1)),
                anio=_anio(url, emision),
                titulo=_texto(celdas[0]),
                estado=m.group(2).lower(),
                emision=emision,
                inicio=date.fromisoformat(_texto(celdas[3])),
                fin=date.fromisoformat(_texto(celdas[4])),
                nivel=_COLOR_NIVEL.get(plano(_texto(celdas[6]))),
                url=url,
            ))
        except ValueError as e:
            problemas.append(f"fila '{nro}': {e}")
    if not completas:
        raise ValueError("Ninguna fila de la tabla de avisos de SENAMHI trae las 7 columnas")
    problemas += _sin_etiqueta_activas(sin_etiqueta, avisos, hoy)
    return TablaAvisos(avisos=avisos, filas=len(filas), problemas=problemas)


def tabla_avisos(hoy: date | None = None) -> TablaAvisos:
    """Avisos meteorológicos emitidos y vigentes (lee ~1,2 MB de HTML: una vez por hora basta)."""
    return parse_tabla(_http.con_reintentos(_bajar_texto, URL_TABLA), hoy)


# ---------------------------------------------------------------------------------------
# 2) Párrafo oficial de cada aviso (página de detalle; es opcional)
# ---------------------------------------------------------------------------------------
def parse_descripciones(pagina: str) -> dict[tuple[int, int], str]:
    """
    {(año, número): 'El SENAMHI informa que...'} de la página de avisos vigentes, que trae
    una pestaña por aviso (id="tabs-3762026" = aviso 376 de 2026).
    """
    out: dict[tuple[int, int], str] = {}
    cortes = list(re.finditer(r"""<div[^>]*\bid=["']tabs-(\d+)(\d{4})["']""", pagina))
    for i, m in enumerate(cortes):
        bloque = pagina[m.end():cortes[i + 1].start() if i + 1 < len(cortes) else len(pagina)]
        p = re.search(r"(El SENAMHI informa.*?)<", bloque, re.S)
        if p:
            out[(int(m.group(2)), int(m.group(1)))] = _texto(p.group(1))
    return out


def descripciones(url: str) -> dict[tuple[int, int], str]:
    """Párrafos oficiales de todos los avisos vigentes (una página de ~1,3 MB los trae todos)."""
    if not _es_enlace_web(url):
        raise ValueError(f"Enlace de aviso fuera de {_HOST_WEB}: {url}")
    return parse_descripciones(_http.con_reintentos(_bajar_texto, url))


# ---------------------------------------------------------------------------------------
# 3) Polígonos por WFS
# ---------------------------------------------------------------------------------------
def _url_wfs(base: str, capa: str, **extra) -> str:
    """URL GetFeature en GeoJSON; sin Nivel 1 salvo que se pase cql_filter=None."""
    params = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": capa,
              "cql_filter": SIN_NIVEL_1, **extra, "outputFormat": "application/json"}
    return base + "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})


def _features(url: str, max_bytes: int = MAX_WFS_BYTES) -> list[dict]:
    datos = _http.con_reintentos(_http.get_bytes, url, max_bytes)
    try:
        fc = json.loads(datos.decode("utf-8", "replace"))
    except ValueError as e:   # excepción XML de GeoServer (llega con HTTP 200)
        raise ValueError(f"El WFS de IDESEP no devolvió GeoJSON: {datos[:200]!r}") from e
    if not isinstance(fc, dict) or fc.get("type") != "FeatureCollection" \
            or not isinstance(fc.get("features"), list):
        raise ValueError("El WFS de IDESEP no devolvió una FeatureCollection")
    return fc["features"]


def _geometria(feature: dict) -> dict | None:
    g = feature.get("geometry")
    if isinstance(g, dict) and g.get("type") in ("Polygon", "MultiPolygon") and g.get("coordinates"):
        return g
    return None


def _agrupar(areas: dict, clave: tuple, base: Area, geometria: dict) -> None:
    area = areas.get(clave)
    if area is None:
        areas[clave] = area = base
    else:
        area.inicio, area.fin = min(area.inicio, base.inicio), max(area.fin, base.fin)
    area.geometrias.append(geometria)


def areas_de_features(aviso: Aviso, mapa: int, features: list[dict]) -> tuple[list[Area], int]:
    """
    Áreas (una por nivel) de un mapa de un aviso y cuántos polígonos se descartaron. Se
    descartan los que no empiezan dentro de las fechas de la tabla (registros erróneos del
    WFS), los de otro número de aviso y los que no traen nivel, fechas o geometría válidas.
    """
    areas: dict[int, Area] = {}
    descartados = 0
    for f in features:
        p = f.get("properties") or {}
        nivel, geometria = _nivel(p.get("nivel")), _geometria(f)
        inicio, fin = _fecha_utc(p.get("fech_ini")), _fecha_utc(p.get("fech_fin"))
        nro = p.get("nro_aviso")
        if (nivel is None or geometria is None or inicio is None or fin is None or fin <= inicio
                or (nro is not None and str(nro).lstrip("0") != str(aviso.numero))
                or not aviso.inicio <= inicio.astimezone(HORA_PERU).date() <= aviso.fin):
            descartados += 1
            continue
        base = Area(tipo="meteorologico", anio=aviso.anio, numero=aviso.numero,
                    mapa=mapa, nivel=nivel, inicio=inicio, fin=fin)
        _agrupar(areas, nivel, base, geometria)
    return list(areas.values()), descartados


def areas_aviso(aviso: Aviso) -> tuple[list[Area], int]:
    """
    Todas las áreas de un aviso (un WFS por mapa, del 1 al número de días) y los polígonos
    descartados. Si un mapa falla, falla el aviso entero: no se guarda un aviso a medias. Un
    mapa sin polígonos válidos también es falla (ValueError): el aviso sigue en la tabla, así
    que el WFS aún no lo publica o trae datos rotos, y no hay que borrar lo que ya se tenía.
    """
    areas: list[Area] = []
    descartados = 0
    for mapa in range(1, aviso.mapas + 1):
        url = _url_wfs(WFS_AVISO, CAPA_AVISO, viewparams=f"qry:{aviso.numero}_{mapa}_{aviso.anio}")
        a, d = areas_de_features(aviso, mapa, _features(url))
        if not a:
            raise ValueError(f"el WFS no trae polígonos válidos del mapa {mapa} de {aviso.mapas} "
                             f"({d} descartados)")
        areas += a
        descartados += d
    return areas, descartados


def areas_de_features_24h(features: list[dict]) -> list[Area]:
    """
    Áreas (una por nivel) del aviso de lluvia de 24 h. Rige de las 13:00 de Lima de su
    'fecha' a las 13:00 del día siguiente. Si llegaran varias fechas se queda la más nueva.
    """
    validos = []
    for f in features:
        p = f.get("properties") or {}
        fecha, nivel, geometria = _fecha(p.get("fecha")), _nivel(p.get("nivel")), _geometria(f)
        if fecha and nivel and geometria:
            validos.append((fecha, nivel, geometria))
    if not validos:
        return []
    ultima = max(fecha for fecha, _, _ in validos)
    inicio = datetime.combine(ultima, HORA_INICIO_24H, HORA_PERU).astimezone(timezone.utc)
    areas: dict[int, Area] = {}
    for fecha, nivel, geometria in validos:
        if fecha == ultima:
            base = Area(tipo="lluvia24h", anio=ultima.year, numero=None, mapa=1, nivel=nivel,
                        inicio=inicio, fin=inicio + timedelta(hours=24))
            _agrupar(areas, nivel, base, geometria)
    return list(areas.values())


def _fechas_24h() -> list[date]:
    """Fechas de toda la vista de 24 h (con el Nivel 1) sin geometrías: ~1 kB."""
    url = _url_wfs(WFS_24H, CAPA_24H, cql_filter=None, propertyName="nivel,fecha")
    fechas = (_fecha((f.get("properties") or {}).get("fecha")) for f in _features(url, MAX_LIVIANO_BYTES))
    return [f for f in fechas if f]


def aviso_24h(hoy: date | None = None) -> list[Area]:
    """
    Áreas del último aviso de lluvia de 24 h (lista vacía si hoy no hay zonas con aviso).
    `hoy` es la fecha de Perú (por defecto, la actual). Como la vista siempre trae el Nivel 1,
    una respuesta filtrada vacía se confirma con _fechas_24h. Falla (ValueError) si la vista
    vino vacía o si su último aviso es de antes de ayer (la vista dejó de actualizarse): eso
    no es "sin zonas con aviso".
    """
    hoy = hoy or datetime.now(HORA_PERU).date()
    areas = areas_de_features_24h(_features(_url_wfs(WFS_24H, CAPA_24H)))
    if areas:
        ultima = areas[0].inicio.astimezone(HORA_PERU).date()
    else:
        fechas = _fechas_24h()
        if not fechas:
            raise ValueError("La vista del aviso de lluvia de 24 h vino vacía (sin el Nivel 1)")
        ultima = max(fechas)
    if ultima < hoy - timedelta(days=1):
        raise ValueError(f"El aviso de lluvia de 24 h no se actualiza desde el {ultima}")
    return areas
