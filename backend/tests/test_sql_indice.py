"""
Reglas de escritura de la tabla indice (backend/ingesta/guardar.py), probadas de verdad
sobre sqlite3, que entiende el mismo INSERT ... ON CONFLICT DO UPDATE ... WHERE excluded.x.

  SQL_ICEN:     solo gana un mes más nuevo; en el mismo mes, solo refresca el mismo origen.
  SQL_ICEN_TMP: refresca el mismo mes o avanza, nunca retrocede.
  SQL_INDICE:   reemplaza siempre (RONI).

Sin Postgres ni red: solo librería estándar.
"""
import itertools
import sqlite3
import unittest

from backend.ingesta.guardar import SQL_ICEN, SQL_ICEN_TMP, SQL_INDICE

# Misma forma que supabase/schema.sql (tipos de sqlite).
TABLA = """
create table indice (
  fuente     text primary key,
  periodo    text,
  valor      double precision,
  categoria  text,
  origen     text,
  ts_captura text
)
"""


class _Base(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        reloj = itertools.count(1)   # now() distinto en cada llamada: se ve si la fila se tocó
        self.conn.create_function("now", 0, lambda: f"t{next(reloj)}")
        self.conn.execute(TABLA)

    def escribir(self, sql, fuente, periodo, valor, categoria, origen):
        self.assertEqual(sql.count("%s"), 5)
        self.conn.execute(sql.replace("%s", "?"), (fuente, periodo, valor, categoria, origen))

    def fila(self, fuente):
        return self.conn.execute(
            "select periodo, valor, categoria, origen, ts_captura from indice where fuente = ?", (fuente,)
        ).fetchone()


class TestSQLICEN(_Base):
    def icen(self, periodo, valor, origen, categoria="Cálida fuerte"):
        self.escribir(SQL_ICEN, "ICEN", periodo, valor, categoria, origen)

    def test_tabla_vacia_inserta(self):
        self.icen("2026-05", 1.98, "IGP", "Cálida moderada")
        self.assertEqual(self.fila("ICEN")[:4], ("2026-05", 1.98, "Cálida moderada", "IGP"))

    def test_mes_mas_nuevo_reemplaza_aunque_sea_de_otro_origen(self):
        self.icen("2026-05", 1.98, "IGP")
        self.icen("2026-07", 3.38, "ENFEN")
        self.assertEqual(self.fila("ICEN")[:4], ("2026-07", 3.38, "Cálida fuerte", "ENFEN"))
        self.icen("2026-08", 3.70, "IGP")
        self.assertEqual(self.fila("ICEN")[:4], ("2026-08", 3.70, "Cálida fuerte", "IGP"))

    def test_mes_mas_viejo_no_reemplaza_ni_del_mismo_origen(self):
        self.icen("2026-07", 3.38, "ENFEN")
        antes = self.fila("ICEN")
        self.icen("2026-05", 1.98, "IGP")      # el IGP va meses atrasado
        self.icen("2026-06", 2.66, "ENFEN")    # un informe más viejo
        self.assertEqual(self.fila("ICEN"), antes)   # ni el ts_captura cambia

    def test_mismo_mes_y_mismo_origen_refresca(self):
        self.icen("2026-07", 3.38, "ENFEN")
        ts = self.fila("ICEN")[4]
        self.icen("2026-07", 3.41, "ENFEN")    # corrección del mismo mes
        periodo, valor, _, origen, ts_nuevo = self.fila("ICEN")
        self.assertEqual((periodo, valor, origen), ("2026-07", 3.41, "ENFEN"))
        self.assertNotEqual(ts_nuevo, ts)

    def test_mismo_mes_y_otro_origen_no_pisa(self):
        self.icen("2026-07", 3.38, "ENFEN")
        antes = self.fila("ICEN")
        self.icen("2026-07", 3.35, "IGP")
        self.assertEqual(self.fila("ICEN"), antes)

    def test_no_toca_las_demas_fuentes(self):
        self.escribir(SQL_INDICE, "RONI", "JJA 2026", 1.36, "El Niño moderado", "NOAA")
        self.icen("2026-07", 3.38, "ENFEN")
        self.assertEqual(self.fila("RONI")[:4], ("JJA 2026", 1.36, "El Niño moderado", "NOAA"))


class TestSQLICENTMP(_Base):
    def tmp(self, periodo, valor):
        self.escribir(SQL_ICEN_TMP, "ICEN_TMP", periodo, valor, "Cálida extraordinaria", "ENFEN")

    def test_no_retrocede_de_mes(self):
        self.tmp("2026-08", 3.73)
        antes = self.fila("ICEN_TMP")
        self.tmp("2026-07", 3.10)   # p. ej. un informe más viejo de una fuente atrasada
        self.assertEqual(self.fila("ICEN_TMP"), antes)

    def test_avanza_y_refresca_el_mismo_mes(self):
        self.tmp("2026-08", 3.73)
        self.tmp("2026-09", 3.90)
        self.assertEqual(self.fila("ICEN_TMP")[:2], ("2026-09", 3.90))
        ts = self.fila("ICEN_TMP")[4]
        self.tmp("2026-09", 3.95)
        self.assertEqual(self.fila("ICEN_TMP")[:2], ("2026-09", 3.95))
        self.assertNotEqual(self.fila("ICEN_TMP")[4], ts)

    def test_cambio_de_anio(self):
        # "AAAA-MM" ordena como texto: diciembre < enero del año siguiente
        self.tmp("2026-12", 1.0)
        self.tmp("2027-01", 0.8)
        self.assertEqual(self.fila("ICEN_TMP")[0], "2027-01")
        self.tmp("2026-12", 1.2)
        self.assertEqual(self.fila("ICEN_TMP")[0], "2027-01")


class TestSQLINDICE(_Base):
    def test_reemplaza_siempre(self):
        self.escribir(SQL_INDICE, "RONI", "JJA 2026", 1.36, "El Niño moderado", "NOAA")
        self.escribir(SQL_INDICE, "RONI", "JAS 2026", 1.50, "El Niño moderado", "NOAA")
        self.assertEqual(self.fila("RONI")[:2], ("JAS 2026", 1.50))


if __name__ == "__main__":
    unittest.main()
