"""
Conector IGP — Índice Costero El Niño (ICEN).

Archivo de texto plano, servidor HTTP-only (met.igp.gob.pe:80). El backend debe
descargarlo (una web HTTPS no puede hacer fetch a http por mixed-content).

  http://met.igp.gob.pe/datos/ICEN.txt   -> columnas: yy  mm  ICEN  (líneas '%' = comentario)

Ojo: el IGP puede atrasarse (en sep-2026 seguía en mayo) mientras el ENFEN ya publicó
meses más nuevos en la Tabla 3 de su Informe Técnico (connectors/enfen.py); la tabla indice
guarda el más reciente de los dos.

El archivo no trae categoría: la de cada mes la calcula SIMPAC con categoria() (cortes de la
Nota Técnica ENFEN 01-2024). La oficial es la de la tabla del Informe Técnico ENFEN.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import _http
from .senamhi import HORA_PERU

URL = "http://met.igp.gob.pe/datos/ICEN.txt"


def categoria(icen: float) -> str:
    """
    Condición del ICEN según la Nota Técnica ENFEN 01-2024 (la que citan los
    comunicados oficiales de 2026). Los cortes antiguos (2012: 0.4/1.0/1.7/3.0)
    clasificaban mal, p. ej. +1.98 salía 'fuerte' y es 'moderada'.
      neutra -0.7..+0.5 · débil hasta +1.3 · moderada hasta +2.1 · fuerte hasta +3.5
    En el borde +2.1 los comunicados se contradicen (CO 10-2026: moderada <= 2.1;
    CO 12-2026: fuerte >= 2.1): aquí +2.1 es moderada. Para las condiciones frías el
    ENFEN usa percentiles sin cortes numéricos publicados: se dice solo 'Fría'.
    """
    if icen > 3.5:
        return "Cálida extraordinaria"
    if icen > 2.1:
        return "Cálida fuerte"
    if icen > 1.3:
        return "Cálida moderada"
    if icen > 0.5:
        return "Cálida débil"
    if icen >= -0.7:
        return "Neutra"
    return "Fría"


def ultimo_mes_posible(ahora: datetime | None = None) -> tuple[int, int]:
    """
    (año, mes) más reciente que puede traer el ICEN.txt: el anterior al mes actual en hora
    de Perú (`ahora` con zona horaria; por defecto, ya). El ICEN de un mes es una media
    corrida de 3 meses y sale después (en la práctica 2 o más meses atrás). Un mes posterior
    es una fila dañada o alterada (el archivo se baja por http) y hay que descartarlo: en
    indice el ICEN nunca retrocede de mes y quedaría fijo en ese mes futuro.
    """
    hoy = (ahora or datetime.now(HORA_PERU)).astimezone(HORA_PERU).date()
    return (hoy.year, hoy.month - 1) if hoy.month > 1 else (hoy.year - 1, 12)


@dataclass
class PuntoICEN:
    anio: int
    mes: int
    valor: float

    @property
    def categoria(self) -> str:
        """Calculada por SIMPAC (el ICEN.txt no la trae): ver categoria()."""
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


def ultimo(ahora: datetime | None = None) -> PuntoICEN | None:
    """La última fila del ICEN.txt, sin las de meses posteriores a ultimo_mes_posible()."""
    tope = ultimo_mes_posible(ahora)
    serie = [p for p in icen() if (p.anio, p.mes) <= tope]
    return serie[-1] if serie else None
