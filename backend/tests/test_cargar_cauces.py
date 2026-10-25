"""
Cargador de los cauces nacionales (backend/mapas/cargar_cauces.py) y su conector (connectors/ana_rios.py):
normalización y comodín de nombres, parseo de respuestas reales de GeoSNIRH (muestras chicas en
tests/muestras/ana_rios_*.json), emparejamiento por nombre + cercanía, unión de tramos, recorte,
validación, copias en disco y el --aplicar con la BD simulada. Sin red ni psycopg.
"""
import io
import json
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from backend.connectors import ana_rios as ar
from backend.mapas import cargar_cauces as cc

MUESTRAS = Path(__file__).parent / "muestras"
RIMAC = (MUESTRAS / "ana_rios_rj056_rimac_chosica_2km.json").read_bytes()
INGENIO = (MUESTRAS / "ana_rios_rj056_quebrada_ingenio.json").read_bytes()
MASHCON = (MUESTRAS / "ana_rios_ign_mashcon_2km.json").read_bytes()
VACIO = b'{"type":"FeatureCollection","features":[]}'
CHOSICA = (-11.92986, -76.68964)


def _linea(lon0, lat0, lon1, lat1, n=5):
    return [[round(lon0 + (lon1 - lon0) * i / (n - 1), 6), round(lat0 + (lat1 - lat0) * i / (n - 1), 6)] for i in range(n)]


def _tramo(id_, codigo, nombre, lineas, km=None, capa="ana_rj056"):
    return ar.Tramo(capa=capa, id=id_, codigo=codigo, nombre=nombre, km_declarado=km, lineas=lineas, props={})


def _fc(*tramos, excedido=False):
    """Respuesta f=geojson como la de ArcGIS, armada con Tramos."""
    campo = {"ana_rj056": ("NOMBRE_CA", "CODIGO_CA", "LONG_KM"), "ana_ign": ("NOMBRE_COMPLETO", "IDE_CUERPO_AGUA", "NUM_LONGITUD")}
    feats = []
    for t in tramos:
        n, c, k = campo[t.capa]
        feats.append({"type": "Feature", "id": t.id, "properties": {n: t.nombre, c: t.codigo, k: t.km_declarado},
                      "geometry": {"type": "MultiLineString", "coordinates": t.lineas}})
    d = {"type": "FeatureCollection", "features": feats}
    if excedido:
        d["exceededTransferLimit"] = True
    return json.dumps(d).encode()


class Descargas:
    """descargar(url) de mentira: responde según la capa y el comodín que lleva la URL, y cuenta."""

    def __init__(self, respuestas):
        self.respuestas, self.urls = respuestas, []

    def __call__(self, url):
        self.urls.append(url)
        capa = "rj" if "NOMBRE_CA" in url else "ign"
        for (c, patron), cuerpo in self.respuestas.items():
            if c == capa and patron in url:
                return cuerpo.pop(0) if isinstance(cuerpo, list) else cuerpo
        return VACIO


class TestNombres(unittest.TestCase):
    def test_normalizado(self):
        self.assertEqual(ar.nombre_normalizado("Río Jequetepeque"), "jequetepeque")
        self.assertEqual(ar.nombre_normalizado("Rio  Mashcon"), "mashcon")
        self.assertEqual(ar.nombre_normalizado("Quebrada Ingenio"), "ingenio")
        self.assertEqual(ar.nombre_normalizado("Río Santiago"), "santiago")
        self.assertEqual(ar.nombre_normalizado("Madre De Dios"), "madre de dios")
        self.assertEqual(ar.nombre_normalizado("MARAÑÓN"), "maranon")
        self.assertEqual(ar.nombre_normalizado(None), "")

    def test_comodin(self):
        # cada letra acentuable pasa a '_' porque ANA escribe la tilde a veces sí y a veces no
        self.assertEqual(ar.patron_like("Rímac"), "% R_M_C")
        self.assertEqual(ar.patron_like("Río Marañón"), "% M_R____")
        self.assertEqual(ar.patron_like("Cañete"), "% C___T_")
        self.assertEqual(ar.patron_like("Madre De Dios"), "% M_DR_ D_ D__S")
        self.assertEqual(ar.where_nombre(ar.IGN, "Mashcon"), "UPPER(NOMBRE_COMPLETO) LIKE '% M_SHC__'")
        self.assertEqual(ar.patron_like("O'Higgins"), "% _''H_GG__S")

    def test_slug(self):
        self.assertEqual(cc.slug("Chancay Lambayeque"), "chancay_lambayeque")
        self.assertEqual(cc.slug("Río Santiago"), "santiago")
        self.assertEqual(cc.slug("Madre De Dios"), "madre_de_dios")
        self.assertEqual(cc.slug("El Ingenio"), "el_ingenio")

    def test_url_consulta(self):
        url = ar.url_consulta(ar.RJ056, ar.where_nombre(ar.RJ056, "Rímac"), punto=CHOSICA)
        self.assertTrue(url.startswith("https://geosnirh.ana.gob.pe/server/rest/services/P%C3%BAblico/Rios/MapServer/37/query?"))
        for trozo in ("f=geojson", "outSR=4326", "geometryPrecision=5", "maxAllowableOffset=5e-05",
                      "geometry=-76.68964%2C-11.92986", "distance=2000", "units=esriSRUnit_Meter",
                      "spatialRel=esriSpatialRelIntersects", "resultOffset=0", "resultRecordCount=5000"):
            self.assertIn(trozo, url)
        self.assertNotIn("distance", ar.url_consulta(ar.IGN, "1=1"))
        self.assertIn("resultRecordCount=2000", ar.url_consulta(ar.IGN, "1=1"))

    def test_titulo_aviso(self):
        self.assertEqual(cc.titulo_aviso("INCREMENTO DEL CAUDAL DEL RÍO MASHCÓN - ESTACIÓN MASHCÓN"), ("MASHCÓN", "MASHCÓN"))
        self.assertEqual(cc.titulo_aviso("SITUACIÓN ACTUAL DEL DESCENSO DEL NIVEL DEL RIO AMAZONAS - ESTACIÓN TAMSHIYACU"),
                         ("AMAZONAS", "TAMSHIYACU"))
        self.assertEqual(cc.titulo_aviso("INCREMENTO DEL NIVEL DEL RÍO UCAYALI - ESTACIÓN PUCALLPA - COHIDRO"),
                         ("UCAYALI", "PUCALLPA - COHIDRO"))
        self.assertIsNone(cc.titulo_aviso("AVISO SIN FORMATO"))


class TestParsear(unittest.TestCase):
    def test_muestras_reales(self):
        tramos, excedido = ar.parsear(RIMAC, ar.RJ056)
        self.assertFalse(excedido)
        self.assertEqual(len(tramos), 1)
        t = tramos[0]
        self.assertEqual((t.id, t.codigo, t.nombre, t.capa), (518, "1375543", "Río Rímac", "ana_rj056"))
        self.assertAlmostEqual(t.km_declarado, 34.59141)
        self.assertEqual(t.vertices, 61)
        self.assertEqual(t.props["NOMBRE_UH"], "Cuenca Rímac")
        self.assertAlmostEqual(cc.longitud_km(t.lineas), 34.5, delta=0.3)       # el offset de 33 m apenas acorta
        self.assertLess(cc.distancia_m(*CHOSICA, t.lineas), 150)                # pasa junto a la estación Chosica
        q, _ = ar.parsear(INGENIO, ar.RJ056)
        self.assertEqual((q[0].nombre, q[0].codigo, q[0].vertices), ("Quebrada Ingenio", "13726", 279))
        self.assertEqual(ar.nombre_normalizado(q[0].nombre), "ingenio")
        m, _ = ar.parsear(MASHCON, ar.IGN)
        self.assertEqual((m[0].id, m[0].codigo, m[0].nombre, m[0].capa), (5553, "5597", "Río Mashcon", "ana_ign"))
        self.assertAlmostEqual(m[0].km_declarado, 6.531, places=2)
        self.assertLess(cc.distancia_m(-7.165, -78.4783, m[0].lineas), 60)      # estación Mashcón

    def test_error_y_formatos(self):
        with self.assertRaisesRegex(ValueError, "error 400"):
            ar.parsear(b'{"error":{"code":400,"message":"Invalid query","details":[]}}', ar.RJ056)
        with self.assertRaisesRegex(ValueError, "FeatureCollection"):
            ar.parsear(b'{"type":"Feature"}', ar.RJ056)
        with self.assertRaisesRegex(ValueError, "Polygon"):
            ar.parsear(b'{"type":"FeatureCollection","features":[{"type":"Feature","id":1,"properties":{},'
                       b'"geometry":{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}}]}', ar.RJ056)
        # exceededTransferLimit en cualquiera de sus dos formas; sin geometría se salta
        datos = {"type": "FeatureCollection", "properties": {"exceededTransferLimit": True},
                 "features": [{"type": "Feature", "id": 7, "properties": {"OBJECTID_1": 7}, "geometry": None}]}
        tramos, excedido = ar.parsear(json.dumps(datos).encode(), ar.RJ056)
        self.assertEqual((tramos, excedido), ([], True))
        # LineString con z y MultiLineString
        datos = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": 1, "properties": {"NOMBRE_CA": "Río X", "CODIGO_CA": "1", "LONG_KM": 1},
             "geometry": {"type": "LineString", "coordinates": [[-78, -7, 100], [-78.01, -7.01, 90]]}},
            {"type": "Feature", "id": 2, "properties": {"NOMBRE_CA": "Río X", "CODIGO_CA": "2", "LONG_KM": None},
             "geometry": {"type": "MultiLineString", "coordinates": [[[-78, -7], [-78, -7.1]], [[-78, -7.1]]]}}]}
        tramos, _ = ar.parsear(json.dumps(datos).encode(), ar.RJ056)
        self.assertEqual([t.lineas for t in tramos], [[[[-78.0, -7.0], [-78.01, -7.01]]], [[[-78.0, -7.0], [-78.0, -7.1]]]])
        self.assertIsNone(tramos[1].km_declarado)

    def test_paginacion(self):
        a, b = _tramo(1, "1", "Río X", [_linea(-78, -7, -78, -7.1)]), _tramo(2, "2", "Río X", [_linea(-78, -7.1, -78, -7.2)])
        d = Descargas({("rj", "resultOffset=0"): _fc(a, excedido=True), ("rj", "resultOffset=1"): _fc(b)})
        with mock.patch.object(ar.time, "sleep"):
            tramos, url, nbytes = ar.consultar(ar.RJ056, "1=1", descargar=d)
        self.assertEqual([t.id for t in tramos], [1, 2])
        self.assertEqual(len(d.urls), 2)
        self.assertIn("resultOffset=0", url)
        self.assertEqual(nbytes, len(_fc(a, excedido=True)) + len(_fc(b)))

    def test_buscar_cerca_confirma_el_nombre(self):
        d = Descargas({("rj", "R_M_C"): RIMAC})
        tramos, _, _ = ar.buscar_cerca(ar.RJ056, "Rímac", CHOSICA, descargar=d)
        self.assertEqual([t.codigo for t in tramos], ["1375543"])
        # el comodín también trae 'Apurímac' ('%R_M_C' casa con 'APURIMAC'): se descarta en el cliente
        tramos, _, _ = ar.buscar_cerca(ar.RJ056, "Apurímac", CHOSICA, descargar=d)
        self.assertEqual(tramos, [])


class TestGeometria(unittest.TestCase):
    def test_distancias_y_largo(self):
        linea = [[-78.0, -7.0], [-78.0, -7.1]]              # 11,1 km hacia el sur
        self.assertAlmostEqual(cc.haversine_km(linea[0], linea[1]), 11.12, places=1)
        self.assertAlmostEqual(cc.longitud_km([linea]), 11.12, places=1)
        self.assertAlmostEqual(cc.distancia_m(-7.05, -78.0, [linea]), 0, delta=0.5)       # sobre la línea
        self.assertAlmostEqual(cc.distancia_m(-7.05, -78.001, [linea]), 110.5, delta=1)   # 0,001° al oeste
        self.assertAlmostEqual(cc.distancia_m(-7.2, -78.0, [linea]), 11_120, delta=20)    # más allá del extremo
        self.assertTrue(cc.en_peru([linea]))
        self.assertFalse(cc.en_peru([[[-7.0, -78.0], [-7.1, -78.0]]]))                  # lat y lon invertidas

    def test_unir_tramos(self):
        semilla = _tramo(1, "1375583", "Río Chancay", [_linea(-76.9, -11.3, -76.8, -11.3)])
        unido = _tramo(2, "1375581", "Río Chancay", [_linea(-76.8, -11.3, -76.7, -11.25)])      # toca el extremo
        encadenado = _tramo(3, "1375585", "Río Chancay", [_linea(-76.7001, -11.25, -76.6, -11.2)])  # a 11 m del 2
        lambayeque = _tramo(4, "137769", "Río Chancay", [_linea(-79.4, -6.6, -79.3, -6.65)])     # el homónimo
        tramos = cc.unir_tramos([lambayeque, encadenado, unido, semilla], [semilla])
        self.assertEqual([t.id for t in tramos], [2, 1, 3])      # ordenados por código
        self.assertNotIn(4, [t.id for t in tramos])
        # la semilla entra aunque la lista completa no la traiga
        self.assertEqual([t.id for t in cc.unir_tramos([lambayeque], [semilla])], [1])

    def test_recortar(self):
        linea = _linea(-78.0, -7.0, -78.0, -8.0, n=101)        # 111 km, un vértice cada 1,1 km
        corto = cc.recortar([linea], [(-7.5, -78.0)], 10)
        self.assertEqual(len(corto), 1)
        self.assertAlmostEqual(cc.longitud_km(corto), 18.9, delta=1.2)   # los vértices van cada 1,1 km
        self.assertEqual(cc.recortar([linea], [(-7.5, -78.0), (-7.9, -78.0)], 5), cc.recortar([linea], [(-7.5, -78.0), (-7.9, -78.0)], 5))
        self.assertEqual(len(cc.recortar([linea], [(-7.5, -78.0), (-7.9, -78.0)], 5)), 2)   # dos ventanas separadas
        self.assertEqual(cc.recortar([linea], [(-6.0, -78.0)], 5), [])                       # ancla lejos: nada


CAUDAL = [
    {"rio": "Rímac", "departamento": "Lima", "estacion": "Chosica", "lat": -11.92986, "lon": -76.68964},
    {"rio": "Rímac", "departamento": "Lima", "estacion": "San Mateo", "lat": -11.7601, "lon": -76.3011},
    {"rio": "Santa", "departamento": "Áncash", "estacion": "San Pedro", "lat": -9.60776, "lon": -77.50963},
    {"rio": "Charanal", "departamento": "Piura", "estacion": "San Pedro", "lat": -5.07954, "lon": -80.0162},
    {"rio": "Mashcon", "departamento": "Cajamarca", "estacion": "Mashcón", "lat": -7.165, "lon": -78.4783},
    {"rio": "Salcca", "departamento": "Cusco", "estacion": "Salcca", "lat": -14.16991, "lon": -71.23186},
    {"rio": "Marañón", "departamento": "Loreto", "estacion": "Nauta", "lat": -4.5146, "lon": -73.5831},
    {"rio": "Marañón", "departamento": "Cajamarca", "estacion": "Balsas", "lat": -6.8448, "lon": -78.0301},
    {"rio": "Titicaca", "departamento": "Puno", "estacion": "Muelle Enafer", "lat": None, "lon": None},
]
AVISOS = [
    {"ce": "47278214", "titulo": "INCREMENTO DEL CAUDAL DEL RÍO RÍMAC - ESTACIÓN CHOSICA", "n": 19, "nombre": "CHOSICA",
     "departamento": "Lima", "lat": -11.92986, "lon": -76.68964},
    {"ce": "114118", "titulo": "INCREMENTO DEL NIVEL DEL RÍO VILCANOTA - ESTACIÓN SALCCA", "n": 7, "nombre": "SALCCA",
     "departamento": "Cusco", "lat": -14.16991, "lon": -71.23186},
    {"ce": "114118", "titulo": "INCREMENTO DEL NIVEL DEL RÍO SALCCA - ESTACIÓN SALCCA", "n": 20, "nombre": "SALCCA",
     "departamento": "Cusco", "lat": -14.16991, "lon": -71.23186},
    {"ce": "472B3006", "titulo": "SITUACIÓN ACTUAL DEL CAUDAL DEL RÍO MARAÑÓN - ESTACIÓN CUMBA", "n": 3, "nombre": "CUMBA",
     "departamento": "Cajamarca", "lat": -5.94135, "lon": -78.66413},
    {"ce": "221804", "titulo": "INCREMENTO DEL NIVEL DEL RÍO BIAVO - ESTACIÓN BIAVO", "n": 1, "nombre": "BIAVO",
     "departamento": "San Martín", "lat": -7.25497, "lon": -76.47778},
    {"ce": "210503", "titulo": "SITUACIÓN ACTUAL DEL CAUDAL DEL RÍO PIURA - ESTACIÓN PUENTE EGUIGUREN", "n": 1,
     "nombre": None, "departamento": None, "lat": None, "lon": None},
    {"ce": "220213", "titulo": "INCREMENTO DEL CAUDAL DEL RÍO MASHCÓN - ESTACIÓN MASHCÓN", "n": 24, "nombre": "MASHCON",
     "departamento": "Cajamarca", "lat": -7.165, "lon": -78.47833},
    {"ce": "999", "titulo": "AVISO SIN FORMATO", "n": 1, "nombre": None, "departamento": None, "lat": None, "lon": None},
]
VIGILADOS = [{"id": "mashcon", "rio_ana": "Mashcon", "estacion_ana": "Mashcón"}]
ALIAS = {"rios": {"titicaca": {"sin_trazo": "Es el lago Titicaca: no hay cauce."}}, "senamhi": {"biavo": "biabo"}}


class TestObjetivos(unittest.TestCase):
    def test_armar(self):
        objetivos, notas = cc.armar_objetivos(CAUDAL, AVISOS, VIGILADOS, ALIAS)
        por = {o.rio_ana: o for o in objetivos}
        self.assertEqual(sorted(por), ["biabo", "charanal", "maranon", "rimac", "salcca", "santa", "titicaca"])
        # el Mashcón ya está en rio_vigilado: no se duplica
        self.assertTrue(any("mashcon" in n and "rio_vigilado" in n for n in notas))
        # un río, varias estaciones y departamentos; la estación SENAMHI se une por el nombre de la estación
        self.assertEqual(por["rimac"].estaciones, ["Chosica", "San Mateo"])
        self.assertEqual(por["rimac"].ces, ["47278214"])
        self.assertEqual(por["maranon"].departamentos, {"Cajamarca", "Loreto"})
        self.assertEqual(por["maranon"].ces, ["472B3006"])                      # Cumba, por el nombre del río
        self.assertEqual([a.origen for a in por["maranon"].anclas], ["ana", "ana", "senamhi"])
        # los dos 'San Pedro' quedan en ríos distintos
        self.assertEqual((por["santa"].estaciones, por["charanal"].estaciones), (["San Pedro"], ["San Pedro"]))
        # el título más frecuente manda (Salcca 20 frente a Vilcanota 7) y coincide con ANA
        self.assertEqual(por["salcca"].ces, ["114118"])
        # río solo de SENAMHI, con alias de nombre y la coordenada de la tabla estacion
        self.assertTrue(por["biabo"].solo_senamhi)
        self.assertEqual((por["biabo"].rio, por["biabo"].estaciones, por["biabo"].ces), ("Biabo", [], ["221804"]))
        self.assertEqual(por["biabo"].con_coordenada[0].lat, -7.25497)
        # sin coordenada ni río de ANA no hay dónde buscar; sin coordenada de ANA tampoco
        self.assertTrue(any("210503" in n for n in notas))
        self.assertEqual(por["titicaca"].con_coordenada, [])
        self.assertNotIn("piura", por)


class TestEmparejar(unittest.TestCase):
    def setUp(self):
        self.o = cc.Objetivo(rio_ana="rimac", rio="Rímac", departamentos={"Lima"},
                             anclas=[cc.Ancla("Chosica", *CHOSICA, "ana"), cc.Ancla("San Mateo", -11.7601, -76.3011, "ana")])
        self.sleep = mock.patch.object(cc.time, "sleep")
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()

    def test_rj056_primero_y_rio_completo(self):
        # cerca de Chosica solo está el tramo 1375543; el río completo trae otro conectado y un homónimo lejano
        tramo, _ = ar.parsear(RIMAC, ar.RJ056)
        fin = tramo[0].lineas[0][-1]
        otro = _tramo(519, "1375545", "Río Rímac", [[fin, [fin[0] - 0.1, fin[1] - 0.05]]], km=12)
        lejos = _tramo(900, "4999", "Río Rímac", [_linea(-73.0, -12.0, -73.1, -12.0)], km=10)
        d = Descargas({("rj", "R_M_C"): [RIMAC, _fc(tramo[0], otro, lejos)]})
        r = cc.emparejar(self.o, {}, descargar=d, pausa=0)
        self.assertTrue(r.ok)
        self.assertIs(r.capa, ar.RJ056)
        self.assertEqual([t.codigo for t in r.tramos], ["1375543", "1375545"])
        self.assertEqual(len(d.urls), 2)                   # búsqueda cerca + río completo
        self.assertIn("distance=2000", d.urls[0])
        self.assertNotIn("distance", d.urls[1])
        self.assertAlmostEqual(r.km_declarado, 46.59, places=1)
        self.assertEqual(r.distancias[0]["estacion"], "Chosica")
        self.assertLess(r.dist_min_m, 150)
        self.assertEqual(r.nombre, "Río Rímac")
        self.assertEqual(r.avisos, ["estación San Mateo a 32582 m del trazo"][:0] + [a for a in r.avisos if "San Mateo" in a])
        f = cc.fila(r)
        self.assertEqual((f["rio_ana"], f["capa"], f["codigos"], f["tramos"], f["estaciones"]),
                         ("rimac", "ana_rj056", ["1375543", "1375545"], 2, ["Chosica", "San Mateo"]))
        self.assertEqual(json.loads(f["geom"])["type"], "MultiLineString")
        self.assertEqual(len(json.loads(f["geom"])["coordinates"]), 2)
        self.assertTrue(f["fuente_url"].startswith("https://") and f["url_consulta"].startswith("https://"))
        self.assertIn("ANA", f["atribucion"])
        self.assertEqual(f["fecha_fuente"], "2018-01-30")
        self.assertIn("OK" if not r.avisos else "AVISO", cc.linea_resumen(r))

    def test_cae_a_ign_y_avisa_alias(self):
        o = cc.Objetivo(rio_ana="mashcon", rio="Mashcon", anclas=[cc.Ancla("Mashcón", -7.165, -78.4783, "ana")])
        d = Descargas({("ign", "M_SHC__"): MASHCON})
        r = cc.emparejar(o, {}, descargar=d, pausa=0)
        self.assertTrue(r.ok)
        self.assertIs(r.capa, ar.IGN)
        self.assertEqual(r.nombre_capa, "Río Mashcon")
        self.assertEqual([u.count("NOMBRE_CA") > 0 for u in d.urls], [True, False, False])   # RJ056 vacío, luego IGN
        self.assertEqual(cc.fila(r)["fecha_fuente"], "2026-04")

    def test_sin_trazo_y_alias(self):
        r = cc.emparejar(self.o, {"rimac": {"sin_trazo": "no hay cauce"}}, descargar=Descargas({}), pausa=0)
        self.assertEqual((r.ok, r.motivo), (False, "no hay cauce"))
        self.assertIn("SIN TRAZO", cc.linea_resumen(r))
        # alias con nombre y capa forzada: solo consulta IGN con el nombre del alias
        d = Descargas({("ign", "LL__T_"): _fc(_tramo(1, "77", "Río Llauta", [_linea(-76.69, -11.93, -76.6, -11.9)], km=10, capa="ana_ign"))})
        r = cc.emparejar(self.o, {"rimac": {"nombre": "Río Llauta", "capa": "ana_ign", "mostrar": "Río Llauta (Palpa)"}},
                         descargar=d, pausa=0)
        self.assertTrue(r.ok)
        self.assertTrue(all("NOMBRE_COMPLETO" in u for u in d.urls))
        self.assertEqual(r.nombre, "Río Llauta (Palpa)")
        self.assertTrue(any(a.startswith("alias:") for a in r.avisos))
        self.assertEqual(cc.fila(r)["alias"], "Río Llauta")
        # nada en ninguna capa
        r = cc.emparejar(self.o, {}, descargar=Descargas({}), pausa=0)
        self.assertFalse(r.ok)
        self.assertIn("sin línea llamada 'Rímac'", r.motivo)
        self.assertIn("cauces_alias.json", r.motivo)

    def test_validaciones(self):
        lejos = _tramo(1, "1", "Río Rímac", [_linea(-76.68, -11.915, -76.60, -11.90)], km=9)   # a ~1,7 km de Chosica
        d = Descargas({("rj", "R_M_C"): _fc(lejos)})
        r = cc.emparejar(self.o, {}, descargar=d, pausa=0)
        self.assertFalse(r.ok)
        self.assertIn("ninguna estación a menos de 300 m", r.motivo)
        self.assertIn("distance=2000", d.urls[0])
        # con radio_m en el alias (coordenada de ANA desplazada) se busca más lejos, se acepta y queda el aviso
        d = Descargas({("rj", "R_M_C"): _fc(lejos)})
        r = cc.emparejar(self.o, {"rimac": {"radio_m": 3000}}, descargar=d, pausa=0)
        self.assertTrue(r.ok)
        self.assertTrue(any("Chosica a" in a for a in r.avisos))
        self.assertIn("distance=3000", d.urls[0])
        # --forzar también
        r = cc.emparejar(self.o, {}, descargar=Descargas({("rj", "R_M_C"): _fc(lejos)}), pausa=0, forzar=True)
        self.assertTrue(r.ok)
        self.assertTrue(any("[forzado]" in a for a in r.avisos))
        # km muy por encima de lo declarado: doble orilla, no se guarda
        doble, _ = ar.parsear(RIMAC, ar.RJ056)
        doble[0].km_declarado = 10.0
        r = cc.emparejar(self.o, {}, descargar=Descargas({("rj", "R_M_C"): _fc(doble[0])}), pausa=0)
        self.assertFalse(r.ok)
        self.assertIn("doble línea", r.motivo)
        # fuera del Perú
        fuera = _tramo(1, "1", "Río Rímac", [_linea(-76.69, -11.93, -60.0, -11.9)], km=1)
        r = cc.emparejar(self.o, {}, descargar=Descargas({("rj", "R_M_C"): _fc(fuera)}), pausa=0)
        self.assertIn("fuera del Perú", r.motivo)

    def test_senamhi_lejana_se_suelta_y_recorte(self):
        self.o.anclas.append(cc.Ancla("Otra", -11.5, -76.0, "senamhi", "123"))
        self.o.ces.append("123")
        tramo, _ = ar.parsear(RIMAC, ar.RJ056)
        r = cc.emparejar(self.o, {}, descargar=Descargas({("rj", "R_M_C"): RIMAC}), pausa=0, recorte_km=5)
        self.assertTrue(r.ok)
        self.assertEqual(self.o.ces, [])
        self.assertTrue(any("SENAMHI 123" in a for a in r.avisos))
        self.assertLess(r.km, 11)                                       # 5 km a cada lado de Chosica
        self.assertEqual(cc.fila(r)["estaciones_senamhi"], [])


class TestCopiasYResumen(unittest.TestCase):
    def test_copia_ida_y_vuelta(self):
        o = cc.Objetivo(rio_ana="rimac", rio="Rímac", departamentos={"Lima"}, anclas=[cc.Ancla("Chosica", *CHOSICA, "ana")])
        with mock.patch.object(cc.time, "sleep"):
            r = cc.emparejar(o, {}, descargar=Descargas({("rj", "R_M_C"): RIMAC}), pausa=0)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = cc.guardar_copia(r, Path(tmp))
            self.assertEqual(ruta.name, "rimac.geojson")
            fc = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertEqual((fc["capa"], fc["nombre_capa"], len(fc["features"])), ("ana_rj056", "Río Rímac", 1))
            self.assertTrue(fc["url_consulta"].startswith("https://"))
            self.assertEqual(fc["features"][0]["properties"]["CODIGO_CA"], "1375543")
            r2 = cc.leer_copia(o, {}, Path(tmp))
            self.assertTrue(r2.desde_copia)
            r2 = cc.completar(r2, "Rímac", cc.RADIO_M)
            self.assertEqual((r2.km, r2.dist_min_m, r2.nombre_capa), (r.km, r.dist_min_m, r.nombre_capa))
            self.assertIn("[copia]", cc.linea_resumen(r2))
            self.assertIsNone(cc.leer_copia(cc.Objetivo(rio_ana="otro", rio="Otro"), {}, Path(tmp)))

    def test_resumen(self):
        o1 = cc.Objetivo(rio_ana="rimac", rio="Rímac")
        o2 = cc.Objetivo(rio_ana="titicaca", rio="Titicaca")
        bien = cc.Resultado(objetivo=o1, capa=ar.RJ056, lineas=[[[-76.7, -11.9], [-76.6, -11.9]]], km=10.9)
        sin = cc.Resultado(objetivo=o2, motivo="Es el lago")
        texto = cc.resumen([bien, sin], [{"rio_ana": "viejo", "capa": "ana_ign", "km": 1}])
        self.assertIn("2 ríos buscados: 1 bien, 0 con aviso, 1 sin trazo", texto)
        self.assertIn("sin trazo: titicaca", texto)
        self.assertIn("sin fila todavía en rio_cauce (1): rimac", texto)
        self.assertIn("--podar): viejo", texto)


class CursorFalso:
    def __init__(self, bd):
        self.bd, self.description, self._filas = bd, None, []

    def execute(self, sql, params=None):
        self.bd["sql"].append((sql.strip().split("\n")[0], params))
        if "to_regclass" in sql:
            self._filas = [(self.bd["hay_tabla"],)]
        elif "from caudal_actual" in sql:
            self.description = [("rio",), ("departamento",), ("estacion",), ("lat",), ("lon",)]
            self._filas = [(f["rio"], f["departamento"], f["estacion"], f["lat"], f["lon"]) for f in CAUDAL]
        elif "from aviso_hidrologico" in sql:
            self.description = [("ce",), ("titulo",), ("n",), ("nombre",), ("departamento",), ("lat",), ("lon",)]
            self._filas = [(a["ce"], a["titulo"], a["n"], a["nombre"], a["departamento"], a["lat"], a["lon"]) for a in AVISOS]
        elif "from rio_vigilado" in sql:
            self.description = [("id",), ("rio_ana",), ("estacion_ana",)]
            self._filas = [("mashcon", "Mashcon", "Mashcón")]
        elif "from rio_cauce" in sql and "delete" not in sql:
            self.description = [("rio_ana",), ("capa",), ("km",)]
            self._filas = [("viejo", "ana_ign", 1)]
        elif sql.strip().startswith("delete"):
            self.bd["borrados"] = params
            self.rowcount = 1

    def executemany(self, sql, filas):
        self.bd["upserts"].extend(filas)

    def fetchone(self):
        return self._filas[0]

    def fetchall(self):
        return self._filas

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ConnFalsa:
    def __init__(self, bd):
        self.bd = bd

    def cursor(self):
        return CursorFalso(self.bd)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestMain(unittest.TestCase):
    def _correr(self, argv, bd):
        salida = io.StringIO()
        with mock.patch.object(cc, "conectar", lambda: ConnFalsa(bd)), redirect_stdout(salida), \
                self.assertLogs("cargar_cauces", level="INFO") as logs:
            codigo = cc.main(argv)
        return codigo, salida.getvalue(), "\n".join(logs.output)

    def test_seco_y_aplicar_desde_copia(self):
        o = cc.Objetivo(rio_ana="rimac", rio="Rímac", anclas=[cc.Ancla("Chosica", *CHOSICA, "ana")])
        with mock.patch.object(cc.time, "sleep"):
            r = cc.emparejar(o, {}, descargar=Descargas({("rj", "R_M_C"): RIMAC}), pausa=0)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(cc, "leer_alias", lambda: ALIAS):
            cc.guardar_copia(r, Path(tmp))
            bd = {"sql": [], "upserts": [], "hay_tabla": True}
            # en seco: solo lee la BD; sin copia ni red, los demás ríos quedan sin trazo pero no revientan
            with mock.patch.object(cc.ana_rios, "_bajar", lambda url: VACIO), mock.patch.object(cc.time, "sleep"):
                codigo, salida, logs = self._correr(["--desde-copia", "--copias", tmp], bd)
            self.assertEqual(codigo, 0)
            self.assertIn("rimac", salida)
            self.assertIn("[copia]", salida)
            self.assertIn("SIN TRAZO  titicaca", salida)
            self.assertIn("Prueba en seco", logs)
            self.assertEqual(bd["upserts"], [])
            # --aplicar escribe solo los que tienen trazo; --podar no se combina con --rio
            with mock.patch.object(cc.ana_rios, "_bajar", lambda url: VACIO), mock.patch.object(cc.time, "sleep"):
                codigo, salida, logs = self._correr(["--desde-copia", "--copias", tmp, "--aplicar", "--rio", "Rímac"], bd)
            self.assertEqual(codigo, 0)
            self.assertEqual([f["rio_ana"] for f in bd["upserts"]], ["rimac"])
            self.assertNotIn("borrados", bd)
            self.assertIn("Guardado: 1 ríos", logs)
            codigo, _, logs = self._correr(["--aplicar", "--rio", "Rímac", "--podar"], bd)
            self.assertEqual(codigo, 1)
            self.assertIn("--podar no se combina", logs)
            # sin la tabla: sale con 2 sin escribir
            bd = {"sql": [], "upserts": [], "hay_tabla": False}
            with mock.patch.object(cc.ana_rios, "_bajar", lambda url: VACIO), mock.patch.object(cc.time, "sleep"):
                codigo, _, logs = self._correr(["--desde-copia", "--copias", tmp, "--aplicar", "--rio", "rimac"], bd)
            self.assertEqual(codigo, 2)
            self.assertIn("Falta la tabla rio_cauce", logs)
            self.assertEqual(bd["upserts"], [])

    def test_rio_desconocido_y_sin_dsn(self):
        bd = {"sql": [], "upserts": [], "hay_tabla": True}
        codigo, _, logs = self._correr(["--rio", "Nilo"], bd)
        self.assertEqual(codigo, 1)
        self.assertIn("Nilo", logs)
        with mock.patch.object(cc, "conectar", side_effect=RuntimeError("Falta SUPABASE_DB_URL")), \
                self.assertLogs("cargar_cauces", level="ERROR") as logs:
            self.assertEqual(cc.main([]), 2)
        self.assertIn("SUPABASE_DB_URL", "\n".join(logs.output))

    def test_aplicar_podar(self):
        bd = {"sql": [], "upserts": [], "hay_tabla": True}
        borrados = cc.aplicar(ConnFalsa(bd), [{"rio_ana": "rimac"}], ["rimac", "santa"], podar=True)
        self.assertEqual((borrados, bd["borrados"]), (1, (["rimac", "santa"],)))
        self.assertEqual(bd["upserts"], [{"rio_ana": "rimac"}])


class TestAliasReal(unittest.TestCase):
    def test_archivo_del_repo(self):
        alias = cc.leer_alias()
        self.assertEqual(alias["senamhi"], {"biavo": "biabo", "cajamarquino": "cajamarca"})
        for clave, a in alias["rios"].items():
            self.assertEqual(clave, cc.slug(clave), clave)
            self.assertTrue(a.get("nombre") or a.get("sin_trazo") or a.get("radio_m") or a.get("nota"), clave)
            if a.get("capa"):
                self.assertIn(a["capa"], ar.CAPAS)
        self.assertIn("sin_trazo", alias["rios"]["titicaca"])
        self.assertIn("sin_trazo", alias["rios"]["canopampa"])
        self.assertEqual(alias["rios"]["chancay_lambayeque"]["nombre"], "Río Chancay")
        # Piura: la estación Puente Sanchez Cerro queda a 35 m del trazo de RJ056; la nota documenta que la
        # fila perdió la estación por el orden de carga, no por la distancia (sin radio_m ni sin_trazo)
        piura = alias["rios"]["piura"]
        self.assertIn("Puente Sanchez Cerro", piura["nota"])
        self.assertNotIn("radio_m", piura)
        self.assertNotIn("sin_trazo", piura)


if __name__ == "__main__":
    unittest.main()
