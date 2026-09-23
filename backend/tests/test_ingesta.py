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
from backend.ingesta.guardar import (SQL_ALERTA, SQL_BORRAR_ALERTAS, SQL_CAUDAL, SQL_ESTACION, SQL_HAY_ICEN_SERIE,
                                     SQL_ICEN, SQL_ICEN_SERIE, SQL_LATIDO, guardar)
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
    def test_caudal_sin_departamento_no_inventa_zona(self):
        [a] = alerts.evaluar_caudal([_caudal("C", "", 15.0)])
        self.assertIsNone(a["zona"])
        self.assertEqual(a["nivel"], "alerta")


class _Cursor:
    def __init__(self, conn):
        self.conn, self.registro, self.ultima, self.rowcount = conn, conn.registro, None, -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.registro.append((sql, params))
        self.ultima = sql

    def executemany(self, sql, filas):
        filas = list(filas)
        self.registro.append((sql, filas))
        # como psycopg: filas afectadas de todo el executemany (sin `escritas`, todas)
        self.rowcount = len(filas) if self.conn.escritas is None else self.conn.escritas

    def fetchone(self):
        assert self.ultima == SQL_HAY_ICEN_SERIE, self.ultima
        return (self.conn.hay_serie,)


class _Conexion:
    """
    Anota cada sentencia. hay_serie: si la tabla icen_serie existe (migración aplicada).
    escritas: filas que dice haber cambiado cada executemany (None: todas las enviadas).
    """

    def __init__(self, hay_serie=True, escritas=None):
        self.registro, self.hay_serie, self.escritas = [], hay_serie, escritas

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]


class _BaseIngesta(unittest.TestCase):
    """Fuentes y BD simuladas (sin pruebas propias: las heredan las clases de abajo)."""

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        config.ajustes.cache_clear()
        self.addCleanup(config.ajustes.cache_clear)
        env = mock.patch.dict("os.environ", {"SIMPAC_LLUVIA_DEPTS": "cajamarca"})
        env.start()
        self.addCleanup(env.stop)

    def _recolectar(self, ana_ok=True, ana_por_fecha=None, icen=None):
        """icen: lista de PuntoICEN que devuelve el ICEN.txt (None: el IGP está caído)."""
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
        igp_mock = (mock.Mock(side_effect=OSError("IGP caído")) if icen is None
                    else mock.Mock(return_value=icen))
        with mock.patch.object(senamhi, "inventario_estaciones", inventario), \
             mock.patch.object(senamhi, "datos_horarios", serie), \
             mock.patch.object(ana, "reporte_caudal", ana_mock), \
             mock.patch.object(igp, "icen", igp_mock), \
             mock.patch.object(igp, "ultimo", side_effect=AssertionError("baja el ICEN.txt otra vez")), \
             mock.patch.object(noaa, "ultimo", return_value=None):
            p = recolectar()
        self.igp_mock = igp_mock
        return p, ana_mock

    def _guardar(self, p, hay_serie=True, escritas=None):
        conn = _Conexion(hay_serie, escritas)

        @contextmanager
        def falso_conectar():
            yield conn

        with mock.patch.object(guardar_mod, "conectar", falso_conectar):
            resumen = guardar(p)
        return conn, resumen


class TestRecolectarYGuardar(_BaseIngesta):
    def test_recolectar_anota_cada_falla_y_sigue(self):
        p, ana_mock = self._recolectar(ana_ok=False)
        self.assertEqual({e.cod for _, e in p.estaciones}, {"111", "222", "333"})
        self.assertIsNone(p.caudales)
        self.assertEqual(p.alertas_caudal, [])
        hoy = datetime.now(senamhi.HORA_PERU).date()
        ayer = hoy - timedelta(days=1)
        for falla in ("senamhi:inventario:piura", "senamhi:series:1/2", f"ana:{ayer}", f"ana:{hoy}", "igp"):
            self.assertIn(falla, p.fallas)
        # solo se guarda la serie de la estación que respondió
        self.assertEqual({f[0] for f in p.lluvia}, {"111"})
        # a ANA se le piden ayer y hoy, en fechas de Perú (no del reloj UTC del contenedor)
        self.assertEqual([c.args[0] for c in ana_mock.call_args_list], [ayer, hoy])

    def test_departamento_de_ana_normalizado(self):
        p, _ = self._recolectar()
        self.assertEqual(p.caudales[0][1].departamento, "Cajamarca")
        self.assertEqual(p.alertas_caudal[0]["zona"], "Cajamarca")

    def _borrados(self, conn):
        return {tipo: refs for tipo, refs, horas in conn.params(SQL_BORRAR_ALERTAS)}

    def test_ana_caida_no_borra_sus_alertas(self):
        p, _ = self._recolectar(ana_ok=False)
        conn, resumen = self._guardar(p)
        self.assertEqual(self._borrados(conn), {"caudal": [], "nivel_bajo": []})
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
        self.assertEqual(self._borrados(conn), {"caudal": [], "nivel_bajo": []})

    def test_ingesta_no_toca_alertas_de_lluvia(self):
        # 3 mm cada hora (72 mm en 24 h) eran una emergencia con los umbrales retirados de
        # SIMPAC; ahora las de lluvia las escribe solo la tarea lluvia_nacional
        p, _ = self._recolectar()
        self.assertEqual(len(p.lluvia), 24)
        conn, resumen = self._guardar(p)
        familias = {"caudal", "nivel_bajo"}
        self.assertLessEqual(set(self._borrados(conn)), familias)
        [filas] = conn.params(SQL_ALERTA)
        self.assertLessEqual({f[0] for f in filas}, familias)
        self.assertEqual(resumen["alertas"], 1)   # la de caudal de C1

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


def _meses(desde_anio, desde_mes, n, valor=0.1):
    """n PuntoICEN mensuales consecutivos desde (desde_anio, desde_mes)."""
    k0 = desde_anio * 12 + desde_mes - 1
    return [igp.PuntoICEN((k0 + i) // 12, (k0 + i) % 12 + 1, round(valor + i / 100, 2)) for i in range(n)]


class TestSerieICENIngesta(_BaseIngesta):
    """La ingesta horaria guarda los últimos 36 meses del IGP en icen_serie."""

    def test_el_icen_txt_se_baja_una_vez_y_da_ultimo_y_serie(self):
        # ICEN.txt desde 1950 hasta mayo de 2026: 917 filas, como el real
        p, _ = self._recolectar(icen=_meses(1950, 1, 917))
        self.igp_mock.assert_called_once_with()
        self.assertEqual(len(p.icen_serie), 36)
        primero, ultimo = p.icen_serie[0], p.icen_serie[-1]
        self.assertEqual(((primero.anio, primero.mes), (ultimo.anio, ultimo.mes)), ((2023, 6), (2026, 5)))
        self.assertIs(p.icen, ultimo)
        self.assertNotIn("igp", p.fallas)
        self.assertEqual(p.avisos, [])

    def test_igp_caido_no_deja_serie(self):
        p, _ = self._recolectar()   # igp.icen lanza OSError
        self.assertEqual((p.icen, p.icen_serie), (None, []))
        self.assertIn("igp", p.fallas)
        conn, resumen = self._guardar(p)
        self.assertEqual(conn.params(SQL_ICEN_SERIE) + conn.params(SQL_HAY_ICEN_SERIE), [])
        self.assertEqual(resumen["icen_serie"], 0)

    def test_guardar_escribe_la_serie_con_origen_igp_en_orden(self):
        p, _ = self._recolectar(icen=_meses(2023, 1, 41, valor=-0.5))
        conn, resumen = self._guardar(p)
        [filas] = conn.params(SQL_ICEN_SERIE)
        self.assertEqual(len(filas), 36)
        self.assertEqual(filas[0], ("2023-06", -0.45, "Neutra", "IGP"))
        self.assertEqual(filas[-1], ("2026-05", -0.1, "Neutra", "IGP"))
        self.assertEqual([f[0] for f in filas], sorted(f[0] for f in filas))
        self.assertEqual({f[3] for f in filas}, {"IGP"})
        # el último mes también va a indice, como antes
        self.assertEqual(conn.params(SQL_ICEN), [("ICEN", "2026-05", -0.1, "Neutra", "IGP")])
        self.assertEqual((resumen["icen_serie"], resumen["avisos"]), (36, []))

    def test_latido_cuenta_los_meses_escritos_no_los_enviados(self):
        # cada hora se reenvían los mismos 36 meses: si ninguno cambió, el latido dice 0
        p, _ = self._recolectar(icen=_meses(2023, 1, 41))
        conn, resumen = self._guardar(p, escritas=0)
        [filas] = conn.params(SQL_ICEN_SERIE)
        self.assertEqual((len(filas), resumen["icen_serie"]), (36, 0))
        [(_, datos)] = conn.params(SQL_LATIDO)
        self.assertEqual(json.loads(datos)["icen_serie"], 0)
        _, resumen = self._guardar(p, escritas=1)   # p. ej. el IGP corrigió un mes
        self.assertEqual(resumen["icen_serie"], 1)

    def test_mes_futuro_del_icen_txt_no_llega_a_indice_ni_a_la_serie(self):
        # ICEN.txt real hasta 2026-05 más una fila de 2099 (dañada o alterada: se baja por
        # http). Antes era el "último mes": corría la ventana y dejaba fijo el ICEN de indice.
        p, _ = self._recolectar(icen=_meses(1950, 1, 917) + [igp.PuntoICEN(2099, 1, 0.3)])
        self.assertEqual((p.icen.anio, p.icen.mes), (2026, 5))
        self.assertEqual((len(p.icen_serie), p.icen_serie[0].anio, p.icen_serie[0].mes), (36, 2023, 6))
        self.assertEqual(p.avisos, ["igp: 1 filas del ICEN.txt descartadas (mes imposible o futuro, o valor imposible)"])
        conn, _ = self._guardar(p)
        self.assertEqual([x[1] for x in conn.params(SQL_ICEN)], ["2026-05"])
        [filas] = conn.params(SQL_ICEN_SERIE)
        self.assertEqual(max(f[0] for f in filas), "2026-05")

    def test_sin_la_tabla_la_serie_se_salta_y_el_resto_se_guarda(self):
        # migración pendiente: no se intenta el INSERT (tumbaría la transacción entera)
        p, _ = self._recolectar(icen=_meses(2025, 1, 17))
        conn, resumen = self._guardar(p, hay_serie=False)
        self.assertEqual(conn.params(SQL_ICEN_SERIE), [])
        self.assertEqual(len(conn.params(SQL_ICEN)), 1)
        self.assertEqual(len(conn.params(SQL_ESTACION)), 1)
        self.assertEqual(resumen["avisos"], [guardar_mod.AVISO_SIN_SERIE])
        self.assertEqual(resumen["icen_serie"], 0)
        [(_, datos)] = conn.params(SQL_LATIDO)
        self.assertEqual(json.loads(datos)["avisos"], [guardar_mod.AVISO_SIN_SERIE])

    def test_filas_danadas_del_icen_txt_se_descartan_con_aviso(self):
        puntos = _meses(2025, 1, 12) + [igp.PuntoICEN(2026, 13, 0.5), igp.PuntoICEN(2026, 1, float("nan")),
                                        igp.PuntoICEN(2026, 2, 99.0)]
        p, _ = self._recolectar(icen=puntos)
        self.assertEqual((p.icen.anio, p.icen.mes), (2025, 12))   # la basura no es "el último mes"
        self.assertEqual(p.avisos, ["igp: 3 filas del ICEN.txt descartadas (mes imposible o futuro, o valor imposible)"])


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
