"""
Conector IGP — Índice Costero El Niño (ICEN).

Archivo de texto plano, servidor HTTP-only (met.igp.gob.pe:80). El backend debe
descargarlo (una web HTTPS no puede hacer fetch a http por mixed-content).

  http://met.igp.gob.pe/datos/ICEN.txt   -> columnas: yy  mm  ICEN  (líneas '%' = comentario)
"""
from __future__ import annotations

from dataclasses import dataclass

from . import _http

URL = "http://met.igp.gob.pe/datos/ICEN.txt"

# Categorías operacionales del ICEN (ENFEN, 2024) para el semáforo del titular.
_CATS = [
    (-99.0, -1.4, "Frío fuerte"),
    (-1.4, -1.0, "Frío moderado"),
    (-1.0, -0.4, "Frío débil"),
    (-0.4, 0.4, "Neutro"),
    (0.4, 1.0, "Cálido débil"),
    (1.0, 1.7, "Cálido moderado"),
    (1.7, 3.0, "Cálido fuerte"),
    (3.0, 99.0, "Cálido extraordinario"),
]


def categoria(icen: float) -> str:
    for lo, hi, nombre in _CATS:
        if lo <= icen < hi:
            return nombre
    return "Desconocido"


@dataclass
class PuntoICEN:
    anio: int
    mes: int
    valor: float

    @property
    def categoria(self) -> str:
        return categoria(self.valor)


def icen() -> list[PuntoICEN]:
    texto = _http.get(URL)
    out: list[PuntoICEN] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("%"):
            continue
        partes = linea.split()
        if len(partes) < 3:
            continue
        try:
            out.append(PuntoICEN(int(partes[0]), int(partes[1]), float(partes[2])))
        except ValueError:
            continue
    return out


def ultimo() -> PuntoICEN | None:
    serie = icen()
    return serie[-1] if serie else None
