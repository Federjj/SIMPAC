"""
Zonas estimadas con el relieve (backend/mapas/zonas_relieve.py) y su cargador
(backend/mapas/cargar_cauces_zonas.py). Sin red ni psycopg.

Las pruebas del cálculo (HAND sobre un relieve sintético chico, conexión al río, umbrales, polígonos,
georreferencia de la tesela) necesitan numpy, scipy, shapely y pyproj (backend/requirements-relieve.txt):
si falta alguna se saltan. Las del cargador son solo librería estándar y corren siempre.
"""
import io
import json
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from backend.mapas import cargar_cauces_zonas as cz

try:
    import numpy as np
    import pyproj  # noqa: F401 - solo para saber si está
    import scipy  # noqa: F401
    import shapely  # noqa: F401
    from backend.mapas import zonas_relieve as zr
    FALTA = None
except ImportError as e:   # numpy, scipy, shapely o pyproj: el módulo los importa al usarlos
    np = None
    zr = None
    FALTA = str(e)


# =============================================================================== cálculo (HAND)
@unittest.skipUnless(FALTA is None, f"faltan librerías del relieve: {FALTA}")
class TestTeselas(unittest.TestCase):
    def test_nombre_de_la_tesela(self):
        # la esquina es floor(lat), floor(lon): Cajamarca (-7.15, -78.5) cae en S08_W079; Tumbes (-3.57, -80.45) en S04_W081
        self.assertEqual(zr.nombre_tesela(-7.15, -78.5), "Copernicus_DSM_COG_10_S08_00_W079_00_DEM")
        self.assertEqual(zr.nombre_tesela(-6.5, -78.5), "Copernicus_DSM_COG_10_S07_00_W079_00_DEM")
        self.assertEqual(zr.nombre_tesela(-3.57, -80.45), "Copernicus_DSM_COG_10_S04_00_W081_00_DEM")
        self.assertEqual(zr.nombre_tesela(0.2, -75.2), "Copernicus_DSM_COG_10_N00_00_W076_00_DEM")
        self.assertEqual(zr.teselas_para(-7.2, -6.9, -79.1, -78.9),
                         ["Copernicus_DSM_COG_10_S08_00_W080_00_DEM", "Copernicus_DSM_COG_10_S08_00_W079_00_DEM",
                          "Copernicus_DSM_COG_10_S07_00_W080_00_DEM", "Copernicus_DSM_COG_10_S07_00_W079_00_DEM"])
        self.assertTrue(zr.URL_TESELA.format(n="X").startswith("https://copernicus-dem-30m.s3.amazonaws.com/X/X.tif"))

    def test_georreferencia_punto_y_area(self):
        datos = np.arange(12, dtype=np.float32).reshape(3, 4)
        # etiquetas como las de la tesela real S07_W079: tiepoint (0,0) -> (-79, -6), 1 arcosegundo, PixelIsPoint (clave 1025 = 2)
        claves = (1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 2, 2048, 0, 1, 4326)
        paso = 1 / 3600
        t = zr.tesela_desde_etiquetas(datos, (0, 0, 0, -79.0, -6.0, 0), (paso, paso, 0), claves)
        self.assertEqual((t.lon0, t.lat0, t.paso), (-79.0, -6.0, paso))
        # PixelIsArea: el centro queda medio píxel adentro
        claves_area = (1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 1, 2048, 0, 1, 4326)
        ta = zr.tesela_desde_etiquetas(datos, (0, 0, 0, -79.0, -6.0, 0), (paso, paso, 0), claves_area)
        self.assertAlmostEqual(ta.lon0, -79.0 + paso / 2)
        self.assertAlmostEqual(ta.lat0, -6.0 - paso / 2)
        with self.assertRaises(ValueError):
            zr.tesela_desde_etiquetas(datos, (0, 0, 0, -79.0, -6.0, 0), (paso, paso, 0), (1, 1, 0, 1, 2048, 0, 1, 32718))

    def test_muestreo_bilineal_y_fuera_de_tesela(self):
        paso = 0.01
        datos = np.array([[0, 10, 20], [100, 110, 120], [200, 210, 220]], dtype=np.float32)
        t = zr.Tesela(datos=datos, lon0=-79.0, lat0=-6.0, paso=paso)
        lats = np.array([-6.0, -6.01, -6.005, -6.5])
        lons = np.array([-79.0, -78.98, -78.995, -79.0])
        v = zr.muestrear([t], lats, lons)
        self.assertAlmostEqual(float(v[0]), 0.0)
        self.assertAlmostEqual(float(v[1]), 120.0)
        self.assertAlmostEqual(float(v[2]), 55.0, places=4)   # entre las cuatro celdas centrales
        self.assertTrue(np.isnan(v[3]))                        # fuera de la tesela


def _valle(ny=40, nx=61, pendiente_rio=0.001, pendiente_ladera=0.5, celda=30.0):
    """
    Relieve sintético: un valle en V con el río por la columna del medio (nx // 2), que baja de norte a
    sur, y laderas que suben pendiente_ladera metros por cada metro de distancia al río. HAND esperado
    en cada celda = distancia al río * pendiente_ladera (las laderas drenan derecho al río).
    """
    filas, cols = np.mgrid[0:ny, 0:nx]
    centro = nx // 2
    cota_rio = 100.0 - filas * celda * pendiente_rio
    dem = cota_rio + np.abs(cols - centro) * celda * pendiente_ladera
    rio = cols == centro
    orden = [(f, centro) for f in range(ny)]
    return dem.astype(np.float64), rio, orden


@unittest.skipUnless(FALTA is None, f"faltan librerías del relieve: {FALTA}")
class TestHand(unittest.TestCase):
    def _hand(self, dem, rio, orden, valido=None):
        valido = np.ones(dem.shape, dtype=bool) if valido is None else valido
        cota = zr.cota_del_rio(dem, rio, orden)
        quemado = dem.copy()
        quemado[rio] = cota[rio] - zr.QUEMA_M
        borde = valido & ~zr._erosionar(valido)
        relleno = zr.rellenar(quemado, rio | borde, valido)
        destino = zr.direccion_d8(relleno, 30.0)
        drena = zr.drenaje(destino, rio)
        return cota, relleno, destino, drena, zr.hand(dem, cota, drena)

    def test_hand_en_un_valle_en_v(self):
        dem, rio, orden = _valle()
        cota, relleno, destino, drena, h = self._hand(dem, rio, orden)
        # la cota del río es la del propio cauce (el mínimo 3x3 toma la celda de aguas abajo, 3 cm más baja) y baja aguas abajo
        self.assertTrue(np.allclose(cota[rio], dem[rio], atol=0.05))
        self.assertTrue(np.all(np.diff(cota[:, 30]) <= 0))
        # todas las celdas drenan a alguna celda del río y la celda del río a sí misma
        self.assertTrue((drena >= 0).all())
        self.assertEqual(int(drena[10, 30]), 10 * 61 + 30)
        # HAND = altura sobre el río: 0 en el cauce, 15 m a una celda (0.5 m/m * 30 m), 150 m a diez celdas
        self.assertAlmostEqual(float(h[10, 30]), 0.0, delta=0.05)
        self.assertAlmostEqual(float(h[10, 31]), 15.0, delta=0.05)
        self.assertAlmostEqual(float(h[25, 20]), 150.0, delta=0.2)
        # el relleno no toca un relieve sin depresiones (salvo el epsilon)
        self.assertTrue(np.allclose(relleno[~rio], dem[~rio], atol=0.1))

    def test_depresion_rellena_y_hand_de_la_celda_baja(self):
        dem, rio, orden = _valle()
        dem[20, 40] -= 30.0           # un hoyo de 30 m en la ladera: sin relleno sería un sumidero
        cota, relleno, destino, drena, h = self._hand(dem, rio, orden)
        # se rellena hasta su punto de desagüe más bajo: la celda vecina del lado del río (15 m más abajo que el borde)
        self.assertAlmostEqual(float(relleno[20, 40]), float(dem[20, 39]), delta=0.1)
        self.assertTrue(rio.ravel()[int(drena[20, 40])])                           # igual drena al río
        self.assertAlmostEqual(float(h[20, 40]), 10 * 15.0 - 30.0, delta=0.2)    # su altura real sobre el río

    def test_puente_sobre_el_rio_no_sube_la_cota(self):
        dem, rio, orden = _valle()
        dem[20, 30] += 12.0            # un puente (modelo de superficie) sobre el cauce
        cota = zr.cota_del_rio(dem, rio, orden)
        self.assertLess(float(cota[20, 30]), float(dem[20, 30]) - 10.0)
        self.assertTrue(np.all(np.diff(cota[:, 30]) <= 0))   # sigue monótona aguas abajo

    def test_zona_por_umbral_y_conexion_al_rio(self):
        # valle ancho y bajo: laderas de 0,9 m por celda; a 2 m llegan 2 celdas por lado (1,8 m), a 3 m llegan 3 (2,7 m)
        dem, rio, orden = _valle(pendiente_ladera=0.9 / 30.0)
        # una hondonada baja (HAND < 2) separada del río por una loma de 10 m: no debe entrar
        dem[15:25, 50:56] = dem[15:25, 30:31] + 0.5
        dem[15:25, 49] += 10.0
        dem[14, 49:57] += 10.0
        dem[25, 49:57] += 10.0
        dem[15:25, 56] += 10.0
        cota, relleno, destino, drena, h = self._hand(dem, rio, orden)
        from scipy.ndimage import distance_transform_edt
        dist = distance_transform_edt(~rio) * 30.0
        valido = np.ones(dem.shape, dtype=bool)
        z2 = zr.zona(h, dist, rio, 2.0, valido)
        z3 = zr.zona(h, dist, rio, 3.0, valido)
        self.assertTrue(z2[20, 30] and z2[20, 32] and not z2[20, 33])
        self.assertTrue(z3[20, 33] and not z3[20, 34])
        self.assertTrue((z3 | ~z2).all())                      # la de 3 m contiene a la de 2 m
        self.assertFalse(z2[20, 52])                           # la hondonada aislada queda fuera
        self.assertFalse(z3[20, 52])
        # lejos del río (más de DIST_MAX_M) no hay zona aunque sea bajo
        dem2 = np.full((20, 120), 100.0)
        rio2 = np.zeros_like(dem2, dtype=bool)
        rio2[:, 0] = True
        h2 = np.zeros_like(dem2)
        dist2 = distance_transform_edt(~rio2) * 30.0
        zl = zr.zona(h2, dist2, rio2, 2.0, np.ones_like(rio2))
        self.assertTrue(zl[10, 40] and not zl[10, 60])

    def test_poligonos_y_control_de_calidad(self):
        import shapely
        malla = zr.Malla(epsg=32717, x0=600000.0, y1=9200000.0, nx=20, ny=10)
        m = np.zeros((10, 20), dtype=bool)
        m[3:7, 2:12] = True
        poli = zr.poligonizar(m, malla, suavizar_m=0, simplificar_m=1.0)
        self.assertEqual(poli.geom_type, "MultiPolygon")
        self.assertAlmostEqual(poli.area, 4 * 10 * 900.0, delta=1.0)
        suave = zr.poligonizar(m, malla)
        self.assertAlmostEqual(suave.area, 4 * 10 * 900.0, delta=0.08 * 40 * 900)   # las esquinas se redondean
        wgs = zr.a_wgs84(suave, 32717)
        x, y = wgs.geoms[0].exterior.coords[0]
        self.assertTrue(-82 < x < -68 and -19 < y < 1)
        self.assertEqual(round(x, 5), x)
        self.assertEqual(zr.poligonizar(np.zeros((10, 20), dtype=bool), malla).is_empty, True)
        # control de calidad: zona grande = descartado; zona que no toca el cauce = descartado
        r = zr.Resultado(rio_ana="x", centro=(-7.0, -79.0), etiqueta="e", corredor_km2=100.0)
        r.zonas = [zr.ZonaCalculada("bajo_2m", 2, 2.0, 30.0, True, shapely.MultiPolygon()),
                   zr.ZonaCalculada("bajo_3m", 3, 3.0, 40.0, True, shapely.MultiPolygon())]
        self.assertIn("30%", zr.controlar(r).descartado)
        r.descartado, r.zonas[0].area_km2 = None, 10.0
        self.assertIsNone(zr.controlar(r).descartado)
        r.zonas[1].toca_cauce = False
        self.assertIn("no toca", zr.controlar(r).descartado)

    def test_tramo_util_centrado_y_encadenado(self):
        import shapely
        # dos piezas que no se tocan (hueco de 100 m): se encadenan; el tramo de 20 km se centra en el punto pedido
        a = [(0.0, 0.0), (10000.0, 0.0)]
        b = [(10100.0, 0.0), (40000.0, 0.0)]
        tramo, todo = zr.tramo_util([a, b], (25000.0, 500.0), 20000.0)
        self.assertAlmostEqual(tramo.length, 20000.0, delta=1.0)
        self.assertAlmostEqual(tramo.bounds[0], 15000.0, delta=1.0)
        self.assertAlmostEqual(tramo.bounds[2], 35000.0, delta=1.0)
        self.assertEqual(todo.geom_type, "MultiLineString")
        # centro cerca de un extremo: la ventana se corre para no acortar el tramo
        tramo2, _ = zr.tramo_util([a, b], (1000.0, 0.0), 20000.0)
        self.assertAlmostEqual(tramo2.length, 20000.0, delta=1.0)
        self.assertAlmostEqual(tramo2.bounds[0], 0.0, delta=1.0)
        # río más corto que el tramo: se usa entero
        tramo3, _ = zr.tramo_util([a], (5000.0, 0.0), 60000.0)
        self.assertAlmostEqual(tramo3.length, 10000.0, delta=1.0)
        # rasterizar una línea deja celdas conectadas (D8) y en orden
        malla = zr.Malla(epsg=32717, x0=0.0, y1=3000.0, nx=100, ny=100)
        mascara, orden = zr.rasterizar_lineas(shapely.LineString([(15, 2985), (2985, 15)]), malla)
        self.assertEqual(orden[0], (0, 0))
        self.assertEqual(orden[-1], (99, 99))
        self.assertTrue(all(max(abs(f2 - f1), abs(c2 - c1)) <= 1 for (f1, c1), (f2, c2) in zip(orden, orden[1:])))
        self.assertEqual(int(mascara.sum()), len(orden))

    def test_salida_geojson_y_metodo(self):
        import shapely
        r = zr.Resultado(rio_ana="rimac", centro=(-12.02, -76.93), etiqueta="la ciudad de Lima", tramo_km=60.0,
                         corredor_km2=300.0, teselas=["T"], segundos=12.0)
        g = shapely.MultiPolygon([shapely.box(-76.9, -12.0, -76.89, -11.99)])
        r.zonas = [zr.ZonaCalculada("bajo_2m", 2, 2.0, 1.5, True, g), zr.ZonaCalculada("bajo_3m", 3, 3.0, 2.5, True, g)]
        fc = zr.coleccion(r)
        p = fc["features"][0]["properties"]
        self.assertEqual(p["clave"], "rimac:relieve:2")
        self.assertEqual(p["subtipo"], "bajo_2m")
        self.assertTrue(p["metodo"].startswith("HAND sobre Copernicus GLO-30, umbral ~2 m / ~3 m, tramo de 60 km alrededor de la ciudad de Lima"))
        self.assertIn("Copernicus", p["atribucion"])
        self.assertIn("no es un mapa oficial", p["nota"])
        self.assertEqual(fc["features"][0]["geometry"]["type"], "MultiPolygon")
        # lo que escribe el pipeline lo acepta el cargador tal cual
        filas = cz.validar("rimac", fc)
        self.assertEqual([f["subtipo"] for f in filas], ["bajo_2m", "bajo_3m"])
        with tempfile.TemporaryDirectory() as d:
            zr.anotar_indice(Path(d), r)
            r2 = zr.Resultado(rio_ana="napo", centro=(0.0, 0.0), etiqueta="", descartado="selva baja")
            zr.anotar_indice(Path(d), r2)
            indice = json.loads((Path(d) / zr.INDICE).read_text(encoding="utf-8"))
            self.assertEqual(indice["rimac"]["estado"], "hecho")
            self.assertEqual(indice["napo"], indice["napo"] | {"estado": "descartado", "motivo": "selva baja"})


# =============================================================================== cargador (solo stdlib)
def _fc(rio="rimac", **cambios):
    anillo = [[-76.9, -12.0], [-76.89, -12.0], [-76.89, -11.99], [-76.9, -11.99], [-76.9, -12.0]]
    base = {"metodo": "HAND sobre Copernicus GLO-30, umbral ~2 m / ~3 m, tramo de 60 km alrededor de la ciudad de Lima",
            "fuente": "Estimación SIMPAC", "licencia": "Aviso Copernicus", "atribucion": "Copernicus; ANA",
            "fecha_fuente": "2026-10-20", "nota": "Estimación, no es un mapa oficial."}
    feats = []
    for n, subtipo, area in ((2, "bajo_2m", 1.5), (3, "bajo_3m", 2.5)):
        feats.append({"type": "Feature",
                      "properties": {**base, "clave": f"{rio}:relieve:{n}", "rio_ana": rio, "subtipo": subtipo, "area_km2": area},
                      "geometry": {"type": "MultiPolygon", "coordinates": [[anillo]]}})
    fc = {"type": "FeatureCollection", "rio_ana": rio, "tramo_km": 60, "descartado": None, "features": feats}
    fc.update(cambios)
    return fc


class TestValidarCargador(unittest.TestCase):
    def test_archivo_bueno(self):
        filas = cz.validar("rimac", _fc())
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0]["clave"], "rimac:relieve:2")
        self.assertEqual(json.loads(filas[0]["geom"])["type"], "MultiPolygon")
        self.assertEqual(cz.resumen("rimac", filas), "Río rimac: 2 zonas (bajo_2m 1.50 km2, bajo_3m 2.50 km2)")

    def test_poligono_suelto_se_envuelve(self):
        fc = _fc()
        fc["features"][0]["geometry"] = {"type": "Polygon", "coordinates": fc["features"][0]["geometry"]["coordinates"][0]}
        self.assertEqual(json.loads(cz.validar("rimac", fc)[0]["geom"])["type"], "MultiPolygon")

    def _rechaza(self, fc, texto, rio="rimac"):
        with self.assertRaises(cz.DatosInvalidos) as cm:
            cz.validar(rio, fc)
        self.assertIn(texto, str(cm.exception))

    def test_lo_que_rechaza(self):
        self._rechaza(_fc(), "no coincide", rio="chillon")
        self._rechaza(_fc(rio_ana="chillon"), "no coincide")
        self._rechaza(_fc(descartado="terreno muy plano"), "descartado")
        self._rechaza(_fc(features=[]), "sin zonas")
        self._rechaza(_fc(), "solo letras", rio="Rímac")
        fc = _fc()
        fc["features"][1]["properties"]["clave"] = "rimac:relieve:2"
        self._rechaza(fc, "repetida")
        fc = _fc()
        fc["features"][1]["properties"]["clave"] = "chillon:relieve:3"
        self._rechaza(fc, "debe ser 'rimac:relieve:<n>'")
        fc = _fc()
        fc["features"][1]["properties"]["subtipo"] = "bajo_1m"
        self._rechaza(fc, "subtipo")
        fc = _fc()
        fc["features"][1]["properties"]["subtipo"] = "bajo_2m"
        self._rechaza(fc, "repetido")
        fc = _fc()
        fc["features"][0]["properties"]["area_km2"] = 0
        self._rechaza(fc, "area_km2")
        fc = _fc()
        fc["features"][0]["properties"]["licencia"] = "  "
        self._rechaza(fc, "falta licencia")
        fc = _fc()
        fc["features"][0]["properties"]["fecha_fuente"] = "20/10/2026"
        self._rechaza(fc, "fecha_fuente")
        fc = _fc()
        fc["features"][0]["geometry"] = {"type": "LineString", "coordinates": [[-76.9, -12.0], [-76.8, -12.0]]}
        self._rechaza(fc, "Polygon o MultiPolygon")
        fc = _fc()
        fc["features"][0]["geometry"]["coordinates"][0][0][-1] = [-76.95, -12.0]   # anillo sin cerrar
        self._rechaza(fc, "anillo")
        fc = _fc()
        fc["features"][0]["geometry"]["coordinates"][0][0][1] = [-12.0, -76.89]    # lat/lon al revés: fuera del Perú
        self._rechaza(fc, "fuera del Perú")

    def test_leer_salta_los_archivos_auxiliares(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "rimac.geojson").write_text(json.dumps(_fc()), encoding="utf-8")
            (Path(d) / "_indice.json").write_text("{}", encoding="utf-8")
            (Path(d) / "_visor_rimac.html").write_text("<html>", encoding="utf-8")
            self.assertEqual(list(cz.leer(Path(d))), ["rimac"])


class CursorFalso:
    def __init__(self, hay_tabla=True, con_trazo=("rimac", "chillon")):
        self.hay_tabla, self.con_trazo, self.sql, self.rowcount = hay_tabla, con_trazo, [], 0
        self._res = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sql.append((sql.strip().split("\n")[0], params))
        if "to_regclass" in sql:
            self._res = [(self.hay_tabla,)]
        elif "from rio_cauce where" in sql:
            self._res = [(r,) for r in params[0] if r in self.con_trazo]
        elif sql.startswith("delete"):
            self.rowcount = 3
            self._res = []

    def executemany(self, sql, filas):
        self.sql.append(("executemany", len(filas)))

    def fetchone(self):
        return self._res[0]

    def fetchall(self):
        return self._res


class ConexionFalsa:
    def __init__(self, cursor):
        self._cur = cursor

    def cursor(self):
        return self._cur


class TestMain(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ruta = Path(self.dir.name)
        (self.ruta / "rimac.geojson").write_text(json.dumps(_fc()), encoding="utf-8")
        (self.ruta / "chillon.geojson").write_text(json.dumps(_fc("chillon")), encoding="utf-8")
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)
        self.dir.cleanup()

    def _main(self, *args, cursor=None):
        salida = io.StringIO()
        with mock.patch.object(cz, "conectar") as con:
            if cursor is not None:
                con.return_value.__enter__.return_value = ConexionFalsa(cursor)
            else:
                con.side_effect = AssertionError("la prueba en seco no debe conectar")
            with redirect_stdout(salida):
                codigo = cz.main(["--datos", str(self.ruta), *args])
        return codigo, salida.getvalue()

    def test_prueba_en_seco_no_conecta(self):
        codigo, texto = self._main()
        self.assertEqual(codigo, 0)
        self.assertIn("Río rimac: 2 zonas", texto)
        self.assertIn("2 ríos válidos, 4 zonas, 0 archivos con errores", texto)

    def test_un_archivo_malo_frena_todo(self):
        (self.ruta / "piura.geojson").write_text(json.dumps(_fc("piura", descartado="muy plano")), encoding="utf-8")
        codigo, texto = self._main()
        self.assertEqual(codigo, 1)
        self.assertIn("1 archivos con errores", texto)
        codigo, _ = self._main("--rio", "rimac")
        self.assertEqual(codigo, 0)
        self.assertEqual(self._main("--rio", "nada")[0], 1)
        self.assertEqual(self._main("--podar", "--rio", "rimac")[0], 1)

    def test_aplicar_upsert_sin_borrar(self):
        cur = CursorFalso()
        codigo, _ = self._main("--aplicar", cursor=cur)
        self.assertEqual(codigo, 0)
        self.assertIn(("executemany", 4), cur.sql)
        self.assertFalse(any(s[0].startswith("delete") for s in cur.sql))
        cur = CursorFalso()
        codigo, _ = self._main("--aplicar", "--podar", cursor=cur)
        self.assertEqual(codigo, 0)
        borrado = [s for s in cur.sql if s[0].startswith("delete")]
        self.assertEqual(len(borrado), 1)
        self.assertEqual(sorted(borrado[0][1][0]), ["chillon:relieve:2", "chillon:relieve:3", "rimac:relieve:2", "rimac:relieve:3"])

    def test_sin_tabla_o_sin_trazo(self):
        self.assertEqual(self._main("--aplicar", cursor=CursorFalso(hay_tabla=False))[0], 2)
        cur = CursorFalso(con_trazo=("rimac",))
        self.assertEqual(self._main("--aplicar", cursor=cur)[0], 1)   # chillon sin fila en rio_cauce: nada se escribe
        self.assertFalse(any(s[0] == "executemany" for s in cur.sql))

    def test_sin_dsn(self):
        salida = io.StringIO()
        with mock.patch.object(cz, "conectar", side_effect=RuntimeError("Falta SUPABASE_DB_URL")):
            with redirect_stdout(salida):
                self.assertEqual(cz.main(["--datos", str(self.ruta), "--aplicar"]), 2)


if __name__ == "__main__":
    unittest.main()
