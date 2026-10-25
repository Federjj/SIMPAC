"""
Cargador de las zonas que podrían inundarse junto a los ríos del país (estimadas con el relieve por
backend/mapas/zonas_relieve.py) a la tabla rio_cauce_zona. Lee backend/data/cauces_zonas/<rio>.geojson:
una FeatureCollection por río con una Feature por umbral (subtipo bajo_2m y bajo_3m, clave
'<rio_ana>:relieve:<n>') y, en cada una, metodo, fuente, licencia, atribucion, fecha_fuente, nota y
area_km2. La web las dibuja desde la vista rio_cauce_zona_mapa igual que las del Mashcón (rio_zona).

Carga ÚNICA, a mano (como cargar_rios.py y cargar_cauces.py): son estimaciones calculadas una vez
sobre el relieve, no cambian solas. Honestidad del dato: cada zona lleva su método y la nota de que es
una estimación, no un mapa oficial; un río sin archivo no tiene zonas (nada se inventa).

Validación (la prueba en seco la muestra por río; nada se escribe si algún archivo falla):
  - rio_ana del archivo igual al nombre del archivo y con el formato de rio_cauce ([a-z0-9_]);
  - claves '<rio_ana>:relieve:<n>' sin repetir; subtipo bajo_2m o bajo_3m, cada uno una sola vez;
  - geometría Polygon o MultiPolygon válida (anillos cerrados de 4 puntos o más) dentro del Perú;
  - area_km2 numérico positivo; metodo, fuente, licencia, atribucion y nota no vacíos;
  - fecha_fuente con formato AAAA-MM-DD; un archivo marcado 'descartado' no se carga.

Se corre dentro del contenedor worker (tiene SUPABASE_DB_URL) o con la variable exportada:
    docker compose run --rm worker python -m backend.mapas.cargar_cauces_zonas              # prueba en seco
    docker compose run --rm worker python -m backend.mapas.cargar_cauces_zonas --aplicar    # escribe
Opciones:
    --rio NOMBRE   solo ese río (rio_ana)
    --datos DIR    otra carpeta de archivos (por defecto backend/data/cauces_zonas)
    --podar        con --aplicar, borra de rio_cauce_zona las zonas que ya no están en los archivos (las
                   de ríos sin archivo y las claves que un archivo ya no trae). Sin esto nada se borra:
                   un río que no se pudo calcular esta vez conserva sus zonas anteriores.
Códigos de salida: 0 bien, 1 datos inválidos o carga cancelada, 2 sin SUPABASE_DB_URL o sin la tabla.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

if __package__ in (None, ""):   # permite también: python backend/mapas/cargar_cauces_zonas.py
    sys.path.insert(0, __file__.rsplit("backend", 1)[0])

from backend.db import conectar

log = logging.getLogger("cargar_cauces_zonas")

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "cauces_zonas"

SUBTIPOS = ("bajo_2m", "bajo_3m")
RIO_ANA = re.compile(r"^[a-z0-9_]+$")
LAT_PERU, LON_PERU = (-18.5, 0.1), (-81.5, -68.5)
OBLIGATORIOS = ("metodo", "fuente", "licencia", "atribucion", "nota")


class DatosInvalidos(ValueError):
    pass


# ----------------------------------------------------------------------------- lectura y validación
def leer(carpeta: Path = DATOS) -> dict[str, dict]:
    """{rio_ana: FeatureCollection} de los <rio>.geojson de la carpeta (los que empiezan con _ no son ríos)."""
    archivos = {}
    for ruta in sorted(carpeta.glob("*.geojson")):
        if ruta.name.startswith("_"):
            continue
        archivos[ruta.stem] = json.loads(ruta.read_text(encoding="utf-8"))
    return archivos


def _anillo_ok(anillo) -> bool:
    if not isinstance(anillo, list) or len(anillo) < 4:
        return False
    for p in anillo:
        if not (isinstance(p, list) and len(p) >= 2 and all(isinstance(v, (int, float)) for v in p[:2])):
            return False
        if not (LAT_PERU[0] <= p[1] <= LAT_PERU[1] and LON_PERU[0] <= p[0] <= LON_PERU[1]):
            return False
    return anillo[0][:2] == anillo[-1][:2]


def validar_geometria(g: dict) -> dict:
    """MultiPolygon válido (un Polygon se envuelve). Lanza DatosInvalidos con el motivo."""
    if not isinstance(g, dict):
        raise DatosInvalidos("sin geometría")
    tipo, coords = g.get("type"), g.get("coordinates")
    if tipo == "Polygon":
        coords = [coords]
    elif tipo != "MultiPolygon":
        raise DatosInvalidos(f"geometría {tipo!r}: debe ser Polygon o MultiPolygon")
    if not isinstance(coords, list) or not coords:
        raise DatosInvalidos("MultiPolygon vacío")
    for poli in coords:
        if not isinstance(poli, list) or not poli:
            raise DatosInvalidos("polígono sin anillos")
        for anillo in poli:
            if not _anillo_ok(anillo):
                raise DatosInvalidos("anillo no cerrado, con menos de 4 puntos o con coordenadas fuera del Perú")
    return {"type": "MultiPolygon", "coordinates": coords}


def validar(rio_ana: str, fc: dict) -> list[dict]:
    """Las filas de rio_cauce_zona del río (geometría como GeoJSON para st_geomfromgeojson)."""
    if not RIO_ANA.match(rio_ana):
        raise DatosInvalidos(f"nombre de archivo {rio_ana!r}: solo letras minúsculas, dígitos y guion bajo")
    if not isinstance(fc, dict) or fc.get("type") != "FeatureCollection":
        raise DatosInvalidos("no es una FeatureCollection")
    if fc.get("rio_ana") != rio_ana:
        raise DatosInvalidos(f"rio_ana {fc.get('rio_ana')!r} no coincide con el archivo {rio_ana}")
    if fc.get("descartado"):
        raise DatosInvalidos(f"marcado como descartado: {fc['descartado']}")
    features = fc.get("features") or []
    if not features:
        raise DatosInvalidos("sin zonas (un archivo vacío no borra nada: se rechaza)")
    filas, claves, subtipos = [], set(), set()
    for f in features:
        p = f.get("properties") or {}
        clave = p.get("clave")
        if not isinstance(clave, str) or not re.match(rf"^{re.escape(rio_ana)}:relieve:\d+$", clave):
            raise DatosInvalidos(f"clave {clave!r}: debe ser '{rio_ana}:relieve:<n>'")
        if clave in claves:
            raise DatosInvalidos(f"clave repetida {clave}")
        claves.add(clave)
        if p.get("rio_ana") not in (None, rio_ana):
            raise DatosInvalidos(f"{clave}: rio_ana {p.get('rio_ana')!r} de otro río")
        subtipo = p.get("subtipo")
        if subtipo not in SUBTIPOS:
            raise DatosInvalidos(f"{clave}: subtipo {subtipo!r} (vale {' o '.join(SUBTIPOS)})")
        if subtipo in subtipos:
            raise DatosInvalidos(f"{clave}: subtipo {subtipo} repetido en el río")
        subtipos.add(subtipo)
        area = p.get("area_km2")
        if not isinstance(area, (int, float)) or isinstance(area, bool) or not area > 0:
            raise DatosInvalidos(f"{clave}: area_km2 {area!r} debe ser un número positivo")
        for campo in OBLIGATORIOS:
            if not isinstance(p.get(campo), str) or not p[campo].strip():
                raise DatosInvalidos(f"{clave}: falta {campo}")
        fecha = p.get("fecha_fuente")
        try:
            date.fromisoformat(fecha)
        except (TypeError, ValueError):
            raise DatosInvalidos(f"{clave}: fecha_fuente {fecha!r} debe ser AAAA-MM-DD") from None
        geom = validar_geometria(f.get("geometry"))
        filas.append({
            "clave": clave, "rio_ana": rio_ana, "subtipo": subtipo, "area_km2": float(area),
            "metodo": p["metodo"].strip(), "fuente": p["fuente"].strip(), "licencia": p["licencia"].strip(),
            "atribucion": p["atribucion"].strip(), "fecha_fuente": fecha, "nota": p["nota"].strip(),
            "geom": json.dumps(geom),
        })
    return filas


def resumen(rio_ana: str, filas: list[dict]) -> str:
    partes = ", ".join(f"{f['subtipo']} {f['area_km2']:.2f} km2" for f in sorted(filas, key=lambda f: f["subtipo"]))
    return f"Río {rio_ana}: {len(filas)} zonas ({partes})"


# ----------------------------------------------------------------------------- BD
SQL_HAY_TABLA = "select to_regclass('public.rio_cauce_zona') is not null"
SQL_RIOS_CON_TRAZO = "select rio_ana from rio_cauce where rio_ana = any(%s)"
SQL_UPSERT = """
insert into rio_cauce_zona (clave, rio_ana, subtipo, geom, area_km2, metodo, fuente, licencia, atribucion,
                            fecha_fuente, nota, cargado_en)
values (%(clave)s, %(rio_ana)s, %(subtipo)s,
        st_multi(st_makevalid(st_setsrid(st_geomfromgeojson(%(geom)s), 4326))),
        %(area_km2)s, %(metodo)s, %(fuente)s, %(licencia)s, %(atribucion)s, %(fecha_fuente)s, %(nota)s, now())
on conflict (clave) do update set
  rio_ana = excluded.rio_ana, subtipo = excluded.subtipo, geom = excluded.geom, area_km2 = excluded.area_km2,
  metodo = excluded.metodo, fuente = excluded.fuente, licencia = excluded.licencia, atribucion = excluded.atribucion,
  fecha_fuente = excluded.fecha_fuente, nota = excluded.nota, cargado_en = now()
"""
SQL_PODAR = "delete from rio_cauce_zona where not (clave = any(%s))"


def aplicar(conn, filas: list[dict], podar: bool = False) -> tuple[int, int]:
    """(escritas, borradas). Upsert en la transacción de conn (sin commit); con podar borra las claves que no vienen."""
    with conn.cursor() as cur:
        cur.executemany(SQL_UPSERT, filas)
        borradas = 0
        if podar:
            cur.execute(SQL_PODAR, ([f["clave"] for f in filas],))
            borradas = cur.rowcount
    return len(filas), borradas


def rios_sin_trazo(conn, rios: list[str]) -> list[str]:
    """Ríos de los archivos que no están en rio_cauce: la web no tendría dónde colgar la zona."""
    with conn.cursor() as cur:
        cur.execute(SQL_RIOS_CON_TRAZO, (rios,))
        con_trazo = {r[0] for r in cur.fetchall()}
    return [r for r in rios if r not in con_trazo]


# ----------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Carga las zonas estimadas con el relieve de los ríos del país (rio_cauce_zona).")
    ap.add_argument("--rio", default=None, help="solo ese río (rio_ana)")
    ap.add_argument("--datos", type=Path, default=DATOS, metavar="DIR", help="carpeta de los <rio>.geojson")
    ap.add_argument("--aplicar", action="store_true", help="escribe en la BD (sin esto es prueba en seco)")
    ap.add_argument("--podar", action="store_true", help="con --aplicar, borra las zonas que ya no están en los archivos")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.podar and args.rio:
        log.error("--podar no se combina con --rio: borraría las zonas de todos los demás ríos.")
        return 1

    archivos = leer(args.datos)
    if args.rio:
        archivos = {k: v for k, v in archivos.items() if k == args.rio}
        if not archivos:
            log.error("No hay %s/%s.geojson", args.datos, args.rio)
            return 1
    if not archivos:
        log.error("No hay archivos <rio>.geojson en %s", args.datos)
        return 1

    filas: list[dict] = []
    errores = 0
    for rio_ana, fc in archivos.items():
        try:
            del_rio = validar(rio_ana, fc)
        except DatosInvalidos as e:
            log.error("Río %s: %s", rio_ana, e)
            errores += 1
            continue
        print(resumen(rio_ana, del_rio), flush=True)
        filas.extend(del_rio)
    print(f"{len(archivos) - errores} ríos válidos, {len(filas)} zonas, {errores} archivos con errores", flush=True)
    if errores:
        log.error("Nada se escribe hasta corregir los archivos.")
        return 1
    if not args.aplicar:
        log.info("Prueba en seco: no se escribió nada. Usa --aplicar para guardar.")
        return 0

    try:
        with conectar() as conn:   # una sola transacción: commit al salir, rollback si algo falla
            with conn.cursor() as cur:
                cur.execute(SQL_HAY_TABLA)
                if not cur.fetchone()[0]:
                    log.error("Falta la tabla rio_cauce_zona: aplica antes la migración rio_cauce_zona (supabase/migrations/).")
                    return 2
            sin_trazo = rios_sin_trazo(conn, sorted(archivos))
            if sin_trazo:
                log.error("Sin trazo en rio_cauce (carga antes cargar_cauces.py): %s. No se escribió nada.", ", ".join(sin_trazo))
                return 1
            escritas, borradas = aplicar(conn, filas, podar=args.podar)
    except RuntimeError as e:
        log.error("%s Corre el cargador dentro del contenedor worker.", e)
        return 2
    log.info("Guardado: %d zonas de %d ríos en rio_cauce_zona (%d borradas por --podar).", escritas, len(archivos), borradas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
