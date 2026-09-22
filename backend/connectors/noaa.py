"""
Conector NOAA / CPC — RONI (Relative Oceanic Niño Index), contexto ENSO global.

Desde febrero de 2026 el CPC vigila El Niño / La Niña con el RONI (la anomalía del
Pacífico central relativa al calentamiento de todo el trópico) en vez del ONI clásico.
Por eso hoy el RONI puede ser bastante menor que el ONI (jun-ago 2026: 1.36 vs 1.80).

  https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt
  columnas: SEAS  YR  ANOM   (el CPC puede corregir un valor hasta 2 meses después)
"""
from __future__ import annotations

from dataclasses import dataclass

from . import _http

URL = "https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt"

# Magnitud según el CPC (en pasos de 0.5); para La Niña se dice en femenino.
_MAGNITUDES = [(2.0, "muy fuerte"), (1.5, "fuerte"), (1.0, "moderado"), (0.5, "débil")]


def fase(anom: float) -> str:
    """'El Niño moderado', 'La Niña débil' o 'Neutro'."""
    if -0.5 < anom < 0.5:
        return "Neutro"
    magnitud = next(m for umbral, m in _MAGNITUDES if abs(anom) >= umbral)
    if anom < 0:
        return "La Niña " + magnitud.replace("moderado", "moderada")
    return "El Niño " + magnitud


@dataclass
class PuntoRONI:
    temporada: str   # trimestre móvil: DJF, JFM, ..., JJA, ..., NDJ
    anio: int
    anom: float      # RONI

    @property
    def fase(self) -> str:
        return fase(self.anom)


def roni() -> list[PuntoRONI]:
    texto = _http.get(URL)
    out: list[PuntoRONI] = []
    for linea in texto.splitlines()[1:]:  # salta la cabecera
        partes = linea.split()
        if len(partes) < 3:
            continue
        try:
            out.append(PuntoRONI(partes[0], int(partes[1]), float(partes[-1])))
        except ValueError:
            continue
    return out


def ultimo() -> PuntoRONI | None:
    serie = roni()
    return serie[-1] if serie else None
