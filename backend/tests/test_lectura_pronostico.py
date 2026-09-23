"""
Lectura del pronóstico de SENAMHI por localidad (backend/ingesta/lectura_pronostico.py): los
casos de la referencia verificada, los conteos reales de la emisión del 22-09-2026 y los
nombres legibles. Sin red: solo librería estándar.
"""
import gzip
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

from backend.connectors import senamhi_pronostico as sp
from backend.ingesta.lectura_pronostico import clasificar, intensidad, nombre_legible, plano

MUESTRAS = Path(__file__).parent / "muestras"
# Página completa del país, tal como llegó (22-09-2026 23:26, hora de Perú).
PAIS = MUESTRAS / "pronostico_pais_20260922_completa.html.gz"

# (ícono, texto) -> (tipo, posible, por, lluvia_segura, granizo, intensidad, momento, cielo).
# Los 13 casos de la referencia, con el resultado que imprimió.
CASOS = [
    ("009", "Cielo nublado parcial variando a cielo nublado y cielo cubierto durante el día con lluvia.",
     ("lluvia", False, "texto+icono", False, False, None, None, None)),
    ("003", "Cielo nublado parcial con tendencia a cielo nublado y lluvia ligera al atardecer.",
     ("lluvia", True, "texto", False, False, "ligera", "al atardecer", None)),
    ("", "Cielo nublado con tendencia a cielo nublado parcial por la tarde ; lluvia.",
     ("lluvia", False, "texto", False, False, None, None, None)),
    ("", "Cielo cubierto con lluvia con tendencia a tormenta",
     ("tormenta", True, "texto", True, False, None, None, None)),
    ("011", "Cielo nublado variando a cielo cubierto con lluvia.",
     ("tormenta", True, "icono", True, False, None, None, None)),
    ("008", "Cielo nublado parcial variando a cielo nublado durante el día.",
     ("lluvia", True, "icono", False, False, None, None, None)),
    ("029", "Cielo nublado parcial con viento moderado.",
     ("sin_lluvia", False, "texto", False, False, None, None, "parcial")),
    ("", "Al atardecer viento fuerte con lluvia ligera en la noche.",
     ("lluvia", False, "texto", False, False, "ligera", "en la noche", None)),
    ("017", "Cielo nublado con tendencia a heladas por la noche y granizo pequeño",
     ("nieve", True, "texto+icono", False, True, None, "en la noche", None)),
    ("", "Cielo cubierto con lluvia y nieve.",
     ("nieve", False, "texto", False, False, None, None, None)),
    ("", "Cielo cubierto con tormenta y chubasco en las primeras horas de la mañana.",
     ("tormenta", False, "texto", True, False, None, "temprano en la mañana", None)),
    ("", "Cielo despejado sin lluvias.",
     ("sin_lluvia", False, "texto", False, False, None, None, "despejado")),
    ("021", "Cielo despejado durante el día.",
     ("sin_lluvia", False, "texto", False, False, None, None, "despejado")),
]
CAMPOS = ("tipo", "posible", "por", "lluvia_segura", "granizo", "intensidad", "momento", "cielo")


def _categoria(r: dict) -> str:
    return r["tipo"] + ("_posible" if r["posible"] else "")


class TestClasificar(unittest.TestCase):
    def test_casos_de_la_referencia(self):
        for icono, texto, esperado in CASOS:
            r = clasificar(icono, texto)
            self.assertEqual(tuple(r[c] for c in CAMPOS), esperado, (icono, texto))
            self.assertEqual(set(r), set(CAMPOS))

    def test_durante_el_dia_no_es_momento(self):
        # Cajamarca, 23-09: "Lluvia", no "Lluvia durante el día"
        r = clasificar("009", "Cielo nublado parcial variando a cielo nublado y cielo cubierto durante el día con lluvia.")
        self.assertIsNone(r["momento"])

    def test_texto_con_entidades_y_vacio(self):
        self.assertEqual(clasificar("008", "Cielo nublado por la ma&ntilde;ana con lluvia")["momento"], "en la mañana")
        self.assertEqual(clasificar(None, None)["tipo"], "sin_lluvia")
        self.assertEqual(clasificar("004", "")["cielo"], "nublado")

    def test_intensidad_por_el_adjetivo_pegado(self):
        self.assertEqual(intensidad(plano("con lluvia de moderada a fuerte y lluvias fuertes")), "fuerte")
        self.assertEqual(intensidad(plano("con chubascos moderados")), "moderada")
        self.assertEqual(intensidad(plano("con viento moderado y lluvia")), None)
        self.assertEqual(intensidad(plano("con lloviznas")), "ligera")


class TestConteosReales(unittest.TestCase):
    """Emisión del martes 22-09-2026: lo que la especificación y la revisión contaron a mano."""

    @classmethod
    def setUpClass(cls):
        pagina = sp.decodificar(gzip.decompress(PAIS.read_bytes()))
        cls.pron = sp.parse_pagina(pagina, date(2026, 9, 23))

    def _conteo(self, dia: date, dp: str | None = None) -> dict:
        return dict(Counter(_categoria(clasificar(d.icono, d.texto))
                            for loc in self.pron.localidades if dp is None or loc.dp == dp
                            for d in loc.dias if d.fecha == dia))

    def test_cajamarca(self):
        self.assertEqual(self._conteo(date(2026, 9, 23), "06"), {"lluvia": 7, "lluvia_posible": 6, "sin_lluvia": 4})
        self.assertEqual(self._conteo(date(2026, 9, 24), "06"), {"lluvia": 6, "lluvia_posible": 8, "sin_lluvia": 3})
        self.assertEqual(self._conteo(date(2026, 9, 25), "06"), {"lluvia": 6, "lluvia_posible": 1, "sin_lluvia": 10})

    def test_pais(self):
        self.assertEqual(self._conteo(date(2026, 9, 23)),
                         {"lluvia": 57, "lluvia_posible": 42, "tormenta_posible": 4, "sin_lluvia": 174})

    def test_moyobamba_icono_de_tormenta_con_texto_de_lluvia(self):
        [moyo] = [loc for loc in self.pron.localidades if loc.codigo == "22-0059"]
        d = moyo.dias[0]
        self.assertEqual((d.fecha, d.icono), (date(2026, 9, 23), "011"))
        r = clasificar(d.icono, d.texto)
        self.assertEqual((r["tipo"], r["posible"], r["por"], r["lluvia_segura"]), ("tormenta", True, "icono", True))


class TestNombreLegible(unittest.TestCase):
    def test_nombres(self):
        casos = {
            "SAN MIGUEL DE PALLAQUES - CAJAMARCA": "San Miguel de Pallaques",
            "LIMA OESTE / CALLAO - LIMA": "Lima Oeste / Callao",
            "CHANCAY BAÑOS - CAJAMARCA": "Chancay Baños",
            "CONTUMAZÁ - CAJAMARCA": "Contumazá",
            "CAJAMARCA - CAJAMARCA": "Cajamarca",
            "STA. ROSA DE OCOPA - JUNIN": "Sta. Rosa de Ocopa",
            "YAURI-ESPINAR - CUSCO": "Yauri-Espinar",
            "LA UNION - HUANUCO": "La Union",          # la primera palabra siempre con mayúscula
            "PUERTO MALDONADO - MADRE DE DIOS": "Puerto Maldonado",
            "SAN VICENTE DE CA&Ntilde;ETE - LIMA": "San Vicente de Cañete",
        }
        for senamhi, legible in casos.items():
            self.assertEqual(nombre_legible(senamhi), legible, senamhi)


if __name__ == "__main__":
    unittest.main()
