"""
Lectura de un día del pronóstico de SENAMHI por localidad (puro, sin red ni BD).

El texto del pronosticador manda; el ícono de SENAMHI solo suma o pone en duda. SENAMHI usa
los íconos con libertad (el 029 "ventisca" para "viento moderado", el 004 solo nubes con
"tendencia a lluvia", el 010/011 de tormenta con textos que solo dicen "con lluvia"), así
que el ícono nunca afirma por sí solo. Leyenda oficial de íconos
(https://www.senamhi.gob.pe/public/images/icono/): 010 y 037 tormentas aisladas, 011
generalizadas; 006 a 009, 035 y 036 lluvia; 012 a 017 aguanieve, nieve y granizo (017).

clasificar(icono, texto), en orden:
  1. Negación ("sin lluvias", "no se prevén lluvias") -> sin_lluvia.
  2. Texto con tormenta, descargas eléctricas, truenos o relámpagos -> tormenta.
  3. Texto con nieve, o con granizo sin lluvia -> nieve.
  4. Texto con lluvia: con ícono de tormenta -> tormenta posible (por 'icono'); si no, lluvia.
  5. Solo el ícono de lluvia, tormenta o nieve -> lluvia posible (por 'icono').
  6. Si no -> sin_lluvia, con el cielo (por ícono o por texto).
  posible: la palabra queda bajo "tendencia a" (sin CON, ';', '.' ni VARIANDO en medio).
  momento: la primera frase de hora después de la palabra y en la misma cláusula; si no, la
  pegada justo antes. "Durante el día" no cuenta: describe el cielo.

Verificado con la emisión del 22-09-2026 para el 23-09: Cajamarca 7 lluvia, 6 puede llover,
4 sin lluvia; el país 57 / 42 / 4 tormenta posible / 174. clasificar e intensidad son la
referencia verificada de la especificación, portada tal cual; nombre_legible además escribe
'Sta.' (no 'STA.') y 'Yauri-Espinar'.
"""
from __future__ import annotations

import html
import re
import unicodedata


def plano(t: str | None) -> str:
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().upper()


LLUVIA = r"LLUVIAS?|CHUBASCOS?|LLOVIZNAS?|PRECIPITACION(?:ES)?"
NIEVE = r"NEVADAS?|NIEVE|AGUANIEVE"
TORMENTA = r"TORMENTAS?|DESCARGAS?\s+ELECTRICAS?|TRUENOS?|RELAMPAGOS?|ACTIVIDAD\s+ELECTRICA"
RX = {k: re.compile(rf"\b(?:{v})\b") for k, v in
      (("lluvia", LLUVIA), ("nieve", NIEVE), ("tormenta", TORMENTA), ("granizo", "GRANIZO"))}
RX_NEG = re.compile(r"\bSIN\s+(?:LLUVIAS?|PRECIPITACION(?:ES)?|CHUBASCOS?)\b"
                    r"|\bNO\s+SE\s+(?:PREVEN|ESPERAN)\s+(?:LLUVIAS?|PRECIPITACION(?:ES)?)")
RX_TEND = re.compile(r"\bTENDENCIA\s+A\b")
CORTE = re.compile(r"\bCON\b|;|\.|\bVARIANDO\b")
MOMENTO = re.compile(r"EN LAS PRIMERAS HORAS DE LA MANANA|(?:POR|EN) LA MANANA|HACIA EL MEDIODIA|AL MEDIODIA|"
                     r"(?:POR|EN) LA TARDE|AL ATARDECER|(?:POR|EN|HACIA) LA NOCHE|(?:HACIA|EN|DE) LA MADRUGADA")
MOMENTO_TXT = [("PRIMERAS HORAS", "temprano en la mañana"), ("MANANA", "en la mañana"), ("MEDIODIA", "hacia el mediodía"),
               ("ATARDECER", "al atardecer"), ("TARDE", "en la tarde"), ("NOCHE", "en la noche"), ("MADRUGADA", "en la madrugada")]
ICONO_TORMENTA = {"010", "011", "037"}
ICONO_LLUVIA = {"006", "007", "008", "009", "035", "036"}
ICONO_NIEVE = {"012", "013", "014", "015", "016", "017"}          # 017 = granizo
ICONO_CIELO = {"001": "despejado", "031": "despejado", "002": "parcial", "003": "parcial", "032": "parcial",
               "033": "parcial", "004": "nublado", "005": "nublado", "034": "nublado", "018": "neblina", "019": "neblina"}
NOMBRE = r"(?:LLUVIAS?|CHUBASCOS?|LLOVIZNAS?|NIEVE|NEVADAS?|PRECIPITACION(?:ES)?)"


def _momento_txt(frase: str) -> str:
    return next(txt for clave, txt in MOMENTO_TXT if clave in frase)


def _posible(P: str, m: re.Match) -> bool:
    """Bajo 'tendencia a' si entre el último 'TENDENCIA A' previo y la palabra no hay CON, ';', '.' ni VARIANDO."""
    previos = list(RX_TEND.finditer(P, 0, m.start()))
    return bool(previos) and not CORTE.search(P, previos[-1].end(), m.start())


def _momento(P: str, m: re.Match) -> str | None:
    """Primera frase de hora DESPUÉS de la palabra, en la misma cláusula; si no, la pegada justo antes.
    'Durante el día' no cuenta: describe el cielo."""
    fin = CORTE.search(P, m.end())
    d = MOMENTO.search(P, m.end(), fin.start() if fin else len(P))
    if d:
        return _momento_txt(d.group(0))
    antes = P[max(0, m.start() - 45):m.start()]
    a = list(MOMENTO.finditer(antes))
    if a and re.fullmatch(r"\s*(?:CON|Y|,)?\s*(?:TENDENCIA\s+A\s+)?", antes[a[-1].end():]):
        return _momento_txt(a[-1].group(0))
    return None


def intensidad(P: str) -> str | None:
    """'ligera' | 'moderada' | 'fuerte' por el adjetivo pegado al sustantivo ('viento moderado' no cuenta)."""
    adj = [m.group(1) for m in re.finditer(NOMBRE + r"\s+(LIGER\w*|DEBIL\w*|MODERAD\w*|FUERTE\w*|INTENS\w*|TORRENCIAL\w*)", P)]
    if any(a.startswith(("FUERTE", "INTENS", "TORRENCIAL")) for a in adj):
        return "fuerte"
    if any(a.startswith("MODERAD") for a in adj):
        return "moderada"
    if adj or re.search(r"\bLLOVIZNAS?\b", P):
        return "ligera"
    return None


def _cielo(icono: str | None, P: str) -> str | None:
    if icono in ICONO_CIELO:
        return ICONO_CIELO[icono]
    for rx, c in ((r"DESPEJAD", "despejado"), (r"NUBES DISPERSAS|NUBLADO PARCIAL", "parcial"),
                  (r"NUBLADO|CUBIERTO", "nublado"), (r"NEBLINA|NIEBLA", "neblina")):
        if re.search(rx, P):
            return c
    return None


def clasificar(icono: str | None, texto: str | None) -> dict:
    """
    {tipo, posible, por, lluvia_segura, granizo, intensidad, momento, cielo}: las columnas
    derivadas de pronostico_localidad (ver el docstring del módulo).
    """
    P = plano(html.unescape(texto or ""))
    base = {"tipo": "sin_lluvia", "posible": False, "por": "texto", "lluvia_segura": False, "granizo": False,
            "intensidad": None, "momento": None, "cielo": None}
    icono_precip = icono in ICONO_TORMENTA | ICONO_LLUVIA | ICONO_NIEVE
    if RX_NEG.search(P):
        return {**base, "cielo": _cielo(icono, P)}
    h = {k: rx.search(P) for k, rx in RX.items()}
    granizo = bool(h["granizo"]) or icono == "017"
    por = "texto+icono" if icono_precip else "texto"
    if h["tormenta"]:
        m = h["tormenta"]
        return {**base, "tipo": "tormenta", "posible": _posible(P, m), "por": por, "granizo": granizo,
                "lluvia_segura": bool(h["lluvia"]) and not _posible(P, h["lluvia"]),
                "intensidad": intensidad(P), "momento": _momento(P, m)}
    if h["nieve"] or (h["granizo"] and not h["lluvia"]):
        m = h["nieve"] or h["granizo"]
        return {**base, "tipo": "nieve", "posible": _posible(P, m), "por": por, "granizo": granizo,
                "intensidad": intensidad(P), "momento": _momento(P, m)}
    if h["lluvia"]:
        m = h["lluvia"]
        posible = _posible(P, m)
        if icono in ICONO_TORMENTA:   # el ícono dice tormenta; el texto, solo lluvia
            return {**base, "tipo": "tormenta", "posible": True, "por": "icono", "lluvia_segura": not posible,
                    "granizo": granizo, "intensidad": intensidad(P), "momento": _momento(P, m)}
        return {**base, "tipo": "lluvia", "posible": posible, "por": por, "granizo": granizo,
                "intensidad": intensidad(P), "momento": _momento(P, m)}
    if icono_precip:   # el ícono dice lluvia (o tormenta o nieve) y el texto no
        return {**base, "tipo": "lluvia", "posible": True, "por": "icono", "granizo": icono == "017"}
    return {**base, "cielo": _cielo(icono, P)}


PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "E", "EL"}


def _palabra(w: str) -> str:
    """'STA.' -> 'Sta.'; 'YAURI-ESPINAR' -> 'Yauri-Espinar'; las iniciales ('J.C.') quedan tal cual."""
    if w.count(".") > 1:
        return w
    return "-".join(p.capitalize() for p in w.split("-"))


def nombre_legible(nombre_senamhi: str) -> str:
    """'SAN MIGUEL DE PALLAQUES - CAJAMARCA' -> 'San Miguel de Pallaques'; 'LIMA OESTE / CALLAO - LIMA' ->
    'Lima Oeste / Callao'. La primera palabra siempre con mayúscula."""
    nombre = html.unescape(nombre_senamhi).rsplit(" - ", 1)[0].strip()
    out = []
    for i, w in enumerate(nombre.split()):
        out.append(w.lower() if i and w.upper() in PARTICULAS else _palabra(w))
    return " ".join(out)
