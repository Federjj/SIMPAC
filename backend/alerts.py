"""
Motor de umbrales de SIMPAC (prototipo).

- Caudal (ANA): usa los umbrales que la propia fuente entrega por estación
  (UALERTA / UEMERGENCIA) → el estado ya viene calculado en el conector.
- Lluvia (SENAMHI): umbrales configurables sobre la precipitación acumulada.

Los umbrales de lluvia de abajo son PLACEHOLDERS y deben calibrarse con
Defensa Civil / SENAMHI para Cajamarca (varían por microcuenca). Se dejan
explícitos y en un solo lugar a propósito.
"""
from __future__ import annotations

# Precipitación acumulada en 24 h (mm)
LLUVIA_24H_ALERTA = 20.0
LLUVIA_24H_EMERGENCIA = 40.0
# Precipitación en 1 h (mm) — lluvia intensa puntual
LLUVIA_1H_ALERTA = 15.0


def referencia_lluvia(cod: str, estacion: str) -> str:
    """Texto con el que se identifica la alerta de lluvia de una estación."""
    return f"{estacion} ({cod})"


def referencia_caudal(c) -> str:
    """Texto con el que se identifica la alerta de caudal de una estación ANA."""
    return f"{c.estacion} ({c.rio})"


def evaluar_caudal(caudales: list) -> list[dict]:
    """`caudales`: lista de EstacionCaudal (conector ANA)."""
    out = []
    for c in caudales:
        if c.estado in ("alerta", "emergencia"):
            out.append({
                "tipo": "caudal",
                "referencia": referencia_caudal(c),
                "zona": c.departamento or None,
                "nivel": c.estado,
                "detalle": f"Caudal {c.valor} {c.unidad}, tendencia {c.tendencia}",
                "valor": c.valor,
                "umbral": c.umbral_emergencia if c.estado == "emergencia" else c.umbral_alerta,
            })
    return out


def evaluar_lluvia(cod: str, estacion: str, serie, zona: str | None = None) -> dict | None:
    """`serie`: SerieHoraria (conector SENAMHI). Devuelve una alerta o None."""
    acc24 = serie.precip_acumulada(24)
    ult = serie.ultimo or {}
    p1h = ult.get("precip_mm") or 0.0

    nivel = None
    valor = acc24
    if acc24 >= LLUVIA_24H_EMERGENCIA:
        nivel, umbral = "emergencia", LLUVIA_24H_EMERGENCIA
    elif acc24 >= LLUVIA_24H_ALERTA:
        nivel, umbral = "alerta", LLUVIA_24H_ALERTA
    elif isinstance(p1h, (int, float)) and p1h >= LLUVIA_1H_ALERTA:
        # lluvia intensa puntual: el valor y el umbral son los de la última hora
        nivel, umbral, valor = "alerta", LLUVIA_1H_ALERTA, p1h
    if not nivel:
        return None
    return {
        "tipo": "lluvia",
        "referencia": referencia_lluvia(cod, estacion),
        "zona": zona,
        "nivel": nivel,
        "detalle": f"Acumulado 24h {acc24} mm; última hora {p1h} mm",
        "valor": valor,
        "umbral": umbral,
    }
