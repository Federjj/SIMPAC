"""
Panorama cacheado en Redis que sirve la API (GET /api/snapshot), todo asíncrono.

Así muchos usuarios no golpean Supabase en cada request: el worker lo refresca
cada 5 min y la API lo lee de Redis. Las consultas a Supabase van en paralelo
(asyncio.gather) y solo leen con la clave pública, igual que el frontend.

Se guardan dos copias: "snapshot" (vence a los SNAPSHOT_TTL segundos) y
"snapshot:ultimo" (no vence). Si la primera venció y Supabase no responde, se
sirve la última buena en vez de un error.

Nota sobre el cliente Redis y los event loops: un cliente redis.asyncio ata su
pool de conexiones al loop donde se usa por primera vez. El worker corre cada
tarea con asyncio.run(), que crea y CIERRA un loop nuevo en cada corrida, así que
no se puede compartir un cliente global entre corridas ("Event loop is closed").
  - worker / uso suelto: cliente efímero por corrida, que se cierra al terminar.
  - API (uvicorn, loop persistente): inyecta un cliente de larga vida (app.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
import redis.asyncio as aioredis

from backend.config import ajustes

log = logging.getLogger(__name__)

CLAVE = "snapshot"
CLAVE_RESPALDO = "snapshot:ultimo"
RESPALDO_TTL = 60   # segundos que se sirve el respaldo antes de reintentar Supabase


def new_redis() -> aioredis.Redis:
    """Crea un cliente Redis nuevo. Quien lo crea debe cerrarlo (await .aclose())."""
    return aioredis.from_url(ajustes().redis_url, decode_responses=True)


@asynccontextmanager
async def _redis_ctx(client: aioredis.Redis | None):
    """Usa el cliente inyectado (persistente) o crea uno efímero y lo cierra al salir."""
    if client is not None:
        yield client
        return
    cli = new_redis()
    try:
        yield cli
    finally:
        await cli.aclose()


async def _leer(c: httpx.AsyncClient, tabla: str, select: str, **filtros: str) -> list[dict]:
    r = await c.get(f"/{tabla}", params={"select": select, **filtros})
    r.raise_for_status()
    return r.json()


async def _armar() -> dict:
    cfg = ajustes()
    clave = cfg.supabase_publishable_key
    async with httpx.AsyncClient(
        base_url=f"{cfg.supabase_url}/rest/v1",
        headers={"apikey": clave, "Authorization": f"Bearer {clave}"},
        timeout=20,
    ) as c:
        indices, caudales, alertas = await asyncio.gather(
            _leer(c, "indice", "fuente,periodo,valor,categoria"),
            # caudal_actual = última lectura de cada estación (no el historial)
            _leer(c, "caudal_actual",
                  "estacion,rio,departamento,fecha,hora,valor,unidad,tendencia,estado,lat,lon"),
            _leer(c, "alerta", "tipo,referencia,zona,nivel,detalle,valor,umbral,ts",
                  vigente="eq.true", order="ts.desc"),
        )
    en_alerta = [c["estacion"] for c in caudales if c.get("estado") in ("alerta", "emergencia")]
    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "indices": indices,
        "caudales": caudales,
        "alertas": alertas,
        "resumen": {"caudales": len(caudales), "en_alerta": en_alerta, "alertas": len(alertas)},
    }


async def _guardar(r: aioredis.Redis, data: dict) -> None:
    texto = json.dumps(data, ensure_ascii=False)
    await r.set(CLAVE, texto, ex=ajustes().snapshot_ttl)
    await r.set(CLAVE_RESPALDO, texto)


async def refresh_snapshot(client: aioredis.Redis | None = None) -> dict:
    """Trae de Supabase y guarda el snapshot en Redis. Devuelve un resumen corto."""
    data = await _armar()
    async with _redis_ctx(client) as r:
        await _guardar(r, data)
    return {"cached": True, **data["resumen"], "en_alerta": len(data["resumen"]["en_alerta"])}


async def get_snapshot(client: aioredis.Redis | None = None) -> dict:
    async with _redis_ctx(client) as r:
        cached = await r.get(CLAVE)
        if cached:
            return json.loads(cached)
        try:
            data = await _armar()
        except httpx.HTTPError as e:
            respaldo = await r.get(CLAVE_RESPALDO)
            if respaldo is None:
                raise
            log.warning("Supabase no respondió (%s); se sirve el último snapshot", e)
            # se re-cachea un rato para que cada request no vuelva a esperar el timeout
            await r.set(CLAVE, respaldo, ex=RESPALDO_TTL)
            return json.loads(respaldo)
        await _guardar(r, data)
        return data
