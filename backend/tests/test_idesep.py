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

    def test_todos_los_zip_sin_repetir_y_en_orden(self):
        # Un registro FEN trae un .zip por trimestre; la URL suelta del script repite la primera.
        pagina = ('<a href="/geonetwork/srv/api/records/x/attachments/Anom_Pp_Ninio_97_98_DEF.zip">1</a>'
                  '<a href="/geonetwork/srv/api/records/x/attachments/Anom_Pp_Ninio_97_98_EFM.zip">2</a>'
                  '<a href="/geonetwork/srv/api/records/x/attachments/Anom_Pp_Ninio_97_98_FMA.zip">3</a>'
                  '<script>var u="https://idesep.senamhi.gob.pe/geonetwork/srv/api/records/x/attachments/Anom_Pp_Ninio_97_98_DEF.zip";</script>')
        with mock.patch.object(_http, "get", lambda url, params=None: pagina):
            enlaces = idesep.enlaces_shapefile("x")
        self.assertEqual([e.rsplit("/", 1)[-1] for e in enlaces],
                         ["Anom_Pp_Ninio_97_98_DEF.zip", "Anom_Pp_Ninio_97_98_EFM.zip", "Anom_Pp_Ninio_97_98_FMA.zip"])
        self.assertEqual([idesep.trimestre_de_nombre(e) for e in enlaces], ["DEF", "EFM", "FMA"])


class TestTrimestre(unittest.TestCase):
    def test_trimestre_de_nombre(self):
        casos = {
            "https://idesep.senamhi.gob.pe/geonetwork/srv/api/records/x/attachments/Anom_Pp_Ninio_82_83_DEF.zip": "DEF",
            "Precipitacion_EFM_Ninio_2023.zip": "EFM",
            "Precipitacion_FMA_Ninio_2023": "FMA",
            "anom_pp_ninio_2017_fma.shp": "FMA",
            "Anom_Pp_Ninio_2017.zip": None,          # sin trimestre en el nombre
            "DEFENSA_civil.zip": None,               # DEF pegado a otras letras no cuenta
            "": None,
        }
        for nombre, esperado in casos.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(idesep.trimestre_de_nombre(nombre), esperado)

    def test_anios_del_evento(self):
        self.assertEqual(cargar_fen.anios_del_evento("1997-1998"), (1997, 1998))
        self.assertEqual(cargar_fen.anios_del_evento("2017"), (2016, 2017))
        with self.assertRaises(ValueError):
            cargar_fen.anios_del_evento("sin año")

    def test_meses_legibles(self):
        casos = [
            ("DEF", "1997-1998", "diciembre de 1997 a febrero de 1998"),
            ("EFM", "1997-1998", "enero a marzo de 1998"),
            ("FMA", "1997-1998", "febrero a abril de 1998"),
            ("DEF", "2017", "diciembre de 2016 a febrero de 2017"),
            ("FMA", "2017", "febrero a abril de 2017"),          # marzo de 2017: desborde del Piura
            ("EFM", "2023", "enero a marzo de 2023"),
            ("DEF", "2023-2024", "diciembre de 2023 a febrero de 2024"),
            ("NDE", "2023-2024", "noviembre de 2023 a enero de 2024"),
            ("def", "1982-1983", "diciembre de 1982 a febrero de 1983"),   # sin distinguir mayúsculas
            (None, "2017", None),
            ("XYZ", "2017", None),
        ]
        for trimestre, periodo, esperado in casos:
            with self.subTest(trimestre=trimestre, periodo=periodo):
                self.assertEqual(cargar_fen.meses_legibles(trimestre, periodo), esperado)


GEOJSON = json.dumps({"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []}, "properties": {"RANGO": "x"}}]})
# lo que devuelve capas_de_registro: (trimestre, enlace, geojson) por cada .zip del registro
CAPAS = [("DEF", "https://idesep.senamhi.gob.pe/x/attachments/a_DEF.zip", GEOJSON),
         ("FMA", "https://idesep.senamhi.gob.pe/x/attachments/a_FMA.zip", GEOJSON)]


import contextlib


@contextlib.contextmanager
def _ctx(obj):
    yield obj


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

    @mock.patch.object(idesep, "capas_de_registro", lambda uuid, s=None, d=None: CAPAS)
    def test_prueba_en_seco(self):
        self.assertEqual(cargar_fen.main([]), 0)

    def test_aplicar_guarda_una_fila_por_evento_y_trimestre(self):
        filas = []

        class Cursor:
            def execute(self, sql, params):
                filas.append(params)

        class Conn:
            def cursor(self):
                return _ctx(Cursor())

        with mock.patch.object(idesep, "capas_de_registro", lambda uuid, s=None, d=None: CAPAS),                 mock.patch.object(cargar_fen, "conectar", lambda: _ctx(Conn())):
            self.assertEqual(cargar_fen.main(["--aplicar"]), 0)
        self.assertEqual(len(filas), 5 * len(CAPAS))
        de_2017 = [f for f in filas if f[3] == "2017"]
        self.assertEqual([(f[4], f[5]) for f in de_2017], [
            ("DEF", "diciembre de 2016 a febrero de 2017"),
            ("FMA", "febrero a abril de 2017"),
        ])
        self.assertIn("on conflict (uuid, (coalesce(trimestre, '')))", cargar_fen.UPSERT)

    def test_un_mapa_caido_no_frena_al_resto(self):
        caido = cargar_fen.EVENTOS_FEN[-1].uuid
        pedidos = []

        def a_veces(uuid, s=None, d=None):
            pedidos.append(uuid)
            if uuid == caido:
                raise RuntimeError("caido")
            return CAPAS

        with mock.patch.object(idesep, "capas_de_registro", a_veces), mock.patch.object(cargar_fen.time, "sleep"):
            self.assertEqual(cargar_fen.main([]), 1)
        # los 4 buenos una vez; el caído se reintenta (IDESEP devuelve 400 a ratos) y recién después se da por perdido
        self.assertEqual(len(pedidos), 4 + cargar_fen.INTENTOS_POR_EVENTO)
        self.assertEqual(pedidos.count(caido), cargar_fen.INTENTOS_POR_EVENTO)

    def test_reintento_por_evento_recupera_un_400_pasajero(self):
        llamadas = []

        def falla_una_vez(uuid, s=None, d=None):
            llamadas.append(uuid)
            if llamadas.count(uuid) == 1:
                raise RuntimeError("HTTP Error 400")
            return CAPAS

        with mock.patch.object(idesep, "capas_de_registro", falla_una_vez), mock.patch.object(cargar_fen.time, "sleep"):
            self.assertEqual(cargar_fen.main([]), 0)
        self.assertEqual(len(llamadas), 10)

    @mock.patch.object(idesep, "capas_de_registro", lambda uuid, s=None, d=None: CAPAS)
    def test_aplicar_sin_dsn(self):
        config.ajustes.cache_clear()
        self.addCleanup(config.ajustes.cache_clear)
        with mock.patch.dict("os.environ", {"SUPABASE_DB_URL": ""}):
            self.assertEqual(cargar_fen.main(["--aplicar"]), 2)


if __name__ == "__main__":
    unittest.main()
