"""
Caché en Redis + lectura de Supabase, todo ASÍNCRONO.
La API sirve un "snapshot" cacheado para que muchos usuarios no golpeen Supabase
en cada request. Las consultas a Supabase se hacen en paralelo con asyncio.gather.
"""
from __future__ import annotations

import asyncio
import json
import os

import httpx
import redis.asyncio as aioredis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
SUPA_URL = os.environ.get("SUPABASE_URL", "")
KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
_H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
TTL = int(os.environ.get("SNAPSHOT_TTL", "300"))

_redis = aioredis.from_url(REDIS_URL, decode_responses=True)


async def _supa(client: httpx.AsyncClient, path: str):
    r = await client.get(f"{SUPA_URL}/rest/v1/{path}", headers=_H, timeout=20)
    r.raise_for_status()
    return r.json()


async def refresh_snapshot() -> dict:
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
    await _redis.set("snapshot", json.dumps(data, ensure_ascii=False), ex=TTL)
    return {"cached": True, "caudales": len(caudales), "en_alerta": len(en_alerta)}


async def get_snapshot() -> dict:
    cached = await _redis.get("snapshot")
    if cached:
        return json.loads(cached)
    await refresh_snapshot()
    return json.loads(await _redis.get("snapshot"))
