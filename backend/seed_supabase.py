"""
Genera SQL de carga (seed) con datos reales de Cajamarca desde los conectores,
para insertarlo en Supabase. Escribe el SQL a un archivo y lo imprime el conteo.

    python backend/seed_supabase.py <ruta_salida.sql>
"""
from __future__ import annotations

import sys
import json
from datetime import date

from dotenv import load_dotenv

sys.path.insert(0, __file__.rsplit("backend", 1)[0])
from backend.connectors import ana, igp, noaa, senamhi
from backend.mapas.mapas_dic_subject import map_subjects

load_dotenv()


def q(s):
    return "null" if s is None else "'" + str(s).replace("'", "''") + "'"


def num(x):
    return "null" if x is None else repr(float(x))


def pt(lon, lat):
    if lon is None or lat is None:
        return "null"
    return f"ST_SetSRID(ST_MakePoint({float(lon)},{float(lat)}),4326)"


def main(out_path: str) -> None:
    bloques = []

    # --- estaciones (dedup por cod) ---
    ests, vistos = [], set()
    for e in senamhi.inventario_estaciones("cajamarca"):
        if e.cod in vistos:
            continue
        vistos.add(e.cod)
        ests.append(e)
    vals = [
        f"({q(e.cod)},{q(e.nombre)},{q(e.tipo)},{q(e.categoria)},{q(e.estado)},{pt(e.lon, e.lat)})"
        for e in ests
    ]
    bloques.append(
        "insert into estacion (cod,nombre,tipo,categoria,estado,geom) values\n"
        + ",\n".join(vals)
        + "\non conflict (cod) do update set nombre=excluded.nombre,"
          "estado=excluded.estado,geom=excluded.geom;"
    )

    # --- caudales de Cajamarca (snapshot de hoy) ---
    # ANA es intermitente; si falla, seguimos con el resto del seed.
    caud = []
    try:
        caud = ana.caudal_cajamarca()
    except Exception as ex:
        print(f"AVISO: ANA no disponible ({type(ex).__name__}); se omite el caudal.")
    if caud:
        hoy = date.today().isoformat()
        vals = [
            f"({q(c.estacion)},{q(c.rio)},{q(c.departamento)},{q(c.provincia)},"
            f"'{hoy}',{q(c.hora)},{num(c.valor)},{q(c.unidad)},{num(c.umbral_alerta)},"
            f"{num(c.umbral_emergencia)},{q(c.tendencia)},{q(c.estado)},{pt(c.lon, c.lat)})"
            for c in caud
        ]
        bloques.append(
            "insert into lectura_caudal (estacion,rio,departamento,provincia,fecha,hora,"
            "valor,unidad,umbral_alerta,umbral_emergencia,tendencia,estado,geom) values\n"
            + ",\n".join(vals)
            + "\non conflict (estacion,fecha,hora) do nothing;"
        )

    # --- índices El Niño ---
    i = igp.ultimo()
    if i:
        bloques.append(
            f"insert into indice (fuente,periodo,valor,categoria) values "
            f"('ICEN','{i.anio}-{i.mes:02d}',{num(i.valor)},{q(i.categoria)}) "
            f"on conflict (fuente) do update set periodo=excluded.periodo,"
            f"valor=excluded.valor,categoria=excluded.categoria,ts_captura=now();"
        )
    o = noaa.ultimo()
    if o:
        bloques.append(
            f"insert into indice (fuente,periodo,valor,categoria) values "
            f"('ONI',{q(o.temporada + ' ' + str(o.anio))},{num(o.anom)},{q(o.fase)}) "
            f"on conflict (fuente) do update set periodo=excluded.periodo,"
            f"valor=excluded.valor,categoria=excluded.categoria,ts_captura=now();"
        )

    # --- mapas FEN (eventos El Niño) ---
    mapas = []
    try:
        mapas = senamhi.mapas_fen(map_subjects)
    except Exception as ex:
        print(f"AVISO: No se pudieron obtener mapas FEN ({type(ex).__name__})")

    if mapas:
        # DELETE primero
        delete_uuids = ", ".join([q(m.uuid) for m in mapas])
        bloques.append(f"delete from mapa where uuid in ({delete_uuids});")

        # INSERT después
        vals = [
            f"({q(m.uuid)},{q(m.titulo)},{q(m.variable)},{q(m.periodo)},"
            f"'SENAMHI/IDESEP',{q(m.geojson)})"
            for m in mapas
        ]
        bloques.append(
            "insert into mapa (uuid,titulo,variable,periodo,fuente,geojson) values\n"
            + ",\n".join(vals) + ";"
        )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(bloques) + "\n")
    print(f"OK: {len(ests)} estaciones, {len(caud)} caudales, {len(mapas)} mapas FEN, indices ICEN/ONI -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "seed.sql")
