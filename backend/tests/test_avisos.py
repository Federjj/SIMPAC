"""
Avisos oficiales de SENAMHI: tabla de avisos, polígonos del WFS, textos oficiales, íconos,
lenguaje claro de las alertas y la regla de no borrar lo que no se pudo consultar. Sin red ni
psycopg: los fragmentos de HTML y GeoJSON son recortes de las respuestas reales del
22-09-2026 (muestras/aviso_vigente_20260922.html: la página de avisos vigentes, con los
avisos 375 y 376 y el 376 repetido al final, como en la página).
"""
import json
import logging
import re
import unittest
import urllib.parse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from backend.connectors import _http
from backend.connectors import senamhi_avisos as fuente
from backend.ingesta import avisos as tarea
from backend.ingesta.guardar import SQL_ALERTA, SQL_LATIDO

UTC = timezone.utc
# 22-09-2026 a las 19:48 de Lima
AHORA = datetime(2026, 9, 23, 0, 48, tzinfo=UTC)
HOY = date(2026, 9, 22)   # fecha de Perú de AHORA
RAIZ = Path(__file__).resolve().parents[2]
VIGENTES = (Path(__file__).parent / "muestras" / "aviso_vigente_20260922.html").read_text(encoding="utf-8")


def _fila(titulo, nro, emision, inicio, fin, horas, color, clase="", b="28968"):
    td = f'<td  class="{clase}">' if clase else "<td >"
    enlace = f'<a href="./?p=aviso-meteorologico-{"vigente" if clase else "detalle"}&a=2026&b={b}&c=00&d=SENA">'
    span = {"AMARILLO": "dos", "NARANJA": "tres", "ROJO": "cuatro"}[color]
    return (f"<tr>\n{td}{enlace}{titulo}</td>\n{td}{enlace}{nro} </td>\n{td}{emision}</td>\n"
            f"{td}{inicio}</td>\n{td}{fin}</td>\n{td}{horas} Hrs. </td>\n"
            f'{td}<span class="{span}">{color}</span></td>\n</tr>')


TABLA = (
    '<table id="table_id" class="table table-striped dataTable"><thead><tr><th>Aviso</th>'
    "<th>Nro.</th><th>Emisi&oacute;n</th><th>Inicio</th><th>Fin</th><th>Duraci&oacute;n</th>"
    "<th>Nivel</th></tr></thead><tbody>"
    + _fila("INCREMENTO DE TEMPERATURA DIURNA EN LA SELVA", "377 (emitido)", "2026-09-22",
            "2026-09-24", "2026-09-26", 61, "AMARILLO", "emitido", "28987")
    + _fila("PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE", "376 (emitido)", "2026-09-21",
            "2026-09-23", "2026-09-24", 47, "AMARILLO", "emitido")
    + _fila("LLOVIZNA EN LA COSTA CENTRO Y SUR", "374 (vigente)", "2026-09-19",
            "2026-09-20", "2026-09-22", 71, "NARANJA", "vigente", "28947")
    + _fila("PRECIPITACIONES EN LA SIERRA (AVISO CANCELADO)", "106 (vigente)", "2026-09-19",
            "2026-09-20", "2026-09-25", 47, "NARANJA", "vigente", "28900")
    + _fila("PRECIPITACIONES EN LA SIERRA (ACTUALIZACIÓN DEL AVISO 090)", "093", "2025-03-23",
            "2025-03-25", "2025-03-25", 23, "AMARILLO")
    + "</tbody></table>"
)

DETALLE = """
<div class="tab-content" id="nav-tabContent">
  <div class="tab-pane fade " id="tabs-3762026" role="tabpanel" aria-labelledby="tabs-3762026-tab">
    <h2 class="desaparecerHR">Aviso N&deg;376&nbsp;<span class="dos">AMARILLO</span></h2>
    <h1 class="aviso-vigente">PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE</h1>
    <div class="col-lg-12 col-md-12 col-sm-12 col-xs-12">
      El SENAMHI informa que, del mi&eacute;rcoles 23 al jueves 24 de setiembre, se presentar&aacute;
      precipitaciones (lluvia), de ligera a moderada intensidad, en la sierra norte. Estas
      precipitaciones estar&aacute;n acompa&ntilde;adas de descargas el&eacute;ctricas.   </div>
  </div>
  <div class="tab-pane fade " id="tabs-3772026" role="tabpanel">
    <div class="col-lg-12">Sin p&aacute;rrafo oficial</div>
  </div>
</div>
"""


def _anillo(lon, lat, d=0.1):
    return [[[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]]]


def _feature(nivel, ini, fin, lon=-78.6, lat=-7.2, nro=376, mapa=1):
    return {"type": "Feature", "id": "view_aviso.fid-5ad84ba9_1a0cba83b22_-1bf9",
            "geometry": {"type": "MultiPolygon", "coordinates": [_anillo(lon, lat)]},
            "properties": {"gid": 25667, "nro_aviso": nro, "nro_mapa": mapa, "nivel": nivel,
                           "fecha_emi": "2026-09-21Z", "cod_fen": "1", "cod_even": "01",
                           "fech_ini": ini, "fech_fin": fin, "cod_sede": "00", "respons": "JMESIA",
                           "pub": 3, "cap": 0}}


def _fc(*features):
    return json.dumps({"type": "FeatureCollection", "totalFeatures": len(features),
                       "features": list(features), "crs": None}).encode()


WFS_376 = {
    1: _fc(_feature("Nivel 2", "2026-09-23T05:00:00Z", "2026-09-24T04:59:59Z"),
           _feature("Nivel 2", "2026-09-23T05:00:00Z", "2026-09-24T04:59:59Z", lon=-78.2, lat=-7.0)),
    2: _fc(_feature("Nivel 2", "2026-09-24T05:00:00Z", "2026-09-25T04:59:59Z", mapa=2)),
}
# El 374 trae su juego de septiembre y otro igual con fechas de agosto (registros erróneos).
WFS_374_1 = _fc(
    _feature("Nivel 3", "2026-09-20T05:00:00Z", "2026-09-21T04:59:59Z", nro=374),
    _feature("Nivel 2", "2026-09-20T05:00:00Z", "2026-09-21T04:59:59Z", nro=374),
    _feature("Nivel 2", "2026-08-20T05:00:00Z", "2026-08-21T04:59:59Z", nro=374),
    _feature("Nivel 3", "2026-08-20T05:00:00Z", "2026-08-21T04:59:59Z", nro=374),
)
EXCEPCION_XML = (b'<?xml version="1.0" ?><ServiceExceptionReport version="1.2.0"><ServiceException>'
                 b"java.lang.RuntimeException: Error</ServiceException></ServiceExceptionReport>")


def _feature_24h(nivel, fecha="2026-09-22Z", lon=-78.6):
    return {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [_anillo(lon, -7.2)]},
            "properties": {"gid": 5, "nivel": nivel, "fecha": fecha,
                           "descripcio": "Ante el pronóstico de lluvias es probable la activación de quebradas...",
                           "recomendac": "Estar atentos a la información oficial...", "respons": "EROJAS"}}


def _liviana_24h(*fechas):
    """Respuesta de la vista de 24 h completa con propertyName=nivel,fecha (sin geometría)."""
    return _fc(*[{"type": "Feature", "id": f"view_aviso24h.fid-{i}", "geometry": None,
                  "properties": {"nivel": "Nivel 1" if i % 2 == 0 else "Nivel 2", "fecha": f}}
                 for i, f in enumerate(fechas)])


def _wfs_24h(filtrada, liviana=None):
    """get_bytes simulado: la consulta con cql_filter (sin Nivel 1) y la liviana (sin filtro)."""
    urls = []

    def falso(url, max_bytes=None):
        urls.append((url, max_bytes))
        return filtrada if "cql_filter" in _params(url) else liviana
    return falso, urls


def _aviso(numero=376, inicio=date(2026, 9, 23), fin=date(2026, 9, 24), titulo=None):
    return fuente.Aviso(numero=numero, anio=2026, estado="emitido", emision=date(2026, 9, 21),
                        titulo=titulo or "PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE",
                        inicio=inicio, fin=fin, nivel=2,
                        url="https://www.senamhi.gob.pe/?p=aviso-meteorologico-vigente&a=2026&b=28968&c=00&d=SENA")


def _params(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))


class TestTabla(unittest.TestCase):
    def test_solo_emitidos_y_vigentes(self):
        t = fuente.parse_tabla(TABLA)
        self.assertEqual(t.filas, 5)
        self.assertEqual([a.numero for a in t.avisos], [377, 376, 374, 106])
        a = t.avisos[1]
        self.assertEqual((a.anio, a.estado, a.emision, a.inicio, a.fin, a.nivel),
                         (2026, "emitido", date(2026, 9, 21), date(2026, 9, 23), date(2026, 9, 24), 2))
        self.assertEqual(a.titulo, "PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE")
        self.assertEqual(a.url, "https://www.senamhi.gob.pe/?p=aviso-meteorologico-vigente&a=2026&b=28968&c=00&d=SENA")
        self.assertEqual((a.tema, a.mapas, a.cancelado), ("lluvia", 2, False))
        self.assertEqual(t.avisos[2].nivel, 3)
        self.assertTrue(t.avisos[3].cancelado)
        self.assertEqual(t.problemas, [])

    def test_vigencia_en_utc(self):
        a = fuente.parse_tabla(TABLA).avisos[1]
        # del 23 a las 00:00 al 24 a las 23:59 de Lima
        self.assertEqual(a.inicio_utc, datetime(2026, 9, 23, 5, tzinfo=UTC))
        self.assertEqual(a.fin_utc, datetime(2026, 9, 25, 5, tzinfo=UTC))

    def test_pagina_cambiada_no_es_sin_avisos(self):
        with self.assertRaises(ValueError):
            fuente.parse_tabla("<html><body>Mantenimiento</body></html>")

    def test_fila_activa_ilegible_no_tumba_las_demas(self):
        mala = _fila("PRECIPITACIONES EN LA SIERRA", "378 (emitido)", "22/09/2026", "2026-09-24",
                     "2026-09-25", 47, "NARANJA", "emitido")
        t = fuente.parse_tabla(TABLA.replace("<tbody>", "<tbody>" + mala), HOY)
        self.assertEqual([a.numero for a in t.avisos], [377, 376, 374, 106])
        self.assertEqual(len(t.problemas), 1)
        self.assertIn("378", t.problemas[0])

    def test_cabecera_cambiada_es_falla(self):
        casos = {
            "columnas movidas": TABLA.replace("<th>Inicio</th><th>Fin</th>", "<th>Fin</th><th>Inicio</th>"),
            "columna renombrada": TABLA.replace("<th>Nro.</th>", "<th>Estado</th>"),
            "sin cabecera": re.sub(r"<thead>.*?</thead>", "", TABLA),
        }
        for caso, pagina in casos.items():
            with self.assertRaisesRegex(ValueError, "cabecera", msg=caso):
                fuente.parse_tabla(pagina, HOY)
        # la cabecera real (con tfoot y entidades HTML) sí se acepta
        real = TABLA.replace("</thead>", "</thead><tfoot><tr><th>Aviso</th><th>Nro.</th></tr></tfoot>")
        self.assertEqual(len(fuente.parse_tabla(real, HOY).avisos), 4)

    def test_filas_sin_las_7_columnas(self):
        sin_nivel = re.sub(r"<td[^>]*><span.*?</td>\n", "", TABLA)   # todas con 6 columnas
        with self.assertRaisesRegex(ValueError, "7 columnas"):
            fuente.parse_tabla(sin_nivel, HOY)
        # una sola fila activa con otra forma: es un problema, no una fila del histórico
        corta = re.sub(r"<td[^>]*><span.*?</td>\n", "", _fila(TITULO_376, "378 (emitido)", "2026-09-22",
                                                               "2026-09-24", "2026-09-25", 47, "AMARILLO", "emitido"))
        t = fuente.parse_tabla(TABLA.replace("<tbody>", "<tbody>" + corta), HOY)
        self.assertEqual([a.numero for a in t.avisos], [377, 376, 374, 106])
        self.assertEqual(len(t.problemas), 1)
        self.assertIn("378 (emitido)", t.problemas[0])
        self.assertIn("trae 6 columnas", t.problemas[0])

    def test_etiqueta_cambiada_no_es_sin_avisos(self):
        # Si SENAMHI cambia la etiqueta, no se lee ningún aviso, pero cada fila que aún no
        # termina (el 374 termina hoy) es un problema. El 106 está cancelado y el 093 terminó.
        t = fuente.parse_tabla(re.sub(r"\((emitido|vigente)\)", r"[\1]", TABLA), HOY)
        self.assertEqual(t.avisos, [])
        self.assertEqual(t.problemas, [
            "fila '377 [emitido]': sin etiqueta (emitido)/(vigente) y termina el 2026-09-26",
            "fila '376 [emitido]': sin etiqueta (emitido)/(vigente) y termina el 2026-09-24",
            "fila '374 [vigente]': sin etiqueta (emitido)/(vigente) y termina el 2026-09-22",
        ])
        # al día siguiente el 374 ya es histórico
        t = fuente.parse_tabla(re.sub(r"\((emitido|vigente)\)", r"[\1]", TABLA), HOY + timedelta(days=1))
        self.assertEqual(len(t.problemas), 2)

    def test_fila_sin_etiqueta_que_aun_no_termina(self):
        pagina = TABLA.replace("376 (emitido)", "376").replace(
            "<tbody>", "<tbody>" + _fila("LLUVIA EN LA SELVA (AVISO CANCELADO)", "379", "2026-09-22",
                                         "2026-09-23", "2026-09-25", 47, "NARANJA", b="28999"))
        t = fuente.parse_tabla(pagina, HOY)
        self.assertEqual([a.numero for a in t.avisos], [377, 374, 106])
        # el 379 cancelado no cuenta; el 376 sí
        self.assertEqual(t.problemas, ["fila '376': sin etiqueta (emitido)/(vigente) y termina el 2026-09-24"])

    def test_original_de_una_actualizacion_sin_etiqueta_no_es_problema(self):
        actualizacion = _fila("PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE (ACTUALIZACIÓN DEL AVISO 376)",
                              "378 (emitido)", "2026-09-22", "2026-09-23", "2026-09-24", 47, "NARANJA",
                              "emitido", "28990")
        pagina = TABLA.replace("376 (emitido)", "376").replace("<tbody>", "<tbody>" + actualizacion)
        t = fuente.parse_tabla(pagina, HOY)
        self.assertEqual([a.numero for a in t.avisos], [378, 377, 374, 106])
        self.assertEqual(t.avisos[0].actualiza, (2026, 376))
        self.assertEqual(t.problemas, [])

    def test_fechas_ilegibles_en_filas_sin_etiqueta(self):
        # Si cambia el formato de fecha, el histórico no se puede descartar: se cuenta junto.
        t = fuente.parse_tabla(re.sub(r"(\d{4})-(\d{2})-(\d{2})", r"\3/\2/\1", TABLA), HOY)
        self.assertEqual(t.avisos, [])
        self.assertEqual(len(t.problemas), 5)   # las 4 activas y el resumen del histórico
        self.assertEqual(t.problemas[-1], "filas sin etiqueta con la fecha de fin ilegible: 1")

    def test_actualizacion_dice_a_que_aviso_reemplaza(self):
        casos = {
            (380, "PRECIPITACIONES EN LA SIERRA (ACTUALIZACIÓN DEL AVISO 373)"): (2026, 373),
            (93, "PRECIPITACIONES EN LA SIERRA (ACTUALIZACION DEL AVISO N° 090)"): (2026, 90),
            (2, "LLUVIA EN LA SELVA (ACTUALIZACIÓN DEL AVISO 380)"): (2025, 380),   # del año anterior
            (366, "INCREMENTO DE TEMPERATURA DIURNA EN LA COSTA Y SIERRA (EXTENSIÓN DEL AVISO 361)"): None,
            (376, "PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE"): None,
        }
        for (numero, titulo), esperado in casos.items():
            self.assertEqual(_aviso(numero, titulo=titulo).actualiza, esperado, titulo)

    def test_tema_desde_el_titulo(self):
        casos = {
            "PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE": "lluvia",
            "LLOVIZNA EN LA COSTA CENTRO Y SUR": "lluvia",
            "NEVADA EN LA SIERRA SUR": "lluvia",
            "LLUVIA EN LA SELVA-PRIMER FRIAJE (ACTUALIZACIÓN DEL AVISO 171)": "lluvia",
            "DÉCIMO FRIAJE EN LA SELVA": "temperatura",
            "DESCENSO DE TEMPERATURA NOCTURNA EN LA SIERRA": "temperatura",
            "INCREMENTO DE VIENTO EN LA COSTA": "viento",
            "OLEAJE ANÓMALO": "otro",
        }
        for titulo, tema in casos.items():
            self.assertEqual(fuente.tema_de_titulo(titulo), tema, titulo)

    def test_descripciones(self):
        d = fuente.parse_descripciones(DETALLE)
        self.assertEqual(list(d), [(2026, 376)])
        self.assertTrue(d[(2026, 376)].startswith("El SENAMHI informa que, del miércoles 23 al jueves 24"))
        self.assertIn("de ligera a moderada intensidad", d[(2026, 376)])

    def test_descripciones_solo_de_senamhi(self):
        with self.assertRaises(ValueError):
            fuente.descripciones("https://otro.example/?p=aviso-meteorologico-vigente")
        with self.assertRaises(ValueError):
            fuente.textos("https://otro.example/?p=aviso-meteorologico-vigente")


class TestTextos(unittest.TestCase):
    def test_general_y_dias_de_la_pagina_real(self):
        t = fuente.parse_textos(VIGENTES)
        self.assertEqual(sorted(t), [(2026, 375), (2026, 376)])
        self.assertEqual(sorted(t[(2026, 375)].dias), [1, 2, 3])
        self.assertEqual(sorted(t[(2026, 376)].dias), [1, 2])
        for clave in t:
            self.assertTrue(t[clave].general.startswith("El SENAMHI informa que"), clave)
        self.assertEqual(t[(2026, 376)].dias[1],
                         "El miércoles 23 de setiembre se esperan acumulados de lluvia hasta los 12 mm/día en Tumbes, "
                         "cercanos a los 6 mm/día en la costa de Piura y valores entre los 7 mm/día y 15 mm/día en la "
                         "sierra norte.")
        self.assertTrue(t[(2026, 375)].dias[2].startswith("El martes 22 de setiembre"))   # así viene
        # parse_descripciones sigue dando solo el general
        self.assertEqual(fuente.parse_descripciones(VIGENTES), {k: v.general for k, v in t.items()})

    def test_gana_el_primer_bloque(self):
        # la página repite tabs-3762026 al final; si el repetido cambiara, manda el primero
        ini = VIGENTES.rindex('id="tabs-3762026"')
        pagina = VIGENTES[:ini] + VIGENTES[ini:].replace("hasta los 12 mm/día", "hasta los 99 mm/día") \
                                                 .replace("El SENAMHI informa", "El SENAMHI informa (repetido)")
        t = fuente.parse_textos(pagina)[(2026, 376)]
        self.assertIn("hasta los 12 mm/día", t.dias[1])
        self.assertNotIn("(repetido)", t.general)
        # pero lo que falta en el primero se toma del repetido
        ini = VIGENTES.index('id="tabs-3762026"')
        fin = VIGENTES.index('id="tabs-3762026"', ini + 1)
        sin_general = VIGENTES[:ini] + VIGENTES[ini:fin].replace("El SENAMHI informa", "SENAMHI dice") + VIGENTES[fin:]
        self.assertTrue(fuente.parse_textos(sin_general)[(2026, 376)].general.startswith("El SENAMHI informa que"))

    def test_iframe_de_otro_aviso_o_anio_se_ignora(self):
        pagina = VIGENTES.replace("av=376&nl=2&mp=2&fc=2026", "av=999&nl=2&mp=2&fc=2026") \
                         .replace("av=375&nl=4&mp=3&fc=2026", "av=375&nl=4&mp=3&fc=2025")
        t = fuente.parse_textos(pagina)
        self.assertEqual(sorted(t[(2026, 376)].dias), [1])
        self.assertEqual(sorted(t[(2026, 375)].dias), [1, 2])

    def test_el_senamhi_sin_distinguir_mayusculas_y_largo_maximo(self):
        pagina = ('<div class="tab-pane" id="tabs-1802026"><div class="col-lg-12">El Senamhi informa que, del '
                  'domingo 10 al lunes 11 de mayo, se presentará precipitaciones' + " en la sierra" * 200 + '.</div>'
                  '<div class="tab-pane" id="v-pills-tab-1-281002026"><p align="justify">' + "x " * 1000 + '</p>'
                  '<br><iframe src="mapas/mapa-avisos-meteorologicos/index.php?av=180&amp;nl=3&amp;mp=1&amp;fc=2026">'
                  '</iframe></div></div>')
        t = fuente.parse_textos(pagina)[(2026, 180)]
        self.assertTrue(t.general.startswith("El Senamhi informa que, del domingo 10"))
        self.assertEqual(len(t.general), fuente.MAX_GENERAL)
        self.assertEqual(len(t.dias[1]), fuente.MAX_TEXTO_DIA)   # con &amp; en el iframe también se lee

    def test_textos_baja_la_pagina_una_vez(self):
        with mock.patch.object(_http, "get_bytes", return_value=VIGENTES.encode()) as m:
            t = fuente.textos("https://www.senamhi.gob.pe/?p=aviso-meteorologico-vigente&a=2026&b=28968&c=00&d=SENA")
        m.assert_called_once()
        self.assertEqual(sorted(t), [(2026, 375), (2026, 376)])

    def test_atribucion_literal(self):
        self.assertTrue(fuente.ATRIBUCION.startswith("Información recopilada y trabajada por el Servicio "
                                                     "Nacional de Meteorología e Hidrología del Perú."))
        self.assertTrue(fuente.ATRIBUCION.endswith("es de mi (nuestra) entera responsabilidad"))


class TestPoligonos(unittest.TestCase):
    def test_duplicados_con_fechas_erroneas_se_descartan(self):
        aviso = _aviso(374, date(2026, 9, 20), date(2026, 9, 22), "LLOVIZNA EN LA COSTA CENTRO Y SUR")
        areas, descartados = fuente.areas_de_features(aviso, 1, json.loads(WFS_374_1)["features"])
        self.assertEqual(descartados, 2)
        self.assertEqual(sorted((a.mapa, a.nivel, len(a.geometrias)) for a in areas), [(1, 2, 1), (1, 3, 1)])
        self.assertEqual({a.inicio for a in areas}, {datetime(2026, 9, 20, 5, tzinfo=UTC)})

    def test_se_agrupa_por_nivel_y_se_piden_todos_los_mapas(self):
        urls = []

        def falso(url, max_bytes=None):
            urls.append(url)
            return WFS_376[int(_params(url)["viewparams"].split("_")[1])]

        with mock.patch.object(_http, "get_bytes", falso):
            areas, descartados = fuente.areas_aviso(_aviso())
        self.assertEqual(descartados, 0)
        self.assertEqual(len(urls), 2)   # 23 y 24: un mapa por día
        p = _params(urls[0])
        self.assertEqual((p["typeName"], p["viewparams"], p["cql_filter"], p["outputFormat"]),
                         ("g_aviso:view_aviso", "qry:376_1_2026", "nivel<>'Nivel 1'", "application/json"))
        self.assertTrue(urls[0].startswith("https://idesep.senamhi.gob.pe/geoserver/g_aviso/ows?"))
        self.assertEqual([(a.mapa, a.nivel, len(a.geometrias)) for a in areas], [(1, 2, 2), (2, 2, 1)])
        self.assertEqual((areas[1].inicio, areas[1].fin),
                         (datetime(2026, 9, 24, 5, tzinfo=UTC), datetime(2026, 9, 25, 4, 59, 59, tzinfo=UTC)))

    def test_excepcion_de_geoserver_es_falla_y_no_se_reintenta(self):
        llamadas = []

        def falso(url, max_bytes=None):
            llamadas.append(url)
            return EXCEPCION_XML

        with mock.patch.object(_http, "get_bytes", falso), self.assertRaises(ValueError):
            fuente.areas_aviso(_aviso())
        self.assertEqual(len(llamadas), 1)

    def test_features_sin_nivel_fecha_o_geometria(self):
        malas = [_feature("Nivel 1", "2026-09-23T05:00:00Z", "2026-09-24T04:59:59Z"),
                 _feature("Nivel 2", "", "2026-09-24T04:59:59Z"),
                 _feature("Nivel 2", "2026-09-23T05:00:00Z", "2026-09-24T04:59:59Z", nro=375),
                 dict(_feature("Nivel 2", "2026-09-23T05:00:00Z", "2026-09-24T04:59:59Z"), geometry=None)]
        areas, descartados = fuente.areas_de_features(_aviso(), 1, malas)
        self.assertEqual((areas, descartados), ([], 4))

    def test_lluvia_24h_rige_desde_las_13_de_lima(self):
        feats = [_feature_24h("Nivel 2"), _feature_24h("Nivel 2", lon=-70.0), _feature_24h("Nivel 3"),
                 _feature_24h("Nivel 2", fecha="2026-09-21Z")]   # uno viejo: se ignora
        areas = fuente.areas_de_features_24h(feats)
        self.assertEqual(sorted((a.nivel, len(a.geometrias)) for a in areas), [(2, 2), (3, 1)])
        a = areas[0]
        self.assertEqual((a.tipo, a.anio, a.numero, a.mapa), ("lluvia24h", 2026, None, 1))
        self.assertEqual((a.inicio, a.fin), (datetime(2026, 9, 22, 18, tzinfo=UTC), datetime(2026, 9, 23, 18, tzinfo=UTC)))

    def test_lluvia_24h_url(self):
        with mock.patch.object(_http, "get_bytes", return_value=_fc(_feature_24h("Nivel 2"))) as m:
            [area] = fuente.aviso_24h(HOY)
        p = _params(m.call_args.args[0])
        self.assertEqual((p["typeName"], p["cql_filter"]), ("g_prono_pp_24h:view_aviso24h", "nivel<>'Nivel 1'"))
        self.assertEqual(area.nivel, 2)
        m.assert_called_once()   # con zonas no hace falta la consulta liviana

    def test_mapa_sin_poligonos_validos_es_falla(self):
        # El 376 sigue en la tabla, pero su mapa 2 viene vacío o con solo registros erróneos.
        casos = {
            "vacío": _fc(),
            "solo descartados": _fc(_feature("Nivel 2", "2026-08-24T05:00:00Z", "2026-08-25T04:59:59Z", mapa=2)),
        }
        for caso, mapa_2 in casos.items():
            respuestas = {1: WFS_376[1], 2: mapa_2}
            with mock.patch.object(_http, "get_bytes", lambda url, max_bytes=None, r=respuestas:
                                   r[int(_params(url)["viewparams"].split("_")[1])]), \
                 self.assertRaisesRegex(ValueError, "polígonos válidos del mapa 2 de 2", msg=caso):
                fuente.areas_aviso(_aviso())

    def test_lluvia_24h_vacia_se_confirma_con_la_vista_liviana(self):
        # Filtrada vacía y la vista completa (solo Nivel 1) es de hoy: no hay zonas con aviso.
        falso, urls = _wfs_24h(_fc(), _liviana_24h("2026-09-22Z", "2026-09-22Z"))
        with mock.patch.object(_http, "get_bytes", falso):
            self.assertEqual(fuente.aviso_24h(HOY), [])
        self.assertEqual(len(urls), 2)
        p = _params(urls[1][0])
        self.assertEqual((p["typeName"], p["propertyName"], p["outputFormat"]),
                         ("g_prono_pp_24h:view_aviso24h", "nivel,fecha", "application/json"))
        self.assertNotIn("cql_filter", p)
        self.assertEqual(urls[1][1], fuente.MAX_LIVIANO_BYTES)
        # la de ayer todavía vale: rige hasta las 13:00 de hoy y la de hoy puede salir tarde
        falso, _ = _wfs_24h(_fc(), _liviana_24h("2026-09-21Z"))
        with mock.patch.object(_http, "get_bytes", falso):
            self.assertEqual(fuente.aviso_24h(HOY), [])

    def test_lluvia_24h_vista_vacia_o_detenida_es_falla(self):
        casos = {
            "vino vacía": _wfs_24h(_fc(), _fc())[0],
            "no se actualiza desde el 2026-09-20": _wfs_24h(_fc(), _liviana_24h("2026-09-20Z", "2026-09-19Z"))[0],
            # con zonas, pero de antes de ayer: tampoco es el aviso vigente
            "no se actualiza desde el 2026-09-19": _wfs_24h(_fc(_feature_24h("Nivel 2", fecha="2026-09-19Z")))[0],
        }
        for mensaje, falso in casos.items():
            with mock.patch.object(_http, "get_bytes", falso), self.assertRaisesRegex(ValueError, mensaje):
                fuente.aviso_24h(HOY)


class TestLenguaje(unittest.TestCase):
    def test_rangos_en_hora_de_peru(self):
        casos = [
            ((2026, 9, 23, 5), (2026, 9, 25, 4, 59, 59), "del 23 al 24 set"),
            ((2026, 9, 23, 5), (2026, 9, 24, 4, 59, 59), "el 23 set"),
            ((2026, 9, 30, 5), (2026, 10, 3, 5), "del 30 set al 2 oct"),
            ((2026, 9, 24, 15), (2026, 9, 27, 4, 59, 59), "desde las 10:00 del 24 set hasta el 26 set"),
            ((2026, 9, 22, 18), (2026, 9, 23, 18), "desde las 13:00 del 22 set hasta las 13:00 del 23 set"),
        ]
        for ini, fin, esperado in casos:
            self.assertEqual(tarea.rango_peru(datetime(*ini, tzinfo=UTC), datetime(*fin, tzinfo=UTC)), esperado)

    def test_detalle_con_intensidad_del_parrafo_oficial(self):
        desc = fuente.parse_descripciones(DETALLE)[(2026, 376)]
        self.assertEqual(
            tarea.detalle_meteorologico("PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE", desc,
                                        datetime(2026, 9, 23, 5, tzinfo=UTC), datetime(2026, 9, 25, 4, 59, 59, tzinfo=UTC)),
            "Lluvias de ligera a moderada intensidad en la sierra norte y costa norte, del 23 al 24 set")

    def test_detalle_sin_parrafo_y_con_departamentos(self):
        ini, fin = datetime(2026, 9, 23, 5, tzinfo=UTC), datetime(2026, 9, 24, 5, tzinfo=UTC)
        self.assertEqual(tarea.detalle_meteorologico("LLUVIA EN TUMBES Y PIURA", None, ini, fin),
                         "Lluvias en Tumbes y Piura, el 23 set")
        self.assertEqual(tarea.detalle_meteorologico("PRECIPITACIONES EN LA SIERRA (ACTUALIZACIÓN DEL AVISO 338)",
                                                     "Se esperan lluvias de moderada a fuerte intensidad.", ini, fin),
                         "Lluvias de moderada a fuerte intensidad en la sierra, el 23 set")
        self.assertEqual(tarea.detalle_meteorologico("NEVADA EN LA SIERRA SUR", None, ini, fin),
                         "Nevadas en la sierra sur, el 23 set")

    def test_intensidad_solo_de_la_primera_oracion(self):
        self.assertIsNone(tarea.intensidad("Se prevé lluvia en la sierra. Vientos de fuerte intensidad."))
        self.assertEqual(tarea.intensidad("llovizna de moderada a fuerte   intensidad en la costa"),
                         "de moderada a fuerte intensidad")

    def test_detalle_24h(self):
        self.assertEqual(tarea.detalle_24h(3, datetime(2026, 9, 22, 18, tzinfo=UTC), datetime(2026, 9, 23, 18, tzinfo=UTC)),
                         "Lluvia de intensidad fuerte, con posibles aniegos e inundaciones (pronóstico de 24 h), "
                         "desde las 13:00 del 22 set hasta las 13:00 del 23 set")


D23, D24, D25, D26 = (datetime(2026, 9, d, 5, tzinfo=UTC) for d in (23, 24, 25, 26))
TITULO_376 = "PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE"


class TestAlertas(unittest.TestCase):
    def test_una_por_aviso_y_departamento_con_el_nivel_mas_alto(self):
        filas = [
            ("meteorologico", 2026, 376, 2, TITULO_376, None, D23, D24, ["Cajamarca", "Piura"]),
            ("meteorologico", 2026, 376, 3, TITULO_376, None, D24, D25, ["Cajamarca"]),
            ("lluvia24h", 2026, None, 2, tarea.TITULO_24H, None, D23, D24, ["Cajamarca"]),
            ("meteorologico", 2026, 380, 4, "LLUVIA EN LA SELVA", None, D23, D24, []),   # sin departamentos
        ]
        alertas = tarea.alertas_de_avisos(filas)
        resumen = [(a["referencia"], a["zona"], a["nivel"]) for a in alertas]
        self.assertEqual(resumen, [("SENAMHI aviso 376", "Cajamarca", "alerta"),
                                   ("SENAMHI aviso 376", "Piura", "aviso"),
                                   ("SENAMHI lluvia 24h", "Cajamarca", "aviso")])
        caj = alertas[0]
        self.assertEqual((caj["tipo"], caj["valor"], caj["umbral"]), ("aviso", None, None))
        self.assertEqual(caj["detalle"], "Lluvias en la sierra norte y costa norte, del 23 al 24 set")
        self.assertEqual(alertas[1]["detalle"], "Lluvias en la sierra norte y costa norte, el 23 set")
        self.assertTrue(alertas[2]["detalle"].startswith("Lluvia de intensidad moderada (pronóstico de 24 h)"))

    def test_rojo_es_emergencia(self):
        [a] = tarea.alertas_de_avisos([("meteorologico", 2026, 1, 4, TITULO_376, None, D23, D24, ["Tumbes"])])
        self.assertEqual(a["nivel"], "emergencia")

    def test_ventana_de_48_h_por_aviso_y_no_por_area(self):
        # AHORA + 48 h = 25 set 00:48 UTC: el día 25 de Lima (desde las 05:00 UTC) queda fuera,
        # pero es del mismo aviso que el 23 y el 24, así que cuenta (antes decía "del 23 al 24").
        filas = [
            ("meteorologico", 2026, 380, 2, TITULO_376, None, D23, D24, ["Cajamarca"]),
            ("meteorologico", 2026, 380, 2, TITULO_376, None, D24, D25, ["Cajamarca"]),
            ("meteorologico", 2026, 380, 3, TITULO_376, None, D25, D26, ["Cajamarca", "Piura"]),
            ("meteorologico", 2026, 381, 4, TITULO_376, None, D25, D26, ["Tumbes"]),   # entero fuera
        ]
        dentro = tarea.en_ventana(filas, AHORA)
        self.assertEqual(dentro, filas[:3])
        alertas = tarea.alertas_de_avisos(dentro)
        self.assertEqual([(a["referencia"], a["zona"], a["nivel"], a["detalle"]) for a in alertas], [
            ("SENAMHI aviso 380", "Cajamarca", "alerta", "Lluvias en la sierra norte y costa norte, del 23 al 25 set"),
            ("SENAMHI aviso 380", "Piura", "alerta", "Lluvias en la sierra norte y costa norte, el 25 set"),
        ])
        # un día después el 381 ya entra
        self.assertEqual(len(tarea.en_ventana(filas, AHORA + timedelta(days=1))), 4)


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

    def executemany(self, sql, filas):
        self.conn.registro.append((sql, list(filas)))

    def fetchone(self):
        assert self.ultima == tarea.SQL_HAY_TABLA, self.ultima
        return (self.conn.hay_tabla, self.conn.hay_tabla and self.conn.hay_columnas)

    def fetchall(self):
        if self.ultima == tarea.SQL_PREVIOS:
            return self.conn.previos
        if self.ultima == tarea.SQL_PREVIOS_V1:   # sin las columnas de íconos
            return [p[:4] for p in self.conn.previos]
        assert self.ultima == tarea.SQL_LLUVIA_VIGENTE, self.ultima
        return self.conn.lluvia


class _Conexion:
    """Anota cada sentencia. SQL_PREVIOS devuelve `previos`; SQL_LLUVIA_VIGENTE, `lluvia`
    (las filas que la BD tendría después de insertar); SQL_HAY_TABLA, `hay_tabla` y
    `hay_columnas` (la migración de íconos)."""

    def __init__(self, previos=(), lluvia=(), hay_tabla=True, hay_columnas=True):
        self.previos, self.lluvia, self.registro = list(previos), list(lluvia), []
        self.hay_tabla, self.hay_columnas = hay_tabla, hay_columnas

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]


def _area(numero=376, mapa=1, nivel=2, inicio=D23, fin=D24, tipo="meteorologico"):
    return fuente.Area(tipo=tipo, anio=2026, numero=numero, mapa=mapa, nivel=nivel, inicio=inicio,
                       fin=fin, geometrias=[{"type": "MultiPolygon", "coordinates": [_anillo(-78.6, -7.2)]}])


def _previo(numero, horas, general=None, dias=None, incompleto=False):
    """Fila de SQL_PREVIOS: guardado hace `horas`; dias como los da jsonb_object_agg."""
    return (2026, numero, AHORA - timedelta(hours=horas), general,
            {str(m): t for m, t in (dias or {}).items()}, incompleto)


A376 = _aviso()
A377 = _aviso(377, date(2026, 9, 24), date(2026, 9, 26), "INCREMENTO DE TEMPERATURA DIURNA EN LA SELVA")
A374 = _aviso(374, date(2026, 9, 20), date(2026, 9, 22), "LLOVIZNA EN LA COSTA CENTRO Y SUR")
ANTERIOR = fuente.Aviso(numero=370, anio=2026, titulo="INCREMENTO DE VIENTO EN LA COSTA", estado="vigente",
                        emision=date(2026, 9, 15), inicio=date(2026, 9, 17), fin=date(2026, 9, 19), nivel=3)
LLUVIA_376 = ("meteorologico", 2026, 376, 2, TITULO_376, "de ligera a moderada intensidad", D23, D25, ["Cajamarca"])
LLUVIA_24H = ("lluvia24h", 2026, None, 2, tarea.TITULO_24H, None,
              datetime(2026, 9, 22, 18, tzinfo=UTC), datetime(2026, 9, 23, 18, tzinfo=UTC), ["Cajamarca", "Piura"])
AREAS_24H = [_area(None, nivel=2, tipo="lluvia24h", inicio=datetime(2026, 9, 22, 18, tzinfo=UTC),
                   fin=datetime(2026, 9, 23, 18, tzinfo=UTC))]


A375 = _aviso(375, date(2026, 9, 23), date(2026, 9, 25), "INCREMENTO DE TEMPERATURA DIURNA EN LA COSTA Y SIERRA")
TEXTOS = fuente.parse_textos(VIGENTES)
GENERAL_376, DIAS_376 = TEXTOS[(2026, 376)].general, TEXTOS[(2026, 376)].dias


def _por_mapa(**mapas):
    """areas_aviso simulado: un área de nivel 2 por mapa (el 1 es del 23); mapas={'375': 3}."""
    def areas(a):
        n = mapas.get(str(a.numero), 1)
        return [_area(a.numero, m, inicio=D23 + timedelta(days=m - 1), fin=D24 + timedelta(days=m - 1))
                for m in range(1, n + 1)], 0
    return areas


def _por_aviso(**errores):
    """areas_aviso simulado: el 376 con dos días, el 377 con uno; errores={'376': excepción}."""
    def areas(a):
        if str(a.numero) in errores:
            raise errores[str(a.numero)]
        if a.numero == 376:
            return [_area(376, 1, inicio=D23, fin=D24), _area(376, 2, inicio=D24, fin=D25)], 0
        return [_area(a.numero, 1, inicio=D24, fin=D25)], 3
    return areas


class TestFilaArea(unittest.TestCase):
    def test_parrafo_de_otro_dia_no_se_guarda(self):
        # el mapa 2 del 375 es del jueves 24, pero su párrafo dice "El martes 22"
        notas = tarea.notas_lectura()
        texto = TEXTOS[(2026, 375)]
        filas = [tarea._fila_area(_area(375, m, nivel, inicio=D23 + timedelta(days=m - 1), fin=D24 + timedelta(days=m - 1)),
                                  A375, texto, notas)
                 for m in (1, 2, 3) for nivel in (2, 3)]
        self.assertEqual([f["texto_dia"] is not None for f in filas], [True, True, False, False, True, True])
        self.assertTrue(filas[0]["texto_dia"].startswith("El miércoles 23 de setiembre"))
        self.assertEqual(notas["fecha_no_coincide"], ["aviso 375 mapa 2"])   # una vez, aunque tenga 2 niveles
        # no es de lluvia: sin ícono ni lectura, pero con su párrafo general
        self.assertEqual({(f["icono"], f["lectura"]) for f in filas}, {(None, None)})
        self.assertTrue(filas[0]["descripcion"].startswith("El SENAMHI informa que, desde el miércoles 23"))
        self.assertEqual((notas["iconos"], notas["mm_literal"], notas["sin_general"]), ({}, [], []))

    def test_376_con_icono_lectura_y_texto_del_dia(self):
        notas = tarea.notas_lectura()
        fila = tarea._fila_area(_area(376, 1), A376, TEXTOS[(2026, 376)], notas)
        self.assertEqual((fila["icono"], fila["texto_dia"], fila["descripcion"]), ("gota", DIAS_376[1], GENERAL_376))
        leido = json.loads(fila["lectura"])
        self.assertEqual((leido["v"], leido["fenomeno"], leido["descargas"], leido["una_region"]), (1, "lluvia", "si", False))
        self.assertEqual([(m["lugar"], m["hasta"]) for m in leido["montos"]],
                         [("Tumbes", 12), ("Costa de Piura", 6), ("Sierra norte", 15)])
        self.assertIn("ráfagas de viento", leido["frase_descargas"])   # el jsonb guarda las tildes tal cual
        self.assertEqual(notas, {"iconos": {"376": "gota"}, "fecha_no_coincide": [], "mm_literal": [], "sin_general": []})

    def test_parrafo_del_dia_sin_mm_leidos_va_literal(self):
        notas = tarea.notas_lectura()
        texto = fuente.TextoAviso(GENERAL_376, {1: "El miércoles 23 de setiembre se esperan acumulados de lluvia "
                                                    "entre los 5 y 14 mm/día."})
        fila = tarea._fila_area(_area(376, 1), A376, texto, notas)
        self.assertIsNotNone(fila["texto_dia"])
        self.assertIsNone(json.loads(fila["lectura"])["montos"])
        self.assertEqual(notas["mm_literal"], ["aviso 376 mapa 1"])

    def test_lluvia_24h(self):
        notas = tarea.notas_lectura()
        fila = tarea._fila_area(AREAS_24H[0], None, None, notas)
        self.assertEqual((fila["icono"], json.loads(fila["lectura"]), fila["texto_dia"]),
                         ("gota", {"v": 1, "fenomeno": "lluvia"}, None))
        self.assertEqual(notas["iconos"], {"24h": "gota"})

    def test_sql_area_con_anclas_y_columnas_nuevas(self):
        for texto in ("st_maximuminscribedcircle(d.geom)", "from st_dump(g.geom) d", "anclas = excluded.anclas",
                      "texto_dia = excluded.texto_dia", "icono = excluded.icono", "lectura = excluded.lectura",
                      "%(texto_dia)s::text, %(icono)s::text, %(lectura)s::jsonb"):
            self.assertIn(texto, tarea.SQL_AREA)
        self.assertNotIn("texto_dia", tarea.SQL_AREA_V1)
        self.assertNotIn("anclas", tarea.SQL_AREA_V1)
        # las columnas del insert y los valores del select van en el mismo orden
        cols = re.search(r"insert into aviso_senamhi \((.*?)\)", tarea.SQL_AREA, re.S).group(1)
        self.assertTrue(re.sub(r"\s+", " ", cols).endswith("departamentos, texto_dia, icono, lectura, anclas"))

    def test_la_migracion_calcula_las_anclas_igual(self):
        # la migración de íconos completa las filas ya guardadas con la misma subconsulta
        [migracion] = (RAIZ / "supabase" / "migrations").glob("*avisos_iconos.sql")
        sql = migracion.read_text(encoding="utf-8")

        def anclas(texto):
            m = re.search(r"select coalesce\(jsonb_agg.*?x\.km2 >= 300\)", texto, re.S)
            return re.sub(r"\s+", " ", m.group(0))

        self.assertEqual(anclas(sql), anclas(tarea.SQL_AREA).replace("st_dump(g.geom)", "st_dump(a.geom)"))
        for columna in ("texto_dia text", "icono text", "lectura jsonb", "anclas jsonb"):
            self.assertIn(f"add column {columna}", sql)
        self.assertIn("texto_dia, icono, lectura, anclas", sql)   # en la vista aviso_vigente


class TestTarea(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.INFO)
        self.addCleanup(logging.disable, logging.NOTSET)

    def correr(self, conn=None, tabla=None, error_tabla=None, areas=None, a24=None, error_24h=None,
               textos=None, pagina=None):
        """pagina: HTML de la tabla, leído con el parse_tabla de verdad (en vez de `tabla`).
        textos: lo que devuelve la página de vigentes (fuente.textos), o una excepción."""
        conn = conn or _Conexion(lluvia=[LLUVIA_376, LLUVIA_24H])

        @contextmanager
        def falso_conectar():
            yield conn

        tabla = tabla or fuente.TablaAvisos(avisos=[A377, A376, A374, ANTERIOR], filas=2054)
        if pagina is not None:
            error_tabla = lambda hoy: fuente.parse_tabla(pagina, hoy)   # noqa: E731
        self.mocks = {
            "tabla_avisos": mock.Mock(return_value=tabla, side_effect=error_tabla),
            "areas_aviso": mock.Mock(side_effect=areas or _por_aviso()),
            "aviso_24h": mock.Mock(return_value=AREAS_24H if a24 is None else a24, side_effect=error_24h),
            "textos": mock.Mock(**({"side_effect": textos} if isinstance(textos, Exception) else
                                   {"return_value": textos or {(2026, 376): fuente.TextoAviso("El SENAMHI informa que...")}})),
        }
        self.excepcion = None
        with mock.patch.object(tarea, "conectar", falso_conectar), \
             mock.patch.multiple(fuente, **self.mocks):
            try:
                devuelto = tarea.actualizar(ahora=AHORA)
            except Exception as e:
                self.excepcion, devuelto = e, None
        [(servicio, datos)] = conn.params(SQL_LATIDO)
        self.assertEqual(servicio, "avisos")
        resumen = json.loads(datos)
        if devuelto is not None:
            self.assertEqual(resumen, devuelto)
        return conn, resumen

    def test_todo_responde(self):
        conn, resumen = self.correr()
        # 374 terminó hoy a las 23:59 de Lima (aún vigente a las 19:48); 370 ya terminó
        self.assertEqual(resumen["vigentes"], [377, 376, 374])
        self.assertEqual((resumen["bajados"], resumen["reusados"]), ([377, 376, 374], []))
        self.assertEqual(resumen["fallas"], [])
        self.assertIn("aviso 377: 3 polígonos descartados (fechas fuera de la vigencia de la tabla o datos incompletos)",
                      resumen["avisos"])
        # nada que conservar: se reemplazan todos los meteorológicos, y también el de 24 h
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO),
                         [(["2026-377", "2026-376", "2026-374"], True, [])])
        self.assertEqual(len(conn.params(tarea.SQL_BORRAR_24H)), 1)
        self.assertEqual(len(conn.params(tarea.SQL_BORRAR_TERMINADOS)), 1)
        [filas] = conn.params(tarea.SQL_AREA)
        # 376 (2 días) + 377 + 374 (su área termina el 25: sigue) + 24 h
        self.assertEqual([(f["tipo"], f["numero"], f["mapa"]) for f in filas],
                         [("meteorologico", 377, 1), ("meteorologico", 376, 1), ("meteorologico", 376, 2),
                          ("meteorologico", 374, 1), ("lluvia24h", None, 1)])
        f376 = filas[1]
        self.assertEqual((f376["tema"], f376["descripcion"], f376["tolerancia"]),
                         ("lluvia", "El SENAMHI informa que...", tarea.TOLERANCIA_GRADOS))
        self.assertEqual(json.loads(f376["geometrias"])[0]["type"], "MultiPolygon")
        self.assertEqual((filas[4]["titulo"], filas[4]["descripcion"], filas[4]["emision"]),
                         (tarea.TITULO_24H, tarea.DESCRIPCION_24H[2], date(2026, 9, 22)))
        self.assertEqual(filas[4]["url"], fuente.URL_AVISO_24H)
        # alertas: se borran las re-evaluadas, como la tabla respondió las de avisos que ya no
        # están, y las de avisos sin áreas de lluvia sin terminar (las de SQL_LLUVIA_VIGENTE)
        [(refrescadas, horas, tabla_ok, conservar, con_areas)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertEqual(refrescadas, ["SENAMHI aviso 374", "SENAMHI aviso 376", "SENAMHI aviso 377", "SENAMHI lluvia 24h"])
        self.assertEqual((horas, tabla_ok, conservar), (6, True, []))
        self.assertEqual(con_areas, ["SENAMHI aviso 376", "SENAMHI lluvia 24h"])
        [alertas] = conn.params(SQL_ALERTA)
        self.assertEqual([(a[0], a[1], a[2], a[3]) for a in alertas],
                         [("aviso", "SENAMHI aviso 376", "Cajamarca", "aviso"),
                          ("aviso", "SENAMHI lluvia 24h", "Cajamarca", "aviso"),
                          ("aviso", "SENAMHI lluvia 24h", "Piura", "aviso")])
        self.assertEqual(alertas[0][4], "Lluvias de ligera a moderada intensidad en la sierra norte y costa norte, "
                                        "del 23 al 24 set")
        self.assertEqual((resumen["areas"], resumen["alertas"], resumen["lluvia24h"]), (5, 3, "2026-09-22"))
        # la página de textos oficiales se pidió una vez, con el enlace de un aviso
        self.mocks["textos"].assert_called_once_with(A377.url)
        # la tabla y el de 24 h se leen con la fecha de Perú (en UTC ya es 23)
        self.mocks["tabla_avisos"].assert_called_once_with(HOY)
        self.mocks["aviso_24h"].assert_called_once_with(HOY)

    def test_si_la_tabla_falla_no_se_borran_los_meteorologicos(self):
        with self.assertLogs(tarea.log, logging.ERROR):
            conn, resumen = self.correr(error_tabla=RuntimeError("HTTP Error 503"))
        self.assertIsNone(self.excepcion)   # el de 24 h sí respondió
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO), [])
        self.mocks["areas_aviso"].assert_not_called()
        self.assertEqual(len(conn.params(tarea.SQL_BORRAR_TERMINADOS)), 1)   # lo terminado se va igual
        [(refrescadas, _, tabla_ok, conservar, con_areas)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertEqual((refrescadas, tabla_ok, conservar), (["SENAMHI lluvia 24h"], False, []))
        # la fila del 376 que sigue en la BD no refresca su alerta (caducará a las 6 h o cuando
        # el 376 ya no tenga áreas sin terminar)
        self.assertIn("SENAMHI aviso 376", con_areas)
        [alertas] = conn.params(SQL_ALERTA)
        self.assertEqual({a[1] for a in alertas}, {"SENAMHI lluvia 24h"})
        self.assertEqual((resumen["vigentes"], resumen["fallas"]), (None, ["tabla"]))
        self.assertEqual(resumen["avisos"], ["tabla de avisos: RuntimeError: HTTP Error 503"])

    def test_fila_activa_ilegible_solo_reemplaza_lo_rebajado(self):
        tabla = fuente.TablaAvisos(avisos=[A376], filas=2054, problemas=["fila '378 (emitido)': fecha ilegible"])
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen = self.correr(tabla=tabla)
        # el 378 podría seguir vigente: no se borra nada que no se haya vuelto a bajar
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO), [(["2026-376"], False, [])])
        [(refrescadas, _, tabla_entera, _, _)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertEqual((refrescadas, tabla_entera), (["SENAMHI aviso 376", "SENAMHI lluvia 24h"], False))
        self.assertEqual(resumen["fallas"], ["tabla incompleta"])
        self.assertIn("tabla de avisos: fila '378 (emitido)': fecha ilegible", resumen["avisos"])

    def test_tabla_con_la_etiqueta_cambiada_no_borra_lo_guardado(self):
        # Hallazgo: con la etiqueta cambiada la tabla se leía como "no hay avisos" y se borraba
        # todo lo meteorológico con sus alertas, sin fallas.
        pagina = re.sub(r"\((emitido|vigente)\)", r"[\1]", TABLA)
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen = self.correr(pagina=pagina)
        self.mocks["tabla_avisos"].assert_called_once_with(HOY)
        self.mocks["areas_aviso"].assert_not_called()
        self.assertEqual(resumen["vigentes"], [])
        self.assertEqual(resumen["fallas"], ["tabla incompleta"])
        self.assertEqual(sum(a.startswith("tabla de avisos: fila") for a in resumen["avisos"]), 3)
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO), [])
        [(refrescadas, _, tabla_entera, _, _)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertEqual((refrescadas, tabla_entera), (["SENAMHI lluvia 24h"], False))

    def test_tabla_con_la_cabecera_cambiada_es_falla(self):
        pagina = TABLA.replace("<th>Inicio</th><th>Fin</th>", "<th>Fin</th><th>Inicio</th>")
        with self.assertLogs(tarea.log, logging.ERROR):
            conn, resumen = self.correr(pagina=pagina)
        self.assertEqual((resumen["vigentes"], resumen["fallas"]), (None, ["tabla"]))
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO), [])

    def test_actualizacion_reemplaza_al_original(self):
        a373 = _aviso(373, date(2026, 9, 22), date(2026, 9, 24), "PRECIPITACIONES EN LA SIERRA NORTE")
        a378 = _aviso(378, date(2026, 9, 23), date(2026, 9, 24),
                      "PRECIPITACIONES EN LA SIERRA NORTE (ACTUALIZACIÓN DEL AVISO 373)")
        lluvia_378 = ("meteorologico", 2026, 378, 3, a378.titulo, None, D23, D25, ["Cajamarca"])
        conn = _Conexion(previos=[_previo(373, 1)], lluvia=[lluvia_378])
        conn, resumen = self.correr(conn=conn, tabla=fuente.TablaAvisos(avisos=[a378, A376, a373], filas=2054))
        # el original no se baja ni genera alertas, y sus filas y alertas se borran
        self.assertEqual([c.args[0].numero for c in self.mocks["areas_aviso"].call_args_list], [378, 376])
        self.assertEqual(resumen["vigentes"], [378, 376])
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO), [(["2026-378", "2026-376", "2026-373"], True, [])])
        [(refrescadas, _, _, conservar, _)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertEqual(refrescadas, ["SENAMHI aviso 373", "SENAMHI aviso 376", "SENAMHI aviso 378", "SENAMHI lluvia 24h"])
        self.assertEqual(conservar, [])
        [alertas] = conn.params(SQL_ALERTA)
        self.assertEqual([(a[1], a[2], a[3]) for a in alertas], [("SENAMHI aviso 378", "Cajamarca", "alerta")])
        self.assertIn("aviso 373: reemplazado por su actualización (aviso 378)", resumen["avisos"])
        self.assertEqual(resumen["fallas"], [])

    def test_si_la_actualizacion_falla_se_conserva_el_original(self):
        a373 = _aviso(373, date(2026, 9, 22), date(2026, 9, 24), "PRECIPITACIONES EN LA SIERRA NORTE")
        a378 = _aviso(378, date(2026, 9, 23), date(2026, 9, 24),
                      "PRECIPITACIONES EN LA SIERRA NORTE (ACTUALIZACIÓN DEL AVISO 373)")
        conn = _Conexion(previos=[_previo(373, 1)])
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen = self.correr(conn=conn, tabla=fuente.TablaAvisos(avisos=[a378, A376, a373], filas=2054),
                                        areas=_por_aviso(**{"378": TimeoutError("timed out")}))
        # sin la actualización en el mapa, el original (ya guardado) se queda, con sus alertas
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO), [(["2026-376"], True, ["2026-378", "2026-373"])])
        [(refrescadas, _, _, conservar, _)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertNotIn("SENAMHI aviso 373", refrescadas)
        self.assertEqual(conservar, ["SENAMHI aviso 378", "SENAMHI aviso 373"])
        self.assertEqual(resumen["fallas"], ["aviso 378"])
        self.assertIn("aviso 373: se conserva hasta que se pueda bajar su actualización (aviso 378)", resumen["avisos"])

    def test_wfs_sin_poligonos_es_falla(self):
        # Hallazgo: un WFS vacío borraba los polígonos y alertas del aviso con solo una nota.
        def areas(a):
            return ([], 0) if a.numero == 376 else _por_aviso()(a)

        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen = self.correr(areas=areas)
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO),
                         [(["2026-377", "2026-374"], True, ["2026-376"])])
        [(refrescadas, _, _, conservar, _)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertNotIn("SENAMHI aviso 376", refrescadas)
        self.assertEqual(conservar, ["SENAMHI aviso 376"])
        [alertas] = conn.params(SQL_ALERTA)
        self.assertNotIn("SENAMHI aviso 376", {a[1] for a in alertas})
        self.assertEqual(resumen["fallas"], ["aviso 376"])
        self.assertEqual(resumen["bajados"], [377, 374])
        self.assertIn("aviso 376: ValueError: el WFS no trae polígonos", resumen["avisos"])

    def test_alertas_de_avisos_terminados_se_borran_aunque_la_fuente_caiga(self):
        # El 376 y el de 24 h terminaron (ya no hay áreas de lluvia sin terminar) mientras la
        # tabla y el WFS de 24 h están caídos: sus alertas se borran igual, sin esperar 6 h.
        with self.assertLogs(tarea.log, logging.ERROR):
            conn, resumen = self.correr(error_tabla=OSError("503"), error_24h=OSError("timed out"),
                                        conn=_Conexion(lluvia=[]))
        [(refrescadas, _, tabla_entera, conservar, con_areas)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertEqual((refrescadas, tabla_entera, conservar, con_areas), ([], False, [], []))
        self.assertIn("or referencia <> all(%s::text[]))", tarea.SQL_BORRAR_ALERTAS_AVISO)

    def test_la_ventana_se_aplica_por_aviso(self):
        tres_dias = [("meteorologico", 2026, 376, 2, TITULO_376, None, D23, D24, ["Cajamarca"]),
                     ("meteorologico", 2026, 376, 3, TITULO_376, None, D25, D26, ["Cajamarca"]),
                     ("meteorologico", 2026, 374, 2, "LLOVIZNA EN LA COSTA", None, D25, D26, ["Lima"])]   # fuera
        conn, _ = self.correr(conn=_Conexion(lluvia=tres_dias))
        [alertas] = conn.params(SQL_ALERTA)
        self.assertEqual([(a[1], a[2], a[3], a[4]) for a in alertas], [
            ("SENAMHI aviso 376", "Cajamarca", "alerta", "Lluvias en la sierra norte y costa norte, del 23 al 25 set")])
        # la ventana ya no va en el SQL: se leen todas las áreas de lluvia sin terminar
        self.assertEqual(conn.params(tarea.SQL_LLUVIA_VIGENTE), [None])

    def test_candado_al_abrir_la_escritura(self):
        conn, _ = self.correr()
        sentencias = [s for s, _ in conn.registro]
        self.assertEqual(sentencias[:4], [tarea.SQL_HAY_TABLA, tarea.SQL_PREVIOS, tarea.SQL_CANDADO,
                                          tarea.SQL_BORRAR_TERMINADOS])
        self.assertEqual(sentencias.count(tarea.SQL_CANDADO), 1)
        # de transacción: se suelta solo al commit o al rollback
        self.assertEqual(tarea.SQL_CANDADO, "select pg_advisory_xact_lock(hashtext('avisos'))")

    def test_departamento_por_cercania_solo_a_menos_de_0_1_grados(self):
        # Hallazgo: el respaldo "estación más cercana" no tenía límite y un polígono mar
        # adentro quedaba en Piura. El límite va en la subconsulta del respaldo.
        respaldo = re.search(r"\(select array\[e\.departamento\].*?limit 1\)", tarea.SQL_AREA, re.S)
        self.assertIsNotNone(respaldo)
        self.assertIn("st_dwithin(e.geom, g.geom, 0.1)", respaldo.group(0))

    def test_si_falla_el_wfs_de_un_aviso_se_conserva_lo_suyo(self):
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen = self.correr(areas=_por_aviso(**{"376": TimeoutError("timed out")}))
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO),
                         [(["2026-377", "2026-374"], True, ["2026-376"])])
        [filas] = conn.params(tarea.SQL_AREA)
        self.assertNotIn(376, [f["numero"] for f in filas])
        [(refrescadas, _, tabla_ok, conservar, _)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertNotIn("SENAMHI aviso 376", refrescadas)
        self.assertEqual((tabla_ok, conservar), (True, ["SENAMHI aviso 376"]))
        [alertas] = conn.params(SQL_ALERTA)
        self.assertNotIn("SENAMHI aviso 376", {a[1] for a in alertas})   # su alerta anterior se queda
        self.assertEqual(resumen["fallas"], ["aviso 376"])
        self.assertIn("aviso 376: TimeoutError: timed out", resumen["avisos"])

    def test_aviso_guardado_hace_poco_no_se_vuelve_a_bajar(self):
        previos = [_previo(376, 2, "El SENAMHI informa que..."), _previo(377, 7)]
        conn = _Conexion(previos=previos, lluvia=[LLUVIA_376])
        conn, resumen = self.correr(conn=conn)
        self.assertEqual([c.args[0].numero for c in self.mocks["areas_aviso"].call_args_list], [377, 374])
        self.assertEqual((resumen["bajados"], resumen["reusados"]), ([377, 374], [376]))
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO),
                         [(["2026-377", "2026-374"], True, ["2026-376"])])
        # el reusado sigue generando su alerta (la tabla lo lista y sus polígonos están en la BD)
        [alertas] = conn.params(SQL_ALERTA)
        self.assertEqual([a[1] for a in alertas], ["SENAMHI aviso 376"])
        [(refrescadas, _, _, conservar, _)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertIn("SENAMHI aviso 376", refrescadas)
        self.assertEqual(conservar, [])

    def test_parrafo_caido_no_es_falla(self):
        @contextmanager
        def falso_conectar():
            yield conn

        conn = _Conexion()
        tabla = fuente.TablaAvisos(avisos=[A376], filas=1)
        with mock.patch.object(tarea, "conectar", falso_conectar), \
             mock.patch.multiple(fuente, tabla_avisos=mock.Mock(return_value=tabla),
                                 areas_aviso=mock.Mock(side_effect=_por_aviso()),
                                 aviso_24h=mock.Mock(return_value=[]),
                                 textos=mock.Mock(side_effect=OSError("red"))), \
             self.assertLogs(tarea.log, logging.WARNING):
            resumen = tarea.actualizar(ahora=AHORA)
        self.assertEqual(resumen["fallas"], [])
        self.assertEqual(resumen["avisos"], ["textos oficiales: OSError: red"])
        [filas] = conn.params(tarea.SQL_AREA)
        self.assertEqual({f["descripcion"] for f in filas}, {None})
        # sin párrafo general: gota (el rayo no se inventa), sin lectura y anotado para reintentar
        self.assertEqual({(f["icono"], f["lectura"], f["texto_dia"]) for f in filas}, {("gota", None, None)})
        self.assertEqual(resumen["lectura"]["sin_general"], [376])

    def test_aviso_24h_desactualizado(self):
        viejo = [_area(None, tipo="lluvia24h", inicio=datetime(2026, 9, 21, 18, tzinfo=UTC),
                       fin=datetime(2026, 9, 22, 18, tzinfo=UTC))]
        conn, resumen = self.correr(a24=viejo, conn=_Conexion())
        self.assertEqual(len(conn.params(tarea.SQL_BORRAR_24H)), 1)   # respondió: el viejo se va
        self.assertIsNone(resumen["lluvia24h"])
        self.assertIn("lluvia 24 h: el último aviso publicado (del 2026-09-21) ya terminó", resumen["avisos"])

    def test_si_falla_el_24h_se_conserva(self):
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen = self.correr(error_24h=OSError("timed out"))
        self.assertEqual(conn.params(tarea.SQL_BORRAR_24H), [])
        [(refrescadas, *_)] = conn.params(tarea.SQL_BORRAR_ALERTAS_AVISO)
        self.assertNotIn("SENAMHI lluvia 24h", refrescadas)
        [alertas] = conn.params(SQL_ALERTA)
        self.assertNotIn("SENAMHI lluvia 24h", {a[1] for a in alertas})
        self.assertEqual(resumen["fallas"], ["lluvia24h"])

    def test_migracion_pendiente_no_consulta_ni_escribe(self):
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen = self.correr(conn=_Conexion(hay_tabla=False))
        self.assertIsNone(self.excepcion)
        for nombre in ("tabla_avisos", "areas_aviso", "aviso_24h", "textos"):
            self.mocks[nombre].assert_not_called()
        self.assertEqual([s for s, _ in conn.registro], [tarea.SQL_HAY_TABLA, SQL_LATIDO])
        self.assertEqual((resumen["fallas"], resumen["avisos"]), (["migracion"], [tarea.AVISO_SIN_TABLA]))

    def test_si_fallan_tabla_y_24h_el_latido_lo_dice_y_la_tarea_falla(self):
        with self.assertLogs(tarea.log, logging.ERROR):
            conn, resumen = self.correr(error_tabla=OSError("a"), error_24h=OSError("b"), conn=_Conexion())
        self.assertIsInstance(self.excepcion, RuntimeError)
        self.assertEqual(resumen["fallas"], ["tabla", "lluvia24h"])
        self.assertEqual(conn.params(tarea.SQL_BORRAR_METEOROLOGICO) + conn.params(tarea.SQL_BORRAR_24H), [])
        self.assertEqual(conn.params(SQL_ALERTA), [])

    # --- íconos y textos oficiales ---------------------------------------------------------
    def test_filas_con_icono_lectura_y_texto_del_dia(self):
        conn, resumen = self.correr(tabla=fuente.TablaAvisos(avisos=[A375, A376], filas=2054),
                                    areas=_por_mapa(**{"375": 3, "376": 2}), textos=TEXTOS)
        [filas] = conn.params(tarea.SQL_AREA)
        por_clave = {(f["tipo"], f["numero"], f["mapa"]): f for f in filas}
        f376 = por_clave[("meteorologico", 376, 2)]
        self.assertEqual((f376["icono"], f376["texto_dia"]), ("gota", DIAS_376[2]))
        self.assertEqual(json.loads(f376["lectura"])["montos"][2]["lugar"], "Sierra norte")
        self.assertIsNone(por_clave[("meteorologico", 375, 2)]["texto_dia"])
        self.assertEqual(por_clave[("lluvia24h", None, 1)]["icono"], "gota")
        self.assertEqual(resumen["lectura"], {"iconos": {"376": "gota", "24h": "gota"},
                                              "fecha_no_coincide": ["aviso 375 mapa 2"],
                                              "mm_literal": [], "sin_general": []})
        self.mocks["textos"].assert_called_once_with(A375.url)

    def test_lluvia_guardada_sin_icono_se_vuelve_a_bajar(self):
        # guardado hace 1 h, pero sin ícono (antes de la migración de íconos): se completa
        conn = _Conexion(previos=[_previo(376, 1, GENERAL_376, DIAS_376, incompleto=True)], lluvia=[LLUVIA_376])
        conn, resumen = self.correr(conn=conn, tabla=fuente.TablaAvisos(avisos=[A376], filas=2054),
                                    areas=_por_mapa(**{"376": 2}))
        self.assertEqual((resumen["bajados"], resumen["reusados"]), ([376], []))
        self.mocks["textos"].assert_not_called()   # ya tenía el general y los dos días
        [filas] = conn.params(tarea.SQL_AREA)
        self.assertEqual([(f["mapa"], f["icono"], f["texto_dia"]) for f in filas if f["numero"] == 376],
                         [(1, "gota", DIAS_376[1]), (2, "gota", DIAS_376[2])])
        # completo y reciente: se reusa
        conn = _Conexion(previos=[_previo(376, 1, GENERAL_376, DIAS_376)], lluvia=[LLUVIA_376])
        _, resumen = self.correr(conn=conn, tabla=fuente.TablaAvisos(avisos=[A376], filas=2054))
        self.assertEqual((resumen["bajados"], resumen["reusados"]), ([], [376]))
        # reciente, con ícono (gota) pero sin su párrafo general (no estaba en la página): también
        # se reusa; no se pide el WFS ni la página en cada corrida, se reintenta a las REFRESCO_HORAS
        conn = _Conexion(previos=[_previo(376, 1)], lluvia=[LLUVIA_376])
        _, resumen = self.correr(conn=conn, tabla=fuente.TablaAvisos(avisos=[A376], filas=2054))
        self.assertEqual((resumen["bajados"], resumen["reusados"]), ([], [376]))
        self.mocks["textos"].assert_not_called()
        self.mocks["areas_aviso"].assert_not_called()

    def test_con_la_pagina_caida_se_usan_los_textos_guardados(self):
        # el 376 se vuelve a bajar (7 h) con sus textos guardados; al 377 le falta el suyo y la página cae
        conn = _Conexion(previos=[_previo(376, 7, GENERAL_376, DIAS_376)], lluvia=[LLUVIA_376])
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen = self.correr(conn=conn, tabla=fuente.TablaAvisos(avisos=[A377, A376], filas=2054),
                                        areas=_por_mapa(**{"376": 2}), textos=OSError("timed out"))
        self.mocks["textos"].assert_called_once_with(A377.url)
        self.assertEqual(resumen["fallas"], [])
        self.assertIn("textos oficiales: OSError: timed out", resumen["avisos"])
        [filas] = conn.params(tarea.SQL_AREA)
        f376 = [f for f in filas if f["numero"] == 376]
        self.assertEqual([(f["descripcion"], f["texto_dia"]) for f in f376],
                         [(GENERAL_376, DIAS_376[1]), (GENERAL_376, DIAS_376[2])])
        self.assertEqual({json.loads(f["lectura"])["fenomeno"] for f in f376}, {"lluvia"})

    def test_la_pagina_se_baja_solo_si_falta_un_texto(self):
        tabla = fuente.TablaAvisos(avisos=[A376], filas=2054)
        # guardado hace 7 h con el general y los dos días: se re-bajan los polígonos, no la página
        conn = _Conexion(previos=[_previo(376, 7, GENERAL_376, DIAS_376)], lluvia=[LLUVIA_376])
        self.correr(conn=conn, tabla=tabla, areas=_por_mapa(**{"376": 2}))
        self.mocks["textos"].assert_not_called()
        # le falta el día 2: se baja, y se suma a lo guardado
        conn = _Conexion(previos=[_previo(376, 7, GENERAL_376, {1: DIAS_376[1]})], lluvia=[LLUVIA_376])
        conn, _ = self.correr(conn=conn, tabla=tabla, areas=_por_mapa(**{"376": 2}),
                              textos={(2026, 376): fuente.TextoAviso(None, {2: DIAS_376[2]})})
        self.mocks["textos"].assert_called_once_with(A376.url)
        [filas] = conn.params(tarea.SQL_AREA)
        self.assertEqual([(f["descripcion"], f["texto_dia"]) for f in filas if f["numero"] == 376],
                         [(GENERAL_376, DIAS_376[1]), (GENERAL_376, DIAS_376[2])])
        # un aviso que no es de lluvia no pide la página por sus días
        conn = _Conexion(previos=[_previo(377, 7, "El SENAMHI informa que...")])
        self.correr(conn=conn, tabla=fuente.TablaAvisos(avisos=[A377], filas=2054))
        self.mocks["textos"].assert_not_called()

    def test_sin_la_migracion_de_iconos_se_guardan_sin_iconos(self):
        conn = _Conexion(previos=[_previo(376, 1, GENERAL_376, incompleto=True)], lluvia=[LLUVIA_376],
                         hay_columnas=False)
        with self.assertLogs(tarea.log, logging.WARNING):
            conn, resumen = self.correr(conn=conn)
        sentencias = [s for s, _ in conn.registro]
        self.assertEqual(sentencias[:2], [tarea.SQL_HAY_TABLA, tarea.SQL_PREVIOS_V1])
        self.assertNotIn(tarea.SQL_AREA, sentencias)
        [filas] = conn.params(tarea.SQL_AREA_V1)
        self.assertEqual([f["numero"] for f in filas], [377, 374, None])   # el 376 (reciente) se reusa
        self.assertEqual(resumen["reusados"], [376])
        self.assertEqual((resumen["fallas"], resumen["avisos"][0], resumen["lectura"]),
                         ([], tarea.AVISO_SIN_ICONOS, None))
        self.assertEqual(len(conn.params(SQL_ALERTA)), 1)   # las alertas siguen

    def test_hay_tabla_pregunta_por_las_columnas_nuevas(self):
        self.assertIn("to_regclass('public.aviso_senamhi')", tarea.SQL_HAY_TABLA)
        self.assertIn("column_name = 'anclas'", tarea.SQL_HAY_TABLA)
        # incompleto = sin ícono (anterior a la migración), no sin lectura: un aviso cuyo párrafo
        # no está en la página tiene ícono (gota) y no se vuelve a pedir al WFS en cada corrida
        self.assertIn("bool_or(tema = 'lluvia' and icono is null)", tarea.SQL_PREVIOS)


if __name__ == "__main__":
    unittest.main()
