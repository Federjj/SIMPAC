"""
Ingesta directa a Supabase (PostgreSQL + PostGIS).

Es el reemplazo de producción de `store.py` (SQLite): corre una pasada de los
conectores y escribe en la BD de Supabase. Reusa exactamente los INSERT con
`ST_SetSRID(ST_MakePoint(...))` ya validados vía el MCP.

Requisitos:
  pip install "psycopg[binary]"
  set SUPABASE_DB_URL = connection string de Supabase
     (Supabase → Settings → Database → Connection string → URI; incluye la contraseña)

Uso:
  python backend/store_supabase.py

⚠️ Escrito pero NO probado desde aquí (falta la credencial). El SQL es el mismo
que ya funcionó por el MCP; lo que falta validar es solo la conexión psycopg.
Pensado para correr cada hora (cron / Programador de tareas / GitHub Actions).
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime

sys.path.insert(0, __file__.rsplit("backend", 1)[0])
from backend import alerts
from backend.connectors import ana, igp, noaa, senamhi

DSN = os.environ.get("SUPABASE_DB_URL")


def _medido_en(ts: str):
    try:
        f, h = ts.split(" - ")
        return datetime.strptime(f.strip() + " " + h.strip(), "%Y/%m/%d %H")
    except Exception:
        return None


def run() -> None:
    try:
        import psycopg
    except ImportError:
        raise SystemExit('Falta psycopg. Instala: pip install "psycopg[binary]"')
    if not DSN:
        raise SystemExit("Falta la variable SUPABASE_DB_URL (connection string de Supabase).")

    # inventario (dedup por cod)
    ests, seen = [], set()
    for e in senamhi.inventario_estaciones("cajamarca"):
        if e.cod not in seen:
            seen.add(e.cod)
            ests.append(e)

    alertas_v: list[dict] = []

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        # --- estaciones ---
        cur.executemany(
            "insert into estacion (cod,nombre,tipo,categoria,estado,geom) "
            "values (%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326)) "
            "on conflict (cod) do update set nombre=excluded.nombre,"
            "estado=excluded.estado,geom=excluded.geom",
            [(e.cod, e.nombre, e.tipo, e.categoria, e.estado, e.lon, e.lat) for e in ests],
        )

        # --- lluvia horaria (automáticas meteorológicas) ---
        for e in [x for x in ests if x.es_automatica and x.tipo == "M"]:
            try:
                s = senamhi.datos_horarios(e)
                cur.executemany(
                    "insert into lectura_lluvia (cod,ts,medido_en,precip_mm,temp_c) "
                    "values (%s,%s,%s,%s,%s) on conflict (cod,ts) do nothing",
                    [(e.cod, ts, _medido_en(ts), p, t)
                     for ts, p, t in zip(s.timestamps, s.precip_mm, s.temp_c)],
                )
                a = alerts.evaluar_lluvia(e.cod, e.nombre, s)
                if a:
                    alertas_v.append(a)
            except Exception as ex:
                print(f"  lluvia {e.nombre}: {type(ex).__name__}")

        # --- caudales (ANA) ---
        try:
            caud = ana.caudal_cajamarca()
            hoy = date.today().isoformat()
            cur.executemany(
                "insert into lectura_caudal (estacion,rio,departamento,provincia,fecha,hora,"
                "valor,unidad,umbral_alerta,umbral_emergencia,tendencia,estado,geom) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326)) "
                "on conflict (estacion,fecha,hora) do nothing",
                [(c.estacion, c.rio, c.departamento, c.provincia, hoy, c.hora, c.valor,
                  c.unidad, c.umbral_alerta, c.umbral_emergencia, c.tendencia, c.estado,
                  c.lon, c.lat) for c in caud],
            )
            alertas_v += alerts.evaluar_caudal(caud)
        except Exception as ex:
            print(f"  caudal ANA no disponible: {type(ex).__name__}")

        # --- índices El Niño ---
        i = igp.ultimo()
        if i:
            cur.execute(
                "insert into indice (fuente,periodo,valor,categoria) values ('ICEN',%s,%s,%s) "
                "on conflict (fuente) do update set periodo=excluded.periodo,"
                "valor=excluded.valor,categoria=excluded.categoria,ts_captura=now()",
                (f"{i.anio}-{i.mes:02d}", i.valor, i.categoria),
            )
        o = noaa.ultimo()
        if o:
            cur.execute(
                "insert into indice (fuente,periodo,valor,categoria) values ('ONI',%s,%s,%s) "
                "on conflict (fuente) do update set periodo=excluded.periodo,"
                "valor=excluded.valor,categoria=excluded.categoria,ts_captura=now()",
                (f"{o.temporada} {o.anio}", o.anom, o.fase),
            )

        # --- alertas vigentes ---
        cur.execute("delete from alerta")
        if alertas_v:
            cur.executemany(
                "insert into alerta (tipo,referencia,zona,nivel,detalle,valor,umbral) "
                "values (%s,%s,%s,%s,%s,%s,%s)",
                [(a["tipo"], a["referencia"], a.get("zona", "Cajamarca"), a["nivel"],
                  a.get("detalle", ""), a.get("valor"), a.get("umbral")) for a in alertas_v],
            )
        conn.commit()

    print(f"Ingesta a Supabase OK: {len(ests)} estaciones; {len(alertas_v)} alertas.")


if __name__ == "__main__":
    run()
