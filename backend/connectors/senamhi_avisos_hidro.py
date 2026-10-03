"""
Conector SENAMHI — avisos hidrológicos (crecidas y descensos de ríos, por estación).

Producto (verificado en vivo el 03-10-2026; SENAMHI no lo documenta):
  - Lista LISTA_URL: una tabla HTML con los avisos de los últimos 12 meses de todo el país
    (1680 filas, ~700 KB): título literal, N.º ("1624 (vigente)" si sigue vigente; las demás
    sin etiqueta), inicio y fin (fechas ISO), duración en horas y nivel
    (<span class="dos|tres|cuatro">AMARILLO|NARANJA|ROJO</span>; 3 filas sin nivel). El
    enlace de cada fila lleva ca (id del aviso) y ce (código de la estación: '220213' es la
    estación MASHCÓN, en el mismo punto que la de ANA).
  - Detalle DETALLE_URL (?ca=..&ce=..): repite la lista entera y agrega el aviso (bloque
    id="nav-avisodet"): número y nivel, emisión, inicio y fin con hora ("Viernes, 13 de Marzo
    de 2026 - 06:00 hrs", hora de Perú), el párrafo oficial ("registró un CAUDAL de 30.17
    m3/s ... Las potenciales áreas de afectación serían los centros poblados de ..."), una
    tabla con el umbral rojo de la estación y la leyenda de los niveles.

Trampas verificadas:
  - La leyenda del detalle trae el texto del nivel ROJO (y del naranja y el amarillo) sea cual
    sea el nivel del aviso: por eso se guarda solo la del rojo (significado_rojo). En un aviso
    de descenso la leyenda es la de descenso (encallamiento de naves, no desborde).
  - Los avisos de la selva van por NIVEL en m.s.n.m (Napo, 70483: umbral 85.81); los de la
    sierra, por CAUDAL en m3/s (Mashcón, 67552: umbral 18).
  - "SITUACIÓN ACTUAL ..." también es un aviso con nivel; "DESCENSO ..." es de estiaje
    (sentido 'descenso'): no enciende la zona de un río.
  - Cada detalle pesa lo mismo que la lista (~700 KB): solo se piden los avisos vigentes de
    las estaciones vigiladas, en serie y con PAUSA_S (backend/ingesta/rios.py).
  - La presentación de la página dice "indicando las áreas que podrían verse afectadas": el
    detalle se lee solo desde el bloque del aviso; sin ese bloque, todo queda en None.
  - La vigencia va en dos señales de la lista: el texto "(vigente)" y class="vigente" en las
    celdas. Se toma cualquiera de las dos y se marca `ambiguo` si no coinciden (la tarea no
    apaga avisos con una página así). "(no vigente)" no cuenta.
  - Ante cambios del HTML, mejor None que un dato equivocado: cada fecha se lee solo hasta la
    etiqueta siguiente (una fecha sin hora no toma la del campo de al lado), se aceptan coma
    decimal y a. m./p. m., y las áreas llegan hasta "Se recomienda" (no hasta el primer punto,
    que puede ser el de "C.P."). Algunas filas de la lista no traen nivel: el detalle lo da
    en su encabezado ("Aviso N°1169 ROJO").
  - La página es UTF-8.

Licencia: la de SENAMHI (leyenda literal ATRIBUCION de senamhi_avisos.py en todo soporte).
"""
from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from datetime import date, datetime

from . import _http
from .senamhi import HORA_PERU

WEB = "https://www.senamhi.gob.pe/"
LISTA_URL = f"{WEB}?p=avisos-hidrologicos"
DETALLE_URL = f"{WEB}?p=avisos-detalle-hidrologicos&ca={{ca}}&ce={{ce}}"
MAX_HTML_BYTES = 10 * 1024 * 1024    # la lista y cada detalle pesan ~700 KB
PAUSA_S = 1.0                        # entre pedidos a la web de SENAMHI

NIVEL = {"dos": 2, "tres": 3, "cuatro": 4}
NIVEL_TXT = {"AMARILLO": 2, "NARANJA": 3, "ROJO": 4}
MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                      "septiembre", "octubre", "noviembre", "diciembre"], start=1)}
MESES["setiembre"] = 9


@dataclass(frozen=True)
class FilaAviso:
    """Una fila de la lista de avisos hidrológicos."""
    ca: int              # id del aviso en la web
    ce: str              # código de la estación ('220213' = Mashcón)
    numero: int
    titulo: str
    vigente: bool        # "(vigente)" en la columna N.º o celdas con class="vigente" (_vigencia)
    inicio_dia: date
    fin_dia: date
    duracion_h: int | None
    nivel: int | None    # 2 amarillo, 3 naranja, 4 rojo; None si la fila no trae nivel
    sentido: str         # 'descenso' si el título dice DESCENSO; si no, 'crecida'
    ambiguo: bool = False  # el texto y la marca de la fila no coinciden sobre si está vigente

    @property
    def url(self) -> str:
        return DETALLE_URL.format(ca=self.ca, ce=self.ce)


def pausa() -> None:
    """Espera entre pedidos a la web de SENAMHI (las pruebas la reemplazan)."""
    time.sleep(PAUSA_S)


def _texto(fragmento: str) -> str:
    """Texto plano de un fragmento HTML: sin etiquetas, con entidades y espacios normalizados."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento))).strip()


def _bajar_texto(url: str) -> str:
    return _http.get_bytes(url, MAX_HTML_BYTES).decode("utf-8", "replace")


# ---------------------------------------------------------------------------------------
# Lista
# ---------------------------------------------------------------------------------------
_FILA = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
_CELDA = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S | re.I)
_ENLACE = re.compile(r"avisos-detalle-hidrologicos&(?:amp;)?ca=(\d+)&(?:amp;)?ce=([0-9A-Za-z]+)")
_SPAN = re.compile(r'<span class="(dos|tres|cuatro)">', re.I)
# Dos señales de vigencia en la lista: el texto "1624 (vigente)" de la columna N.º y la clase
# class="vigente" que SENAMHI pone en las celdas de esas filas (las demás no llevan clase).
_TXT_VIGENTE = re.compile(r"(?<!no )\bvigente\b", re.I)        # "(no vigente)" no cuenta
_CLASE_VIGENTE = re.compile(r"""<td\b[^>]*\bclass\s*=\s*["'][^"']*(?<![\w-])vigente(?![\w-])""", re.I)


def _vigencia(nro: str, fila: str) -> tuple[bool, bool]:
    """
    (vigente, ambiguo). Vigente si lo dice el texto o la marca de la fila: si SENAMHI quita una
    de las dos, el aviso no se apaga. ambiguo si no coinciden (la tarea no apaga ninguno).
    """
    txt, clase = bool(_TXT_VIGENTE.search(nro)), bool(_CLASE_VIGENTE.search(fila))
    return txt or clase, txt != clase


def parsear_lista(pagina: str) -> list[FilaAviso]:
    """Filas de la tabla de avisos. Una fila que no se entiende se salta (no rompe el resto)."""
    out: dict[int, FilaAviso] = {}
    for fila in _FILA.findall(pagina):
        celdas = _CELDA.findall(fila)
        m = _ENLACE.search(fila)
        if len(celdas) < 6 or not m:
            continue
        titulo, nro, ini, fin, dur = (_texto(c) for c in celdas[:5])
        num = re.match(r"(\d+)", nro)
        try:
            ini_d, fin_d = date.fromisoformat(ini), date.fromisoformat(fin)
        except ValueError:
            continue
        if not num or not titulo:
            continue
        s = _SPAN.search(celdas[5])
        nivel = NIVEL[s.group(1).lower()] if s else NIVEL_TXT.get(_texto(celdas[5]).upper())
        sentido = "descenso" if "DESCENSO" in titulo.upper() else "crecida"
        ca = int(m.group(1))
        vigente, ambiguo = _vigencia(nro, fila)
        out[ca] = FilaAviso(ca=ca, ce=m.group(2), numero=int(num.group(1)), titulo=titulo,
                            vigente=vigente, inicio_dia=ini_d, fin_dia=fin_d,
                            duracion_h=int(dur) if dur.isdigit() else None, nivel=nivel, sentido=sentido,
                            ambiguo=ambiguo)
    return list(out.values())


def bajar_lista() -> str:
    """La página de la lista (una petición de ~700 KB)."""
    return _http.con_reintentos(_bajar_texto, LISTA_URL)


# ---------------------------------------------------------------------------------------
# Detalle
# ---------------------------------------------------------------------------------------
_FECHA = re.compile(r"(\d{1,2}) de (\w+) del? (\d{4})\s*(?:-|a las)\s*(\d{1,2}):(\d{2})"
                    r"(?:\s*(?:hrs?|horas)\.?)?(?:\s*([ap])\.?\s?m\b\.?)?", re.I)
# Etiquetas del encabezado del aviso: el valor de un campo llega hasta la siguiente (una fecha
# sin hora no toma la hora del campo de al lado).
_ETIQUETA = re.compile(r"Fecha de|Plazo", re.I)
# "Las potenciales áreas de afectación serían los centros poblados de ..." hasta la frase que le
# sigue en el párrafo oficial ("Se recomienda ..."), no hasta el primer punto ("C.P. ...").
_AREAS = re.compile(r"(Las (?:potenciales )?[áa]reas\b.{0,80}?(?:afectaci[oó]n|afectadas).{0,800}?)\s*"
                    r"(?=Se recomienda|El SENAMHI|Cuerpo de Agua)", re.I | re.S)


def _fecha(texto: str | None) -> datetime | None:
    """
    'Viernes, 13 de Marzo de 2026 - 06:00 hrs' -> 2026-03-13 06:00 en hora de Perú. Acepta
    'del 2026' y a. m./p. m. ('4:00 p.m.' -> 16:00); una hora imposible da None.
    """
    m = _FECHA.search(texto or "")
    if not m or m.group(2).lower() not in MESES:
        return None
    d, mes, a, h, mi, ap = m.groups()
    h = int(h)
    if ap:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ap.lower() == "p" else 0)
    try:
        return datetime(int(a), MESES[mes.lower()], int(d), h, int(mi), tzinfo=HORA_PERU)
    except ValueError:   # 31 de junio, 25:00...
        return None


def _numero(texto: str) -> float | None:
    """
    '30.17' -> 30.17; '1,234.5' -> 1234.5 (coma de miles, como escribe SENAMHI); '30,17' -> 30.17
    (una sola coma y ningún punto: coma decimal). Lo demás, None.
    """
    s = texto.strip()
    if not re.fullmatch(r"\d[\d.,]*", s):
        return None
    s = s.replace(",", ".") if s.count(",") == 1 and "." not in s else s.replace(",", "")
    try:
        return float(s)
    except ValueError:   # '1.2.3'
        return None


def parsear_detalle(pagina: str) -> dict:
    """
    Datos del aviso en su página de detalle: emision, inicio, fin (hora de Perú), valor y
    unidad (lo que registró la estación), areas (literal), umbral_rojo, significado_rojo
    (literal de la leyenda del nivel rojo), numero (N.º del aviso, para comprobar que es el
    pedido) y nivel (2 a 4, del encabezado "Aviso N°1169 ROJO": la lista a veces no lo trae).
    Las claves que no se encuentran quedan en None.
    """
    # Solo el bloque del aviso: la página repite la lista y su presentación ("indicando las áreas
    # que podrían verse afectadas y el nivel de peligrosidad") se confundiría con las áreas.
    i = pagina.find('id="nav-avisodet"')
    cuerpo = pagina[i:] if i >= 0 else ""
    t = _texto(cuerpo)

    def campo(etiqueta: str) -> str | None:
        m = re.search(etiqueta + r"\s*:?\s*", t, re.I)
        if not m:
            return None
        resto = t[m.end():m.end() + 200]
        corte = _ETIQUETA.search(resto)
        return resto[:corte.start()] if corte else resto

    numero = re.search(r"Aviso N\s*[°º]\s*0*(\d+)(?:\s+(AMARILLO|NARANJA|ROJO)\b)?", t, re.I)
    valor = re.search(r"registr[oó] un (CAUDAL|NIVEL) de ([\d.,]+)\s*(m3/s|m\.?s\.?n\.?m\.?|m)\b", t, re.I)
    areas = _AREAS.search(t)
    # tabla "Cuerpo de Agua | Estación | Distrito | Caudal (o Nivel) a las HH:MM | Umbral Rojo": la 5.ª celda
    j = cuerpo.find("Umbral Rojo")
    celdas = re.findall(r'<td class="align-middle">(.*?)</td>', cuerpo[j:j + 3000], re.S) if j >= 0 else []
    umbral = _texto(celdas[4]) if len(celdas) >= 5 else ""
    # leyenda del nivel rojo (la página trae la del rojo sea cual sea el nivel del aviso)
    rojo = re.search(r'<span class="leyendaNivel\d">\s*ROJO\s*</span>.*?<td class="text-justify">(.*?)</td>',
                     cuerpo, re.S)
    return {
        "numero": int(numero.group(1)) if numero else None,
        "nivel": NIVEL_TXT[numero.group(2).upper()] if numero and numero.group(2) else None,
        "emision": _fecha(campo(r"Fecha de emisi[oó]n")),
        "inicio": _fecha(campo(r"Fecha de inicio")),
        "fin": _fecha(campo(r"Fecha de fin(?:al)?")),
        "valor": _numero(valor.group(2)) if valor else None,
        "unidad": valor.group(3) if valor else None,
        "areas": areas.group(1).strip() if areas else None,
        "umbral_rojo": _numero(umbral) if umbral else None,
        "significado_rojo": (_texto(rojo.group(1)) or None) if rojo else None,
    }


def bajar_detalle(ca: int, ce: str) -> str:
    """La página de detalle de un aviso (una petición de ~700 KB: repite la lista)."""
    if not re.fullmatch(r"[0-9A-Za-z]+", str(ce)):
        raise ValueError(f"Código de estación inesperado: {ce!r}")
    return _http.con_reintentos(_bajar_texto, DETALLE_URL.format(ca=int(ca), ce=ce))
