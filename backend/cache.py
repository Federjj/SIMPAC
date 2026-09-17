"""
Cache en Redis + lectura de Supabase, todo ASINCRONO.
La API sirve un "snapshot" cacheado para que muchos usuarios no golpeen Supabase
en cada request. Las consultas a Supabase se hacen en paralelo con asyncio.gather.

Nota importante sobre el cliente Redis y los event loops:
un cliente redis.asyncio ata su pool de conexiones al event loop donde se usa por
primera vez. El worker (Celery) corre cada tarea con asyncio.run(), que crea y
CIERRA un loop nuevo en cada corrida; por eso NO se puede compartir un cliente
global entre corridas (daria "Event loop is closed"). Solucion:
  - worker / uso suelto: se crea un cliente efimero por corrida y se cierra.
  - API (uvicorn, loop persistente): inyecta un cliente de larga vida (ver app.py).
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
SUPA_URL = os.environ.get("SUPABASE_URL", "")
KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
_H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
TTL = int(os.environ.get("SNAPSHOT_TTL", "300"))


def new_redis() -> aioredis.Redis:
    """Crea un cliente Redis nuevo. Quien lo crea debe cerrarlo (await .aclose())."""
    return aioredis.from_url(REDIS_URL, decode_responses=True)


@asynccontextmanager
async def _redis_ctx(client: aioredis.Redis | None):
    """Usa el cliente inyectado (persistente) o crea uno efimero y lo cierra al salir."""
    if client is not None:
        yield client
        return
    cli = new_redis()
    try:
        yield cli
    finally:
        await cli.aclose()


async def _supa(client: httpx.AsyncClient, path: str):
    r = await client.get(f"{SUPA_URL}/rest/v1/{path}", headers=_H, timeout=20)
    r.raise_for_status()
    return r.json()


async def refresh_snapshot(client: aioredis.Redis | None = None) -> dict:
    """Trae de Supabase (en paralelo) y guarda el snapshot en Redis."""
    async with httpx.AsyncClient() as c:
        indices, caudales = await asyncio.gather(
            _supa(c, "indice?select=fuente,periodo,valor,categoria"),
            _supa(c, "lectura_caudal?select=estacion,rio,departamento,valor,unidad,estado,lat,lon"),
        )
    en_alerta = [c["estacion"] for c in caudales if c.get("estado") in ("alerta", "emergencia")]
    data = {
        "indices": indices,
        "caudales": caudales,
        "resumen": {"caudales": len(caudales), "en_alerta": en_alerta},
    }
    async with _redis_ctx(client) as r:
        await r.set("snapshot", json.dumps(data, ensure_ascii=False), ex=TTL)
    return {"cached": True, "caudales": len(caudales), "en_alerta": len(en_alerta)}


async def get_snapshot(client: aioredis.Redis | None = None) -> dict:
    async with _redis_ctx(client) as r:
        cached = await r.get("snapshot")
        if cached:
            return json.loads(cached)
        await refresh_snapshot(client=r)
        return json.loads(await r.get("snapshot"))
