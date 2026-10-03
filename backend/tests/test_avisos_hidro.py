"""
Avisos hidrológicos de SENAMHI (backend/connectors/senamhi_avisos_hidro.py): la lista de 12
meses, el detalle de un aviso y las descargas simuladas. Sin red: solo librería estándar.

Muestras reales (backend/tests/muestras/, 03-10-2026 de madrugada, hora de Perú):
  avisos_hidrologicos_lista_20261003.html.gz       la lista entera (1680 avisos, 7 vigentes)
  aviso_hidrologico_67552_mashcon_rojo.html.gz     detalle del aviso 1169 del Mashcón (rojo,
                                                   13-03-2026: 30.17 m3/s, umbral 18)
  aviso_hidrologico_70483_napo_descenso.html.gz    detalle del aviso 1624 del Napo (descenso,
                                                   vigente: nivel en m.s.n.m, umbral 85.81)
"""
import gzip
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

from backend.connectors import _http
from backend.connectors import senamhi_avisos_hidro as sh
from backend.connectors.senamhi import HORA_PERU

MUESTRAS = Path(__file__).parent / "muestras"


def _leer(nombre: str) -> str:
    return gzip.decompress((MUESTRAS / nombre).read_bytes()).decode("utf-8")


LISTA = _leer("avisos_hidrologicos_lista_20261003.html.gz")
MASHCON_ROJO = _leer("aviso_hidrologico_67552_mashcon_rojo.html.gz")
NAPO_DESCENSO = _leer("aviso_hidrologico_70483_napo_descenso.html.gz")


def _fila_html(ca=1, ce="220213", nro="10", ini="2026-03-17", fin="2026-03-18", dur="24",
               nivel='<span class="dos">AMARILLO</span>', titulo="INCREMENTO DEL CAUDAL DEL RÍO MASHCÓN", clase=None):
    """Como en la web: las filas vigentes llevan "(vigente)" en el N.º y class="vigente" en sus celdas."""
    enlace = f'<a href="./?p=avisos-detalle-hidrologicos&ca={ca}&ce={ce}">'
    celdas = [f"{enlace}{titulo}</a>", f"{enlace}{nro}</a>", ini, fin, dur, nivel]
    vigente = "(vigente)" in nro if clase is None else clase
    td = '<td  class="vigente" >' if vigente else "<td >"
    return "<tr>" + "".join(f"{td}{c}</td>" for c in celdas) + "</tr>"


class TestLista(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.filas = sh.parsear_lista(LISTA)
        cls.por_ca = {f.ca: f for f in cls.filas}

    def test_conteos_de_la_muestra(self):
        f = self.filas
        self.assertEqual(len(f), 1680)
        self.assertEqual(sum(x.vigente for x in f), 7)
        self.assertEqual(sum(x.ce == "220213" for x in f), 27)      # Mashcón
        self.assertEqual(sum(x.nivel is None for x in f), 3)
        self.assertEqual(sum(x.sentido == "descenso" for x in f), 37)
        self.assertEqual({x.nivel for x in f}, {2, 3, 4, None})

    def test_fila_del_mashcon(self):
        f = self.por_ca[67739]
        self.assertEqual((f.ce, f.numero, f.nivel, f.sentido, f.vigente), ("220213", 1233, 2, "crecida", False))
        self.assertEqual((f.inicio_dia, f.fin_dia, f.duracion_h), (date(2026, 3, 17), date(2026, 3, 18), 24))
        self.assertEqual(f.titulo, "INCREMENTO DEL CAUDAL DEL RÍO MASHCÓN - ESTACIÓN MASHCÓN")   # UTF-8
        self.assertEqual(f.url, "https://www.senamhi.gob.pe/?p=avisos-detalle-hidrologicos&ca=67739&ce=220213")

    def test_rojo_y_vigente(self):
        rojo = self.por_ca[67552]
        self.assertEqual((rojo.numero, rojo.nivel, rojo.vigente), (1169, 4, False))
        napo = self.por_ca[70483]
        self.assertEqual((napo.ce, napo.numero, napo.vigente, napo.sentido, napo.nivel, napo.duracion_h),
                         ("240111", 1624, True, "descenso", 2, 60))
        # "SITUACIÓN ACTUAL ..." es de crecida
        self.assertEqual(self.por_ca[70487].sentido, "crecida")

    def test_codigo_de_estacion_con_letras(self):
        self.assertEqual(self.por_ca[65908].ce, "472B730C")
        self.assertIsNone(self.por_ca[65908].nivel)

    def test_pagina_vacia(self):
        self.assertEqual(sh.parsear_lista(""), [])
        self.assertEqual(sh.parsear_lista("<html><body>Mantenimiento</body></html>"), [])

    def test_filas_raras_se_saltan(self):
        pagina = "<table>" + "".join([
            _fila_html(ca=1),
            _fila_html(ca=2, ini="17/03/2026"),                     # fecha ilegible
            _fila_html(ca=3, nro="s/n"),                            # sin número
            _fila_html(ca=4, titulo=""),                            # sin título
            "<tr><td>sin enlace</td><td>1</td><td>2026-03-17</td><td>2026-03-18</td><td>1</td><td>x</td></tr>",
            _fila_html(ca=5, nivel="NARANJA", dur=""),              # nivel solo en texto, sin duración
            _fila_html(ca=6, nivel="", nro="12 (vigente)", titulo="DESCENSO DEL NIVEL DEL RÍO NAPO"),
            _fila_html(ca=1, nro="11"),                             # ca repetido: gana la última
            _fila_html(ca=7).replace("<td >24</td>", ""),          # 5 celdas: se salta sin romper
        ]) + "</table>"
        f = {x.ca: x for x in sh.parsear_lista(pagina)}
        self.assertEqual(sorted(f), [1, 5, 6])
        self.assertEqual(f[1].numero, 11)
        self.assertEqual((f[5].nivel, f[5].duracion_h), (3, None))
        self.assertEqual((f[6].nivel, f[6].vigente, f[6].sentido), (None, True, "descenso"))

    def test_vigencia_con_dos_senales(self):
        def fila(**kw):
            [f] = sh.parsear_lista(_fila_html(**kw))
            return f.vigente, f.ambiguo
        self.assertEqual(fila(nro="12 (vigente)"), (True, False))               # como hoy: texto y marca
        self.assertEqual(fila(nro="12"), (False, False))
        self.assertEqual(fila(nro="12", clase=True), (True, True))              # SENAMHI quitó el texto
        self.assertEqual(fila(nro="12 (vigente)", clase=False), (True, True))   # o la marca
        self.assertEqual(fila(nro="12 (no vigente)"), (False, False))           # "no vigente" no es vigente
        self.assertEqual(fila(nro='12 <span class="badge">Vigente</span>', clase=True), (True, False))
        # en la muestra las dos señales coinciden en las 1680 filas
        self.assertFalse(any(x.ambiguo for x in self.filas))
        sin_texto = sh.parsear_lista(LISTA.replace(" (vigente)", ""))
        self.assertEqual(sum(x.vigente for x in sin_texto), 7)

    def test_enlace_con_amp(self):
        fila = _fila_html(ca=9).replace("&ca=", "&amp;ca=").replace("&ce=", "&amp;ce=")
        [f] = sh.parsear_lista(fila)
        self.assertEqual((f.ca, f.ce), (9, "220213"))


class TestDetalle(unittest.TestCase):
    def test_mashcon_rojo(self):
        d = sh.parsear_detalle(MASHCON_ROJO)
        self.assertEqual((d["numero"], d["nivel"]), (1169, 4))       # "Aviso N°1169 ROJO"
        self.assertEqual((d["valor"], d["unidad"], d["umbral_rojo"]), (30.17, "m3/s", 18.0))
        self.assertTrue(d["areas"].startswith("Las potenciales áreas de afectación"))
        self.assertIn("BAMBAMARCA CHICO", d["areas"])
        self.assertTrue(d["areas"].endswith("MOLLEPAMPA."))
        self.assertTrue(d["significado_rojo"].startswith("Se espera desborde del río"))
        self.assertEqual(d["inicio"], datetime(2026, 3, 13, 6, 0, tzinfo=HORA_PERU))
        self.assertEqual(d["fin"], datetime(2026, 3, 13, 16, 0, tzinfo=HORA_PERU))
        self.assertEqual(d["emision"], datetime(2026, 3, 13, 9, 36, tzinfo=HORA_PERU))
        self.assertEqual(d["inicio"].utcoffset(), timedelta(hours=-5))
        self.assertEqual(d["inicio"].isoformat(), "2026-03-13T06:00:00-05:00")

    def test_napo_en_msnm(self):
        d = sh.parsear_detalle(NAPO_DESCENSO)
        self.assertEqual((d["numero"], d["nivel"]), (1624, 2))
        self.assertEqual((d["valor"], d["unidad"], d["umbral_rojo"]), (87.0, "m.s.n.m", 85.81))
        self.assertEqual((d["inicio"], d["fin"]), (datetime(2026, 10, 2, 6, 0, tzinfo=HORA_PERU),
                                                   datetime(2026, 10, 4, 18, 0, tzinfo=HORA_PERU)))
        # la leyenda del rojo de un aviso de descenso no habla de desborde
        self.assertNotIn("desborde", d["significado_rojo"])
        self.assertIn("encallamiento", d["significado_rojo"])

    def test_pagina_vacia_o_sin_aviso(self):
        vacio = dict.fromkeys(("numero", "nivel", "emision", "inicio", "fin", "valor", "unidad", "areas",
                               "umbral_rojo", "significado_rojo"))
        self.assertEqual(sh.parsear_detalle(""), vacio)
        # la lista sola (sin el bloque del aviso) no se confunde con un detalle
        self.assertEqual(sh.parsear_detalle(LISTA), vacio)
        # sin el bloque del aviso no se lee el resto de la página, aunque traiga los datos
        self.assertEqual(sh.parsear_detalle(MASHCON_ROJO.replace('id="nav-avisodet"', 'id="otro"')), vacio)

    def test_fechas(self):
        self.assertEqual(sh._fecha("Martes, 1 de Setiembre de 2026 a las 7:05 hrs"),
                         datetime(2026, 9, 1, 7, 5, tzinfo=HORA_PERU))
        self.assertIsNone(sh._fecha("31 de Junio de 2026 - 06:00"))          # no existe
        self.assertIsNone(sh._fecha("13 de Marzzo de 2026 - 06:00"))
        self.assertIsNone(sh._fecha(None))

    def test_variantes_del_html(self):
        """Cambios plausibles de la página: o el dato correcto, o None; nunca uno equivocado."""
        def con(viejo, nuevo, cuenta=1):
            self.assertIn(viejo, MASHCON_ROJO)
            return sh.parsear_detalle(MASHCON_ROJO.replace(viejo, nuevo, cuenta))
        # coma decimal
        self.assertEqual(con("30.17 m3/s", "30,17 m3/s")["valor"], 30.17)
        self.assertEqual(con('<td class="align-middle">18</td>', '<td class="align-middle">18,5</td>')["umbral_rojo"],
                         18.5)
        # a. m. / p. m.
        self.assertEqual(con("16:00 hrs", "4:00 p.m.")["fin"], datetime(2026, 3, 13, 16, 0, tzinfo=HORA_PERU))
        self.assertEqual(con("16:00 hrs", "4:00 PM")["fin"], datetime(2026, 3, 13, 16, 0, tzinfo=HORA_PERU))
        self.assertEqual(con("06:00 hrs</div>", "6:00 a.m.</div>")["inicio"],
                         datetime(2026, 3, 13, 6, 0, tzinfo=HORA_PERU))
        self.assertIsNone(con("16:00 hrs", "16:00 p.m.")["fin"])               # imposible
        # una fecha sin hora no toma la hora del campo siguiente
        d = con("Fecha de inicio: </strong>Viernes, 13 de Marzo de 2026 - 06:00 hrs",
                "Fecha de inicio: </strong>Viernes, 13 de Marzo de 2026")
        self.assertIsNone(d["inicio"])
        self.assertEqual(d["fin"], datetime(2026, 3, 13, 16, 0, tzinfo=HORA_PERU))
        # "del 2026" y "Fecha de fin"
        self.assertEqual(con("de Marzo de 2026", "de Marzo del 2026", 3)["inicio"],
                         datetime(2026, 3, 13, 6, 0, tzinfo=HORA_PERU))
        self.assertEqual(con("Fecha de final", "Fecha de fin")["fin"], datetime(2026, 3, 13, 16, 0, tzinfo=HORA_PERU))
        # las áreas con una abreviatura no se cortan en su punto
        areas = con("BAMBAMARCA CHICO", "C.P. BAMBAMARCA CHICO")["areas"]
        self.assertIn("C.P. BAMBAMARCA CHICO", areas)
        self.assertTrue(areas.endswith("MOLLEPAMPA."))
        # sin "Se recomienda", llegan hasta la frase siguiente del párrafo oficial (nunca al resto de la página)
        areas = con("Se recomienda a la población", "Recomendamos a la población")["areas"]
        self.assertTrue(areas.startswith("Las potenciales áreas de afectación"))
        self.assertTrue(areas.endswith("cercana al río."))

    def test_numeros(self):
        self.assertEqual([sh._numero(x) for x in ("30.17", "18", "30,17", "1,234.5", "85.81")],
                         [30.17, 18.0, 30.17, 1234.5, 85.81])
        for raro in ("", "S/D", "1.2.3", "-3", "18 m3/s"):
            self.assertIsNone(sh._numero(raro), raro)

    def test_umbral_no_numerico(self):
        pagina = MASHCON_ROJO.replace('<td class="align-middle">18</td>', '<td class="align-middle">S/D</td>')
        self.assertIsNone(sh.parsear_detalle(pagina)["umbral_rojo"])


class TestDescarga(unittest.TestCase):
    def setUp(self):
        self.urls = []

        def falso_get_bytes(url, max_bytes=None):
            self.urls.append((url, max_bytes))
            return "<p>RÍO</p>".encode("utf-8")

        p = mock.patch.object(_http, "get_bytes", falso_get_bytes)
        p.start()
        self.addCleanup(p.stop)

    def test_lista(self):
        self.assertEqual(sh.bajar_lista(), "<p>RÍO</p>")              # UTF-8
        self.assertEqual(self.urls, [("https://www.senamhi.gob.pe/?p=avisos-hidrologicos", sh.MAX_HTML_BYTES)])

    def test_detalle(self):
        sh.bajar_detalle(67552, "220213")
        self.assertEqual(self.urls[0][0],
                         "https://www.senamhi.gob.pe/?p=avisos-detalle-hidrologicos&ca=67552&ce=220213")

    def test_detalle_con_reintentos(self):
        fallas = [OSError("timed out"), OSError("timed out")]

        def a_la_tercera(url, max_bytes=None):
            self.urls.append((url, max_bytes))
            if fallas:
                raise fallas.pop()
            return b"<p>ok</p>"

        with mock.patch.object(_http, "get_bytes", a_la_tercera), mock.patch.object(_http.time, "sleep"):
            self.assertEqual(sh.bajar_detalle(67552, "220213"), "<p>ok</p>")
        self.assertEqual(len(self.urls), _http.INTENTOS)

    def test_detalle_rechaza_un_codigo_raro(self):
        for raro in ("220213&x=1", "", "22 02"):
            with self.assertRaises(ValueError):
                sh.bajar_detalle(1, raro)
        self.assertEqual(self.urls, [])

    def test_pausa(self):
        with mock.patch.object(sh.time, "sleep") as dormir:
            sh.pausa()
        dormir.assert_called_once_with(sh.PAUSA_S)


if __name__ == "__main__":
    unittest.main()
