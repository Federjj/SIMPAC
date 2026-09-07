"""
Conector NOAA / CPC — ONI (Oceanic Niño Index), contexto ENSO global.

  https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
  columnas: SEAS  YR  TOTAL  ANOM   (ANOM = ONI, base 1991-2020)
"""
from __future__ import annotations

from dataclasses import dataclass

from . import _http

URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"


@dataclass
class PuntoONI:
    temporada: str   # DJF, JFM, ...
    anio: int
    sst: float       # TOTAL
    anom: float      # ONI

    @property
    def fase(self) -> str:
        if self.anom >= 0.5:
            return "El Niño"
        if self.anom <= -0.5:
            return "La Niña"
        return "Neutro"


def oni() -> list[PuntoONI]:
    texto = _http.get(URL)
    out: list[PuntoONI] = []
    for linea in texto.splitlines()[1:]:  # salta la cabecera
        partes = linea.split()
        if len(partes) < 4:
            continue
        try:
            out.append(PuntoONI(partes[0], int(partes[1]), float(partes[2]), float(partes[3])))
        except ValueError:
            continue
    return out


def ultimo() -> PuntoONI | None:
    serie = oni()
    return serie[-1] if serie else None
