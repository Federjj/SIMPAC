"""
Lluvia nacional: capa de umbrales de SENAMHI (WFS), fechas del visor de lluvia observada y
huella de prec_1_all_points, emparejamiento con nuestra tabla estacion y la tarea
'lluvia_nacional' con la BD simulada (incluidos el latido anterior y las alertas de lluvia).
Sin red ni psycopg: solo librería estándar.
"""
import json
import logging
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from unittest import mock

from backend.connectors import _http
from backend.connectors import senamhi_umbrales as su
from backend.ingesta import lluvia_nacional as tarea
from backend.ingesta.guardar import SQL_LATIDO
from backend.ingesta.lluvia_nacional import EstacionRef

# 22-09-2026 19:40 en Lima
AHORA = datetime(2026, 9, 23, 0, 40, tzinfo=timezone.utc)


def _punto(nombre, lon, lat, pp=0, umbral=5, pp_acum=0, hora="19:00:00", fecha="22/09/2026",
           departamento="CAJAMARCA", alt=2500):
    return {"type": "Feature", "id": "umbrales_precipitacion.fid-x",
            "geometry": {"type": "Point", "coordinates": [lon, lat, alt]}, "geometry_name": "geom",
            "properties": {"nombre": nombre, "pp": pp, "umbral": umbral, "pp_acum": pp_acum,
                           "umb_acum": None if umbral is None else umbral * 3, "hora": hora, "fecha": fecha,
                           "departamento": departamento, "provincia": "P", "distrito": "D",
                           "cuenca": "C", "control": 2}}


def _coleccion(*features):
    return json.dumps({"type": "FeatureCollection", "totalFeatures": len(features),
                       "features": list(features),
                       "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}}})


# Extracto literal de la respuesta real del 22-09-2026 a las 19:4x (9 de 216 puntos): dos
# "CABO INGA" homónimos a 400 m, la ñ mal codificada de AYMAÑA, una estación trabada desde
# la 01:00 (VON HUMBOLDT), otra atrasada (BAMBAMARCA H GORE a las 14:00) y una lloviendo.
REAL = (
    '{"type":"FeatureCollection","features":['
    '{"type":"Feature","id":"umbrales_precipitacion.fid-5ad84ba9_1a0cba83b22_-1ec0","geometry":{"type":"Point","coordinates":[-80.40182,-3.97594,228]},"geometry_name":"geom","properties":{"nombre":"CABO INGA","pp":1,"umbral":15,"pp_acum":1,"umb_acum":45,"hora":"18:00:00","fecha":"22/09/2026","departamento":"TUMBES","provincia":"TUMBES","distrito":"SAN JACINTO","cuenca":"Cuenca Tumbes","control":3}},'
    '{"type":"Feature","id":"umbrales_precipitacion.fid-5ad84ba9_1a0cba83b22_-1ebe","geometry":{"type":"Point","coordinates":[-80.39898,-3.97972,143]},"geometry_name":"geom","properties":{"nombre":"CABO INGA","pp":0.9,"umbral":15,"pp_acum":0.9,"umb_acum":45,"hora":"18:00:00","fecha":"22/09/2026","departamento":"TUMBES","provincia":"TUMBES","distrito":"SAN JACINTO","cuenca":"Cuenca Tumbes","control":3}},'
    '{"type":"Feature","id":"umbrales_precipitacion.fid-5ad84ba9_1a0cba83b22_-1e97","geometry":{"type":"Point","coordinates":[-72.89331,-15.21134,2683]},"geometry_name":"geom","properties":{"nombre":"COTAHUASI","pp":0,"umbral":5,"pp_acum":29.1,"umb_acum":15,"hora":"18:00:00","fecha":"22/09/2026","departamento":"AREQUIPA","provincia":"LA UNION","distrito":"COTAHUASI","cuenca":"Cuenca Ocoña","control":3}},'
    '{"type":"Feature","id":"umbrales_precipitacion.fid-5ad84ba9_1a0cba83b22_-1e7f","geometry":{"type":"Point","coordinates":[-78.52073,-7.09094,2906]},"geometry_name":"geom","properties":{"nombre":"RIO GRANDE GORE","pp":0,"umbral":5,"pp_acum":0,"umb_acum":15,"hora":"18:00:00","fecha":"22/09/2026","departamento":"CAJAMARCA","provincia":"CAJAMARCA","distrito":"LOS BAÑOS DEL INCA","cuenca":"Cuenca Crisnejas","control":3}},'
    '{"type":"Feature","id":"umbrales_precipitacion.fid-5ad84ba9_1a0cba83b22_-1e5b","geometry":{"type":"Point","coordinates":[-78.52363,-6.67996,2565]},"geometry_name":"geom","properties":{"nombre":"BAMBAMARCA GORE","pp":0,"umbral":5,"pp_acum":0,"umb_acum":15,"hora":"19:00:00","fecha":"22/09/2026","departamento":"CAJAMARCA","provincia":"HUALGAYOC","distrito":"BAMBAMARCA","cuenca":"Intercuenca Alto Marañón IV","control":2}},'
    '{"type":"Feature","id":"umbrales_precipitacion.fid-5ad84ba9_1a0cba83b22_-1e42","geometry":{"type":"Point","coordinates":[-76.93931,-12.08221,247]},"geometry_name":"geom","properties":{"nombre":"VON HUMBOLDT","pp":0,"umbral":1,"pp_acum":0,"umb_acum":3,"hora":"01:00:00","fecha":"22/09/2026","departamento":"LIMA","provincia":"LIMA","distrito":"LA MOLINA","cuenca":"Cuenca Rimac","control":4}},'
    '{"type":"Feature","id":"umbrales_precipitacion.fid-5ad84ba9_1a0cba83b22_-1e2e","geometry":{"type":"Point","coordinates":[-70.66759,-13.87279,4175]},"geometry_name":"geom","properties":{"nombre":"AYMAÃ±A","pp":0,"umbral":4,"pp_acum":0.1,"umb_acum":12,"hora":"19:00:00","fecha":"22/09/2026","departamento":"PUNO","provincia":"CARABAYA","distrito":"CORANI","cuenca":"Cuenca Inambari","control":2}},'
    '{"type":"Feature","id":"umbrales_precipitacion.fid-5ad84ba9_1a0cba83b22_-1e19","geometry":{"type":"Point","coordinates":[-78.54119,-6.66975,2866]},"geometry_name":"geom","properties":{"nombre":"BAMBAMARCA H GORE","pp":0,"umbral":5,"pp_acum":0.3,"umb_acum":15,"hora":"14:00:00","fecha":"22/09/2026","departamento":"CAJAMARCA","provincia":"HUALGAYOC","distrito":"BAMBAMARCA","cuenca":"Intercuenca Alto Marañón IV","control":4}},'
    '{"type":"Feature","id":"umbrales_precipitacion.fid-5ad84ba9_1a0cba83b22_-1e0c","geometry":{"type":"Point","coordinates":[-76.32508,-11.40443,4447]},"geometry_name":"geom","properties":{"nombre":"MARCAPOMACOCHA","pp":0.9,"umbral":5,"pp_acum":2.4,"umb_acum":15,"hora":"19:00:00","fecha":"22/09/2026","departamento":"JUNIN","provincia":"YAULI","distrito":"MARCAPOMACOCHA","cuenca":"Cuenca Mantaro","control":2}}'
    '],"totalFeatures":9,"crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:EPSG::4326"}}}'
).encode("utf-8")

# Filas reales de nuestra tabla estacion para esos puntos (y vecinas que no deben ganar).
ESTACIONES_REALES = [
    EstacionRef("103043", "CABO INGA", "M", "DIFERIDO", "Tumbes", -3.97594, -80.40182),
    EstacionRef("472F00A6", "CABO INGA M", "M", "AUTOMATICA", "Tumbes", -3.97594, -80.40182),
    EstacionRef("47E01126", "CABO INGA H", "H", "AUTOMATICA", "Tumbes", -3.97873, -80.39938),
    EstacionRef("115019", "COTAHUASI", "M", "REAL", "Arequipa", -15.21134, -72.89325),
    EstacionRef("47280292", "COTAHUASI", "M", "AUTOMATICA", "Arequipa", -15.21134, -72.89331),
    EstacionRef("472645F0", "UNC CAJAMARCA", "M", "AUTOMATICA", "Cajamarca", -7.16747, -78.49307),
    EstacionRef("100015", "BAMBAMARCA", "M", "REAL", "Cajamarca", -6.67655, -78.51834),
    EstacionRef("472680EE", "BAMBAMARCA M", "M", "AUTOMATICA", "Cajamarca", -6.67981, -78.52346),
    EstacionRef("4726D092", "BAMBAMARCA H", "H", "AUTOMATICA", "Cajamarca", -6.66975, -78.54119),
    EstacionRef("472AC278", "VON HUMBOLDT", "M", "AUTOMATICA", "Lima", -12.08221, -76.93944),
    EstacionRef("4721AAE4", "AYMAÑA", "M", "AUTOMATICA", "Puno", -13.87279, -70.66759),
    EstacionRef("472D9030", "MARCAPOMACOCHA", "M", "AUTOMATICA", "Junín", -11.40443, -76.32508),
]

VISOR = """
<table><tbody>
<tr><td class="bg-info"><a href="#" class="text-light btn-block btnDate" data-corrltv="1">2026-09-21</a></td></tr>
<tr><td class=""><a href="#" class="text-light btn-block btnDate" data-corrltv="2">2026-09-20</a></td></tr>
<tr><td class=""><a href="#" class="text-light btn-block btnDate" data-corrltv="3">2026-09-19</a></td></tr>
</tbody></table>
"""

# Extracto literal de monitoreo_meteorologico:prec_1_all_points pedida con
# propertyName=estacion,prec (22-09-2026 20:27, 5 de 546 puntos): tres SAN PABLO homónimos.
PUNTOS = (
    '{"type":"FeatureCollection","totalFeatures":546,"features":['
    '{"type":"Feature","id":"prec_1_all_points.9","geometry":null,"properties":{"estacion":"SAN PABLO","prec":0}},'
    '{"type":"Feature","id":"prec_1_all_points.56","geometry":null,"properties":{"estacion":"SAN PABLO","prec":0}},'
    '{"type":"Feature","id":"prec_1_all_points.75","geometry":null,"properties":{"estacion":"SAN GABAN","prec":59.3}},'
    '{"type":"Feature","id":"prec_1_all_points.226","geometry":null,"properties":{"estacion":"SAN PABLO","prec":0}},'
    '{"type":"Feature","id":"prec_1_all_points.325","geometry":null,"properties":{"estacion":"LLAPA","prec":13.5}}'
    '],"crs":null}'
).encode("utf-8")

# Latidos de corridas anteriores (solo lo que lee resolver_fechas y algo más, como en la BD).
PREVIO_20 = {"estaciones": 216, "prec_1": "2026-09-20", "prec_1_ac07d": "2026-09-20",
             "prec_1_ac07d_desde": "2026-09-14", "prec_1_pendiente": None,
             "fechas_leidas_en": "2026-09-21T23:30:00-05:00", "prec_1_huella": "huella-del-20",
             "fallas": [], "avisos": []}
PREVIO_21 = {**PREVIO_20, "prec_1": "2026-09-21", "prec_1_ac07d": "2026-09-21",
             "prec_1_ac07d_desde": "2026-09-15", "fechas_leidas_en": "2026-09-22T19:10:00-05:00",
             "prec_1_huella": "huella-del-21"}
FECHAS_PREVIO_20 = {k: PREVIO_20[k] for k in tarea.CAMPOS_FECHAS}


def _fechas(dia: date) -> su.FechasLluviaObservada:
    return su.FechasLluviaObservada(prec_1=dia, prec_1_ac07d=dia, prec_1_ac07d_desde=dia - timedelta(days=6))


def _lima(dia, hora):
    """Hora de Lima (UTC-5) -> datetime en UTC, como lo pasa Celery."""
    return datetime(2026, 9, dia, hora, tzinfo=timezone.utc) + timedelta(hours=5)


def _por_nombre(lecturas):
    return {lec.nombre: lec for lec in lecturas}


class TestCapaUmbrales(unittest.TestCase):
    def test_respuesta_real(self):
        lecturas, avisos = su.parse_geojson(REAL, AHORA)
        self.assertEqual(avisos, [])
        self.assertEqual(len(lecturas), 9)
        # los dos CABO INGA son estaciones distintas: la clave lleva las coordenadas
        self.assertEqual(len({lec.clave for lec in lecturas}), 9)
        n = _por_nombre(lecturas)
        self.assertIn("AYMAÑA", n)   # la ñ reparada y en mayúsculas
        cota = n["COTAHUASI"]
        self.assertEqual((cota.pp_1h, cota.umbral_1h, cota.pp_6h, cota.umbral_6h), (0.0, 5.0, 29.1, 15.0))
        self.assertEqual((cota.lat, cota.lon, cota.altitud_m), (-15.21134, -72.89331, 2683.0))
        self.assertEqual((cota.departamento, cota.distrito, cota.cuenca), ("AREQUIPA", "COTAHUASI", "Cuenca Ocoña"))
        # 18:00 de Lima son las 23:00 UTC
        self.assertEqual(cota.medido_en.astimezone(timezone.utc), datetime(2026, 9, 22, 23, tzinfo=timezone.utc))
        self.assertEqual(n["VON HUMBOLDT"].medido_en.hour, 1)

    def test_hora_de_peru(self):
        m = su.parse_medido_en("22/09/2026", "18:00:00")
        self.assertEqual(m.utcoffset(), timedelta(hours=-5))
        self.assertEqual(su.parse_medido_en("2026-09-22Z", "07:30"), datetime(2026, 9, 22, 7, 30, tzinfo=m.tzinfo))
        for fecha, hora in (("22/09/2026", "24:00:00"), ("31/02/2026", "10:00:00"), ("", "10:00"),
                            ("22/09/2026", None), (None, "10:00")):
            self.assertIsNone(su.parse_medido_en(fecha, hora), (fecha, hora))

    def test_puntos_malos_se_descartan_sin_tumbar_el_resto(self):
        sin_geom = _punto("SIN GEOM", -78.5, -7.1)
        sin_geom["geometry"] = None
        texto = _coleccion(
            _punto("BUENA", -78.5, -7.1, pp=2.5),
            sin_geom,
            _punto("FUERA", -60.0, -7.1),
            _punto("FECHA MALA", -78.5, -7.1, fecha="ayer"),
            _punto("FUTURA", -78.5, -7.1, hora="23:00:00"),   # 23:00 de Lima = 3 h después de AHORA
            _punto("NEGATIVA", -78.4, -7.0, pp=-999, pp_acum=1.2),
            _punto("", -78.5, -7.1),
        )
        lecturas, avisos = su.parse_geojson(texto, AHORA)
        self.assertEqual(sorted(lec.nombre for lec in lecturas), ["BUENA", "NEGATIVA"])
        neg = _por_nombre(lecturas)["NEGATIVA"]
        self.assertIsNone(neg.pp_1h)        # código de error del sensor, no lluvia
        self.assertEqual(neg.pp_6h, 1.2)
        self.assertEqual(len(avisos), 6)
        for texto_aviso in ("SIN GEOM: sin coordenadas", "FUERA: coordenadas fuera del Perú",
                            "FECHA MALA: fecha u hora ilegible", "FUTURA: hora en el futuro",
                            "NEGATIVA: pp descartado", "punto 6: sin nombre"):
            self.assertTrue(any(a.startswith(texto_aviso) for a in avisos), texto_aviso)

    def test_error_de_geoserver_no_es_capa_vacia(self):
        xml = b'<?xml version="1.0"?><ServiceExceptionReport><ServiceException>Timeout</ServiceException></ServiceExceptionReport>'
        with self.assertRaises(ValueError):
            su.parse_geojson(xml)
        with self.assertRaises(ValueError):
            su.parse_geojson('{"type": "FeatureCollection"}')

    def test_reparar_texto(self):
        self.assertEqual(su.reparar_texto("AYMAÃ±A"), "AYMAÑA")
        self.assertEqual(su.reparar_texto("Peñas Ã³ptimas"), "Peñas Ã³ptimas")   # mezcla: no se toca
        self.assertEqual(su.reparar_texto("ÑAÑA"), "ÑAÑA")

    def test_descarga_con_reintentos_y_tope(self):
        pedidas = []

        def falso_get_bytes(url, max_bytes=None):
            pedidas.append((url, max_bytes))
            return REAL

        with mock.patch.object(_http, "get_bytes", falso_get_bytes):
            lecturas, _ = su.lecturas(AHORA)
        self.assertEqual(len(lecturas), 9)
        [(url, tope)] = pedidas
        self.assertTrue(url.startswith("https://idesep.senamhi.gob.pe/geoserver/g_umbrales/ows?"))
        self.assertIn("typeName=g_umbrales%3Aumbrales_precipitacion", url)
        self.assertIn("outputFormat=application%2Fjson", url)
        self.assertEqual(tope, su.MAX_BYTES_WFS)

    def test_atribucion_literal_de_senamhi(self):
        self.assertEqual(su.ATRIBUCION,
                         "Información recopilada y trabajada por el Servicio Nacional de Meteorología e "
                         "Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) "
                         "entera responsabilidad")


class TestFechasVisor(unittest.TestCase):
    def test_fechas_de_prec_1_y_del_acumulado(self):
        f = su.parse_fechas_visor(VISOR)
        self.assertEqual(f.a_json(), {"prec_1": "2026-09-21", "prec_1_ac07d": "2026-09-21",
                                      "prec_1_ac07d_desde": "2026-09-15"})

    def test_sin_fecha(self):
        with self.assertRaises(ValueError):
            su.parse_fechas_visor("<html>sin botones</html>")

    def test_fechas_incoherentes(self):
        with self.assertRaises(ValueError):
            su.parse_fechas_visor(VISOR.replace("2026-09-20", "2026-09-18"))

    def test_descarga(self):
        with mock.patch.object(_http, "get_bytes", lambda url, max_bytes=None: VISOR.encode()):
            self.assertEqual(su.fechas_lluvia_observada().prec_1, date(2026, 9, 21))


class TestHuellaPrec1(unittest.TestCase):
    def _features(self):
        return json.loads(PUNTOS)["features"]

    def _texto(self, features):
        return json.dumps({"type": "FeatureCollection", "features": features})

    def test_respuesta_real(self):
        h = su.parse_huella(PUNTOS)
        self.assertRegex(h, r"^[0-9a-f]{16}$")
        self.assertEqual(su.parse_huella(PUNTOS.decode()), h)

    def test_no_depende_del_orden_ni_del_id(self):
        fs = self._features()[::-1]
        for i, f in enumerate(fs):
            f["id"] = f"prec_1_all_points.{1000 + i}"
        self.assertEqual(su.parse_huella(self._texto(fs)), su.parse_huella(PUNTOS))

    def test_cambia_con_los_datos(self):
        base = su.parse_huella(PUNTOS)
        fs = self._features()
        fs[2]["properties"]["prec"] = 59.4          # SAN GABAN corregida
        self.assertNotEqual(su.parse_huella(self._texto(fs)), base)
        fs = self._features()
        del fs[0]                                   # uno de los tres SAN PABLO deja de venir
        self.assertNotEqual(su.parse_huella(self._texto(fs)), base)
        fs = self._features()
        fs[4]["properties"]["prec"] = None          # LLAPA sin dato no es LLAPA con 13,5
        self.assertNotEqual(su.parse_huella(self._texto(fs)), base)

    def test_capa_vacia_sin_valores_o_con_error(self):
        sin_valores = [{"type": "Feature", "properties": {"estacion": "X", "prec": None}},
                       {"type": "Feature", "properties": {"estacion": "Y", "prec": "0"}}]
        xml = b'<?xml version="1.0"?><ServiceExceptionReport><ServiceException>x</ServiceException></ServiceExceptionReport>'
        for texto in (self._texto([]), self._texto(sin_valores), xml, '{"type": "FeatureCollection"}'):
            with self.assertRaises(ValueError, msg=texto):
                su.parse_huella(texto)

    def test_descarga_con_reintentos_y_tope(self):
        pedidas = []

        def falso_get_bytes(url, max_bytes=None):
            pedidas.append((url, max_bytes))
            return PUNTOS

        with mock.patch.object(_http, "get_bytes", falso_get_bytes):
            self.assertEqual(su.huella_prec_1(), su.parse_huella(PUNTOS))
        [(url, tope)] = pedidas
        self.assertTrue(url.startswith("https://idesep.senamhi.gob.pe/geoserver/monitoreo_meteorologico/ows?"))
        self.assertIn("typeName=monitoreo_meteorologico%3Aprec_1_all_points", url)
        self.assertIn("propertyName=estacion%2Cprec", url)
        self.assertEqual(tope, su.MAX_BYTES_PUNTOS)


class TestResolverFechas(unittest.TestCase):
    """Qué fecha de la lluvia observada se guarda (el visor la calcula con el reloj)."""

    def test_de_madrugada_el_visor_adelanta_pero_los_datos_no(self):
        # 22-09 a las 03:00: el visor ya dice 21, pero el dato del 21 termina a las 07:00
        campos, avisos = tarea.resolver_fechas(PREVIO_20, _fechas(date(2026, 9, 21)), "huella-del-20", _lima(22, 3))
        self.assertEqual(campos, {**FECHAS_PREVIO_20, "prec_1_pendiente": "2026-09-21"})
        self.assertEqual(avisos, ["fechas: el visor ya anuncia el 2026-09-21, pero los datos de prec_1 siguen "
                                  "siendo los mismos: se mantiene el 2026-09-20"])

    def test_cuando_senamhi_procesa_el_dia_se_acepta(self):
        campos, avisos = tarea.resolver_fechas(PREVIO_20, _fechas(date(2026, 9, 21)), "huella-del-21", _lima(22, 9))
        self.assertEqual(campos, {"prec_1": "2026-09-21", "prec_1_ac07d": "2026-09-21",
                                  "prec_1_ac07d_desde": "2026-09-15",
                                  "fechas_leidas_en": "2026-09-22T09:00:00-05:00",
                                  "prec_1_huella": "huella-del-21", "prec_1_pendiente": None})
        self.assertEqual(avisos, [])

    def test_sin_huella_la_fecha_no_avanza(self):
        campos, avisos = tarea.resolver_fechas(PREVIO_20, _fechas(date(2026, 9, 21)), None, _lima(22, 9))
        self.assertEqual(campos, {**FECHAS_PREVIO_20, "prec_1_pendiente": "2026-09-21"})
        self.assertEqual(avisos, ["fechas: el visor ya anuncia el 2026-09-21, pero no se pudo comprobar si los "
                                  "datos de prec_1 cambiaron: se mantiene el 2026-09-20"])

    def test_misma_fecha_renueva_la_huella(self):
        # SENAMHI corrige el día en curso: la próxima medianoche se compara con lo último
        campos, avisos = tarea.resolver_fechas(PREVIO_21, _fechas(date(2026, 9, 21)), "corregida", _lima(22, 20))
        self.assertEqual((campos["prec_1"], campos["prec_1_huella"], campos["fechas_leidas_en"]),
                         ("2026-09-21", "corregida", "2026-09-22T20:00:00-05:00"))
        self.assertEqual(avisos, [])
        # sin huella en esta corrida se queda la anterior
        campos, _ = tarea.resolver_fechas(PREVIO_21, _fechas(date(2026, 9, 21)), None, _lima(22, 20))
        self.assertEqual(campos["prec_1_huella"], "huella-del-21")

    def test_sin_nada_con_que_comparar_se_acepta_el_visor(self):
        for previo in ({}, {"prec_1": "ayer", "prec_1_huella": "x"}, {"prec_1": None}):
            campos, avisos = tarea.resolver_fechas(previo, _fechas(date(2026, 9, 21)), "h", _lima(22, 3))
            self.assertEqual((campos["prec_1"], campos["prec_1_ac07d_desde"], campos["prec_1_huella"]),
                             ("2026-09-21", "2026-09-15", "h"), previo)
            self.assertEqual(avisos, [])
        # latido del formato anterior (sin huella): no hay con qué comparar
        viejo = {k: v for k, v in PREVIO_20.items() if k not in ("prec_1_huella", "fechas_leidas_en")}
        campos, _ = tarea.resolver_fechas(viejo, _fechas(date(2026, 9, 21)), "h", _lima(22, 3))
        self.assertEqual((campos["prec_1"], campos["prec_1_pendiente"]), ("2026-09-21", None))

    def test_visor_caido_conserva_las_fechas_anteriores(self):
        campos, avisos = tarea.resolver_fechas(PREVIO_20, None, None, _lima(22, 9))
        self.assertEqual(campos, {**FECHAS_PREVIO_20, "prec_1_pendiente": None})
        self.assertEqual(avisos, [])
        campos, _ = tarea.resolver_fechas({}, None, None, _lima(22, 9))
        self.assertEqual(campos, {**dict.fromkeys(tarea.CAMPOS_FECHAS), "prec_1_pendiente": None})

    def test_fecha_futura_o_que_retrocede_no_se_usa(self):
        campos, avisos = tarea.resolver_fechas(PREVIO_20, _fechas(date(2026, 9, 22)), "otra", _lima(22, 9))
        self.assertEqual(campos, {**FECHAS_PREVIO_20, "prec_1_pendiente": None})
        self.assertEqual(avisos, ["fechas: el visor dice que prec_1 es del 2026-09-22, posterior a ayer "
                                  "(2026-09-21): no se usa"])
        campos, avisos = tarea.resolver_fechas(PREVIO_21, _fechas(date(2026, 9, 20)), "otra", _lima(22, 9))
        self.assertEqual(campos["prec_1"], "2026-09-21")
        self.assertEqual(avisos, ["fechas: el visor volvió al 2026-09-20 (ya se había leído el 2026-09-21): no se usa"])

    def test_ahora_si_avisa_que_senamhi_no_actualizo(self):
        # Antes se miraba la fecha del visor (siempre "ayer") y el aviso no saltaba nunca.
        # SENAMHI no procesó el 21 en todo el día 22: el 23 a la 01:00 sigue el 20.
        campos, avisos = tarea.resolver_fechas(PREVIO_20, _fechas(date(2026, 9, 22)), "huella-del-20", _lima(23, 1))
        self.assertEqual((campos["prec_1"], campos["prec_1_pendiente"]), ("2026-09-20", "2026-09-22"))
        self.assertIn("fechas: SENAMHI no ha actualizado la lluvia observada (prec_1 es del 2026-09-20)", avisos)
        # con el visor caído también
        _, avisos = tarea.resolver_fechas(PREVIO_20, None, None, _lima(23, 1))
        self.assertEqual(avisos, ["fechas: SENAMHI no ha actualizado la lluvia observada (prec_1 es del 2026-09-20)"])


class TestEmparejamiento(unittest.TestCase):
    def test_nombres(self):
        casos = [("CUTERVO GORE", "CUTERVO", (True, True)),
                 ("CASA GRANDE", "CASAGRANDE", (True, True)),
                 ("EMA PAMPA DE MAJES", "PAMPA DE MAJES", (True, True)),
                 ("CHANCAY BAÑOS", "CHANCAY BANOS", (True, True)),
                 ("CRISNEJAS", "PUENTE CRISNEJAS", (True, False)),
                 ("PUENTE CARRETERA", "PUENTE CARRETERA RAMIS", (True, False)),
                 ("RIO GRANDE GORE", "UNC CAJAMARCA", (False, False)),
                 ("SAN", "SAN MARCOS", (False, False)),   # parte común muy corta
                 ("GORE", "GORE", (False, False))]
        for a, b, esperado in casos:
            self.assertEqual(tarea.mismo_nombre(a, b), esperado, (a, b))

    def test_respuesta_real(self):
        lecturas, _ = su.parse_geojson(REAL, AHORA)
        parejas = tarea.emparejar(lecturas, ESTACIONES_REALES)
        cod = {lec.clave: parejas[lec.clave].cod for lec in lecturas}
        n = _por_nombre(lecturas)
        cabos = sorted((lec for lec in lecturas if lec.nombre == "CABO INGA"), key=lambda lec: lec.lon)
        self.assertEqual([cod[c.clave] for c in cabos], ["472F00A6", "47E01126"])   # automáticas, una cada una
        self.assertEqual(cod[n["COTAHUASI"].clave], "47280292")        # la automática, no la convencional
        self.assertEqual(cod[n["BAMBAMARCA GORE"].clave], "472680EE")
        self.assertEqual(cod[n["BAMBAMARCA H GORE"].clave], "4726D092")  # el nombre dice hidrológica
        self.assertEqual(cod[n["AYMAÑA"].clave], "4721AAE4")
        self.assertIsNone(cod[n["RIO GRANDE GORE"].clave])             # UNC CAJAMARCA está a 9 km
        self.assertEqual(parejas[n["MARCAPOMACOCHA"].clave].departamento, "Junín")
        self.assertEqual(parejas[n["RIO GRANDE GORE"].clave].departamento, "Cajamarca")

    def _lectura(self, nombre, lat, lon, departamento="LAMBAYEQUE"):
        return su.LecturaUmbral(nombre=nombre, lat=lat, lon=lon, altitud_m=None, departamento=departamento,
                                provincia=None, distrito=None, cuenca=None, pp_1h=0.0, umbral_1h=5.0,
                                pp_6h=0.0, umbral_6h=15.0, medido_en=AHORA)

    def test_misma_posicion_con_otro_nombre_solo_si_es_automatica(self):
        olmos = self._lectura("OLMOS", -5.83714, -79.81911)
        auto = EstacionRef("4726F67E", "PASABAR", "M", "AUTOMATICA", "Lambayeque", -5.83714, -79.81911)
        conv = EstacionRef("105076", "PASABAR", "M", "REAL", "Lambayeque", -5.83714, -79.81911)
        self.assertEqual(tarea.emparejar([olmos], [conv, auto])[olmos.clave].cod, "4726F67E")
        self.assertIsNone(tarea.emparejar([olmos], [conv])[olmos.clave].cod)
        lejos = EstacionRef("X", "PASABAR", "M", "AUTOMATICA", "Lambayeque", -5.8380, -79.8191)   # ~95 m
        self.assertIsNone(tarea.emparejar([olmos], [lejos])[olmos.clave].cod)

    def test_mismo_nombre_pero_lejos(self):
        lec = self._lectura("HUAYHUAHUASI", -14.65517, -71.52614, "CUSCO")
        e = EstacionRef("114124", "HUAYHUAHUASI", "M", "AUTOMATICA", "Cusco", -14.67242, -71.51991)   # 2 km
        self.assertIsNone(tarea.emparejar([lec], [e])[lec.clave].cod)

    def test_una_estacion_no_se_asigna_dos_veces(self):
        eha = self._lectura("SALITRAL EHA", -5.34602, -79.83761, "PIURA")
        otra = self._lectura("SALITRAL", -5.34588, -79.83794, "PIURA")   # a 40 m, no está en la tabla
        e = EstacionRef("47E067B6", "SALITRAL", "H", "AUTOMATICA", "Piura", -5.34602, -79.83761)
        parejas = tarea.emparejar([otra, eha], [e])
        self.assertEqual((parejas[eha.clave].cod, parejas[otra.clave].cod), ("47E067B6", None))

    def test_departamento_de_la_estacion_mas_cercana_si_la_capa_no_lo_trae(self):
        lec = self._lectura("NUEVA", -7.10, -78.60, departamento=None)
        e = EstacionRef("X", "OTRA", "M", "REAL", "Cajamarca", -7.20, -78.50)   # 15 km: no es pareja
        pareja = tarea.emparejar([lec], [e])[lec.clave]
        self.assertEqual((pareja.cod, pareja.departamento), (None, "Cajamarca"))
        # la capa escribe 'SAN MARTIN': se guarda el nombre canónico
        lec2 = self._lectura("TOCACHE", -8.2, -76.5, departamento="SAN MARTIN")
        self.assertEqual(tarea.emparejar([lec2], [])[lec2.clave].departamento, "San Martín")


class _Cursor:
    def __init__(self, conn):
        self.conn, self.ultima, self.ultimos, self.rowcount = conn, None, None, -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.registro.append((sql, params))
        self.ultima, self.ultimos = sql, params
        self.rowcount = 2 if sql == tarea.SQL_PURGA else 1

    def executemany(self, sql, filas):
        self.conn.registro.append((sql, list(filas)))

    def fetchall(self):
        if self.ultima == tarea.SQL_LLUVIA_VIGENTE:
            return self.conn.vigentes_en_bd(self.ultimos[0])
        assert self.ultima == tarea.SQL_ESTACIONES, self.ultima
        return [(e.cod, e.nombre, e.tipo, e.estado, e.departamento, e.lat, e.lon) for e in self.conn.estaciones]

    def fetchone(self):
        if self.ultima == tarea.SQL_HAY_ALERTA_LLUVIA:
            return (self.conn.migrada,)
        assert self.ultima == tarea.SQL_LATIDO_PREVIO, self.ultima
        return None if self.conn.latido is None else (self.conn.latido,)   # jsonb ya decodificado


class _Conexion:
    """
    Anota cada sentencia. migrada: si la migración de alertas de lluvia está aplicada.
    en_bd: {clave: fila de SQL_LLUVIA_SENAMHI} que la BD tiene después del upsert y que
    manda sobre lo que trajo la capa (una lectura más nueva, o una estación que no vino).
    """

    def __init__(self, estaciones, latido=None, migrada=True, en_bd=None):
        self.estaciones, self.latido, self.registro = estaciones, latido, []
        self.migrada, self.en_bd = migrada, en_bd or {}

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]

    def sentencias(self):
        return [s for s, _ in self.registro]

    def vigentes_en_bd(self, desde):
        """
        SQL_LLUVIA_VIGENTE sobre la BD simulada: el último upsert más en_bd, con su filtro y el
        orden de sus columnas (el texto lo fija test_sql_fija_tipo_y_nivel).
        """
        subidas = self.params(tarea.SQL_LLUVIA_SENAMHI)
        bd = {f[0]: f for f in (subidas[-1] if subidas else [])}
        bd.update(self.en_bd)
        return [(f[0], f[1], f[3], f[4], f[8], f[9], f[10], f[11], f[12], f[13], f[14])
                for f in sorted(bd.values(), key=lambda f: f[0]) if f[12] >= desde]


def _fila_bd(nombre, lon, lat, pp_1h, umbral_1h, pp_6h=0.0, medido_en=AHORA - timedelta(minutes=40),
             departamento="Cajamarca", provincia="CHOTA"):
    """Una fila de lluvia_senamhi como la guarda SQL_LLUVIA_SENAMHI (clave, fila)."""
    lec = su.LecturaUmbral(nombre=nombre, lat=lat, lon=lon, altitud_m=None, departamento=None,
                           provincia=provincia, distrito=None, cuenca=None, pp_1h=pp_1h, umbral_1h=umbral_1h,
                           pp_6h=pp_6h, umbral_6h=umbral_1h * 3, medido_en=medido_en)
    [fila] = tarea.filas([lec], {lec.clave: tarea.Pareja(cod=None, departamento=departamento)})
    return lec.clave, fila


# Las tres claves de la evaluación cuando no se tocaron las alertas.
SIN_EVALUAR = {"evaluadas": None, "alertas": None, "alertas_6h": None}
DETALLE_COTAHUASI = ("En Cotahuasi (provincia de La Union) llovió 29.1 mm en las 6 horas que terminaron a las "
                     "18:00. SENAMHI usa 15 mm en 6 horas como referencia para esta estación. Es lo que midió "
                     "la estación, no un aviso oficial.")


class _BaseTarea(unittest.TestCase):
    """Fuentes y BD simuladas (sin pruebas propias: las heredan las clases de abajo)."""

    def setUp(self):
        logging.disable(logging.ERROR)   # la tarea avisa de las fallas simuladas
        self.addCleanup(logging.disable, logging.NOTSET)

    def correr(self, capa=REAL, error_capa=None, visor=VISOR, error_visor=None, huella=PUNTOS,
               error_huella=None, latido=None, ahora=AHORA, migrada=True, en_bd=None,
               estaciones=ESTACIONES_REALES):
        conn = _Conexion(estaciones, latido, migrada=migrada, en_bd=en_bd)
        self.huellas_pedidas = 0

        @contextmanager
        def falso_conectar():
            yield conn

        def falso_lecturas(momento):
            if error_capa:
                raise error_capa
            return su.parse_geojson(capa, momento)

        def falsas_fechas():
            if error_visor:
                raise error_visor
            return su.parse_fechas_visor(visor)

        def falsa_huella():
            self.huellas_pedidas += 1
            if error_huella:
                raise error_huella
            return su.parse_huella(huella)

        self.excepcion = None
        with mock.patch.object(tarea, "conectar", falso_conectar), \
             mock.patch.object(su, "lecturas", falso_lecturas), \
             mock.patch.object(su, "fechas_lluvia_observada", falsas_fechas), \
             mock.patch.object(su, "huella_prec_1", falsa_huella):
            try:
                devuelto = tarea.actualizar(ahora)
            except Exception as e:
                self.excepcion, devuelto = e, None
        [(servicio, datos)] = conn.params(SQL_LATIDO)   # el latido se escribe siempre
        self.assertEqual(servicio, "lluvia_nacional")
        self.assertEqual(conn.params(tarea.SQL_LATIDO_PREVIO), [("lluvia_nacional",)])
        # el candado va primero, siempre, y una sola vez
        self.assertEqual(conn.registro[0][0], tarea.SQL_CANDADO)
        self.assertEqual(conn.sentencias().count(tarea.SQL_CANDADO), 1)
        resumen = json.loads(datos)
        if devuelto is not None:
            self.assertEqual(resumen, devuelto)
        return conn, resumen

    def assertAlertasSinTocar(self, conn, resumen):
        for sql in (tarea.SQL_HAY_ALERTA_LLUVIA, tarea.SQL_LLUVIA_VIGENTE, tarea.SQL_BORRAR_ALERTAS_LLUVIA,
                    tarea.SQL_ALERTA_LLUVIA):
            self.assertEqual(conn.params(sql), [], sql)
        self.assertEqual({k: resumen[k] for k in SIN_EVALUAR}, SIN_EVALUAR)


class TestTareaLluviaNacional(_BaseTarea):
    def test_corrida_normal(self):
        conn, resumen = self.correr()
        self.assertIsNone(self.excepcion)
        [filas] = conn.params(tarea.SQL_LLUVIA_SENAMHI)
        self.assertEqual(len(filas), 9)
        self.assertEqual(conn.params(tarea.SQL_PURGA), [(tarea.PURGA_DIAS,)])
        fila = next(f for f in filas if f[1] == "COTAHUASI")
        clave, nombre, cod, depto, prov, dist, cuenca, alt, pp1, u1, pp6, u6, medido, lon, lat = fila
        self.assertEqual((cod, depto, prov, alt), ("47280292", "Arequipa", "LA UNION", 2683.0))
        self.assertEqual((pp1, u1, pp6, u6), (0.0, 5.0, 29.1, 15.0))
        self.assertEqual((lon, lat), (-72.89331, -15.21134))    # ST_MakePoint(lon, lat)
        self.assertIsNotNone(medido.tzinfo)
        # COTAHUASI (18:00): 0 mm en la hora frente a 5, pero 29,1 mm en 6 h frente a 15
        [alertas] = conn.params(tarea.SQL_ALERTA_LLUVIA)
        self.assertEqual(alertas, [("COTAHUASI@-15.21134,-72.89331", "Arequipa", DETALLE_COTAHUASI,
                                    29.1, 15.0, 6, medido, -72.89331, -15.21134)])
        self.assertEqual(resumen, {
            # VON HUMBOLDT (01:00) y BAMBAMARCA H (14:00) pasan de 3 h
            "estaciones": 9, "vigentes": 7, "lloviendo": 3, "sobre_umbral": 0,
            "evaluadas": 7, "alertas": 1, "alertas_6h": 1,
            "cajamarca": {"estaciones": 3, "vigentes": 2, "lloviendo": 0},
            "sin_pareja": 1, "hora": "2026-09-22T19:00:00-05:00", "purgadas": 2,
            # sin latido anterior: se acepta la fecha del visor y se guarda la huella de sus datos
            "prec_1": "2026-09-21", "prec_1_ac07d": "2026-09-21", "prec_1_ac07d_desde": "2026-09-15",
            "prec_1_pendiente": None, "fechas_leidas_en": "2026-09-22T19:40:00-05:00",
            "prec_1_huella": su.parse_huella(PUNTOS),
            "atribucion": su.ATRIBUCION, "fallas": [], "avisos": [],
        })

    def test_sobre_umbral(self):
        capa = _coleccion(_punto("CHOTA GORE", -78.67588, -6.55405, pp=12.4, umbral=10),
                          _punto("CUTERVO GORE", -78.81339, -6.37914, pp=3, umbral=10),
                          # igual al umbral no lo supera: el mapa marca con > (lluviaAhora.js)
                          _punto("SANTA CRUZ", -78.94, -6.62, pp=10, umbral=10))
        conn, resumen = self.correr(capa=capa)
        self.assertEqual((resumen["lloviendo"], resumen["sobre_umbral"]), (3, 1))
        self.assertEqual(resumen["cajamarca"], {"estaciones": 3, "vigentes": 3, "lloviendo": 3})
        # una sola alerta, la misma que cuenta sobre_umbral (SANTA CRUZ, 10 = 10, no)
        [alertas] = conn.params(tarea.SQL_ALERTA_LLUVIA)
        [(referencia, zona, detalle, valor, umbral, ventana, *_)] = alertas
        self.assertEqual((referencia, zona, valor, umbral, ventana),
                         ("CHOTA GORE@-6.55405,-78.67588", "Cajamarca", 12.4, 10.0, 1))
        self.assertEqual(detalle, "En Chota GORE (provincia de P) llovió 12.4 mm en la hora que terminó a las "
                                  "19:00. SENAMHI usa 10 mm en una hora como referencia para esta estación. "
                                  "Es lo que midió la estación, no un aviso oficial.")
        self.assertEqual((resumen["evaluadas"], resumen["alertas"], resumen["alertas_6h"]), (3, 1, 0))
        self.assertEqual(resumen["alertas"], resumen["sobre_umbral"])

    def test_sobre_umbral_con_decimales(self):
        lec = su.LecturaUmbral(nombre="X", lat=-7.1, lon=-78.5, altitud_m=None, departamento="CAJAMARCA",
                               provincia=None, distrito=None, cuenca=None, pp_1h=5.0, umbral_1h=5.0,
                               pp_6h=None, umbral_6h=None, medido_en=AHORA)
        parejas = {lec.clave: tarea.Pareja(cod=None, departamento="Cajamarca")}
        self.assertEqual(tarea.conteo([lec], parejas, AHORA)["sobre_umbral"], 0)
        lec.pp_1h = 5.1
        self.assertEqual(tarea.conteo([lec], parejas, AHORA)["sobre_umbral"], 1)
        lec.pp_1h, lec.umbral_1h = 5.1, None    # sin umbral no se cuenta
        self.assertEqual(tarea.conteo([lec], parejas, AHORA)["sobre_umbral"], 0)

    def test_capa_caida_no_toca_la_tabla_y_la_tarea_falla(self):
        conn, resumen = self.correr(error_capa=TimeoutError("timed out"))
        self.assertIsInstance(self.excepcion, RuntimeError)
        self.assertEqual(conn.params(tarea.SQL_LLUVIA_SENAMHI), [])
        self.assertEqual(conn.params(tarea.SQL_PURGA), [])       # una fuente caída no borra nada
        self.assertEqual(conn.params(tarea.SQL_ESTACIONES), [])
        self.assertEqual(resumen["fallas"], ["umbrales"])
        self.assertEqual(resumen["avisos"], ["umbrales: TimeoutError: timed out"])
        self.assertIsNone(resumen["estaciones"])
        self.assertEqual(resumen["prec_1"], "2026-09-21")        # las fechas se leyeron igual
        self.assertAlertasSinTocar(conn, resumen)                # ni se borran las de lluvia

    def test_capa_vacia_es_falla(self):
        conn, resumen = self.correr(capa=_coleccion())
        self.assertIsInstance(self.excepcion, RuntimeError)
        self.assertEqual(conn.params(tarea.SQL_PURGA), [])
        self.assertEqual(resumen["fallas"], ["umbrales"])
        self.assertAlertasSinTocar(conn, resumen)

    def test_visor_caido_sigue_con_la_capa(self):
        conn, resumen = self.correr(error_visor=ValueError("No se encontró la fecha de prec_1"))
        self.assertIsNone(self.excepcion)
        self.assertEqual(len(conn.params(tarea.SQL_LLUVIA_SENAMHI)[0]), 9)
        # sin latido anterior no hay fecha que conservar
        self.assertEqual((resumen["prec_1"], resumen["prec_1_ac07d"], resumen["fechas_leidas_en"]), (None, None, None))
        self.assertEqual(resumen["fallas"], ["fechas"])
        self.assertEqual(resumen["avisos"], ["fechas: ValueError: No se encontró la fecha de prec_1"])
        self.assertEqual(self.huellas_pedidas, 0)   # sin fecha del visor la huella no sirve

    def test_visor_caido_conserva_las_fechas_del_latido_anterior(self):
        _, resumen = self.correr(error_visor=TimeoutError("timed out"), latido=PREVIO_21)
        self.assertIsNone(self.excepcion)
        self.assertEqual({k: resumen[k] for k in tarea.CAMPOS_FECHAS},
                         {k: PREVIO_21[k] for k in tarea.CAMPOS_FECHAS})
        self.assertEqual(resumen["fechas_leidas_en"], "2026-09-22T19:10:00-05:00")   # de cuándo son
        self.assertIsNone(resumen["prec_1_pendiente"])
        self.assertEqual(resumen["fallas"], ["fechas"])
        self.assertEqual(resumen["avisos"], ["fechas: TimeoutError: timed out"])

    def test_huella_caida_es_falla_de_fechas(self):
        _, resumen = self.correr(error_huella=TimeoutError("timed out"), latido=PREVIO_21)
        self.assertIsNone(self.excepcion)
        self.assertEqual(resumen["fallas"], ["fechas"])
        self.assertEqual(resumen["avisos"], ["fechas: huella de prec_1_all_points: TimeoutError: timed out"])
        # la fecha no avanzó: se acepta y queda la huella anterior
        self.assertEqual((resumen["prec_1"], resumen["prec_1_huella"], resumen["fechas_leidas_en"]),
                         ("2026-09-21", "huella-del-21", "2026-09-22T19:40:00-05:00"))

    def test_de_madrugada_se_mantiene_el_dia_anterior_hasta_que_cambien_los_datos(self):
        # 22-09 a las 03:00 y a las 09:00 en Lima; el visor ya dice 21 las dos veces
        previo = {**PREVIO_20, "prec_1_huella": su.parse_huella(PUNTOS)}
        capa = _coleccion(_punto("BAMBAMARCA GORE", -78.52363, -6.67996, hora="02:00:00"))
        _, resumen = self.correr(capa=capa, latido=previo, ahora=_lima(22, 3))
        self.assertIsNone(self.excepcion)
        self.assertEqual((resumen["prec_1"], resumen["prec_1_ac07d"], resumen["prec_1_ac07d_desde"]),
                         ("2026-09-20", "2026-09-20", "2026-09-14"))
        self.assertEqual(resumen["prec_1_pendiente"], "2026-09-21")
        self.assertEqual(resumen["fechas_leidas_en"], previo["fechas_leidas_en"])
        self.assertEqual(resumen["fallas"], [])   # es lo normal cada madrugada: aviso, no falla
        self.assertEqual(len(resumen["avisos"]), 1)
        self.assertTrue(resumen["avisos"][0].startswith("fechas: el visor ya anuncia el 2026-09-21"))

        procesado = PUNTOS.replace(b'"prec":59.3', b'"prec":12.0')
        capa = _coleccion(_punto("BAMBAMARCA GORE", -78.52363, -6.67996, hora="08:00:00"))
        _, resumen = self.correr(capa=capa, huella=procesado, latido=resumen, ahora=_lima(22, 9))
        self.assertEqual((resumen["prec_1"], resumen["prec_1_ac07d_desde"], resumen["prec_1_pendiente"]),
                         ("2026-09-21", "2026-09-15", None))
        self.assertEqual(resumen["prec_1_huella"], su.parse_huella(procesado))
        self.assertEqual(resumen["avisos"], [])

    def test_lluvia_observada_desactualizada(self):
        # 24-09 a las 19:40 y el visor sigue en el 21 (sin latido anterior se acepta)
        capa = _coleccion(_punto("BAMBAMARCA GORE", -78.52363, -6.67996, fecha="24/09/2026"))
        _, resumen = self.correr(capa=capa, ahora=AHORA + timedelta(days=2))
        self.assertIsNone(self.excepcion)
        self.assertEqual(resumen["avisos"],
                         ["fechas: SENAMHI no ha actualizado la lluvia observada (prec_1 es del 2026-09-21)"])

    def test_capa_con_todo_viejo_es_falla(self):
        # la capa responde, pero su dato más nuevo es de hace 25 h
        conn, resumen = self.correr(ahora=AHORA + timedelta(days=1))
        self.assertIsInstance(self.excepcion, RuntimeError)
        self.assertEqual(len(conn.params(tarea.SQL_LLUVIA_SENAMHI)[0]), 9)   # se guarda igual
        self.assertEqual(resumen["vigentes"], 0)
        self.assertEqual(resumen["fallas"], ["umbrales"])
        self.assertIn("umbrales: ninguna estación tiene dato de las últimas 3 h", resumen["avisos"])
        self.assertAlertasSinTocar(conn, resumen)

    def test_menos_de_la_mitad_vigentes_es_aviso(self):
        capa = _coleccion(_punto("A", -78.5, -7.1), _punto("B", -78.4, -7.1, hora="10:00:00"),
                          _punto("C", -78.3, -7.1, hora="11:00:00"))
        _, resumen = self.correr(capa=capa)
        self.assertIsNone(self.excepcion)
        self.assertEqual(resumen["fallas"], [])
        self.assertEqual(resumen["avisos"], ["umbrales: solo 1 de 3 estaciones tienen dato de las últimas 3 h"])
        # la mitad justa no avisa
        _, resumen = self.correr(capa=_coleccion(_punto("A", -78.5, -7.1), _punto("B", -78.4, -7.1, hora="10:00:00")))
        self.assertEqual(resumen["avisos"], [])

    def test_avisos_se_recortan(self):
        capa = _coleccion(_punto("BUENA", -78.5, -7.1),
                          *[_punto(f"MALA {i}", -78.5, -7.1, fecha="x") for i in range(30)])
        _, resumen = self.correr(capa=capa)
        self.assertEqual(len(resumen["avisos"]), tarea.MAX_AVISOS + 1)
        self.assertEqual(resumen["avisos"][-1], "... y 10 avisos más")

    def test_punto_repetido_queda_el_mas_reciente(self):
        capa = _coleccion(_punto("X", -78.5, -7.1, hora="18:00:00", pp=1),
                          _punto("X", -78.5, -7.1, hora="19:00:00", pp=2))
        conn, _ = self.correr(capa=capa)
        [filas] = conn.params(tarea.SQL_LLUVIA_SENAMHI)
        self.assertEqual([f[8] for f in filas], [2.0])

    def test_sql_no_retrocede_ni_borra_lo_que_no_vino(self):
        self.assertIn("where excluded.medido_en >= lluvia_senamhi.medido_en", tarea.SQL_LLUVIA_SENAMHI)
        self.assertIn("on conflict (clave)", tarea.SQL_LLUVIA_SENAMHI)
        self.assertIn("ts_captura < now()", tarea.SQL_PURGA)


class TestAlertasLluviaNacional(_BaseTarea):
    """Alertas de lluvia (tipo 'lluvia'): las escribe solo esta tarea, desde la BD."""

    def test_candado_primero(self):
        # beat + corrida suelta: el candado va antes que todo, también con la capa caída
        for kwargs in ({}, {"error_capa": TimeoutError("timed out")}):
            conn, _ = self.correr(**kwargs)
            self.assertEqual(conn.registro[0], (tarea.SQL_CANDADO, None), kwargs)
        self.assertEqual(tarea.SQL_CANDADO, "select pg_advisory_xact_lock(hashtext('lluvia_nacional'))")

    def test_reemplazo_despues_del_upsert(self):
        conn, _ = self.correr()
        pasos = (tarea.SQL_LLUVIA_SENAMHI, tarea.SQL_LLUVIA_VIGENTE, tarea.SQL_BORRAR_ALERTAS_LLUVIA,
                 tarea.SQL_ALERTA_LLUVIA)
        self.assertEqual([s for s in conn.sentencias() if s in pasos], list(pasos))
        self.assertEqual(conn.sentencias()[-1], SQL_LATIDO)
        # vigentes = medido_en de las últimas 3 h respecto de la corrida
        [(desde,)] = conn.params(tarea.SQL_LLUVIA_VIGENTE)
        self.assertEqual(desde, AHORA - timedelta(hours=3))

    def test_estacion_trabada_no_alerta(self):
        # VON HUMBOLDT sigue en la capa con su lectura de la 01:00: 5 mm frente a 1
        capa = _coleccion(_punto("VON HUMBOLDT", -76.93931, -12.08221, pp=5, umbral=1, hora="01:00:00",
                                 departamento="LIMA"),
                          _punto("BAMBAMARCA GORE", -78.52363, -6.67996))
        conn, resumen = self.correr(capa=capa)
        self.assertEqual(conn.params(tarea.SQL_ALERTA_LLUVIA), [])
        self.assertEqual(conn.params(tarea.SQL_BORRAR_ALERTAS_LLUVIA), [None])   # ninguna pasa: se van
        self.assertEqual((resumen["evaluadas"], resumen["alertas"], resumen["alertas_6h"]), (1, 0, 0))

    def test_bd_mas_nueva_manda(self):
        # la capa trae CHOTA GORE vieja (18:00) sobre la referencia; la BD ya tiene las 19:00 sin lluvia
        capa = _coleccion(_punto("CHOTA GORE", -78.67588, -6.55405, pp=12.4, umbral=10, hora="18:00:00"))
        clave, fila = _fila_bd("CHOTA GORE", -78.67588, -6.55405, pp_1h=0.0, umbral_1h=10.0,
                               medido_en=datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc))
        conn, resumen = self.correr(capa=capa, en_bd={clave: fila})
        self.assertEqual(conn.params(tarea.SQL_ALERTA_LLUVIA), [])
        self.assertEqual((resumen["evaluadas"], resumen["alertas"]), (1, 0))
        self.assertEqual(resumen["sobre_umbral"], 1)   # el conteo del lote solo mira la capa

    def test_estacion_ausente_conserva_su_alerta(self):
        # CHOTA GORE no vino en esta corrida, pero su lectura de las 19:00 sigue vigente en la BD
        clave, fila = _fila_bd("CHOTA GORE", -78.67588, -6.55405, pp_1h=12.4, umbral_1h=10.0)
        conn, resumen = self.correr(en_bd={clave: fila})
        [alertas] = conn.params(tarea.SQL_ALERTA_LLUVIA)
        self.assertEqual(sorted((a[0], a[5]) for a in alertas),
                         [(clave, 1), ("COTAHUASI@-15.21134,-72.89331", 6)])
        self.assertEqual((resumen["evaluadas"], resumen["alertas"], resumen["alertas_6h"]), (8, 2, 1))

    def test_sin_evaluables_no_toca(self):
        # sin referencia (o con 0) no se sabe si "no pasa ninguna": se quedan las que había
        capa = _coleccion(_punto("A", -78.5, -7.1, pp=30, umbral=None), _punto("B", -78.4, -7.1, pp=2, umbral=None),
                          _punto("C", -78.3, -7.1, pp=3, umbral=0))
        conn, resumen = self.correr(capa=capa)
        self.assertIsNone(self.excepcion)
        self.assertEqual(conn.params(tarea.SQL_LLUVIA_VIGENTE), [(AHORA - timedelta(hours=3),)])
        self.assertEqual(conn.params(tarea.SQL_BORRAR_ALERTAS_LLUVIA), [])
        self.assertEqual(conn.params(tarea.SQL_ALERTA_LLUVIA), [])
        self.assertEqual((resumen["evaluadas"], resumen["alertas"], resumen["alertas_6h"]), (0, None, None))
        self.assertEqual(resumen["avisos"], [tarea.AVISO_SIN_EVALUABLES])
        self.assertEqual(resumen["fallas"], [])

    def test_migracion_pendiente(self):
        # el worker salió antes que la migración: lluvia_senamhi y el latido se guardan igual
        conn, resumen = self.correr(migrada=False)
        self.assertIsNone(self.excepcion)
        self.assertEqual(len(conn.params(tarea.SQL_LLUVIA_SENAMHI)[0]), 9)
        self.assertEqual(conn.params(tarea.SQL_HAY_ALERTA_LLUVIA), [None])
        for sql in (tarea.SQL_LLUVIA_VIGENTE, tarea.SQL_BORRAR_ALERTAS_LLUVIA, tarea.SQL_ALERTA_LLUVIA):
            self.assertEqual(conn.params(sql), [], sql)
        self.assertEqual({k: resumen[k] for k in SIN_EVALUAR}, SIN_EVALUAR)
        self.assertEqual(resumen["avisos"], [tarea.AVISO_SIN_MIGRACION])
        self.assertEqual(resumen["fallas"], [])

    def test_zona_canonica_y_referencia_clave(self):
        # la capa escribe 'SAN MARTIN'; la referencia es la clave, con o sin estación emparejada
        capa = _coleccion(_punto("TOCACHE", -76.51, -8.18, pp=8, umbral=5, departamento="SAN MARTIN"))
        propia = EstacionRef("4720TOC0", "TOCACHE", "M", "AUTOMATICA", "San Martín", -8.18, -76.51)
        alertas = []
        for estaciones, cod in (([], None), ([propia], "4720TOC0")):
            conn, _ = self.correr(capa=capa, estaciones=estaciones)
            [[fila]] = conn.params(tarea.SQL_LLUVIA_SENAMHI)
            self.assertEqual(fila[2], cod)
            [[alerta]] = conn.params(tarea.SQL_ALERTA_LLUVIA)
            alertas.append(alerta)
        self.assertEqual(alertas[0], alertas[1])
        self.assertEqual(alertas[0][:2], ("TOCACHE@-8.18000,-76.51000", "San Martín"))

    def test_sql_fija_tipo_y_nivel(self):
        self.assertIn("'lluvia'", tarea.SQL_ALERTA_LLUVIA)
        self.assertIn("'aviso'", tarea.SQL_ALERTA_LLUVIA)
        self.assertEqual(tarea.SQL_ALERTA_LLUVIA.count("%s"), 9)
        self.assertEqual(tarea.SQL_BORRAR_ALERTAS_LLUVIA, "delete from alerta where tipo = 'lluvia'")
        self.assertIn("'public.alerta_lluvia_referencia_key'", tarea.SQL_HAY_ALERTA_LLUVIA)
        # _Conexion.vigentes_en_bd no ejecuta el SELECT: imita este texto (filtro de vigencia y
        # orden de las columnas), así que se fija entero
        self.assertEqual(tarea.SQL_LLUVIA_VIGENTE,
                         "select clave, nombre, departamento, provincia, pp_1h, umbral_1h, pp_6h, umbral_6h, "
                         "medido_en, lon, lat from lluvia_senamhi where medido_en >= %s order by clave")


if __name__ == "__main__":
    unittest.main()
