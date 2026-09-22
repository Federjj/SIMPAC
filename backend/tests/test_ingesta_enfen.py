"""
Tarea 'enfen': comunicado + ICEN del Informe Técnico, con la BD y los conectores simulados.

El informe se baja solo si es posterior al último leído (guardado en el latido). Comunicado
e informe van por separado: si uno falla, el otro se guarda igual; si fallan los dos, el
latido lo dice y la tarea lanza la excepción. Un informe descartado queda en el latido para
no volver a bajarlo antes de 24 h. Sin red ni psycopg: solo librería estándar.
"""
import json
import logging
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest import mock

from backend.connectors import enfen
from backend.ingesta import enfen as tarea
from backend.ingesta.guardar import SQL_ICEN, SQL_ICEN_TMP, SQL_INDICE, SQL_LATIDO

URL_IT_15 = "https://www.senamhi.gob.pe/load/file/02273SENA-54.pdf"
URL_IT_16 = "https://www.senamhi.gob.pe/load/file/02273SENA-55.pdf"
LEIDO_15 = enfen.ReferenciaInforme(url=URL_IT_15, publicado=date(2026, 8, 28), numero=15, fecha=date(2026, 8, 26))
LEIDO_16 = enfen.ReferenciaInforme(url=URL_IT_16, publicado=date(2026, 9, 14), numero=16, fecha=date(2026, 9, 11))
HACE_UN_RATO = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
FALLIDO_16 = enfen.ReferenciaInforme(url=URL_IT_16, publicado=date(2026, 9, 14), ts=HACE_UN_RATO,
                                     error="No se encontró la tabla del ICEN")
PREVIO = {"comunicado": "CO 15-2026", "fecha": "2026-08-28", "estado": "Alerta de El Niño Costero",
          "informe": LEIDO_15.a_json(), "icen": "2026-06", "icen_tmp": "2026-07"}


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
        self.conn, self.ultima = conn, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.registro.append((sql, params))
        self.ultima = sql

    def fetchone(self):
        assert self.ultima == tarea.SQL_LATIDO_PREVIO
        return None if self.conn.latido is None else (self.conn.latido,)


class _Conexion:
    """Anota cada sentencia; el SELECT del latido devuelve `latido` (jsonb ya decodificado)."""

    def __init__(self, latido=None):
        self.latido, self.registro = latido, []

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]


class TestTareaENFEN(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.INFO)   # el resumen de cada corrida; los avisos sí se prueban
        self.addCleanup(logging.disable, logging.NOTSET)

    def correr(self, latido=None, consulta=None, error=None, comunicado=None, error_comunicado=None):
        """
        Corre la tarea y devuelve (conexión, resumen del latido, mock del informe). Si la
        tarea lanza, la excepción queda en self.excepcion (el latido se revisa igual).
        """
        conn = _Conexion(latido)

        @contextmanager
        def falso_conectar():
            yield conn

        informe_mock = mock.Mock(return_value=consulta, side_effect=error)
        comunicado_mock = mock.Mock(return_value=comunicado or _comunicado(), side_effect=error_comunicado)
        self.excepcion = None
        with mock.patch.object(tarea, "conectar", falso_conectar), \
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

    def test_informe_nuevo_escribe_icen_y_temporal(self):
        conn, resumen, informe_mock = self.correr(latido=PREVIO, consulta=_nuevo())
        informe_mock.assert_called_once_with(LEIDO_15, None)   # lo leído según el latido anterior
        self.assertEqual(conn.params(SQL_ICEN), [("ICEN", "2026-07", 3.38, "Cálida fuerte", "ENFEN")])
        # el temporal va con la regla que no retrocede de mes
        self.assertEqual(conn.params(SQL_ICEN_TMP), [("ICEN_TMP", "2026-08", 3.73, "Cálida extraordinaria", "ENFEN")])
        self.assertEqual(conn.params(SQL_INDICE), [])
        self.assertEqual(len(conn.params(tarea.SQL_COMUNICADO)), 1)
        self.assertEqual(resumen, {
            "comunicado": "CO 16-2026", "fecha": "2026-09-14", "estado": "Alerta de El Niño Costero",
            "informe": {"url": URL_IT_16, "publicado": "2026-09-14", "numero": 16, "fecha": "2026-09-11"},
            "informe_fallido": None, "icen": "2026-07", "icen_tmp": "2026-08", "fallas": [], "avisos": [],
        })

    def test_informe_sin_cambios_no_toca_indice_y_conserva_lo_leido(self):
        previo = dict(PREVIO, informe=LEIDO_16.a_json(), icen="2026-07", icen_tmp="2026-08")
        conn, resumen, informe_mock = self.correr(latido=previo, consulta=_sin_cambios())
        informe_mock.assert_called_once_with(LEIDO_16, None)
        self.assertEqual(conn.params(SQL_ICEN) + conn.params(SQL_ICEN_TMP), [])
        self.assertEqual((resumen["informe"], resumen["icen"], resumen["icen_tmp"]),
                         (LEIDO_16.a_json(), "2026-07", "2026-08"))
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


if __name__ == "__main__":
    unittest.main()
