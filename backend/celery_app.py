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
  - rios: avisos hidrológicos de SENAMHI (lista del país; el detalle solo para los ríos vigilados,
    hoy el Mashcón) para las señales de la zona que un río podría afectar (cada hora).
  - titular: titular en lenguaje claro por departamento (titular_zona) a partir de los datos
    oficiales ya guardados; con clave de API lo redacta un modelo, si no, reglas fijas (cada 30 min;
    solo llama al modelo si cambiaron los insumos del departamento).
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
    "rios": {"task": "backend.celery_app.rios", "schedule": 3600.0},
    "titular": {"task": "backend.celery_app.titular", "schedule": 1800.0},
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


# 240 s: backend/ingesta/rios.py deja de pedir detalles a los 100 s (PLAZO_S) para que el
# latido se escriba siempre dentro de este límite.
@celery.task(name="backend.celery_app.rios", soft_time_limit=240, time_limit=300)
def rios():
    from backend.ingesta.rios import actualizar
    return actualizar()


# 120 s: backend/ingesta/titular.py deja de pedir al modelo a los 90 s (PLAZO_S); lo que falte
# sale por reglas o conserva el titular anterior, y el latido se escribe siempre.
@celery.task(name="backend.celery_app.titular", soft_time_limit=120, time_limit=180)
def titular():
    from backend.ingesta.titular import actualizar
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
    rios.delay()
    # countdown: el titular resume lo que las otras tareas acaban de escribir (avisos, lluvia, ríos)
    titular.apply_async(countdown=300)


# Avisador push (HU-20, backend/ingesta/push.py): cada 5 min lee titular_zona y manda por FCM solo
# los cambios a alerta/emergencia y la vuelta a la calma. 60 s: push.py deja de enviar a los 40 s
# (PLAZO_S) para que el latido se escriba siempre; sin FIREBASE_CREDENCIALES solo deja el latido.
@celery.task(name="backend.celery_app.push", soft_time_limit=60, time_limit=90)
def push():
    from backend.ingesta.push import actualizar
    return actualizar()


celery.conf.beat_schedule["push"] = {"task": "backend.celery_app.push", "schedule": 300.0}


@beat_init.connect
def _al_arrancar_push(**_):
    # 420 s: después del titular (300 s), que es lo que el avisador lee
    push.apply_async(countdown=420)
