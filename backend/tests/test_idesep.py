"""Conector IDESEP (catálogo CSW y enlace del shapefile) y cargador de mapas FEN."""
import json
import logging
import unittest
from unittest import mock

from backend import config
from backend.connectors import _http, idesep
from backend.mapas import cargar_fen


def _pagina_csw(registros, siguiente):
    items = "".join(
        f"<csw:SummaryRecord><dc:identifier>{u}</dc:identifier><dc:title>{t}</dc:title></csw:SummaryRecord>"
        for u, t in registros
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><csw:GetRecordsResponse '
        'xmlns:csw="http://www.opengis.net/cat/csw/2.0.2" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<csw:SearchResults numberOfRecordsMatched="3" nextRecord="{siguiente}">{items}</csw:SearchResults>'
        "</csw:GetRecordsResponse>"
    )


REGISTROS = [
    idesep.Registro("u1", "A"),
    idesep.Registro("u2", "B"),
    idesep.Registro("u3", "Anomalías de Precipitación – Evento Nuevo 2030"),
]


class TestCatalogo(unittest.TestCase):
    def test_paginacion(self):
        pedidas = []

        def falso_get(url, params=None):
            pedidas.append(params["startPosition"])
            if params["startPosition"] == "1":
                return _pagina_csw([("u1", "A"), ("u2", "B")], 3)
            return _pagina_csw([("u3", "C")], 0)

        with mock.patch.object(_http, "get", falso_get):
            regs = idesep.listar_registros(por_pagina=2)
        self.assertEqual([r.uuid for r in regs], ["u1", "u2", "u3"])
        self.assertEqual(pedidas, ["1", "3"])

    def test_exception_report_no_es_catalogo_vacio(self):
        xml = ('<?xml version="1.0"?><ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows">'
               '<ows:Exception exceptionCode="NoApplicableCode"/></ows:ExceptionReport>')
        with mock.patch.object(_http, "get", lambda url, params=None: xml):
            with self.assertRaises(RuntimeError):
                idesep.listar_registros()

    def test_titulo_normalizado(self):
        self.assertEqual(idesep.buscar_uuid("anomalías de  precipitación - evento nuevo 2030", REGISTROS), "u3")
        self.assertIsNone(idesep.buscar_uuid("No existe", REGISTROS))


class TestEnlaceShapefile(unittest.TestCase):
    def enlace(self, pagina):
        with mock.patch.object(_http, "get", lambda url, params=None: pagina):
            return idesep.enlace_shapefile("x")

    def test_href_absoluto_desescapado(self):
        self.assertEqual(
            self.enlace('<a href="https://idesep.senamhi.gob.pe/geonetwork/srv/api/records/x/attachments/a.zip?x=1&amp;y=2.zip">z</a>'),
            "https://idesep.senamhi.gob.pe/geonetwork/srv/api/records/x/attachments/a.zip?x=1&y=2.zip")

    def test_href_relativo(self):
        self.assertEqual(
            self.enlace('<a href="/geonetwork/srv/api/records/x/attachments/b.zip">z</a>'),
            "https://idesep.senamhi.gob.pe/geonetwork/srv/api/records/x/attachments/b.zip")

    def test_url_suelta_en_script(self):
        self.assertTrue(self.enlace(
            '<script>var u="https://idesep.senamhi.gob.pe/geonetwork/srv/api/records/x/attachments/c.zip";</script>'
        ).endswith("/attachments/c.zip"))

    def test_solo_https_del_propio_idesep(self):
        pagina = ('<a href="https://evil.example/attachments/m.zip">1</a>'
                  '<a href="http://idesep.senamhi.gob.pe/g/attachments/h.zip">2</a>'
                  '<a href="file:///etc/attachments/f.zip">3</a>'
                  '<a href="/geonetwork/srv/api/records/x/attachments/ok.zip">4</a>')
        self.assertTrue(self.enlace(pagina).endswith("/attachments/ok.zip"))

    def test_sin_enlace_valido(self):
        for pagina in ('<a href="https://evil.example/attachments/m.zip">x</a>',
                       '<a href="/otra/cosa.zip">x</a>'):
            with self.assertRaises(ValueError):
                self.enlace(pagina)


GEOJSON = json.dumps({"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []}, "properties": {"RANGO": "x"}}]})


class TestCargadorFEN(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def test_eventos_con_uuid_fijo_no_consultan_catalogo(self):
        fijos = [e.uuid for e in cargar_fen.EVENTOS_FEN]
        self.assertEqual(len(fijos), 5)
        self.assertTrue(all(fijos))
        with mock.patch.object(idesep, "listar_registros", side_effect=AssertionError("no debía consultarse")):
            resueltos, faltan = cargar_fen._resolver(cargar_fen.EVENTOS_FEN)
        self.assertEqual([u for _, u in resueltos], fijos)
        self.assertEqual(faltan, [])

    def test_resolver_por_titulo(self):
        nuevo = cargar_fen.EventoFEN("Anomalías de Precipitación - Evento Nuevo 2030", "2030")
        nulo = cargar_fen.EventoFEN("No existe en el catalogo", "1900")
        with mock.patch.object(idesep, "listar_registros", lambda: REGISTROS):
            resueltos, faltan = cargar_fen._resolver([nuevo, nulo])
        self.assertEqual([u for _, u in resueltos], ["u3"])
        self.assertEqual(faltan, ["No existe en el catalogo"])

    @mock.patch.object(idesep, "geojson_de_registro", lambda uuid, s=None, d=None: GEOJSON)
    def test_prueba_en_seco(self):
        self.assertEqual(cargar_fen.main([]), 0)

    def test_un_mapa_caido_no_frena_al_resto(self):
        caido = cargar_fen.EVENTOS_FEN[-1].uuid
        pedidos = []

        def a_veces(uuid, s=None, d=None):
            pedidos.append(uuid)
            if uuid == caido:
                raise RuntimeError("caido")
            return GEOJSON

        with mock.patch.object(idesep, "geojson_de_registro", a_veces):
            self.assertEqual(cargar_fen.main([]), 1)
        self.assertEqual(len(pedidos), 5)

    @mock.patch.object(idesep, "geojson_de_registro", lambda uuid, s=None, d=None: GEOJSON)
    def test_aplicar_sin_dsn(self):
        config.ajustes.cache_clear()
        self.addCleanup(config.ajustes.cache_clear)
        with mock.patch.dict("os.environ", {"SUPABASE_DB_URL": ""}):
            self.assertEqual(cargar_fen.main(["--aplicar"]), 2)


if __name__ == "__main__":
    unittest.main()
