"""
Cargador de los ríos vigilados (backend/mapas/cargar_rios.py): validación de los archivos de
backend/data/rios/mashcon/ (los reales, sin copiarlos) y lo que rechaza, y el --aplicar con la BD
simulada. Sin red ni psycopg: solo librería estándar.
"""
import copy
import json
import logging
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from backend import config
from backend.mapas import cargar_rios as cr

MASHCON = cr.DATOS / "mashcon"
DATOS = cr.leer(MASHCON)


def _datos():
    """Copia de los archivos reales para estropearla en cada prueba."""
    return copy.deepcopy(DATOS)


class TestValidar(unittest.TestCase):
    def test_archivos_reales(self):
        fila, zonas, incidentes = cr.validar(_datos(), "mashcon")
        self.assertEqual(len(zonas), 13)
        self.assertEqual(len(incidentes), 14)
        self.assertEqual(sum(1 for i in incidentes if i["lat"] is not None), 10)
        tipos = [z["tipo"] for z in zonas]
        self.assertEqual({t: tipos.count(t) for t in set(tipos)}, {"estimada": 3, "estudio": 4, "faja": 6})
        self.assertEqual(cr.resumen(fila, zonas, incidentes),
                         "Río mashcon: 13 zonas {estimada 3, estudio 4, faja 6}, 14 incidentes (10 en el mapa)")
        # la fila del río: estaciones para emparejar ANA y SENAMHI, y geometrías listas para PostGIS
        self.assertEqual((fila["id"], fila["departamento"], fila["estacion_ana"], fila["rio_ana"],
                          fila["estacion_senamhi"]), ("mashcon", "Cajamarca", "Mashcón", "Mashcon", "220213"))
        self.assertEqual((fila["centro_lat"], fila["centro_lon"], fila["zoom"]), (-7.14987, -78.49459, 13))
        self.assertEqual(json.loads(fila["cauce"])["type"], "MultiLineString")
        self.assertEqual(len(json.loads(fila["cauce"])["coordinates"]), 1)        # el tronco
        self.assertEqual(len(json.loads(fila["afluentes"])["coordinates"]), 3)    # Grande, Porcón, San Lucas
        self.assertEqual(json.loads(fila["guia_rotulo"])["type"], "LineString")
        self.assertEqual(json.loads(fila["cuenca"])["type"], "MultiPolygon")
        lugares = json.loads(fila["lugares_aviso"])
        self.assertEqual(len(lugares), 8)
        self.assertEqual([l["nombre"] for l in lugares if not l["mapa"]], ["Bellavista"])   # nombre ambiguo
        # todas las claves llevan el río delante; las fajas son líneas
        self.assertTrue(all(z["clave"].startswith("mashcon:") for z in zonas))
        self.assertTrue(all(json.loads(z["geom"])["type"] == "MultiLineString" for z in zonas if z["tipo"] == "faja"))
        # las 3 crecidas en rojo no se dibujan; el de 1974 solo tiene el distrito
        sin_punto = sorted(i["id"] for i in incidentes if i["lat"] is None)
        self.assertEqual(sin_punto, ["MAS-1974-02-22", "SEN-2021-0987", "SEN-2022-0593", "SEN-2026-1169"])

    def test_zona_sin_licencia(self):
        d = _datos()
        d["zonas.geojson"]["features"][0]["properties"]["licencia"] = ""
        with self.assertRaisesRegex(ValueError, "licencia"):
            cr.validar(d)

    def test_fuente_url_con_http(self):
        d = _datos()
        d["zonas.geojson"]["features"][1]["properties"]["fuente_url"] = "http://registry.opendata.aws/copernicus-dem/"
        with self.assertRaisesRegex(ValueError, "https"):
            cr.validar(d)
        d = _datos()
        d["incidentes.json"]["incidentes"][3]["otras_fuentes"][0]["url"] = "http://www.senamhi.gob.pe/x.pdf"
        with self.assertRaisesRegex(ValueError, "https"):
            cr.validar(d)

    def test_faja_con_poligono(self):
        d = _datos()
        faja = d["faja.geojson"]["features"][0]
        faja["geometry"] = {"type": "Polygon", "coordinates": [[[-78.5, -7.1], [-78.4, -7.1], [-78.4, -7.2], [-78.5, -7.1]]]}
        with self.assertRaisesRegex(ValueError, "tipo faja con geometría Polygon"):
            cr.validar(d)

    def test_claves_repetidas(self):
        d = _datos()
        zonas = d["zonas.geojson"]["features"]
        zonas[1]["properties"]["clave"] = zonas[0]["properties"]["clave"]
        with self.assertRaisesRegex(ValueError, "claves repetidas"):
            cr.validar(d)
        d = _datos()
        incidentes = d["incidentes.json"]["incidentes"]
        incidentes[1]["id"] = incidentes[0]["id"]
        with self.assertRaisesRegex(ValueError, "ids repetidos"):
            cr.validar(d)

    def test_clave_de_otro_rio(self):
        d = _datos()
        d["zonas.geojson"]["features"][0]["properties"]["clave"] = "chonta:relieve:3"
        with self.assertRaisesRegex(ValueError, "debe empezar con 'mashcon:'"):
            cr.validar(d)

    def test_lat_sin_lon(self):
        d = _datos()
        d["incidentes.json"]["incidentes"][1]["lon"] = None
        with self.assertRaisesRegex(ValueError, "lat y lon van juntos"):
            cr.validar(d)
        d = _datos()
        d["rio.json"]["lugares_aviso"][0]["lat"] = None   # Bambamarca Chico (mapa: true)
        with self.assertRaisesRegex(ValueError, "lat y lon van juntos"):
            cr.validar(d)

    def test_incidente_sin_punto_con_precision_de_punto(self):
        d = _datos()
        i = d["incidentes.json"]["incidentes"][1]
        i["lat"] = i["lon"] = None
        with self.assertRaisesRegex(ValueError, "precisión punto necesita lat y lon"):
            cr.validar(d)

    def test_lat_lon_invertidas(self):
        d = _datos()
        i = d["incidentes.json"]["incidentes"][1]
        i["lat"], i["lon"] = i["lon"], i["lat"]
        with self.assertRaisesRegex(ValueError, "fuera del Perú"):
            cr.validar(d)

    def test_valores_que_la_bd_rechazaria(self):
        d = _datos()
        d["incidentes.json"]["incidentes"][0]["tipo"] = "huayco"
        with self.assertRaisesRegex(ValueError, "tipo 'huayco'"):
            cr.validar(d)
        d = _datos()
        d["incidentes.json"]["incidentes"][0]["fecha"] = "22-02-1974"
        with self.assertRaisesRegex(ValueError, "AAAA-MM-DD"):
            cr.validar(d)
        d = _datos()
        d["rio.json"]["departamento"] = "CAJAMARCA"
        with self.assertRaisesRegex(ValueError, "no canónico"):
            cr.validar(d)

    def test_otro_rio(self):
        with self.assertRaisesRegex(ValueError, "es del río 'mashcon', no de 'chonta'"):
            cr.validar(_datos(), "chonta")

    def test_archivos_vacios(self):
        # con --aplicar, la poda borraría todas las zonas e incidentes del río
        d = _datos()
        d["zonas.geojson"]["features"] = []
        with self.assertRaisesRegex(ValueError, "ninguna zona estimada ni de estudio"):
            cr.validar(d)                                   # aunque queden las fajas
        d["faja.geojson"]["features"] = []
        with self.assertRaisesRegex(ValueError, "ninguna zona estimada ni de estudio"):
            cr.validar(d)
        d = _datos()
        d["incidentes.json"]["incidentes"] = []
        with self.assertRaisesRegex(ValueError, "no tiene incidentes"):
            cr.validar(d)

    def test_lugar_en_el_mapa_sin_coordenadas(self):
        d = _datos()
        lugar = next(l for l in d["rio.json"]["lugares_aviso"] if l["mapa"])
        lugar["lat"] = lugar["lon"] = None
        with self.assertRaisesRegex(ValueError, "mapa=true necesita lat y lon"):
            cr.validar(d)

    def test_fuente_coord_con_http(self):
        d = _datos()
        d["rio.json"]["lugares_aviso"][0]["fuente_coord"] = "http://geocatmin.ingemmet.gob.pe/"
        with self.assertRaisesRegex(ValueError, "https"):
            cr.validar(d)

    def test_geometrias_del_cauce_y_la_cuenca(self):
        d = _datos()
        d["cuenca.geojson"]["features"].append(copy.deepcopy(d["cuenca.geojson"]["features"][0]))
        with self.assertRaisesRegex(ValueError, "un solo MultiPolygon"):
            cr.validar(d)
        d = _datos()
        d["cauce.geojson"]["features"] = [f for f in d["cauce.geojson"]["features"]
                                          if f["properties"]["parte"] != "tronco"]
        with self.assertRaisesRegex(ValueError, "falta la parte 'tronco'"):
            cr.validar(d)
        d = _datos()
        f = d["cauce.geojson"]["features"][0]
        f["geometry"] = {"type": "MultiLineString", "coordinates": [f["geometry"]["coordinates"]]}
        with self.assertRaisesRegex(ValueError, "deben ser LineString"):
            cr.validar(d)


class _Cursor:
    """Lleva rio_zona y rio_incidente en memoria ({clave o id: río}) con la semántica de las sentencias."""

    def __init__(self, conn):
        self.conn, self.rowcount, self.filas = conn, -1, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        c = self.conn
        c.registro.append((sql, params))
        self.rowcount = 0
        if sql == cr.SQL_HAY_TABLAS:
            self.filas = [(c.migrada,)]
        elif sql == cr.SQL_CONTAR:
            rio = params["rio"]
            zonas = [k for k, r in c.zonas.items() if r == rio]
            incidentes = [k for k, r in c.incidentes.items() if r == rio]
            self.filas = [(len(zonas), sum(k not in params["claves"] for k in zonas),
                           len(incidentes), sum(k not in params["ids"] for k in incidentes))]
        elif sql == cr.SQL_INCIDENTES_AJENOS:
            ids, rio = params
            self.filas = sorted((k, r) for k, r in c.incidentes.items() if k in ids and r != rio)
        elif sql in (cr.SQL_PODAR_ZONAS, cr.SQL_PODAR_INCIDENTES):   # where rio = %s and not (... = any(%s))
            tabla = c.zonas if sql == cr.SQL_PODAR_ZONAS else c.incidentes
            rio, quedan = params
            borrar = [k for k, r in tabla.items() if r == rio and k not in quedan]
            for k in borrar:
                del tabla[k]
            self.rowcount = len(borrar)

    def executemany(self, sql, filas):
        filas = list(filas)
        self.conn.registro.append((sql, filas))
        if sql == cr.SQL_ZONA:
            self.conn.zonas.update({z["clave"]: z["rio"] for z in filas})
        elif sql == cr.SQL_INCIDENTE:            # on conflict (id) ... where rio_incidente.rio = excluded.rio
            for i in filas:
                self.conn.incidentes.setdefault(i["id"], i["rio"])

    def fetchone(self):
        return self.filas[0]

    def fetchall(self):
        return self.filas


class _Conexion:
    def __init__(self, migrada=True, zonas=None, incidentes=None):
        self.migrada, self.registro = migrada, []
        self.zonas, self.incidentes = dict(zonas or {}), dict(incidentes or {})

    def cursor(self):
        return _Cursor(self)

    def sentencias(self):
        return [s for s, _ in self.registro]


def _en_la_bd(rio="mashcon"):
    """(zonas, incidentes) como los dejó una carga anterior de los archivos reales."""
    _, zonas, incidentes = cr.validar(_datos())
    return {z["clave"]: rio for z in zonas}, {i["id"]: rio for i in incidentes}


def _conectar(conn):
    @contextmanager
    def falso_conectar():
        yield conn
    return falso_conectar


class TestMain(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def test_prueba_en_seco_no_conecta(self):
        with mock.patch.object(cr, "conectar", side_effect=AssertionError("no debía conectarse")):
            self.assertEqual(cr.main([]), 0)

    def test_aplicar_en_una_transaccion(self):
        conn = _Conexion()
        with mock.patch.object(cr, "conectar", _conectar(conn)):
            self.assertEqual(cr.main(["--aplicar"]), 0)
        self.assertEqual(conn.sentencias(), [cr.SQL_HAY_TABLAS, cr.SQL_CONTAR, cr.SQL_INCIDENTES_AJENOS, cr.SQL_RIO,
                                             cr.SQL_PODAR_ZONAS, cr.SQL_ZONA, cr.SQL_PODAR_INCIDENTES,
                                             cr.SQL_INCIDENTE])
        fila, podar_z, zonas, podar_i, incidentes = (p for _, p in conn.registro[3:])
        self.assertEqual(fila["id"], "mashcon")
        self.assertEqual(podar_z[0], "mashcon")
        self.assertEqual(sorted(podar_z[1]), sorted(z["clave"] for z in zonas))   # borra solo las que ya no están
        self.assertEqual((len(zonas), len(incidentes)), (13, 14))
        self.assertEqual(sorted(podar_i[1]), sorted(i["id"] for i in incidentes))
        # json para las columnas jsonb y GeoJSON para st_geomfromgeojson
        self.assertIsInstance(incidentes[0]["otras_fuentes"], str)
        self.assertEqual(json.loads(zonas[0]["geom"])["type"], "MultiPolygon")

    def test_segunda_carga_igual(self):
        zonas, incidentes = _en_la_bd()
        conn = _Conexion(zonas=zonas, incidentes=incidentes)
        with mock.patch.object(cr, "conectar", _conectar(conn)):
            self.assertEqual(cr.main(["--aplicar"]), 0)
        self.assertEqual((conn.zonas, conn.incidentes), (zonas, incidentes))

    def test_poda_grande_pide_podar(self):
        zonas, incidentes = _en_la_bd()
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "mashcon"
            shutil.copytree(MASHCON, carpeta)
            for nombre, quedan in (("zonas.geojson", 1), ("faja.geojson", 0)):   # recortados: 12 de 13 zonas fuera
                ruta = carpeta / nombre
                z = json.loads(ruta.read_text(encoding="utf-8"))
                z["features"] = z["features"][:quedan]
                ruta.write_text(json.dumps(z), encoding="utf-8")
            conn = _Conexion(zonas=zonas, incidentes=incidentes)
            with mock.patch.object(cr, "conectar", _conectar(conn)):
                self.assertEqual(cr.main(["--datos", str(carpeta), "--aplicar"]), 1)
            self.assertEqual(conn.sentencias(), [cr.SQL_HAY_TABLAS, cr.SQL_CONTAR])   # no escribió nada
            self.assertEqual(len(conn.zonas), 13)
            conn = _Conexion(zonas=zonas, incidentes=incidentes)
            with mock.patch.object(cr, "conectar", _conectar(conn)):
                self.assertEqual(cr.main(["--datos", str(carpeta), "--aplicar", "--podar"]), 0)
            self.assertEqual(len(conn.zonas), 1)
            # lo mismo con los incidentes (13 de 14 fuera)
            shutil.rmtree(carpeta)
            shutil.copytree(MASHCON, carpeta)
            ruta = carpeta / "incidentes.json"
            inc = json.loads(ruta.read_text(encoding="utf-8"))
            inc["incidentes"] = inc["incidentes"][:1]
            ruta.write_text(json.dumps(inc), encoding="utf-8")
            conn = _Conexion(zonas=zonas, incidentes=incidentes)
            with mock.patch.object(cr, "conectar", _conectar(conn)):
                self.assertEqual(cr.main(["--datos", str(carpeta), "--aplicar"]), 1)
            self.assertEqual(len(conn.incidentes), 14)
        # borrar menos de la mitad no pide --podar
        conn = _Conexion(zonas={**zonas, "mashcon:sobra": "mashcon"}, incidentes=incidentes)
        with mock.patch.object(cr, "conectar", _conectar(conn)):
            self.assertEqual(cr.main(["--aplicar"]), 0)
        self.assertNotIn("mashcon:sobra", conn.zonas)

    def test_la_poda_es_solo_del_rio(self):
        for sql in (cr.SQL_PODAR_ZONAS, cr.SQL_PODAR_INCIDENTES):
            self.assertIn("where rio = %s and not", sql)
        zonas, incidentes = _en_la_bd()
        conn = _Conexion(zonas={**zonas, "chonta:relieve:2": "chonta"},
                         incidentes={**incidentes, "CHO-2019": "chonta"})
        with mock.patch.object(cr, "conectar", _conectar(conn)):
            self.assertEqual(cr.main(["--aplicar"]), 0)
        self.assertEqual(conn.zonas["chonta:relieve:2"], "chonta")
        self.assertEqual(conn.incidentes["CHO-2019"], "chonta")

    def test_incidente_de_otro_rio(self):
        # los ids no llevan el río delante: la misma emergencia de ANA ya cargada para otro río no se mueve
        self.assertIn("where rio_incidente.rio = excluded.rio", " ".join(cr.SQL_INCIDENTE.split()))
        self.assertNotIn("rio = excluded.rio,", cr.SQL_INCIDENTE)
        conn = _Conexion(incidentes={"ANA-EEH-8759": "chonta"})
        with mock.patch.object(cr, "conectar", _conectar(conn)):
            self.assertEqual(cr.main(["--aplicar"]), 1)
        self.assertEqual(conn.sentencias(), [cr.SQL_HAY_TABLAS, cr.SQL_CONTAR, cr.SQL_INCIDENTES_AJENOS])
        self.assertEqual(conn.incidentes, {"ANA-EEH-8759": "chonta"})

    def test_sin_migracion_no_escribe(self):
        conn = _Conexion(migrada=False)
        with mock.patch.object(cr, "conectar", _conectar(conn)):
            self.assertEqual(cr.main(["--aplicar"]), 2)
        self.assertEqual([s for s, _ in conn.registro], [cr.SQL_HAY_TABLAS])

    def test_aplicar_sin_dsn(self):
        config.ajustes.cache_clear()
        self.addCleanup(config.ajustes.cache_clear)
        with mock.patch.dict("os.environ", {"SUPABASE_DB_URL": ""}):
            self.assertEqual(cr.main(["--aplicar"]), 2)

    def test_datos_invalidos_no_escriben(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "mashcon"
            shutil.copytree(MASHCON, carpeta)
            ruta = carpeta / "faja.geojson"
            faja = json.loads(ruta.read_text(encoding="utf-8"))
            del faja["features"][0]["properties"]["metodo"]
            ruta.write_text(json.dumps(faja), encoding="utf-8")
            with mock.patch.object(cr, "conectar", side_effect=AssertionError("no debía conectarse")):
                self.assertEqual(cr.main(["--datos", str(carpeta), "--aplicar"]), 1)
            (carpeta / "incidentes.json").unlink()
            self.assertEqual(cr.main(["--datos", str(carpeta)]), 1)


if __name__ == "__main__":
    unittest.main()
