"""
Cargador de "A dónde acudir" a Supabase (tabla punto_acudir): establecimientos de salud,
comisarías, compañías de bomberos y oficinas de Defensa Civil con coordenadas, todos de fuentes
oficiales y cada uno con su fuente, licencia y fecha.

Es una carga manual (como los ríos vigilados), no una tarea del worker: las fuentes cambian poco
(RENIPRESS publica un CSV al mes; el padrón de comisarías es de 2019). Lee los archivos de
backend/data/acudir/ y, con --descargar, los vuelve a bajar de las fuentes:

  fuentes.json              de dónde y cuándo se bajó cada archivo (url, actualizado, licencia)
  renipress_cajamarca.csv   SUSALUD RENIPRESS (datosabiertos.gob.pe), solo el dpto. Cajamarca
                            (el CSV del país pesa 20 MB: con --pais se baja a una caché temporal)
  comisarias_cenepred.json  capa 12 'ComisariasBasicas' del servicio CENEPRED COEN_FEN_2027
                            (padrón MININTER de noviembre de 2019 ya como puntos WGS84), todo el país
  bomberos_cenepred.json    capa 14 'Bomberos' del mismo servicio: el punto de cada compañía
  bomberos_cgbvp.json       directorio del portal del CGBVP (dirección y teléfono por compañía)
  defensa_civil.json        puntos capturados a mano de fichas de gob.pe (INDECI, municipalidad,
                            gobierno regional), con la URL de la ficha y la fecha de verificación
  numeros.json              números de emergencia para el panel "Llama a" (no van a la BD; el
                            frontend tiene una copia en frontend/src/data/emergencias.js)

Qué entra como "a dónde acudir" (y qué no):
  - salud: solo IPRESS ACTIVAS con coordenadas que sean hospital, clínica, centro de salud, puesto
    de salud o policlínico (no consultorios, laboratorios, ópticas ni centros odontológicos) y que
    no sean penitenciarias. atiende_24h sale del texto libre HORARIO; si no se entiende, queda null.
  - comisaria y bomberos: todos los puntos del país. Sin horario en la fuente: atiende_24h null.
  - albergues y zonas seguras: NO se cargan. Al 14-10-2026 no hay fuente oficial abierta con esos
    datos (ni INDECI, ni CENEPRED, ni la municipalidad); cuando exista se carga con su fuente_url.

Por defecto es una prueba en seco: valida, cuenta y no escribe. Con --aplicar escribe en UNA
transacción (upsert por clave, idempotente). Nunca borra nada por sí solo: --podar quita, solo
dentro de las fuentes y departamentos que se cargaron, las claves que ya no vienen. Si una fuente
no se puede bajar, --descargar deja el archivo anterior y avisa (una fuente caída no borra datos).

Se corre dentro del contenedor worker, que tiene SUPABASE_DB_URL:
    docker compose run --rm worker python -m backend.mapas.cargar_acudir                 # en seco
    docker compose run --rm worker python -m backend.mapas.cargar_acudir --aplicar
    docker compose run --rm worker python -m backend.mapas.cargar_acudir --descargar     # refresca los archivos
    docker compose run --rm worker python -m backend.mapas.cargar_acudir --descargar --pais --aplicar
Opciones:
    --datos DIR    lee los archivos de otra carpeta
    --pais         salud de todo el país (usa la caché temporal del CSV completo; con --descargar la llena)
    --podar        con --aplicar, borra las claves que ya no vienen (dentro de lo cargado)
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
import ssl
import sys
import tempfile
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

if __package__ in (None, ""):   # permite también: python backend/mapas/cargar_acudir.py
    sys.path.insert(0, __file__.rsplit("backend", 1)[0])

from backend.connectors._http import con_reintentos
from backend.db import conectar
from backend.ingesta.departamentos import DEPARTAMENTOS, nombre_departamento

log = logging.getLogger("cargar_acudir")

DATOS = Path(__file__).resolve().parents[1] / "data" / "acudir"
CACHE_PAIS = Path(tempfile.gettempdir()) / "simpac_acudir"      # CSV del país (20 MB): no va al repo
ARCHIVOS = {
    "fuentes": "fuentes.json",
    "renipress": "renipress_cajamarca.csv",
    "comisarias": "comisarias_cenepred.json",
    "bomberos_cenepred": "bomberos_cenepred.json",
    "bomberos_cgbvp": "bomberos_cgbvp.json",
    "manual": "defensa_civil.json",
    "numeros": "numeros.json",
}

# Fuentes (verificadas el 14-10-2026).
FICHA_RENIPRESS = ("https://www.datosabiertos.gob.pe/dataset/"
                   "registro-nacional-de-entidades-prestadoras-de-servicios-de-salud-renipress")
BASE_RENIPRESS = "https://www.datosabiertos.gob.pe/sites/default/files/"
CENEPRED = "https://sig.cenepred.gob.pe/arcgis_server/rest/services/sectores/COEN_FEN_2027/MapServer"
CAPA_COMISARIAS, CAPA_BOMBEROS = 12, 14
CGBVP_API = "https://portal.bomberosperu.gob.pe/api/"
CGBVP_PAGINA = "https://portal.bomberosperu.gob.pe/comandancias-departamentales/"
FICHA_COMISARIAS = ("https://www.datosabiertos.gob.pe/dataset/"
                    "comisar%C3%ADas-b%C3%A1sicas-de-la-polic%C3%ADa-nacional-del-per%C3%BA-mininter")
# El padrón de comisarías que sirve CENEPRED es el de MININTER "a noviembre de 2019" (sin fecha en
# los metadatos del servicio): es la fecha del dato, no la de la descarga.
FECHA_PADRON_COMISARIAS = "2019-11-30"
# datosabiertos.gob.pe y el portal del CGBVP responden 403 a un User-Agent que no sea de navegador.
UA_NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0 Safari/537.36")
_CTX = ssl.create_default_context()

TIPOS = ("salud", "comisaria", "bomberos", "zona_segura", "albergue", "otro")
CANONICOS = set(DEPARTAMENTOS.values()) | {"Callao"}
# Recuadro del Perú: atrapa una lat/lon invertida o un (0, 0).
LAT_PERU, LON_PERU = (-18.5, 0.1), (-81.5, -68.5)
COLUMNAS_RENIPRESS = ("INSTITUCION", "COD_IPRESS", "NOMBRE", "CLASIFICACION", "DEPARTAMENTO", "PROVINCIA",
                      "DISTRITO", "UBIGEO", "DIRECCION", "CATEGORIA", "TELEFONO", "HORARIO", "ESTADO", "NORTE", "ESTE")
# Clasificación RENIPRESS -> etiqueta en lenguaje claro. Lo que no está aquí (consultorios,
# laboratorios, ópticas, odontológicos, hemodiálisis...) no es "a dónde acudir" y se descarta.
CLASIFICACION_SALUD = {
    "HOSPITALES O CLINICAS DE ATENCION GENERAL": "Hospital",
    "HOSPITALES O CLINICAS DE ATENCION ESPECIALIZADA": "Hospital especializado",
    "INSTITUTOS DE SALUD ESPECIALIZADOS": "Instituto especializado",
    "CENTROS DE SALUD CON CAMAS DE INTERNAMIENTO": "Centro de salud con camas",
    "CENTROS DE SALUD O CENTROS MEDICOS": "Centro de salud",
    "PUESTOS DE SALUD O POSTAS DE SALUD": "Puesto de salud",
    "POLICLINICOS": "Policlínico",
}
CAMPOS_FILA = ("clave", "tipo", "nombre", "categoria", "atiende_24h", "direccion", "distrito", "provincia",
               "departamento", "ubigeo", "telefono", "lat", "lon", "fuente", "fuente_url", "fuente_id", "licencia",
               "atribucion", "detalle", "actualizado")
CAMPOS_MANUAL = ("clave", "tipo", "nombre", "categoria", "direccion", "departamento", "provincia", "distrito",
                 "lat", "lon", "fuente", "fuente_url", "atribucion", "actualizado")
CAMPOS_NUMERO = ("ambito", "servicio", "numero", "fuente_url", "verificado")


# ----------------------------------------------------------------------------------------------
# Normalización
# ----------------------------------------------------------------------------------------------

# Siempre en minúscula (salvo al inicio): preposiciones y conjunciones. Los artículos solo tras una
# preposición ('Baños del Inca', 'Virgen de la Puerta'), porque en los nombres propios van con
# mayúscula ('Clínica Los Fresnos', 'Los Baños del Inca').
_MINUSCULAS = {"de", "del", "y", "e", "en", "al", "con", "por", "para", "a", "o", "u"}
_ARTICULOS = {"la", "las", "los", "el"}
_SIGLAS = {"PNP", "CPNP", "INPE", "MINSA", "CBP", "CGBVP", "UNC", "UPN", "EP", "SRL", "SAC", "EIRL", "SA", "CLAS",
           "ONG", "AA", "HH", "EMG", "IPRESS", "MPC", "GORE", "INDECI", "COER", "DIRESA", "AM", "PM"}
_ROMANO = re.compile(r"^(?=[IVXLC]+$)(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$")
# Tildes de las palabras más frecuentes en los nombres (las fuentes vienen sin tildes y en mayúsculas).
_TILDES = {
    "clinica": "clínica", "medico": "médico", "medica": "médica", "odontologico": "odontológico",
    "policlinico": "policlínico", "pediatrico": "pediátrico", "atencion": "atención", "region": "región",
    "comisaria": "comisaría", "compañia": "compañía", "jose": "josé", "maria": "maría", "jesus": "jesús",
    "martin": "martín", "simon": "simón", "bolivar": "bolívar", "ramon": "ramón", "peru": "perú", "jaen": "jaén",
    "celendin": "celendín", "contumaza": "contumazá", "encañada": "encañada", "andres": "andrés", "nicolas": "nicolás",
    "belen": "belén", "fatima": "fátima", "concepcion": "concepción", "asuncion": "asunción", "union": "unión",
    "rehabilitacion": "rehabilitación", "especializacion": "especialización", "diagnostico": "diagnóstico",
    "numero": "número", "basico": "básico", "basica": "básica", "publica": "pública", "publico": "público",
    "quiñones": "quiñones", "ancash": "áncash", "huanuco": "huánuco", "junin": "junín", "apurimac": "apurímac",
    "san martin": "san martín", "sanchez": "sánchez", "rodriguez": "rodríguez", "gonzalez": "gonzález",
    "gutierrez": "gutiérrez", "hernandez": "hernández", "fernandez": "fernández", "perez": "pérez",
    "garcia": "garcía", "lopez": "lópez", "ramirez": "ramírez", "chavez": "chávez", "velasquez": "velásquez",
}


def nombre_bonito(texto: str | None) -> str | None:
    """
    'HOSPITAL REGIONAL DOCENTE DE CAJAMARCA' -> 'Hospital Regional Docente de Cajamarca'.
    Mayúscula inicial en cada palabra salvo artículos y preposiciones; siglas, números romanos y
    categorías (II-2, I-E) en mayúsculas; tildes de las palabras más frecuentes.
    """
    if texto is None:
        return None
    texto = re.sub(r"\s+", " ", texto.strip())
    if not texto:
        return None
    anterior = [None]   # palabra anterior en minúscula (None al inicio)

    def caso(w: str, acronimo: bool) -> str:
        up, low = w.upper(), w.lower()
        if up in _SIGLAS or _ROMANO.match(up) or acronimo:   # 'PNP', 'II', 'S.A.C.'
            salida = up
        elif up == "ESSALUD":
            salida = "EsSalud"
        elif anterior[0] is not None and (low in _MINUSCULAS or (low in _ARTICULOS and anterior[0] in _MINUSCULAS)):
            salida = low
        else:
            base = _TILDES.get(low, low)
            salida = base[:1].upper() + base[1:]
        anterior[0] = low
        return salida

    def palabra(m: re.Match) -> str:
        w = m.group(0)
        # Letra suelta con punto ('S.A.C.', 'P.S') o pegada a un punto anterior: sigla. 'Av.' y 'No.' no.
        sigue_punto = m.end() < len(texto) and texto[m.end()] == "."
        acronimo = sigue_punto and (len(w) == 1 or (m.start() > 0 and texto[m.start() - 1] == "."))
        if "-" in w:                                       # 'II-2', 'II-E', 'I-4'
            if re.fullmatch(r"[IVX]+-[0-9E]", w.upper()):
                anterior[0] = w.lower()
                return w.upper()
            return "-".join(caso(p, False) for p in w.split("-"))
        return caso(w, acronimo)

    return re.sub(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:-[A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ]+)*", palabra, texto)


def nombre_comisaria(texto: str) -> str:
    """'CPNP CENTRAL CAJAMARCA' -> 'Comisaría Central Cajamarca'; 'CPNP BAÑOS DEL INCA' -> 'Comisaría Baños del Inca'."""
    resto = re.sub(r"^\s*(CPNP|COMISARIA|COMISARÍA)\s+(PNP\s+)?", "", texto.strip(), flags=re.I)
    return "Comisaría " + (nombre_bonito(resto) or "")


def nombre_bomberos(texto: str) -> str:
    """'Cajamarca Nº59' -> 'Compañía de Bomberos Cajamarca Nº 59'."""
    con_espacio = re.sub(r"\bN[º°]\s*(\d+)", r"Nº \1", texto.strip(), flags=re.I)
    return "Compañía de Bomberos " + (nombre_bonito(con_espacio) or "")


def telefono_limpio(texto: str | None) -> str | None:
    """
    Como lo da la fuente, solo con los espacios normalizados: '076 - 363333' -> '076-363333',
    '076599040; 076599030' -> '076599040 / 076599030'. None si no tiene al menos 6 dígitos ('0', '').
    """
    if not texto:
        return None
    t = re.sub(r"\s+", " ", str(texto).strip())
    # Separadores entre números: ';', '/' y el guion con espacios cuando ambos lados son un número
    # ('044-233333 - 044-294104'); '076 - 363333' es un solo número (código y número).
    trozos = re.split(r"(\s*[;/]\s*|\s+-\s+)", t)
    salida = trozos[0]
    for sep, siguiente in zip(trozos[1::2], trozos[2::2]):
        numero = "-" in sep and (len(re.sub(r"\D", "", salida.split(" / ")[-1])) < 6
                                 or len(re.sub(r"\D", "", siguiente)) < 6)
        salida += ("-" if numero else " / ") + siguiente
    t = re.sub(r"\s*-\s*", "-", salida).strip(" /")
    if len(re.sub(r"\D", "", t)) < 6:
        return None
    return t


def atiende_24h(horario: str | None) -> bool | None:
    """
    Lee el texto libre HORARIO de RENIPRESS. True: '24 HORAS', '24HRS', '00:00 - 24:00', 'L-D 00 -24',
    '7:00 - 7:00' (empieza y termina a la misma hora). False: un rango de horas que no es de 24 h o
    '12 HORAS'. None: vacío o no se entiende (nunca se adivina).
    """
    t = re.sub(r"\s+", " ", (horario or "").strip().upper())
    t = re.sub(r"\b([AP])\.?\s?M\.?", r"\1M", t).replace(".", ":")      # '7 a.m.' -> '7 AM'
    if not t:
        return None
    if (re.search(r"\b24\s*H", t)                               # '24 HORAS', '24HRS', '24 H'
            or re.match(r"^(?:[A-Z-]+ )*24:00\b", t)               # '24:00 HORAS', 'L-D 24:00' (no '6:00 - 24:00')
            or "LAS 24" in t
            or re.search(r"\b0?0:00\s*(-|A)\s*24:00", t)           # '00:00 - 24:00'
            or re.search(r"(?<![\d:])00?\s*-\s*24\b", t)           # 'L-D 00 -24' (no '1:00 - 24:00')
            or re.search(r"\b24\b\s*$", t)):                       # 'LUNES A DOMINGO: 24'
        return True
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([AP]M)?\s*(?:-|A)\s*(\d{1,2})(?::(\d{2}))?\s*([AP]M)?", t)
    if m:
        h1, m1, h2, m2 = int(m.group(1)), int(m.group(2) or 0), int(m.group(4)), int(m.group(5) or 0)
        if m.group(6) == "PM" and h2 < 12:      # '7:00 A 7 PM' son 12 h, no 24
            h2 += 12
        if m.group(3) == "PM" and h1 < 12:
            h1 += 12
        return (h1, m1) == (h2, m2)
    if re.search(r"\b12 H", t):
        return False
    return None


def _coord(texto) -> float | None:
    if texto is None:
        return None
    try:
        return float(str(texto).strip().replace(",", "."))
    except ValueError:
        return None


def _en_peru(lat: float, lon: float) -> bool:
    return LAT_PERU[0] <= lat <= LAT_PERU[1] and LON_PERU[0] <= lon <= LON_PERU[1]


def _fecha(texto, donde: str) -> str:
    try:
        return date.fromisoformat(str(texto)[:10]).isoformat()
    except (TypeError, ValueError):
        raise ValueError(f"{donde}: fecha {texto!r} no es AAAA-MM-DD") from None


# ----------------------------------------------------------------------------------------------
# Parseo de cada fuente -> filas de punto_acudir
# ----------------------------------------------------------------------------------------------

def parsear_renipress(texto_csv: str, meta: dict) -> tuple[list[dict], Counter]:
    """
    CSV de RENIPRESS (separado por ';', con BOM) -> filas tipo 'salud' y el conteo de lo descartado.
    meta: la entrada 'renipress' de fuentes.json (url, actualizado, licencia).
    """
    lector = csv.DictReader(io.StringIO(texto_csv.lstrip("\ufeff")), delimiter=";")
    faltan = [c for c in COLUMNAS_RENIPRESS if c not in (lector.fieldnames or [])]
    if faltan:
        raise ValueError(f"RENIPRESS: faltan columnas {faltan} (¿cambió el formato del CSV?)")
    filas, descartes = [], Counter()
    for r in lector:
        if (r["ESTADO"] or "").strip().upper() != "ACTIVO":
            descartes["no activo"] += 1
            continue
        clasif = (r["CLASIFICACION"] or "").split(",")[0].strip().upper()
        etiqueta = CLASIFICACION_SALUD.get(clasif)
        if not etiqueta:
            descartes["no es hospital, centro, puesto ni policlínico"] += 1
            continue
        institucion = (r["INSTITUCION"] or "").strip().upper()
        if institucion == "INPE" or "PENITENCIARI" in (r["NOMBRE"] or "").upper():
            descartes["penitenciario (no es de acceso público)"] += 1
            continue
        lat, lon = _coord(r["NORTE"]), _coord(r["ESTE"])
        if lat is None or lon is None:
            descartes["sin coordenadas"] += 1
            continue
        if not _en_peru(lat, lon):
            descartes["coordenadas fuera del Perú"] += 1
            continue
        if institucion == "PRIVADO" and etiqueta.startswith("Hospital"):
            etiqueta = etiqueta.replace("Hospital", "Clínica")
        nivel = (r["CATEGORIA"] or "").strip()
        horario = re.sub(r"\s+", " ", (r["HORARIO"] or "").strip()) or None
        detalle = {
            "institucion": institucion or None,
            "clasificacion": clasif,
            "nivel": nivel if nivel and nivel != "0" else None,
            "horario": horario,
            "con_internamiento": "CON INTERNAMIENTO" in (r.get("TIPO_ESTABLECIMIENTO") or "").upper(),
        }
        filas.append({
            "clave": f"renipress:{r['COD_IPRESS'].strip()}",
            "tipo": "salud",
            "nombre": nombre_bonito(r["NOMBRE"]),
            "categoria": f"{etiqueta} {nivel}" if detalle["nivel"] else etiqueta,
            "atiende_24h": atiende_24h(horario),
            "direccion": nombre_bonito(r["DIRECCION"]),
            "distrito": nombre_bonito(r["DISTRITO"]),
            "provincia": nombre_bonito(r["PROVINCIA"]),
            "departamento": nombre_departamento(r["DEPARTAMENTO"]),
            "ubigeo": (r["UBIGEO"] or "").strip()[:6] or None,
            "telefono": telefono_limpio(r["TELEFONO"]),
            "lat": lat, "lon": lon,
            "fuente": "SUSALUD RENIPRESS",
            "fuente_url": meta["url"],
            "fuente_id": r["COD_IPRESS"].strip(),
            "licencia": meta.get("licencia"),
            "atribucion": "Fuente: SUSALUD, Registro Nacional de IPRESS (RENIPRESS), datosabiertos.gob.pe",
            "detalle": detalle,
            "actualizado": _fecha(meta["actualizado"], "fuentes.json renipress"),
        })
    return filas, descartes


def _punto_geojson(f: dict) -> tuple[float, float] | None:
    g = f.get("geometry") or {}
    if g.get("type") != "Point" or len(g.get("coordinates") or []) < 2:
        return None
    lon, lat = g["coordinates"][0], g["coordinates"][1]
    return (lat, lon) if lat is not None and lon is not None else None


def parsear_comisarias(geojson: dict, meta: dict) -> tuple[list[dict], Counter]:
    """Capa 12 'ComisariasBasicas' de CENEPRED (GeoJSON, WGS84) -> filas tipo 'comisaria'."""
    filas, descartes = [], Counter()
    for f in geojson.get("features", []):
        p = f.get("properties") or {}
        cod = (p.get("cod_cpnp") or "").strip()
        if not cod:
            descartes["sin cod_cpnp"] += 1
            continue
        punto = _punto_geojson(f)
        if punto is None:
            descartes["sin coordenadas"] += 1
            continue
        if not _en_peru(*punto):
            descartes["coordenadas fuera del Perú"] += 1
            continue
        tipo_comi = (p.get("tipo_comi") or "").strip().upper() or None
        filas.append({
            "clave": f"comisarias:{cod}",
            "tipo": "comisaria",
            "nombre": nombre_comisaria(p.get("comisaria") or ""),
            "categoria": f"Comisaría tipo {tipo_comi}" if tipo_comi else "Comisaría",
            "atiende_24h": None,                      # la fuente no trae horario
            "direccion": None,                        # ni dirección ni teléfono
            "distrito": nombre_bonito(p.get("distrito")),
            "provincia": nombre_bonito(p.get("provincia")),
            "departamento": nombre_departamento(p.get("departamen")),
            "ubigeo": (p.get("id_dist") or "").strip()[:6] or None,
            "telefono": None,
            "lat": punto[0], "lon": punto[1],
            "fuente": "MININTER (padrón de comisarías) vía CENEPRED COEN_FEN_2027",
            "fuente_url": meta["url"],
            "fuente_id": cod,
            "licencia": meta.get("licencia"),
            "atribucion": "Fuente: MININTER, comisarías básicas PNP (nov. 2019), servido por CENEPRED/COEN",
            "detalle": {
                "tipo_comisaria": tipo_comi,
                "region_policial": (p.get("regionpol") or "").strip() or None,
                "division": (p.get("divpol_div") or "").strip() or None,
                "nota": meta.get("nota"),
            },
            "actualizado": _fecha(meta["actualizado"], "fuentes.json comisarias"),
        })
    return filas, descartes


def _numero_compania(texto: str | None) -> str | None:
    """'B-59' -> '59'; 'Cajamarca Nº59' -> '59'; 'LA UNION Nº240' -> '240'."""
    if not texto:
        return None
    m = re.search(r"N[º°]\s*(\d+)", texto, flags=re.I) or re.search(r"(\d+)\s*$", texto) or re.search(r"\d+", texto)
    return m.group(1) if m and m.lastindex else (m.group(0) if m else None)


def parsear_bomberos(geojson: dict, cgbvp: dict, meta_cenepred: dict, meta_cgbvp: dict) -> tuple[list[dict], Counter]:
    """
    Capa 14 'Bomberos' de CENEPRED (el punto de cada compañía) cruzada por número de compañía con
    el directorio del portal del CGBVP (dirección y teléfono) -> filas tipo 'bomberos'.
    Una compañía del CGBVP sin punto en CENEPRED no se carga (no se geocodifica a mano).
    """
    directorio: dict[str, dict] = {}
    for lista in (cgbvp.get("companias") or {}).values():
        for c in lista:
            n = _numero_compania(c.get("nombre"))
            if n:
                directorio.setdefault(n, c)
    filas, descartes, usadas = [], Counter(), set()
    for f in geojson.get("features", []):
        p = f.get("properties") or {}
        n = _numero_compania(p.get("cia")) or _numero_compania(p.get("nombre"))
        if not n:
            descartes["sin número de compañía"] += 1
            continue
        punto = _punto_geojson(f)
        if punto is None or not _en_peru(*punto):
            descartes["sin coordenadas o fuera del Perú"] += 1
            continue
        c = directorio.get(n)
        usadas.add(n)
        if c is None:
            descartes["punto CENEPRED sin ficha en el portal CGBVP (sin dirección ni teléfono)"] += 1
        filas.append({
            "clave": f"bomberos:{n}",
            "tipo": "bomberos",
            "nombre": nombre_bomberos((c or {}).get("nombre") or p.get("nombre") or f"Nº{n}"),
            "categoria": "Compañía de bomberos",
            "atiende_24h": None,
            "direccion": nombre_bonito((c or {}).get("direccion")) if c else None,
            "distrito": nombre_bonito(p.get("distrito")),
            "provincia": nombre_bonito(p.get("provincia")),
            "departamento": nombre_departamento(p.get("departamen")),
            "ubigeo": (p.get("id_dist") or "").strip()[:6] or None,
            "telefono": telefono_limpio((c or {}).get("telefonos")) if c else None,
            "lat": punto[0], "lon": punto[1],
            "fuente": "CGBVP (portal) + CENEPRED COEN_FEN_2027 (ubicación)",
            "fuente_url": meta_cgbvp["url"],
            "fuente_id": n,
            "licencia": None,
            "atribucion": "Fuente: CGBVP, portal.bomberosperu.gob.pe; ubicación: CENEPRED/COEN, capa Bomberos",
            "detalle": {
                "comandancia": (p.get("comandanci") or "").strip() or None,
                "cia": (p.get("cia") or "").strip() or None,
                "codidenest": (c or {}).get("codidenest"),
                "fundacion": (c or {}).get("fecha_fundacion"),
                "coordenadas_de": meta_cenepred["url"],
                "sin_directorio_cgbvp": c is None or None,
            },
            "actualizado": _fecha(meta_cgbvp["actualizado"], "fuentes.json bomberos_cgbvp"),
        })
    descartes["compañía CGBVP sin punto en CENEPRED (no se carga)"] += len(set(directorio) - usadas)
    return filas, descartes


def parsear_manual(datos: dict) -> list[dict]:
    """defensa_civil.json: puntos capturados a mano; todos los campos son obligatorios y se revisan."""
    filas = []
    for p in datos.get("puntos", []):
        donde = f"defensa_civil.json {p.get('clave')!r}"
        falta = [c for c in CAMPOS_MANUAL if p.get(c) in (None, "")]
        if falta:
            raise ValueError(f"{donde}: faltan {falta}")
        if not str(p["clave"]).startswith("manual:"):
            raise ValueError(f"{donde}: la clave debe empezar con 'manual:'")
        detalle = p.get("detalle") or {}
        if not isinstance(detalle, dict) or not detalle.get("verificado_en"):
            raise ValueError(f"{donde}: detalle.verificado_en es obligatorio (cuándo se comprobó la ficha)")
        _fecha(detalle["verificado_en"], f"{donde} verificado_en")
        filas.append({**{c: None for c in CAMPOS_FILA}, **{c: p.get(c) for c in CAMPOS_FILA if c in p},
                      "detalle": detalle, "actualizado": _fecha(p["actualizado"], donde)})
    return filas


def validar_fila(f: dict) -> dict:
    """Lo mismo que exigen los CHECK de la tabla, con un error claro; devuelve la fila lista para SQL."""
    donde = f"punto {f.get('clave')!r}"
    if not re.fullmatch(r"[a-z_]+:[A-Za-z0-9_.-]+", str(f.get("clave") or "")):
        raise ValueError(f"{donde}: clave inválida (se espera '<fuente>:<id>')")
    if f.get("tipo") not in TIPOS:
        raise ValueError(f"{donde}: tipo {f.get('tipo')!r} no es uno de {TIPOS}")
    for c in ("nombre", "fuente", "fuente_url", "atribucion", "actualizado"):
        if not f.get(c):
            raise ValueError(f"{donde}: falta {c}")
    if f["departamento"] not in CANONICOS:
        raise ValueError(f"{donde}: departamento {f['departamento']!r} no es canónico "
                         f"(se espera {nombre_departamento(f['departamento'])!r})")
    lat, lon = _coord(f.get("lat")), _coord(f.get("lon"))
    if lat is None or lon is None or not _en_peru(lat, lon):
        raise ValueError(f"{donde}: ({f.get('lat')}, {f.get('lon')}) no cae en el Perú (¿lat y lon invertidas?)")
    if not str(f["fuente_url"]).startswith("https://"):
        raise ValueError(f"{donde}: fuente_url debe ser https ({f['fuente_url']!r})")
    if f.get("telefono") is not None and len(re.sub(r"\D", "", str(f["telefono"]))) < 6:
        raise ValueError(f"{donde}: teléfono sin dígitos ({f['telefono']!r})")
    if f.get("atiende_24h") not in (True, False, None):
        raise ValueError(f"{donde}: atiende_24h debe ser true, false o null")
    if f.get("ubigeo") is not None and not re.fullmatch(r"\d{6}", str(f["ubigeo"])):
        raise ValueError(f"{donde}: ubigeo {f['ubigeo']!r} no tiene 6 dígitos")
    detalle = f.get("detalle") or {}
    if not isinstance(detalle, dict):
        raise ValueError(f"{donde}: detalle debe ser un objeto")
    fila = {c: f.get(c) for c in CAMPOS_FILA}
    fila.update(lat=lat, lon=lon, actualizado=_fecha(f["actualizado"], donde),
                detalle=json.dumps({k: v for k, v in detalle.items() if v is not None}, ensure_ascii=False))
    return fila


def validar_numeros(datos: dict) -> list[dict]:
    """numeros.json: cada número con servicio, ámbito, fuente https y fecha de verificación."""
    numeros = datos.get("numeros")
    if not numeros:
        raise ValueError("numeros.json: sin números")
    for n in numeros:
        donde = f"numeros.json {n.get('servicio')!r}"
        falta = [c for c in CAMPOS_NUMERO if n.get(c) in (None, "")]
        if falta:
            raise ValueError(f"{donde}: faltan {falta}")
        if n["ambito"] not in ("nacional", "Cajamarca"):
            raise ValueError(f"{donde}: ambito debe ser 'nacional' o 'Cajamarca'")
        if not re.search(r"\d{3}", n["numero"]):
            raise ValueError(f"{donde}: número sin dígitos ({n['numero']!r})")
        if not n["fuente_url"].startswith("https://"):
            raise ValueError(f"{donde}: fuente_url debe ser https")
        _fecha(n["verificado"], donde)
    return numeros


# ----------------------------------------------------------------------------------------------
# Lectura de la carpeta de datos
# ----------------------------------------------------------------------------------------------

def _leer_json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def cargar(carpeta: Path = DATOS, pais: bool = False) -> tuple[list[dict], dict[str, Counter]]:
    """
    Lee y valida todos los archivos. (filas listas para SQL, descartes por fuente).
    Lanza ValueError con lo que esté mal. Con pais=True, salud sale del CSV completo en CACHE_PAIS.
    """
    faltan = [a for k, a in ARCHIVOS.items() if not (carpeta / a).is_file()]
    if faltan:
        raise ValueError(f"faltan archivos en {carpeta}: {', '.join(faltan)} (corre --descargar)")
    fuentes = _leer_json(carpeta / ARCHIVOS["fuentes"])
    for k in ("renipress", "comisarias", "bomberos_cenepred", "bomberos_cgbvp"):
        if not fuentes.get(k, {}).get("url") or not fuentes[k].get("actualizado"):
            raise ValueError(f"fuentes.json: la fuente {k!r} necesita url y actualizado")
    validar_numeros(_leer_json(carpeta / ARCHIVOS["numeros"]))

    if pais:
        ruta_csv = CACHE_PAIS / fuentes["renipress"].get("archivo", "")
        if not ruta_csv.is_file():
            raise ValueError(f"--pais necesita el CSV completo en {ruta_csv}: corre antes --descargar --pais")
    else:
        ruta_csv = carpeta / ARCHIVOS["renipress"]
    salud, d_salud = parsear_renipress(ruta_csv.read_text(encoding="utf-8-sig"), fuentes["renipress"])
    comisarias, d_com = parsear_comisarias(_leer_json(carpeta / ARCHIVOS["comisarias"]), fuentes["comisarias"])
    bomberos, d_bom = parsear_bomberos(_leer_json(carpeta / ARCHIVOS["bomberos_cenepred"]),
                                       _leer_json(carpeta / ARCHIVOS["bomberos_cgbvp"]),
                                       fuentes["bomberos_cenepred"], fuentes["bomberos_cgbvp"])
    manual = parsear_manual(_leer_json(carpeta / ARCHIVOS["manual"]))
    for nombre, lista in (("salud", salud), ("comisarías", comisarias), ("bomberos", bomberos), ("Defensa Civil", manual)):
        if not lista:
            raise ValueError(f"la fuente de {nombre} no dio ningún punto (¿archivo vacío o recortado?)")
    filas = [validar_fila(f) for f in salud + comisarias + bomberos + manual]
    claves = [f["clave"] for f in filas]
    repetidas = sorted({c for c, n in Counter(claves).items() if n > 1})
    if repetidas:
        raise ValueError(f"claves repetidas: {repetidas[:10]}")
    return filas, {"salud": d_salud, "comisarias": d_com, "bomberos": d_bom}


def conteo(filas: list[dict]) -> dict:
    """Totales por tipo, por departamento y de Cajamarca (región, provincia y ciudad)."""
    por_tipo = Counter(f["tipo"] for f in filas)
    por_depto: dict[str, Counter] = {}
    for f in filas:
        por_depto.setdefault(f["departamento"], Counter())[f["tipo"]] += 1
    caj = [f for f in filas if f["departamento"] == "Cajamarca"]
    prov = [f for f in caj if (f.get("provincia") or "") == "Cajamarca"]
    ciudad = [f for f in prov if (f.get("distrito") or "") in ("Cajamarca", "Los Baños del Inca", "Baños del Inca")]
    return {
        "total": len(filas),
        "por_tipo": dict(por_tipo),
        "salud_24h": sum(1 for f in filas if f["tipo"] == "salud" and f["atiende_24h"] is True),
        "por_departamento": {d: dict(c) for d, c in sorted(por_depto.items())},
        "cajamarca": {"region": len(caj), "provincia": len(prov), "ciudad": len(ciudad),
                      "salud_24h_region": sum(1 for f in caj if f["atiende_24h"] is True),
                      "salud_24h_provincia": sum(1 for f in prov if f["atiende_24h"] is True)},
    }


def resumen(filas: list[dict]) -> str:
    """'1380 puntos: salud 1256 (24 h: 44), comisaria 118, bomberos 4, otro 2 | Cajamarca: región 1380, provincia 300, ciudad 120'."""
    c = conteo(filas)
    partes = []
    for t in TIPOS:
        if c["por_tipo"].get(t):
            partes.append(f"{t} {c['por_tipo'][t]}" + (f" (24 h: {c['salud_24h']})" if t == "salud" else ""))
    k = c["cajamarca"]
    return (f"{c['total']} puntos: {', '.join(partes)} | Cajamarca: región {k['region']}, "
            f"provincia {k['provincia']}, ciudad {k['ciudad']}")


# ----------------------------------------------------------------------------------------------
# Escritura en la BD
# ----------------------------------------------------------------------------------------------

SQL_UPSERT = """
insert into punto_acudir (clave, tipo, nombre, categoria, atiende_24h, direccion, distrito, provincia, departamento,
                          ubigeo, telefono, lat, lon, fuente, fuente_url, fuente_id, licencia, atribucion, detalle,
                          actualizado)
values (%(clave)s, %(tipo)s, %(nombre)s, %(categoria)s, %(atiende_24h)s, %(direccion)s, %(distrito)s, %(provincia)s,
        %(departamento)s, %(ubigeo)s, %(telefono)s, %(lat)s, %(lon)s, %(fuente)s, %(fuente_url)s, %(fuente_id)s,
        %(licencia)s, %(atribucion)s, %(detalle)s::jsonb, %(actualizado)s)
on conflict (clave) do update set
  tipo = excluded.tipo, nombre = excluded.nombre, categoria = excluded.categoria, atiende_24h = excluded.atiende_24h,
  direccion = excluded.direccion, distrito = excluded.distrito, provincia = excluded.provincia,
  departamento = excluded.departamento, ubigeo = excluded.ubigeo, telefono = excluded.telefono, lat = excluded.lat,
  lon = excluded.lon, fuente = excluded.fuente, fuente_url = excluded.fuente_url, fuente_id = excluded.fuente_id,
  licencia = excluded.licencia, atribucion = excluded.atribucion, detalle = excluded.detalle,
  actualizado = excluded.actualizado, cargado_en = now()
"""
# Poda acotada: solo la fuente (prefijo de la clave) y los departamentos que vinieron en esta carga.
SQL_CONTAR_PODA = """
select count(*) from punto_acudir
 where clave like %(prefijo)s and departamento = any(%(deptos)s) and not (clave = any(%(claves)s))
"""
SQL_PODAR = """
delete from punto_acudir
 where clave like %(prefijo)s and departamento = any(%(deptos)s) and not (clave = any(%(claves)s))
"""
SQL_HAY_TABLA = "select to_regclass('public.punto_acudir') is not null"


def hay_tabla(conn) -> bool:
    """¿Ya se aplicó la migración punto_acudir?"""
    with conn.cursor() as cur:
        cur.execute(SQL_HAY_TABLA)
        return bool(cur.fetchone()[0])


def _ambitos(filas: list[dict]) -> list[dict]:
    """Por fuente (prefijo de clave): claves y departamentos de esta carga."""
    por_fuente: dict[str, dict] = {}
    for f in filas:
        a = por_fuente.setdefault(f["clave"].split(":", 1)[0], {"claves": [], "deptos": set()})
        a["claves"].append(f["clave"])
        a["deptos"].add(f["departamento"])
    return [{"prefijo": p + ":%", "claves": a["claves"], "deptos": sorted(a["deptos"])} for p, a in por_fuente.items()]


def aplicar(conn, filas: list[dict], podar: bool = False) -> tuple[int, int]:
    """
    Escribe en la transacción de conn (no hace commit). (filas escritas, filas podadas).
    Sin podar no borra nada: solo informa cuántas claves de las fuentes y departamentos cargados ya
    no vienen. Con podar las borra (y solo esas).
    """
    podadas = 0
    with conn.cursor() as cur:
        cur.executemany(SQL_UPSERT, filas)
        for a in _ambitos(filas):
            cur.execute(SQL_CONTAR_PODA, a)
            sobran = cur.fetchone()[0]
            if not sobran:
                continue
            if podar:
                cur.execute(SQL_PODAR, a)
                podadas += cur.rowcount
            else:
                log.warning("%d puntos de %r en %s ya no vienen en la fuente; se conservan (usa --podar para quitarlos).",
                            sobran, a["prefijo"], ", ".join(a["deptos"]))
    return len(filas), podadas


# ----------------------------------------------------------------------------------------------
# Descarga de las fuentes (red)
# ----------------------------------------------------------------------------------------------

def _bajar(url: str, cabeceras: dict | None = None, max_bytes: int = 80_000_000) -> tuple[bytes, dict]:
    """GET con User-Agent de navegador y reintentos -> (bytes, cabeceras de la respuesta)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA_NAVEGADOR, **(cabeceras or {})})

    def ir():
        with urllib.request.urlopen(req, timeout=120, context=_CTX) as r:
            datos = r.read(max_bytes + 1)
            if len(datos) > max_bytes:
                raise ValueError(f"{url}: la descarga supera {max_bytes} bytes")
            return datos, {k.lower(): v for k, v in r.headers.items()}
    return con_reintentos(ir)


def ultimo_csv_renipress(html: str) -> str:
    """Nombre del CSV más reciente que enlaza la ficha ('RENIPRESS_30-09-2026.csv')."""
    fechas = {}
    for m in re.finditer(r"RENIPRESS_(\d{2})-(\d{2})-(\d{4})\.csv", html):
        fechas[date(int(m.group(3)), int(m.group(2)), int(m.group(1)))] = m.group(0)
    if not fechas:
        raise ValueError("la ficha de RENIPRESS no enlaza ningún RENIPRESS_dd-mm-aaaa.csv (¿cambió la página?)")
    return fechas[max(fechas)]


def filtrar_csv(texto: str, departamento: str = "CAJAMARCA") -> str:
    """El mismo CSV (cabecera, ';') con solo las filas de un departamento."""
    lector = csv.reader(io.StringIO(texto.lstrip("\ufeff")), delimiter=";")
    cabecera = next(lector)
    i = cabecera.index("DEPARTAMENTO")
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";", lineterminator="\n")
    w.writerow(cabecera)
    for fila in lector:
        if len(fila) > i and fila[i].strip().upper() == departamento:
            w.writerow(fila)
    return salida.getvalue()


def _capa_cenepred(capa: int) -> dict:
    """Todos los puntos de una capa del MapServer en GeoJSON WGS84 (paginado de a 1000)."""
    features, offset = [], 0
    while True:
        url = (f"{CENEPRED}/{capa}/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"
               f"&resultOffset={offset}&resultRecordCount=1000")
        datos, _ = _bajar(url)
        pagina = json.loads(datos.decode("utf-8"))
        if "features" not in pagina:
            raise ValueError(f"CENEPRED capa {capa}: respuesta sin features ({str(pagina)[:120]})")
        features += pagina["features"]
        if not pagina.get("exceededTransferLimit") or not pagina["features"]:
            break
        offset += len(pagina["features"])
    return {"type": "FeatureCollection", "features": features}


def _cgbvp() -> dict:
    """Comandancias y compañías del portal del CGBVP (sin el nombre del jefe ni la foto)."""
    cab = {"Accept": "application/json", "Referer": CGBVP_PAGINA}
    campos = ("codidenest", "nombre", "direccion", "telefonos", "fecha_fundacion")
    datos, _ = _bajar(CGBVP_API + "Comandancia", cab)
    comandancias = [{c: x.get(c) for c in campos} for x in json.loads(datos.decode("utf-8"))]
    if not comandancias:
        raise ValueError("CGBVP: la API no devolvió comandancias")
    companias = {}
    for cm in comandancias:
        datos, _ = _bajar(f"{CGBVP_API}Compania/{cm['codidenest']}", cab)
        companias[cm["codidenest"]] = [{c: x.get(c) for c in campos} for x in json.loads(datos.decode("utf-8"))]
    return {"comandancias": comandancias, "companias": companias}


def _escribir_json(ruta: Path, datos) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def descargar(carpeta: Path = DATOS, pais: bool = False) -> list[str]:
    """
    Vuelve a bajar cada fuente y reescribe su archivo y su entrada en fuentes.json. Si una fuente
    falla, su archivo anterior se queda como está (y se devuelve en la lista de fallas).
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_fuentes = carpeta / ARCHIVOS["fuentes"]
    fuentes = _leer_json(ruta_fuentes) if ruta_fuentes.is_file() else {}
    hoy = datetime.now(timezone.utc).date().isoformat()
    fallas = []

    try:
        html, _ = _bajar(FICHA_RENIPRESS)
        archivo = ultimo_csv_renipress(html.decode("utf-8", "ignore"))
        datos, cab = _bajar(BASE_RENIPRESS + archivo)
        texto = datos.decode("utf-8-sig")
        try:
            actualizado = parsedate_to_datetime(cab["last-modified"]).date().isoformat()
        except (KeyError, TypeError, ValueError):
            m = re.match(r"RENIPRESS_(\d{2})-(\d{2})-(\d{4})", archivo)
            actualizado = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        subconjunto = filtrar_csv(texto)
        if subconjunto.count("\n") < 100:
            raise ValueError("el CSV de RENIPRESS trae menos de 100 filas de Cajamarca (¿archivo recortado?)")
        (carpeta / ARCHIVOS["renipress"]).write_text("\ufeff" + subconjunto, encoding="utf-8")
        if pais:
            CACHE_PAIS.mkdir(parents=True, exist_ok=True)
            (CACHE_PAIS / archivo).write_text(texto, encoding="utf-8")
        fuentes["renipress"] = {
            "url": BASE_RENIPRESS + archivo, "ficha": FICHA_RENIPRESS, "archivo": archivo,
            "actualizado": actualizado, "descargado": hoy, "licencia": "ODC-By",
            "filtro": "renipress_cajamarca.csv tiene solo DEPARTAMENTO = CAJAMARCA; el CSV completo va a la caché temporal con --pais",
        }
        log.info("RENIPRESS: %s (del %s), %d filas de Cajamarca", archivo, actualizado, subconjunto.count("\n") - 1)
    except Exception as e:   # noqa: BLE001  una fuente caída no borra el archivo anterior
        log.error("RENIPRESS no se pudo bajar: %s", e)
        fallas.append("renipress")

    try:
        geo = _capa_cenepred(CAPA_COMISARIAS)
        if len(geo["features"]) < 1000:
            raise ValueError(f"CENEPRED comisarías: solo {len(geo['features'])} puntos (se esperan ~1300)")
        _escribir_json(carpeta / ARCHIVOS["comisarias"], geo)
        fuentes["comisarias"] = {
            "url": f"{CENEPRED}/{CAPA_COMISARIAS}", "ficha": FICHA_COMISARIAS, "capa": "ComisariasBasicas",
            "actualizado": FECHA_PADRON_COMISARIAS, "descargado": hoy, "licencia": "ODC-By",
            "nota": "Padrón MININTER de comisarías básicas a noviembre de 2019 (datosabiertos.gob.pe), servido por CENEPRED como puntos WGS84; puede haber cambios.",
        }
        log.info("CENEPRED comisarías: %d puntos", len(geo["features"]))
    except Exception as e:   # noqa: BLE001
        log.error("CENEPRED comisarías no se pudo bajar: %s", e)
        fallas.append("comisarias")

    try:
        geo = _capa_cenepred(CAPA_BOMBEROS)
        if len(geo["features"]) < 150:
            raise ValueError(f"CENEPRED bomberos: solo {len(geo['features'])} puntos (se esperan ~210)")
        _escribir_json(carpeta / ARCHIVOS["bomberos_cenepred"], geo)
        fuentes["bomberos_cenepred"] = {
            "url": f"{CENEPRED}/{CAPA_BOMBEROS}", "capa": "Bomberos", "actualizado": hoy, "descargado": hoy,
            "licencia": None, "nota": "Puntos de las compañías de bomberos del servicio CENEPRED COEN_FEN_2027 (sin fecha en los metadatos).",
        }
        log.info("CENEPRED bomberos: %d puntos", len(geo["features"]))
    except Exception as e:   # noqa: BLE001
        log.error("CENEPRED bomberos no se pudo bajar: %s", e)
        fallas.append("bomberos_cenepred")

    try:
        datos = _cgbvp()
        n = sum(len(v) for v in datos["companias"].values())
        if n < 150:
            raise ValueError(f"CGBVP: solo {n} compañías (se esperan ~240)")
        _escribir_json(carpeta / ARCHIVOS["bomberos_cgbvp"], datos)
        fuentes["bomberos_cgbvp"] = {
            "url": CGBVP_PAGINA, "api": CGBVP_API, "actualizado": hoy, "descargado": hoy, "licencia": None,
            "nota": "Directorio vigente del portal del CGBVP (API interna del sitio); se guarda sin el nombre del jefe ni la foto.",
        }
        log.info("CGBVP: %d comandancias, %d compañías", len(datos["comandancias"]), n)
    except Exception as e:   # noqa: BLE001
        log.error("CGBVP no se pudo bajar: %s", e)
        fallas.append("bomberos_cgbvp")

    _escribir_json(ruta_fuentes, fuentes)
    return fallas


# ----------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Carga los puntos de 'A dónde acudir' (salud, comisarías, bomberos, "
                                             "Defensa Civil) a Supabase.")
    ap.add_argument("--datos", type=Path, default=DATOS, metavar="DIR", help="carpeta con los archivos")
    ap.add_argument("--descargar", action="store_true", help="vuelve a bajar las fuentes a la carpeta (red)")
    ap.add_argument("--pais", action="store_true", help="salud de todo el país (CSV completo en la caché temporal)")
    ap.add_argument("--aplicar", action="store_true", help="escribe en la BD (sin esto es prueba en seco)")
    ap.add_argument("--podar", action="store_true", help="con --aplicar, borra las claves que ya no vienen")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.descargar:
        fallas = descargar(args.datos, pais=args.pais)
        if fallas:
            log.error("No se pudieron bajar: %s. Se conservan los archivos anteriores.", ", ".join(fallas))
    try:
        filas, descartes = cargar(args.datos, pais=args.pais)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as e:
        log.error("Datos inválidos en %s: %s", args.datos, e)
        return 1
    for fuente, d in descartes.items():
        if d:
            log.info("Descartes de %s: %s", fuente, ", ".join(f"{k} {n}" for k, n in d.most_common()))
    c = conteo(filas)
    log.info("%s", resumen(filas))
    log.info("Por departamento: %s", "; ".join(f"{d} {sum(t.values())}" for d, t in c["por_departamento"].items()))
    if not args.aplicar:
        log.info("Prueba en seco: no se escribió nada. Usa --aplicar para guardar.")
        return 0

    try:
        with conectar() as conn:   # una sola transacción: commit al salir, rollback si algo falla
            if not hay_tabla(conn):
                log.error("Falta la tabla punto_acudir: aplica antes la migración punto_acudir (supabase/migrations/).")
                return 2
            escritas, podadas = aplicar(conn, filas, podar=args.podar)
    except RuntimeError as e:      # falta SUPABASE_DB_URL o psycopg
        log.error("%s Corre el cargador dentro del contenedor worker.", e)
        return 2
    log.info("Guardado: %d puntos (upsert por clave); %d podados.", escritas, podadas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
