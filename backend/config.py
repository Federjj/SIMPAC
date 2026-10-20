"""
Configuración de SIMPAC: las variables de entorno se leen aquí y solo aquí.

Se leen al primer uso (no al importar), así los módulos se pueden importar en
pruebas o en la API aunque falte alguna variable que solo usa el worker.
Los conectores NO importan este módulo: siguen siendo independientes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Ajustes:
    redis_url: str
    supabase_url: str
    supabase_publishable_key: str
    supabase_db_url: str | None      # secreto: solo lo recibe el worker
    snapshot_ttl: int                # segundos; mayor que el refresco del beat (300 s)
    lluvia_deptos: tuple[str, ...]   # slugs de SENAMHI; solo decide qué series de 24 h guarda
                                     # la ingesta (lectura_lluvia), no las alertas
    # Titular interpretado (backend/ingesta/titular.py). Sin clave, el titular sale por reglas
    # fijas en Python (origen 'reglas'); con clave, lo redacta el modelo a partir de las cifras.
    llm_key: str                     # SIMPAC_LLM_KEY o, si no está, ANTHROPIC_API_KEY (solo el worker)
    llm_modelo: str                  # SIMPAC_LLM_MODELO; por defecto el Haiku más barato que acepta temperature
    # Orígenes a los que la API responde (CORS, backend/app.py): la web servida por nginx, Vite en
    # desarrollo y la app Android (Capacitor sirve desde https://localhost / capacitor://localhost).
    cors_origenes: tuple[str, ...]   # SIMPAC_CORS_ORIGENES, separados por coma


@lru_cache
def ajustes() -> Ajustes:
    return Ajustes(
        redis_url=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_publishable_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
        supabase_db_url=os.environ.get("SUPABASE_DB_URL") or None,
        snapshot_ttl=int(os.environ.get("SNAPSHOT_TTL", "900")),
        lluvia_deptos=tuple(
            d.strip() for d in os.environ.get("SIMPAC_LLUVIA_DEPTS", "cajamarca").split(",") if d.strip()
        ),
        llm_key=(os.environ.get("SIMPAC_LLM_KEY") or os.environ.get("ANTHROPIC_API_KEY") or "").strip(),
        llm_modelo=(os.environ.get("SIMPAC_LLM_MODELO") or "").strip() or LLM_MODELO_DEFECTO,
        cors_origenes=origenes_cors(os.environ.get("SIMPAC_CORS_ORIGENES")),
    )


# Haiku 4.5 (id con fecha, vigente): acepta temperature=0, que el titular exige. Haiku 5.5 es más
# barato pero rechaza (400) cualquier temperature distinta de la de fábrica.
LLM_MODELO_DEFECTO = "claude-haiku-4-5-20251001"
CORS_ORIGENES_DEFECTO = ("http://localhost:8080", "http://localhost:5173", "https://localhost", "capacitor://localhost")


def origenes_cors(texto: str | None) -> tuple[str, ...]:
    """
    'https://simpac.pe, http://localhost:8080' -> ('https://simpac.pe', 'http://localhost:8080').
    Vacío o solo comas: los de desarrollo y la app (CORS_ORIGENES_DEFECTO). Un '*' se descarta:
    la API ya no se abre a cualquier origen (plan de seguridad); se quita la barra final.
    """
    if texto is None or not texto.strip():
        return CORS_ORIGENES_DEFECTO
    vistos: list[str] = []
    for o in texto.split(","):
        o = o.strip().rstrip("/")
        if o and o != "*" and o not in vistos:
            vistos.append(o)
    return tuple(vistos) or CORS_ORIGENES_DEFECTO
