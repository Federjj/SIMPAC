"""Índices El Niño (ICEN con los cortes ENFEN 01-2024, RONI de NOAA) y ríos con umbral de nivel bajo."""
import unittest
from unittest import mock

from backend import alerts
from backend.connectors import ana, igp, noaa


class TestICEN(unittest.TestCase):
    def test_categorias_enfen_2024(self):
        # valores y categorías del Informe Técnico ENFEN N° 16-2026 (set-25 a jul-26 y el estimado de agosto)
        casos = {-0.42: "Neutra", 0.42: "Neutra", 0.96: "Cálida débil", 1.34: "Cálida moderada",
                 1.98: "Cálida moderada", 2.66: "Cálida fuerte", 3.38: "Cálida fuerte",
                 3.73: "Cálida extraordinaria", -0.9: "Fría"}
        for valor, esperado in casos.items():
            self.assertEqual(igp.categoria(valor), esperado, valor)

    def test_bordes(self):
        self.assertEqual(igp.categoria(0.5), "Neutra")
        self.assertEqual(igp.categoria(1.3), "Cálida débil")
        self.assertEqual(igp.categoria(2.1), "Cálida moderada")
        self.assertEqual(igp.categoria(3.5), "Cálida fuerte")
        self.assertEqual(igp.categoria(-0.7), "Neutra")


class TestRONI(unittest.TestCase):
    def test_magnitudes_cpc(self):
        casos = {1.36: "El Niño moderado", 0.5: "El Niño débil", 1.5: "El Niño fuerte",
                 2.0: "El Niño muy fuerte", 0.49: "Neutro", -0.49: "Neutro",
                 -1.2: "La Niña moderada", -0.6: "La Niña débil", -2.3: "La Niña muy fuerte"}
        for valor, esperado in casos.items():
            self.assertEqual(noaa.fase(valor), esperado, valor)

    def test_parser_de_tres_columnas(self):
        texto = "SEAS  YR   ANOM\n MJJ 2026   1.05\n JJA 2026   1.36\n basura\n"
        with mock.patch.object(noaa._http, "get", lambda url, params=None: texto):
            p = noaa.ultimo()
        self.assertEqual((p.temporada, p.anio, p.anom, p.fase), ("JJA", 2026, 1.36, "El Niño moderado"))


def _rio(valor, alerta, emergencia, unidad="m.s.n.m", tendencia="Ascendente"):
    return ana.EstacionCaudal(estacion="Enapu Perú", rio="Itaya", departamento="Loreto", provincia="P",
                              distrito="D", operador="O", valor=valor, unidad=unidad,
                              umbral_alerta=alerta, umbral_emergencia=emergencia,
                              tendencia=tendencia, hora="06:00", lat=-3.7, lon=-73.2)


class TestNivelBajo(unittest.TestCase):
    def test_umbral_invertido_es_de_vaciante(self):
        # 22-09-2026: Enapu Perú 109.89 con alerta 108.78 y emergencia 107.97 -> NO es emergencia
        self.assertTrue(_rio(109.89, 108.78, 107.97).umbral_bajo)
        self.assertEqual(_rio(109.89, 108.78, 107.97).estado, "normal")
        self.assertEqual(_rio(108.5, 108.78, 107.97).estado, "alerta")
        self.assertEqual(_rio(107.9, 108.78, 107.97).estado, "emergencia")

    def test_umbral_de_crecida_sigue_igual(self):
        c = _rio(0.09, 14.0, 18.0, unidad="m³/s")
        self.assertFalse(c.umbral_bajo)
        self.assertEqual(c.estado, "normal")
        self.assertEqual(_rio(15.0, 14.0, 18.0, unidad="m³/s").estado, "alerta")
        self.assertEqual(_rio(18.0, 14.0, 18.0, unidad="m³/s").estado, "emergencia")

    def test_lluvia_de_una_hora_es_fuerte_solo_sobre_15(self):
        from backend.connectors import senamhi
        def serie(ultima):
            return senamhi.SerieHoraria(estacion="E", codigo="X", timestamps=[f"2026/09/22 - {h:02d}" for h in range(24)],
                                        precip_mm=[0.0] * 23 + [ultima], temp_c=[])
        self.assertIsNone(alerts.evaluar_lluvia("X", "E", serie(15.0)))   # 15 mm/h es moderada
        self.assertEqual(alerts.evaluar_lluvia("X", "E", serie(15.5))["umbral"], alerts.LLUVIA_1H_ALERTA)

    def test_alerta_de_vaciante_tiene_su_tipo(self):
        [a] = alerts.evaluar_caudal([_rio(108.5, 108.78, 107.97, tendencia="Descendente")])
        self.assertEqual((a["tipo"], a["nivel"]), ("nivel_bajo", "alerta"))
        self.assertIn("bajando", a["detalle"])
        [c] = alerts.evaluar_caudal([_rio(15.0, 14.0, 18.0, unidad="m³/s")])
        self.assertEqual(c["tipo"], "caudal")
        self.assertTrue(c["detalle"].startswith("Caudal"))


if __name__ == "__main__":
    unittest.main()
