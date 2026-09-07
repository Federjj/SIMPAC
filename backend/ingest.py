"""
Job de ingesta de SIMPAC (prototipo).

Corre una "pasada": trae datos de las fuentes, los guarda en SQLite y recalcula
las alertas vigentes. Ejecutar periódicamente (cada hora) con cron / Programador
de tareas de Windows / APScheduler.

    python backend/ingest.py
"""
from __future__ import annotations

import sys
from datetime import date

sys.path.insert(0, __file__.rsplit("backend", 1)[0])

from backend import alerts, store
from backend.connectors import ana, igp, noaa, senamhi


def correr() -> dict:
    conn = store.connect()
    store.init_db(conn)
    resumen = {"estaciones": 0, "lluvia_filas": 0, "caudal_filas": 0, "alertas": 0}
    alertas_vigentes: list[dict] = []

    # 1) Inventario de estaciones (Cajamarca)
    try:
        ests = senamhi.inventario_estaciones("cajamarca")
        for e in ests:
            store.upsert_estacion(conn, e)
        resumen["estaciones"] = len(ests)
    except Exception as e:
        print("  [inventario] error:", e)
        ests = []

    # 2) Lluvia horaria de estaciones automáticas meteorológicas
    autos = [e for e in ests if e.es_automatica and e.tipo == "M"]
    for e in autos:
        try:
            s = senamhi.datos_horarios(e)
            for ts, p, t in zip(s.timestamps, s.precip_mm, s.temp_c):
                store.insert_lluvia(conn, e.cod, e.nombre, ts, p, t)
                resumen["lluvia_filas"] += 1
            a = alerts.evaluar_lluvia(e.cod, e.nombre, s)
            if a:
                alertas_vigentes.append(a)
        except Exception as ex:
            print(f"  [lluvia {e.nombre}] error:", ex)

    # 3) Caudales de ríos (ANA) — Cajamarca
    try:
        caud = ana.caudal_cajamarca()
        hoy = date.today().isoformat()
        for c in caud:
            store.insert_caudal(conn, c, hoy)
            resumen["caudal_filas"] += 1
        alertas_vigentes += alerts.evaluar_caudal(caud)
    except Exception as ex:
        print("  [caudal] error:", ex)

    # 4) Contexto El Niño (ICEN / ONI)
    try:
        i = igp.ultimo()
        if i:
            store.set_indice(conn, "ICEN", f"{i.anio}-{i.mes:02d}", i.valor, i.categoria)
    except Exception as ex:
        print("  [ICEN] error:", ex)
    try:
        o = noaa.ultimo()
        if o:
            store.set_indice(conn, "ONI", f"{o.temporada} {o.anio}", o.anom, o.fase)
    except Exception as ex:
        print("  [ONI] error:", ex)

    # 5) Alertas vigentes
    store.replace_alertas(conn, alertas_vigentes)
    resumen["alertas"] = len(alertas_vigentes)

    conn.commit()
    conn.close()
    return resumen


if __name__ == "__main__":
    r = correr()
    print("Ingesta OK:", r)
