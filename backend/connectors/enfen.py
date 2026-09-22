"""
Conector ENFEN — Comunicado Oficial (estado del Sistema de Alerta ante El Niño y
La Niña costeros) e Informe Técnico (valores del ICEN).

La Comisión Multisectorial ENFEN publica cada ~2 semanas un "Comunicado Oficial
ENFEN N° NN-AAAA" en PDF (y, si hay cambios bruscos, un "Comunicado Extraordinario"
entre medio). No hay API: se descubre el último comunicado en listados web, se baja
el PDF y se lee su texto con pypdf.

Operaciones públicas:
  1. ultimo_comunicado()        -> descubre el comunicado más reciente, lo baja y lo parsea.
  2. parsear_texto(texto, url)  -> texto ya extraído -> ComunicadoENFEN (sin red ni pypdf).
  3. informe_tecnico_icen(leido, fallido) -> ConsultaInforme: ICEN y ICENtmp del último
     Informe Técnico, solo si es posterior al ya leído (no se vuelve a bajar: 12-17 MB,
     ~88 páginas) y no se descartó hace menos de 24 h.
  4. parsear_informe(paginas, url) -> texto de las páginas -> InformeICEN (sin red ni pypdf).

Descubrimiento (en este orden; si una fuente falla se pasa a la siguiente):
  a) gob.pe, compendio "Comunicados ENFEN" de SENAMHI. Cada tarjeta trae la fecha de
     publicación y el título con el número ("Comunicado Oficial ENFEN N°16 - 2026");
     la ficha del comunicado enlaza el PDF en cdn.www.gob.pe.
       https://www.gob.pe/institucion/senamhi/colecciones/1308-comunicados-enfen
  b) SENAMHI, página "Fenómeno El Niño", bloque "ENFEN - Comunicado Oficial" (enlaces
     al PDF con la fecha como texto, sin número).
       https://www.senamhi.gob.pe/?p=fenomeno-el-nino
  c) Web del ENFEN (WordPress + WP Download Manager): enlaces
     /download/comunicado-oficial-enfen-n-NN-AAAA/?wpdmdl=ID
       https://enfen.imarpe.gob.pe/comunicados/
     Va última porque su DNS no resolvía desde la red local ni desde Docker el
     22-09-2026 (con el DNS 8.8.8.8 sí: 45.232.105.211, y el sitio responde bien).
  Si el comunicado hallado ya pasó la fecha anunciada del próximo (más 2 días de
  margen), se consultan también las demás fuentes y se queda el más nuevo.

Formato de los PDF (revisados el 22-09-2026 los comunicados 2020-2026):
  - Encabezado "COMUNICADO OFICIAL ENFEN N° 16-2026" (también "N°05-2025", "N°2-2026",
    "COMUNICADO EXTRAORDINARIO ENFEN N° 01-2025") y debajo la fecha de emisión:
    "14 de setiembre 2026", "16 de abril de 2025", "Callao, 19 de octubre de 2020".
  - "Estado del sistema de alerta: Alerta de El Niño Costero1" (el 1 pegado es la
    llamada de una nota al pie).
  - "RESUMEN EJECUTIVO" (desde 2024) y, al final, la fecha del próximo comunicado con
    redacción variable: "El próximo Comunicado Oficial se emitirá el lunes 28 de
    septiembre del 2026", "La emisión del próximo Comunicado Oficial ordinario será el
    viernes 16 de mayo de 2025", "Próxima actualización del Comunicado: 13 de abril de 2022".
  - Los comunicados 2020-2026 NO traen valores numéricos del ICEN (solo umbrales de las
    notas técnicas). Los valores salen en la Tabla 3 del Informe Técnico ENFEN
    ("Jul-26 3.38 Cálida Fuerte ... Mes ICENtmp ... Ago-26 3.73 Cálida Extraordinaria").
    parsear_texto reconoce ese formato de tabla si aparece; si no, icen = [] e
    icen_tmp = None.

Informe Técnico ENFEN (sale con cada comunicado; va meses por delante del ICEN.txt del IGP):
  - Descubrimiento: SENAMHI ?p=fenomeno-el-nino, bloque "Informe Técnico ENFEN" (no el
    "Informe Técnico SENAMHI - ENFEN"), y gob.pe, compendio "Informe Técnico del ENFEN":
      https://www.gob.pe/institucion/senamhi/colecciones/23315-informe-tecnico-del-enfen
    Se consultan las dos y vale la publicación más reciente; el mismo informe en ambas
    (mismo PDF, fechas a <= 4 días) cuenta como uno, para no bajarlo dos veces.
  - Identidad: cada fuente sirve el PDF con otra URL, así que el informe leído se recuerda
    por URL y por fecha de publicación (ReferenciaInforme, en el latido de la tarea). No se
    baja un candidato con la misma URL ni con fecha <= la del leído (+4 días de margen):
    ni el mismo informe desde la otra fuente ni uno más viejo de un listado atrasado.
  - Fallas: las de red se reintentan en cada corrida. Un informe que se bajó y no sirve
    (no es PDF en ninguna copia, pypdf no lo lee, sin tabla, meses fuera de rango, excede
    el tope) lanza InformeDescartado y no se vuelve a bajar antes de 24 h.
  - Lectura: portada "AÑO 12 N° 16 / INFORME TÉCNICO ENFEN / 11 SEPTIEMBRE DEL 2026" y la
    Tabla 3 en la pág. 26-32. Se extrae página por página y se para en la tabla (IT 16-2026:
    30 de 88 páginas, 1.3 s en vez de 3 s). Probado el 22-09-2026 con los IT N° 02 a 16 de
    2026 y tres de 2025. El ICEN más reciente debe ser del mes del informe o de hasta 6
    meses antes; un ICENtmp incoherente se descarta con aviso (errata real en el IT 03-2026).

pypdf se importa dentro de las funciones que leen el PDF: importar este módulo no exige
dependencias extra (las pruebas corren solo con la librería estándar). Sus errores (y
cualquiera al extraer una página) se convierten en ValueError('PDF ilegible: ...'): el
archivo se bajó bien y no se entiende, no es una falla de red.
"""
from __future__ import annotations

import html
import io
import logging
import re
import time
import unicodedata
import urllib.parse
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone

from . import _http

log = logging.getLogger(__name__)

GOBPE_COLECCION = "https://www.gob.pe/institucion/senamhi/colecciones/1308-comunicados-enfen"
GOBPE_INFORMES = "https://www.gob.pe/institucion/senamhi/colecciones/23315-informe-tecnico-del-enfen"
SENAMHI_NINO = "https://www.senamhi.gob.pe/?p=fenomeno-el-nino"
ENFEN_COMUNICADOS = "https://enfen.imarpe.gob.pe/comunicados/"

# Solo se bajan PDF por HTTPS y de estos hosts.
_HOSTS_PDF = frozenset({"cdn.www.gob.pe", "www.senamhi.gob.pe", "enfen.imarpe.gob.pe"})

MAX_PDF_BYTES = 20 * 1024 * 1024    # un comunicado pesa 0.4-1 MB
MAX_PAGINAS = 12                     # y tiene 2-6 páginas
MARGEN_VENCIDO = timedelta(days=2)   # atraso tolerado respecto de la fecha anunciada
# Si ninguna fuente trae uno más nuevo, el hallado se acepta solo hasta este atraso: más
# allá, algo anda mal (p. ej. un listado que cambió de orden y devuelve uno de 2020).
MAX_ATRASO = timedelta(days=21)          # respecto del "próximo" anunciado
MAX_ANTIGUEDAD_SIN_PROXIMO = timedelta(days=45)

# Informe Técnico ENFEN: 11.7-17.2 MB y ~88 páginas en 2026 (N° 02 a 16).
MAX_INFORME_BYTES = 40 * 1024 * 1024
MAX_MESES_ICEN = 6                   # el ICEN más reciente no puede ser más viejo que esto
# El mismo informe aparece en SENAMHI y en gob.pe, a veces con días de diferencia; entre
# dos informes pasan 11 días o más.
MISMO_INFORME = timedelta(days=4)
# Un informe que se bajó y no sirvió no se vuelve a bajar antes de esto (las fallas de red
# sí se reintentan en cada corrida).
ESPERA_FALLIDO = timedelta(hours=24)
_MAX_ERROR = 300   # caracteres del motivo que se guardan en el latido

# Las fechas de los comunicados son hora local de Perú: UTC-5 fijo.
HORA_PERU = timezone(timedelta(hours=-5), "America/Lima")

# Valores posibles de ComunicadoENFEN.estado (Nota Técnica ENFEN 01-2026). Un estado
# fuera de esta lista hace fallar parsear_texto con ValueError: mejor un error visible
# que publicar un estado mal leído.
ESTADOS = (
    "No activo",
    "Vigilancia de El Niño Costero",
    "Alerta de El Niño Costero",
    "Vigilancia de La Niña Costera",
    "Alerta de La Niña Costera",
)


@dataclass
class ComunicadoENFEN:
    numero: int
    anio: int
    fecha: date                  # emisión (la que figura en el PDF)
    estado: str                  # uno de ESTADOS
    proximo: date | None         # fecha anunciada del próximo comunicado
    url: str                     # del PDF
    resumen: str | None          # 1 a 3 frases oficiales, recortadas, sin inventar
    icen: list[tuple[str, float, str]] = field(default_factory=list)   # [("AAAA-MM", valor, categoría)]
    icen_tmp: tuple[str, float, str] | None = None                     # estimado temporal
    extraordinario: bool = False  # "Comunicado Extraordinario" (comparte numeración con los oficiales)
    avisos: list[str] = field(default_factory=list)   # problemas de descubrimiento (no se guarda)


@dataclass
class InformeICEN:
    """ICEN de la Tabla 3 del Informe Técnico ENFEN."""
    url: str                     # del PDF
    numero: int | None           # "AÑO 12 N° 16" de la portada
    fecha: date | None           # la del informe en la portada (no la de publicación)
    icen: list[tuple[str, float, str]]            # [("AAAA-MM", valor, categoría)], ordenada
    icen_tmp: tuple[str, float, str] | None       # estimado temporal del mes siguiente
    avisos: list[str] = field(default_factory=list)   # p. ej. ICENtmp descartado (no se guarda)


def _fecha_json(valor, tipo=date):
    """date/datetime de un texto ISO del latido; None si falta o no se entiende."""
    if not isinstance(valor, str):
        return None
    try:
        return tipo.fromisoformat(valor)
    except ValueError:
        return None


@dataclass
class ReferenciaInforme:
    """
    Un Informe Técnico ya visto, tal como se guarda en el latido 'enfen': el último leído o
    el último descartado. Cada fuente sirve el PDF con otra URL, así que también lo
    identifica `publicado`, la fecha del listado (SENAMHI o gob.pe).
    """
    url: str
    publicado: date | None = None
    numero: int | None = None      # de la portada (el leído)
    fecha: date | None = None      # de la portada (el leído)
    ts: datetime | None = None     # cuándo se descartó (el fallido), con zona horaria
    error: str | None = None       # por qué se descartó (el fallido)
    alias: list[str] = field(default_factory=list)   # otras URL del MISMO informe (misma portada)

    def a_json(self) -> dict:
        datos = {
            "url": self.url,
            "publicado": self.publicado.isoformat() if self.publicado else None,
            "numero": self.numero,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "ts": self.ts.isoformat(timespec="seconds") if self.ts else None,
            "error": self.error,
            "alias": self.alias or None,
        }
        return {k: v for k, v in datos.items() if v is not None}

    @classmethod
    def de_json(cls, datos) -> ReferenciaInforme | None:
        """
        Inverso de a_json. Acepta el formato anterior del latido (solo la URL, texto) y
        tolera datos dañados: lo que no se entiende queda en None.
        """
        if isinstance(datos, str):
            datos = {"url": datos}
        if not isinstance(datos, dict) or not isinstance(datos.get("url"), str) or not datos["url"]:
            return None
        ts = _fecha_json(datos.get("ts"), datetime)
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        numero = datos.get("numero")
        error = datos.get("error")
        alias = datos.get("alias")
        return cls(
            url=datos["url"],
            publicado=_fecha_json(datos.get("publicado")),
            numero=numero if isinstance(numero, int) and not isinstance(numero, bool) else None,
            fecha=_fecha_json(datos.get("fecha")),
            ts=ts,
            error=error if isinstance(error, str) else None,
            alias=[a for a in alias if isinstance(a, str) and a] if isinstance(alias, list) else [],
        )


@dataclass
class ConsultaInforme:
    """Resultado de informe_tecnico_icen() cuando no hubo falla."""
    informe: InformeICEN | None           # None: no hay uno posterior al leído, o está en espera
    leido: ReferenciaInforme | None       # el último leído: el nuevo, o el anterior (con su
                                          # fecha de publicación si le faltaba)
    en_espera: bool = False               # el informe vigente se descartó hace < ESPERA_FALLIDO
    avisos: list[str] = field(default_factory=list)   # fuentes caídas, copias que no eran PDF...


class InformeDescartado(ValueError):
    """
    El Informe Técnico se bajó pero no sirve: ninguna copia es un PDF, pypdf no lo lee, no
    trae la tabla, sus meses no cuadran, excede el tope o no es posterior al ya leído. Volver
    a bajarlo no lo arregla: `referencia` (con la hora) se guarda en el latido y ese informe
    no se vuelve a bajar antes de ESPERA_FALLIDO. `avisos`: fallas de las fuentes.
    """

    def __init__(self, mensaje: str, referencia: ReferenciaInforme, avisos: list[str] | None = None):
        super().__init__(mensaje)
        self.referencia = referencia
        self.avisos = list(avisos or [])


class _NoEsPDF(ValueError):
    """La descarga no empieza con %PDF (p. ej. una página de mantenimiento con 200)."""


# ---------------------------------------------------------------------------
# Normalización de texto
# ---------------------------------------------------------------------------

_GUIONES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_COMILLAS = dict.fromkeys(map(ord, "“”„«»‘’‚‹›"), '"')


def _plano(texto: str) -> str:
    """Texto NFC en una sola línea: guiones y comillas unificados, espacios colapsados."""
    t = unicodedata.normalize("NFC", texto).translate(_GUIONES).translate(_COMILLAS)
    return re.sub(r"\s+", " ", t).strip()


def _clave(s: str) -> str:
    """
    Copia de s en minúsculas y sin tildes, de la MISMA longitud: las búsquedas se hacen
    aquí y los recortes de texto oficial se toman de s con las mismas posiciones.
    """
    return "".join(unicodedata.normalize("NFD", c)[0].lower()[0] for c in s)


def _texto_html(fragmento: str) -> str:
    return _plano(html.unescape(re.sub(r"<[^>]*>", " ", fragmento)))


# ---------------------------------------------------------------------------
# Fechas en español
# ---------------------------------------------------------------------------

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
_MESES_CORTOS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
    "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}
_MES = "|".join(sorted(_MESES, key=len, reverse=True))

# Sobre texto _clave: "14 de setiembre de 2026", "14 de setiembre 2026",
# "28 de septiembre del 2026", "14 septiembre- 2026", "28 de septiembre" (sin año).
_RE_FECHA = re.compile(
    rf"(?<!\d)(\d{{1,2}})\s*(?:de\s+)?({_MES})(?![a-z])"
    r"(?:[\s,]*(?:-\s*)?(?:(?:de|del)\s+)?(\d{4})(?!\d))?"
)


def _fecha(m: re.Match, referencia: date | None = None) -> date:
    """
    Fecha de un match de _RE_FECHA. Sin año, se usa la primera fecha posterior a
    `referencia` (p. ej. un comunicado de diciembre que anuncia el próximo en enero).
    """
    dia, mes = int(m.group(1)), _MESES[m.group(2)]
    if m.group(3):
        return date(int(m.group(3)), mes, dia)
    if referencia is None:
        raise ValueError(f"Fecha sin año: {m.group(0)!r}")
    f = date(referencia.year, mes, dia)
    return f if f > referencia else date(referencia.year + 1, mes, dia)


def _primera_fecha(texto_clave: str) -> date | None:
    """Primera fecha completa (con año) del texto."""
    for m in _RE_FECHA.finditer(texto_clave):
        if not m.group(3):
            continue
        try:
            return _fecha(m)
        except ValueError:   # p. ej. "31 de junio": se ignora
            continue
    return None


# ---------------------------------------------------------------------------
# Parseo del texto del comunicado
# ---------------------------------------------------------------------------

# "comunicado oficial enfen n° 16-2026", "comunicado extraordinario enfen n° 01-2025",
# "comunicado enfen n°06 - 2024", "comunicado_of_enfen n° 12-2021" (títulos de gob.pe).
_RE_ENCABEZADO = re.compile(
    r"comunicado[\s_]+(?:(?:oficial|of)[\s_]+)?(extraordinario[\s_]+)?(?:oficial[\s_]+)?"
    r"enfen[\s_]+n\s*[°º.]*\s*(?P<numero>\d{1,2})\s*-\s*(?P<anio>\d{4})(?!\d)"
)
_RE_ROTULO_ESTADO = re.compile(r"estado\s+del\s+sistema\s+de\s+alerta\s*:\s*")
_RE_ESTADO = re.compile(
    r'"?\s*(?:no\s*activ[oa]|(vigilancia|alerta)\s+(?:de\s+)?(el\s+nino|la\s+nina)\s+coster[oa])(?![a-z])'
)
# El mismo estado sobre texto sin espacios: pypdf a veces parte palabras ("Ni ño").
_RE_ESTADO_COMPACTO = re.compile(r'"?(?:noactiv[oa]|(vigilancia|alerta)(?:de)?(elnino|lanina)coster[oa])')
_RE_VERBO_ESTADO = re.compile(r"\b(mantiene|cambia|activa|declara)\b")
_RE_PROXIMO = re.compile(r"pr\s?oxim[oa]\s+(?:comunicado|actualizacion|emision)")
_RE_RESUMEN = re.compile(r"resumen\s+ejecutivo")
_RE_CUERPO = re.compile(r"la\s+comision\s+multisectorial")
# Llamada a nota al pie pegada a una palabra o tras una comilla de cierre: "débiles2
# actuales", "RONI7", '"Alerta de El Niño Costero" 1 ya que'. No toca decimales ("v5.0")
# ni cifras tras una comilla de apertura ('"58 %"') o antes de un símbolo ('"fuerte" 45 %').
_RE_LLAMADA = re.compile(
    r'(?<=[^\W\d_])\d{1,2}(?![.,]?\d)(?=[\s,.;:)]|$)'
    r'|(?<=\S")\s?\d{1,2}(?=\s+[a-záéíóúñ]|[,;:)]|$)'
)
_RE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[¿\"(]?[A-ZÁÉÍÓÚÑ])")

# Tabla del ICEN (formato del Informe Técnico ENFEN), sobre texto _clave.
_MES_CORTO = "|".join(_MESES_CORTOS)
_CATEGORIA = r"(neutra|(?:calida|fria)\s+(?:muy\s+fuerte|debil|moderada|fuerte|extraordinar\s?ia))"
_RE_FILA_ICEN = re.compile(
    rf"(?<![a-z])({_MES_CORTO})\s*-\s*(\d{{2}})\s+([+-]?\s?\d{{1,2}}[.,]\d{{1,2}})\s+{_CATEGORIA}(?![a-z])"
)
_RE_CAB_ICEN = re.compile(r"(?<![a-z])mes\s+icen(?![a-z])(?!\s*-?\s*tmp)")
_RE_CAB_ICEN_TMP = re.compile(r"(?<![a-z])mes\s+icen\s*-?\s*tmp(?![a-z])")
_MAX_SALTO_FILA = 160   # caracteres entre filas de la misma tabla (columnas RONI/ONI)


def _estado_canonico(m: re.Match) -> str:
    if not m.group(1):
        return "No activo"
    tipo = m.group(1).capitalize()
    fenomeno = "El Niño Costero" if m.group(2).startswith("el") else "La Niña Costera"
    return f"{tipo} de {fenomeno}"


def _estado_tras_rotulo(clave: str, inicio: int) -> tuple[str, int] | None:
    """Estado justo después del rótulo, ignorando espacios (cortes de pypdf)."""
    m = _RE_ESTADO.match(clave, inicio)
    if m:
        return _estado_canonico(m), m.end()
    ventana = clave[inicio:inicio + 120]
    posiciones = [i for i, c in enumerate(ventana) if not c.isspace()]
    compacto = "".join(ventana[i] for i in posiciones)
    m = _RE_ESTADO_COMPACTO.match(compacto)
    if not m:
        return None
    return _estado_canonico(m), inicio + posiciones[m.end() - 1] + 1


def _estado(plano: str, clave: str) -> tuple[str, int | None]:
    """Estado canónico y posición donde termina el rótulo "Estado del sistema de alerta: X"."""
    rotulo = _RE_ROTULO_ESTADO.search(clave)
    if rotulo:
        hallado = _estado_tras_rotulo(clave, rotulo.end())
        if not hallado:
            crudo = plano[rotulo.end():rotulo.end() + 60]
            raise ValueError(f"Estado del sistema de alerta no reconocido: {crudo!r}")
        return hallado
    # Respaldo: la frase del cuerpo, p. ej. 'mantiene el estado de "Alerta de El Niño
    # Costero"' o 'cambia ... de "No Activo" a "Vigilancia de El Niño Costero"'.
    for v in _RE_VERBO_ESTADO.finditer(clave, 0, 8000):
        frase = clave[v.start():v.start() + 300].split(". ")[0]
        if "estado" not in frase:
            continue
        citados = [m for m in _RE_ESTADO.finditer(frase) if m.group(0).startswith('"')]
        if citados:
            return _estado_canonico(citados[-1] if v.group(1) == "cambia" else citados[0]), None
    raise ValueError("No se encontró el estado del sistema de alerta en el comunicado")


def _proximo(clave: str, fecha: date) -> date | None:
    for p in _RE_PROXIMO.finditer(clave):
        ventana = clave[p.end():p.end() + 200].split(". ")[0]
        for m in _RE_FECHA.finditer(ventana):
            try:
                prox = _fecha(m, referencia=fecha)
            except ValueError:
                continue
            if fecha < prox <= fecha + timedelta(days=366):
                return prox
            log.warning("Fecha del próximo comunicado fuera de rango (%s, emisión %s): se ignora", prox, fecha)
            break   # se prueba la siguiente mención del próximo comunicado
    return None


def _resumen(plano: str, clave: str, desde: int, fin_estado: int | None,
             max_frases: int = 3, max_chars: int = 480) -> str | None:
    """
    Primeras frases del RESUMEN EJECUTIVO (desde 2024). Si no lo hay, las primeras del
    texto que sigue a "Estado del sistema de alerta: X" (comunicados 2020-2023); si
    tampoco está ese rótulo, None.
    """
    # pypdf a veces saca el recuadro del resumen después del cuerpo (CO 05-2026): se
    # busca en todo el texto.
    r = _RE_RESUMEN.search(clave, desde)
    if r:
        inicio = r.end()
        fin = _RE_CUERPO.search(clave, inicio)
        bloque = plano[inicio:fin.start() if fin else inicio + 3000]
    elif fin_estado is not None:
        bloque = plano[fin_estado:fin_estado + 3000].lstrip("0123456789 ")   # llamada de nota al pie
    else:
        return None
    bloque = _RE_LLAMADA.sub("", bloque).strip(" .:-")
    frases: list[str] = []
    for f in _RE_FRASE.split(bloque):
        f = f.strip()
        if not f:
            continue
        if frases and len(" ".join(frases + [f])) > max_chars:
            break
        frases.append(f)
        if len(frases) >= max_frases:
            break
    texto = " ".join(frases).strip()
    if not texto:
        return None
    if len(texto) > max_chars:   # una sola frase muy larga: se corta en una palabra
        texto = texto[:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return texto


def _categoria_icen(c: str) -> str:
    # Mismo formato que igp.categoria(): "Cálida fuerte", "Fría débil", "Neutra".
    palabras = re.sub(r"extraordinar\s?ia", "extraordinaria", c).split()
    if palabras[0] == "neutra":
        return "Neutra"
    signo = {"calida": "Cálida", "fria": "Fría"}[palabras[0]]
    magnitud = " ".join(palabras[1:]).replace("debil", "débil")
    return f"{signo} {magnitud}"


def _fila_icen(m: re.Match) -> tuple[str, float, str]:
    mes = _MESES_CORTOS[m.group(1)]
    valor = float(m.group(3).replace(" ", "").replace(",", "."))
    return f"{2000 + int(m.group(2)):04d}-{mes:02d}", valor, _categoria_icen(m.group(4))


def _icen(clave: str) -> tuple[list[tuple[str, float, str]], tuple[str, float, str] | None]:
    """Filas de la tabla del ICEN y del ICENtmp, si el texto las trae."""
    tmp_cabs = [c.start() for c in _RE_CAB_ICEN_TMP.finditer(clave)]
    filas: dict[str, tuple[str, float, str]] = {}
    for cab in _RE_CAB_ICEN.finditer(clave):
        tope = min((t for t in tmp_cabs if t > cab.end()), default=len(clave))
        pos = cab.end()
        while True:
            m = _RE_FILA_ICEN.search(clave, pos, tope)
            if not m or m.start() - pos > _MAX_SALTO_FILA:
                break
            fila = _fila_icen(m)
            filas.setdefault(fila[0], fila)
            pos = m.end()
    icen_tmp = None
    for t in _RE_CAB_ICEN_TMP.finditer(clave):
        m = _RE_FILA_ICEN.search(clave, t.end())
        if m and m.start() - t.end() <= _MAX_SALTO_FILA:
            icen_tmp = _fila_icen(m)
            break
    return sorted(filas.values()), icen_tmp


def parsear_texto(texto: str, url: str) -> ComunicadoENFEN:
    """
    Datos de un comunicado a partir de su texto (el que devuelve pypdf). Tolera saltos
    de línea y espacios raros, tildes y mayúsculas. Si falta el encabezado con el
    número, la fecha de emisión o el estado, lanza ValueError: nunca datos a medias.
    """
    plano = _plano(texto or "")
    clave = _clave(plano)
    if not clave:
        raise ValueError(f"El comunicado no tiene texto (¿PDF escaneado?): {url}")

    enc = _RE_ENCABEZADO.search(clave)
    if not enc:
        raise ValueError(f"No se encontró el encabezado 'COMUNICADO OFICIAL ENFEN N° NN-AAAA' en {url}")
    numero, anio = int(enc.group(2)), int(enc.group(3))

    fecha = _primera_fecha(clave[enc.end():enc.end() + 250])
    if fecha is None:
        raise ValueError(f"No se encontró la fecha de emisión del comunicado {numero}-{anio} ({url})")
    if abs(fecha.year - anio) > 1:
        raise ValueError(f"La fecha de emisión {fecha} no corresponde al comunicado {numero}-{anio} ({url})")

    estado, fin_estado = _estado(plano, clave)
    icen, icen_tmp = _icen(clave)
    return ComunicadoENFEN(
        numero=numero,
        anio=anio,
        fecha=fecha,
        estado=estado,
        proximo=_proximo(clave, fecha),
        url=url,
        resumen=_resumen(plano, clave, enc.end(), fin_estado),
        icen=icen,
        icen_tmp=icen_tmp,
        extraordinario=bool(enc.group(1)),
    )


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _importar_pypdf():
    try:
        import pypdf
    except ImportError as e:
        raise RuntimeError(
            "Falta pypdf (lo usa solo el lector de comunicados ENFEN). Corre la tarea dentro "
            "del contenedor worker o instala backend/requirements.txt."
        ) from e
    return pypdf


def _ilegible(e: Exception, donde: str = "") -> ValueError:
    """
    Error de pypdf (pypdf.errors.PyPdfError u otro al extraer una página) -> ValueError: el
    archivo se bajó bien y no se entiende. Así no se trata como falla de red (que se
    reintenta y baja la otra copia del mismo archivo).
    """
    return ValueError(f"PDF ilegible{donde}: {type(e).__name__}: {e}")


def _lector_pdf(pypdf, datos: bytes):
    try:
        lector = pypdf.PdfReader(io.BytesIO(datos))
        return lector, len(lector.pages)
    except Exception as e:
        raise _ilegible(e) from e


def _texto_pdf(datos: bytes) -> str:
    pypdf = _importar_pypdf()
    lector, total = _lector_pdf(pypdf, datos)
    textos = []
    for i in range(min(total, MAX_PAGINAS)):
        try:
            textos.append(lector.pages[i].extract_text() or "")
        except Exception as e:
            raise _ilegible(e, f" (página {i + 1})") from e
    return "\n".join(textos)


def _es_pdf_valido(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and p.netloc in _HOSTS_PDF


def _exigir_pdf(datos: bytes, url: str) -> None:
    if not datos.lstrip()[:5].startswith(b"%PDF"):
        raise _NoEsPDF(f"La descarga no es un PDF: {url}")


def leer_pdf(url: str) -> ComunicadoENFEN:
    """Baja el PDF de un comunicado (con tope de tamaño) y lo parsea."""
    if not _es_pdf_valido(url):
        raise ValueError(f"URL de PDF no permitida: {url}")
    datos = _http.con_reintentos(_http.get_bytes, url, MAX_PDF_BYTES)
    _exigir_pdf(datos, url)
    return parsear_texto(_texto_pdf(datos), url)


# ---------------------------------------------------------------------------
# Descubrimiento del último comunicado
# ---------------------------------------------------------------------------

_RE_ENLACE = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.S | re.I)
_RE_PDF_GOBPE = re.compile(
    r"""https://cdn\.www\.gob\.pe/uploads/document/file/\d+/[^"'\s<>?#]+?\.pdf(?=[?#"'\s<>]|$)""", re.I)
_RE_DESCARGA_ENFEN = re.compile(
    r"https://enfen\.imarpe\.gob\.pe/download/"
    r"(comunicado-(?:oficial-|extraordinario-)?enfen-n-?(\d{1,2})-(\d{4})(?!\d)[a-z0-9-]*)/?\?wpdmdl=(\d+)",
    re.I)


def _atributo(atributos: str, nombre: str) -> str:
    m = re.search(rf"""\b{nombre}\s*=\s*(["'])(.*?)\1""", atributos, re.I | re.S)
    return html.unescape(m.group(2)).strip() if m else ""


@dataclass
class _Tarjeta:
    url: str               # ficha del comunicado en gob.pe
    publicado: date | None
    anio: int
    numero: int


def _tarjetas_gobpe(pagina: str, titulo: re.Pattern = _RE_ENCABEZADO,
                    base: str = GOBPE_COLECCION) -> list[_Tarjeta]:
    """
    Documentos de un compendio de gob.pe: ficha, fecha de publicación y número. `titulo`
    reconoce el título de la tarjeta (grupos 'numero' y 'anio').
    """
    out: list[_Tarjeta] = []
    for a in _RE_ENLACE.finditer(pagina):
        href = _atributo(a.group(1), "href")
        if "/informes-publicaciones/" not in href:
            continue
        t = titulo.search(_clave(_texto_html(a.group(2))))
        if not t:
            continue
        # La fecha de publicación va en el div justo antes del enlace: la última fecha
        # con año del tramo previo.
        previo = _clave(_texto_html(pagina[max(0, a.start() - 400):a.start()]))
        fechas = [m for m in _RE_FECHA.finditer(previo) if m.group(3)]
        try:
            publicado = _fecha(fechas[-1]) if fechas else None
        except ValueError:
            publicado = None
        out.append(_Tarjeta(urllib.parse.urljoin(base, href), publicado,
                            int(t.group("anio")), int(t.group("numero"))))
    return out


def _ultima_tarjeta(tarjetas: list[_Tarjeta]) -> _Tarjeta:
    # Manda la fecha de publicación: los títulos traen erratas ("N°09-2024" publicado en 2025).
    return max(tarjetas, key=lambda t: (t.publicado or date.min, t.anio, t.numero))


def _pdf_de_ficha_gobpe(url_ficha: str) -> str:
    pagina = _http.con_reintentos(_http.get, url_ficha)
    enlaces = list(dict.fromkeys(html.unescape(u) for u in _RE_PDF_GOBPE.findall(pagina)))
    preferidos = [u for u in enlaces if re.search(r"enfen|comunicado", u, re.I)]
    for u in preferidos + enlaces:
        if _es_pdf_valido(u):
            return u
    raise ValueError(f"La ficha de gob.pe no enlaza el PDF del documento: {url_ficha}")


def _pdf_gobpe() -> str:
    pagina = _http.con_reintentos(_http.get, GOBPE_COLECCION)
    tarjetas = _tarjetas_gobpe(pagina)
    if not tarjetas:
        raise ValueError("El compendio 'Comunicados ENFEN' de gob.pe no lista comunicados")
    return _pdf_de_ficha_gobpe(_ultima_tarjeta(tarjetas).url)


def _ultimo_pdf_senamhi(es_del_tipo: Callable[[str], bool], que: str) -> tuple[date, str]:
    """
    (fecha, url) del PDF más reciente de un bloque de la página El Niño de SENAMHI. El
    bloque se reconoce por el atributo title de sus enlaces (es_del_tipo recibe el title
    en _clave); la fecha es el texto del enlace ("14 Septiembre- 2026").
    """
    pagina = _http.con_reintentos(_http.get, SENAMHI_NINO)
    hallados: list[tuple[date, str]] = []
    for a in _RE_ENLACE.finditer(pagina):
        attrs = a.group(1)
        titulo = _clave(_plano(_atributo(attrs, "title")))
        href = _atributo(attrs, "href")
        if not es_del_tipo(titulo) or not href.lower().endswith(".pdf"):
            continue
        fecha = _primera_fecha(_clave(_texto_html(a.group(2)) or _atributo(attrs, "alt")))
        url = urllib.parse.urljoin(SENAMHI_NINO, href)
        if fecha and _es_pdf_valido(url):
            hallados.append((fecha, url))
    if not hallados:
        raise ValueError(f"La página El Niño de SENAMHI no lista {que}")
    # max() se queda con el primero en caso de empate: la página va de nuevo a viejo.
    return max(hallados, key=lambda h: h[0])


def _pdf_senamhi() -> str:
    return _ultimo_pdf_senamhi(lambda t: "comunicado" in t and "enfen" in t, "comunicados ENFEN")[1]


def _pdf_enfen() -> str:
    pagina = html.unescape(_http.con_reintentos(_http.get, ENFEN_COMUNICADOS))
    hallados = {(int(m.group(3)), int(m.group(2)), int(m.group(4))): m.group(1)
                for m in _RE_DESCARGA_ENFEN.finditer(pagina)}
    if not hallados:
        raise ValueError("La web del ENFEN no lista comunicados descargables")
    anio, numero, wpdmdl = max(hallados)
    return f"https://enfen.imarpe.gob.pe/download/{hallados[(anio, numero, wpdmdl)]}/?wpdmdl={wpdmdl}"


_FUENTES = (("gob.pe", _pdf_gobpe), ("SENAMHI", _pdf_senamhi), ("web ENFEN", _pdf_enfen))


def _hoy() -> date:
    return datetime.now(HORA_PERU).date()


def _orden(c: ComunicadoENFEN) -> tuple:
    return (c.fecha, c.anio, c.numero)


def _vencido(c: ComunicadoENFEN) -> bool:
    return c.proximo is not None and _hoy() > c.proximo + MARGEN_VENCIDO


def _demasiado_viejo(c: ComunicadoENFEN) -> bool:
    if c.proximo is not None:
        return _hoy() > c.proximo + MAX_ATRASO
    return _hoy() - c.fecha > MAX_ANTIGUEDAD_SIN_PROXIMO


def ultimo_comunicado() -> ComunicadoENFEN:
    """
    Comunicado ENFEN más reciente, ya parseado. Prueba las fuentes en orden; si una
    falla (red, cambio de formato) pasa a la siguiente. Si todas fallan lanza
    RuntimeError con el motivo de cada una.
    """
    _importar_pypdf()   # sin pypdf no sirve ninguna fuente: se avisa de inmediato
    errores: list[str] = []
    ilegibles: list[str] = []   # PDF bajados que no se entienden: posible cambio de formato
    hallados: list[ComunicadoENFEN] = []

    def entregar(c: ComunicadoENFEN) -> ComunicadoENFEN:
        # Si otra fuente tenía un PDF que no se pudo leer, puede ser uno más nuevo con
        # formato distinto: se entrega lo que hay, pero el aviso queda visible.
        for aviso in ilegibles:
            log.error("ENFEN: %s", aviso)
        c.avisos = ilegibles + errores
        return c

    for nombre, descubrir in _FUENTES:
        try:
            url = descubrir()
        except Exception as e:   # red, listado que cambió...: se prueba la siguiente fuente
            log.warning("ENFEN: la fuente %s falló: %s: %s", nombre, type(e).__name__, e)
            errores.append(f"{nombre}: {type(e).__name__}: {e}")
            continue
        if any(c.url == url for c in hallados):
            continue
        try:
            hallados.append(leer_pdf(url))
        except ValueError as e:
            ilegibles.append(f"{nombre}: no se pudo leer {url}: {e}")
            continue
        except Exception as e:
            log.warning("ENFEN: la fuente %s falló al bajar el PDF: %s: %s", nombre, type(e).__name__, e)
            errores.append(f"{nombre}: {type(e).__name__}: {e}")
            continue
        mejor = max(hallados, key=_orden)
        if not _vencido(mejor):
            return entregar(mejor)
        log.warning("ENFEN: el comunicado %d-%d anunciaba el próximo para el %s; se revisan las demás fuentes",
                    mejor.numero, mejor.anio, mejor.proximo)
    if hallados:
        mejor = max(hallados, key=_orden)
        if _demasiado_viejo(mejor):
            raise RuntimeError(
                f"El comunicado más nuevo hallado ({mejor.numero}-{mejor.anio}, {mejor.fecha}) está muy "
                "atrasado: no se usa. " + " | ".join(ilegibles + errores))
        log.warning("ENFEN: no se halló un comunicado posterior al %d-%d (anunciado para el %s)",
                    mejor.numero, mejor.anio, mejor.proximo)
        return entregar(mejor)
    raise RuntimeError("No se pudo obtener el último comunicado ENFEN. " + " | ".join(ilegibles + errores))


# ---------------------------------------------------------------------------
# Informe Técnico ENFEN: el ICEN al día
# ---------------------------------------------------------------------------

# Sobre texto _clave. Portada: "AÑO 12 N° 16 INFORME TÉCNICO ENFEN 11 SEPTIEMBRE DEL 2026";
# créditos (pág. 2): "Informe Técnico ENFEN. Año 12, N° 16, 11 de septiembre del 2026, 87 p."
_RE_INFORME = re.compile(r"informe\s+tecnico\s+(?:del\s+)?enfen(?![a-z])")
_RE_NUMERO_INFORME = re.compile(r"(?<![a-z])ano\s*\d{1,2}\s*,?\s*n\s*[°º.]*\s*(\d{1,2})(?!\d)")
# Tarjetas de gob.pe: "Informe Técnico del ENFEN N°16-2026", "Informe Técnico del ENFEN N°14 - 2026".
_RE_TITULO_INFORME = re.compile(
    r"informe\s+tecnico\s+(?:del\s+)?enfen\s+n\s*[°º.]*\s*(?P<numero>\d{1,2})\s*-\s*(?P<anio>\d{4})(?!\d)")
# title de los enlaces de SENAMHI. Exacto: "Informe Técnico SENAMHI - ENFEN" es otro documento.
_RE_TITULO_INFORME_SENAMHI = re.compile(r"informe\s+tecnico\s+(?:del\s+)?enfen")


def _cabecera_informe(clave: str) -> tuple[int | None, date | None]:
    """Número y fecha del informe a partir del texto de la portada o de los créditos."""
    m = _RE_NUMERO_INFORME.search(clave)
    numero = int(m.group(1)) if m else None
    for t in _RE_INFORME.finditer(clave):
        fecha = _primera_fecha(clave[t.end():t.end() + 120])
        if fecha:
            return numero, fecha
    return numero, None


def _mes(periodo: str | date) -> int:
    """Meses desde el año 0: "2026-07" o una fecha -> entero comparable."""
    if isinstance(periodo, date):
        return periodo.year * 12 + periodo.month - 1
    anio, mes = periodo.split("-")
    return int(anio) * 12 + int(mes) - 1


def _validar_meses(icen: list[tuple[str, float, str]], icen_tmp: tuple[str, float, str] | None,
                   fecha: date | None, url: str) -> tuple[tuple[str, float, str] | None, list[str]]:
    """
    Los meses leídos tienen que ser razonables. Si el ICEN no lo es, la tabla se leyó mal:
    ValueError. Un ICENtmp incoherente se descarta con aviso (el IT N° 03-2026 lo rotula
    "Dic-25", igual que el último ICEN, cuando es el de enero): no invalida el ICEN.
    Devuelve (icen_tmp o None, avisos).
    """
    hoy = _hoy()
    if fecha is not None and fecha > hoy + timedelta(days=1):   # la portada nunca va adelantada
        raise ValueError(f"La fecha del Informe Técnico ({fecha}) es futura: {url}")
    referencia = fecha or hoy
    futuros = [p for p, _, _ in icen if _mes(p) > _mes(referencia)]
    if futuros:
        raise ValueError(f"El Informe Técnico trae un ICEN posterior a su fecha ({referencia}): "
                         f"{', '.join(futuros)} ({url})")
    ultimo = icen[-1][0]
    if _mes(ultimo) < _mes(referencia) - MAX_MESES_ICEN:
        raise ValueError(f"El ICEN más reciente del Informe Técnico ({ultimo}) tiene más de "
                         f"{MAX_MESES_ICEN} meses respecto de {referencia}: {url}")
    if icen_tmp and not _mes(ultimo) < _mes(icen_tmp[0]) <= _mes(referencia):
        aviso = (f"ICENtmp descartado: {icen_tmp[0]} no está entre el último ICEN ({ultimo}) "
                 f"y la fecha del informe ({referencia}): {url}")
        log.warning("ENFEN: %s", aviso)
        return None, [aviso]
    return icen_tmp, []


def parsear_informe(paginas: Iterable[str], url: str) -> InformeICEN:
    """
    ICEN del Informe Técnico a partir del texto de sus páginas, en orden. Se detiene en la
    tabla (pág. ~30 de ~88): con un iterador perezoso las páginas siguientes ni se extraen.
    Si no halla la tabla, o sus meses no son razonables, lanza ValueError.
    """
    numero = fecha = None
    anterior = ""
    con_texto = False
    hallado = None   # (icen, icen_tmp, página)
    n = 0
    for n, texto in enumerate(paginas, 1):
        clave = _clave(_plano(texto or ""))
        con_texto = con_texto or bool(clave)
        if n <= 2 and (numero is None or fecha is None):
            num, fec = _cabecera_informe(clave)
            numero = numero if numero is not None else num
            fecha = fecha or fec
        # La tabla puede empezar al pie de una página y seguir en la siguiente.
        if "icen" in clave or "icen" in anterior:
            icen, icen_tmp = _icen(f"{anterior} {clave}")
            if icen and (hallado is None or icen_tmp is not None):
                hallado = (icen, icen_tmp, n)
        # completa, o ya se miró la página siguiente por si el ICENtmp quedó allí
        if hallado and (hallado[1] is not None or hallado[2] < n):
            break
        anterior = clave
    if not con_texto:
        raise ValueError(f"El Informe Técnico no tiene texto (¿PDF escaneado?): {url}")
    if hallado is None:
        raise ValueError(f"No se encontró la tabla del ICEN ('Mes ICEN Categoría ...') en las {n} "
                         f"páginas del Informe Técnico: {url}")
    icen, icen_tmp, pagina = hallado
    icen_tmp, avisos = _validar_meses(icen, icen_tmp, fecha, url)
    log.info("ENFEN: tabla del ICEN en la página %d del Informe Técnico (se leyeron %d)", pagina, n)
    return InformeICEN(url=url, numero=numero, fecha=fecha, icen=icen, icen_tmp=icen_tmp, avisos=avisos)


def _paginas_pdf(datos: bytes) -> Iterator[str]:
    """
    Texto de cada página, extraído recién cuando se pide (~0.04 s por página con pypdf).
    Un error de pypdf sale como ValueError('PDF ilegible ...').
    """
    pypdf = _importar_pypdf()
    lector, total = _lector_pdf(pypdf, datos)
    for i in range(total):
        try:
            texto = lector.pages[i].extract_text() or ""
        except Exception as e:
            raise _ilegible(e, f" (página {i + 1})") from e
        yield texto


def leer_informe(url: str) -> InformeICEN:
    """
    Baja un Informe Técnico (con tope de tamaño) y lee el ICEN de su tabla. Cualquier
    problema con el archivo bajado (no es PDF, ilegible, sin tabla, excede el tope) es
    ValueError; las fallas de red, OSError / HTTPError.
    """
    if not _es_pdf_valido(url):
        raise ValueError(f"URL de PDF no permitida: {url}")
    inicio = time.monotonic()
    datos = _http.con_reintentos(_http.get_bytes, url, MAX_INFORME_BYTES)
    bajado = time.monotonic()
    _exigir_pdf(datos, url)
    informe = parsear_informe(_paginas_pdf(datos), url)
    log.info("ENFEN: Informe Técnico N° %s (%s): %.1f MB bajados en %.1f s, leído en %.1f s",
             informe.numero, informe.fecha, len(datos) / 1e6, bajado - inicio, time.monotonic() - bajado)
    return informe


def _informe_senamhi() -> tuple[date | None, str]:
    return _ultimo_pdf_senamhi(lambda t: bool(_RE_TITULO_INFORME_SENAMHI.fullmatch(t)),
                               "informes técnicos ENFEN")


def _informe_gobpe() -> tuple[date | None, str]:
    pagina = _http.con_reintentos(_http.get, GOBPE_INFORMES)
    tarjetas = _tarjetas_gobpe(pagina, _RE_TITULO_INFORME, GOBPE_INFORMES)
    if not tarjetas:
        raise ValueError("El compendio 'Informe Técnico del ENFEN' de gob.pe no lista informes")
    ultima = _ultima_tarjeta(tarjetas)
    return ultima.publicado, _pdf_de_ficha_gobpe(ultima.url)


# SENAMHI primero: una sola página y URL estable; gob.pe pide el compendio y la ficha.
_FUENTES_INFORME = (("SENAMHI", _informe_senamhi), ("gob.pe", _informe_gobpe))


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _ya_leido(publicado: date | None, url: str, leido: ReferenciaInforme | None) -> bool:
    """El candidato es el informe ya leído (desde cualquier fuente) o uno anterior."""
    if leido is None:
        return False
    if url == leido.url or url in leido.alias:
        return True
    return publicado is not None and leido.publicado is not None and publicado <= leido.publicado + MISMO_INFORME


def _en_espera(publicado: date | None, url: str, fallido: ReferenciaInforme | None, ahora: datetime) -> bool:
    """El candidato es el informe descartado (desde cualquier fuente) hace menos de ESPERA_FALLIDO."""
    if fallido is None or fallido.ts is None or not timedelta(0) <= ahora - fallido.ts < ESPERA_FALLIDO:
        return False
    if url == fallido.url:
        return True
    return (publicado is not None and fallido.publicado is not None
            and abs(publicado - fallido.publicado) <= MISMO_INFORME)


def _frente_al_leido(informe: InformeICEN, leido: ReferenciaInforme | None) -> str:
    """
    Compara por la PORTADA (fecha del informe) apenas se lee, sin importar lo que dijo el
    listado: 'nuevo', 'mismo' (el ya leído servido con otra URL) o 'viejo' (un listado que
    volvió a publicar uno anterior). Si falta alguna portada no se puede saber: 'nuevo' (las
    reglas SQL igual impiden que el ICEN retroceda).
    """
    if leido is None or informe.fecha is None or leido.fecha is None:
        return "nuevo"
    if informe.fecha == leido.fecha:
        return "mismo"
    return "viejo" if informe.fecha < leido.fecha else "nuevo"


def _descartado(mensaje: str, url: str, publicado: date | None, avisos: list[str]) -> InformeDescartado:
    log.error("ENFEN: Informe Técnico descartado, no se vuelve a bajar en %s: %s", ESPERA_FALLIDO, mensaje)
    ref = ReferenciaInforme(url=url, publicado=publicado, ts=_ahora(), error=mensaje[:_MAX_ERROR])
    return InformeDescartado(mensaje, ref, avisos)


def informe_tecnico_icen(leido: ReferenciaInforme | None = None,
                         fallido: ReferenciaInforme | None = None) -> ConsultaInforme:
    """
    ICEN del último Informe Técnico ENFEN, si es posterior a `leido` (el de la corrida
    anterior). Si no lo es, ConsultaInforme sin informe y sin bajar nada: pesa ~17 MB y sale
    cada 2-4 semanas.

    Consulta todas las fuentes (son páginas livianas) y se queda con la publicación más
    reciente: un listado que deja de actualizarse no frena el ICEN. Un candidato con la URL
    del leído o con fecha de publicación <= la suya (+ MISMO_INFORME) no se baja: ni el mismo
    informe servido por la otra fuente ni uno más viejo de un listado atrasado.

    Fallas:
      - de red (listado o descarga): se prueba la copia de la otra fuente; si no queda
        ninguna, RuntimeError, y la próxima corrida reintenta.
      - una copia que no es un PDF (p. ej. HTML de mantenimiento con 200): se prueba la otra;
        si ninguna lo es, InformeDescartado.
      - PDF ilegible, sin la tabla, meses fuera de rango, excede el tope: InformeDescartado
        sin bajar la otra copia (es el mismo archivo).
      - el informe es `fallido` (descartado hace menos de ESPERA_FALLIDO): no se baja y la
        consulta vuelve con en_espera=True.
    Los avisos de las fuentes vuelven siempre: en la consulta o en la excepción.
    """
    _importar_pypdf()   # sin pypdf no se puede leer: se avisa antes de ir a la red
    errores: list[str] = []
    candidatos: list[tuple[str, date | None, str]] = []   # (fuente, publicado, url del PDF)
    for nombre, descubrir in _FUENTES_INFORME:
        try:
            publicado, url = descubrir()
        except Exception as e:   # red, listado que cambió...: se sigue con la otra fuente
            log.warning("ENFEN: la fuente %s de informes técnicos falló: %s: %s", nombre, type(e).__name__, e)
            errores.append(f"informe {nombre}: {type(e).__name__}: {e}")
            continue
        candidatos.append((nombre, publicado, url))
    if not candidatos:
        raise RuntimeError("No se pudo descubrir el último Informe Técnico ENFEN. " + " | ".join(errores))

    # Latido del formato anterior (solo la URL): se completa con la fecha del listado.
    if leido is not None and leido.publicado is None:
        leido = next((replace(leido, publicado=p) for _, p, u in candidatos if u == leido.url and p), leido)

    fechas = [p for _, p, _ in candidatos if p]
    vigentes = [c for c in candidatos if c[1] and c[1] >= max(fechas) - MISMO_INFORME] if fechas else candidatos
    nuevos = [c for c in vigentes if not _ya_leido(c[1], c[2], leido)]
    if not nuevos:
        log.info("ENFEN: no hay un Informe Técnico posterior al ya leído (%s, publicado %s): no se baja",
                 leido.url, leido.publicado)
        return ConsultaInforme(None, leido, avisos=errores)

    ahora = _ahora()
    pendientes = [c for c in nuevos if not _en_espera(c[1], c[2], fallido, ahora)]
    if not pendientes:
        aviso = (f"Informe Técnico en espera hasta {fallido.ts + ESPERA_FALLIDO:%Y-%m-%d %H:%M} UTC, "
                 f"se descartó {fallido.url}: {fallido.error}")
        log.warning("ENFEN: %s", aviso)
        return ConsultaInforme(None, leido, en_espera=True, avisos=errores + [aviso])

    no_pdf: list[tuple[date | None, str, str]] = []   # (publicado, url, motivo)
    for nombre, publicado, url in pendientes:
        try:
            informe = leer_informe(url)
        except _NoEsPDF as e:   # p. ej. página de mantenimiento: la otra copia puede estar bien
            log.warning("ENFEN: la copia de %s del Informe Técnico no es un PDF: %s", nombre, url)
            no_pdf.append((publicado, url, f"informe {nombre}: {e}"))
            continue
        except ValueError as e:   # ilegible, sin la tabla, excede el tope: la otra copia es el mismo archivo
            mensaje = str(e) if url in str(e) else f"{e} ({url})"
            raise _descartado(mensaje, url, publicado, errores + [m for _, _, m in no_pdf]) from e
        except Exception as e:   # red: se prueba la copia de la otra fuente
            log.warning("ENFEN: no se pudo bajar el Informe Técnico de %s: %s: %s", nombre, type(e).__name__, e)
            errores.append(f"informe {nombre}: {type(e).__name__}: {e}")
            continue
        avisos = errores + [m for _, _, m in no_pdf]
        frente = _frente_al_leido(informe, leido)
        if frente == "mismo":
            # el mismo informe con otra URL: se anota como alias para no volver a bajarlo
            fechas_pub = [f for f in (leido.publicado, publicado) if f]
            mismo = replace(leido, alias=sorted(set(leido.alias) | {url}),
                            publicado=max(fechas_pub) if fechas_pub else None)
            log.info("ENFEN: %s es el mismo Informe Técnico ya leído (portada del %s): se anota como alias",
                     url, informe.fecha)
            return ConsultaInforme(None, mismo, avisos=avisos)
        if frente == "viejo":
            raise _descartado(f"El Informe Técnico de {url} (portada del {informe.fecha}) es anterior "
                              f"al ya leído ({leido.fecha})", url, publicado, avisos)
        ref = ReferenciaInforme(url=url, publicado=publicado, numero=informe.numero, fecha=informe.fecha)
        return ConsultaInforme(informe, ref, avisos=avisos + informe.avisos)
    if len(no_pdf) == len(pendientes):
        publicado, url, _ = no_pdf[0]
        raise _descartado("Ninguna copia del Informe Técnico es un PDF: " + " | ".join(m for _, _, m in no_pdf),
                          url, publicado, errores)
    raise RuntimeError("No se pudo bajar el Informe Técnico ENFEN. "
                       + " | ".join(errores + [m for _, _, m in no_pdf]))
