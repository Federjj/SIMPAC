"""
Genera SQL de carga para caudales (ANA) y lluvia horaria (SENAMHI automáticas),
más las alertas derivadas. Escribe archivos .sql para cargarlos en Supabase.

    python backend/seed_supabase_extra.py <dir_salida>
"""
from __future__ import annotations

import sys
from datetime import date, datetime

sys.path.insert(0, __file__.rsplit("backend", 1)[0])
from backend import alerts
from backend.connectors import ana, senamhi


def q(s):
    return "null" if s is None else "'" + str(s).replace("'", "''") + "'"


def num(x):
    return "null" if x is None else repr(float(x))


def pt(lon, lat):
    if lon is None or lat is None:
        return "null"
    return f"ST_SetSRID(ST_MakePoint({float(lon)},{float(lat)}),4326)"


def ts_to_tstz(ts: str):
    # "2026/09/06 - 21" -> '2026-09-06 21:00:00-05' (Perú UTC-5)
    try:
        fecha, hora = ts.split(" - ")
        dt = datetime.strptime(fecha.strip() + " " + hora.strip(), "%Y/%m/%d %H")
        return "'" + dt.strftime("%Y-%m-%d %H:00:00-05") + "'"
    except Exception:
        return "null"


def main(out_dir: str) -> None:
    alertas_vigentes: list[dict] = []

    # ---- CAUDAL (ANA) ----
    caudal_sql = ""
    try:
        caud = ana.caudal_cajamarca()
        hoy = date.today().isoformat()
        vals = [
            f"({q(c.estacion)},{q(c.rio)},{q(c.departamento)},{q(c.provincia)},"
            f"'{hoy}',{q(c.hora)},{num(c.valor)},{q(c.unidad)},{num(c.umbral_alerta)},"
            f"{num(c.umbral_emergencia)},{q(c.tendencia)},{q(c.estado)},{pt(c.lon, c.lat)})"
            for c in caud
        ]
        if vals:
            caudal_sql = (
                "insert into lectura_caudal (estacion,rio,departamento,provincia,fecha,hora,"
                "valor,unidad,umbral_alerta,umbral_emergencia,tendencia,estado,geom) values\n"
                + ",\n".join(vals)
                + "\non conflict (estacion,fecha,hora) do nothing;\n"
            )
        alertas_vigentes += alerts.evaluar_caudal(caud)
        print(f"caudal: {len(caud)} estaciones")
    except Exception as ex:
        print(f"caudal: ANA no disponible ({type(ex).__name__})")

    with open(f"{out_dir}/caudal.sql", "w", encoding="utf-8") as f:
        f.write(caudal_sql)

    # ---- LLUVIA horaria (estaciones automáticas meteorológicas) ----
    autos_m = [e for e in senamhi.inventario_estaciones("cajamarca")
               if e.es_automatica and e.tipo == "M"]
    filas = []
    for e in autos_m:
        try:
            s = senamhi.datos_horarios(e)
            for ts, p, t in zip(s.timestamps, s.precip_mm, s.temp_c):
                filas.append(
                    f"({q(e.cod)},{q(ts)},{ts_to_tstz(ts)},{num(p)},{num(t)})"
                )
            a = alerts.evaluar_lluvia(e.cod, e.nombre, s)
            if a:
                alertas_vigentes.append(a)
        except Exception as ex:
            print(f"  lluvia {e.nombre}: {type(ex).__name__}")
    lluvia_sql = ""
    if filas:
        lluvia_sql = (
            "insert into lectura_lluvia (cod,ts,medido_en,precip_mm,temp_c) values\n"
            + ",\n".join(filas)
            + "\non conflict (cod,ts) do nothing;\n"
        )
    with open(f"{out_dir}/lluvia.sql", "w", encoding="utf-8") as f:
        f.write(lluvia_sql)
    print(f"lluvia: {len(autos_m)} estaciones automáticas, {len(filas)} filas horarias")

    # ---- ALERTAS derivadas ----
    alerta_sql = "delete from alerta;\n"
    if alertas_vigentes:
        vals = [
            f"({q(a['tipo'])},{q(a['referencia'])},{q(a.get('zona', 'Cajamarca'))},"
            f"{q(a['nivel'])},{q(a.get('detalle', ''))},{num(a.get('valor'))},{num(a.get('umbral'))})"
            for a in alertas_vigentes
        ]
        alerta_sql += (
            "insert into alerta (tipo,referencia,zona,nivel,detalle,valor,umbral) values\n"
            + ",\n".join(vals) + ";\n"
        )
    with open(f"{out_dir}/alerta.sql", "w", encoding="utf-8") as f:
        f.write(alerta_sql)
    print(f"alertas vigentes: {len(alertas_vigentes)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
