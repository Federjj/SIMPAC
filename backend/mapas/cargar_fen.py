"""
Cargador de los mapas históricos de eventos El Niño (IDESEP/SENAMHI) a Supabase.

Son mapas estáticos (no cambian), por eso no van en la ingesta horaria: se cargan
a mano cuando haga falta. Es la única vía que escribe estos mapas en la tabla mapa.

Cada registro de IDESEP trae un .zip por trimestre (DEF = diciembre a febrero, EFM =
enero a marzo, FMA = febrero a abril) y se guarda UNA FILA POR EVENTO Y TRIMESTRE:
periodo es el evento ("1997-1998"), trimestre el código de SENAMHI ("DEF") y meses el
texto legible ("diciembre de 1997 a febrero de 1998"). Hasta el 24-10-2026 se guardaba
solo el primer .zip (5 filas); hoy son 13.

Por defecto es una prueba en seco: descarga y muestra el resumen, sin escribir.
Con --aplicar hace upsert por (uuid, trimestre) (idempotente: correrlo dos veces no
duplica filas; las filas viejas, con su trimestre ya puesto por la migración, se actualizan).

Se corre dentro del contenedor worker, que ya tiene geopandas y SUPABASE_DB_URL:
    docker compose run --rm worker python -m backend.mapas.cargar_fen
    docker compose run --rm worker python -m backend.mapas.cargar_fen --aplicar --simplificar 0.005 --decimales 5

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
import time
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

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
# inicial con la que SENAMHI nombra cada mes en el código del trimestre (D de diciembre, etc.);
# como enero y junio/julio comparten letra, el código se resuelve por su mes inicial en TRIMESTRES.
_MES_INICIAL = {t: (11 + i) % 12 for i, t in enumerate(idesep.TRIMESTRES)}   # DEF -> 11 (diciembre)


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

# Índice único mapa_uuid_trimestre_key: (uuid, coalesce(trimestre, '')), así el mapa mensual
# (trimestre null) y una capa sin trimestre en el nombre también caben una sola vez.
UPSERT = (
    "insert into mapa (uuid, titulo, variable, periodo, trimestre, meses, fuente, geojson) "
    "values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
    "on conflict (uuid, (coalesce(trimestre, ''))) do update set titulo=excluded.titulo, "
    "variable=excluded.variable, periodo=excluded.periodo, meses=excluded.meses, "
    "fuente=excluded.fuente, geojson=excluded.geojson, ts_captura=now()"
)


def anios_del_evento(periodo: str) -> tuple[int, int]:
    """
    (año en que empieza el verano, año en que termina). "1997-1998" -> (1997, 1998);
    "2017" -> (2016, 2017): el evento de un solo año empieza en diciembre del anterior.
    """
    partes = [int(p) for p in periodo.split("-") if p.strip().isdigit()]
    if not partes:
        raise ValueError(f"periodo sin año: {periodo!r}")
    return (partes[0], partes[-1]) if len(partes) > 1 else (partes[0] - 1, partes[0])


def meses_legibles(trimestre: str | None, periodo: str) -> str | None:
    """
    Meses que cubre un trimestre de un evento, en palabras:
      ("DEF", "1997-1998") -> "diciembre de 1997 a febrero de 1998"
      ("EFM", "2023")      -> "enero a marzo de 2023"
      ("FMA", "2017")      -> "febrero a abril de 2017"
    Si el trimestre cruza el año nuevo (NDE, DEF), los meses antes de enero son del primer año
    del evento y los demás del último; si no lo cruza, todos son del último año.
    None si el trimestre no se reconoce.
    """
    if not trimestre or trimestre.upper() not in _MES_INICIAL:
        return None
    inicio = _MES_INICIAL[trimestre.upper()]
    anio_ini, anio_fin = anios_del_evento(periodo)
    cruza = inicio + 2 >= 12
    m1, m3 = inicio, (inicio + 2) % 12
    a1 = anio_ini if cruza and m1 >= inicio else anio_fin
    a3 = anio_ini if cruza and m3 >= inicio else anio_fin
    if a1 == a3:
        return f"{MESES[m1]} a {MESES[m3]} de {a1}"
    return f"{MESES[m1]} de {a1} a {MESES[m3]} de {a3}"


def _resumen(geojson: str) -> str:
    data = json.loads(geojson)
    feats = data.get("features", [])
    tipos = sorted({(f.get("geometry") or {}).get("type", "?") for f in feats})
    return f"{len(feats)} features, {'/'.join(tipos)}, {len(geojson) / 1e6:.2f} MB"


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


# IDESEP responde a veces HTTP 400 a la página de un registro y al rato bien (visto el 25-10-2026 en
# dos corridas seguidas, con registros distintos). _http.con_reintentos no repite los 4xx (en general
# repetirlos no arregla nada), así que acá cada evento se intenta hasta 3 veces con una pausa.
INTENTOS_POR_EVENTO = 3
PAUSA_S = 5


def _con_paciencia(fn, *args, intentos: int = INTENTOS_POR_EVENTO, pausa: float = PAUSA_S):
    for intento in range(1, intentos + 1):
        try:
            return fn(*args)
        except Exception as e:
            if intento == intentos:
                raise
            log.warning("Falló (%s: %s); reintento %d/%d en %ds", type(e).__name__, e, intento, intentos - 1, pausa)
            time.sleep(pausa)


@dataclass(frozen=True)
class Fila:
    evento: EventoFEN
    uuid: str
    trimestre: str | None
    meses: str | None
    geojson: str


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

    listos: list[Fila] = []
    resueltos, fallidos = _resolver(EVENTOS_FEN)
    for evento, uuid in resueltos:
        try:
            capas = _con_paciencia(idesep.capas_de_registro, uuid, args.simplificar, args.decimales)
        except Exception as e:  # un mapa caído no debe frenar a los demás
            log.error("No se pudo obtener %s (%s): %s", evento.periodo, uuid, e)
            fallidos.append(evento.titulo)
            continue
        if len({t for t, _, _ in capas}) < len(capas):
            log.warning("%s: hay capas con el mismo trimestre; se guarda la última de cada una", evento.periodo)
        for trimestre, enlace, geojson in capas:
            meses = meses_legibles(trimestre, evento.periodo)
            if not trimestre:
                log.warning("%s: %s no dice el trimestre en su nombre; se guarda sin él", evento.periodo, enlace)
            log.info("OK %s %s (%s) | %s | %s", evento.periodo, trimestre or "-", meses or "sin meses", uuid, _resumen(geojson))
            listos.append(Fila(evento, uuid, trimestre, meses, geojson))
            if args.exportar:
                os.makedirs(args.exportar, exist_ok=True)
                ruta = os.path.join(args.exportar, f"fen_{evento.periodo}_{trimestre or 'sin_trimestre'}.geojson")
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(geojson)

    if args.aplicar and listos:
        try:
            with conectar() as conn, conn.cursor() as cur:
                for fila in listos:
                    cur.execute(UPSERT, (fila.uuid, fila.evento.titulo, VARIABLE, fila.evento.periodo,
                                         fila.trimestre, fila.meses, FUENTE, fila.geojson))
        except RuntimeError as e:   # falta SUPABASE_DB_URL o psycopg
            log.error("%s Corre el cargador dentro del contenedor worker.", e)
            return 2
        log.info("Guardados %d mapas (evento y trimestre) en la tabla mapa.", len(listos))
    elif not args.aplicar:
        log.info("Prueba en seco: no se escribió nada. Usa --aplicar para guardar.")

    if fallidos:
        log.error("Fallaron %d mapas: %s", len(fallidos), "; ".join(fallidos))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
