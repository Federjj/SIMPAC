"""
Worker de SIMPAC — Celery + Redis (cola/broker) con beat (programador).

Tareas:
  - ingesta: baja datos de las fuentes y los escribe en Supabase (cada hora).
  - enfen: busca el último comunicado oficial del ENFEN (PDF) y lo guarda (cada 6 h).
  - avisos: avisos oficiales de SENAMHI como áreas y sus alertas por departamento (cada hora).
  - lluvia_nacional: lluvia de la última hora en ~200 estaciones de SENAMHI de todo el país
    (cada 30 min: las estaciones reportan cada hora pero no todas a la misma hora).
  - pronostico: pronóstico oficial de SENAMHI por localidad, ~277 localidades con 3 a 5 días
    (cada hora: SENAMHI lo renueva una vez por día hábil, de noche).
  - nowcast: nowcasting de lluvia de SENAMHI para ahora, +1 h y +2 h, EXPERIMENTAL (cada
    10 min, como sale el producto; una corrida atrasada más de 9 min se descarta).
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
    "pronostico": {"task": "backend.celery_app.pronostico", "schedule": 3600.0},
    # expires: si la cola se atrasa (el worker ocupado con otra tarea), no se juntan corridas
    # viejas del nowcasting; a los 9 min ya viene la siguiente
    "nowcast": {"task": "backend.celery_app.nowcast", "schedule": 600.0, "options": {"expires": 540}},
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


# Límites de tiempo: la GeoServer y la web de SENAMHI a veces se cuelgan. El soft lanza una
# excepción dentro de la tarea (en una descarga queda como falla en el latido; en plena
# transacción, esta se revierte) y el duro mata el proceso si aun así no terminó.
@celery.task(name="backend.celery_app.pronostico", soft_time_limit=300, time_limit=360)
def pronostico():
    from backend.ingesta.pronostico import actualizar
    return actualizar()


# 240 s: backend/ingesta/nowcast.py deja de pedir horizontes a los 90 s (PLAZO_S) para que el
# latido se escriba siempre dentro de este límite.
@celery.task(name="backend.celery_app.nowcast", soft_time_limit=240, time_limit=300)
def nowcast():
    from backend.ingesta.nowcast import actualizar
    return actualizar()


@celery.task(name="backend.celery_app.refresh_cache")
def refresh_cache():
    from backend.snapshot import refresh_snapshot
    return asyncio.run(refresh_snapshot())


@beat_init.connect
def _al_arrancar(**_):
    # beat no guarda su programación entre despliegues (el contenedor se recrea en cada
    # 'docker compose up --build'): sin esto la tarea 'enfen' correría recién 6 h después
    # de cada despliegue, y en una BD nueva el panel quedaría sin estado ENFEN ni avisos (ni
    # pronóstico: su primera corrida programada sería 1 h después).
    ingesta.delay()
    enfen.delay()
    avisos.delay()
    lluvia_nacional.delay()
    pronostico.delay()
    nowcast.delay()
