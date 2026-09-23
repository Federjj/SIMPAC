"""
Lectura del texto oficial de los avisos de SENAMHI: qué ícono lleva cada aviso y qué dice su
párrafo. backend/ingesta/avisos.py lo guarda en aviso_senamhi (icono, lectura, texto_dia).
Puro: sin red ni BD.

Todo lo que sale de aquí es derivado y el frontend lo rotula "basado en el aviso de SENAMHI",
junto a la cita literal. La regla es no inventar: lo que no se lee con certeza queda en None y
se muestra el texto tal cual.

Ícono (icono_aviso). Ningún campo del WFS dice lluvia o tormenta (cod_even solo repite el tipo
del título); las descargas eléctricas salen solo en el párrafo general, y en el 97% de los
avisos de lluvia (en el 100% de los de la sierra). Regla, sobre los 439 avisos de lluvia,
llovizna y nevada de 2024 a 2026 (245 gota con rayo, 182 gota, 12 copo):
  - 'copo': nevada (el título no dice lluvia ni llovizna).
  - 'gota_rayo': lluvia de UNA región (costa, sierra o selva) en el título, sin otra región en
    el párrafo y con las descargas afirmadas ("estarán acompañadas de descargas eléctricas").
    En un aviso de varias regiones la frase puede valer solo para una: el 376 ("sierra norte y
    costa norte") las dice solo para la sierra, y su parte norte mezcla costa y sierra de
    Piura. Sin una capa de regiones no se sabe a qué parte va el rayo: lleva gota y el popup
    cita la frase.
  - 'gota': todo lo demás, también sin párrafo general (el rayo nunca se inventa) y el aviso
    de lluvia de 24 h (su tabla de "fenómenos asociados" es una plantilla por región).

Montos por día (montos): "El miércoles 23 de setiembre se esperan acumulados de lluvia hasta
los 12 mm/día en Tumbes, cercanos a los 6 mm/día en la costa de Piura y valores entre los 7
mm/día y 15 mm/día en la sierra norte." -> Tumbes hasta 12, Costa de Piura cerca de 6, Sierra
norte de 7 a 15. Todo o nada: si un monto no se entiende o no tiene un lugar claro, el párrafo
entero queda en None y se muestra literal. Sobre los 1027 párrafos por día del corpus se lee el
92% (945), sin ningún lugar mal atribuido.
"""
from __future__ import annotations

import html
import re
import unicodedata
from datetime import date

from backend.ingesta.departamentos import DEPARTAMENTOS

LECTURA_V = 1   # versión del formato de aviso_senamhi.lectura (campo "v")


def limpio(texto: str | None) -> str:
    """Sin entidades HTML y con los espacios juntos."""
    return re.sub(r"\s+", " ", html.unescape(texto or "")).strip()


def plano(texto: str | None) -> str:
    """Mayúsculas ASCII: 'Precipitación' -> 'PRECIPITACION'."""
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper()


def plano1(texto: str) -> str:
    """Como plano(), pero con el MISMO largo que el texto (un carácter por cada uno), para
    recortar el original con los índices de una búsqueda hecha sobre el plano."""
    out = []
    for c in texto:
        b = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode()
        out.append((b[:1] or " ").upper())
    return "".join(out)


# ---------------------------------------------------------------------------------------
# Párrafo general
# ---------------------------------------------------------------------------------------
# Oraciones sobre el texto ORIGINAL (con mayúsculas y minúsculas): "m s. n. m." va en
# minúscula y no parte la oración, porque después del punto no viene una mayúscula.
ORACION = re.compile(r"(?<=[.;])\s+(?=[A-ZÁÉÍÓÚÑ¿])")
REGION = re.compile(r"\b(COSTA|LITORAL|SIERRA|ALTOANDIN\w*|ANDIN\w*|ALTIPLANO|INTERANDIN\w*|SELVA|AMAZONI\w*)\b")
DESC = re.compile(r"DESCARGAS?\s+ELECTRICAS?")
COND = re.compile(r"NO SE DESCARTA|PODRI[AE]|POSIBLE|PROBABLE|EVENTUAL")
FIN_CLAUSULA = re.compile(r"[,;]")
# "Estas precipitaciones estarán acompañadas de descargas..." remite a la oración anterior.
REF = re.compile(r"^(?:ESTAS|ESTOS|DICHAS|DICHOS|ESTE|ESTA|LAS CUALES|LOS CUALES)\b")
# Con las erratas reales "de ligero a moderado" y "de moderad a fuerte".
_I = r"(?:LIGER[OA]|MODERAD[OA]?|MUY FUERTE|FUERTE|EXTREMA)"
RX_INT = re.compile(rf"\bDE\s+{_I}(?:\s+A\s+{_I})?\s+INTENSIDAD\b")
# "por encima de los 2800 m s. n. m.", "sobre los 4 000 m": 2800, 4000.
ALT = r"(?:POR\s+ENCIMA\s+DE|SOBRE|SUPERIORES?\s+A|MAYORES?\s+A)\s+(?:LOS\s+)?(\d{1,2}[ .]?\d{3})\s*M\b"
RX_GRAN = re.compile(r"GRANIZO\s+EN\s+[^.;]*?" + ALT)
RX_NIEVE = re.compile(r"(?:NEVADAS?|NIEVE)\s+EN\s+[^.;]*?" + ALT)
RX_RAF = re.compile(r"RAFAGAS\s+DE\s+VIENTO[^.;]*?(CERCANAS\s+A|SUPERIORES\s+A|MAYORES\s+A|QUE\s+PODRIAN\s+ALCANZAR\s+HASTA|"
                    r"HASTA|ALREDEDOR\s+DE|PROXIMAS\s+A|DE)\s+(?:LOS\s+)?(\d{2,3})\s*KM/H")
FORMA_RAF = {"CERCANAS A": "cercanas a", "PROXIMAS A": "cercanas a", "ALREDEDOR DE": "de alrededor de",
             "SUPERIORES A": "de más de", "MAYORES A": "de más de", "QUE PODRIAN ALCANZAR HASTA": "de hasta",
             "HASTA": "de hasta", "DE": "de"}
MAX_FRASE = 400   # la frase de descargas se cita; más larga se corta en una palabra, con "…"

_NOMBRES_PROPIOS = sorted([*DEPARTAMENTOS.values(), "Callao"], key=len, reverse=True)


def region(palabra: str) -> str:
    """'COSTA' | 'LITORAL' -> 'costa'; 'SELVA' | 'AMAZONIA' -> 'selva'; lo andino -> 'sierra'."""
    if palabra in ("COSTA", "LITORAL"):
        return "costa"
    if palabra.startswith(("SELVA", "AMAZONI")):
        return "selva"
    return "sierra"


def fenomeno(titulo: str) -> str | None:
    """'lluvia' | 'llovizna' | 'nevada' según el título; None si no es de lluvia."""
    t = plano(titulo)
    if re.search(r"NEVADA|NIEVE", t) and not re.search(r"PRECIPITAC|LLUVIA|LLOVIZNA", t):
        return "nevada"
    if "LLOVIZNA" in t and not re.search(r"PRECIPITAC|LLUVIA", t):
        return "llovizna"
    if re.search(r"PRECIPITAC|LLUVIA|GRANIZ", t):
        return "lluvia"
    return None


def en_claro(texto: str) -> str:
    """'LA SIERRA DE MOQUEGUA Y TACNA' -> 'la sierra de Moquegua y Tacna'."""
    t = texto.lower().replace("-", ", ")
    for nombre in _NOMBRES_PROPIOS:
        t = re.sub(rf"\b{re.escape(nombre.lower())}\b", nombre, t)
    return t


def donde(titulo: str) -> str | None:
    """'PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE (ACTUALIZACIÓN DEL AVISO 373)' ->
    'la sierra norte y costa norte'; None si el título no dice dónde."""
    t = re.sub(r"\s*\([^)]*\)", "", titulo).strip()
    m = re.match(r".+?\s+EN\s+(.+)$", t, re.I)
    return en_claro(m.group(1)) if m else None


def _oraciones(texto: str | None) -> list[str]:
    return [o for o in ORACION.split(limpio(texto)) if o.strip()]


def intensidad(texto: str | None) -> str | None:
    """'de ligera a moderada intensidad', de la primera oración del párrafo oficial. Las
    erratas se leen y se devuelven corregidas ('de moderad a fuerte' -> 'de moderada a
    fuerte'): es un rótulo derivado; el texto literal va aparte."""
    oraciones = _oraciones(texto)
    m = RX_INT.search(plano(oraciones[0])) if oraciones else None
    if not m:
        return None
    t = re.sub(r"\s+", " ", m.group(0)).lower()
    return re.sub(r"\bmoderad[ao]?\b", "moderada", re.sub(r"\bligero\b", "ligera", t))


def condicional(oracion: str) -> bool:
    """La oración dice las descargas en condicional ("no se descarta la ocurrencia de descargas").
    Se mira desde el inicio de la oración hasta el fin de la cláusula de la última mención, no
    lo que sigue: "acompañadas de descargas eléctricas y ráfagas de viento, con velocidades que
    podrían alcanzar hasta los 50 km/h" afirma las descargas."""
    P = plano(oracion)
    fin = [m.end() for m in DESC.finditer(P)][-1]
    corte = FIN_CLAUSULA.search(P, fin)
    return bool(COND.search(P, 0, corte.start() if corte else len(P)))


def leer_general(titulo: str, general: str) -> dict:
    """
    Lo que dice el párrafo general: regiones del título (solo lo que va después de " EN ") y
    del párrafo, si es de una sola región, descargas ('si' | 'condicional' | 'no') con su
    primera frase literal, intensidad, granizo y nieve (con la altura, si la dice) y ráfagas.
    """
    ors = _oraciones(general)
    P = plano(limpio(general))
    t = plano(re.sub(r"\([^)]*\)", "", titulo))
    t_donde = t.split(" EN ", 1)[1] if " EN " in t else t
    tr = {region(x) for x in REGION.findall(t_donde)}
    pr = {region(x) for x in REGION.findall(P)}
    # Descargas: 'condicional' solo si TODAS las oraciones que las nombran son condicionales.
    idx = [i for i, o in enumerate(ors) if DESC.search(plano(o))]
    descargas = "no" if not idx else ("condicional" if all(condicional(ors[i]) for i in idx) else "si")
    frase = None
    if idx:
        i = idx[0]
        frase = ors[i]
        if i > 0 and REF.match(plano(ors[i])):
            frase = f"{ors[i - 1]} {frase}"
        if len(frase) > MAX_FRASE:
            frase = frase[:MAX_FRASE].rsplit(" ", 1)[0] + "…"
    gr, ni, rf = RX_GRAN.search(P), RX_NIEVE.search(P), RX_RAF.search(P)

    def alt(m):
        return int(re.sub(r"\D", "", m.group(1))) if m else None

    return {
        "regiones_titulo": sorted(tr), "regiones_parrafo": sorted(pr),
        "una_region": len(tr) == 1 and pr <= tr,
        "descargas": descargas, "frase_descargas": frase,
        "intensidad": intensidad(general),
        "granizo": {"menciona": "GRANIZ" in P, "sobre_m": alt(gr)},
        "nieve": {"menciona": bool(re.search(r"NEVAD|NIEVE", P)), "sobre_m": alt(ni)},
        "rafagas": {"forma": FORMA_RAF[re.sub(r"\s+", " ", rf.group(1))], "kmh": int(rf.group(2))} if rf else None,
    }


def icono_aviso(tipo: str, titulo: str, leido: dict | None) -> str | None:
    """'gota' | 'gota_rayo' | 'copo'; None si el aviso no es de lluvia, llovizna ni nevada.
    `leido`: leer_general() (o lectura()) del párrafo general; None si no se leyó."""
    if tipo == "lluvia24h":
        return "gota"
    f = fenomeno(titulo)
    if f is None:
        return None
    if f == "nevada":
        return "copo"
    if f == "lluvia" and leido and leido.get("una_region") and leido.get("descargas") == "si":
        return "gota_rayo"
    return "gota"


# ---------------------------------------------------------------------------------------
# Párrafo de cada día
# ---------------------------------------------------------------------------------------
_MESES = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7,
          "AGOSTO": 8, "SETIEMBRE": 9, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}
_SEMANA = ("LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO")   # date.weekday()
# "El martes 22 de setiembre...", "Para el viernes 10 de julio,...", "El sábado 28de febrero",
# "El domingo 23 se esperan..." (sin mes: 'SE' no es un mes).
_FECHA_DIA = re.compile(r"^(?:PARA\s+)?EL\s+(?:([A-Z]+)\s*,?\s*)?(\d{1,2})(?:\s*(?:DE\s+)?([A-Z]+))?")


def _fecha_leida(texto: str | None) -> tuple[str | None, int, int | None] | None:
    """(nombre del día, número, mes) con los que empieza el párrafo de un día (nombre y mes
    None si no están); None si no empieza con una fecha."""
    m = _FECHA_DIA.match(plano(limpio(texto)))
    return (m.group(1), int(m.group(2)), _MESES.get(m.group(3) or "")) if m else None


def fecha_texto_dia(texto: str | None, anio: int) -> date | None:
    """Fecha con la que empieza el párrafo de un día (el nombre del día no se mira); None si
    no empieza con una fecha legible (con mes)."""
    f = _fecha_leida(texto)
    if not (f and f[2]):
        return None
    try:
        return date(anio, f[2], f[1])
    except ValueError:
        return None


def es_del_dia(texto: str | None, fecha: date) -> bool:
    """
    El párrafo de un día es el de `fecha` (la del mapa): coincide el número y, además, el mes o
    el nombre del día. SENAMHI a veces se equivoca en el mes (el 377 de 2024, del 14 al 16 de
    diciembre, dice "El sábado 14 de noviembre"), pero no en el día de la semana; "El martes 22"
    en el mapa del jueves 24 no vale. Sin mes ("El domingo 23 se esperan...") basta el número.
    Un párrafo que no empieza con una fecha no se puede comprobar: vale.
    """
    f = _fecha_leida(texto)
    if f is None:
        return True
    semana, dia, mes = f
    if dia != fecha.day:
        return False
    return mes is None or mes == fecha.month or semana == _SEMANA[fecha.weekday()]


N = r"\d+(?:[.,]\d+)?"
U = r"(?:M{2,3}\s*/\s*DIA|MM|CM)\b"
CUAL = (r"ENTRE|DE\s+HASTA|HASTA|CERCAN[OA]S?\s+A|ALREDEDOR(?:\s+DE)?|PROXIM[OA]S?\s+A|EN\s+TORNO\s+A|"
        r"APROXIMADAMENTE(?:\s+DE)?|POR\s+ENCIMA\s+DE|SOBRE|SUPERIORES?\s+A|MAYORES?\s+A|DE")
MONTO = re.compile(rf"(?:(?P<cual>{CUAL})\s+)?(?:(?:LOS|LAS)\s+)?(?P<a>{N})\s*(?:{U})?"
                   rf"(?:\s+(?:Y|A)\s+(?:LOS\s+)?(?P<b>{N}))?\s*(?P<u>{U})")
# Todos los números del texto, salvo los de la fecha con que empieza ("El domingo 11 de enero
# del 2026"), tienen que quedar leídos; si no, el párrafo va literal. No basta con los que
# llevan unidad: en "valores de 20, 30 y 40 mm/día en la selva norte, centro y sur" el 20 va
# sin unidad y la selva norte no es "30 a 40".
NUMS = re.compile(N)
_ANIO = re.compile(r"\s*,?\s*(?:DEL?\s+)?\d{4}\b")
# Cortes entre tramos: coma, punto y coma, fin de oración, "mientras que", y " y " antes de
# otro monto o lugar ("y cercanos a", "y próximos a": CERCAN, PROXIM, SUPERIOR y MAYOR son
# comienzos de palabra). Nunca entre dígitos ("0.5 mm" y "0,5 mm" no se cortan).
CORTE = re.compile(r",(?!\d)|;|\.(?=\s|$)|\bMIENTRAS\s+QUE\b|\s+Y\s+(?=(?:(?:EN|PARA|VALORES|REGISTROS|ACUMULADOS|HASTA|"
                   r"ENTRE|ALREDEDOR|SOBRE|POR\s+ENCIMA|DE\s+(?:ALREDEDOR|HASTA|ENTRE|LOS))\b|CERCAN|PROXIM|SUPERIOR|MAYOR))")
# "en promedio", "en horas de la tarde", "en su mayoría" no dicen dónde.
_NO_LUGAR = r"PROMEDIO|GENERAL|SU\s+MAYORIA|HORAS|LA\s+(?:TARDE|NOCHE|MANANA|MADRUGADA)"
LUGAR = re.compile(rf"\b(?:EN|PARA)\s+(?!(?:TORNO|FORMA|{_NO_LUGAR})\b)")
FIN_LUGAR = re.compile(r"\s+(?:SE\s|VALORES\b|ACUMULADOS\b|REGISTROS\b|DE\s+FORMA\b|ALREDEDOR\b|CERCAN|HASTA\b|ENTRE\b|"
                       r"PROXIM|SOBRE\b)|$")
# Un "lugar" con esto no es un lugar: el tramo se leyó mal.
MALO = re.compile(rf"\d|\bMM\b|\bCM\b|\bCOMO\b|\b(?:LUNES|MARTES|MIERCOLES|JUEVES|VIERNES|SABADO|DOMINGO|{_NO_LUGAR})\b")
MAX_LUGAR = 60


def _forma(cual: str | None, b: float | None) -> str | None:
    """'rango' | 'hasta' | 'cerca' | 'mas_de'; None si no se sabe ("de 22 mm" suelto)."""
    if b is not None:
        return "rango"
    c = re.sub(r"\s+", " ", cual or "")
    if c in ("HASTA", "DE HASTA"):
        return "hasta"
    if c.startswith(("SOBRE", "POR ENCIMA", "SUPERIOR", "MAYOR")):
        return "mas_de"
    if c.startswith(("CERCAN", "ALREDEDOR", "PROXIM", "EN TORNO", "APROX")):
        return "cerca"
    return None


def _numero(x: str) -> int | float:
    """'12' -> 12, '0.5' o '0,5' -> 0.5."""
    v = float(x.replace(",", "."))
    return int(v) if v.is_integer() else v


def montos(texto: str | None) -> list[dict] | None:
    """
    [{lugar, desde, hasta, forma, unidad}] del párrafo de un día, con forma 'rango' (desde a
    hasta), 'hasta', 'cerca' o 'mas_de' (desde = None) y unidad 'mm' (mm/día) o 'cm' (nieve).
    None si el párrafo no trae montos o si alguno no se lee con certeza (todo o nada).
    """
    t = limpio(texto)
    P = plano1(t)
    f = _FECHA_DIA.match(P)
    desde = f.end() if f else 0
    anio = _ANIO.match(P, desde)
    esperados = len(NUMS.findall(P, anio.end() if anio else desde))
    if not esperados:
        return None
    tramos = []
    ini = 0
    for c in CORTE.finditer(P):
        tramos.append((ini, c.start()))
        ini = c.end()
    tramos.append((ini, len(P)))
    items = []
    usados = 0
    for a0, a1 in tramos:
        tramo = P[a0:a1]
        ms = list(MONTO.finditer(tramo))
        if not ms:
            continue
        if len(ms) > 1:
            return None
        m = ms[0]
        b = _numero(m["b"]) if m["b"] else None
        forma = _forma(m["cual"], b)
        if forma is None or (b is not None and _numero(m["a"]) > b):   # "entre 18 y 5 mm": mal leído
            return None
        # El lugar va después del monto ("hasta 12 mm/día en Tumbes") o, si no, antes, en el
        # mismo tramo ("En la costa de Piura se prevén valores cercanos a 6 mm/día").
        despues = LUGAR.search(tramo, m.end())
        antes = list(LUGAR.finditer(tramo, 0, m.start()))
        if despues:
            ini = despues.end()
            fin = FIN_LUGAR.search(tramo, ini).start()
        elif antes:
            ini = antes[-1].end()
            fin = min(FIN_LUGAR.search(tramo, ini).start(), m.start())
        else:
            return None
        lugar = t[a0 + ini:a0 + fin].strip(" ,.;")
        lugar = re.sub(r"^(?:la|el|los|las)\s+", "", lugar)   # solo en minúscula: "La Libertad" queda
        if not lugar or len(lugar) > MAX_LUGAR or MALO.search(plano1(lugar)):
            return None
        usados += 1 + (1 if b is not None else 0)
        items.append({"lugar": lugar[0].upper() + lugar[1:],
                      "desde": _numero(m["a"]) if b is not None else None,
                      "hasta": b if b is not None else _numero(m["a"]),
                      "forma": forma, "unidad": "cm" if m["u"].startswith("CM") else "mm"})
    return items if items and usados == esperados else None


# ---------------------------------------------------------------------------------------
# Lectura completa (aviso_senamhi.lectura)
# ---------------------------------------------------------------------------------------
def lectura(tipo: str, titulo: str, general: str | None, texto_dia: str | None) -> dict | None:
    """
    Lo que se guarda en aviso_senamhi.lectura. None si el aviso no es de lluvia, llovizna ni
    nevada, o si es de lluvia pero no se leyó su párrafo general (la tarea lo vuelve a
    intentar en la próxima corrida). El aviso de 24 h no tiene párrafo propio.
    """
    if tipo == "lluvia24h":
        return {"v": LECTURA_V, "fenomeno": "lluvia"}
    f = fenomeno(titulo)
    if f is None or not general:
        return None
    return {"v": LECTURA_V, "fenomeno": f, "donde": donde(titulo), **leer_general(titulo, general),
            "montos": montos(texto_dia)}
