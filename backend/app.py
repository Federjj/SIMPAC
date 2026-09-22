"""
API de SIMPAC — FastAPI ASINCRONO.
Sirve un snapshot cacheado en Redis (rapido con muchos usuarios); el frontend
puede seguir leyendo Supabase directo para lo detallado.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.cache import get_snapshot, new_redis, refresh_snapshot


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Un solo cliente Redis de larga vida, atado al loop de uvicorn.
    app.state.redis = new_redis()
    try:
        yield
    finally:
        await app.state.redis.aclose()


app = FastAPI(title="SIMPAC API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True, "service": "simpac-api"}


@app.get("/api/snapshot")
async def snapshot():
    """Contexto El Nino + caudales + resumen (cacheado en Redis)."""
    return await get_snapshot(client=app.state.redis)


@app.post("/api/refresh")
async def refresh():
    """Fuerza refresco de la cache (lo usa el worker; util para debug)."""
    return await refresh_snapshot(client=app.state.redis)
