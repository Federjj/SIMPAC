"""
API de SIMPAC — FastAPI ASÍNCRONO.
Sirve un snapshot cacheado en Redis (rápido con muchos usuarios); el frontend
puede seguir leyendo Supabase directo para lo detallado.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.cache import get_snapshot, refresh_snapshot

app = FastAPI(title="SIMPAC API", version="0.1.0")
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
    """Contexto El Niño + caudales + resumen (cacheado en Redis)."""
    return await get_snapshot()


@app.post("/api/refresh")
async def refresh():
    """Fuerza refresco de la cache (lo usa el worker; util para debug)."""
    return await refresh_snapshot()
