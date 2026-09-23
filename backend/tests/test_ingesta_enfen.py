"""
Tarea 'enfen': comunicado + ICEN del Informe Técnico, con la BD y los conectores simulados.

El informe se baja solo si es posterior al último leído (guardado en el latido). Comunicado
e informe van por separado: si uno falla, el otro se guarda igual; si fallan los dos, el
latido lo dice y la tarea lanza la excepción. Un informe descartado queda en el latido para
no volver a bajarlo antes de 24 h; una relectura que halla un informe más viejo deja la
marca serie_pendiente y se repite cada 24 h. Sin red ni psycopg: solo librería estándar.
"""
import json
import logging
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from unittest import mock

from backend.connectors import enfen
from backend.ingesta import enfen as tarea
from backend.ingesta.guardar import (AVISO_SIN_SERIE, SQL_HAY_ICEN_SERIE, SQL_ICEN, SQL_ICEN_SERIE, SQL_ICEN_TMP,
                                     SQL_INDICE, SQL_LATIDO)

URL_IT_15 = "https://www.senamhi.gob.pe/load/file/02273SENA-54.pdf"
URL_IT_16 = "https://www.senamhi.gob.pe/load/file/02273SENA-55.pdf"
LEIDO_15 = enfen.ReferenciaInforme(url=URL_IT_15, publicado=date(2026, 8, 28), numero=15, fecha=date(2026, 8, 26))
LEIDO_16 = enfen.ReferenciaInforme(url=URL_IT_16, publicado=date(2026, 9, 14), numero=16, fecha=date(2026, 9, 11))
HACE_UN_RATO = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
FALLIDO_16 = enfen.ReferenciaInforme(url=URL_IT_16, publicado=date(2026, 9, 14), ts=HACE_UN_RATO,
                                     error="No se encontró la tabla del ICEN")
PREVIO = {"comunicado": "CO 15-2026", "fecha": "2026-08-28", "estado": "Alerta de El Niño Costero",
          "informe": LEIDO_15.a_json(), "icen": "2026-06", "icen_tmp": "2026-07"}
AHORA = datetime(2026, 9, 22, 18, 0, tzinfo=timezone.utc)   # reloj de la tarea en las pruebas


def _comunicado():
    return enfen.ComunicadoENFEN(numero=16, anio=2026, fecha=date(2026, 9, 14), estado="Alerta de El Niño Costero",
                                 proximo=date(2026, 9, 28), url="https://cdn.www.gob.pe/co-16-2026.pdf",
                                 resumen="ENFEN sostiene que El Niño Costero continuaría.")


def _informe():
    return enfen.InformeICEN(url=URL_IT_16, numero=16, fecha=date(2026, 9, 11),
                             icen=[("2026-06", 2.66, "Cálida fuerte"), ("2026-07", 3.38, "Cálida fuerte")],
                             icen_tmp=("2026-08", 3.73, "Cálida extraordinaria"))


def _nuevo(avisos=()):
    return enfen.ConsultaInforme(_informe(), LEIDO_16, avisos=list(avisos))


def _sin_cambios(leido=LEIDO_16, avisos=()):
    return enfen.ConsultaInforme(None, leido, avisos=list(avisos))


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

    def executemany(self, sql, filas):
        filas = list(filas)
        self.conn.registro.append((sql, filas))
        # como psycopg: filas afectadas de todo el executemany (sin `escritas`, todas)
        self.rowcount = len(filas) if self.conn.escritas is None else self.conn.escritas

    def fetchone(self):
        if self.ultima == SQL_HAY_ICEN_SERIE:
            return (self.conn.meses_serie is not None,)
        if self.ultima == tarea.SQL_MESES_SERIE:
            assert self.conn.meses_serie is not None, "consulta icen_serie sin que exista"
            return (self.conn.meses_serie,)
        assert self.ultima == tarea.SQL_LATIDO_PREVIO, self.ultima
        return None if self.conn.latido is None else (self.conn.latido,)


class _Conexion:
    """
    Anota cada sentencia; el SELECT del latido devuelve `latido` (jsonb ya decodificado).
    meses_serie: meses del ENFEN que ya tiene icen_serie (None: la tabla no existe).
    escritas: filas que el executemany de icen_serie dice haber cambiado (None: todas).
    """

    def __init__(self, latido=None, meses_serie=12, escritas=None):
        self.latido, self.meses_serie, self.escritas, self.registro = latido, meses_serie, escritas, []

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]


class _BaseENFEN(unittest.TestCase):
    """Conectores y BD simulados (sin pruebas propias: las heredan las clases de abajo)."""

    def setUp(self):
        logging.disable(logging.INFO)   # el resumen de cada corrida; los avisos sí se prueban
        self.addCleanup(logging.disable, logging.NOTSET)

    def correr(self, latido=None, consulta=None, error=None, comunicado=None, error_comunicado=None,
               meses_serie=12, escritas=None, ahora=AHORA):
        """
        Corre la tarea y devuelve (conexión, resumen del latido, mock del informe). Si la
        tarea lanza, la excepción queda en self.excepcion (el latido se revisa igual).
        """
        conn = _Conexion(latido, meses_serie, escritas)

        @contextmanager
        def falso_conectar():
            yield conn

        informe_mock = mock.Mock(return_value=consulta, side_effect=error)
        comunicado_mock = mock.Mock(return_value=comunicado or _comunicado(), side_effect=error_comunicado)
        self.excepcion = None
        with mock.patch.object(tarea, "conectar", falso_conectar), \
             mock.patch.object(tarea, "_ahora", return_value=ahora), \
             mock.patch.object(enfen, "ultimo_comunicado", comunicado_mock), \
             mock.patch.object(enfen, "informe_tecnico_icen", informe_mock):
            try:
                devuelto = tarea.actualizar()
            except Exception as e:
                self.excepcion, devuelto = e, None
        [(servicio, datos)] = conn.params(SQL_LATIDO)   # el latido se escribe siempre
        self.assertEqual(servicio, "enfen")
        resumen = json.loads(datos)
        if devuelto is not None:
            self.assertEqual(resumen, devuelto)
        return conn, resumen, informe_mock


class TestTareaENFEN(_BaseENFEN):
    def test_informe_nuevo_escribe_icen_y_temporal(self):
        conn, resumen, informe_mock = self.correr(latido=PREVIO, consulta=_nuevo())
        informe_mock.assert_called_once_with(LEIDO_15, None)   # lo leído según el latido anterior
        self.assertEqual(conn.params(SQL_ICEN), [("ICEN", "2026-07", 3.38, "Cálida fuerte", "ENFEN")])
        # el temporal va con la regla que no retrocede de mes
        self.assertEqual(conn.params(SQL_ICEN_TMP), [("ICEN_TMP", "2026-08", 3.73, "Cálida extraordinaria", "ENFEN")])
        self.assertEqual(conn.params(SQL_INDICE), [])
        self.assertEqual(len(conn.params(tarea.SQL_COMUNICADO)), 1)
        # todos los meses de la tabla van a la serie con origen ENFEN (el ICENtmp no)
        self.assertEqual(conn.params(SQL_ICEN_SERIE), [[("2026-06", 2.66, "Cálida fuerte", "ENFEN"),
                                                        ("2026-07", 3.38, "Cálida fuerte", "ENFEN")]])
        self.assertEqual(resumen, {
            "comunicado": "CO 16-2026", "fecha": "2026-09-14", "estado": "Alerta de El Niño Costero",
            "informe": {"url": URL_IT_16, "publicado": "2026-09-14", "numero": 16, "fecha": "2026-09-11"},
            "informe_fallido": None, "icen": "2026-07", "icen_tmp": "2026-08", "icen_serie": 2,
            "serie_pendiente": None, "fallas": [], "avisos": [],
        })

    def test_icen_serie_del_latido_cuenta_los_meses_escritos_no_los_enviados(self):
        # se envían los 2 meses de la tabla, pero ya estaban iguales: el latido dice 0
        conn, resumen, _ = self.correr(latido=PREVIO, consulta=_nuevo(), escritas=0)
        [filas] = conn.params(SQL_ICEN_SERIE)
        self.assertEqual((len(filas), resumen["icen_serie"]), (2, 0))
        conn, resumen, _ = self.correr(latido=PREVIO, consulta=_nuevo(), escritas=1)
        self.assertEqual(resumen["icen_serie"], 1)

    def test_informe_sin_cambios_no_toca_indice_y_conserva_lo_leido(self):
        previo = dict(PREVIO, informe=LEIDO_16.a_json(), icen="2026-07", icen_tmp="2026-08")
        conn, resumen, informe_mock = self.correr(latido=previo, consulta=_sin_cambios())
        informe_mock.assert_called_once_with(LEIDO_16, None)
        self.assertEqual(conn.params(SQL_ICEN) + conn.params(SQL_ICEN_TMP) + conn.params(SQL_ICEN_SERIE), [])
        self.assertEqual((resumen["informe"], resumen["icen"], resumen["icen_tmp"], resumen["icen_serie"]),
                         (LEIDO_16.a_json(), "2026-07", "2026-08", 0))
        self.assertEqual(resumen["fallas"], [])

    def test_avisos_de_las_fuentes_llegan_aunque_el_informe_no_cambie(self):
        aviso = "informe SENAMHI: HTTPError: HTTP Error 503"
        _, resumen, _ = self.correr(latido=PREVIO, consulta=_sin_cambios(avisos=[aviso]))
        self.assertEqual(resumen["avisos"], [aviso])

    def test_latido_del_formato_anterior(self):
        # solo 'informe_url': se pasa como referencia sin fecha (el conector la completa)
        previo = {"comunicado": "CO 16-2026", "informe_url": URL_IT_16, "icen": "2026-07"}
        completado = enfen.ReferenciaInforme(url=URL_IT_16, publicado=date(2026, 9, 14))
        _, resumen, informe_mock = self.correr(latido=previo, consulta=_sin_cambios(completado))
        informe_mock.assert_called_once_with(enfen.ReferenciaInforme(url=URL_IT_16), None)
        self.assertEqual(resumen["informe"], {"url": URL_IT_16, "publicado": "2026-09-14"})
        self.assertNotIn("informe_url", resumen)

    def test_sin_latido_previo(self):
        _, resumen, informe_mock = self.correr(latido=None, consulta=_nuevo())
        informe_mock.assert_called_once_with(None, None)
        self.assertEqual(resumen["informe"]["url"], URL_IT_16)

    def test_informe_descartado_queda_en_el_latido_y_el_comunicado_se_guarda(self):
        e = enfen.InformeDescartado("No se encontró la tabla del ICEN", FALLIDO_16,
                                    avisos=["informe gob.pe: HTTPError: HTTP Error 503"])
        with self.assertLogs(tarea.log, logging.WARNING):   # "ENFEN con fallas parciales"
            conn, resumen, _ = self.correr(latido=PREVIO, error=e)
        self.assertIsNone(self.excepcion)   # solo falló el informe
        self.assertEqual(len(conn.params(tarea.SQL_COMUNICADO)), 1)
        self.assertEqual(conn.params(SQL_ICEN) + conn.params(SQL_ICEN_TMP), [])
        # lo leído no cambia (la próxima corrida no baja el N° 15) y el descartado se anota con la hora
        self.assertEqual((resumen["informe"], resumen["icen"]), (LEIDO_15.a_json(), "2026-06"))
        self.assertEqual(resumen["informe_fallido"], {
            "url": URL_IT_16, "publicado": "2026-09-14", "ts": "2026-09-22T12:00:00+00:00",
            "error": "No se encontró la tabla del ICEN"})
        self.assertEqual(resumen["fallas"], ["informe"])
        self.assertEqual(resumen["avisos"], ["informe gob.pe: HTTPError: HTTP Error 503",
                                             "informe técnico: InformeDescartado: No se encontró la tabla del ICEN"])

    def test_descartado_se_pasa_a_la_corrida_siguiente_y_sigue_en_espera(self):
        previo = dict(PREVIO, informe_fallido=FALLIDO_16.a_json())
        espera = enfen.ConsultaInforme(None, LEIDO_15, en_espera=True, avisos=["Informe Técnico en espera hasta ..."])
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen, informe_mock = self.correr(latido=previo, consulta=espera)
        informe_mock.assert_called_once_with(LEIDO_15, FALLIDO_16)
        self.assertEqual(resumen["informe_fallido"], FALLIDO_16.a_json())   # misma hora: la espera no se alarga
        self.assertEqual(resumen["fallas"], ["informe"])
        self.assertIsNone(self.excepcion)

    def test_informe_leido_borra_el_descartado(self):
        previo = dict(PREVIO, informe_fallido=FALLIDO_16.a_json())
        _, resumen, _ = self.correr(latido=previo, consulta=_nuevo())
        self.assertIsNone(resumen["informe_fallido"])
        self.assertEqual(resumen["informe"], LEIDO_16.a_json())

    def test_falla_de_red_del_informe_conserva_lo_anterior(self):
        previo = dict(PREVIO, informe_fallido=FALLIDO_16.a_json())
        with self.assertLogs(tarea.log, logging.WARNING) as logs:
            _, resumen, _ = self.correr(latido=previo, error=RuntimeError("No se pudo bajar el Informe Técnico ENFEN."))
        self.assertIn("No se pudo bajar", logs.output[0])
        self.assertEqual((resumen["informe"], resumen["informe_fallido"]), (LEIDO_15.a_json(), FALLIDO_16.a_json()))
        self.assertEqual(resumen["avisos"], ["informe técnico: RuntimeError: No se pudo bajar el Informe Técnico ENFEN."])

    def test_si_falla_el_comunicado_el_informe_se_procesa_igual(self):
        with self.assertLogs(tarea.log, logging.ERROR):
            conn, resumen, informe_mock = self.correr(
                latido=PREVIO, consulta=_nuevo(), error_comunicado=RuntimeError("No se pudo obtener el último comunicado"))
        self.assertIsNone(self.excepcion)
        informe_mock.assert_called_once()
        self.assertEqual(conn.params(tarea.SQL_COMUNICADO), [])
        self.assertEqual(len(conn.params(SQL_ICEN)), 1)
        self.assertEqual(len(conn.params(SQL_ICEN_TMP)), 1)
        # se conservan los datos del comunicado anterior
        self.assertEqual((resumen["comunicado"], resumen["fecha"], resumen["estado"]),
                         ("CO 15-2026", "2026-08-28", "Alerta de El Niño Costero"))
        self.assertEqual(resumen["fallas"], ["comunicado"])
        self.assertEqual(resumen["avisos"], ["comunicado: RuntimeError: No se pudo obtener el último comunicado"])

    def test_si_falla_el_comunicado_sin_latido_previo(self):
        with self.assertLogs(tarea.log, logging.ERROR):
            _, resumen, _ = self.correr(consulta=_nuevo(), error_comunicado=RuntimeError("todas caídas"))
        self.assertEqual((resumen["comunicado"], resumen["fecha"], resumen["estado"]), (None, None, None))

    def test_si_fallan_comunicado_e_informe_el_latido_lo_dice_y_la_tarea_falla(self):
        for error, consulta in ((RuntimeError("No se pudo descubrir el último Informe Técnico ENFEN."), None),
                                (enfen.InformeDescartado("sin tabla", FALLIDO_16), None),
                                (None, enfen.ConsultaInforme(None, LEIDO_15, en_espera=True))):
            with self.subTest(error=error, consulta=consulta):
                with self.assertLogs(tarea.log, logging.ERROR):
                    conn, resumen, _ = self.correr(latido=PREVIO, consulta=consulta, error=error,
                                                   error_comunicado=RuntimeError("todas las fuentes caídas"))
                self.assertIsInstance(self.excepcion, RuntimeError)
                self.assertIn("fallaron el comunicado y el Informe Técnico", str(self.excepcion))
                self.assertEqual(resumen["fallas"], ["comunicado", "informe"])
                self.assertEqual(resumen["comunicado"], "CO 15-2026")
                self.assertEqual(conn.params(tarea.SQL_COMUNICADO), [])

    def test_comunicado_caido_e_informe_sin_cambios_no_es_falla_total(self):
        with self.assertLogs(tarea.log, logging.ERROR):
            _, resumen, _ = self.correr(latido=PREVIO, consulta=_sin_cambios(LEIDO_15),
                                        error_comunicado=RuntimeError("todas las fuentes caídas"))
        self.assertIsNone(self.excepcion)
        self.assertEqual(resumen["fallas"], ["comunicado"])

    def test_avisos_del_comunicado_y_del_informe(self):
        c = _comunicado()
        c.avisos = ["gob.pe: HTTPError: HTTP Error 404"]
        _, resumen, _ = self.correr(comunicado=c, consulta=_nuevo(avisos=["informe SENAMHI: HTTPError: HTTP Error 503"]))
        self.assertEqual(resumen["avisos"], ["gob.pe: HTTPError: HTTP Error 404",
                                             "informe SENAMHI: HTTPError: HTTP Error 503"])
        self.assertEqual(resumen["fallas"], [])


# Latido real del 22-09-2026: el IT 16 se leyó con la versión anterior (sin número ni portada).
LEIDO_16_VIEJO_FORMATO = enfen.ReferenciaInforme(url=URL_IT_16, publicado=date(2026, 9, 14))
PREVIO_16 = dict(PREVIO, informe=LEIDO_16_VIEJO_FORMATO.a_json(), icen="2026-07", icen_tmp="2026-08")
URL_IT_16_GOBPE = "https://cdn.www.gob.pe/uploads/document/file/9000001/IT-16-2026.pdf"


def _informe_15():
    return enfen.InformeICEN(url=URL_IT_15, numero=15, fecha=date(2026, 8, 26),
                             icen=[("2026-05", 1.98, "Cálida moderada"), ("2026-06", 2.66, "Cálida fuerte")],
                             icen_tmp=("2026-07", 3.30, "Cálida fuerte"))


# Lo que devuelve un listado atrasado al releer: el IT 15, más viejo que el leído (IT 16).
REF_15 = enfen.ReferenciaInforme(url=URL_IT_15, publicado=date(2026, 8, 28), numero=15, fecha=date(2026, 8, 26))
PREVIO_LEIDO_16 = dict(PREVIO_16, informe=LEIDO_16.a_json())
URL_IT_17 = "https://www.senamhi.gob.pe/load/file/02273SENA-56.pdf"
LEIDO_17 = enfen.ReferenciaInforme(url=URL_IT_17, publicado=date(2026, 9, 28), numero=17, fecha=date(2026, 9, 25))


def _viejo():
    return enfen.ConsultaInforme(_informe_15(), REF_15)


def _nuevo_17():
    informe = enfen.InformeICEN(url=URL_IT_17, numero=17, fecha=date(2026, 9, 25),
                                icen=[("2026-07", 3.38, "Cálida fuerte"), ("2026-08", 3.71, "Cálida extraordinaria")],
                                icen_tmp=("2026-09", 3.80, "Cálida extraordinaria"))
    return enfen.ConsultaInforme(informe, LEIDO_17)


def _marca(ts):
    """serie_pendiente tal como queda en el latido: el IT 15 que halló la relectura y cuándo."""
    return replace(REF_15, ts=ts).a_json()


def _aviso_pendiente(ts):
    return ("icen_serie incompleta: al releer el Informe Técnico vigente se halló uno anterior al leído "
            f"({URL_IT_15}); se vuelve a releer desde {ts + timedelta(hours=24):%Y-%m-%d %H:%M} UTC")


class TestSerieENFEN(_BaseENFEN):
    """icen_serie: los meses de cada informe nuevo y el relleno único con el informe vigente."""

    def test_serie_vacia_relee_el_informe_vigente_una_vez(self):
        # 1ra corrida tras la migración: la serie no tiene meses del ENFEN -> se pide el
        # informe como si no se hubiera leído (leido=None), respetando el descartado
        conn, resumen, informe_mock = self.correr(latido=PREVIO_16, consulta=_nuevo(), meses_serie=0)
        informe_mock.assert_called_once_with(None, None)
        [filas] = conn.params(SQL_ICEN_SERIE)
        self.assertEqual([(f[0], f[3]) for f in filas], [("2026-06", "ENFEN"), ("2026-07", "ENFEN")])
        self.assertEqual(resumen["icen_serie"], 2)
        # el mismo informe: lo leído gana número y portada, y el indice solo se refresca (mismo mes)
        self.assertEqual(resumen["informe"], LEIDO_16.a_json())
        self.assertEqual(conn.params(SQL_ICEN), [("ICEN", "2026-07", 3.38, "Cálida fuerte", "ENFEN")])
        self.assertEqual(resumen["fallas"], [])
        # 2da corrida: la serie ya tiene los meses -> vuelve la regla de no bajarlo otra vez
        previo = resumen
        conn, resumen, informe_mock = self.correr(latido=previo, consulta=_sin_cambios(), meses_serie=2)
        informe_mock.assert_called_once_with(LEIDO_16, None)
        self.assertEqual((conn.params(SQL_ICEN_SERIE), resumen["icen_serie"]), ([], 0))

    def test_relectura_respeta_el_informe_en_espera(self):
        previo = dict(PREVIO_16, informe_fallido=FALLIDO_16.a_json())
        espera = enfen.ConsultaInforme(None, None, en_espera=True, avisos=["Informe Técnico en espera hasta ..."])
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen, informe_mock = self.correr(latido=previo, consulta=espera, meses_serie=0)
        informe_mock.assert_called_once_with(None, FALLIDO_16)
        # lo leído no se pierde aunque la consulta vuelva sin referencia
        self.assertEqual(resumen["informe"], LEIDO_16_VIEJO_FORMATO.a_json())
        self.assertEqual(conn.params(SQL_ICEN_SERIE), [])
        self.assertEqual(resumen["fallas"], ["informe"])

    def test_relectura_con_falla_de_red_conserva_lo_leido(self):
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen, _ = self.correr(latido=PREVIO_16, error=RuntimeError("No se pudo bajar"), meses_serie=0)
        self.assertEqual(resumen["informe"], LEIDO_16_VIEJO_FORMATO.a_json())
        self.assertEqual(conn.params(SQL_ICEN_SERIE), [])

    def test_relectura_desde_otra_url_anota_alias(self):
        # el mismo IT 16 servido por gob.pe (publicado 2 días después): alias, no uno nuevo
        ref = enfen.ReferenciaInforme(url=URL_IT_16_GOBPE, publicado=date(2026, 9, 16), numero=16,
                                      fecha=date(2026, 9, 11))
        _, resumen, _ = self.correr(latido=PREVIO_16, consulta=enfen.ConsultaInforme(_informe(), ref), meses_serie=0)
        self.assertEqual(resumen["informe"], {"url": URL_IT_16_GOBPE, "publicado": "2026-09-16", "numero": 16,
                                              "fecha": "2026-09-11", "alias": [URL_IT_16]})
        self.assertEqual(resumen["icen_serie"], 2)

    def test_relectura_que_halla_uno_mas_nuevo_es_un_informe_nuevo(self):
        # lo leído era el IT 15 y el listado ya trae el 16
        conn, resumen, informe_mock = self.correr(latido=PREVIO, consulta=_nuevo(), meses_serie=0)
        informe_mock.assert_called_once_with(None, None)
        self.assertEqual(resumen["informe"], LEIDO_16.a_json())
        self.assertEqual(len(conn.params(SQL_ICEN)), 1)
        self.assertEqual(len(conn.params(SQL_ICEN_TMP)), 1)

    def test_relectura_que_halla_uno_mas_viejo_no_retrocede(self):
        # un listado atrasado devuelve el IT 15: sus meses llenan la serie (así no se relee
        # cada 6 h), pero lo leído, el latido y el indice siguen en el IT 16
        leido = LEIDO_16.a_json()
        previo = dict(PREVIO_16, informe=leido)
        ref_15 = enfen.ReferenciaInforme(url=URL_IT_15, publicado=date(2026, 8, 28), numero=15, fecha=date(2026, 8, 26))
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen, _ = self.correr(latido=previo, consulta=enfen.ConsultaInforme(_informe_15(), ref_15),
                                           meses_serie=0)
        self.assertEqual(resumen["informe"], leido)
        self.assertEqual(conn.params(SQL_ICEN) + conn.params(SQL_ICEN_TMP), [])
        self.assertEqual((resumen["icen"], resumen["icen_tmp"]), ("2026-07", "2026-08"))
        [filas] = conn.params(SQL_ICEN_SERIE)
        self.assertEqual([f[0] for f in filas], ["2026-05", "2026-06"])

    def test_relectura_que_halla_uno_mas_viejo_deja_la_marca_y_avisa(self):
        # a la serie le falta 2026-07 (solo está en el IT 16): el latido lo dice y lo recuerda
        with self.assertLogs(tarea.log, logging.WARNING):
            _, resumen, _ = self.correr(latido=PREVIO_LEIDO_16, consulta=_viejo(), meses_serie=0)
        self.assertEqual(resumen["serie_pendiente"], {
            "url": URL_IT_15, "publicado": "2026-08-28", "numero": 15, "fecha": "2026-08-26",
            "ts": "2026-09-22T18:00:00+00:00"})
        self.assertEqual(resumen["avisos"], [_aviso_pendiente(AHORA)])
        self.assertTrue(resumen["avisos"][0].endswith("desde 2026-09-23 18:00 UTC"))
        self.assertEqual(resumen["fallas"], [])   # no es una falla: el informe vigente está leído

    def test_serie_incompleta_se_relee_cada_24_h_hasta_dar_con_el_vigente(self):
        # 1) la relectura halla el IT 15: sus meses van a la serie y queda la marca
        with self.assertLogs(tarea.log, logging.WARNING):
            _, r1, _ = self.correr(latido=PREVIO_LEIDO_16, consulta=_viejo(), meses_serie=0)
        # 2) 6 h después la serie ya tiene meses del ENFEN, pero la marca sigue: no se relee
        # antes de 24 h (se consulta como siempre, con lo leído) y el aviso se mantiene
        conn, r2, informe_mock = self.correr(latido=r1, consulta=_sin_cambios(), meses_serie=2,
                                             ahora=AHORA + timedelta(hours=6))
        informe_mock.assert_called_once_with(LEIDO_16, None)
        self.assertEqual(conn.params(SQL_ICEN_SERIE), [])
        self.assertEqual(r2["serie_pendiente"], _marca(AHORA))   # misma hora: la espera no se alarga
        self.assertEqual(r2["avisos"], [_aviso_pendiente(AHORA)])
        # 3) pasadas 24 h se relee y da el IT 16: sus meses completan la serie y la marca se borra
        conn, r3, informe_mock = self.correr(latido=r2, consulta=_nuevo(), meses_serie=2,
                                             ahora=AHORA + timedelta(hours=25))
        informe_mock.assert_called_once_with(None, None)
        [filas] = conn.params(SQL_ICEN_SERIE)
        self.assertEqual([f[0] for f in filas], ["2026-06", "2026-07"])
        self.assertEqual((r3["serie_pendiente"], r3["avisos"], r3["informe"]), (None, [], LEIDO_16.a_json()))
        # 4) sin marca y con meses: vuelve la regla de no bajarlo otra vez
        _, _, informe_mock = self.correr(latido=r3, consulta=_sin_cambios(), meses_serie=3,
                                         ahora=AHORA + timedelta(hours=31))
        informe_mock.assert_called_once_with(LEIDO_16, None)

    def test_relectura_que_vuelve_a_hallar_el_viejo_renueva_la_espera(self):
        previo = dict(PREVIO_LEIDO_16, serie_pendiente=_marca(AHORA - timedelta(hours=25)))
        with self.assertLogs(tarea.log, logging.WARNING):
            _, resumen, informe_mock = self.correr(latido=previo, consulta=_viejo(), meses_serie=2)
        informe_mock.assert_called_once_with(None, None)
        self.assertEqual(resumen["serie_pendiente"], _marca(AHORA))
        self.assertEqual(resumen["avisos"], [_aviso_pendiente(AHORA)])
        self.assertEqual(resumen["informe"], LEIDO_16.a_json())

    def test_relectura_pendiente_con_falla_de_red_conserva_la_marca(self):
        marca = _marca(AHORA - timedelta(hours=25))
        previo = dict(PREVIO_LEIDO_16, serie_pendiente=marca)
        with self.assertLogs(tarea.log, logging.WARNING):
            _, resumen, informe_mock = self.correr(latido=previo, error=RuntimeError("No se pudo bajar"),
                                                   meses_serie=2)
        informe_mock.assert_called_once_with(None, None)
        self.assertEqual(resumen["serie_pendiente"], marca)   # se reintenta en la próxima corrida
        self.assertEqual(resumen["avisos"][-1], _aviso_pendiente(AHORA - timedelta(hours=25)))
        self.assertEqual(resumen["fallas"], ["informe"])

    def test_un_informe_nuevo_borra_la_marca_sin_esperar_la_relectura(self):
        # el IT 17 trae los meses más nuevos: la serie queda al día aunque no se haya releído
        previo = dict(PREVIO_LEIDO_16, serie_pendiente=_marca(AHORA - timedelta(hours=1)))
        conn, resumen, informe_mock = self.correr(latido=previo, consulta=_nuevo_17(), meses_serie=2)
        informe_mock.assert_called_once_with(LEIDO_16, None)
        self.assertEqual(len(conn.params(SQL_ICEN_SERIE)), 1)
        self.assertEqual((resumen["serie_pendiente"], resumen["avisos"]), (None, []))
        self.assertEqual(resumen["informe"], LEIDO_17.a_json())

    def test_sin_latido_previo_no_hace_falta_releer(self):
        _, _, informe_mock = self.correr(latido=None, consulta=_nuevo(), meses_serie=0)
        informe_mock.assert_called_once_with(None, None)

    def test_sin_la_tabla_no_relee_ni_escribe_la_serie(self):
        conn, resumen, informe_mock = self.correr(latido=PREVIO_16, consulta=_nuevo(), meses_serie=None)
        informe_mock.assert_called_once_with(LEIDO_16_VIEJO_FORMATO, None)   # sin relectura
        self.assertEqual(conn.params(tarea.SQL_MESES_SERIE) + conn.params(SQL_ICEN_SERIE), [])
        # el resto se guarda igual y el latido avisa que falta la migración
        self.assertEqual(len(conn.params(SQL_ICEN)), 1)
        self.assertEqual(len(conn.params(tarea.SQL_COMUNICADO)), 1)
        self.assertEqual((resumen["icen_serie"], resumen["avisos"], resumen["fallas"]), (0, [AVISO_SIN_SERIE], []))
        self.assertIsNone(self.excepcion)

    def test_serie_con_meses_no_relee(self):
        _, _, informe_mock = self.correr(latido=PREVIO_16, consulta=_sin_cambios(), meses_serie=1)
        informe_mock.assert_called_once_with(LEIDO_16_VIEJO_FORMATO, None)


if __name__ == "__main__":
    unittest.main()
