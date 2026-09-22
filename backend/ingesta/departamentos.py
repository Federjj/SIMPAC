"""
Departamentos del Perú: slug del endpoint ?dp= de SENAMHI -> nombre para mostrar.

Las fuentes escriben los nombres cada una a su manera ("Apurimac", "ÁNCASH",
"Madre De Dios"...). nombre_departamento() los lleva todos a una sola forma, así
el filtro por departamento y la zona de las alertas coinciden entre fuentes.
"""
from __future__ import annotations

import re
import unicodedata

# Los 24 departamentos del mapa de estaciones de SENAMHI, con SU slug (verificados
# el 22-09-2026). Un slug mal escrito no da error: SENAMHI devuelve las ~980
# estaciones del país, que quedarían todas con el departamento equivocado.
DEPARTAMENTOS = {
    "amazonas": "Amazonas",
    "ancash": "Áncash",
    "apurimac": "Apurímac",
    "arequipa": "Arequipa",
    "ayacucho": "Ayacucho",
    "cajamarca": "Cajamarca",
    "cusco": "Cusco",
    "huancavelica": "Huancavelica",
    "huanuco": "Huánuco",
    "ica": "Ica",
    "junin": "Junín",
    "la-libertad": "La Libertad",
    "lambayeque": "Lambayeque",
    "lima": "Lima",
    "loreto": "Loreto",
    "madre-de-dios": "Madre de Dios",
    "moquegua": "Moquegua",
    "pasco": "Pasco",
    "piura": "Piura",
    "puno": "Puno",
    "san-martin": "San Martín",
    "tacna": "Tacna",
    "tumbes": "Tumbes",
    "ucayali": "Ucayali",
}


def clave(texto: str) -> str:
    """'Madre De Dios' -> 'madrededios' (sin tildes, espacios, guiones ni mayúsculas)."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sin_tildes.lower())


# El Callao no tiene página propia en SENAMHI, pero ANA sí lo reporta.
_NOMBRES = {clave(n): n for n in [*DEPARTAMENTOS.values(), "Callao"]}


def nombre_departamento(texto: str | None) -> str | None:
    """Nombre canónico ('APURIMAC' -> 'Apurímac'); None si viene vacío."""
    if not texto or not texto.strip():
        return None
    return _NOMBRES.get(clave(texto), texto.strip().title())
