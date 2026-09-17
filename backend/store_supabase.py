"""
Ingesta a Supabase (PostgreSQL + PostGIS) — NACIONAL y CONCURRENTE.

Corre una pasada de todos los conectores y escribe en Supabase. Paraleliza las
descargas (ThreadPoolExecutor) porque son I/O: bajar 24 departamentos en serie
tardaría muchísimo; en paralelo es rápido.

Requisitos:
  pip install "psycopg[binary]"
  SUPABASE_DB_URL = connection string de Supabase (incluye la contraseña; secreto)

Uso directo: python backend/store_supabase.py
(En producción lo llama el worker Celery cada hora — ver celery_app.py.)
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

sys.path.insert(0, __file__.rsplit("backend", 1)[0])
from backend import alerts
from backend.connectors import ana, igp, noaa, senamhi

DSN = os.environ.get("SUPABASE_DB_URL")

# Slugs de departamento para el endpoint ?dp= de SENAMHI (los que fallen se saltan).
DEPARTAMENTOS = [
    "amazonas", "ancash", "apurimac", "arequipa", "ayacucho", "cajamarca", "cusco",
    "huancavelica", "huanuco", "ica", "junin", "lalibertad", "lambayeque", "lima",
    "loreto", "madrededios", "moquegua", "pasco", "piura", "puno", "sanmartin",
    "tacna", "tumbes", "ucayali",
]
# Para la lluvia horaria solo consultamos estos dptos (una request por estación
# automática; por defecto Cajamarca, el foco, para no golpear de más a SENAMHI).
LLUVIA_DEPTS = [d.strip() for d in os.environ.get("SIMPAC_LLUVIA_DEPTS", "cajamarca").split(",") if d.strip()]


def _medido_en(ts: str):
    try:
        f, h = ts.split(" - ")
        return datetime.strptime(f.strip() + " " + h.strip(), "%Y/%m/%d %H")
    except Exception:
        return None


def run() -> dict:
    try:
        import psycopg
    except ImportError:
        raise SystemExit('Falta psycopg. Instala: pip install "psycopg[binary]"')
    if not DSN:
        raise SystemExit("Falta SUPABASE_DB_URL.")

    # 1) Inventario de estaciones — 24 dptos en paralelo
    def _inv(dp):
        try:
            return dp, senamhi.inventario_estaciones(dp)
        except Exception:
            return dp, []

    ests, seen = [], set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for dp, rows in ex.map(_inv, DEPARTAMENTOS):
            for e in rows:
                if e.cod in seen:
                    continue
                seen.add(e.cod)
                ests.append((dp, e))

    # 2) Lluvia horaria (estaciones automáticas meteorológicas de LLUVIA_DEPTS) — en paralelo
    autos = [e for (dp, e) in ests if dp in LLUVIA_DEPTS and e.es_automatica and e.tipo == "M"]

    def _serie(e):
        try:
            return e, senamhi.datos_horarios(e)
        except Exception:
            return e, None

    lluvia_rows, alertas_v = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for e, s in ex.map(_serie, autos):
            if not s:
                continue
            for ts, p, t in zip(s.timestamps, s.precip_mm, s.temp_c):
                lluvia_rows.append((e.cod, ts, _medido_en(ts), p, t))
            a = alerts.evaluar_lluvia(e.cod, e.nombre, s)
            if a:
                alertas_v.append(a)

    # 3) Caudales (ANA, nacional en una sola llamada)
    try:
        caud = ana.reporte_caudal()
        alertas_v += alerts.evaluar_caudal(caud)
    except Exception:
        caud = []

    # 4) Índices El Niño
    i = igp.ultimo()
    o = noaa.ultimo()

    # 5) Escritura a Supabase
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.executemany(
            "insert into estacion (cod,nombre,tipo,categoria,estado,geom) "
            "values (%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326)) "
            "on conflict (cod) do update set nombre=excluded.nombre,estado=excluded.estado,geom=excluded.geom",
            [(e.cod, e.nombre, e.tipo, e.categoria, e.estado, e.lon, e.lat) for (_, e) in ests],
        )
        if lluvia_rows:
            cur.executemany(
                "insert into lectura_lluvia (cod,ts,medido_en,precip_mm,temp_c) values (%s,%s,%s,%s,%s) "
                "on conflict (cod,ts) do nothing",
                lluvia_rows,
            )
        hoy = date.today().isoformat()
        cur.executemany(
            "insert into lectura_caudal (estacion,rio,departamento,provincia,fecha,hora,valor,unidad,"
            "umbral_alerta,umbral_emergencia,tendencia,estado,geom) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326)) "
            "on conflict (estacion,fecha,hora) do nothing",
            [(c.estacion, c.rio, c.departamento, c.provincia, hoy, c.hora, c.valor, c.unidad,
              c.umbral_alerta, c.umbral_emergencia, c.tendencia, c.estado, c.lon, c.lat)
             for c in caud if c.lat is not None],
        )
        if i:
            cur.execute(
                "insert into indice (fuente,periodo,valor,categoria) values ('ICEN',%s,%s,%s) "
                "on conflict (fuente) do update set periodo=excluded.periodo,valor=excluded.valor,"
                "categoria=excluded.categoria,ts_captura=now()",
                (f"{i.anio}-{i.mes:02d}", i.valor, i.categoria),
            )
        if o:
            cur.execute(
                "insert into indice (fuente,periodo,valor,categoria) values ('ONI',%s,%s,%s) "
                "on conflict (fuente) do update set periodo=excluded.periodo,valor=excluded.valor,"
                "categoria=excluded.categoria,ts_captura=now()",
                (f"{o.temporada} {o.anio}", o.anom, o.fase),
            )
        cur.execute("delete from alerta")
        if alertas_v:
            cur.executemany(
                "insert into alerta (tipo,referencia,zona,nivel,detalle,valor,umbral) "
                "values (%s,%s,%s,%s,%s,%s,%s)",
                [(a["tipo"], a["referencia"], a.get("zona", "Cajamarca"), a["nivel"],
                  a.get("detalle", ""), a.get("valor"), a.get("umbral")) for a in alertas_v],
            )
        conn.commit()

    resumen = {"estaciones": len(ests), "lluvia": len(lluvia_rows), "caudal": len(caud), "alertas": len(alertas_v)}
    print("Ingesta nacional a Supabase OK:", resumen)
    return resumen


if __name__ == "__main__":
    run()
