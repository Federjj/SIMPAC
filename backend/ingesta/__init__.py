"""
Ingesta horaria a Supabase: recolectar() baja de las fuentes y guardar() escribe.

La corre el worker Celery cada hora (ver celery_app.py). Para una corrida suelta,
dentro del contenedor worker (tiene SUPABASE_DB_URL):
    docker compose run --rm worker python -m backend.ingesta
"""
from __future__ import annotations

import logging

from backend.ingesta import guardar, recolectar

log = logging.getLogger(__name__)


def run() -> dict:
    resumen = guardar.guardar(recolectar.recolectar())
    if resumen["fallas"]:
        log.warning("Ingesta con fallas parciales: %s", resumen)
    else:
        log.info("Ingesta OK: %s", resumen)
    return resumen
