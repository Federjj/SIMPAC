"""
Capa de persistencia (prototipo) — SQLite, sin dependencias.

Refleja el esquema que en producción irá en PostgreSQL + PostGIS. Aquí guardamos
lat/lon como columnas y hacemos los cálculos geográficos en Python; migrar a
PostGIS es reemplazar este módulo (las firmas de las funciones no cambian).

Acumular histórico propio es el objetivo: las fuentes solo exponen ventanas
cortas en tiempo real, así que cada corrida del job guarda una foto.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "simpac.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS estacion (
  cod TEXT PRIMARY KEY,
  nombre TEXT, tipo TEXT, categoria TEXT, estado TEXT,
  lat REAL, lon REAL, departamento TEXT, fuente TEXT
);
CREATE TABLE IF NOT EXISTS lectura_lluvia (
  cod TEXT, estacion TEXT, ts TEXT,          -- ts = "YYYY/MM/DD - HH"
  precip_mm REAL, temp_c REAL, ts_captura TEXT,
  PRIMARY KEY (cod, ts)
);
CREATE TABLE IF NOT EXISTS lectura_caudal (
  estacion TEXT, rio TEXT, departamento TEXT, provincia TEXT,
  fecha TEXT, hora TEXT,                      -- fecha = YYYY-MM-DD
  valor REAL, unidad TEXT, ualerta REAL, uemergencia REAL,
  tendencia TEXT, estado TEXT, lat REAL, lon REAL, ts_captura TEXT,
  PRIMARY KEY (estacion, fecha, hora)
);
CREATE TABLE IF NOT EXISTS indice (
  fuente TEXT PRIMARY KEY,                    -- 'ONI' | 'ICEN'
  periodo TEXT, valor REAL, categoria TEXT, ts_captura TEXT
);
CREATE TABLE IF NOT EXISTS alerta (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tipo TEXT, referencia TEXT, zona TEXT,
  nivel TEXT, detalle TEXT, valor REAL, umbral REAL, ts TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# ---------- escritura ----------

def upsert_estacion(conn, e) -> None:
    conn.execute(
        """INSERT INTO estacion (cod,nombre,tipo,categoria,estado,lat,lon,departamento,fuente)
           VALUES (?,?,?,?,?,?,?,?, 'SENAMHI')
           ON CONFLICT(cod) DO UPDATE SET nombre=excluded.nombre, estado=excluded.estado,
             lat=excluded.lat, lon=excluded.lon, categoria=excluded.categoria""",
        (e.cod, e.nombre, e.tipo, e.categoria, e.estado, e.lat, e.lon, "Cajamarca"),
    )


def insert_lluvia(conn, cod, estacion, ts, precip, temp) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO lectura_lluvia (cod,estacion,ts,precip_mm,temp_c,ts_captura)
           VALUES (?,?,?,?,?,?)""",
        (cod, estacion, ts, precip, temp, _now()),
    )


def insert_caudal(conn, c, fecha: str) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO lectura_caudal
           (estacion,rio,departamento,provincia,fecha,hora,valor,unidad,ualerta,uemergencia,
            tendencia,estado,lat,lon,ts_captura)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (c.estacion, c.rio, c.departamento, c.provincia, fecha, c.hora, c.valor, c.unidad,
         c.umbral_alerta, c.umbral_emergencia, c.tendencia, c.estado, c.lat, c.lon, _now()),
    )


def set_indice(conn, fuente, periodo, valor, categoria) -> None:
    conn.execute(
        """INSERT INTO indice (fuente,periodo,valor,categoria,ts_captura) VALUES (?,?,?,?,?)
           ON CONFLICT(fuente) DO UPDATE SET periodo=excluded.periodo, valor=excluded.valor,
             categoria=excluded.categoria, ts_captura=excluded.ts_captura""",
        (fuente, periodo, valor, categoria, _now()),
    )


def replace_alertas(conn, alertas: list[dict]) -> None:
    conn.execute("DELETE FROM alerta")
    for a in alertas:
        conn.execute(
            """INSERT INTO alerta (tipo,referencia,zona,nivel,detalle,valor,umbral,ts)
               VALUES (?,?,?,?,?,?,?,?)""",
            (a["tipo"], a["referencia"], a.get("zona", "Cajamarca"), a["nivel"],
             a.get("detalle", ""), a.get("valor"), a.get("umbral"), _now()),
        )


# ---------- lectura ----------

def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def estaciones(conn) -> list[dict]:
    return _rows(conn.execute("SELECT * FROM estacion ORDER BY nombre"))


def caudales_ultimos(conn) -> list[dict]:
    return _rows(conn.execute(
        """SELECT l.* FROM lectura_caudal l
           WHERE (l.fecha||l.hora) = (
             SELECT MAX(l2.fecha||l2.hora) FROM lectura_caudal l2 WHERE l2.estacion=l.estacion)
           ORDER BY l.estacion"""))


def lluvia_serie(conn, cod: str, limite: int = 48) -> list[dict]:
    return _rows(conn.execute(
        "SELECT ts,precip_mm,temp_c FROM lectura_lluvia WHERE cod=? ORDER BY ts DESC LIMIT ?",
        (cod, limite)))[::-1]


def indices(conn) -> list[dict]:
    return _rows(conn.execute("SELECT * FROM indice"))


def alertas(conn) -> list[dict]:
    return _rows(conn.execute("SELECT * FROM alerta ORDER BY nivel DESC, referencia"))
