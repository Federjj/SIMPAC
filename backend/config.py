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
    lluvia_deptos: tuple[str, ...]   # slugs de SENAMHI con lluvia horaria


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
    )
