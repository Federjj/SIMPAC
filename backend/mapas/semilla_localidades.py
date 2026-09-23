"""
Semilla del catálogo de coordenadas del pronóstico por localidad de SENAMHI
(backend/data/localidades_senamhi.json, lo lee la tarea 'pronostico').

La página de pronóstico no trae coordenadas. Cada localidad casi siempre coincide con una
estación meteorológica de SENAMHI del mismo nombre, en el mismo departamento (la tabla
estacion, que llena la ingesta con el inventario de todos los departamentos). Se corre UNA
vez (o cuando SENAMHI agregue localidades), con red y con BD, y su salida se revisa a mano
y se sube al repo: la tarea nunca inventa un punto.

  1. Baja la página del país (backend/connectors/senamhi_pronostico.py), o lee una guardada
     con --html.
  2. Lee las estaciones meteorológicas (tipo 'M') de la tabla estacion (solo lectura).
  3. Empareja por nombre normalizado (sin tildes ni signos) en el mismo departamento,
     prefiriendo las convencionales (CO, CP, MAP). ALIAS cubre los nombres que no coinciden
     (Cajamarca = AUGUSTO WEBERBAUER) y, si hay homónimas, cuál es.
  4. MANUAL manda sobre lo anterior: ciudades sin estación homónima, con el centro urbano
     aproximado (ubicacion 'ciudad (centro aproximado)').
  5. Imprime las localidades sin resolver y las que tenían varias estaciones posibles.

Se corre dentro del contenedor worker, montando el repo para que el archivo quede en el host:
    docker compose run --rm -v "${PWD}:/app" worker python -m backend.mapas.semilla_localidades
Opciones:
    --html ARCHIVO    lee la página guardada en vez de bajarla
    --salida RUTA     dónde escribir el catálogo (por defecto, el del repo)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):   # permite también: python backend/mapas/semilla_localidades.py
    sys.path.insert(0, __file__.rsplit("backend", 1)[0])

from backend.connectors import senamhi_pronostico as fuente
from backend.connectors.senamhi import HORA_PERU
from backend.db import conectar
from backend.ingesta.departamentos import nombre_departamento
from backend.ingesta.pronostico import CATALOGO

PREFERIDAS = ("CO", "CP", "MAP")   # convencionales: el punto de referencia histórico de la localidad
CIUDAD = "ciudad (centro aproximado)"
SQL_ESTACIONES = ("select cod, nombre, categoria, departamento, lat, lon from estacion "
                  "where tipo = 'M' and geom is not null")

# Nombre normalizado de la localidad -> (nombre normalizado de la estación, punto para elegir
# entre homónimas del mismo departamento o None). Verificados con el inventario del 22-09-2026.
ALIAS: dict[str, tuple[str, tuple[float, float] | None]] = {
    "CAJAMARCA": ("AUGUSTO WEBERBAUER", None),
    "ENCANADA": ("LA ENCANADA", None),
    # hay otra SAN MIGUEL en la provincia de San Ignacio; la de San Miguel de Pallaques es la CO
    "SAN MIGUEL DE PALLAQUES": ("SAN MIGUEL", (-6.99684, -78.85308)),
    # la estación lleva el nombre del lugar más otra palabra (revisadas una por una)
    "ATICO": ("PUNTA ATICO", None),
    "MAJES": ("PAMPA DE MAJES", None),
    "ANTA": ("ANTA ANCACHURO", None),
    "BERNALES": ("HACIENDA BERNALES", None),
    "CHINCHA": ("FONAGRO CHINCHA", None),
    "HUACHO": ("UNJF SANCHEZ CARRION HUACHO", None),
    "SAN VICENTE DE CANETE": ("CANETE", None),
    "JENARO HERRERA": ("GENARO HERRERA", None),
    "STA RITA DE CASTILLA": ("SANTA RITA DE CASTILLA", None),
    "MOHO": ("HUARAYA MOHO", None),
    "YUNGUYO": ("TAHUACO YUNGUYO", None),
}

# codigo -> (lat, lon, ubicacion). Ciudades sin estación homónima: las 13 de la maqueta
# (centro urbano aproximado) y las capitales, con las coordenadas de frontend/src/data/cities.js.
MANUAL: dict[str, tuple[float, float, str]] = {
    "20-0003": (-5.1945, -80.6328, CIUDAD),     # Piura
    "14-0004": (-6.7714, -79.8409, CIUDAD),     # Chiclayo
    "24-0002": (-3.5669, -80.4515, CIUDAD),     # Tumbes
    "20-0151": (-4.9039, -80.6853, CIUDAD),     # Sullana
    "20-0034": (-4.5772, -81.2719, CIUDAD),     # Talara
    "20-0149": (-5.0892, -81.1144, CIUDAD),     # Paita
    "13-0280": (-7.2271, -79.4292, CIUDAD),     # Chepén
    "01-0118": (-5.7561, -78.4436, CIUDAD),     # Bagua Grande
    "01-0309": (-5.9444, -77.9775, CIUDAD),     # Pedro Ruiz
    "14-0307": (-5.9853, -79.7461, CIUDAD),     # Olmos
    "14-0134": (-6.1519, -79.7142, CIUDAD),     # Motupe
    "14-0128": (-6.6408, -79.3894, CIUDAD),     # Chongoyape
    "22-0324": (-7.1778, -76.7289, CIUDAD),     # Juanjuí
    "02-0013": (-9.5278, -77.5278, CIUDAD),     # Huaraz
    "03-0031": (-13.6339, -72.8814, CIUDAD),    # Abancay
    "04-0018": (-16.409, -71.5375, CIUDAD),     # Arequipa
    "05-0017": (-13.1587, -74.2239, CIUDAD),    # Ayacucho
    "08-0019": (-13.532, -71.9675, CIUDAD),     # Cusco
    "11-0029": (-14.0678, -75.7286, CIUDAD),    # Ica
    "12-0028": (-12.0686, -75.2103, CIUDAD),    # Huancayo
    "15-0001": (-12.0464, -77.0428, CIUDAD),    # Lima Oeste / Callao (el centro de Lima)
    "16-0021": (-3.7491, -73.2538, CIUDAD),     # Iquitos
    "23-0010": (-18.0066, -70.2463, CIUDAD),    # Tacna
}


def normalizar(nombre: str) -> str:
    """'Chancay Baños' -> 'CHANCAY BANOS'; 'LIMA OESTE / CALLAO' -> 'LIMA OESTE CALLAO'."""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^A-Z]+", " ", sin_tildes.upper()).split())


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat2 - lat1) * 111.2
    dx = (lon2 - lon1) * 111.2 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def emparejar(localidades: list[fuente.Localidad], estaciones: list[tuple]) -> tuple[dict, list[str], list[str]]:
    """
    (catálogo {codigo: entrada}, sin resolver, notas de homónimas). estaciones: filas
    (cod, nombre, categoria, departamento, lat, lon) de la tabla estacion.
    """
    por_nombre: dict[tuple[str | None, str], list[tuple]] = {}
    for e in estaciones:
        por_nombre.setdefault((nombre_departamento(e[3]), normalizar(e[1])), []).append(e)
    catalogo: dict[str, dict] = {}
    sin_resolver: list[str] = []
    notas: list[str] = []
    for loc in localidades:
        nombre, _, depto = loc.nombre_senamhi.rpartition(" - ")
        depto = nombre_departamento(depto)
        n = normalizar(nombre or loc.nombre_senamhi)
        alias, cerca = ALIAS.get(n, (None, None))
        candidatas = por_nombre.get((depto, n)) or (por_nombre.get((depto, alias)) if alias else None) or []
        if cerca:
            candidatas = sorted(candidatas, key=lambda e: _km(cerca[0], cerca[1], e[4], e[5]))[:1]
        else:
            candidatas = sorted(candidatas, key=lambda e: (e[2] not in PREFERIDAS, e[0]))
            mejores = [e for e in candidatas if (e[2] in PREFERIDAS) == (candidatas[0][2] in PREFERIDAS)]
            if len(mejores) > 1:
                notas.append(f"{loc.codigo} {loc.nombre_senamhi}: varias estaciones posibles, se usa la primera: "
                             + "; ".join(f"{e[1]} {e[2]} {e[0]} ({e[4]:.5f}, {e[5]:.5f})" for e in mejores))
        entrada = None
        if candidatas:
            cod, nom, cat, _, lat, lon = candidatas[0]
            entrada = {"nombre_senamhi": loc.nombre_senamhi, "lat": round(lat, 5), "lon": round(lon, 5),
                       "ubicacion": f"estación SENAMHI {nom} ({cat or 's/c'})"}
        if loc.codigo in MANUAL:
            lat, lon, ubicacion = MANUAL[loc.codigo]
            if entrada:
                notas.append(f"{loc.codigo} {loc.nombre_senamhi}: MANUAL reemplaza a la {entrada['ubicacion']}")
            entrada = {"nombre_senamhi": loc.nombre_senamhi, "lat": lat, "lon": lon, "ubicacion": ubicacion}
        if entrada:
            catalogo[loc.codigo] = entrada
        else:
            sin_resolver.append(f"{loc.codigo} {loc.nombre_senamhi}")
    return catalogo, sin_resolver, notas


def escribir(ruta: Path, catalogo: dict, sin_resolver: list[str]) -> None:
    """Una localidad por línea (diffs legibles al revisar)."""
    lineas = [f"  {json.dumps(c)}: {json.dumps(catalogo[c], ensure_ascii=False)}" for c in sorted(catalogo)]
    texto = ('{"generado": ' + json.dumps(datetime.now(HORA_PERU).date().isoformat())
             + ',\n "sin_ubicar": ' + json.dumps(sorted(sin_resolver), ensure_ascii=False)
             + ',\n "localidades": {\n' + ",\n".join(lineas) + "\n}}\n")
    json.loads(texto)   # que sea JSON válido antes de escribirlo
    ruta.write_text(texto, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Arma el catálogo de coordenadas del pronóstico por localidad.")
    ap.add_argument("--html", type=Path, help="página del país ya guardada (si no, se baja)")
    ap.add_argument("--salida", type=Path, default=CATALOGO)
    args = ap.parse_args(argv)

    hoy = datetime.now(HORA_PERU).date()
    if args.html:
        pron = fuente.parse_pagina(fuente.decodificar(args.html.read_bytes()), hoy)
    else:
        pron = fuente.pronostico_pais(hoy)
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_ESTACIONES)
        estaciones = [(cod, nom, cat, dep, float(lat), float(lon)) for cod, nom, cat, dep, lat, lon in cur.fetchall()]
    catalogo, sin_resolver, notas = emparejar(pron.localidades, estaciones)
    escribir(args.salida, catalogo, sin_resolver)
    print(f"emisión {pron.emision}: {len(pron.localidades)} localidades, {len(estaciones)} estaciones M")
    print(f"con punto: {len(catalogo)}; sin resolver: {len(sin_resolver)} -> {args.salida}")
    for s in sin_resolver:
        print("  SIN RESOLVER", s)
    for n in notas:
        print("  REVISAR", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
