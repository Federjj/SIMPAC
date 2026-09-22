"""
Conexión a Supabase (Postgres) para quien escribe: el worker y los cargadores.

La API no la usa: no recibe SUPABASE_DB_URL y solo lee por la API REST.
Al salir del `with` sin errores se hace commit; si hay una excepción, rollback.
"""
from __future__ import annotations

from contextlib import contextmanager

from backend.config import ajustes


@contextmanager
def conectar():
    dsn = ajustes().supabase_db_url
    if not dsn:
        raise RuntimeError("Falta SUPABASE_DB_URL (solo existe en el worker; ver .env.docker.example).")
    try:
        import psycopg
    except ImportError as e:
        raise RuntimeError('Falta psycopg: pip install "psycopg[binary]"') from e
    with psycopg.connect(dsn) as conn:
        yield conn
