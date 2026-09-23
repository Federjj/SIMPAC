"""
Conector SENAMHI — pronóstico oficial del tiempo por localidad (?p=pronostico-meteorologico).

Una sola página (~770 KB, sin compresión, 0,2 a 0,3 s) trae las ~277 localidades del país
(17 en Cajamarca), cada una con 3 a 5 días: el ícono que eligió el pronosticador, máxima,
mínima y un texto ("Cielo nublado parcial variando a cielo nublado ... con lluvia."). No trae
coordenadas: las pone el catálogo backend/data/localidades_senamhi.json (lo arma
backend/mapas/semilla_localidades.py) y la lectura del texto está en
backend/ingesta/lectura_pronostico.py.

Forma de la página (verificada el 22-09-2026; el mismo patrón lee las copias de Wayback
desde enero de 2024):
  - "Emisión: martes, 22 de septiembre del 2026", sin hora. Sale una por día hábil, de
    noche (a las 20:15 todavía puede verse la del día anterior); en fines de semana y
    feriados sigue la del último día hábil.
  - Un bloque por localidad: <span class='nameCity'> con el enlace
    ?p=pronostico-detalle&dp=06&localidad=0011 y el nombre 'CAJAMARCA - CAJAMARCA'; por día,
    cinco <div>: col-sm-3 (fecha 'miércoles, 23 de septiembre', sin año), col-sm-1
    (iconNNN.png), text-danger (máxima, ' 21&ordm;C'), text-primary (mínima) y col-sm-6 (texto).
  - Puede traer el mismo día de la emisión (20 localidades traían "martes, 22" en la del
    22) y a veces solo 2 días. El mes viene como "septiembre" o "setiembre". Alguna vez
    repitió un día con dos textos distintos (copia del 25-05-2025): queda el primero.

Una página cambiada no se lee como "sin pronóstico": falla (ValueError) si no trae la
emisión o es posterior a hoy, si trae menos de MIN_LOCALIDADES o más de MAX_LOCALIDADES
legibles, o si más del MAX_PROBLEMAS de los bloques no se entendió. Un bloque cuyo número
de fechas no coincide con los días leídos se descarta entero (no se sabe qué día falta).

Licencia: la de SENAMHI (ATRIBUCION en backend/connectors/senamhi_avisos.py). El texto se
guarda literal; el ícono y el resumen de SIMPAC se rotulan "basados en SENAMHI".
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from . import _http
from .senamhi import HORA_PERU

URL_PAIS = "https://www.senamhi.gob.pe/?p=pronostico-meteorologico"
MAX_HTML_BYTES = 5 * 1024 * 1024   # hoy 770 KB
MIN_LOCALIDADES, MAX_LOCALIDADES, MAX_PROBLEMAS, MAX_TEXTO = 200, 400, 0.10, 600
TEMP_MIN, TEMP_MAX = -30, 50       # °C; fuera de esto es un error de tipeo y va como None
DIAS_ANTES, DIAS_DESPUES = 1, 7    # un día vale si cae entre emisión - 1 y emisión + 7

MESES = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7,
         "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11,
         "DICIEMBRE": 12}

_EMISION = re.compile(r"Emisi(?:&oacute;|ó)n:\s*([^<]+)", re.I)
_BLOQUE = re.compile(r"<span class=['\"]nameCity['\"]>", re.I)
_FIN_TABLA = re.compile(r"</tbody>", re.I)   # el último bloque llega hasta el pie de la página
_CABECERA = re.compile(r"dp=(\d{2})&(?:amp;)?localidad=(\d{4})['\"]>([^<]+)</a>", re.I)
_COL3 = re.compile(r"<div class=['\"]col-sm-3['\"]>", re.I)
# Temperatura con hasta 3 cifras (no 2): un '100' se descarta por rango en vez de leerse 10.
_DIA = re.compile(
    r"<div class=['\"]col-sm-3['\"]>\s*([^<]+?)\s*</div>\s*"
    r"<div class=['\"]col-sm-1['\"]>\s*<img[^>]*?icon(\d{3})\.png[^>]*>\s*</div>\s*"
    r"<div class=['\"]col-sm-1 text-danger['\"]>\s*<strong>\s*(-?\d{1,3})?[^<]*</strong>\s*</div>\s*"
    r"<div class=['\"]col-sm-1 text-primary['\"]>\s*<strong>\s*(-?\d{1,3})?[^<]*</strong>\s*</div>\s*"
    r"<div class=['\"]col-sm-6['\"]>([^<]*)</div>", re.I)


@dataclass
class Dia:
    fecha: date            # día pronosticado (hora de Perú)
    icono: str             # '009': el ícono que eligió el pronosticador
    tmax: int | None
    tmin: int | None
    texto: str             # literal (recortado a MAX_TEXTO)


@dataclass
class Localidad:
    dp: str                # '06'
    localidad: str         # '0011'
    nombre_senamhi: str    # 'CAJAMARCA - CAJAMARCA'
    dias: list[Dia] = field(default_factory=list)

    @property
    def codigo(self) -> str:
        """'06-0011': la clave de la localidad (el enlace de detalle usa dp y localidad)."""
        return f"{self.dp}-{self.localidad}"


@dataclass
class Pronostico:
    emision: date
    localidades: list[Localidad]
    problemas: list[str] = field(default_factory=list)   # bloques o días que no se entendieron


def _plano(texto: str) -> str:
    """Mayúsculas sin tildes: 'miércoles, 23 de septiembre' -> 'MIERCOLES, 23 DE SEPTIEMBRE'."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def _texto(fragmento: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(fragmento)).strip()


def decodificar(b: bytes) -> str:
    """
    La página viene en UTF-8; si algún día llega en Windows-1252 (latin), se lee igual. Un
    byte dañado en una página UTF-8 no la pasa entera a Windows-1252 (todas las tildes saldrían
    como 'maÃ±ana'): se reemplaza por U+FFFD y pronostico_pais lo anota en `problemas`. Es
    Windows-1252 solo si hay más secuencias inválidas que caracteres UTF-8 válidos fuera de ASCII.
    """
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        t = b.decode("utf-8", "replace")
        malos = t.count("�")
        buenos = sum(1 for c in t if c > "\x7f") - malos
        return t if malos <= buenos else b.decode("cp1252", "replace")


def fecha_emision(t: str) -> date:
    """'martes, 22 de septiembre del 2026' -> date(2026, 9, 22); ValueError si no se entiende."""
    m = re.search(r"(\d{1,2})\s+DE\s+([A-Z]+)\s+DEL?\s+(\d{4})", _plano(_texto(t)))
    mes = MESES.get(m.group(2)) if m else None
    if not mes:
        raise ValueError(f"No se entiende la fecha de emisión del pronóstico: {t!r}")
    return date(int(m.group(3)), mes, int(m.group(1)))   # ValueError si el día no existe


def fecha_dia(t: str, emision: date) -> date | None:
    """
    'miércoles, 23 de septiembre' (sin año) -> date. El año es el de la emisión, o el
    siguiente si la fecha queda más de 30 días antes ('jueves, 1 de enero' en la emisión del
    31-12), o el anterior si queda más de 30 días después ('miércoles, 31 de diciembre' en la
    del 1-1). Se ignora el nombre del día. None si no se entiende.
    """
    m = re.search(r"(\d{1,2})\s+DE\s+([A-Z]+)", _plano(_texto(t)))
    mes = MESES.get(m.group(2)) if m else None
    if not mes:
        return None
    dia = int(m.group(1))
    try:
        f = date(emision.year, mes, dia)
        if f < emision - timedelta(days=30):
            f = date(emision.year + 1, mes, dia)
        elif f > emision + timedelta(days=30):
            f = date(emision.year - 1, mes, dia)
    except ValueError:   # '31 de septiembre'
        return None
    return f


def _temperatura(t: str) -> int | None:
    v = int(t) if t else None
    return v if v is not None and TEMP_MIN <= v <= TEMP_MAX else None


def _dias(bloque: list[tuple[str, ...]], emision: date) -> tuple[list[Dia], list[str], list[str]]:
    """
    Días de un bloque, las fechas que no se entendieron o no corresponden a la emisión y las
    repetidas (la copia del 25-05-2025 traía dos versiones del domingo y del lunes: queda la
    primera).
    """
    dias: list[Dia] = []
    malas: list[str] = []
    repetidas: list[str] = []
    desde, hasta = emision - timedelta(days=DIAS_ANTES), emision + timedelta(days=DIAS_DESPUES)
    for fecha_t, icono, tmax_t, tmin_t, texto in bloque:
        f = fecha_dia(fecha_t, emision)
        if f is None or not desde <= f <= hasta:
            malas.append(_texto(fecha_t))
            continue
        if any(d.fecha == f for d in dias):
            repetidas.append(_texto(fecha_t))
            continue
        tmax, tmin = _temperatura(tmax_t), _temperatura(tmin_t)
        if tmax is not None and tmin is not None and tmin > tmax:   # no se sabe cuál está mal
            tmax = tmin = None
        dias.append(Dia(fecha=f, icono=icono, tmax=tmax, tmin=tmin, texto=_texto(texto)[:MAX_TEXTO]))
    return dias, malas, repetidas


def parse_pagina(pagina: str, hoy: date) -> Pronostico:
    """
    Localidades y días de la página del país (o de un departamento, con &dp=). `hoy` es la
    fecha de Perú. Falla (ValueError) según el docstring del módulo; lo que no se entiende
    de un bloque va a `problemas`.
    """
    m = _EMISION.search(pagina)
    if not m:
        raise ValueError("No se encontró la fecha de emisión en la página de pronóstico de SENAMHI")
    emision = fecha_emision(m.group(1))
    if emision > hoy:
        raise ValueError(f"La emisión del pronóstico ({emision}) es posterior a hoy ({hoy})")

    bloques = _BLOQUE.split(pagina)[1:]
    localidades: list[Localidad] = []
    problemas: list[str] = []
    con_problemas = 0
    vistas: set[str] = set()
    for i, bloque in enumerate(bloques, 1):
        bloque = _FIN_TABLA.split(bloque, 1)[0]
        c = _CABECERA.search(bloque)
        if not c:
            problemas.append(f"bloque {i}: sin código de localidad")
            con_problemas += 1
            continue
        loc = Localidad(dp=c.group(1), localidad=c.group(2), nombre_senamhi=_texto(c.group(3)))
        quien = f"{loc.codigo} {loc.nombre_senamhi}"
        leidos = _DIA.findall(bloque)
        fechas = len(_COL3.findall(bloque))
        if fechas != len(leidos) or not leidos:
            problemas.append(f"{quien}: {fechas} fechas y {len(leidos)} días leídos")
            con_problemas += 1
            continue
        if loc.codigo in vistas:
            problemas.append(f"{quien}: repetida en la página (queda la primera)")
            con_problemas += 1
            continue
        vistas.add(loc.codigo)
        loc.dias, malas, repetidas = _dias(leidos, emision)
        if malas:
            problemas.append(f"{quien}: fechas que no corresponden a la emisión del {emision}: {', '.join(malas)}")
        if repetidas:
            problemas.append(f"{quien}: días repetidos (queda el primero): {', '.join(repetidas)}")
        con_problemas += bool(malas or repetidas)
        if loc.dias:
            localidades.append(loc)

    if not MIN_LOCALIDADES <= len(localidades) <= MAX_LOCALIDADES:
        raise ValueError(f"La página de pronóstico de SENAMHI trae {len(localidades)} localidades legibles "
                         f"(se esperan de {MIN_LOCALIDADES} a {MAX_LOCALIDADES})")
    if con_problemas > MAX_PROBLEMAS * len(bloques):
        raise ValueError(f"La página de pronóstico de SENAMHI cambió: {con_problemas} de {len(bloques)} "
                         f"bloques no se entienden ({'; '.join(problemas[:3])})")
    return Pronostico(emision=emision, localidades=localidades, problemas=problemas)


def pronostico_pais(hoy: date | None = None) -> Pronostico:
    """Pronóstico de todas las localidades del país (una página de ~770 KB)."""
    hoy = hoy or datetime.now(HORA_PERU).date()
    datos = _http.con_reintentos(_http.get_bytes, URL_PAIS, MAX_HTML_BYTES)
    pagina = decodificar(datos)
    pron = parse_pagina(pagina, hoy)
    ilegibles = pagina.count("�")
    if ilegibles:   # va primero: el latido guarda solo los primeros problemas
        pron.problemas.insert(0, f"la página trae {ilegibles} caracteres ilegibles (se reemplazaron por U+FFFD)")
    return pron
