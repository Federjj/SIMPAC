"""Conectores de fuentes de datos de SIMPAC.

Un módulo por organismo; cada uno normaliza su fuente a estructuras simples.
Ver docs/README-tecnico.md para el detalle de cada endpoint.
"""
from . import ana, igp, noaa, senamhi  # noqa: F401

__all__ = ["senamhi", "ana", "igp", "noaa"]
