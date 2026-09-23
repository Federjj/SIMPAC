"""
Panorama cacheado en Redis que sirve la API (GET /api/snapshot), todo asíncrono.

Así muchos usuarios no golpean Supabase en cada request: el worker lo refresca
cada 5 min y la API lo lee de Redis. Las consultas a Supabase van en paralelo
(asyncio.gather) y solo leen con la clave pública, igual que el frontend.

Se guardan dos copias: "snapshot" (vence a los SNAPSHOT_TTL segundos) y
"snapshot:ultimo" (no vence). Si la primera venció y Supabase no responde, se
sirve la última buena en vez de un error.

Alertas (vista alerta_actual): cada una trae `oficial`. Las de tipo 'lluvia' tienen
oficial=false: una estación midió más lluvia que la referencia de SENAMHI para ese lugar,
no es un aviso. Su `umbral` es de esa estación y se lee con `ventana_h` (1 = mm en la
última hora, 6 = mm en las últimas 6 h). La app o las notificaciones nunca deben tratarlas
como alerta oficial. resumen.alertas cuenta filas (compatibilidad); alertas_oficiales y
lluvia_sobre_referencia las separan.

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

from backend import alerts
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


async def _alertas(c: httpx.AsyncClient) -> list[dict]:
    """
    alerta_actual = las vigentes, sin la lluvia medida de más de 3 h. Si la vista todavía no
    existe (el worker o la API salieron antes que la migración alerta_lluvia_referencia_senamhi,
    PostgREST da 404), las vigentes de la tabla alerta sin las de tipo 'lluvia' (antes de la
    migración ninguna tiene ventana_h, y la vista tampoco las mostraría). Así el snapshot no se
    congela en el respaldo viejo ni falla refresh_snapshot.
    """
    try:
        return await _leer(c, "alerta_actual",
                           "tipo,referencia,zona,nivel,detalle,valor,umbral,ventana_h,ts,lat,lon", order="ts.desc")
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 404:
            raise
    log.warning("Falta la vista alerta_actual (migración pendiente): se leen las alertas de la tabla alerta")
    filas = await _leer(c, "alerta", "tipo,referencia,zona,nivel,detalle,valor,umbral,ts",
                        vigente="eq.true", order="ts.desc")
    return [{**a, "ventana_h": None, "lat": None, "lon": None}   # las mismas claves que la vista
            for a in filas if a["tipo"] != "lluvia"]


async def _armar() -> dict:
    cfg = ajustes()
    clave = cfg.supabase_publishable_key
    async with httpx.AsyncClient(
        base_url=f"{cfg.supabase_url}/rest/v1",
        headers={"apikey": clave, "Authorization": f"Bearer {clave}"},
        timeout=20,
    ) as c:
        indices, caudales, alertas, enfen = await asyncio.gather(
            _leer(c, "indice", "fuente,periodo,valor,categoria,origen"),
            # caudal_actual = última lectura de cada estación (no el historial)
            _leer(c, "caudal_actual",
                  "estacion,rio,departamento,fecha,hora,valor,unidad,umbral_alerta,umbral_emergencia,"
                  "tendencia,estado,lat,lon"),
            _alertas(c),
            _leer(c, "comunicado_enfen", "anio,numero,extraordinario,fecha,estado,proximo,url",
                  order="fecha.desc", limit="1"),
        )
    def bajo(c):   # umbrales de nivel bajo (vaciante): el de emergencia es menor que el de alerta
        ua, ue = c.get("umbral_alerta"), c.get("umbral_emergencia")
        return ua is not None and ue is not None and ue < ua

    for a in alertas:
        a["oficial"] = alerts.es_oficial(a["tipo"])
    activos = [c for c in caudales if c.get("estado") in ("alerta", "emergencia")]
    en_alerta = [c["estacion"] for c in activos if not bajo(c)]      # ríos crecidos
    nivel_bajo = [c["estacion"] for c in activos if bajo(c)]         # ríos demasiado bajos
    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "indices": indices,
        "enfen": enfen[0] if enfen else None,   # último comunicado oficial (estado del Sistema de Alerta)
        "caudales": caudales,
        "alertas": alertas,
        "resumen": {"caudales": len(caudales), "en_alerta": en_alerta, "nivel_bajo": nivel_bajo,
                    "alertas": len(alertas),
                    "alertas_oficiales": sum(1 for a in alertas if a["oficial"]),
                    "lluvia_sobre_referencia": sum(1 for a in alertas if a["tipo"] == "lluvia")},
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
    res = data["resumen"]
    return {"cached": True, **res, "en_alerta": len(res["en_alerta"]), "nivel_bajo": len(res["nivel_bajo"])}


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
