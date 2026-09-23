"""
Conector SENAMHI (GeoServer de IDESEP) — lluvia horaria de todo el Perú y fecha de las
capas de lluvia observada.

Tres productos:
  1. lecturas()                  -> última lectura de cada estación de la capa WFS
                                    g_umbrales:umbrales_precipitacion (~216 estaciones
                                    automáticas de 24 departamentos en una sola petición).
  2. fechas_lluvia_observada()   -> fecha que el visor de SENAMHI da a las capas WMS
                                    relativas monitoreo_meteorologico:prec_1 (ayer) y
                                    prec_1_ac07d.
  3. huella_prec_1()             -> huella de los valores de la capa WFS
                                    monitoreo_meteorologico:prec_1_all_points (las 546
                                    estaciones con que se interpola prec_1; ~60 KB pidiendo solo
                                    estacion y prec). Sirve para saber si prec_1 cambió de día.

Campos de la capa (verificados en vivo el 22-09-2026; no hay documentación publicada):
  nombre        nombre de la estación. NO trae código: hay homónimas (dos "CABO INGA" a
                400 m, una meteorológica y otra hidrológica) y algún nombre con la ñ mal
                codificada ("AYMAÃ±A"), que aquí se repara.
  pp            mm de lluvia de la hora que termina en fecha + hora (igual al valor de
                esa hora en la serie de map_red_graf.php).
  umbral        mm/h, de 1 a 25 según la estación. El visor de SENAMHI pinta la estación
                como "Alerta" cuando pp lo supera (COTAHUASI: 8 mm con umbral 5), pero su
                uso oficial no está documentado: es un "umbral de referencia de SENAMHI".
  pp_acum       mm de las ÚLTIMAS 6 HORAS (6 valores horarios, del de fecha + hora hacia
                atrás). No es el acumulado del día ni de 3 h: comprobado contra las series
                horarias (COTAHUASI a las 18:00 suma 13..18 h = 29,1 y deja fuera las
                12 h; SAPILLICA y SIBINACOCHA también cierran solo con 6 h).
  umb_acum      umbral de referencia para esas 6 h; en las 216 estaciones vale 3 x umbral.
  fecha, hora   'DD/MM/AAAA' y 'HH:MM:SS', hora de Perú. Cada estación trae la suya: la
                capa se va llenando durante la hora y alguna queda trabada horas atrás.
  departamento, provincia, distrito, cuenca   en mayúsculas y sin tildes.
  control       estado del punto en el visor: 1 "Alerta", 2 "Normal", 3 "atrasado por
                1 Hr", 4 "atrasado por más de 1 Hr". Mezcla frescura y umbral y cambia con
                el reloj: no se guarda (la frescura se calcula con fecha y hora).
  geometría     Point [lon, lat, altitud en m].

Las capas prec_1 / prec_1_ac07d son relativas (prec_N = N días atrás) y no dicen su fecha.
El visor oficial la muestra en botones con data-corrltv="N">AAAA-MM-DD; el mismo N sirve
a prec_N y a prec_N_ac07d, que suma prec_N .. prec_(N+6) (comprobado con los puntos de las
estaciones: 85 de 89 cierran al décimo de mm). O sea, prec_1_ac07d son los 7 días que
terminan el día de prec_1.

Qué es "prec_1 del 21 set": la lluvia de las 07:00 del 21 a las 07:00 del 22, hora de Perú
(el día pluviométrico de SENAMHI). Verificado contra las series horarias: CHOTA 6,9,
MALINOWSKY 3,6 y CHALACO 2,0 mm son su suma horaria de las 08 h del 21 a las 07 h del 22. Así
que el dato del 21 recién existe pasadas las 07:00 del 22, cuando SENAMHI lo procesa.

La fecha del visor parece salir del reloj del PHP, no de los datos: los 15 botones son días
seguidos que terminan "ayer", y ni las capacidades del WMS ni los puntos traen fecha. Si es
así, entre las 00:00 y el proceso de la mañana el visor ya dice "22" mientras la capa sigue
con el 21. Para notarlo está la huella de prec_1_all_points: la superficie prec_1 pasa por los valores de esos puntos
(GetFeatureInfo del 22-09-2026: SAN GABAN 59,3, CHINCHAVITO 20, SANTA MARIA DE NIEVA 16,7 y
LLAPA 13,5 mm, igual que el punto), o sea que son el mismo dato; mientras la huella no cambie
se asume que el ráster tampoco (el cambio de día no se pudo observar en vivo). La decisión
de qué fecha mostrar la toma la tarea: backend/ingesta/lluvia_nacional.resolver_fechas.

Licencia: los términos de SENAMHI exigen citar, en todo soporte, la leyenda literal de
ATRIBUCION. La GeoServer no envía CORS (el navegador no puede leer el WFS) y es lenta e
intermitente (3-8 s por petición): se reintenta con _http.con_reintentos.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import _http
from .senamhi import HORA_PERU

URL_WFS = "https://idesep.senamhi.gob.pe/geoserver/g_umbrales/ows"
PARAMS_WFS = {
    "service": "WFS",
    "version": "1.0.0",
    "request": "GetFeature",
    "typeName": "g_umbrales:umbrales_precipitacion",
    "outputFormat": "application/json",
}
URL_WFS_PREC = "https://idesep.senamhi.gob.pe/geoserver/monitoreo_meteorologico/ows"
PARAMS_PREC_1 = {
    "service": "WFS",
    "version": "1.0.0",
    "request": "GetFeature",
    "typeName": "monitoreo_meteorologico:prec_1_all_points",
    "propertyName": "estacion,prec",   # sin geometría ni textos: ~60 KB en vez de ~145 KB
    "outputFormat": "application/json",
}
URL_VISOR = "https://www.senamhi.gob.pe/mapas/mapa-monitoreo-meteo/monitoreo-precipitacion.php"
URL_TERMINOS = "https://www.senamhi.gob.pe/?p=terminos-condiciones"

# Leyenda literal que exigen los Términos y Condiciones de SENAMHI (sección "Usos
# permitidos") en todo soporte donde se use su información. Copiada tal cual el 22-09-2026.
ATRIBUCION = (
    "Información recopilada y trabajada por el Servicio Nacional de Meteorología e "
    "Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) "
    "entera responsabilidad"
)

MAX_BYTES_WFS = 5 * 1024 * 1024     # la capa pesa ~90 KB
MAX_BYTES_VISOR = 2 * 1024 * 1024   # el visor pesa ~24 KB
MAX_BYTES_PUNTOS = 2 * 1024 * 1024  # prec_1_all_points con estacion y prec pesa ~60 KB

# Perú con margen (el mismo recuadro que exige report.geom en la BD).
_LON = (-81.5, -68.5)
_LAT = (-18.5, 0.1)
# Por encima de esto es un código de error del sensor, no lluvia (el récord mundial en
# 1 h ronda los 300 mm).
_MAX_MM = {"pp": 300.0, "pp_acum": 1000.0}
# Una lectura con la hora más adelantada que esto respecto del reloj es un error de fecha.
_TOLERANCIA_FUTURO = timedelta(hours=1)


@dataclass
class LecturaUmbral:
    nombre: str
    lat: float
    lon: float
    altitud_m: float | None
    departamento: str | None     # tal como viene (mayúsculas, sin tildes)
    provincia: str | None
    distrito: str | None
    cuenca: str | None
    pp_1h: float | None          # mm en la hora que termina en medido_en
    umbral_1h: float | None      # umbral de referencia SENAMHI (mm/h)
    pp_6h: float | None          # mm en las 6 h que terminan en medido_en
    umbral_6h: float | None      # umbral de referencia SENAMHI para 6 h (= 3 x umbral_1h)
    medido_en: datetime          # con zona horaria de Perú

    @property
    def clave(self) -> str:
        """Identificador estable: la capa no trae código y hay nombres repetidos."""
        return f"{self.nombre}@{self.lat:.5f},{self.lon:.5f}"


def reparar_texto(texto: str) -> str:
    """'AYMAÃ±A' -> 'AYMAÑA': UTF-8 leído como Latin-1 en el origen. Si no se puede, igual."""
    if not re.search(r"[ÃÂ]", texto):
        return texto
    for codec in ("latin-1", "cp1252"):
        try:
            reparado = texto.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        # 'Ã±' es la ñ minúscula: si el nombre venía en mayúsculas, se mantiene así
        return reparado.upper() if texto.isupper() else reparado
    return texto


def _texto(valor) -> str | None:
    if not isinstance(valor, str):
        return None
    t = reparar_texto(valor).strip()
    return t or None


def _numero(valor, maximo: float | None = None) -> float | None:
    """mm >= 0; None si falta, no es número, es negativo (código de error) o es absurdo."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    v = float(valor)
    if v != v or v < 0 or (maximo is not None and v > maximo):   # v != v: NaN
        return None
    return v


def parse_medido_en(fecha: str, hora: str) -> datetime | None:
    """('22/09/2026', '18:00:00') -> 2026-09-22 18:00 en hora de Perú; None si no se entiende."""
    if not isinstance(fecha, str) or not isinstance(hora, str):
        return None
    f = fecha.strip().rstrip("Z")
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dia = datetime.strptime(f, formato).date()
            break
        except ValueError:
            continue
    else:
        return None
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", hora.strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return datetime(dia.year, dia.month, dia.day, int(m.group(1)), int(m.group(2)), tzinfo=HORA_PERU)


def _features(texto: str | bytes, capa: str) -> list:
    """
    Features de una respuesta WFS. ValueError si el cuerpo no es un GeoJSON: la GeoServer
    responde 200 con un ServiceExceptionReport en XML cuando falla.
    """
    try:
        datos = json.loads(texto)
    except (ValueError, UnicodeDecodeError) as e:
        muestra = texto[:200] if isinstance(texto, str) else texto[:200].decode("utf-8", "replace")
        raise ValueError(f"La capa {capa} no devolvió JSON: {muestra!r}") from e
    if not isinstance(datos, dict) or not isinstance(datos.get("features"), list):
        raise ValueError(f"La capa {capa} no devolvió una FeatureCollection")
    return datos["features"]


def parse_geojson(texto: str | bytes, ahora: datetime | None = None) -> tuple[list[LecturaUmbral], list[str]]:
    """
    FeatureCollection del WFS -> (lecturas válidas, avisos). Un punto mal formado se
    descarta con su aviso; no tumba al resto. Si el cuerpo no es un GeoJSON, ValueError.
    """
    features = _features(texto, "de umbrales")
    limite = (ahora + _TOLERANCIA_FUTURO) if ahora else None
    lecturas: list[LecturaUmbral] = []
    avisos: list[str] = []
    for i, f in enumerate(features):
        p = (f or {}).get("properties") or {}
        nombre = _texto(p.get("nombre"))
        etiqueta = nombre or f"punto {i}"
        coords = ((f or {}).get("geometry") or {}).get("coordinates")
        if not nombre:
            avisos.append(f"{etiqueta}: sin nombre")
            continue
        try:
            lon, lat = float(coords[0]), float(coords[1])
        except (TypeError, ValueError, IndexError):
            avisos.append(f"{etiqueta}: sin coordenadas")
            continue
        if not (_LON[0] <= lon <= _LON[1] and _LAT[0] <= lat <= _LAT[1]):
            avisos.append(f"{etiqueta}: coordenadas fuera del Perú ({lat}, {lon})")
            continue
        medido_en = parse_medido_en(p.get("fecha"), p.get("hora"))
        if medido_en is None:
            avisos.append(f"{etiqueta}: fecha u hora ilegible ({p.get('fecha')!r} {p.get('hora')!r})")
            continue
        if limite and medido_en > limite:
            avisos.append(f"{etiqueta}: hora en el futuro ({medido_en.isoformat()})")
            continue
        pp_1h = _numero(p.get("pp"), _MAX_MM["pp"])
        pp_6h = _numero(p.get("pp_acum"), _MAX_MM["pp_acum"])
        for campo, crudo, limpio in (("pp", p.get("pp"), pp_1h), ("pp_acum", p.get("pp_acum"), pp_6h)):
            if crudo is not None and limpio is None:
                avisos.append(f"{etiqueta}: {campo} descartado ({crudo!r})")
        altitud = None
        if len(coords) > 2 and isinstance(coords[2], (int, float)) and not isinstance(coords[2], bool):
            altitud = float(coords[2])
        lecturas.append(LecturaUmbral(
            nombre=nombre, lat=lat, lon=lon, altitud_m=altitud,
            departamento=_texto(p.get("departamento")), provincia=_texto(p.get("provincia")),
            distrito=_texto(p.get("distrito")), cuenca=_texto(p.get("cuenca")),
            pp_1h=pp_1h, umbral_1h=_numero(p.get("umbral")),
            pp_6h=pp_6h, umbral_6h=_numero(p.get("umb_acum")),
            medido_en=medido_en,
        ))
    return lecturas, avisos


def lecturas(ahora: datetime | None = None) -> tuple[list[LecturaUmbral], list[str]]:
    """Última lectura de cada estación de la capa (una petición para todo el país)."""
    url = URL_WFS + "?" + urllib.parse.urlencode(PARAMS_WFS)
    cuerpo = _http.con_reintentos(_http.get_bytes, url, MAX_BYTES_WFS)
    return parse_geojson(cuerpo, ahora)


@dataclass
class FechasLluviaObservada:
    prec_1: date                  # día de prec_1 según el visor ("ayer" por su reloj)
    prec_1_ac07d: date            # último día del acumulado de 7 días (= prec_1)
    prec_1_ac07d_desde: date      # primer día del acumulado (prec_1 - 6 días)

    def a_json(self) -> dict:
        return {"prec_1": self.prec_1.isoformat(), "prec_1_ac07d": self.prec_1_ac07d.isoformat(),
                "prec_1_ac07d_desde": self.prec_1_ac07d_desde.isoformat()}


def parse_fechas_visor(html: str) -> FechasLluviaObservada:
    """Fechas de los botones del visor: data-corrltv="1">2026-09-21</a>. ValueError si no están."""
    dias: dict[int, date] = {}
    for n, iso in re.findall(r"""data-corrltv\s*=\s*["']?(\d+)["']?[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*<""", html):
        try:
            dias.setdefault(int(n), date.fromisoformat(iso))
        except ValueError:
            continue
    if 1 not in dias:
        raise ValueError("No se encontró la fecha de prec_1 (data-corrltv=\"1\") en el visor de SENAMHI")
    # Coherencia: prec_N tiene que ser N-1 días antes que prec_1. Si no, el visor cambió de
    # formato y la fecha no es confiable.
    for n, d in dias.items():
        if d != dias[1] - timedelta(days=n - 1):
            raise ValueError(f"Fechas del visor incoherentes: prec_1={dias[1]} y prec_{n}={d}")
    return FechasLluviaObservada(prec_1=dias[1], prec_1_ac07d=dias[1],
                                 prec_1_ac07d_desde=dias[1] - timedelta(days=6))


def fechas_lluvia_observada() -> FechasLluviaObservada:
    cuerpo = _http.con_reintentos(_http.get_bytes, URL_VISOR, MAX_BYTES_VISOR)
    return parse_fechas_visor(cuerpo.decode("utf-8", "replace"))


def parse_huella(texto: str | bytes) -> str:
    """
    FeatureCollection de prec_1_all_points -> huella (16 hex del SHA-256) de los pares
    estación = lluvia. No depende del orden ni del id de los puntos (hay nombres repetidos:
    tres SAN PABLO; se cuentan todos). ValueError si no es un GeoJSON o no trae ningún valor:
    una capa vacía o a medio regenerar cambiaría la huella sin que haya un día nuevo.
    """
    pares: list[str] = []
    valores = 0
    for f in _features(texto, "prec_1_all_points"):
        p = (f or {}).get("properties") or {}
        v = p.get("prec")
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v:   # v == v: no NaN
            valores += 1
            v = f"{float(v):.2f}"
        else:
            v = "-"
        pares.append(f"{p.get('estacion')}={v}")
    if not valores:
        raise ValueError("La capa prec_1_all_points no trajo ningún valor de lluvia")
    return hashlib.sha256("\n".join(sorted(pares)).encode("utf-8")).hexdigest()[:16]


def huella_prec_1() -> str:
    url = URL_WFS_PREC + "?" + urllib.parse.urlencode(PARAMS_PREC_1)
    return parse_huella(_http.con_reintentos(_http.get_bytes, url, MAX_BYTES_PUNTOS))
