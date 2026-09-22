"""
API de SIMPAC — FastAPI asíncrono.

Sirve un snapshot cacheado en Redis (rápido con muchos usuarios); el frontend
sigue leyendo Supabase directo para lo detallado. Es de solo lectura: el refresco
lo hace el worker (tarea refresh_cache), no hay endpoint público para forzarlo.
"""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.snapshot import get_snapshot, new_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Un solo cliente Redis de larga vida, atado al loop de uvicorn.
    app.state.redis = new_redis()
    try:
        yield
    finally:
        await app.state.redis.aclose()


app = FastAPI(title="SIMPAC API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True, "service": "simpac-api"}


@app.get("/api/snapshot")
async def snapshot():
    """Contexto El Niño + último caudal por estación + alertas vigentes (cacheado en Redis)."""
    try:
        return await get_snapshot(client=app.state.redis)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail="Supabase no disponible y aún no hay snapshot") from e
