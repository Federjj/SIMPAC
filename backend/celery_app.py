"""
Worker de SIMPAC — Celery + Redis (cola/broker) con beat (programador).

Tareas:
  - ingesta: baja datos de las fuentes y los escribe en Supabase (cada hora).
  - refresh_cache: refresca el snapshot en Redis (cada 5 min).

Correr (lo hace docker-compose):
  celery -A backend.celery_app worker --beat --loglevel=info
"""
import asyncio
import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery = Celery("simpac", broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(timezone="America/Lima", enable_utc=False)
celery.conf.beat_schedule = {
    "ingesta-horaria": {"task": "backend.celery_app.ingesta", "schedule": 3600.0},
    "refresh-cache": {"task": "backend.celery_app.refresh_cache", "schedule": 300.0},
}


@celery.task(name="backend.celery_app.ingesta")
def ingesta():
    from backend import store_supabase
    return store_supabase.run()


@celery.task(name="backend.celery_app.refresh_cache")
def refresh_cache():
    from backend.cache import refresh_snapshot
    return asyncio.run(refresh_snapshot())
