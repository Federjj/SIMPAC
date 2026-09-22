"""
Escritura de una Pasada en Supabase, en una sola transacción.

Regla de las alertas: solo se reemplazan las de las estaciones que se volvieron a
evaluar (con dato). Si ANA o una estación no respondió, su alerta se queda: no es un
"todo normal". Para que una fuente caída no deje alertas colgadas para siempre, las
que no se refrescan caducan a las SIN_DATOS_HORAS.
"""
from __future__ import annotations

from backend.db import conectar
from backend.ingesta.departamentos import DEPARTAMENTOS
from backend.ingesta.recolectar import Pasada

SIN_DATOS_HORAS = 6

SQL_ESTACION = (
    "insert into estacion (cod,nombre,tipo,categoria,estado,departamento,geom) "
    "values (%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326)) "
    "on conflict (cod) do update set nombre=excluded.nombre, tipo=excluded.tipo, "
    "categoria=excluded.categoria, estado=excluded.estado, "
    "departamento=excluded.departamento, geom=excluded.geom"
)
# SENAMHI corrige la última hora en la siguiente consulta: se actualiza si cambió.
SQL_LLUVIA = (
    "insert into lectura_lluvia (cod,ts,medido_en,precip_mm,temp_c) values (%s,%s,%s,%s,%s) "
    "on conflict (cod,ts) do update set medido_en=excluded.medido_en, "
    "precip_mm=excluded.precip_mm, temp_c=excluded.temp_c "
    "where (lectura_lluvia.medido_en, lectura_lluvia.precip_mm, lectura_lluvia.temp_c) "
    "is distinct from (excluded.medido_en, excluded.precip_mm, excluded.temp_c)"
)
SQL_CAUDAL = (
    "insert into lectura_caudal (estacion,rio,departamento,provincia,fecha,hora,valor,unidad,"
    "umbral_alerta,umbral_emergencia,tendencia,estado,geom) "
    "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326)) "
    "on conflict do nothing"   # clave única (estacion, rio, fecha, hora): hay nombres repetidos
)
SQL_INDICE = (
    "insert into indice (fuente,periodo,valor,categoria) values (%s,%s,%s,%s) "
    "on conflict (fuente) do update set periodo=excluded.periodo, valor=excluded.valor, "
    "categoria=excluded.categoria, ts_captura=now()"
)
SQL_BORRAR_ALERTAS = (
    "delete from alerta where tipo = %s "
    "and (referencia = any(%s) or ts < now() - make_interval(hours => %s))"
)
SQL_ALERTA = (
    "insert into alerta (tipo,referencia,zona,nivel,detalle,valor,umbral) "
    "values (%s,%s,%s,%s,%s,%s,%s)"
)


def _filas_caudal(p: Pasada) -> list[tuple]:
    return [(c.estacion, c.rio, c.departamento or None, c.provincia, fecha, c.hora,
             c.valor, c.unidad, c.umbral_alerta, c.umbral_emergencia, c.tendencia, c.estado,
             c.lon, c.lat)
            for fecha, c in (p.caudales or []) if c.lat is not None and c.lon is not None]


def guardar(p: Pasada) -> dict:
    caudal = _filas_caudal(p)
    alertas = p.alertas_lluvia + p.alertas_caudal
    with conectar() as conn, conn.cursor() as cur:
        if p.estaciones:
            cur.executemany(SQL_ESTACION, [
                (e.cod, e.nombre, e.tipo, e.categoria, e.estado, DEPARTAMENTOS.get(dp, dp), e.lon, e.lat)
                for dp, e in p.estaciones
            ])
        if p.lluvia:
            cur.executemany(SQL_LLUVIA, p.lluvia)
        if caudal:
            cur.executemany(SQL_CAUDAL, caudal)
        if p.icen:
            cur.execute(SQL_INDICE, ("ICEN", f"{p.icen.anio}-{p.icen.mes:02d}", p.icen.valor, p.icen.categoria))
        if p.oni:
            cur.execute(SQL_INDICE, ("ONI", f"{p.oni.temporada} {p.oni.anio}", p.oni.anom, p.oni.fase))

        cur.execute(SQL_BORRAR_ALERTAS, ("caudal", p.caudal_ok, SIN_DATOS_HORAS))
        cur.execute(SQL_BORRAR_ALERTAS, ("lluvia", p.lluvia_ok, SIN_DATOS_HORAS))
        if alertas:
            cur.executemany(SQL_ALERTA, [
                (a["tipo"], a["referencia"], a.get("zona"), a["nivel"],
                 a.get("detalle", ""), a.get("valor"), a.get("umbral"))
                for a in alertas
            ])
    return {
        "estaciones": len(p.estaciones),
        "lluvia": len(p.lluvia),
        "caudal": len(caudal) if p.caudales is not None else None,
        "alertas": len(alertas),
        "fallas": p.fallas,
    }
