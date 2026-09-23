"""
Nowcasting de SENAMHI: última emisión del visor, nombres de fichero, WFS (filtro, orden de
ejes, descartes, fechas, producto no publicado) y la tarea 'nowcast' con la BD y la GeoServer
simuladas. Sin red ni psycopg: solo librería estándar.

Muestras reales (backend/tests/muestras/, 22-09-2026 a las 23:17 de Lima, con el nowcasting
detenido desde las 20:40):
  nowcast_visor_20260922.html          extracto del visor: var fichero y 3 enlaces data-fichero
  nowcast_20260922-2040_forecast.json  6 de los 256 elementos del +1 h de las 20:40: un nivel 0,
                                       y de nivel 1, 2 y 3 dentro del recuadro del Perú, más uno
                                       de nivel 1 y otro de nivel 3 en Colombia y el Pacífico
"""
import copy
import json
import logging
import unittest
import urllib.parse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from backend.connectors import _http
from backend.connectors import senamhi_nowcast as sn
from backend.connectors.senamhi import HORA_PERU
from backend.ingesta import nowcast as tarea
from backend.ingesta.guardar import SQL_LATIDO

MUESTRAS = Path(__file__).parent / "muestras"
VISOR = (MUESTRAS / "nowcast_visor_20260922.html").read_text(encoding="utf-8")
WFS_2040 = json.loads((MUESTRAS / "nowcast_20260922-2040_forecast.json").read_text(encoding="utf-8"))

UTC = timezone.utc
T = datetime(2026, 9, 22, 20, 40, tzinfo=HORA_PERU)              # = 01:40Z del 23
F0 = "nowcasting_20260922-2040_analysis_20260922-2040_web"
F60 = "nowcasting_20260922-2040_forecast_20260922-2140_web"
F120 = "nowcasting_20260922-2040_forecast_20260922-2240_web"
AHORA = datetime(2026, 9, 23, 1, 48, tzinfo=UTC)                 # 20:48 en Lima: 8 min después
XML_EXCEPCION = (b'<?xml version="1.0" encoding="UTF-8"?><ows:ExceptionReport version="2.0.0">'
                 b'<ows:Exception exceptionCode="NoApplicableCode"><ows:ExceptionText>java.io.IOException'
                 b'</ows:ExceptionText></ows:Exception></ows:ExceptionReport>')


def _elemento(nivel=1, fichero=F60, fecha1="2026-09-23T01:40:00Z", fecha2="2026-09-23T02:40:00Z",
              x=-78.5, y=-7.2, lado=0.018):
    """Un cuadrado de ~2 km como los del WFS (esquina en x, y)."""
    anillo = [[x, y], [x, y + lado], [x + lado, y + lado], [x + lado, y], [x, y]]
    return {"type": "Feature", "id": "view_nowcasting.fid-x", "geometry": {"type": "Polygon", "coordinates": [anillo]},
            "geometry_name": "geom",
            "properties": {"gid": 1, "producto": "forecast", "fecha1": fecha1, "fecha2": fecha2, "nivel": nivel,
                           "ppmin": 5, "ppmax": 8, "fichero": fichero}}


def _coleccion(*features):
    return {"type": "FeatureCollection", "features": list(features)}


def _bytes(fc) -> bytes:
    return json.dumps(fc).encode("utf-8")


class TestVisor(unittest.TestCase):
    def test_ultima_emision_de_la_muestra(self):
        e = sn.ultima_emision(VISOR)
        self.assertEqual(e, T)
        self.assertEqual(e.utcoffset(), timedelta(hours=-5))

    def test_gana_la_mas_nueva_de_var_y_data_fichero(self):
        html = VISOR.replace('data-fichero="nowcasting_20260922-2020_forecast_',
                             'data-fichero="nowcasting_20260922-2050_forecast_')
        self.assertEqual(sn.ultima_emision(html), T + timedelta(minutes=10))
        # solo var fichero (un análisis también vale)
        solo_var = 'var fichero = "nowcasting_20260922-2300_analysis_20260922-2300_web";'
        self.assertEqual(sn.ultima_emision(solo_var), datetime(2026, 9, 22, 23, 0, tzinfo=HORA_PERU))

    def test_sin_fichero_es_error(self):
        with self.assertRaises(ValueError):
            sn.ultima_emision("<html>Mantenimiento</html>")
        with self.assertRaises(ValueError):   # fecha imposible
            sn.ultima_emision('var fichero = "nowcasting_20261399-2599_forecast_20261399-2699_web";')

    def test_ficheros(self):
        self.assertEqual(sn.ficheros(T), {0: F0, 60: F60, 120: F120})
        # la misma emisión en UTC da los mismos nombres (van en hora de Lima)
        self.assertEqual(sn.ficheros(T.astimezone(UTC)), {0: F0, 60: F60, 120: F120})

    def test_ficheros_cruzan_la_medianoche(self):
        f = sn.ficheros(datetime(2026, 9, 22, 23, 10, tzinfo=HORA_PERU))
        self.assertEqual(f[0], "nowcasting_20260922-2310_analysis_20260922-2310_web")
        self.assertEqual(f[60], "nowcasting_20260922-2310_forecast_20260923-0010_web")
        self.assertEqual(f[120], "nowcasting_20260922-2310_forecast_20260923-0110_web")


class TestWfs(unittest.TestCase):
    def test_url_filtrada(self):
        url = sn.url_wfs(F60)
        self.assertTrue(url.startswith(sn.WFS + "?"))
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(q["version"], ["2.0.0"])
        self.assertEqual(q["request"], ["GetFeature"])
        self.assertEqual(q["typeNames"], ["g_nowcasting:view_nowcasting"])
        self.assertEqual(q["outputFormat"], ["application/json"])
        self.assertEqual(q["viewparams"], [f"fichero:{F60}"])
        self.assertEqual(q["CQL_FILTER"], ["nivel>0"])
        self.assertEqual(q["propertyName"], ["nivel,fecha1,fecha2,fichero,geom"])
        self.assertNotIn("count", q)
        self.assertNotIn("BBOX", urllib.parse.unquote(url).upper())

    def test_url_sin_filtro(self):
        url = sn.url_wfs(F60, filtrado=False)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(q["count"], ["1"])
        self.assertEqual(q["propertyName"], ["nivel,fecha1,fecha2,fichero"])   # sin geometría
        self.assertNotIn("CQL_FILTER", q)
        self.assertNotIn("BBOX", urllib.parse.unquote(url).upper())

    def test_url_rechaza_un_fichero_raro(self):
        for raro in (F60 + ";x:1", F60 + "\n", "otro", ""):
            with self.assertRaises(ValueError):
                sn.url_wfs(raro)

    def test_muestra_real(self):
        por_nivel, desde, hasta, descartados = sn.parse_features(WFS_2040, F60)
        self.assertEqual({n: len(g) for n, g in por_nivel.items()}, {1: 2, 2: 1, 3: 2})
        self.assertEqual(descartados, 1)   # el de nivel 0
        # fecha1 y fecha2 en UTC
        self.assertEqual((desde, hasta), (datetime(2026, 9, 23, 1, 40, tzinfo=UTC),
                                          datetime(2026, 9, 23, 2, 40, tzinfo=UTC)))
        self.assertEqual(desde.utcoffset(), timedelta(0))

    def test_fechas_con_otra_zona_se_pasan_a_utc(self):
        fc = _coleccion(_elemento(fecha1="2026-09-22T20:40:00-05:00", fecha2="2026-09-22T21:40:00-05:00"))
        _, desde, hasta, _ = sn.parse_features(fc, F60)
        self.assertEqual((desde, hasta), (datetime(2026, 9, 23, 1, 40, tzinfo=UTC),
                                          datetime(2026, 9, 23, 2, 40, tzinfo=UTC)))

    def test_descarta_nivel_0_otro_fichero_y_geometrias_invalidas(self):
        punto = _elemento()
        punto["geometry"] = {"type": "Point", "coordinates": [-78.5, -7.2]}
        abierto = _elemento()
        abierto["geometry"]["coordinates"][0].pop()          # anillo sin cerrar
        nan = _elemento()
        nan["geometry"]["coordinates"][0][1] = [float("nan"), -7.2]
        fc = _coleccion(_elemento(nivel=0), _elemento(nivel=4), _elemento(nivel=True),
                        _elemento(fichero="nowcasting_20260922-2030_forecast_20260922-2130_web"),
                        _elemento(nivel="2"), punto, abierto, nan, "no es un elemento")
        por_nivel, _, _, descartados = sn.parse_features(fc, F60)
        self.assertEqual({n: len(g) for n, g in por_nivel.items()}, {2: 1})
        self.assertEqual(descartados, 8)

    def test_ejes_invertidos(self):
        fc = copy.deepcopy(WFS_2040)
        for f in fc["features"]:
            f["geometry"]["coordinates"] = [[[y, x] for x, y in anillo] for anillo in f["geometry"]["coordinates"]]
        with self.assertRaisesRegex(ValueError, "orden de ejes inesperado"):
            sn.parse_features(fc, F60)

    def test_no_es_una_featurecollection(self):
        for fc in ({"type": "Feature"}, {"type": "FeatureCollection", "features": None}, [], None):
            with self.assertRaises(ValueError):
                sn.parse_features(fc, F60)

    def test_demasiados_elementos(self):
        with mock.patch.object(sn, "MAX_FEATURES", 5):
            with self.assertRaises(ValueError):
                sn.parse_features(WFS_2040, F60)


class TestProducto(unittest.TestCase):
    """producto() con la GeoServer simulada: respuestas en orden (filtrada y, si hace falta, sin filtro)."""

    def pedir(self, *respuestas, h=60):
        self.urls = []
        self.pausas = 0
        cola = list(respuestas)

        def falso_get_bytes(url, max_bytes=None):
            self.urls.append(url)
            return cola.pop(0)

        def falsa_pausa():
            self.pausas += 1

        with mock.patch.object(_http, "get_bytes", falso_get_bytes), mock.patch.object(sn, "pausa", falsa_pausa):
            return sn.producto(T, h)

    def test_muestra_real(self):
        p = self.pedir(_bytes(WFS_2040))
        self.assertEqual((p.horizonte, p.fichero, p.emision), (60, F60, T))
        self.assertEqual((p.desde, p.hasta), (datetime(2026, 9, 23, 1, 40, tzinfo=UTC),
                                              datetime(2026, 9, 23, 2, 40, tzinfo=UTC)))
        # solo cuentan (y se guardan) las que tocan el recuadro del Perú: una por nivel
        self.assertEqual(p.manchas, 3)
        self.assertEqual({n: len(g) for n, g in p.por_nivel.items()}, {1: 1, 2: 1, 3: 1})
        self.assertEqual(p.descartados, 1)
        self.assertEqual(len(self.urls), 1)      # con manchas no hace falta la consulta sin filtro
        self.assertEqual(self.pausas, 0)

    def test_xml_de_excepcion_con_http_200_es_falla(self):
        with self.assertRaises(ValueError) as cm:
            self.pedir(XML_EXCEPCION)
        self.assertNotIsInstance(cm.exception, sn.ProductoNoPublicado)

    def test_vacio_con_filtro_y_sin_filtro_no_esta_publicado(self):
        with self.assertRaises(sn.ProductoNoPublicado):
            self.pedir(_bytes(_coleccion()), _bytes(_coleccion()))
        self.assertEqual(len(self.urls), 2)
        self.assertIn("count=1", self.urls[1])
        self.assertEqual(self.pausas, 1)         # en serie y con pausa

    def test_sin_filtro_de_otro_fichero_no_esta_publicado(self):
        otro = _elemento(nivel=0, fichero="nowcasting_20260922-2030_forecast_20260922-2130_web")
        otro["geometry"] = None
        with self.assertRaises(sn.ProductoNoPublicado):
            self.pedir(_bytes(_coleccion()), _bytes(_coleccion(otro)))

    def test_vacio_con_algo_sin_filtro_es_un_producto_sin_manchas(self):
        cero = _elemento(nivel=0, fecha1="2026-09-23T01:40:00Z", fecha2="2026-09-23T02:40:00Z")
        cero["geometry"] = None                  # la consulta sin filtro no pide la geometría
        p = self.pedir(_bytes(_coleccion()), _bytes(_coleccion(cero)))
        self.assertEqual((p.manchas, p.por_nivel), (0, {}))
        self.assertEqual((p.desde, p.hasta), (datetime(2026, 9, 23, 1, 40, tzinfo=UTC),
                                              datetime(2026, 9, 23, 2, 40, tzinfo=UTC)))

    def test_solo_fuera_del_peru_es_un_producto_sin_manchas(self):
        colombia = _elemento(nivel=3, x=-74.0, y=3.0)
        p = self.pedir(_bytes(_coleccion(colombia)))
        self.assertEqual((p.manchas, p.por_nivel), (0, {}))
        self.assertEqual(len(self.urls), 1)

    def test_sin_fechas(self):
        sin = _elemento(fecha1=None, fecha2=None)
        p = self.pedir(_bytes(_coleccion(sin)))  # +1 h: [T, T+60]
        self.assertEqual((p.desde, p.hasta), (T.astimezone(UTC), T.astimezone(UTC) + timedelta(minutes=60)))
        for h in (0, 120):
            with self.assertRaises(ValueError):
                self.pedir(_bytes(_coleccion(_elemento(fichero=sn.ficheros(T)[h], fecha2=None))), h=h)

    def test_fechas_al_reves(self):
        with self.assertRaises(ValueError):
            self.pedir(_bytes(_coleccion(_elemento(fecha1="2026-09-23T02:40:00Z", fecha2="2026-09-23T01:40:00Z"))))


# ---------------------------------------------------------------------------------------
# Tarea
# ---------------------------------------------------------------------------------------
class _Cursor:
    def __init__(self, conn):
        self.conn, self.ultima, self.fila = conn, None, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.registro.append((sql, params))
        self.ultima, self.fila = sql, None
        if sql == tarea.SQL_CANDADO:
            self.conn.productos.update(self.conn.carrera)   # otra corrida escribió entretanto
        elif sql == tarea.SQL_PRODUCTO:
            previo = self.conn.productos.get(params["h"])
            if previo is None or params["emision"] >= previo:   # la guarda del upsert
                self.conn.productos[params["h"]] = params["emision"]
                self.fila = (params["h"],)

    def fetchone(self):
        if self.ultima == tarea.SQL_HAY_TABLA:
            return (self.conn.migrada,)
        assert self.ultima == tarea.SQL_PRODUCTO, self.ultima
        return self.fila

    def fetchall(self):
        assert self.ultima == tarea.SQL_PREVIOS, self.ultima
        return list(self.conn.productos.items())


class _Conexion:
    """
    Anota cada sentencia. productos: {horizonte: emisión} de nowcast_producto. carrera: lo que
    otra corrida guardó entre la lectura de los previos y el candado. migrada: si están las tablas.
    """

    def __init__(self, productos=None, carrera=None, migrada=True):
        self.productos, self.carrera, self.migrada = dict(productos or {}), carrera or {}, migrada
        self.registro = []

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]

    def sentencias(self):
        return [s for s, _ in self.registro]


def _elementos_de(fichero: str, h: int) -> list[dict]:
    """Los 6 elementos de la muestra, como si fueran del fichero del horizonte h."""
    t = T.astimezone(UTC)
    fecha1, fecha2 = (t, t) if h == 0 else (t, t + timedelta(minutes=h))
    out = copy.deepcopy(WFS_2040["features"])
    for f in out:
        f["properties"].update(fichero=fichero, fecha1=fecha1.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               fecha2=fecha2.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return out


class _GeoServer:
    """
    El WFS simulado: responde por el fichero de viewparams y aplica CQL_FILTER=nivel>0, count y
    propertyName como la GeoServer. publicados: {fichero: elementos}; errores: ficheros que
    responden el XML de excepción (con HTTP 200).
    """

    def __init__(self, publicados, errores=()):
        self.publicados, self.errores, self.pedidos = publicados, set(errores), []

    def get_bytes(self, url, max_bytes=None):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        fichero = q["viewparams"][0].removeprefix("fichero:")
        self.pedidos.append((fichero, "CQL_FILTER" in q))
        if fichero in self.errores:
            return XML_EXCEPCION
        feats = self.publicados.get(fichero, [])
        if q.get("CQL_FILTER") == ["nivel>0"]:
            feats = [f for f in feats if f["properties"]["nivel"] > 0]
        if "count" in q:
            feats = feats[:int(q["count"][0])]
        campos = q["propertyName"][0].split(",")
        feats = [{**f, "geometry": f["geometry"] if "geom" in campos else None,
                  "properties": {k: v for k, v in f["properties"].items() if k in campos}} for f in feats]
        return _bytes(_coleccion(*feats))


TODOS = {F0: _elementos_de(F0, 0), F60: _elementos_de(F60, 60), F120: _elementos_de(F120, 120)}


class TestTarea(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.ERROR)   # la tarea avisa de las fallas simuladas
        self.addCleanup(logging.disable, logging.NOTSET)

    def correr(self, conn=None, visor=T, error_visor=None, publicados=None, errores=(), ahora=AHORA):
        conn = conn or _Conexion()
        self.geoserver = _GeoServer(TODOS if publicados is None else publicados, errores)
        self.pausas = 0

        @contextmanager
        def falso_conectar():
            yield conn

        def falso_visor():
            if error_visor:
                raise error_visor
            return visor

        def falsa_pausa():
            self.pausas += 1

        self.excepcion = None
        with mock.patch.object(tarea, "conectar", falso_conectar), \
             mock.patch.object(sn, "emision_visor", falso_visor), \
             mock.patch.object(sn, "pausa", falsa_pausa), \
             mock.patch.object(_http, "get_bytes", self.geoserver.get_bytes):
            try:
                devuelto = tarea.actualizar(ahora)
            except Exception as e:
                self.excepcion, devuelto = e, None
        [(servicio, datos)] = conn.params(SQL_LATIDO)   # el latido se escribe siempre
        self.assertEqual(servicio, "nowcast")
        resumen = json.loads(datos)
        if devuelto is not None:
            self.assertEqual(resumen, devuelto)
        return conn, resumen

    def escritura(self, conn):
        """Sentencias de la transacción de escritura (después de leer los previos)."""
        s = conn.sentencias()
        self.assertEqual(s[:2], [tarea.SQL_HAY_TABLA, tarea.SQL_PREVIOS])
        self.assertEqual(s[2], tarea.SQL_CANDADO)   # el candado va primero y una sola vez
        self.assertEqual(s.count(tarea.SQL_CANDADO), 1)
        self.assertEqual(s[-1], SQL_LATIDO)
        return s[2:]

    def test_corrida_normal(self):
        conn, resumen = self.correr()
        self.assertIsNone(self.excepcion)
        self.assertEqual(resumen, {
            "emision": "2026-09-22T20:40:00-05:00", "edad_min": 8, "bajados": [60, 120, 0], "reusados": [],
            "manchas": {"60": 3, "120": 3, "0": 3}, "retraso_min": 8, "detenido": False,
            "fallas": [], "avisos": [],
        })
        # en serie, el +1 h primero, un pedido por horizonte (hay manchas) y pausas entre ellos
        self.assertEqual(self.geoserver.pedidos, [(F60, True), (F120, True), (F0, True)])
        self.assertEqual(self.pausas, 2)
        s = self.escritura(conn)
        self.assertEqual(s[1:6], [tarea.SQL_PRODUCTO, tarea.SQL_BORRAR_MANCHAS] + [tarea.SQL_MANCHA] * 3)
        productos = conn.params(tarea.SQL_PRODUCTO)
        self.assertEqual([p["h"] for p in productos], [60, 120, 0])
        p60 = productos[0]
        self.assertEqual((p60["fichero"], p60["emision"], p60["manchas"]), (F60, T, 3))
        self.assertEqual((p60["desde"], p60["hasta"]), (datetime(2026, 9, 23, 1, 40, tzinfo=UTC),
                                                        datetime(2026, 9, 23, 2, 40, tzinfo=UTC)))
        self.assertEqual(conn.params(tarea.SQL_BORRAR_MANCHAS), [(60,), (120,), (0,)])
        manchas = conn.params(tarea.SQL_MANCHA)
        self.assertEqual([(m["h"], m["nivel"]) for m in manchas],
                         [(60, 1), (60, 2), (60, 3), (120, 1), (120, 2), (120, 3), (0, 1), (0, 2), (0, 3)])
        self.assertEqual(manchas[0]["tolerancia"], tarea.TOLERANCIA_GRADOS)
        [geom] = json.loads(manchas[0]["geometrias"])     # la de nivel 1 dentro del Perú (no la del Pacífico)
        self.assertEqual(geom["type"], "Polygon")
        self.assertTrue(-81.4 <= geom["coordinates"][0][0][0] <= -68.6)

    def test_emision_igual_no_pide_el_wfs(self):
        conn = _Conexion(productos={0: T, 60: T, 120: T})
        conn, resumen = self.correr(conn)
        self.assertIsNone(self.excepcion)
        self.assertEqual(self.geoserver.pedidos, [])
        self.assertEqual((resumen["bajados"], resumen["reusados"], resumen["manchas"]), ([], [60, 120, 0], {}))
        self.assertIsNone(resumen["retraso_min"])
        self.assertEqual(self.escritura(conn), [tarea.SQL_CANDADO, SQL_LATIDO])

    def test_solo_se_baja_lo_que_falta(self):
        conn = _Conexion(productos={60: T, 120: T - timedelta(minutes=10)})
        conn, resumen = self.correr(conn)
        self.assertEqual(self.geoserver.pedidos, [(F120, True), (F0, True)])
        self.assertEqual((resumen["bajados"], resumen["reusados"]), ([120, 0], [60]))
        self.assertEqual(self.pausas, 1)

    def test_si_falla_el_mas_2h_su_fila_no_se_toca(self):
        conn, resumen = self.correr(errores={F120})
        self.assertIsNone(self.excepcion)        # un horizonte caído no tumba la tarea
        self.assertEqual(resumen["fallas"], ["h120"])
        self.assertEqual(len(resumen["avisos"]), 1)
        self.assertTrue(resumen["avisos"][0].startswith("h120: ValueError: El WFS del nowcasting no devolvió GeoJSON"))
        self.assertEqual((resumen["bajados"], resumen["reusados"]), ([60, 0], []))
        self.assertEqual([p["h"] for p in conn.params(tarea.SQL_PRODUCTO)], [60, 0])
        self.assertEqual(conn.params(tarea.SQL_BORRAR_MANCHAS), [(60,), (0,)])
        self.assertNotIn(120, [m["h"] for m in conn.params(tarea.SQL_MANCHA)])

    def test_producto_no_publicado(self):
        conn, resumen = self.correr(publicados={F60: TODOS[F60], F120: TODOS[F120]})
        self.assertEqual(resumen["fallas"], ["h0"])
        self.assertEqual(resumen["avisos"], [f"h0: ProductoNoPublicado: SENAMHI aún no publica {F0}"])
        self.assertEqual(self.geoserver.pedidos[-2:], [(F0, True), (F0, False)])
        self.assertEqual([p["h"] for p in conn.params(tarea.SQL_PRODUCTO)], [60, 120])

    def test_sin_manchas_se_guarda_y_borra_las_viejas(self):
        solo_cero = [f for f in TODOS[F60] if f["properties"]["nivel"] == 0]
        conn = _Conexion(productos={0: T, 120: T, 60: T - timedelta(minutes=10)})
        conn, resumen = self.correr(conn, publicados={F60: solo_cero})
        self.assertEqual(self.geoserver.pedidos, [(F60, True), (F60, False)])
        self.assertEqual((resumen["bajados"], resumen["manchas"]), ([60], {"60": 0}))
        [p] = conn.params(tarea.SQL_PRODUCTO)
        self.assertEqual((p["h"], p["manchas"]), (60, 0))
        self.assertEqual(conn.params(tarea.SQL_BORRAR_MANCHAS), [(60,)])   # las de la emisión anterior
        self.assertEqual(conn.params(tarea.SQL_MANCHA), [])

    def test_un_producto_mas_viejo_no_pisa(self):
        # Al leer los previos, el +1 h guardado era de las 20:30; al escribir, otra corrida ya
        # guardó uno de las 20:50: el upsert no devuelve fila y sus manchas no se tocan.
        conn = _Conexion(productos={0: T, 120: T, 60: T - timedelta(minutes=10)},
                         carrera={60: T + timedelta(minutes=10)})
        conn, resumen = self.correr(conn)
        self.assertIsNone(self.excepcion)
        self.assertEqual(self.geoserver.pedidos, [(F60, True)])
        self.assertEqual(len(conn.params(tarea.SQL_PRODUCTO)), 1)
        self.assertEqual(conn.params(tarea.SQL_BORRAR_MANCHAS), [])
        self.assertEqual(conn.params(tarea.SQL_MANCHA), [])
        self.assertEqual(conn.productos[60], T + timedelta(minutes=10))
        self.assertEqual((resumen["bajados"], sorted(resumen["reusados"])), ([], [0, 60, 120]))
        self.assertEqual(resumen["avisos"], [f"h60: ya hay guardada una emisión más nueva que {F60}; no se pisa"])

    def test_emision_guardada_mas_nueva_que_el_visor_no_se_baja(self):
        conn = _Conexion(productos={0: T, 120: T, 60: T + timedelta(minutes=10)})
        conn, resumen = self.correr(conn)
        self.assertEqual(self.geoserver.pedidos, [])
        self.assertEqual(resumen["reusados"], [60, 120, 0])
        self.assertEqual(resumen["avisos"], ["h60: ya hay guardada una emisión más nueva (20:50) que la del visor "
                                             "(20:40); no se baja"])

    def test_visor_caido(self):
        conn, resumen = self.correr(error_visor=OSError("timed out"))
        self.assertIsInstance(self.excepcion, RuntimeError)
        self.assertEqual(self.geoserver.pedidos, [])
        self.assertEqual(self.escritura(conn), [tarea.SQL_CANDADO, SQL_LATIDO])   # solo el latido
        self.assertEqual(resumen, {"emision": None, "edad_min": None, "bajados": [], "reusados": [], "manchas": {},
                                   "retraso_min": None, "detenido": None, "fallas": ["visor"],
                                   "avisos": ["visor: OSError: timed out"]})

    def test_visor_con_una_emision_en_el_futuro(self):
        conn, resumen = self.correr(visor=AHORA + timedelta(minutes=10))
        self.assertIsInstance(self.excepcion, RuntimeError)
        self.assertEqual(self.geoserver.pedidos, [])
        self.assertEqual(resumen["fallas"], ["visor"])
        self.assertIn("posterior a ahora", resumen["avisos"][0])
        # 4 min adelantado se acepta (relojes)
        adelantada = AHORA + timedelta(minutes=4)
        _, resumen = self.correr(_Conexion(productos={0: adelantada, 60: adelantada, 120: adelantada}),
                                 visor=adelantada)
        self.assertIsNone(self.excepcion)
        self.assertEqual((resumen["fallas"], resumen["edad_min"]), ([], -4))

    def test_detenido(self):
        # 23:25 del 22-09: la última emisión sigue siendo la de las 20:40 (ya guardada)
        conn = _Conexion(productos={0: T, 60: T, 120: T})
        _, resumen = self.correr(conn, ahora=datetime(2026, 9, 23, 4, 25, tzinfo=UTC))
        self.assertIsNone(self.excepcion)        # no es falla: el visor respondió
        self.assertEqual((resumen["edad_min"], resumen["detenido"], resumen["fallas"]), (165, True, []))
        self.assertEqual(resumen["avisos"], ["SENAMHI no publica el nowcasting desde las 20:40"])
        # pasada la medianoche se dice el día
        _, resumen = self.correr(_Conexion(productos={0: T, 60: T, 120: T}),
                                 ahora=datetime(2026, 9, 23, 5, 10, tzinfo=UTC))
        self.assertEqual(resumen["avisos"], ["SENAMHI no publica el nowcasting desde las 20:40 del 22-09"])
        # 30 min justos todavía no
        _, resumen = self.correr(_Conexion(productos={0: T, 60: T, 120: T}), ahora=T + timedelta(minutes=30))
        self.assertEqual((resumen["detenido"], resumen["avisos"]), (False, []))

    def test_sin_migracion(self):
        conn = _Conexion(migrada=False)
        conn, resumen = self.correr(conn)
        self.assertIsNone(self.excepcion)
        self.assertEqual(conn.sentencias(), [tarea.SQL_HAY_TABLA, SQL_LATIDO])
        self.assertEqual(self.geoserver.pedidos, [])
        self.assertEqual(resumen["fallas"], ["migracion"])
        self.assertEqual(resumen["avisos"], [tarea.AVISO_SIN_TABLA])

    def test_sin_tiempo_no_se_piden_mas_horizontes(self):
        with mock.patch.object(tarea, "PLAZO_S", -1):
            conn, resumen = self.correr()
        self.assertIsNone(self.excepcion)
        self.assertEqual(self.geoserver.pedidos, [])
        self.assertEqual(resumen["fallas"], ["h60", "h120", "h0"])
        self.assertEqual(conn.params(tarea.SQL_PRODUCTO), [])


class TestSql(unittest.TestCase):
    def test_upsert_no_pisa_una_emision_mas_nueva(self):
        sql = " ".join(tarea.SQL_PRODUCTO.split())
        self.assertIn("on conflict (horizonte_min) do update set", sql)
        self.assertIn("where excluded.emision >= nowcast_producto.emision returning horizonte_min", sql)

    def test_manchas_recortadas_al_peru(self):
        sql = " ".join(tarea.SQL_MANCHA.split())
        self.assertIn("st_intersects(p.geom, st_makeenvelope(-81.4, -18.4, -68.6, 0.1, 4326))", sql)
        self.assertIn("st_simplifypreservetopology(st_union(p.geom), %(tolerancia)s::float8)", sql)
        self.assertIn("where g.geom is not null and not st_isempty(g.geom)", sql)
        self.assertEqual(tarea.SQL_CANDADO, "select pg_advisory_xact_lock(hashtext('nowcast'))")


if __name__ == "__main__":
    unittest.main()
