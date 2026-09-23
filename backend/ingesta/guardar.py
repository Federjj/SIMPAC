"""
Escritura de una Pasada en Supabase, en una sola transacción.

Regla de las alertas de ríos (caudal, nivel_bajo): solo se reemplazan las de las
estaciones que se volvieron a evaluar (con dato). Si ANA o una estación no respondió, su
alerta se queda: no es un "todo normal". Para que una fuente caída no deje alertas
colgadas para siempre, las que no se refrescan caducan a las SIN_DATOS_HORAS. Las de
lluvia las escribe la tarea lluvia_nacional (backend/ingesta/lluvia_nacional.py).

Serie del ICEN (icen_serie, para el gráfico): se guardan los últimos meses del IGP, con la
categoría que calcula SIMPAC (igp.categoria; la de los meses del ENFEN es la oficial de la
tabla de su informe). El latido cuenta en 'icen_serie' los meses escritos (insertados o
cambiados), no los enviados: la ingesta reenvía los mismos cada hora. Si la migración de
la tabla todavía no se aplicó, la serie se salta con un aviso y el resto de la pasada se
guarda igual.
"""
from __future__ import annotations

import json
import logging

from backend.db import conectar
from backend.ingesta.departamentos import DEPARTAMENTOS
from backend.ingesta.recolectar import Pasada

log = logging.getLogger(__name__)

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
    # clave (estacion, rio, fecha, hora): hay nombres repetidos. Si la misma lectura vuelve
    # con otro valor, umbral o estado (p. ej. al cambiar la regla de vaciante), se corrige.
    "on conflict (estacion,rio,fecha,hora) do update set valor=excluded.valor, "
    "umbral_alerta=excluded.umbral_alerta, umbral_emergencia=excluded.umbral_emergencia, "
    "tendencia=excluded.tendencia, estado=excluded.estado, departamento=excluded.departamento "
    "where (lectura_caudal.valor, lectura_caudal.umbral_alerta, lectura_caudal.umbral_emergencia, "
    "lectura_caudal.tendencia, lectura_caudal.estado, lectura_caudal.departamento) is distinct from "
    "(excluded.valor, excluded.umbral_alerta, excluded.umbral_emergencia, excluded.tendencia, "
    "excluded.estado, excluded.departamento)"
)
SQL_INDICE = (
    "insert into indice (fuente,periodo,valor,categoria,origen) values (%s,%s,%s,%s,%s) "
    "on conflict (fuente) do update set periodo=excluded.periodo, valor=excluded.valor, "
    "categoria=excluded.categoria, origen=excluded.origen, ts_captura=now()"
)
# El ICEN llega del IGP (cada hora, a veces meses atrasado) y del Informe Técnico ENFEN:
# se queda el mes más nuevo. En el mismo mes cada origen solo refresca el suyo, y nunca
# se retrocede a un mes más viejo (ni siquiera desde el mismo origen).
SQL_ICEN = SQL_INDICE + (
    " where excluded.periodo > indice.periodo"
    " or (excluded.periodo = indice.periodo and excluded.origen = indice.origen)"
)
# El ICEN_TMP solo sale del Informe Técnico ENFEN: se refresca el mismo mes, pero nunca
# retrocede (una fuente atrasada no lo pisa con el de un informe más viejo).
SQL_ICEN_TMP = SQL_INDICE + " where excluded.periodo >= indice.periodo"
# Serie mensual del ICEN (tabla icen_serie). Un mes del ENFEN (Informe Técnico) nunca lo
# pisa el IGP; el IGP completa los meses que el ENFEN no trae y corrige los suyos; un
# informe nuevo corrige al anterior. Si el mes no cambió no se reescribe: ts_captura dice
# cuándo llegó el valor vigente, y el rowcount del executemany cuenta solo los meses
# insertados o cambiados. Las filas van en orden de mes (así la ingesta y la tarea enfen
# bloquean las filas en el mismo orden y no se trancan si coinciden).
SQL_ICEN_SERIE = (
    "insert into icen_serie (mes,valor,categoria,origen) values (%s,%s,%s,%s) "
    "on conflict (mes) do update set valor=excluded.valor, categoria=excluded.categoria, "
    "origen=excluded.origen, ts_captura=now() "
    "where (excluded.origen = 'ENFEN' or icen_serie.origen = excluded.origen) "
    "and (icen_serie.valor, icen_serie.categoria, icen_serie.origen) "
    "is distinct from (excluded.valor, excluded.categoria, excluded.origen)"
)
# La migración de icen_serie puede no estar aplicada todavía (el worker se despliega aparte).
SQL_HAY_ICEN_SERIE = "select to_regclass('public.icen_serie') is not null"
AVISO_SIN_SERIE = "icen_serie: falta la tabla (migración pendiente); la serie del ICEN no se guardó"
# Cuándo corrió de verdad cada tarea (el frontend avisa "sin actualizar" si se detiene).
SQL_LATIDO = (
    "insert into latido (servicio, ts, resumen) values (%s, now(), %s::jsonb) "
    "on conflict (servicio) do update set ts=now(), resumen=excluded.resumen"
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


def hay_icen_serie(cur) -> bool:
    """La tabla icen_serie existe (su migración ya se aplicó)."""
    cur.execute(SQL_HAY_ICEN_SERIE)
    fila = cur.fetchone()
    return bool(fila and fila[0])


def filas_serie(meses: list[tuple[str, float, str]], origen: str) -> list[tuple]:
    """
    Filas de icen_serie a partir de [("AAAA-MM", valor, categoría)], en orden de mes. La
    categoría va tal cual: la oficial de la tabla del informe (ENFEN) o la calculada por
    SIMPAC con igp.categoria (IGP).
    """
    return [(mes, valor, categoria, origen) for mes, valor, categoria in sorted(meses)]


def guardar(p: Pasada) -> dict:
    caudal = _filas_caudal(p)
    alertas = p.alertas_caudal
    avisos = list(p.avisos)
    serie = 0   # meses del IGP escritos en icen_serie (insertados o cambiados)
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
            cur.execute(SQL_ICEN, ("ICEN", f"{p.icen.anio}-{p.icen.mes:02d}", p.icen.valor,
                                   p.icen.categoria, "IGP"))
        if p.icen_serie:
            if hay_icen_serie(cur):
                cur.executemany(SQL_ICEN_SERIE, filas_serie(
                    [(f"{x.anio}-{x.mes:02d}", x.valor, x.categoria) for x in p.icen_serie], "IGP"))
                # psycopg 3 (el worker tiene 3.3.6) suma las filas afectadas de todo el
                # executemany; las que el WHERE deja igual (sin cambios, mes del ENFEN) no cuentan
                serie = cur.rowcount
            else:
                log.warning("Ingesta: %s", AVISO_SIN_SERIE)
                avisos.append(AVISO_SIN_SERIE)
        if p.roni:
            cur.execute(SQL_INDICE, ("RONI", f"{p.roni.temporada} {p.roni.anio}", p.roni.anom,
                                     p.roni.fase, "NOAA"))

        # una estación puede pasar de crecida a nivel bajo: se limpian las dos familias
        for tipo in ("caudal", "nivel_bajo"):
            cur.execute(SQL_BORRAR_ALERTAS, (tipo, p.caudal_ok, SIN_DATOS_HORAS))
        if alertas:
            cur.executemany(SQL_ALERTA, [
                (a["tipo"], a["referencia"], a.get("zona"), a["nivel"],
                 a.get("detalle", ""), a.get("valor"), a.get("umbral"))
                for a in alertas
            ])
        resumen = {
            "estaciones": len(p.estaciones),
            "lluvia": len(p.lluvia),
            "caudal": len(caudal) if p.caudales is not None else None,
            "alertas": len(alertas),
            "icen_serie": serie,
            "fallas": p.fallas,
            "avisos": avisos,
        }
        cur.execute(SQL_LATIDO, ("ingesta", json.dumps(resumen)))
    return resumen
