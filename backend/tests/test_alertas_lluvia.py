"""
Alertas de lluvia con la referencia de SENAMHI por estación (backend/alerts.py): cuándo pasa,
qué ventana manda, nivel siempre 'aviso' y los textos exactos que ve la gente. También la
restricción alerta_lluvia_referencia_check de la BD, probada de verdad sobre sqlite3.
"""
import re
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend import alerts

SUPABASE = Path(__file__).resolve().parents[2] / "supabase"   # no está en la imagen del worker

# 18:00 de Lima (las estaciones de la capa marcan la hora de Perú)
MEDIDO = datetime(2026, 9, 22, 23, tzinfo=timezone.utc)
CLAVE = "CHOTA GORE@-6.55405,-78.67588"
PROHIBIDAS = ("fuerte", "intensa", "alerta", "emergencia", "peligro", "extrema")


def _evaluar(pp_1h, umbral_1h, pp_6h=0.0, umbral_6h="3x", nombre="CHOTA GORE", provincia="CHOTA",
             zona="Cajamarca", clave=CLAVE, medido_en=MEDIDO):
    """Por defecto umbral_6h = 3 x umbral_1h, como en las 216 estaciones de la capa."""
    if umbral_6h == "3x":
        umbral_6h = None if umbral_1h is None else umbral_1h * 3
    return alerts.evaluar_lluvia_referencia(clave, nombre, provincia, zona, pp_1h, umbral_1h,
                                            pp_6h, umbral_6h, medido_en)


class TestReglaLluvia(unittest.TestCase):
    def test_mayor_estricto(self):
        self.assertIsNone(_evaluar(5.0, 5))
        a = _evaluar(5.1, 5)
        self.assertEqual((a["ventana_h"], a["valor"], a["umbral"]), (1, 5.1, 5))
        self.assertFalse(alerts.pasa(15, 15))
        self.assertTrue(alerts.pasa(15.1, 15))

    def test_no_evaluable(self):
        for pp_1h, umbral_1h in ((12.0, None), (12.0, 0), (12.0, -1), (None, 5)):
            self.assertFalse(alerts.lluvia_evaluable(pp_1h, umbral_1h), (pp_1h, umbral_1h))
            # ni siquiera con las 6 h muy por encima: sin la hora no se evalúa
            self.assertIsNone(_evaluar(pp_1h, umbral_1h, pp_6h=99.0, umbral_6h=15), (pp_1h, umbral_1h))
        self.assertTrue(alerts.lluvia_evaluable(0.0, 5))

    def test_solo_6h(self):
        a = _evaluar(4, 5, pp_6h=16, umbral_6h=15)
        self.assertEqual((a["ventana_h"], a["valor"], a["umbral"]), (6, 16, 15))

    def test_6h_sin_dato(self):
        self.assertIsNone(_evaluar(4, 5, pp_6h=None, umbral_6h=15))
        self.assertIsNone(_evaluar(4, 5, pp_6h=16, umbral_6h=None))
        # referencia de 6 h en 0 o negativa: no pasa con cualquier lluvia (la de 1 h sí es evaluable)
        for umbral_6h in (0, -1):
            self.assertIsNone(_evaluar(0.0, 5, pp_6h=0.1, umbral_6h=umbral_6h), umbral_6h)
        self.assertFalse(alerts.pasa(0.1, 0))
        self.assertFalse(alerts.pasa(0.1, -1))
        a = _evaluar(6, 5, pp_6h=None)
        self.assertEqual((a["ventana_h"], a["valor"]), (1, 6))
        self.assertNotIn("6 horas", a["detalle"])

    def test_pasan_las_dos_una_sola(self):
        a = _evaluar(12.4, 10, pp_6h=31, umbral_6h=30)
        self.assertEqual((a["ventana_h"], a["valor"], a["umbral"]), (1, 12.4, 10))
        self.assertIn("12.4 mm", a["detalle"])
        self.assertIn("31 mm", a["detalle"])

    def test_nivel_siempre_aviso(self):
        for pp_1h, pp_6h in ((50.0, 0.0), (0.0, 150.0), (50.0, 150.0)):
            a = _evaluar(pp_1h, 5, pp_6h=pp_6h, umbral_6h=15)
            self.assertEqual((a["tipo"], a["nivel"]), ("lluvia", "aviso"))
        self.assertEqual(alerts.NIVEL_LLUVIA, "aviso")

    def test_referencia_zona_ts(self):
        a = _evaluar(12.4, 10)
        self.assertEqual((a["referencia"], a["zona"], a["ts"]), (CLAVE, "Cajamarca", MEDIDO))
        a = _evaluar(12.4, 10, zona=None)
        self.assertIsNone(a["zona"])
        self.assertEqual(set(a), {"tipo", "referencia", "zona", "nivel", "detalle", "valor", "umbral",
                                  "ventana_h", "ts"})


class TestTextosLluvia(unittest.TestCase):
    def test_textos_exactos(self):
        self.assertEqual(
            _evaluar(12.4, 10)["detalle"],
            "En Chota GORE (provincia de Chota) llovió 12.4 mm en la hora que terminó a las 18:00. "
            "SENAMHI usa 10 mm en una hora como referencia para esta estación. "
            "Es lo que midió la estación, no un aviso oficial.")
        self.assertEqual(
            _evaluar(0.0, 5.0, pp_6h=29.1, umbral_6h=15.0, nombre="COTAHUASI", provincia="LA UNION",
                     zona="Arequipa", clave="COTAHUASI@-15.21134,-72.89331")["detalle"],
            "En Cotahuasi (provincia de La Union) llovió 29.1 mm en las 6 horas que terminaron a las 18:00. "
            "SENAMHI usa 15 mm en 6 horas como referencia para esta estación. "
            "Es lo que midió la estación, no un aviso oficial.")
        self.assertEqual(
            _evaluar(12.4, 10, pp_6h=31.0, umbral_6h=30)["detalle"],
            "En Chota GORE (provincia de Chota) llovió 12.4 mm en la hora que terminó a las 18:00 y 31 mm "
            "en las 6 horas que terminaron a esa hora. SENAMHI usa 10 mm en una hora y 30 mm en 6 horas "
            "como referencia para esta estación. Es lo que midió la estación, no un aviso oficial.")
        # sin provincia no se inventa el paréntesis
        for provincia in (None, ""):
            self.assertEqual(
                _evaluar(12.4, 10, provincia=provincia)["detalle"],
                "En Chota GORE llovió 12.4 mm en la hora que terminó a las 18:00. "
                "SENAMHI usa 10 mm en una hora como referencia para esta estación. "
                "Es lo que midió la estación, no un aviso oficial.")

    def test_hora_de_peru(self):
        a = _evaluar(12.4, 10, medido_en=datetime(2026, 9, 22, 23, 0, tzinfo=timezone.utc))
        self.assertIn("a las 18:00.", a["detalle"])
        # pasada la medianoche UTC sigue siendo el día anterior en Lima
        a = _evaluar(12.4, 10, medido_en=datetime(2026, 9, 23, 4, 0, tzinfo=timezone.utc))
        self.assertIn("a las 23:00.", a["detalle"])

    def test_mm(self):
        self.assertEqual(alerts._mm(12.4), "12.4")
        self.assertEqual(alerts._mm(8.0), "8")
        self.assertEqual(alerts._mm(10), "10")
        self.assertEqual(alerts._mm(29.149999), "29.1")
        self.assertEqual(alerts._mm(0.05), "0.1")

    def test_detalle_sin_palabras_alarmantes(self):
        casos = [_evaluar(12.4, 10), _evaluar(4, 5, pp_6h=16, umbral_6h=15),
                 _evaluar(12.4, 10, pp_6h=31, umbral_6h=30), _evaluar(250.0, 25, provincia=None)]
        for a in casos:
            detalle = a["detalle"]
            self.assertIn("no un aviso oficial", detalle)
            for palabra in PROHIBIDAS:
                self.assertIsNone(re.search(palabra, detalle, re.I), (palabra, detalle))

    def test_nombre_legible(self):
        casos = {"BAMBAMARCA M": "Bambamarca", "CHOTA GORE": "Chota GORE",
                 "BAMBAMARCA H GORE": "Bambamarca H GORE", "UNC CAJAMARCA": "UNC Cajamarca",
                 "AYMAÑA": "Aymaña", "CHANCAY BAÑOS": "Chancay Baños", "SENAMHI-PUNO": "SENAMHI-Puno",
                 "PUENTE (CHILETE)": "Puente (Chilete)"}
        for entrada, esperado in casos.items():
            self.assertEqual(alerts.nombre_legible(entrada), esperado, entrada)

    def test_provincia_legible(self):
        casos = {"LA UNION": "La Union", "RODRIGUEZ DE MENDOZA": "Rodriguez de Mendoza",
                 "CHOTA": "Chota", "SAN IGNACIO": "San Ignacio", "  DEL  CARMEN ": "Del Carmen",
                 "MARISCAL RAMON CASTILLA Y LOS ANDES": "Mariscal Ramon Castilla y los Andes"}
        for entrada, esperado in casos.items():
            self.assertEqual(alerts.provincia_legible(entrada), esperado, entrada)


class TestOficialYRetirados(unittest.TestCase):
    def test_es_oficial(self):
        for tipo in ("aviso", "caudal", "nivel_bajo"):
            self.assertTrue(alerts.es_oficial(tipo), tipo)
        for tipo in ("lluvia", "otro", None):
            self.assertFalse(alerts.es_oficial(tipo), tipo)

    def test_criterios_retirados(self):
        # los umbrales provisionales de SIMPAC (20 y 40 mm en 24 h, 15 mm en 1 h) ya no existen
        for nombre in ("LLUVIA_24H_ALERTA", "LLUVIA_24H_EMERGENCIA", "LLUVIA_1H_ALERTA", "evaluar_lluvia",
                       "referencia_lluvia"):
            self.assertFalse(hasattr(alerts, nombre), nombre)


@unittest.skipUnless(SUPABASE.is_dir(), "sin la carpeta supabase/")
class TestRestriccionEnLaBD(unittest.TestCase):
    """El CHECK de la migración y de schema.sql, evaluado por sqlite3 (misma lógica de 3 valores)."""

    def _check(self, archivo):
        m = re.search(r"alerta_lluvia_referencia_check\s+check\s*(\(.*\))", archivo.read_text(encoding="utf-8"))
        self.assertIsNotNone(m, archivo.name)
        return m.group(1)

    def test_nivel_siempre_aviso_tambien_con_nulos(self):
        [migracion] = (SUPABASE / "migrations").glob("*alerta_lluvia_referencia_senamhi.sql")
        check = self._check(migracion)
        self.assertEqual(self._check(SUPABASE / "schema.sql"), check)
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute(f"create table alerta (tipo text, nivel text, ventana_h integer, check {check})")
        aceptadas = [("lluvia", "aviso", 1), ("lluvia", "aviso", 6), ("caudal", "alerta", None),
                     ("aviso", "emergencia", None), ("lluvia", "aviso", None), (None, None, None)]
        # con tipo o nivel NULL la comparación da NULL, y un CHECK con NULL deja pasar la fila
        rechazadas = [("lluvia", None, 1), (None, "aviso", 6), ("lluvia", "alerta", 1), ("lluvia", "aviso", 3),
                      ("aviso", "aviso", 1)]
        for fila in aceptadas:
            conn.execute("insert into alerta values (?, ?, ?)", fila)
        for fila in rechazadas:
            with self.assertRaises(sqlite3.IntegrityError, msg=fila):
                conn.execute("insert into alerta values (?, ?, ?)", fila)


if __name__ == "__main__":
    unittest.main()
