"""Ingesta horaria: horas, departamentos, alertas y la regla de no borrar lo que no se re-evaluó."""
import json
import logging
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest import mock

from backend import alerts, config
from backend.connectors import ana, igp, noaa, senamhi
from backend.ingesta import guardar as guardar_mod
from backend.ingesta.departamentos import DEPARTAMENTOS, clave, nombre_departamento
from backend.ingesta.guardar import SQL_BORRAR_ALERTAS, SQL_CAUDAL, SQL_ESTACION, SQL_ICEN, SQL_LATIDO, guardar
from backend.ingesta.recolectar import Pasada, filas_lluvia, recolectar


def _estacion(cod, estado="AUTOMATICA", tipo="M"):
    return senamhi.Estacion(cod=cod, nombre=f"Est {cod}", lat=-7.1, lon=-78.5,
                            tipo=tipo, categoria="EMA", estado=estado)


def _serie(cod, precip, temp=None):
    ts = [f"2026/09/22 - {h:02d}" for h in range(len(precip))]
    return senamhi.SerieHoraria(estacion=f"Est {cod}", codigo=cod, timestamps=ts,
                                precip_mm=precip, temp_c=temp if temp is not None else [])


def _caudal(estacion, departamento, valor, alerta=10.0, emergencia=20.0):
    return ana.EstacionCaudal(estacion=estacion, rio="Rio", departamento=departamento, provincia="P",
                              distrito="D", operador="O", valor=valor, unidad="m3/s",
                              umbral_alerta=alerta, umbral_emergencia=emergencia,
                              tendencia="Estable", hora="13:00", lat=-7.0, lon=-78.0)


class TestHoras(unittest.TestCase):
    def test_hora_de_senamhi_es_hora_de_peru(self):
        # 13:00 en Lima son las 18:00 UTC (antes se guardaba como 13:00 UTC: 5 h antes)
        self.assertEqual(senamhi.parse_ts("2026/09/22 - 13").astimezone(timezone.utc),
                         datetime(2026, 9, 22, 18, tzinfo=timezone.utc))

    def test_hora_ilegible(self):
        for malo in ("", "2026/09/22", "2026/09/22 - 24", "22/09/2026 - 13", "a - b - c"):
            self.assertIsNone(senamhi.parse_ts(malo), malo)

    def test_filas_sin_temperatura_no_se_pierden(self):
        filas = filas_lluvia("X", _serie("X", [0.0, 1.5, None]))
        self.assertEqual(len(filas), 3)
        self.assertEqual([f[3] for f in filas], [0.0, 1.5, None])
        self.assertTrue(all(f[4] is None for f in filas))
        self.assertIsNotNone(filas[0][2].tzinfo)


class TestDepartamentos(unittest.TestCase):
    def test_nombres_de_distintas_fuentes_coinciden(self):
        casos = {"APURIMAC": "Apurímac", "Áncash": "Áncash", "Madre De Dios": "Madre de Dios",
                 "san martin": "San Martín", "LA LIBERTAD": "La Libertad", "Callao": "Callao",
                 "Huanuco": "Huánuco", "Junin": "Junín"}
        for entrada, esperado in casos.items():
            self.assertEqual(nombre_departamento(entrada), esperado, entrada)

    def test_vacio_y_desconocido(self):
        self.assertIsNone(nombre_departamento(""))
        self.assertIsNone(nombre_departamento(None))
        self.assertEqual(nombre_departamento("OTRA REGION"), "Otra Region")

    def test_clave_ignora_guiones_y_tildes(self):
        self.assertEqual(clave("La Libertad"), clave("la-libertad"))
        self.assertEqual(clave("San Martín"), "sanmartin")

    def test_cada_slug_de_senamhi_tiene_su_nombre(self):
        # los slugs de SENAMHI llevan guiones; su nombre canónico tiene que resolverse igual
        for slug_dp, nombre in DEPARTAMENTOS.items():
            self.assertEqual(nombre_departamento(slug_dp), nombre, slug_dp)
        self.assertEqual(len(DEPARTAMENTOS), 24)


class TestInventarioSenamhi(unittest.TestCase):
    def test_coordenada_sin_cero_inicial(self):
        # SENAMHI publica "lat": -.1172 (JSON inválido); antes tumbaba el departamento entero
        html = ('<script>var PruebaTest = [{"nom": "GUEPPI", "cate": "EMA", "lat": -.1172, '
                '"lon": -75.2503, "ico": "M", "cod": "101004", "estado": "AUTOMATICA"}];</script>')
        with mock.patch.object(senamhi._http, "get", lambda url, params=None: html):
            [e] = senamhi.inventario_estaciones("loreto")
        self.assertEqual((e.cod, e.lat, e.lon), ("101004", -0.1172, -75.2503))


class TestAlertas(unittest.TestCase):
    def test_lluvia_lleva_la_zona_recibida(self):
        a = alerts.evaluar_lluvia("X", "Est X", _serie("X", [2.0] * 24), zona="Piura")
        self.assertEqual((a["nivel"], a["zona"], a["valor"]), ("emergencia", "Piura", 48.0))

    def test_lluvia_intensa_de_una_hora(self):
        a = alerts.evaluar_lluvia("X", "Est X", _serie("X", [0.0] * 23 + [16.0]))
        self.assertEqual((a["nivel"], a["valor"], a["umbral"]), ("alerta", 16.0, alerts.LLUVIA_1H_ALERTA))

    def test_sin_lluvia_no_hay_alerta(self):
        self.assertIsNone(alerts.evaluar_lluvia("X", "Est X", _serie("X", [0.1] * 24)))

    def test_caudal_sin_departamento_no_inventa_zona(self):
        [a] = alerts.evaluar_caudal([_caudal("C", "", 15.0)])
        self.assertIsNone(a["zona"])
        self.assertEqual(a["nivel"], "alerta")


class _Cursor:
    def __init__(self, registro):
        self.registro = registro

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.registro.append((sql, params))

    def executemany(self, sql, filas):
        self.registro.append((sql, list(filas)))


class _Conexion:
    def __init__(self):
        self.registro = []

    def cursor(self):
        return _Cursor(self.registro)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]


class TestRecolectarYGuardar(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        config.ajustes.cache_clear()
        self.addCleanup(config.ajustes.cache_clear)
        env = mock.patch.dict("os.environ", {"SIMPAC_LLUVIA_DEPTS": "cajamarca"})
        env.start()
        self.addCleanup(env.stop)

    def _recolectar(self, ana_ok=True, ana_por_fecha=None):
        def inventario(dp):
            if dp == "piura":
                raise OSError("caído")
            if dp == "cajamarca":
                return [_estacion("111"), _estacion("222"), _estacion("333", estado="REAL")]
            return []

        def serie(e):
            if e.cod == "222":
                raise OSError("timeout")
            return _serie(e.cod, [3.0] * 24, [15.0] * 24)

        if ana_por_fecha is not None:   # {"ayer": [...], "hoy": [...]}; una lista None = esa fecha falla
            hoy = datetime.now(senamhi.HORA_PERU).date()

            def reporte(fecha):
                filas = ana_por_fecha["hoy" if fecha == hoy else "ayer"]
                if filas is None:
                    raise OSError("ANA caído")
                return filas
            ana_mock = mock.Mock(side_effect=reporte)
        elif ana_ok:
            ana_mock = mock.Mock(return_value=[_caudal("C1", "CAJAMARCA", 25.0)])
        else:
            ana_mock = mock.Mock(side_effect=OSError("ANA caído"))
        with mock.patch.object(senamhi, "inventario_estaciones", inventario), \
             mock.patch.object(senamhi, "datos_horarios", serie), \
             mock.patch.object(ana, "reporte_caudal", ana_mock), \
             mock.patch.object(igp, "ultimo", side_effect=OSError("IGP caído")), \
             mock.patch.object(noaa, "ultimo", return_value=None):
            return recolectar(), ana_mock

    def test_recolectar_anota_cada_falla_y_sigue(self):
        p, ana_mock = self._recolectar(ana_ok=False)
        self.assertEqual({e.cod for _, e in p.estaciones}, {"111", "222", "333"})
        self.assertIsNone(p.caudales)
        self.assertEqual(p.alertas_caudal, [])
        hoy = datetime.now(senamhi.HORA_PERU).date()
        ayer = hoy - timedelta(days=1)
        for falla in ("senamhi:inventario:piura", "senamhi:series:1/2", f"ana:{ayer}", f"ana:{hoy}", "igp"):
            self.assertIn(falla, p.fallas)
        # solo la estación que respondió se re-evaluó; su alerta lleva el departamento
        self.assertEqual(p.lluvia_ok, ["Est 111 (111)"])
        self.assertEqual([(a["referencia"], a["zona"]) for a in p.alertas_lluvia], [("Est 111 (111)", "Cajamarca")])
        # a ANA se le piden ayer y hoy, en fechas de Perú (no del reloj UTC del contenedor)
        self.assertEqual([c.args[0] for c in ana_mock.call_args_list], [ayer, hoy])

    def test_departamento_de_ana_normalizado(self):
        p, _ = self._recolectar()
        self.assertEqual(p.caudales[0][1].departamento, "Cajamarca")
        self.assertEqual(p.alertas_caudal[0]["zona"], "Cajamarca")

    def _guardar(self, p):
        conn = _Conexion()

        @contextmanager
        def falso_conectar():
            yield conn

        with mock.patch.object(guardar_mod, "conectar", falso_conectar):
            resumen = guardar(p)
        return conn, resumen

    def _borrados(self, conn):
        return {tipo: refs for tipo, refs, horas in conn.params(SQL_BORRAR_ALERTAS)}

    def test_ana_caida_no_borra_sus_alertas(self):
        p, _ = self._recolectar(ana_ok=False)
        conn, resumen = self._guardar(p)
        self.assertEqual(self._borrados(conn), {"caudal": [], "nivel_bajo": [], "lluvia": ["Est 111 (111)"]})
        self.assertIsNone(resumen["caudal"])

    def test_ana_ok_reemplaza_sus_alertas(self):
        p, _ = self._recolectar()
        conn, resumen = self._guardar(p)
        # las dos familias se limpian para las estaciones re-evaluadas: una estación puede
        # pasar de crecida a nivel bajo (o salir de la vaciante) sin dejar alertas viejas
        self.assertEqual(self._borrados(conn)["caudal"], ["C1 (Rio)"])
        self.assertEqual(self._borrados(conn)["nivel_bajo"], ["C1 (Rio)"])
        self.assertEqual(resumen["caudal"], 1)

    def test_estacion_que_sale_de_la_vaciante_no_deja_alerta(self):
        # ayer muy baja (alerta por nivel bajo), hoy por encima del umbral: se borra y no se repone
        bajo = _caudal("Nanay", "Loreto", 123.0, alerta=123.09, emergencia=122.06)
        repuesto = _caudal("Nanay", "Loreto", 123.26, alerta=123.09, emergencia=122.06)
        p, _ = self._recolectar(ana_por_fecha={"ayer": [bajo], "hoy": [repuesto]})
        self.assertEqual(p.alertas_caudal, [])
        conn, _ = self._guardar(p)
        self.assertEqual(self._borrados(conn)["nivel_bajo"], ["Nanay (Rio)"])

    def test_de_madrugada_el_reporte_de_ayer_sostiene_la_alerta(self):
        # a las 00:30 el reporte de hoy viene vacío: la emergencia de ayer no se borra
        # como si todo estuviera normal, se re-evalúa con la lectura de ayer
        p, _ = self._recolectar(ana_por_fecha={"ayer": [_caudal("C1", "Loreto", 25.0)], "hoy": []})
        self.assertEqual([a["nivel"] for a in p.alertas_caudal], ["emergencia"])
        conn, _ = self._guardar(p)
        self.assertEqual(self._borrados(conn)["caudal"], ["C1 (Rio)"])
        [filas] = conn.params(SQL_CAUDAL)
        self.assertEqual(filas[0][4], datetime.now(senamhi.HORA_PERU).date() - timedelta(days=1))

    def test_lectura_de_hoy_gana_salvo_que_venga_sin_dato(self):
        p, _ = self._recolectar(ana_por_fecha={
            "ayer": [_caudal("C1", "Loreto", 25.0), _caudal("C2", "Loreto", 25.0)],
            "hoy": [_caudal("C1", "Loreto", 5.0), _caudal("C2", "Loreto", None)],
        })
        valores = {c.estacion: c.valor for _, c in p.caudales}
        self.assertEqual(valores, {"C1": 5.0, "C2": 25.0})

    def test_estacion_ausente_conserva_su_alerta(self):
        # C9 no vino ni ayer ni hoy: su alerta no se toca (caduca sola a las 6 h)
        p, _ = self._recolectar(ana_por_fecha={"ayer": None, "hoy": [_caudal("C1", "Loreto", 5.0)]})
        conn, _ = self._guardar(p)
        self.assertNotIn("C9 (Rio)", self._borrados(conn)["caudal"])
        self.assertEqual(self._borrados(conn)["caudal"], ["C1 (Rio)"])

    def test_estaciones_se_guardan_con_su_departamento(self):
        p, _ = self._recolectar()
        conn, _ = self._guardar(p)
        [filas] = conn.params(SQL_ESTACION)
        self.assertEqual({f[5] for f in filas}, {"Cajamarca"})

    def test_pasada_vacia_no_falla(self):
        conn, resumen = self._guardar(Pasada())
        self.assertEqual(resumen["estaciones"], 0)
        self.assertEqual(self._borrados(conn), {"caudal": [], "nivel_bajo": [], "lluvia": []})

    def test_latido_con_el_resumen(self):
        p, _ = self._recolectar()
        conn, resumen = self._guardar(p)
        [(servicio, datos)] = conn.params(SQL_LATIDO)
        self.assertEqual(servicio, "ingesta")
        self.assertEqual(json.loads(datos), resumen)

    def test_icen_solo_se_reemplaza_por_uno_mas_nuevo(self):
        p = Pasada(icen=igp.PuntoICEN(2026, 5, 1.98))
        conn, _ = self._guardar(p)
        self.assertEqual(conn.params(SQL_ICEN), [("ICEN", "2026-05", 1.98, "Cálida moderada", "IGP")])
        self.assertIn("excluded.periodo > indice.periodo", SQL_ICEN)


class TestConfig(unittest.TestCase):
    def setUp(self):
        config.ajustes.cache_clear()
        self.addCleanup(config.ajustes.cache_clear)

    def test_lista_de_departamentos_de_lluvia(self):
        with mock.patch.dict("os.environ", {"SIMPAC_LLUVIA_DEPTS": " cajamarca, piura ,,"}):
            self.assertEqual(config.ajustes().lluvia_deptos, ("cajamarca", "piura"))

    def test_dsn_vacio_es_none(self):
        with mock.patch.dict("os.environ", {"SUPABASE_DB_URL": ""}):
            self.assertIsNone(config.ajustes().supabase_db_url)


if __name__ == "__main__":
    unittest.main()
