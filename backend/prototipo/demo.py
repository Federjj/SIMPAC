"""
Demo de los conectores de SIMPAC. Corre así (Python 3.10+, sin dependencias):

    python -m backend.prototipo.demo

Muestra una "foto" en tiempo real de Cajamarca: contexto El Niño (ICEN/ONI),
caudales de ríos con su estado de alerta, y la lluvia horaria de una estación
automática. Sirve como prueba de humo de que los endpoints siguen vivos.
"""
from __future__ import annotations

import sys
import traceback

sys.path.insert(0, __file__.rsplit("backend", 1)[0])  # permite ejecutarlo desde cualquier cwd

from backend.connectors import ana, igp, noaa, senamhi


def seccion(t: str) -> None:
    print("\n" + t)
    print("-" * len(t))


def main() -> None:
    print("=== SIMPAC · foto en tiempo real (Cajamarca) ===")

    seccion("Contexto El Niño")
    try:
        o = noaa.ultimo()
        print(f"  NOAA ONI   {o.temporada} {o.anio}: {o.anom:+.2f}  -> {o.fase}")
    except Exception as e:
        print("  NOAA error:", e)
    try:
        i = igp.ultimo()
        print(f"  IGP  ICEN  {i.anio}-{i.mes:02d}: {i.valor:+.2f}  -> {i.categoria}")
    except Exception as e:
        print("  IGP error:", e)

    seccion("Ríos de Cajamarca (ANA, tiempo real)")
    try:
        rios = ana.caudal_cajamarca()
        rios.sort(key=lambda e: e.estacion)
        for e in rios:
            marca = {"emergencia": "[EMERGENCIA]", "alerta": "[ALERTA]"}.get(e.estado, "")
            v = "s.d." if e.valor is None else f"{e.valor:g} {e.unidad}"
            print(f"  {e.estacion:18} {e.rio:12} {e.hora:>5}  {v:>12}  ({e.estado}) {marca}")
        alertadas = [e for e in rios if e.estado in ("alerta", "emergencia")]
        print(f"  -> {len(rios)} estaciones; {len(alertadas)} en alerta/emergencia.")
    except Exception as e:
        print("  ANA error:", e)
        traceback.print_exc()

    seccion("Lluvia horaria — estación automática de Cajamarca (SENAMHI)")
    try:
        autos = senamhi.estaciones_automaticas("cajamarca")
        meteo = [e for e in autos if e.tipo == "M"] or autos
        if not meteo:
            print("  (sin estaciones automáticas)")
        else:
            est = meteo[0]
            s = senamhi.datos_horarios(est)
            u = s.ultimo or {}
            print(f"  {est.nombre} ({est.cod}) — {len(s.timestamps)} horas")
            print(f"  último: {u.get('ts')}  precip={u.get('precip_mm')} mm  temp={u.get('temp_c')} °C")
            print(f"  precip acumulada 24 h: {s.precip_acumulada(24)} mm")
    except Exception as e:
        print("  SENAMHI error:", e)
        traceback.print_exc()


if __name__ == "__main__":
    main()
