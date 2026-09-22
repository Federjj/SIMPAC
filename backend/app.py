"""
API de SIMPAC — FastAPI ASINCRONO.
Sirve un snapshot cacheado en Redis (rapido con muchos usuarios); el frontend
puede seguir leyendo Supabase directo para lo detallado.
"""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.cache import get_snapshot, new_redis, refresh_snapshot
from backend.connectors import senamhi
from backend.mapas.mapas_dic_subject import map_subjects

load_dotenv()


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


@app.post("/update-fen-events")
async def update_fen_events():
    """
    Busca y actualiza mapas de eventos El Niño en Supabase.
    Elimina mapas antiguos e inserta los nuevos (por UUID).
    """
    try:
        import psycopg
    except ImportError:
        return {"error": "Falta psycopg. Instala: pip install psycopg[binary]"}

    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        return {"error": "SUPABASE_DB_URL no configurada"}

    # Obtener mapas FEN desde el conector SENAMHI
    mapas = senamhi.mapas_fen(map_subjects)
    if not mapas:
        return {"message": "No se encontraron mapas FEN", "count": 0}

    # Insertar en Supabase (DELETE + INSERT)
    try:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            for mapa in mapas:
                # Eliminar si existe
                cur.execute("delete from mapa where uuid = %s", (mapa.uuid,))
                # Insertar nuevo
                cur.execute(
                    "insert into mapa (uuid,titulo,variable,periodo,fuente,geojson) "
                    "values (%s,%s,%s,%s,%s,%s::jsonb)",
                    (mapa.uuid, mapa.titulo, mapa.variable, mapa.periodo, "SENAMHI/IDESEP", mapa.geojson),
                )
            conn.commit()
        return {"message": "OK", "count": len(mapas), "mapas": [m.titulo for m in mapas]}
    except Exception as e:
        return {"error": str(e), "count": 0}
