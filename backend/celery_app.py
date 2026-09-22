"""
Worker de SIMPAC — Celery + Redis (cola/broker) con beat (programador).

Tareas:
  - ingesta: baja datos de las fuentes y los escribe en Supabase (cada hora).
  - refresh_cache: refresca el snapshot en Redis (cada 5 min).

Los nombres de las tareas son fijos a propósito: beat las encola por nombre, así
que moverlas de módulo no rompe lo programado.

Correr (lo hace docker-compose):
  celery -A backend.celery_app worker --beat --loglevel=info
"""
import asyncio

from celery import Celery

from backend.config import ajustes

_redis = ajustes().redis_url
celery = Celery("simpac", broker=_redis, backend=_redis)
celery.conf.update(timezone="America/Lima", enable_utc=False)
celery.conf.beat_schedule = {
    "ingesta-horaria": {"task": "backend.celery_app.ingesta", "schedule": 3600.0},
    "refresh-cache": {"task": "backend.celery_app.refresh_cache", "schedule": 300.0},
}


@celery.task(name="backend.celery_app.ingesta")
def ingesta():
    from backend.ingesta import run
    return run()


@celery.task(name="backend.celery_app.refresh_cache")
def refresh_cache():
    from backend.snapshot import refresh_snapshot
    return asyncio.run(refresh_snapshot())
