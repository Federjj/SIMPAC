"""
Recolección: una pasada por todas las fuentes, sin tocar la BD.

Las descargas son I/O, por eso van en paralelo (ThreadPoolExecutor): bajar 24
departamentos en serie tardaría mucho. Cada fuente se protege por separado: si
una se cae, la pasada sigue y queda anotado en Pasada.fallas, para que guardar()
no borre como "resuelto" lo que en realidad no se pudo volver a consultar.
"""
from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from backend import alerts
from backend.config import ajustes
from backend.connectors import ana, igp, noaa, senamhi
from backend.ingesta.departamentos import DEPARTAMENTOS, nombre_departamento

log = logging.getLogger(__name__)

HILOS = 8   # descargas simultáneas (no golpear de más a SENAMHI)
MESES_SERIE_IGP = 36   # meses del ICEN.txt que van a icen_serie (el gráfico muestra ~24)
MAX_ICEN = 10.0        # |ICEN| mayor que esto es una fila dañada (el récord ronda +4)


@dataclass
class Pasada:
    """Todo lo que se bajó en una corrida, listo para guardar."""
    estaciones: list[tuple[str, senamhi.Estacion]] = field(default_factory=list)   # (departamento, estación)
    lluvia: list[tuple] = field(default_factory=list)          # filas de lectura_lluvia
    lluvia_ok: list[str] = field(default_factory=list)         # referencias de alerta re-evaluadas
    alertas_lluvia: list[dict] = field(default_factory=list)
    caudales: list[tuple[date, ana.EstacionCaudal]] | None = None   # (fecha, lectura); None = ANA no respondió
    caudal_ok: list[str] = field(default_factory=list)         # referencias de alerta re-evaluadas
    alertas_caudal: list[dict] = field(default_factory=list)
    # último mes del IGP (nunca posterior al mes anterior al actual) y los MESES_SERIE_IGP
    # hasta él, en orden; su categoría la calcula SIMPAC (igp.categoria)
    icen: igp.PuntoICEN | None = None
    icen_serie: list[igp.PuntoICEN] = field(default_factory=list)
    roni: noaa.PuntoRONI | None = None
    fallas: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)            # datos raros que se descartaron


def _inventario(pasada: Pasada) -> None:
    def bajar(dp):
        try:
            return dp, senamhi.inventario_estaciones(dp)
        except Exception as e:   # un departamento caído no frena a los demás
            log.warning("SENAMHI inventario %s: %s", dp, e)
            return dp, None

    vistos: set[str] = set()
    with ThreadPoolExecutor(max_workers=HILOS) as ex:
        for dp, filas in ex.map(bajar, DEPARTAMENTOS):
            if filas is None:
                pasada.fallas.append(f"senamhi:inventario:{dp}")
                continue
            for e in filas:
                if e.cod not in vistos:
                    vistos.add(e.cod)
                    pasada.estaciones.append((dp, e))


def filas_lluvia(cod: str, serie: senamhi.SerieHoraria) -> list[tuple]:
    """(cod, ts, medido_en, precip_mm, temp_c) por hora. Si a la estación le falta una
    de las dos series (p. ej. no mide temperatura), ese valor va en None: zip() a
    secas cortaría a la lista más corta y se perdería toda la lluvia."""
    def en(lista, i):
        return lista[i] if i < len(lista) else None
    return [(cod, ts, senamhi.parse_ts(ts), en(serie.precip_mm, i), en(serie.temp_c, i))
            for i, ts in enumerate(serie.timestamps)]


def _lluvia(pasada: Pasada) -> None:
    deptos = set(ajustes().lluvia_deptos)
    autos = [(dp, e) for dp, e in pasada.estaciones
             if dp in deptos and e.es_automatica and e.tipo == "M"]

    def bajar(item):
        dp, e = item
        try:
            return dp, e, senamhi.datos_horarios(e)
        except Exception as ex:
            log.warning("SENAMHI serie %s (%s): %s", e.cod, e.nombre, ex)
            return dp, e, None

    fallidas = 0
    with ThreadPoolExecutor(max_workers=HILOS) as ex:
        for dp, e, serie in ex.map(bajar, autos):
            if serie is None:
                fallidas += 1
                continue
            pasada.lluvia += filas_lluvia(e.cod, serie)
            pasada.lluvia_ok.append(alerts.referencia_lluvia(e.cod, e.nombre))
            a = alerts.evaluar_lluvia(e.cod, e.nombre, serie, zona=DEPARTAMENTOS.get(dp))
            if a:
                pasada.alertas_lluvia.append(a)
    if fallidas:
        pasada.fallas.append(f"senamhi:series:{fallidas}/{len(autos)}")


def _caudal(pasada: Pasada) -> None:
    # El reporte de ANA de un día trae solo las estaciones que YA midieron ese día: de
    # madrugada viene casi vacío y hay estaciones que miden una vez al día. Por eso se
    # piden ayer y hoy y se queda la última lectura de cada estación. "Hoy" es el de
    # Perú: el contenedor corre en UTC y desde las 19:00 de Lima ya sería mañana.
    hoy = datetime.now(senamhi.HORA_PERU).date()
    ultimas: dict[tuple[str, str], tuple[date, ana.EstacionCaudal]] = {}
    respondio = False
    for fecha in (hoy - timedelta(days=1), hoy):
        try:
            filas = ana.reporte_caudal(fecha)
        except Exception as e:
            log.warning("ANA caudales %s: %s", fecha, e)
            pasada.fallas.append(f"ana:{fecha.isoformat()}")
            continue
        respondio = True
        for c in filas:
            c.departamento = nombre_departamento(c.departamento) or ""
            clave = (c.estacion, c.rio)
            if c.valor is not None or clave not in ultimas:   # una fila sin dato no pisa una con dato
                ultimas[clave] = (fecha, c)
    if not respondio:
        return
    pasada.caudales = list(ultimas.values())
    actuales = [c for _, c in pasada.caudales]
    # solo cuenta como re-evaluada la estación que trae un valor
    pasada.caudal_ok = [alerts.referencia_caudal(c) for c in actuales if c.valor is not None]
    pasada.alertas_caudal = alerts.evaluar_caudal(actuales)


def serie_icen_igp(puntos: list[igp.PuntoICEN], meses: int = MESES_SERIE_IGP,
                   ahora: datetime | None = None) -> tuple[list[igp.PuntoICEN], int]:
    """
    Los últimos `meses` meses del ICEN.txt (contados desde su último mes, no por filas), en
    orden. Descarta las filas imposibles (mes fuera de 1-12, año raro, valor no finito o
    |ICEN| > MAX_ICEN) y las de meses posteriores al anterior al actual en hora de Perú
    (igp.ultimo_mes_posible; `ahora`: por defecto, ya): una sola fila dañada no debe tumbar
    la escritura de la pasada, y un mes futuro correría la ventana, quedaría para siempre en
    icen_serie (nada se borra) y dejaría fijo el ICEN de indice. Si un mes se repite, vale
    la última fila. Devuelve (serie, filas descartadas).
    """
    anio_tope, mes_tope = igp.ultimo_mes_posible(ahora)
    tope = anio_tope * 12 + mes_tope - 1
    por_mes: dict[int, igp.PuntoICEN] = {}
    descartadas = 0
    for p in puntos:
        k = p.anio * 12 + p.mes - 1
        if not (1 <= p.mes <= 12 and 1900 <= p.anio <= 2100 and k <= tope
                and math.isfinite(p.valor) and abs(p.valor) <= MAX_ICEN):
            descartadas += 1
            continue
        por_mes[k] = p
    if not por_mes:
        return [], descartadas
    desde = max(por_mes) - meses + 1
    return [por_mes[k] for k in sorted(por_mes) if k >= desde], descartadas


def _indices(pasada: Pasada) -> None:
    # El ICEN.txt trae la serie completa: se baja una vez y de ahí salen el último mes
    # (tabla indice) y la serie (icen_serie). El de indice sale de la serie ya filtrada:
    # nunca es de un mes posterior al anterior al actual.
    try:
        puntos = igp.icen()
    except Exception as e:
        log.warning("IGP: %s", e)
        pasada.fallas.append("igp")
    else:
        pasada.icen_serie, descartadas = serie_icen_igp(puntos)
        pasada.icen = pasada.icen_serie[-1] if pasada.icen_serie else None
        if descartadas:
            pasada.avisos.append(f"igp: {descartadas} filas del ICEN.txt descartadas "
                                 "(mes imposible o futuro, o valor imposible)")
        if not pasada.icen_serie:
            pasada.avisos.append("igp: el ICEN.txt no trae ningún mes válido")
    try:
        pasada.roni = noaa.ultimo()
    except Exception as e:
        log.warning("NOAA: %s", e)
        pasada.fallas.append("noaa")


def recolectar() -> Pasada:
    pasada = Pasada()
    _inventario(pasada)
    _lluvia(pasada)
    _caudal(pasada)
    _indices(pasada)
    return pasada
