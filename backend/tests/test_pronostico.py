"""
Pronóstico por localidad de SENAMHI: la página (backend/connectors/senamhi_pronostico.py), el
catálogo de coordenadas (backend/data/localidades_senamhi.json y su semilla) y la tarea
'pronostico' con la BD simulada. Sin red ni psycopg: solo librería estándar.
"""
import gzip
import json
import logging
import re
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from backend.connectors import _http
from backend.connectors import senamhi_pronostico as sp
from backend.ingesta import pronostico as tarea
from backend.ingesta.guardar import SQL_LATIDO
from backend.mapas import semilla_localidades as semilla

MUESTRAS = Path(__file__).parent / "muestras"
# 5 de las 277 localidades (Cajamarca, Bambamarca, Jaén, Moyobamba y Moquegua), sin cambios.
MUESTRA = (MUESTRAS / "pronostico_pais_20260922.html").read_text(encoding="utf-8")
# La página completa del país, tal como llegó (22-09-2026 23:26, hora de Perú).
PAIS = sp.decodificar(gzip.decompress((MUESTRAS / "pronostico_pais_20260922_completa.html.gz").read_bytes()))

HOY = date(2026, 9, 23)
# 23-09-2026 a la 01:00 en Lima: "hoy" es el 23 y la emisión vigente es la del 22 en la noche
AHORA = datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc)
CAJAMARCA = ["06-0011", "06-0033", "06-0064", "06-0065", "06-0122", "06-0123", "06-0124", "06-0127",
             "06-0209", "06-0274", "06-0275", "06-0276", "06-0277", "06-0278", "06-0320", "06-0321", "06-0381"]
# Localidad de SENAMHI de cada ciudad del frontend (frontend/src/data/cities.js; Lima y Callao comparten).
CIUDADES = {"Cajamarca": "06-0011", "Lima": "15-0001", "Callao": "15-0001", "Arequipa": "04-0018",
            "Trujillo": "13-0005", "Chiclayo": "14-0004", "Piura": "20-0003", "Iquitos": "16-0021",
            "Cusco": "08-0019", "Huancayo": "12-0028", "Pucallpa": "25-0024", "Tacna": "23-0010",
            "Ica": "11-0029", "Puno": "21-0030", "Ayacucho": "05-0017", "Huánuco": "10-0014",
            "Huaraz": "02-0013", "Moyobamba": "22-0059", "Abancay": "03-0031", "Huancavelica": "09-0016",
            "Cerro de Pasco": "19-0060", "Moquegua": "18-0035", "Tumbes": "24-0002",
            "Chachapoyas": "01-0012", "Puerto Maldonado": "17-0027"}


def _muestra(pagina=MUESTRA, hoy=HOY):
    """parse_pagina de una página chica (con menos de MIN_LOCALIDADES)."""
    with mock.patch.object(sp, "MIN_LOCALIDADES", 1):
        return sp.parse_pagina(pagina, hoy)


def _bloque(pagina, codigo):
    """Texto del bloque de una localidad ('06-0123') dentro de la página."""
    dp, loc = codigo.split("-")
    ini = pagina.index(f"dp={dp}&localidad={loc}'")
    fin = pagina.find("nameCity", ini)
    return pagina[ini:fin if fin > 0 else pagina.index("</tbody>")]


def _cambiar_bloque(pagina, codigo, viejo, nuevo, veces=1):
    b = _bloque(pagina, codigo)
    return pagina.replace(b, b.replace(viejo, nuevo, veces))


class TestPagina(unittest.TestCase):
    def test_muestra(self):
        p = _muestra()
        self.assertEqual(p.emision, date(2026, 9, 22))
        self.assertEqual([loc.codigo for loc in p.localidades], ["06-0011", "06-0123", "06-0124", "22-0059", "18-0035"])
        self.assertEqual(p.problemas, [])
        caj = p.localidades[0]
        self.assertEqual(caj.nombre_senamhi, "CAJAMARCA - CAJAMARCA")
        self.assertEqual([(d.fecha, d.icono, d.tmax, d.tmin) for d in caj.dias],
                         [(date(2026, 9, 23), "009", 21, 10), (date(2026, 9, 24), "008", 22, 9),
                          (date(2026, 9, 25), "008", 24, 8)])
        self.assertEqual(caj.dias[0].texto, "Cielo nublado parcial variando a cielo nublado y cielo cubierto "
                                            "durante el día con lluvia.")
        # Moquegua trae también el día de la emisión ("martes, 22")
        self.assertEqual([d.fecha.day for d in p.localidades[-1].dias], [22, 23, 24])

    def test_pagina_completa(self):
        p = sp.parse_pagina(PAIS, HOY)
        self.assertEqual((len(p.localidades), sum(len(loc.dias) for loc in p.localidades)), (277, 831))
        self.assertEqual(p.problemas, [])
        self.assertEqual(sorted(loc.codigo for loc in p.localidades if loc.dp == "06"), sorted(CAJAMARCA))

    def test_cp1252(self):
        p = _muestra(sp.decodificar(MUESTRA.encode("cp1252")))
        self.assertEqual(len(p.localidades), 5)
        self.assertIn("mañana", p.localidades[2].dias[0].texto)   # Jaén
        self.assertEqual(sp.decodificar("Emisión".encode("utf-8")), "Emisión")

    def test_un_byte_danado_no_pasa_la_pagina_a_cp1252(self):
        # un byte inválido a mitad de la página UTF-8: se reemplaza ese, no se lee todo en cp1252
        b = PAIS.encode("utf-8")
        danada = b[:len(b) // 2] + b"\xff" + b[len(b) // 2:]
        t = sp.decodificar(danada)
        self.assertEqual(t.count("�"), 1)
        self.assertNotIn("Ã", t)
        caj = next(loc for loc in sp.parse_pagina(t, HOY).localidades if loc.codigo == "06-0011")
        self.assertTrue(caj.dias[0].texto.endswith("durante el día con lluvia."))
        # la tarea lo ve en problemas
        with mock.patch.object(_http, "get_bytes", lambda url, max_bytes=None: danada):
            p = sp.pronostico_pais(HOY)
        self.assertEqual(p.problemas[0], "la página trae 1 caracteres ilegibles (se reemplazaron por U+FFFD)")

    def test_setiembre_y_entidades(self):
        pagina = MUESTRA.replace("septiembre", "setiembre").replace("con lluvia.", "con lluvia &amp; neblina.", 1)
        p = _muestra(pagina)
        self.assertEqual(p.emision, date(2026, 9, 22))
        self.assertTrue(p.localidades[0].dias[0].texto.endswith("durante el día con lluvia & neblina."))

    def test_sin_emision(self):
        with self.assertRaisesRegex(ValueError, "emisión"):
            _muestra(MUESTRA.replace("Emisi&oacute;n:", "Actualizado:"))

    def test_emision_futura(self):
        with self.assertRaisesRegex(ValueError, "posterior a hoy"):
            _muestra(hoy=date(2026, 9, 21))

    def test_pocas_o_demasiadas_localidades(self):
        with self.assertRaisesRegex(ValueError, "5 localidades"):
            sp.parse_pagina(MUESTRA, HOY)   # sin parchear: menos de MIN_LOCALIDADES
        with mock.patch.object(sp, "MAX_LOCALIDADES", 276), self.assertRaisesRegex(ValueError, "277 localidades"):
            sp.parse_pagina(PAIS, HOY)
        with self.assertRaisesRegex(ValueError, "0 localidades"):
            sp.parse_pagina("<strong>Emisi&oacute;n: martes, 22 de septiembre del 2026</strong> sin tabla", HOY)

    def test_bloque_descuadrado_va_a_problemas(self):
        # a Bambamarca le falta el ícono de un día: 3 fechas y 2 días leídos -> se descarta entera
        pagina = _cambiar_bloque(PAIS, "06-0123", ".png", ".gif")
        p = sp.parse_pagina(pagina, HOY)
        self.assertEqual(len(p.localidades), 276)
        self.assertNotIn("06-0123", [loc.codigo for loc in p.localidades])
        self.assertEqual(p.problemas, ["06-0123 BAMBAMARCA - CAJAMARCA: 3 fechas y 2 días leídos"])

    def test_demasiados_problemas_es_falla(self):
        codigos = re.findall(r"dp=(\d{2})&localidad=(\d{4})'", PAIS)
        pagina = PAIS
        for dp, loc in codigos[:28]:   # 28 de 277 > 10 %
            pagina = _cambiar_bloque(pagina, f"{dp}-{loc}", ".png", ".gif")
        with self.assertRaisesRegex(ValueError, "28 de 277 bloques"):
            sp.parse_pagina(pagina, HOY)
        pagina = PAIS
        for dp, loc in codigos[:27]:   # 27 no pasa del 10 %
            pagina = _cambiar_bloque(pagina, f"{dp}-{loc}", ".png", ".gif")
        self.assertEqual(len(sp.parse_pagina(pagina, HOY).localidades), 250)

    def test_fecha_fuera_de_la_emision(self):
        # 'viernes, 2 de octubre' en la emisión del 22-09: más de 7 días después
        pagina = _cambiar_bloque(MUESTRA, "06-0124", "viernes, 25 de septiembre", "viernes, 2 de octubre")
        with mock.patch.object(sp, "MIN_LOCALIDADES", 1), mock.patch.object(sp, "MAX_PROBLEMAS", 0.5):
            p = sp.parse_pagina(pagina, HOY)
        jaen = p.localidades[2]
        self.assertEqual([d.fecha.day for d in jaen.dias], [23, 24])
        self.assertEqual(p.problemas, ["06-0124 JAEN - CAJAMARCA: fechas que no corresponden a la emisión "
                                       "del 2026-09-22: viernes, 2 de octubre"])

    def test_dia_repetido_queda_el_primero(self):
        # como en la copia del 25-05-2025: dos versiones del mismo día en un bloque
        pagina = _cambiar_bloque(MUESTRA, "06-0124", "jueves, 24 de septiembre", "mi&eacute;rcoles, 23 de septiembre")
        with mock.patch.object(sp, "MIN_LOCALIDADES", 1), mock.patch.object(sp, "MAX_PROBLEMAS", 0.5):
            p = sp.parse_pagina(pagina, HOY)
        jaen = p.localidades[2]
        self.assertEqual([(d.fecha.day, d.icono) for d in jaen.dias], [(23, "003"), (25, "003")])
        self.assertEqual(p.problemas, ["06-0124 JAEN - CAJAMARCA: días repetidos (queda el primero): "
                                       "miércoles, 23 de septiembre"])

    def test_cambio_de_anio(self):
        self.assertEqual(sp.fecha_emision("miércoles, 31 de diciembre del 2025"), date(2025, 12, 31))
        self.assertEqual(sp.fecha_dia("jueves, 1 de enero", date(2025, 12, 31)), date(2026, 1, 1))
        self.assertEqual(sp.fecha_dia("miércoles, 31 de diciembre", date(2026, 1, 1)), date(2025, 12, 31))
        self.assertEqual(sp.fecha_dia("mi&eacute;rcoles, 23 de setiembre", date(2026, 9, 22)), date(2026, 9, 23))
        self.assertIsNone(sp.fecha_dia("jueves, 31 de septiembre", date(2026, 9, 22)))
        self.assertIsNone(sp.fecha_dia("mañana", date(2026, 9, 22)))
        with self.assertRaises(ValueError):
            sp.fecha_emision("martes 22")

    def test_temperaturas_fuera_de_rango(self):
        pagina = _cambiar_bloque(MUESTRA, "06-0011", "<strong> 21&ordm;C", "<strong> 75&ordm;C")
        pagina = _cambiar_bloque(pagina, "06-0011", "<strong> 22&ordm;C", "<strong> 100&ordm;C")
        pagina = _cambiar_bloque(pagina, "06-0011", "<strong> 8&ordm;C", "<strong> 30&ordm;C")   # mínima > máxima
        pagina = _cambiar_bloque(pagina, "06-0123", "<strong> 22&ordm;C", "<strong> --&ordm;C")   # sin dato
        caj, bamba = _muestra(pagina).localidades[:2]
        self.assertEqual([(d.tmax, d.tmin) for d in caj.dias], [(None, 10), (None, 9), (None, None)])
        self.assertIsNone(bamba.dias[0].tmax)

    def test_texto_recortado(self):
        pagina = _cambiar_bloque(MUESTRA, "06-0011", "con lluvia.", "con lluvia." + " x" * 400)
        self.assertEqual(len(_muestra(pagina).localidades[0].dias[0].texto), sp.MAX_TEXTO)

    def test_localidad_repetida(self):
        b = _bloque(MUESTRA, "06-0011")
        pagina = MUESTRA.replace("</tbody>", "<tr><td><span class='nameCity'><a href='?p=pronostico-detalle&" + b + "</tbody>")
        with mock.patch.object(sp, "MAX_PROBLEMAS", 0.5):
            p = _muestra(pagina)
        self.assertEqual(len(p.localidades), 5)
        self.assertEqual(p.problemas, ["06-0011 CAJAMARCA - CAJAMARCA: repetida en la página (queda la primera)"])

    def test_descarga_con_reintentos_y_tope(self):
        pedidas = []

        def falso_get_bytes(url, max_bytes=None):
            pedidas.append((url, max_bytes))
            return PAIS.encode("utf-8")

        with mock.patch.object(_http, "get_bytes", falso_get_bytes):
            self.assertEqual(len(sp.pronostico_pais(HOY).localidades), 277)
        self.assertEqual(pedidas, [("https://www.senamhi.gob.pe/?p=pronostico-meteorologico", sp.MAX_HTML_BYTES)])


class TestCatalogo(unittest.TestCase):
    """El catálogo revisado del repo (lo lee la tarea en producción)."""

    @classmethod
    def setUpClass(cls):
        cls.catalogo, cls.avisos = tarea.cargar_catalogo()
        cls.crudo = json.loads(tarea.CATALOGO.read_text(encoding="utf-8"))

    def test_condicion_de_aceptacion(self):
        self.assertEqual(self.avisos, [])
        faltan = [c for c in CAJAMARCA + sorted(set(CIUDADES.values())) if c not in self.catalogo]
        self.assertEqual(faltan, [])
        self.assertEqual((self.catalogo["06-0011"]["lat"], self.catalogo["06-0011"]["lon"]), (-7.1675, -78.49309))
        # San Miguel de Pallaques es la CO de San Miguel, no la homónima de San Ignacio
        self.assertEqual((self.catalogo["06-0320"]["lat"], self.catalogo["06-0320"]["lon"]), (-6.99684, -78.85308))

    def test_formato(self):
        self.assertRegex(self.crudo["generado"], r"^\d{4}-\d{2}-\d{2}$")
        for codigo, e in self.crudo["localidades"].items():
            self.assertRegex(codigo, r"^\d{2}-\d{4}$")
            self.assertEqual(set(e), {"nombre_senamhi", "lat", "lon", "ubicacion"}, codigo)
            self.assertTrue(e["ubicacion"].startswith(("estación SENAMHI ", "ciudad (centro aproximado)")), codigo)

    def test_nombres_iguales_a_la_pagina(self):
        # un código del catálogo que también está en la página del 22-09 lleva el mismo nombre
        pagina = {loc.codigo: loc.nombre_senamhi for loc in sp.parse_pagina(PAIS, HOY).localidades}
        for codigo, e in self.catalogo.items():
            if codigo in pagina:
                self.assertEqual(e["nombre_senamhi"], pagina[codigo], codigo)
        sin = {s.split(" ", 1)[0] for s in self.crudo["sin_ubicar"]}
        self.assertFalse(sin & set(self.catalogo))


class TestSemilla(unittest.TestCase):
    ESTACIONES = [
        ("000325", "AUGUSTO WEBERBAUER", "MAP", "Cajamarca", -7.1675, -78.49309),
        ("4726A7D4", "UNC CAJAMARCA", "EMA", "Cajamarca", -7.16747, -78.49307),
        ("000388", "SAN MIGUEL", "CO", "Cajamarca", -6.99684, -78.85308),
        ("000999", "SAN MIGUEL", "CO", "Cajamarca", -5.13, -78.99),        # la homónima de San Ignacio
        ("100015", "BAMBAMARCA", "CP", "Cajamarca", -6.67655, -78.51834),
        ("472680EE", "BAMBAMARCA M", "EMA", "Cajamarca", -6.67981, -78.52346),
        ("4727ABCD", "JAEN", "EMA", "Cajamarca", -5.70, -78.80),
        ("000111", "JAEN", "CP", "Cajamarca", -5.67664, -78.77416),
        ("000222", "MOQUEGUA", "CP", "Moquegua", -17.17875, -70.93269),
        ("000333", "MOYOBAMBA", "CO", "Amazonas", -6.0, -77.0),            # mismo nombre, otro departamento
    ]

    def _localidad(self, codigo, nombre):
        return sp.Localidad(dp=codigo[:2], localidad=codigo[3:], nombre_senamhi=nombre)

    def test_emparejar(self):
        locs = [self._localidad("06-0011", "CAJAMARCA - CAJAMARCA"),
                self._localidad("06-0320", "SAN MIGUEL DE PALLAQUES - CAJAMARCA"),
                self._localidad("06-0123", "BAMBAMARCA - CAJAMARCA"),
                self._localidad("06-0124", "JAEN - CAJAMARCA"),
                self._localidad("22-0059", "MOYOBAMBA - SAN MARTIN"),
                self._localidad("20-0003", "PIURA - PIURA"),
                self._localidad("18-0035", "MOQUEGUA - MOQUEGUA")]
        catalogo, sin, notas = semilla.emparejar(locs, self.ESTACIONES)
        self.assertEqual(catalogo["06-0011"], {"nombre_senamhi": "CAJAMARCA - CAJAMARCA", "lat": -7.1675,
                                               "lon": -78.49309,
                                               "ubicacion": "estación SENAMHI AUGUSTO WEBERBAUER (MAP)"})
        self.assertEqual((catalogo["06-0320"]["lat"], catalogo["06-0320"]["lon"]), (-6.99684, -78.85308))
        self.assertEqual(catalogo["06-0123"]["ubicacion"], "estación SENAMHI BAMBAMARCA (CP)")   # la convencional
        self.assertEqual(catalogo["06-0124"]["lat"], -5.67664)
        self.assertEqual(catalogo["20-0003"], {"nombre_senamhi": "PIURA - PIURA", "lat": -5.1945, "lon": -80.6328,
                                               "ubicacion": "ciudad (centro aproximado)"})
        self.assertEqual(sin, ["22-0059 MOYOBAMBA - SAN MARTIN"])   # la MOYOBAMBA de Amazonas no sirve
        self.assertEqual(notas, [])
        # dos convencionales homónimas en el mismo departamento: se avisa
        _, _, notas = semilla.emparejar(locs[3:4], self.ESTACIONES + [("000112", "JAEN", "CO", "Cajamarca", -5.6, -78.7)])
        self.assertEqual(len(notas), 1)
        self.assertIn("varias estaciones posibles", notas[0])

    def test_normalizar(self):
        self.assertEqual(semilla.normalizar("Chancay Baños"), "CHANCAY BANOS")
        self.assertEqual(semilla.normalizar("LIMA OESTE / CALLAO"), "LIMA OESTE CALLAO")
        self.assertEqual(semilla.normalizar("STA. RITA DE CASTILLA"), "STA RITA DE CASTILLA")

    def test_escribir_lo_lee_la_tarea(self):
        catalogo, sin, _ = semilla.emparejar([self._localidad("06-0011", "CAJAMARCA - CAJAMARCA"),
                                              self._localidad("06-0033", "CHOTA - CAJAMARCA")], self.ESTACIONES)
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "catalogo.json"
            semilla.escribir(ruta, catalogo, sin)
            leido, avisos = tarea.cargar_catalogo(ruta)
            crudo = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(set(leido), {"06-0011"})
        self.assertEqual(crudo["sin_ubicar"], ["06-0033 CHOTA - CAJAMARCA"])
        self.assertEqual(avisos, [])


class _Cursor:
    def __init__(self, conn):
        self.conn, self.ultima, self.rowcount = conn, None, -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.registro.append((sql, params))
        self.ultima = sql
        self.rowcount = 7 if sql == tarea.SQL_PURGA else 1

    def executemany(self, sql, filas):
        filas = list(filas)
        self.conn.registro.append((sql, filas))
        self.rowcount = len(filas) - self.conn.viejas   # las que la guarda de emisión no dejó pasar

    def fetchone(self):
        assert self.ultima == tarea.SQL_HAY_TABLA, self.ultima
        return (self.conn.migrada,)


class _Conexion:
    def __init__(self, migrada=True, viejas=0):
        self.migrada, self.viejas, self.registro = migrada, viejas, []

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]

    def sentencias(self):
        return [s for s, _ in self.registro]


def _catalogo(entradas):
    """Un catálogo temporal con esas entradas {codigo: (lat, lon)}."""
    d = tempfile.TemporaryDirectory()
    ruta = Path(d.name) / "catalogo.json"
    ruta.write_text(json.dumps({"generado": "2026-09-23", "localidades": {
        c: {"nombre_senamhi": n, "lat": lat, "lon": lon, "ubicacion": "estación SENAMHI X (CO)"}
        for c, (n, lat, lon) in entradas.items()}}), encoding="utf-8")
    return d, ruta


class TestTarea(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.ERROR)   # la tarea avisa de las fallas simuladas
        self.addCleanup(logging.disable, logging.NOTSET)

    def correr(self, pagina=PAIS, error=None, ahora=AHORA, migrada=True, catalogo=None, viejas=0):
        conn = _Conexion(migrada=migrada, viejas=viejas)

        @contextmanager
        def falso_conectar():
            yield conn

        def falso_pais(hoy):
            if error:
                raise error
            return sp.parse_pagina(pagina, hoy)

        self.excepcion = None
        with ExitStack() as parches:
            parches.enter_context(mock.patch.object(tarea, "conectar", falso_conectar))
            parches.enter_context(mock.patch.object(sp, "pronostico_pais", falso_pais))
            if catalogo is not None:
                parches.enter_context(mock.patch.object(tarea, "CATALOGO", catalogo))
            try:
                devuelto = tarea.actualizar(ahora)
            except Exception as e:
                self.excepcion, devuelto = e, None
        [(servicio, datos)] = conn.params(SQL_LATIDO)   # el latido se escribe siempre
        self.assertEqual(servicio, "pronostico")
        self.assertEqual(conn.sentencias()[0], tarea.SQL_HAY_TABLA)
        self.assertEqual(conn.sentencias()[-1], SQL_LATIDO)
        resumen = json.loads(datos)
        if devuelto is not None:
            self.assertEqual(resumen, devuelto)
        return conn, resumen

    def test_corrida_normal(self):
        conn, resumen = self.correr()
        self.assertIsNone(self.excepcion)
        self.assertEqual(conn.sentencias(), [tarea.SQL_HAY_TABLA, tarea.SQL_CANDADO, tarea.SQL_PRONOSTICO,
                                             tarea.SQL_PURGA, SQL_LATIDO])
        [filas] = conn.params(tarea.SQL_PRONOSTICO)
        self.assertEqual(len(filas), 811)   # 831 días menos los 20 del martes 22, que ya pasó
        self.assertEqual(min(f["fecha"] for f in filas), HOY)
        caj = next(f for f in filas if f["codigo"] == "06-0011" and f["fecha"] == HOY)
        self.assertEqual(caj, {
            "codigo": "06-0011", "fecha": HOY, "dp": "06", "localidad": "0011", "nombre": "Cajamarca",
            "nombre_senamhi": "CAJAMARCA - CAJAMARCA", "departamento": "Cajamarca", "emision": date(2026, 9, 22),
            "icono_senamhi": "009", "tmax": 21, "tmin": 10,
            "texto": "Cielo nublado parcial variando a cielo nublado y cielo cubierto durante el día con lluvia.",
            "tipo": "lluvia", "posible": False, "por": "texto+icono", "lluvia_segura": False, "granizo": False,
            "intensidad": None, "momento": None, "cielo": None, "lat": -7.1675, "lon": -78.49309,
            "ubicacion": "estación SENAMHI AUGUSTO WEBERBAUER (MAP)"})
        # todas las filas traen todas las columnas del INSERT
        columnas = set(re.findall(r"%\((\w+)\)s", tarea.SQL_PRONOSTICO))
        self.assertEqual(len(columnas), 23)
        self.assertTrue(all(set(f) == columnas for f in filas))
        moyo = next(f for f in filas if f["codigo"] == "22-0059" and f["fecha"] == HOY)
        self.assertEqual((moyo["departamento"], moyo["tipo"], moyo["posible"], moyo["por"]),
                         ("San Martín", "tormenta", True, "icono"))
        self.assertEqual(conn.params(tarea.SQL_PURGA), [(HOY,)])
        self.assertEqual(resumen["pais"]["2026-09-23"],
                         {"lluvia": 57, "posible": 42, "tormenta": 4, "nieve": 0, "sin_lluvia": 174})
        self.assertEqual(resumen["cajamarca"], {
            "2026-09-23": {"lluvia": 7, "posible": 6, "tormenta": 0, "nieve": 0, "sin_lluvia": 4},
            "2026-09-24": {"lluvia": 6, "posible": 8, "tormenta": 0, "nieve": 0, "sin_lluvia": 3},
            "2026-09-25": {"lluvia": 6, "posible": 1, "tormenta": 0, "nieve": 0, "sin_lluvia": 10}})
        self.assertEqual({k: resumen[k] for k in ("emision", "localidades", "filas", "escritas", "purgadas",
                                                   "problemas", "fallas", "avisos")},
                         {"emision": "2026-09-22", "localidades": 277, "filas": 811, "escritas": 811,
                          "purgadas": 7, "problemas": [], "fallas": [], "avisos": []})
        # las que el catálogo no ubica se guardan igual (con lat null) y se listan (hasta 30)
        sin = json.loads(tarea.CATALOGO.read_text(encoding="utf-8"))["sin_ubicar"]
        sin_codigos = {s.split(" ", 1)[0] for s in sin}
        dias_sin = sum(1 for loc in sp.parse_pagina(PAIS, HOY).localidades if loc.codigo in sin_codigos
                       for d in loc.dias if d.fecha >= HOY)
        self.assertEqual(len([f for f in filas if f["lat"] is None]), dias_sin)
        self.assertLessEqual(set(resumen["sin_ubicacion"][:30]), set(sin))
        self.assertEqual(resumen["sin_ubicacion"][30:], [f"... y {len(sin) - 30} más"])

    def test_pagina_caida_solo_latido_y_falla(self):
        conn, resumen = self.correr(error=TimeoutError("timed out"))
        self.assertIsInstance(self.excepcion, RuntimeError)
        self.assertEqual(conn.params(tarea.SQL_PRONOSTICO), [])
        self.assertEqual(conn.params(tarea.SQL_PURGA), [])       # una fuente caída no borra nada
        self.assertEqual(resumen["fallas"], ["pagina"])
        self.assertEqual(resumen["avisos"], ["página: TimeoutError: timed out"])
        self.assertEqual((resumen["emision"], resumen["localidades"], resumen["filas"], resumen["cajamarca"]),
                         (None, None, 0, {}))

    def test_pagina_ilegible_es_falla(self):
        conn, resumen = self.correr(pagina=MUESTRA)   # 5 localidades: menos de MIN_LOCALIDADES
        self.assertIsInstance(self.excepcion, RuntimeError)
        self.assertEqual(conn.params(tarea.SQL_PRONOSTICO), [])
        self.assertEqual(resumen["fallas"], ["pagina"])
        self.assertTrue(resumen["avisos"][0].startswith("página: ValueError: La página de pronóstico de SENAMHI trae 5"))

    def test_sin_migracion(self):
        conn, resumen = self.correr(migrada=False)
        self.assertIsNone(self.excepcion)
        self.assertEqual(conn.sentencias(), [tarea.SQL_HAY_TABLA, SQL_LATIDO])
        self.assertEqual(resumen["fallas"], ["migracion"])
        self.assertEqual(resumen["avisos"], [tarea.AVISO_SIN_TABLA])
        self.assertIsNone(resumen["escritas"])

    def test_localidad_sin_catalogo_va_con_lat_null(self):
        d, ruta = _catalogo({"06-0011": ("CAJAMARCA - CAJAMARCA", -7.1675, -78.49309),
                             "06-0123": ("BAMBAMARCA - CAJAMARCA", -6.67655, 78.51834),      # lon sin el signo
                             "06-0124": ("JAEN - CAJAMARCA", -5.67664, -78.77416)})
        self.addCleanup(d.cleanup)
        conn, resumen = self.correr(catalogo=ruta)
        self.assertIsNone(self.excepcion)
        [filas] = conn.params(tarea.SQL_PRONOSTICO)
        self.assertEqual(len(filas), 811)
        por_codigo = {f["codigo"]: f for f in filas}
        self.assertEqual((por_codigo["06-0124"]["lat"], por_codigo["06-0124"]["ubicacion"]),
                         (-5.67664, "estación SENAMHI X (CO)"))
        self.assertEqual((por_codigo["06-0123"]["lat"], por_codigo["06-0123"]["lon"]), (None, None))
        self.assertEqual((por_codigo["22-0059"]["lat"], por_codigo["22-0059"]["ubicacion"]), (None, None))
        self.assertEqual(len(resumen["sin_ubicacion"]), 31)   # 30 y "... y 245 más"
        self.assertEqual(resumen["sin_ubicacion"][-1], "... y 245 más")
        self.assertEqual(resumen["avisos"], ["catálogo: 06-0123 fuera del Perú (-6.67655, 78.51834): queda sin ubicar"])

    def test_catalogo_ilegible_no_escribe_nada(self):
        # sin catálogo las filas irían con lat/lon null y el upsert (la misma emisión se
        # reescribe) borraría los puntos guardados: solo latido y la tarea falla
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "roto.json"
            ruta.write_text('{"localidades": {"06-0011": {"lat": -7.1675,}}}', encoding="utf-8")   # coma de más
            conn, resumen = self.correr(catalogo=ruta)
        self.assertIsInstance(self.excepcion, RuntimeError)
        self.assertIn("catálogo de localidades", str(self.excepcion))
        self.assertEqual(conn.sentencias(), [tarea.SQL_HAY_TABLA, tarea.SQL_CANDADO, SQL_LATIDO])
        self.assertEqual(resumen["fallas"], ["catalogo"])
        self.assertTrue(resumen["avisos"][0].startswith("catálogo: JSONDecodeError"))
        self.assertEqual((resumen["emision"], resumen["filas"], resumen["escritas"], resumen["purgadas"],
                          resumen["sin_ubicacion"]), ("2026-09-22", 0, None, None, []))

    def test_nombre_distinto_al_del_catalogo(self):
        d, ruta = _catalogo({"06-0011": ("CAJAMARCA NORTE - CAJAMARCA", -7.1675, -78.49309)})
        self.addCleanup(d.cleanup)
        conn, resumen = self.correr(catalogo=ruta)
        [filas] = conn.params(tarea.SQL_PRONOSTICO)
        self.assertEqual(next(f for f in filas if f["codigo"] == "06-0011")["lat"], -7.1675)
        self.assertEqual(resumen["avisos"], ["catálogo: 06-0011 ahora es 'CAJAMARCA - CAJAMARCA' (el catálogo "
                                             "dice 'CAJAMARCA NORTE - CAJAMARCA'): revisar el punto"])

    def test_purga_con_la_fecha_de_lima(self):
        # 04:30Z del 23-09 son las 23:30 del 22 en Lima: hoy es el 22 y el martes 22 se guarda
        conn, resumen = self.correr(ahora=datetime(2026, 9, 23, 4, 30, tzinfo=timezone.utc))
        self.assertEqual(conn.params(tarea.SQL_PURGA), [(date(2026, 9, 22),)])
        self.assertEqual(resumen["filas"], 831)
        self.assertEqual(resumen["pais"]["2026-09-22"]["sin_lluvia"] + resumen["pais"]["2026-09-22"]["lluvia"]
                         + resumen["pais"]["2026-09-22"]["posible"] + resumen["pais"]["2026-09-22"]["tormenta"]
                         + resumen["pais"]["2026-09-22"]["nieve"], 20)

    def test_emision_mas_vieja_no_pisa(self):
        self.assertTrue(tarea.SQL_PRONOSTICO.endswith("where excluded.emision >= pronostico_localidad.emision"))
        self.assertIn("on conflict (codigo, fecha) do update set", tarea.SQL_PRONOSTICO)
        self.assertIn("ts_captura = now()", tarea.SQL_PRONOSTICO)
        self.assertEqual(tarea.SQL_PURGA, "delete from pronostico_localidad where fecha < %s")
        self.assertEqual(tarea.SQL_CANDADO, "select pg_advisory_xact_lock(hashtext('pronostico'))")
        self.assertEqual(tarea.SQL_HAY_TABLA, "select to_regclass('public.pronostico_localidad') is not null")
        # la BD ya tenía una emisión más nueva para 11 filas: el latido cuenta solo las escritas
        _, resumen = self.correr(viejas=11)
        self.assertEqual((resumen["filas"], resumen["escritas"]), (811, 800))

    def test_emision_atrasada_es_aviso(self):
        # sábado 26-09 a las 10:00 en Lima y la página sigue con la emisión del martes 22
        conn, resumen = self.correr(ahora=datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc))
        self.assertIsNone(self.excepcion)
        self.assertEqual(resumen["fallas"], [])
        self.assertEqual(resumen["avisos"], ["SENAMHI no publica un pronóstico nuevo desde el 2026-09-22"])
        self.assertEqual(resumen["filas"], 0)            # todos sus días ya pasaron
        self.assertEqual(conn.params(tarea.SQL_PRONOSTICO), [])
        self.assertEqual(conn.params(tarea.SQL_PURGA), [(date(2026, 9, 26),)])
        # el viernes 25 todavía no avisa (3 días)
        _, resumen = self.correr(ahora=datetime(2026, 9, 25, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(resumen["avisos"], [])



if __name__ == "__main__":
    unittest.main()
