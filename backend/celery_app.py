"""
Worker de SIMPAC — Celery + Redis (cola/broker) con beat (programador).

Tareas:
  - ingesta: baja datos de las fuentes y los escribe en Supabase (cada hora).
  - enfen: busca el último comunicado oficial del ENFEN (PDF) y lo guarda (cada 6 h).
  - avisos: avisos oficiales de SENAMHI como áreas y sus alertas por departamento (cada hora).
  - lluvia_nacional: lluvia de la última hora en ~200 estaciones de SENAMHI de todo el país
    (cada 30 min: las estaciones reportan cada hora pero no todas a la misma hora).
  - refresh_cache: refresca el snapshot en Redis (cada 5 min).

Los nombres de las tareas son fijos a propósito: beat las encola por nombre, así
que moverlas de módulo no rompe lo programado.

Correr (lo hace docker-compose):
  celery -A backend.celery_app worker --beat --loglevel=info
"""
import asyncio

from celery import Celery
from celery.signals import beat_init

from backend.config import ajustes

_redis = ajustes().redis_url
celery = Celery("simpac", broker=_redis, backend=_redis)
celery.conf.update(timezone="America/Lima", enable_utc=False)
celery.conf.beat_schedule = {
    "ingesta-horaria": {"task": "backend.celery_app.ingesta", "schedule": 3600.0},
    "refresh-cache": {"task": "backend.celery_app.refresh_cache", "schedule": 300.0},
    # el comunicado sale cada ~2 semanas: revisar 4 veces al día basta y sobra
    "enfen": {"task": "backend.celery_app.enfen", "schedule": 6 * 3600.0},
    "avisos": {"task": "backend.celery_app.avisos", "schedule": 3600.0},
    "lluvia-nacional": {"task": "backend.celery_app.lluvia_nacional", "schedule": 1800.0},
}


@celery.task(name="backend.celery_app.ingesta")
def ingesta():
    from backend.ingesta import run
    return run()


@celery.task(name="backend.celery_app.enfen")
def enfen():
    from backend.ingesta.enfen import actualizar
    return actualizar()


@celery.task(name="backend.celery_app.avisos")
def avisos():
    from backend.ingesta.avisos import actualizar
    return actualizar()


@celery.task(name="backend.celery_app.lluvia_nacional")
def lluvia_nacional():
    from backend.ingesta.lluvia_nacional import actualizar
    return actualizar()


@celery.task(name="backend.celery_app.refresh_cache")
def refresh_cache():
    from backend.snapshot import refresh_snapshot
    return asyncio.run(refresh_snapshot())


@beat_init.connect
def _al_arrancar(**_):
    # beat no guarda su programación entre despliegues (el contenedor se recrea en cada
    # 'docker compose up --build'): sin esto la tarea 'enfen' correría recién 6 h después
    # de cada despliegue, y en una BD nueva el panel quedaría sin estado ENFEN ni avisos.
    ingesta.delay()
    enfen.delay()
    avisos.delay()
    lluvia_nacional.delay()
