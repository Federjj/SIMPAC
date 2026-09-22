"""
Cargador de los mapas históricos de eventos El Niño (IDESEP/SENAMHI) a Supabase.

Son mapas estáticos (no cambian), por eso no van en la ingesta horaria: se cargan
a mano cuando haga falta. Es la única vía que escribe estos mapas en la tabla mapa.

Por defecto es una prueba en seco: descarga y muestra el resumen, sin escribir.
Con --aplicar hace upsert por uuid (idempotente: correrlo dos veces no duplica filas).

Se corre dentro del contenedor worker, que ya tiene geopandas y SUPABASE_DB_URL:
    docker compose run --rm worker python -m backend.mapas.cargar_fen
    docker compose run --rm worker python -m backend.mapas.cargar_fen --aplicar

Opciones:
    --simplificar 0.005   simplifica geometrías (grados; ~550 m) para aligerar el peso
    --decimales 5         redondea coordenadas
    --exportar DIR        guarda cada GeoJSON en DIR (para abrirlo en visor_geojson.html)
    --catalogo            lista el catálogo IDESEP (uuid + título) y sale

Para --exportar dentro de Docker hay que montar una carpeta del host, si no los
archivos se pierden al borrar el contenedor (--rm). En PowerShell:
    docker compose run --rm -v "${PWD}/backend/mapas:/out" worker python -m backend.mapas.cargar_fen --exportar /out
(en Git Bash, anteponer MSYS_NO_PATHCONV=1 para que no reescriba /out).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass

if __package__ in (None, ""):   # permite también: python backend/mapas/cargar_fen.py
    sys.path.insert(0, __file__.rsplit("backend", 1)[0])

from backend.connectors import idesep
from backend.db import conectar

log = logging.getLogger("cargar_fen")

# variable='FEN' distingue estos mapas históricos del mapa mensual
# (variable='precipitacion'), que es el que muestra hoy el frontend.
VARIABLE = "FEN"
FUENTE = "SENAMHI/IDESEP"


@dataclass(frozen=True)
class EventoFEN:
    titulo: str             # título exacto del registro en el catálogo IDESEP
    periodo: str            # duración del evento, no un mes
    uuid: str | None = None  # fijo si ya se conoce; si falta se busca por título


# Los uuids fijos son los que ya están cargados en la BD (verificados con el catálogo).
EVENTOS_FEN = [
    EventoFEN("Anomalías de Precipitación - Evento El Niño 82 - 83", "1982-1983",
              "5e888752-5eea-487f-91bc-f3281489bb33"),
    EventoFEN("Anomalías de Precipitación - Evento El Niño 97 - 98", "1997-1998",
              "25c9f90e-d845-43f0-ad6c-9aa32dcecf7c"),
    EventoFEN("Anomalías de Precipitación - Evento El Niño Costero 2017", "2017",
              "d57bba7e-cbb4-4f2d-9d8e-7bd013dae5d9"),
    EventoFEN("Anomalías de Precipitación - Evento El Niño 2023 - 2024", "2023-2024",
              "d6e9a47a-2b78-4f8e-ad07-2c3e6f8f7b9e"),
    EventoFEN("Anomalías de Precipitación - Evento El Niño Costero 2023", "2023",
              "85118c06-f2bb-46a8-9432-bb0e0a67be8e"),
    # Para sumar otro evento basta el título exacto (ver --catalogo): el uuid se resuelve solo.
]

UPSERT = (
    "insert into mapa (uuid, titulo, variable, periodo, fuente, geojson) "
    "values (%s, %s, %s, %s, %s, %s::jsonb) "
    "on conflict (uuid) do update set titulo=excluded.titulo, variable=excluded.variable, "
    "periodo=excluded.periodo, fuente=excluded.fuente, geojson=excluded.geojson, ts_captura=now()"
)


def _resumen(geojson: str) -> str:
    data = json.loads(geojson)
    feats = data.get("features", [])
    tipos = sorted({(f.get("geometry") or {}).get("type", "?") for f in feats})
    return f"{len(feats)} features, {'/'.join(tipos)}, {len(geojson) / 1e6:.1f} MB"


def _resolver(eventos: list[EventoFEN]) -> tuple[list[tuple[EventoFEN, str]], list[str]]:
    """(eventos con uuid, títulos que no se encontraron en el catálogo)."""
    faltan = [e for e in eventos if not e.uuid]
    registros = idesep.listar_registros() if faltan else []
    resueltos, no_encontrados = [], []
    for e in eventos:
        uuid = e.uuid or idesep.buscar_uuid(e.titulo, registros)
        if uuid:
            resueltos.append((e, uuid))
        else:
            log.error("No está en el catálogo IDESEP: %s", e.titulo)
            no_encontrados.append(e.titulo)
    return resueltos, no_encontrados


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Carga los mapas históricos de eventos El Niño a Supabase.")
    ap.add_argument("--aplicar", action="store_true", help="escribe en la BD (sin esto es prueba en seco)")
    ap.add_argument("--simplificar", type=float, default=None, metavar="TOL")
    ap.add_argument("--decimales", type=int, default=None, metavar="N")
    ap.add_argument("--exportar", default=None, metavar="DIR")
    ap.add_argument("--catalogo", action="store_true", help="lista el catálogo IDESEP y sale")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.catalogo:
        for r in idesep.listar_registros():
            print(f"{r.uuid}  {r.titulo}")
        return 0

    listos: list[tuple[EventoFEN, str, str]] = []
    resueltos, fallidos = _resolver(EVENTOS_FEN)
    for evento, uuid in resueltos:
        try:
            geojson = idesep.geojson_de_registro(uuid, args.simplificar, args.decimales)
        except Exception as e:  # un mapa caído no debe frenar a los demás
            log.error("No se pudo obtener %s (%s): %s", evento.periodo, uuid, e)
            fallidos.append(evento.titulo)
            continue
        log.info("OK %s | %s | %s", evento.periodo, uuid, _resumen(geojson))
        listos.append((evento, uuid, geojson))
        if args.exportar:
            os.makedirs(args.exportar, exist_ok=True)
            ruta = os.path.join(args.exportar, f"fen_{evento.periodo}.geojson")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(geojson)

    if args.aplicar and listos:
        try:
            with conectar() as conn, conn.cursor() as cur:
                for evento, uuid, geojson in listos:
                    cur.execute(UPSERT, (uuid, evento.titulo, VARIABLE, evento.periodo, FUENTE, geojson))
        except RuntimeError as e:   # falta SUPABASE_DB_URL o psycopg
            log.error("%s Corre el cargador dentro del contenedor worker.", e)
            return 2
        log.info("Guardados %d mapas en la tabla mapa.", len(listos))
    elif not args.aplicar:
        log.info("Prueba en seco: no se escribió nada. Usa --aplicar para guardar.")

    if fallidos:
        log.error("Fallaron %d mapas: %s", len(fallidos), "; ".join(fallidos))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
