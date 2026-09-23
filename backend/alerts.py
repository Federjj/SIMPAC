"""
Motor de umbrales de SIMPAC: decide qué lectura es una alerta. Puro y sin red.

- Caudal (ANA): usa los umbrales que la propia fuente entrega por estación
  (UALERTA / UEMERGENCIA), de crecida o de nivel bajo (vaciante) → el estado ya
  viene calculado en el conector.
- Lluvia (SENAMHI): la referencia de SENAMHI de cada estación, de la capa g_umbrales
  (umbral_1h, y umbral_6h = 3 x umbral_1h). Pasa si la lluvia de la última hora supera
  umbral_1h o la de las últimas 6 h supera umbral_6h (mayor estricto, como el mapa). SENAMHI
  no la documenta como umbral de alerta y, según sus curvas IDF, se supera casi cada año en
  2 de cada 3 estaciones: por eso el nivel es siempre 'aviso' y el texto dice que no es un
  aviso oficial. La evalúa la tarea lluvia_nacional (backend/ingesta/lluvia_nacional.py).

Se retiraron los umbrales provisionales de SIMPAC para la lluvia (20 y 40 mm en 24 h, 15 mm
en 1 h): eran los mismos en todo el país y no se ajustaban a cada lugar (20 mm en 24 h es
lluvia normal en la selva).
"""
from __future__ import annotations

import re

from backend.connectors.senamhi import HORA_PERU

# Lo que publica una fuente oficial (ANA o SENAMHI). 'lluvia' es lo que midió una estación
# frente a la referencia de SENAMHI: no es un aviso oficial.
TIPOS_OFICIALES = frozenset({"aviso", "caudal", "nivel_bajo"})
NIVEL_LLUVIA = "aviso"   # la lluvia medida nunca sube de nivel (tampoco en la BD)

# Palabras que en el nombre de una provincia van en minúscula (salvo al inicio).
_MINUSCULAS = frozenset({"de", "del", "la", "las", "los", "y"})


def es_oficial(tipo) -> bool:
    return tipo in TIPOS_OFICIALES


def referencia_caudal(c) -> str:
    """Texto con el que se identifica la alerta de caudal de una estación ANA."""
    return f"{c.estacion} ({c.rio})"


_TENDENCIA = {"Ascendente": "subiendo", "Descendente": "bajando", "Estable": "estable"}


def evaluar_caudal(caudales: list) -> list[dict]:
    """
    `caudales`: lista de EstacionCaudal (conector ANA). Con umbrales de nivel bajo
    (vaciante) la alerta es de tipo 'nivel_bajo': el río está demasiado BAJO, no crecido.
    """
    out = []
    for c in caudales:
        if c.estado not in ("alerta", "emergencia"):
            continue
        tendencia = _TENDENCIA.get(c.tendencia, c.tendencia.lower() or "sin tendencia")
        if c.umbral_bajo:
            tipo, detalle = "nivel_bajo", f"Río bajo (vaciante): nivel {c.valor} {c.unidad}, {tendencia}"
        else:
            medida = "Caudal" if c.unidad == "m³/s" else "Nivel"
            tipo, detalle = "caudal", f"{medida} {c.valor} {c.unidad}, {tendencia}"
        out.append({
            "tipo": tipo,
            "referencia": referencia_caudal(c),
            "zona": c.departamento or None,
            "nivel": c.estado,
            "detalle": detalle,
            "valor": c.valor,
            "umbral": c.umbral_emergencia if c.estado == "emergencia" else c.umbral_alerta,
        })
    return out


def pasa(pp, umbral) -> bool:
    """La lluvia supera la referencia (igual no pasa; sin referencia o con 0, tampoco)."""
    return pp is not None and umbral is not None and umbral > 0 and pp > umbral


def lluvia_evaluable(pp_1h, umbral_1h) -> bool:
    """Hay lluvia de la hora y referencia (> 0). Sin eso la de 6 h tampoco se mira."""
    return pp_1h is not None and umbral_1h is not None and umbral_1h > 0


def _capitalizar(s: str) -> str:
    """Mayúscula en la primera letra y en la que sigue a un espacio, '(' o '-'."""
    return re.sub(r"(^|[\s(-])([a-záéíóúñü])", lambda m: m.group(1) + m.group(2).upper(), s)


def nombre_legible(nombre: str) -> str:
    """
    'CHOTA GORE' -> 'Chota GORE', 'BAMBAMARCA M' -> 'Bambamarca'. La misma regla que
    nombreEstacion (frontend/src/lib/lenguaje.js), para que el detalle y el mapa coincidan.
    """
    s = _capitalizar(re.sub(r"\s+[MH]$", "", nombre, flags=re.I).lower())
    return re.sub(r"\b(Unc|Gore|Senamhi)\b", lambda m: m.group(0).upper(), s)


def provincia_legible(provincia: str) -> str:
    """'LA UNION' -> 'La Union', 'RODRIGUEZ DE MENDOZA' -> 'Rodriguez de Mendoza'."""
    palabras = _capitalizar(" ".join(provincia.lower().split())).split(" ")
    return " ".join(p.lower() if i and p.lower() in _MINUSCULAS else p for i, p in enumerate(palabras))


def _mm(v) -> str:
    """12.4 -> '12.4', 8.0 -> '8' (punto decimal, como el mapa con es-PE)."""
    return f"{round(v, 1):g}"


def _detalle_lluvia(nombre, provincia, pp_1h, umbral_1h, pp_6h, umbral_6h, p1, p6, medido_en) -> str:
    donde = nombre_legible(nombre) + (f" (provincia de {provincia_legible(provincia)})" if provincia else "")
    hora = medido_en.astimezone(HORA_PERU).strftime("%H:%M")
    if p1 and p6:
        midio = (f"llovió {_mm(pp_1h)} mm en la hora que terminó a las {hora} y {_mm(pp_6h)} mm "
                 "en las 6 horas que terminaron a esa hora")
        referencia = f"{_mm(umbral_1h)} mm en una hora y {_mm(umbral_6h)} mm en 6 horas"
    elif p1:
        midio = f"llovió {_mm(pp_1h)} mm en la hora que terminó a las {hora}"
        referencia = f"{_mm(umbral_1h)} mm en una hora"
    else:
        midio = f"llovió {_mm(pp_6h)} mm en las 6 horas que terminaron a las {hora}"
        referencia = f"{_mm(umbral_6h)} mm en 6 horas"
    return (f"En {donde} {midio}. SENAMHI usa {referencia} como referencia para esta estación. "
            "Es lo que midió la estación, no un aviso oficial.")


def evaluar_lluvia_referencia(clave, nombre, provincia, zona, pp_1h, umbral_1h,
                              pp_6h, umbral_6h, medido_en) -> dict | None:
    """
    Una estación de lluvia_senamhi frente a la referencia de SENAMHI -> alerta o None. Una
    sola por estación: ventana_h 1 si pasó la de 1 h (aunque también pase la de 6 h), si no
    6; valor y umbral son los de esa ventana. referencia = clave de lluvia_senamhi, zona = su
    departamento (None = sin departamento), ts = hora de la medición.
    """
    if not lluvia_evaluable(pp_1h, umbral_1h):
        return None
    p1, p6 = pasa(pp_1h, umbral_1h), pasa(pp_6h, umbral_6h)
    if not (p1 or p6):
        return None
    ventana, valor, umbral = (1, pp_1h, umbral_1h) if p1 else (6, pp_6h, umbral_6h)
    return {
        "tipo": "lluvia",
        "referencia": clave,
        "zona": zona,
        "nivel": NIVEL_LLUVIA,
        "detalle": _detalle_lluvia(nombre, provincia, pp_1h, umbral_1h, pp_6h, umbral_6h, p1, p6, medido_en),
        "valor": valor,
        "umbral": umbral,
        "ventana_h": ventana,
        "ts": medido_en,
    }
