"""
Conector ENFEN: parseo del texto de los comunicados y descubrimiento del último; ICEN del
Informe Técnico (descubrimiento, no volver a bajar el ya leído ni uno más viejo, espera de
24 h para uno descartado, lectura de la Tabla 3); errores de pypdf como PDF ilegible.

Los fragmentos son texto real extraído con pypdf de los PDF oficiales (recortados, con
sus saltos de línea y espacios raros tal cual). Sin red ni pypdf: solo librería estándar.
"""
import io
import sys
import types
import unicodedata
import unittest
import urllib.error
from datetime import date, datetime, timedelta, timezone
from unittest import mock

from backend.connectors import _http, enfen

# --- Comunicado Oficial ENFEN N° 16-2026 (Alerta de El Niño Costero) --------------------
CO_16_2026 = """COMISIÓN MULTISECTORIAL ENCARGADA
DEL ESTUDIO NACIONAL DEL FENÓMENO “EL NIÑO” – ENFEN
Decreto Supremo N° 007-2017-PRODUCE
“Año de la esperanza y el fortalecimiento de la democracia “
https://enfen.imarpe.gob.p
e

COMUNICADO OFICIAL ENFEN N° 16-2026
14 de setiembre 2026

Estado del sistema de alerta: Alerta de El Niño Costero1

RESUMEN EJECUTIVO

ENFEN sostiene que El Niño Costero (región Niño 1+2) continuaría hasta mediados de otoño de 2027,
con la más alta probabilidad de una magnitud extraordinaria de setiembre 2026 a enero de 2027.

El Niño (región Niño 3.4) presentaría una magnitud muy fuerte de setiembre de 2026 a enero de 2027.
Entre febrero y marzo, cambiaría a fuerte, para continuar debilitándose durante el otoño hacia una
condición neutra.

Para el trimestre setiembre –noviembre se prevé que las temperaturas del aire se mantengan muy
superiores a las habituales en la costa peruana, registrand o nuevos récords.
La Comisión Multisectorial encargada del Estudio Nacional del Fenómeno “El Niño” (ENFEN),
luego de analizar la evolución reciente de las condiciones oceánicas y atmosféricas en el Pacífico
Tropical (Figura 1) y los pronósticos climáticos tanto nacionales como internacionales, mantiene el
estado de “Alerta de El Niño Costero” y sostiene, a la fecha, lo siguiente:
La Comisión Multisectorial del ENFEN mantendrá el monitoreo continuo de las condiciones
oceánicas, atmosféricas, hidrológicas y biológicas-pesqueras para actualizar sus pronósticos. El
próximo Comunicado Oficial se emitirá el lunes 28 de septiembre del 2026.
"""

# --- Comunicado Oficial ENFEN N° 05-2025 (No activo: pasa de Vigilancia a No Activo) -----
CO_05_2025 = """COMUNICADO OFICIAL ENFEN N°05-2025
16 de abril de 2025

Estado del sistema de alerta: No activo1

RESUMEN EJECUTIVO

ENFEN cambia el estado del “sistema de alerta ante El Niño costero” de "Vigilancia” a “No Activo” en la región
Niño 1+2, debido a que es más probable que las condiciones cálidas débiles actuales se atenúen
progresivamente, con una transición a la condición neutra durante mayo, manteniéndose así hasta diciembre de
2025.

La Comisión Multisectorial del ENFEN, en base al análisis de las condiciones oceánicas y
atmosféricas observadas hasta la fecha, así como de los pronósticos de los modelos climáticos
nacionales como internacionales, cambia el estado del “sistema de alerta ante El Niño costero” de
"Vigilancia” a “No Activo” en la región Niño 1+2 (Figura 1), debido a que es más probable que las
condiciones cálidas débiles2 actuales se atenúen progresivamente, con una transición a la condición
neutra durante mayo, manteniéndose así hasta diciembre de 2025 (Figura 2).
La Comisión Multisectorial del ENFEN continuará monitoreando la evolución de las condiciones
oceánicas, atmosféricas  y biológicas -pesqueras, y  actualizando las perspectivas. La emisión del
próximo Comunicado Oficial ordinario será el viernes 16 de mayo de 2025.
"""

# --- Comunicado Oficial ENFEN N° 01-2026 (Vigilancia de El Niño Costero) ----------------
CO_01_2026 = """COMUNICADO OFICIAL ENFEN N° 01-2026
15 de enero 2026

Estado del sistema de alerta: Vigilancia de El Niño Costero 1

RESUMEN EJECUTIVO

ENFEN cambia el Estado del Sistema de Alerta ante El Niño Costero/La Niña Costera de “No Activo”
a “Vigilancia de El Niño Costero. A partir de abril de 2026, las condiciones cálidas débiles  son las más
probables, persistiendo al menos hasta octubre de 2026, lo cual configuraría el desarrollo de un evento
de El Niño Costero de magnitud débil, por lo pronto.
La Comisión Multisectorial del ENFEN continuará monitoreando la evolución de las condiciones
oceánicas, atmosféricas y biológicas -pesqueras, y actualizando las pe rspectivas. La emisión
del próximo Comunicado Oficial ordinario será el viernes 30 de enero de 2026.
"""

# --- Comunicado Oficial ENFEN N° 13-2025 (diciembre; anuncia el próximo para enero) -------
CO_13_2025 = """COMUNICADO OFICIAL ENFEN N°13-2025
18 de diciembre 2025

Estado del sistema de alerta: No Activo1

RESUMEN EJECUTIVO

El ENFEN mantiene el Estado del Sistema de Alerta ante El Niño Costero/La Niña Costera en “No
Activo”. Para este verano (diciembre 2025 - marzo 2026), en la región Niño 1+2 , es más probable la
condición neutra (58 %), seguida de las condi ciones cálidas (32 %).
La Comisión Multisectorial del ENFEN continuará monitoreando la evolución de las condiciones
oceánicas, atmosféricas y biológicas -pesqueras, y actualizando las perspectivas. La emisión
del próximo Comunicado Oficial ordinario será el jueves 15 de enero de 2026.
"""

# --- Comunicado Extraordinario ENFEN N° 01-2025 -----------------------------------------
CE_01_2025 = """https://enfen.imarpe.gob.pe

COMUNICADO EXTRAORDINARIO ENFEN N° 01-2025
 28 de febrero de 2025

Estado del sistema de alerta: Vigilancia de El Niño Costero1


RESUMEN EJECUTIVO


El ENFEN ha activado la Vigilancia de El Niño Costero en la región Niño 1+2, ante la eventualidad de un
evento cálido débil y de corta duración. En el Pacífico central (3.4) se prevé una condición neutra hasta
septiembre de 2025.
oceánicas y atmosféricas y actualizando las perspectivas. El ENFEN emitirá su próximo comunicado
oficial el viernes 14 de marzo de 2025.
"""

# --- Comunicado Oficial ENFEN N° 13-2020 (Alerta de La Niña Costera, formato antiguo) ----
CO_13_2020 = """COMUNICADO OFICIAL ENFEN N°13-2020
Callao, 19 de octubre de 2020


Estado del sistema de alerta: Alerta de La Niña Costera1

La Comisión Multisectorial encargada del Estudio Nacional del Fenómeno “El Niño” (ENFEN) se reunió
para analizar la información oceanográfica, atmosférica, biológico -pesquera e hidrológica hasta el 16
de octubre de 2020, así como para actualizar las perspectivas.
El Índice Costero El Niño para el mes de agosto (ICEN2) y el ICEN temporal (ICEN -tmp) para
setiembre indican condiciones frías débiles.
y actualizando las perspectivas en forma más frecuente. La emisión del próximo comunicado será el
día 09 de noviembre de 2020.
"""

# --- Comunicado Oficial ENFEN N° 03-2022 ('Próxima actualización del Comunicado') -------
CO_03_2022 = """COMUNICADO OFICIAL ENFEN N°03-2022
14 de marzo de 2022

Estado del sistema de alerta: No Activo1

La Comisión Multisectorial del ENFEN cambia el estado del Sistema de alerta ante La Niña
costera a “No Activo”, debido a que es más probable que la temperatura superficial del mar
en la región Niño 1+2, que incluye la zona norte y centro del mar peruano, presente valores
en promedio dentro del rango neutral desde marzo hasta, por lo menos, inicios de invierno.
Próxima actualización del Comunicado: 13 de abril de 2022.
"""

# --- Nota al pie del CO 11-2026: umbrales del ICEN con coma decimal (no son valores) ----
NOTA_CO_11_2026 = """2  Las condiciones mensuales para la región Niño 1+2, que abarca el mar peruano al norte de los 10°S, se establecen en base al valor
del ICEN. En el caso de la magnitud cálida moderada, esta corresponde cuando el valor del ICEN es mayor a +1,3 y menor o igual
que +2,1; y para la magnitud cálida fuerte, corresponde el valor del ICEN mayor a +2,1 y menor o igual a +3,5 (Nota Técnica ENFEN
"""

# --- Tabla 3 del Informe Técnico ENFEN N° 16-2026 (los comunicados no la traen) ---------
TABLA_ICEN_IT_16 = """Tabla 3. Valores del ICEN, RONI, ONI y sus categorías desde agosto de 2025 hasta julio
de 2026, así como sus temporales para agosto.

Valores del índice Costero El Niño RONI ONI
Mes ICEN Categoría RONI Categoría ONI Categoría
Ago-25 –0.01 Neutra –0.63 Fría Débil –0.32 Neutra
Set-25 –0.22 Neutra –0.78 Fría Débil –0.45 Neutra
Mar-26 0.96 Cálida Débil –0.48 Neutra  0.11 Neutra
Abr-26 1.34 Cálida
Moderada –0.06 Neutra  0.48 Neutra
Jun-26 2.66 Cálida
Fuerte 0.97 Cálida Débil 1.41 Cálida
Moderada
Jul-26 3.38 Cálida
Fuerte 1.36 Cálida
Moderada 1.80 Cálida
Fuerte
Mes ICENtmp Mes RONItmp Mes ONItmp Mes
Ago-26  3.73
Cálida
Extraordinar
ia
 1.79 Cálida
Fuerte  2.35 Cálida Muy
Fuerte
"""

URL = "https://cdn.www.gob.pe/uploads/document/file/10621138/8596065-comunicado_of_enfen-n-16-2026.pdf"


class TestParseo(unittest.TestCase):
    def test_co_16_2026_alerta(self):
        c = enfen.parsear_texto(CO_16_2026, URL)
        self.assertEqual((c.numero, c.anio), (16, 2026))
        self.assertEqual(c.fecha, date(2026, 9, 14))            # "14 de setiembre 2026"
        self.assertEqual(c.estado, "Alerta de El Niño Costero")  # sin el "1" de la nota al pie
        self.assertEqual(c.proximo, date(2026, 9, 28))          # "lunes 28 de septiembre del 2026"
        self.assertEqual(c.url, URL)
        self.assertEqual(c.icen, [])
        self.assertIsNone(c.icen_tmp)
        self.assertTrue(c.resumen.startswith("ENFEN sostiene que El Niño Costero (región Niño 1+2) continuaría"))
        self.assertTrue(c.resumen.endswith("hacia una condición neutra."))
        self.assertNotIn("\n", c.resumen)
        self.assertNotIn("temperaturas del aire", c.resumen)     # máximo 3 frases

    def test_co_05_2025_no_activo(self):
        c = enfen.parsear_texto(CO_05_2025, "u")
        self.assertEqual((c.numero, c.anio, c.fecha), (5, 2025, date(2025, 4, 16)))
        self.assertEqual(c.estado, "No activo")
        self.assertEqual(c.proximo, date(2025, 5, 16))
        self.assertTrue(c.resumen.startswith('ENFEN cambia el estado del "sistema de alerta'))

    def test_co_01_2026_vigilancia(self):
        c = enfen.parsear_texto(CO_01_2026, "u")
        self.assertEqual((c.numero, c.anio, c.fecha), (1, 2026, date(2026, 1, 15)))
        self.assertEqual(c.estado, "Vigilancia de El Niño Costero")   # "Costero 1" con espacio
        self.assertEqual(c.proximo, date(2026, 1, 30))

    def test_diciembre_anuncia_enero_del_anio_siguiente(self):
        c = enfen.parsear_texto(CO_13_2025, "u")
        self.assertEqual(c.fecha, date(2025, 12, 18))
        self.assertEqual(c.estado, "No activo")
        self.assertEqual(c.proximo, date(2026, 1, 15))
        # Variante sin año: se infiere la primera fecha posterior a la emisión.
        sin_anio = CO_13_2025.replace("jueves 15 de enero de 2026", "jueves 15 de enero")
        self.assertEqual(enfen.parsear_texto(sin_anio, "u").proximo, date(2026, 1, 15))

    def test_proximo_sin_anio_septiembre(self):
        texto = CO_16_2026.replace("lunes 28 de septiembre del 2026", "lunes 28 de septiembre")
        self.assertEqual(enfen.parsear_texto(texto, "u").proximo, date(2026, 9, 28))

    def test_extraordinario(self):
        c = enfen.parsear_texto(CE_01_2025, "u")
        self.assertEqual((c.numero, c.anio, c.fecha), (1, 2025, date(2025, 2, 28)))
        self.assertEqual(c.estado, "Vigilancia de El Niño Costero")
        self.assertEqual(c.proximo, date(2025, 3, 14))
        self.assertTrue(c.resumen.startswith("El ENFEN ha activado la Vigilancia"))
        self.assertTrue(c.extraordinario)
        self.assertFalse(enfen.parsear_texto(CO_16_2026, "u").extraordinario)

    def test_estado_con_palabras_partidas_por_pypdf(self):
        texto = CO_16_2026.replace("Alerta de El Niño Costero", "Alerta de El Ni ño Coste ro", 1)
        self.assertEqual(enfen.parsear_texto(texto, "u").estado, "Alerta de El Niño Costero")

    def test_proximo_ignora_una_mencion_fuera_de_rango(self):
        texto = CO_16_2026.replace(
            "El próximo Comunicado Oficial",
            "En el próximo comunicado del 10 de setiembre de 2026 se revisó. El próximo Comunicado Oficial", 1)
        self.assertEqual(enfen.parsear_texto(texto, "u").proximo, date(2026, 9, 28))

    def test_llamadas_de_nota_al_pie_sin_borrar_cifras(self):
        self.assertEqual(enfen._RE_LLAMADA.sub("", "ERSST v5.0 y débiles2 actuales"), "ERSST v5.0 y débiles actuales")
        self.assertEqual(enfen._RE_LLAMADA.sub("", 'con "58 %" y "fuerte" 45 %'), 'con "58 %" y "fuerte" 45 %')
        self.assertEqual(enfen._RE_LLAMADA.sub("", '"Alerta de El Niño Costero" 1 ya que'),
                         '"Alerta de El Niño Costero" ya que')

    def test_formato_2020_la_nina_y_sin_resumen_ejecutivo(self):
        c = enfen.parsear_texto(CO_13_2020, "u")
        self.assertEqual((c.numero, c.anio), (13, 2020))
        self.assertEqual(c.fecha, date(2020, 10, 19))            # "Callao, 19 de octubre de 2020"
        self.assertEqual(c.estado, "Alerta de La Niña Costera")
        self.assertEqual(c.proximo, date(2020, 11, 9))           # "el día 09 de noviembre de 2020"
        self.assertTrue(c.resumen.startswith("La Comisión Multisectorial encargada"))
        self.assertEqual(c.icen, [])                             # menciona el ICEN pero sin valores

    def test_proxima_actualizacion_2022(self):
        c = enfen.parsear_texto(CO_03_2022, "u")
        self.assertEqual((c.fecha, c.estado, c.proximo), (date(2022, 3, 14), "No activo", date(2022, 4, 13)))

    def test_encabezado_sin_cero_ni_espacio(self):
        texto = CO_01_2026.replace("N° 01-2026", "N°2-2026")
        c = enfen.parsear_texto(texto, "u")
        self.assertEqual((c.numero, c.anio), (2, 2026))


class TestTolerancia(unittest.TestCase):
    def esperado(self, c):
        self.assertEqual((c.numero, c.anio, c.fecha, c.estado, c.proximo),
                         (16, 2026, date(2026, 9, 14), "Alerta de El Niño Costero", date(2026, 9, 28)))

    def test_crlf_nbsp_y_espacios_repetidos(self):
        texto = CO_16_2026.replace("\n", "\r\n").replace(" de ", " de  ")
        self.esperado(enfen.parsear_texto(texto, "u"))

    def test_tildes_descompuestas_nfd(self):
        self.esperado(enfen.parsear_texto(unicodedata.normalize("NFD", CO_16_2026), "u"))

    def test_mayusculas_y_sin_tildes(self):
        texto = CO_16_2026.replace(
            "Estado del sistema de alerta: Alerta de El Niño Costero1",
            "ESTADO DEL SISTEMA DE ALERTA: ALERTA DE EL NINO COSTERO",
        ).replace("14 de setiembre 2026", "14 DE SETIEMBRE DE 2026")
        self.esperado(enfen.parsear_texto(texto, "u"))

    def test_estado_desde_el_cuerpo_si_falta_el_rotulo(self):
        sin_rotulo = CO_16_2026.replace("Estado del sistema de alerta: Alerta de El Niño Costero1", "")
        c = enfen.parsear_texto(sin_rotulo, "u")
        self.assertEqual(c.estado, "Alerta de El Niño Costero")   # 'mantiene el estado de "Alerta..."'
        # 'cambia ... de "Vigilancia" a "No Activo"': vale el estado nuevo.
        sin_rotulo = CO_05_2025.replace("Estado del sistema de alerta: No activo1", "")
        self.assertEqual(enfen.parsear_texto(sin_rotulo, "u").estado, "No activo")
        # 'de "No Activo" a "Vigilancia de El Niño Costero.' (comilla de cierre ausente en el PDF)
        sin_rotulo = CO_01_2026.replace("Estado del sistema de alerta: Vigilancia de El Niño Costero 1", "")
        self.assertEqual(enfen.parsear_texto(sin_rotulo, "u").estado, "Vigilancia de El Niño Costero")

    def test_proximo_anterior_a_la_emision_se_descarta(self):
        texto = CO_16_2026.replace("lunes 28 de septiembre del 2026", "lunes 28 de septiembre del 2025")
        with self.assertLogs(enfen.log, "WARNING"):
            self.assertIsNone(enfen.parsear_texto(texto, "u").proximo)

    def test_sin_proximo(self):
        texto = CO_16_2026.split("La Comisión Multisectorial del ENFEN mantendrá")[0]
        self.assertIsNone(enfen.parsear_texto(texto, "u").proximo)


class TestICEN(unittest.TestCase):
    def test_tabla_del_informe_tecnico(self):
        c = enfen.parsear_texto(CO_16_2026 + TABLA_ICEN_IT_16, "u")
        self.assertEqual(c.icen, [
            ("2025-08", -0.01, "Neutra"),
            ("2025-09", -0.22, "Neutra"),
            ("2026-03", 0.96, "Cálida débil"),
            ("2026-04", 1.34, "Cálida moderada"),
            ("2026-06", 2.66, "Cálida fuerte"),
            ("2026-07", 3.38, "Cálida fuerte"),
        ])
        # "Extraordinar\nia" cortado por pypdf; no entra en la lista mensual.
        self.assertEqual(c.icen_tmp, ("2026-08", 3.73, "Cálida extraordinaria"))

    def test_coma_decimal(self):
        tabla = (TABLA_ICEN_IT_16.replace("3.38", "3,38").replace("3.73", "+3,73")
                 .replace("–0.01", "–0,01"))
        c = enfen.parsear_texto(CO_16_2026 + tabla, "u")
        self.assertIn(("2026-07", 3.38, "Cálida fuerte"), c.icen)
        self.assertIn(("2025-08", -0.01, "Neutra"), c.icen)
        self.assertEqual(c.icen_tmp, ("2026-08", 3.73, "Cálida extraordinaria"))

    def test_umbrales_con_coma_no_son_valores(self):
        c = enfen.parsear_texto(CO_16_2026 + NOTA_CO_11_2026, "u")
        self.assertEqual(c.icen, [])
        self.assertIsNone(c.icen_tmp)


class TestErrores(unittest.TestCase):
    def test_sin_estado(self):
        texto = "COMUNICADO OFICIAL ENFEN N° 16-2026 \n14 de setiembre 2026 \n \nRESUMEN EJECUTIVO \n"
        with self.assertRaisesRegex(ValueError, "estado"):
            enfen.parsear_texto(texto, "u")

    def test_estado_no_reconocido(self):
        texto = CO_16_2026.replace("Alerta de El Niño Costero1", "Aviso especial de oleajes")
        with self.assertRaisesRegex(ValueError, "no reconocido"):
            enfen.parsear_texto(texto, "u")

    def test_sin_fecha(self):
        texto = CO_16_2026.replace("14 de setiembre 2026", "")
        with self.assertRaisesRegex(ValueError, "fecha de emisión"):
            enfen.parsear_texto(texto, "u")

    def test_sin_encabezado(self):
        with self.assertRaisesRegex(ValueError, "encabezado"):
            enfen.parsear_texto(CO_16_2026.replace("COMUNICADO OFICIAL ENFEN N° 16-2026", ""), "u")

    def test_texto_vacio(self):
        for texto in ("", " \n \n", None):
            with self.assertRaises(ValueError):
                enfen.parsear_texto(texto, "u")


# --- Páginas de descubrimiento (fragmentos reales del HTML, 22-09-2026) ------------------

def _tarjeta(fecha, ficha, titulo):
    return (
        '<div class="col-md-6 py-2"><div class="p-4 shadow-campaign-card border-b-5 border-black h-full '
        'flex flex-col justify-between"><div class="border-b border-gray-700 pb-2 font-medium mb-3">'
        f'{fecha}</div><a class="leading-6 font-bold" href="/institucion/senamhi/informes-publicaciones/{ficha}">'
        f'{titulo}</a>ENFEN mantiene el estado de «Alerta de El Niño Costero». En la región Niño 1+2, se '
        'mantiene una alta probabilidad de ...<div class="mt-3 leading-5 text-sm">Disponible en formato PDF'
        '</div></div></div>'
    )


GOBPE_COLECCION_HTML = (
    '<div class="w-full js-official-documents-search-results"><div class="row">'
    # desordenadas a propósito: manda la fecha de publicación, no la posición
    + _tarjeta("28 de agosto de 2026", "8535460-comunicado-oficial-enfen-n-15-2026", "Comunicado Oficial ENFEN N°15 -2026")
    + _tarjeta("14 de setiembre de 2026", "8596065-comunicado-oficial-enfen-n-16-2026", "Comunicado Oficial ENFEN N°16 - 2026")
    + _tarjeta("27 de febrero de 2025", "6523595-comunicado-extraordinario-enfen-n-01-2025",
               "Comunicado Extraordinario ENFEN N°01 - 2025")
    + _tarjeta("16 de diciembre de 2021", "2555715-comunicado_of_enfen-n-12-2021", "Comunicado_Of_ENFEN N° 12-2021")
    + '<a href="/institucion/senamhi/informes-publicaciones/698037-politica-de-privacidad-de-gob-pe">Política</a>'
    + "</div></div>"
)

GOBPE_FICHA_16_HTML = (
    '<p>Esta publicación pertenece al compendio <a href="/institucion/senamhi/colecciones/1308-comunicados-enfen">'
    ' Comunicados ENFEN</a></p><div class="institution-document__files"><a class="track-ga-click" '
    'data-download-track-id-value="10621138" '
    'href="https://cdn.www.gob.pe/uploads/document/file/10621138/8596065-comunicado_of_enfen-n-16-2026.pdf?v=1789430560" '
    'target="_blank"><div class="border-3 border-blue-200 max-w-6 min-h-8.5"><img alt="Vista preliminar de documento '
    'Comunicado_Of_ENFEN N° 16-2026" src="https://cdn.www.gob.pe/uploads/document/file/10621138/'
    'preview_8596065-comunicado_of_enfen-n-16-2026.jpg?v=1789430560" /></div></a></div>'
)
URL_FICHA_16 = ("https://www.gob.pe/institucion/senamhi/informes-publicaciones/"
                "8596065-comunicado-oficial-enfen-n-16-2026")

SENAMHI_NINO_HTML = (
    '<a href="../../load/file/02204SENA-222.pdf" target="_blank" title="ENFEN - Comunicado Oficial" '
    'alt="ENFEN - Comunicado Oficial"><img src="public/images/portada.jpg"></a>'
    '<h4>ENFEN - Comunicado Oficial</h4><ul>'
    '<li><a href="../../load/file/02204SENA-221.pdf" title="ENFEN - Comunicado Oficial" alt="28 Agosto    - 2026" '
    'target="_blank">28 Agosto    - 2026</a></li>'
    '<li><a href="../../load/file/02204SENA-222.pdf" title="ENFEN - Comunicado Oficial" alt="14 Septiembre- 2026" '
    'target="_blank" onclick="ga(\'send\', \'event\', \'Boletines\', \'descarga\', \'ENFEN - Comunicado Oficial\', 0);">'
    '14 Septiembre- 2026</a></li>'
    '<li><a href="https://evil.example/x.pdf" title="ENFEN - Comunicado Oficial">30 Septiembre- 2026</a></li>'
    '<li><a href="http://www.senamhi.gob.pe/load/file/02204SENA-999.pdf" title="ENFEN - Comunicado Oficial">'
    '29 Septiembre- 2026</a></li>'
    '</ul><h4>Informe Técnico ENFEN</h4><ul><li><a href="../../load/file/02273SENA-55.pdf" '
    'title="Informe Técnico ENFEN">19 Septiembre- 2026</a></li></ul>'
)
URL_SENAMHI_16 = "https://www.senamhi.gob.pe/load/file/02204SENA-222.pdf"

ENFEN_COMUNICADOS_HTML = (
    '<a href="https://enfen.imarpe.gob.pe/download/comunicado-oficial-enfen-n-15-2026/?wpdmdl=2145&amp;'
    'refresh=6ab2954161f511790088513">Ver</a>'
    '<i class="fa fa-exclamation-circle"></i> Comunicado Oficial Enfen N° 16-2026<br><i>14 Septiembre, 2026</i><br>'
    '<a href="https://enfen.imarpe.gob.pe/download/comunicado-oficial-enfen-n-16-2026/?wpdmdl=2158&amp;'
    'refresh=6ab2a3df2922d1790092255" style="color:#DE3131 !important">Ver Comunicado </a>'
    '<a href="https://enfen.imarpe.gob.pe/2026/07/17/comunicado-oficial-enfen-n-13-2026-estado-de-sistema/">nota</a>'
)
URL_ENFEN_16 = "https://enfen.imarpe.gob.pe/download/comunicado-oficial-enfen-n-16-2026/?wpdmdl=2158"


def _no_encontrado(url):
    e = urllib.error.HTTPError(url, 404, "Not Found", None, io.BytesIO(b""))
    e.close()   # el cuerpo no se usa: cerrado no deja ResourceWarning
    return e


class _Red:
    """Simula _http.get y _http.get_bytes con respuestas por URL y anota lo pedido."""

    def __init__(self, paginas, pdfs):
        self.paginas, self.pdfs, self.pedidas = paginas, pdfs, []

    def get(self, url, params=None):
        self.pedidas.append(url)
        r = self.paginas.get(url)
        if r is None:
            raise _no_encontrado(url)
        return r

    def get_bytes(self, url, max_bytes=None):
        self.pedidas.append(url)
        if url not in self.pdfs:
            raise _no_encontrado(url)
        if isinstance(self.pdfs[url], Exception):   # p. ej. el ValueError del tope de _http
            raise self.pdfs[url]
        return self.pdfs[url]

    def parches(self):
        # _texto_pdf simulado: el "PDF" es b"%PDF-" + el texto del comunicado.
        return (mock.patch.object(_http, "get", self.get),
                mock.patch.object(_http, "get_bytes", self.get_bytes),
                mock.patch.object(enfen, "_importar_pypdf", lambda: None),
                mock.patch.object(enfen, "_texto_pdf", lambda datos: datos[5:].decode("utf-8")))


def _pdf(texto):
    return b"%PDF-" + texto.encode("utf-8")


class _PdfReadError(Exception):
    """Como pypdf.errors.PdfReadError: hereda de PyPdfError, no de ValueError."""


def _pypdf_falso(pagina_rota=None):
    """
    pypdf simulado: el "PDF" es b"%PDF-" + el texto de las páginas separadas por \\f. Uno
    que empieza con b"%PDF-ROTO" no abre, y la página `pagina_rota` (1..n) falla al
    extraer el texto, como hace pypdf con un PDF dañado.
    """
    class Pagina:
        def __init__(self, texto, rota):
            self.texto, self.rota = texto, rota

        def extract_text(self):
            if self.rota:
                raise KeyError("/Font")
            return self.texto

    class PdfReader:
        def __init__(self, stream):
            datos = stream.read()
            if datos.startswith(b"%PDF-ROTO"):
                raise _PdfReadError("EOF marker not found")
            self.pages = [Pagina(t, n == pagina_rota)
                          for n, t in enumerate(datos[5:].decode("utf-8").split("\f"), 1)]

    return types.SimpleNamespace(PdfReader=PdfReader)


class TestPypdf(unittest.TestCase):
    """Los errores de pypdf son 'PDF ilegible' (ValueError), no fallas de red."""

    def test_no_abre(self):
        with mock.patch.object(enfen, "_importar_pypdf", _pypdf_falso):
            with self.assertRaisesRegex(ValueError, "PDF ilegible: _PdfReadError: EOF marker"):
                enfen._texto_pdf(b"%PDF-ROTO")
            with self.assertRaisesRegex(ValueError, "PDF ilegible"):
                list(enfen._paginas_pdf(b"%PDF-ROTO"))

    def test_pagina_que_no_se_puede_extraer(self):
        with mock.patch.object(enfen, "_importar_pypdf", lambda: _pypdf_falso(pagina_rota=2)):
            with self.assertRaisesRegex(ValueError, r"PDF ilegible \(página 2\): KeyError"):
                enfen._texto_pdf(b"%PDF-uno\fdos")
            paginas = enfen._paginas_pdf(b"%PDF-uno\fdos\ftres")
            self.assertEqual(next(paginas), "uno")   # perezoso: la 1 sale antes del error
            with self.assertRaisesRegex(ValueError, r"página 2"):
                next(paginas)

    def test_texto_de_las_primeras_paginas(self):
        paginas = "\f".join(str(n) for n in range(1, enfen.MAX_PAGINAS + 5))
        with mock.patch.object(enfen, "_importar_pypdf", _pypdf_falso):
            texto = enfen._texto_pdf(b"%PDF-" + paginas.encode())
        self.assertEqual(texto.split("\n"), [str(n) for n in range(1, enfen.MAX_PAGINAS + 1)])


class TestDescubrimiento(unittest.TestCase):
    def test_gobpe_elige_la_ultima_publicacion_y_su_pdf(self):
        red = _Red({enfen.GOBPE_COLECCION: GOBPE_COLECCION_HTML, URL_FICHA_16: GOBPE_FICHA_16_HTML}, {})
        with mock.patch.object(_http, "get", red.get):
            self.assertEqual(enfen._pdf_gobpe(), URL)   # sin ?v= ni la vista previa .jpg
        self.assertEqual(red.pedidas, [enfen.GOBPE_COLECCION, URL_FICHA_16])

    def test_gobpe_titulos_antiguos_y_extraordinarios(self):
        tarjetas = enfen._tarjetas_gobpe(GOBPE_COLECCION_HTML)
        self.assertEqual([(t.anio, t.numero, t.publicado) for t in tarjetas], [
            (2026, 15, date(2026, 8, 28)),
            (2026, 16, date(2026, 9, 14)),
            (2025, 1, date(2025, 2, 27)),
            (2021, 12, date(2021, 12, 16)),
        ])

    def test_gobpe_ficha_sin_pdf(self):
        red = _Red({enfen.GOBPE_COLECCION: GOBPE_COLECCION_HTML, URL_FICHA_16: "<p>sin archivos</p>"}, {})
        with mock.patch.object(_http, "get", red.get):
            with self.assertRaisesRegex(ValueError, "no enlaza el PDF"):
                enfen._pdf_gobpe()

    def test_gobpe_sin_comunicados(self):
        with mock.patch.object(_http, "get", lambda url, params=None: "<html>mantenimiento</html>"):
            with self.assertRaises(ValueError):
                enfen._pdf_gobpe()

    def test_senamhi_elige_la_fecha_mas_reciente_solo_https_propio(self):
        with mock.patch.object(_http, "get", lambda url, params=None: SENAMHI_NINO_HTML):
            self.assertEqual(enfen._pdf_senamhi(), URL_SENAMHI_16)

    def test_enfen_elige_el_mayor_numero_sin_refresh(self):
        with mock.patch.object(_http, "get", lambda url, params=None: ENFEN_COMUNICADOS_HTML):
            self.assertEqual(enfen._pdf_enfen(), URL_ENFEN_16)

    def test_leer_pdf_rechaza_hosts_ajenos_y_no_pdf(self):
        with self.assertRaisesRegex(ValueError, "no permitida"):
            enfen.leer_pdf("http://cdn.www.gob.pe/x.pdf")
        red = _Red({}, {URL: b"<html>error</html>"})
        with mock.patch.object(_http, "get_bytes", red.get_bytes):
            with self.assertRaisesRegex(ValueError, "no es un PDF"):
                enfen.leer_pdf(URL)


class TestUltimoComunicado(unittest.TestCase):
    PAGINAS = {
        enfen.GOBPE_COLECCION: GOBPE_COLECCION_HTML,
        URL_FICHA_16: GOBPE_FICHA_16_HTML,
        enfen.SENAMHI_NINO: SENAMHI_NINO_HTML,
        enfen.ENFEN_COMUNICADOS: ENFEN_COMUNICADOS_HTML,
    }

    def correr(self, red, avisos=True, hoy=date(2026, 9, 22)):
        p = red.parches()
        with p[0], p[1], p[2], p[3], mock.patch.object(enfen, "_hoy", lambda: hoy):
            if not avisos:
                with self.assertNoLogs(enfen.log, "WARNING"):
                    return enfen.ultimo_comunicado()
            with self.assertLogs(enfen.log, "WARNING"):   # cada fuente fallida deja un aviso
                return enfen.ultimo_comunicado()

    def test_primera_fuente_al_dia(self):
        red = _Red(self.PAGINAS, {URL: _pdf(CO_16_2026)})
        c = self.correr(red, avisos=False)
        self.assertEqual((c.numero, c.anio, c.estado, c.url), (16, 2026, "Alerta de El Niño Costero", URL))
        self.assertNotIn(enfen.SENAMHI_NINO, red.pedidas)   # no hizo falta seguir

    def test_si_gobpe_falla_usa_senamhi(self):
        paginas = dict(self.PAGINAS)
        del paginas[enfen.GOBPE_COLECCION]                    # 404
        red = _Red(paginas, {URL_SENAMHI_16: _pdf(CO_16_2026)})
        c = self.correr(red)
        self.assertEqual((c.numero, c.url), (16, URL_SENAMHI_16))

    def test_pdf_invalido_pasa_a_la_siguiente_fuente(self):
        red = _Red(self.PAGINAS, {URL: b"<html>", URL_SENAMHI_16: _pdf(CO_16_2026)})
        self.assertEqual(self.correr(red).url, URL_SENAMHI_16)

    def test_vencido_busca_uno_mas_nuevo_en_otra_fuente(self):
        # gob.pe todavía muestra el 05-2025 (anunciaba el próximo para el 16-05-2025).
        red = _Red(self.PAGINAS, {URL: _pdf(CO_05_2025), URL_SENAMHI_16: _pdf(CO_16_2026)})
        c = self.correr(red)
        self.assertEqual((c.numero, c.anio, c.url), (16, 2026, URL_SENAMHI_16))
        self.assertNotIn(enfen.ENFEN_COMUNICADOS, red.pedidas)

    def test_vencido_sin_otro_mas_nuevo_devuelve_el_mejor(self):
        # el 13-2025 anunciaba el próximo para el 15-01-2026; el 20-01 todavía se acepta
        red = _Red(self.PAGINAS, {URL: _pdf(CO_05_2025), URL_SENAMHI_16: _pdf(CO_05_2025),
                                  URL_ENFEN_16: _pdf(CO_13_2025)})
        c = self.correr(red, hoy=date(2026, 1, 20))
        self.assertEqual((c.numero, c.anio), (13, 2025))

    def test_demasiado_viejo_es_error_visible(self):
        # p. ej. un listado que cambió de orden: en setiembre de 2026 no se publica uno de 2025
        red = _Red(self.PAGINAS, {URL: _pdf(CO_05_2025), URL_SENAMHI_16: _pdf(CO_05_2025),
                                  URL_ENFEN_16: _pdf(CO_13_2025)})
        with self.assertRaisesRegex(RuntimeError, "atrasado"):
            self.correr(red)

    def test_pdf_ilegible_deja_aviso_aunque_otra_fuente_responda(self):
        # gob.pe trae un comunicado con un formato que no se entiende: se usa el de SENAMHI,
        # pero el problema queda registrado (log de error y avisos del resultado)
        ilegible = CO_16_2026.replace("Alerta de El Niño Costero", "Alerta ante El Niño Costero")
        red = _Red(self.PAGINAS, {URL: _pdf(ilegible), URL_SENAMHI_16: _pdf(CO_16_2026)})
        p = red.parches()
        with p[0], p[1], p[2], p[3], mock.patch.object(enfen, "_hoy", lambda: date(2026, 9, 22)):
            with self.assertLogs(enfen.log, "ERROR"):
                c = enfen.ultimo_comunicado()
        self.assertEqual(c.url, URL_SENAMHI_16)
        self.assertTrue(any("no se pudo leer" in a for a in c.avisos))

    def test_pdf_que_pypdf_no_lee_cuenta_como_ilegible(self):
        # antes salía como falla de red ("no se pudo bajar")
        red = _Red(self.PAGINAS, {URL: b"%PDF-ROTO", URL_SENAMHI_16: _pdf(CO_16_2026)})
        with mock.patch.object(_http, "get", red.get), mock.patch.object(_http, "get_bytes", red.get_bytes), \
             mock.patch.object(enfen, "_importar_pypdf", _pypdf_falso), \
             mock.patch.object(enfen, "_hoy", lambda: date(2026, 9, 22)):
            with self.assertLogs(enfen.log, "ERROR"):
                c = enfen.ultimo_comunicado()
        self.assertEqual(c.url, URL_SENAMHI_16)
        [aviso] = c.avisos
        self.assertIn(f"no se pudo leer {URL}: PDF ilegible: _PdfReadError", aviso)

    def test_todas_fallan(self):
        red = _Red({}, {})
        with self.assertRaises(RuntimeError) as ctx:
            self.correr(red)
        for fuente in ("gob.pe", "SENAMHI", "web ENFEN"):
            self.assertIn(fuente, str(ctx.exception))

    def test_sin_pypdf_error_claro(self):
        with mock.patch.dict(sys.modules, {"pypdf": None}):
            with self.assertRaisesRegex(RuntimeError, "pypdf"):
                enfen.ultimo_comunicado()


# --- Informe Técnico ENFEN: páginas reales (pypdf, IT N° 16-2026 y N° 03-2026) ------------
PORTADA_IT_16 = """

AÑO 12 N° 16
INFORME TÉCNICO ENFEN
11 SEPTIEMBRE DEL 2026


COMISIÓN MULTISECTORIAL ENCARGADA DEL
ESTUDIO NACIONAL DEL FENÓMENO “EL NIÑO”

"""
CREDITOS_IT_16 = """Comisión Multisectorial Encargada del Estudio Nacional del Fenómeno “El Niño” (ENFEN), 2026.
Informe Técnico ENFEN. Año 12, N° 16, 11 de septiembre del 2026, 87 p.
Los Informes Técnicos previos están disponibles en http://enfen.imarpe.gob.pe así como en las páginas web de las instituciones que conforman
 Fecha de Publicación: 15 de septiembre del 2026"""
# Menciona el ICEN pero no es la tabla (pág. 11).
TEXTO_ICEN_IT_16 = """El valor del ICEN de julio y su valor temporal de agosto de 2026 se ubican en las
categorías Cálida Fuerte y Cálida Extraordinaria, respectivamente. Por su parte, el
ONI relativo (RONI) se encuentra en la categoría Cálida Moderada"""
# IT N° 03-2026: el ICENtmp viene rotulado "Dic-25" (errata: la leyenda dice enero de 2026).
PORTADA_IT_03 = "AÑO 12 N° 03 \nINFORME TÉCNICO ENFEN \n12 FEBRERO DE 2026 \n"
TABLA_ICEN_IT_03 = """Tabla 3. Valores del ICEN, ONI y sus categorías desde enero de 2025 hasta diciembre de
2025, así como sus temporales para enero de 2026.
Valores del índice Costero El Niño ONI
Mes ICEN Categoría ONI Categoría
Nov-25 –0.50 Neutra –0.55 Fría Débil
Dic-25 –0.51 Neutra –0.55 Fría Débil
Mes ICENtmp Mes ONItmp Mes
Dic-25 –0.43 Neutra –0.53 Fría Débil
Fuente: IGP
"""
ICEN_IT_16 = [("2025-08", -0.01, "Neutra"), ("2025-09", -0.22, "Neutra"), ("2026-03", 0.96, "Cálida débil"),
              ("2026-04", 1.34, "Cálida moderada"), ("2026-06", 2.66, "Cálida fuerte"),
              ("2026-07", 3.38, "Cálida fuerte")]


class _Paginas:
    """Páginas de un PDF simulado que anota cuántas se pidieron (para ver que se corta a tiempo)."""

    def __init__(self, *paginas):
        self.paginas, self.leidas = paginas, 0

    def __iter__(self):
        for p in self.paginas:
            self.leidas += 1
            yield p


class TestParsearInforme(unittest.TestCase):
    def setUp(self):
        hoy = mock.patch.object(enfen, "_hoy", lambda: date(2026, 9, 22))
        hoy.start()
        self.addCleanup(hoy.stop)

    def leer(self, *paginas):
        return enfen.parsear_informe(_Paginas(*paginas), "u")

    def test_tabla_3_del_it_16(self):
        paginas = _Paginas(PORTADA_IT_16, CREDITOS_IT_16, TEXTO_ICEN_IT_16, "Figura 5", TABLA_ICEN_IT_16,
                           "Tabla 8. Pronóstico del ICEN", "no se lee", "no se lee")
        i = enfen.parsear_informe(paginas, "u")
        self.assertEqual((i.numero, i.fecha, i.url), (16, date(2026, 9, 11), "u"))   # portada, no la publicación
        self.assertEqual(i.icen, ICEN_IT_16)
        self.assertEqual(i.icen_tmp, ("2026-08", 3.73, "Cálida extraordinaria"))
        self.assertEqual(i.avisos, [])
        self.assertEqual(paginas.leidas, 5)   # se detiene en la tabla

    def test_numero_y_fecha_de_los_creditos_si_la_portada_es_imagen(self):
        i = self.leer("", CREDITOS_IT_16, TABLA_ICEN_IT_16)
        self.assertEqual((i.numero, i.fecha), (16, date(2026, 9, 11)))

    def test_sin_portada_se_valida_contra_hoy(self):
        i = self.leer("", "", TABLA_ICEN_IT_16)
        self.assertEqual((i.numero, i.fecha, i.icen[-1][0]), (None, None, "2026-07"))

    def test_tabla_partida_entre_dos_paginas(self):
        tabla, tmp = TABLA_ICEN_IT_16.split("Mes ICENtmp")
        paginas = _Paginas(PORTADA_IT_16, tabla, "Mes ICENtmp" + tmp, "no se lee")
        i = enfen.parsear_informe(paginas, "u")
        self.assertEqual(i.icen[-1], ("2026-07", 3.38, "Cálida fuerte"))
        self.assertEqual(i.icen_tmp, ("2026-08", 3.73, "Cálida extraordinaria"))
        self.assertEqual(paginas.leidas, 3)

    def test_sin_icentmp_mira_una_pagina_mas_y_para(self):
        tabla = TABLA_ICEN_IT_16.split("Mes ICENtmp")[0]
        paginas = _Paginas(PORTADA_IT_16, tabla, "Figura 6", "no se lee")
        i = enfen.parsear_informe(paginas, "u")
        self.assertEqual((i.icen[-1][0], i.icen_tmp), ("2026-07", None))
        self.assertEqual(paginas.leidas, 3)

    def test_icentmp_con_errata_se_descarta_con_aviso(self):
        with self.assertLogs(enfen.log, "WARNING"):
            i = self.leer(PORTADA_IT_03, TABLA_ICEN_IT_03)
        self.assertEqual((i.numero, i.fecha), (3, date(2026, 2, 12)))
        self.assertEqual(i.icen[-1], ("2025-12", -0.51, "Neutra"))   # el ICEN vale igual
        self.assertIsNone(i.icen_tmp)
        self.assertIn("ICENtmp descartado", i.avisos[0])

    def test_sin_tabla(self):
        with self.assertRaisesRegex(ValueError, "tabla del ICEN"):
            self.leer(PORTADA_IT_16, TEXTO_ICEN_IT_16, NOTA_CO_11_2026)

    def test_pdf_sin_texto(self):
        with self.assertRaisesRegex(ValueError, "escaneado"):
            self.leer("", " \n ", "")

    def test_mes_posterior_a_la_fecha_del_informe(self):
        # la portada dice 11-09-2026 pero la tabla trae octubre: se leyó mal algo
        tabla = TABLA_ICEN_IT_16.replace("Jul-26 3.38", "Oct-26 3.38")
        with self.assertRaisesRegex(ValueError, "posterior a su fecha"):
            self.leer(PORTADA_IT_16, tabla)

    def test_icen_de_hace_mas_de_6_meses(self):
        # informe de setiembre con un ICEN que llega solo a febrero: no es la tabla vigente
        tabla = ("Mes ICEN Categoría RONI Categoría ONI Categoría \n"
                 "Feb-26 0.42 Neutra –0.72 Fría Débil –0.16 Neutra \n")
        with self.assertRaisesRegex(ValueError, "más de 6 meses"):
            self.leer(PORTADA_IT_16, tabla)

    def test_fecha_del_informe_futura(self):
        with self.assertRaisesRegex(ValueError, "futura"):
            self.leer(PORTADA_IT_16.replace("2026", "2027"), TABLA_ICEN_IT_16)


# Bloques reales de https://www.senamhi.gob.pe/?p=fenomeno-el-nino (22-09-2026, recortados).
SENAMHI_INFORMES_HTML = (
    '<div class="card-body" style="padding: 0.25rem 1rem;"><h4>ENFEN - Comunicado Oficial</h4><ul>'
    '<li><a href="../../load/file/02204SENA-222.pdf" title="ENFEN - Comunicado Oficial" alt="14 Septiembre- 2026" '
    'target="_blank">14 Septiembre- 2026</a></li></ul></div>'
    '<div class="card-body" style="padding: 0.25rem 1rem;"><h4>Informe Técnico ENFEN</h4><ul>'
    '<li><a href="../../load/file/02273SENA-55.pdf" title="Informe Técnico ENFEN" alt="14 Septiembre- 2026" '
    'target="_blank" onclick="ga(\'send\', \'event\', \'Boletines\', \'descarga\', \'Informe Técnico ENFEN\', 0);">'
    '14 Septiembre- 2026</a></li>'
    '<li><a href="../../load/file/02273SENA-54.pdf" title="Informe Técnico ENFEN" alt="28 Agosto    - 2026" '
    'target="_blank">28 Agosto    - 2026</a></li></ul></div>'
    # otro documento: fecha adelantada a propósito, para ver que no se confunde
    '<div class="card-body" style="padding: 0.25rem 1rem;"><h4>Informe Técnico SENAMHI - ENFEN</h4><ul>'
    '<li><a href="../../load/file/02203SENA-144.pdf" title="Informe Técnico SENAMHI - ENFEN" alt="20 Septiembre- 2026" '
    'target="_blank">20 Septiembre- 2026</a></li></ul></div>'
)
URL_IT_SENAMHI = "https://www.senamhi.gob.pe/load/file/02273SENA-55.pdf"

GOBPE_INFORMES_HTML = (
    '<div class="w-full js-official-documents-search-results"><div class="row">'
    + _tarjeta("28 de agosto de 2026", "8535461-informe-tecnico-del-enfen-n-15-2026", "Informe Técnico del ENFEN N°15-2026")
    + _tarjeta("14 de setiembre de 2026", "8633845-informe-tecnico-del-enfen-n-16-2026",
               "Informe Técnico del ENFEN N°16-2026")
    + _tarjeta("12 de agosto de 2026", "8484924-informe-tecnico-del-enfen-n-14-2026", "Informe Técnico del ENFEN N°14 - 2026")
    # errata real del título (es de 2025): manda la fecha de publicación
    + _tarjeta("16 de julio de 2025", "6965635-informe-tecnico-del-enfen-n-09-2024", "Informe Técnico del ENFEN N°09-2024")
    + "</div></div>"
)
URL_FICHA_IT_16 = ("https://www.gob.pe/institucion/senamhi/informes-publicaciones/"
                   "8633845-informe-tecnico-del-enfen-n-16-2026")
URL_IT_GOBPE = ("https://cdn.www.gob.pe/uploads/document/file/10671694/"
                "8633845-informe-tecnico-del-enfen-n-16-2026.pdf")
GOBPE_FICHA_IT_16_HTML = (
    '<div class="institution-document__files"><a class="track-ga-click" data-download-track-id-value="10671694" '
    f'href="{URL_IT_GOBPE}?v=1790088719" target="_blank"><div class="border-3 border-blue-200 max-w-6 min-h-8.5">'
    '<img alt="Vista preliminar de documento Informe Técnico del ENFEN N°16-2026" '
    'src="https://cdn.www.gob.pe/uploads/document/file/10671694/'
    'preview_8633845-informe-tecnico-del-enfen-n-16-2026.jpg?v=1790088719" /></div></a></div>'
)


def _pdf_paginas(*paginas):
    return b"%PDF-" + "\f".join(paginas).encode("utf-8")


URL_IT_15_SENAMHI = "https://www.senamhi.gob.pe/load/file/02273SENA-54.pdf"
# SENAMHI sigue mostrando el N° 15; gob.pe, el N° 15 (atrasado) o el N° 16 con 2 días de diferencia.
SENAMHI_SOLO_IT_15_HTML = (
    '<h4>Informe Técnico ENFEN</h4><ul><li><a href="../../load/file/02273SENA-54.pdf" '
    'title="Informe Técnico ENFEN" alt="28 Agosto    - 2026" target="_blank">28 Agosto    - 2026</a></li></ul>')
GOBPE_SOLO_IT_15_HTML = _tarjeta("28 de agosto de 2026", "8535461-informe-tecnico-del-enfen-n-15-2026",
                                 "Informe Técnico del ENFEN N°15-2026")
URL_FICHA_IT_15 = ("https://www.gob.pe/institucion/senamhi/informes-publicaciones/"
                   "8535461-informe-tecnico-del-enfen-n-15-2026")
URL_IT_15_GOBPE = "https://cdn.www.gob.pe/uploads/document/file/10500000/8535461-informe-tecnico-del-enfen-n-15-2026.pdf"
GOBPE_FICHA_IT_15_HTML = f'<div class="institution-document__files"><a href="{URL_IT_15_GOBPE}?v=1">PDF</a></div>'

# Lo que el latido guarda del informe leído (ReferenciaInforme)
LEIDO_15 = enfen.ReferenciaInforme(url=URL_IT_15_SENAMHI, publicado=date(2026, 8, 28), numero=15,
                                   fecha=date(2026, 8, 26))
LEIDO_16 = enfen.ReferenciaInforme(url=URL_IT_SENAMHI, publicado=date(2026, 9, 14), numero=16,
                                   fecha=date(2026, 9, 11))
AHORA = datetime(2026, 9, 22, 17, 0, tzinfo=timezone.utc)


class TestInformeTecnico(unittest.TestCase):
    PAGINAS = {
        enfen.SENAMHI_NINO: SENAMHI_INFORMES_HTML,
        enfen.GOBPE_INFORMES: GOBPE_INFORMES_HTML,
        URL_FICHA_IT_16: GOBPE_FICHA_IT_16_HTML,
    }
    IT_16 = _pdf_paginas(PORTADA_IT_16, CREDITOS_IT_16, TABLA_ICEN_IT_16)

    def correr(self, red, leido=None, fallido=None, ahora=AHORA):
        # pypdf simulado (_pypdf_falso): las páginas pasan por el _paginas_pdf de verdad.
        with mock.patch.object(_http, "get", red.get), mock.patch.object(_http, "get_bytes", red.get_bytes), \
             mock.patch.object(enfen, "_importar_pypdf", _pypdf_falso), \
             mock.patch.object(enfen, "_hoy", lambda: date(2026, 9, 22)), \
             mock.patch.object(enfen, "_ahora", lambda: ahora):
            return enfen.informe_tecnico_icen(leido, fallido)

    def pdfs_pedidos(self, red):
        return [u for u in red.pedidas if u.endswith(".pdf")]

    def test_descubre_en_senamhi_solo_el_bloque_del_informe(self):
        with mock.patch.object(_http, "get", lambda url, params=None: SENAMHI_INFORMES_HTML):
            self.assertEqual(enfen._informe_senamhi(), (date(2026, 9, 14), URL_IT_SENAMHI))
            # y el de comunicados sigue eligiendo el comunicado
            self.assertEqual(enfen._pdf_senamhi(), URL_SENAMHI_16)

    def test_descubre_en_gobpe_por_fecha_de_publicacion(self):
        red = _Red(self.PAGINAS, {})
        with mock.patch.object(_http, "get", red.get):
            self.assertEqual(enfen._informe_gobpe(), (date(2026, 9, 14), URL_IT_GOBPE))
        self.assertEqual(red.pedidas, [enfen.GOBPE_INFORMES, URL_FICHA_IT_16])

    def test_informe_nuevo_se_baja_de_senamhi(self):
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: self.IT_16})
        r = self.correr(red, leido=LEIDO_15)
        i = r.informe
        self.assertEqual((i.url, i.numero, i.fecha), (URL_IT_SENAMHI, 16, date(2026, 9, 11)))
        self.assertEqual(i.icen[-1], ("2026-07", 3.38, "Cálida fuerte"))
        self.assertEqual(i.icen_tmp, ("2026-08", 3.73, "Cálida extraordinaria"))
        # lo que se guarda para no volver a bajarlo: URL, publicación (listado) y portada
        self.assertEqual(r.leido, LEIDO_16)
        self.assertEqual((r.en_espera, r.avisos), (False, []))
        self.assertEqual(self.pdfs_pedidos(red), [URL_IT_SENAMHI])

    def test_misma_url_no_se_descarga_y_completa_la_fecha_del_latido_anterior(self):
        # latido del formato anterior: solo la URL
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: self.IT_16})
        r = self.correr(red, leido=enfen.ReferenciaInforme(url=URL_IT_SENAMHI))
        self.assertIsNone(r.informe)
        self.assertEqual(r.leido, enfen.ReferenciaInforme(url=URL_IT_SENAMHI, publicado=date(2026, 9, 14)))
        self.assertEqual(self.pdfs_pedidos(red), [])

    def test_mismo_informe_leido_desde_la_otra_fuente_no_se_descarga(self):
        # la vez anterior SENAMHI estaba caído y se leyó la copia de gob.pe
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: self.IT_16, URL_IT_GOBPE: self.IT_16})
        leido = enfen.ReferenciaInforme(url=URL_IT_GOBPE, publicado=date(2026, 9, 14))
        r = self.correr(red, leido=leido)
        self.assertEqual((r.informe, r.leido), (None, leido))
        self.assertEqual(self.pdfs_pedidos(red), [])

    def test_si_cae_la_fuente_del_leido_no_baja_la_copia_de_la_otra(self):
        # se leyó la copia de SENAMHI; hoy SENAMHI no responde y gob.pe lista el mismo informe
        # 2 días después, con otra URL: por la fecha de publicación es el mismo
        paginas = dict(self.PAGINAS)
        del paginas[enfen.SENAMHI_NINO]
        paginas[enfen.GOBPE_INFORMES] = GOBPE_INFORMES_HTML.replace("14 de setiembre de 2026", "16 de setiembre de 2026")
        red = _Red(paginas, {URL_IT_GOBPE: self.IT_16})
        with self.assertLogs(enfen.log, "WARNING"):
            r = self.correr(red, leido=LEIDO_16)
        self.assertEqual((r.informe, r.leido), (None, LEIDO_16))
        self.assertEqual(self.pdfs_pedidos(red), [])
        # y la falla de SENAMHI llega a los avisos aunque no haya informe nuevo
        [aviso] = r.avisos
        self.assertIn("informe SENAMHI: HTTPError", aviso)

    def test_nunca_baja_uno_mas_viejo_que_el_leido(self):
        # SENAMHI caído y gob.pe atrasado (todavía el N° 15): no se baja ni se retrocede
        paginas = {enfen.GOBPE_INFORMES: GOBPE_SOLO_IT_15_HTML, URL_FICHA_IT_15: GOBPE_FICHA_IT_15_HTML}
        red = _Red(paginas, {URL_IT_15_GOBPE: _pdf_paginas("N° 15")})
        with self.assertLogs(enfen.log, "WARNING"):
            r = self.correr(red, leido=LEIDO_16)
        self.assertEqual((r.informe, r.leido), (None, LEIDO_16))
        self.assertEqual(self.pdfs_pedidos(red), [])

    def test_sin_fecha_de_publicacion_se_compara_la_portada(self):
        # SENAMHI caído y la tarjeta de gob.pe sin fecha: no se puede saber antes de bajarlo;
        # por la portada es el mismo N° 16 ya leído: no se usa, y su URL queda como alias
        paginas = dict(self.PAGINAS)
        del paginas[enfen.SENAMHI_NINO]
        paginas[enfen.GOBPE_INFORMES] = _tarjeta("", "8633845-informe-tecnico-del-enfen-n-16-2026",
                                                 "Informe Técnico del ENFEN N°16-2026")
        red = _Red(paginas, {URL_IT_GOBPE: self.IT_16})
        with self.assertLogs(enfen.log, "WARNING"):
            r = self.correr(red, leido=LEIDO_16)
        self.assertIsNone(r.informe)
        self.assertEqual(r.leido.alias, [URL_IT_GOBPE])
        self.assertTrue(any("SENAMHI" in a for a in r.avisos))
        # la corrida siguiente ya no lo baja
        red2 = _Red(paginas, {URL_IT_GOBPE: self.IT_16})
        with self.assertLogs(enfen.log, "WARNING"):
            r2 = self.correr(red2, leido=r.leido)
        self.assertIsNone(r2.informe)
        self.assertEqual(self.pdfs_pedidos(red2), [])

    def test_informe_viejo_re_publicado_con_fecha_nueva_se_descarta(self):
        # gob.pe vuelve a listar el N° 15 con fecha de hoy: por el listado parece nuevo, pero
        # la portada es anterior a la del ya leído (N° 16): se descarta y no se usa
        paginas = dict(self.PAGINAS)
        del paginas[enfen.SENAMHI_NINO]
        paginas[enfen.GOBPE_INFORMES] = _tarjeta("20 de setiembre de 2026", "8633845-informe-tecnico-del-enfen-n-16-2026",
                                                 "Informe Técnico del ENFEN N°16-2026")
        viejo = _pdf_paginas(PORTADA_IT_16.replace("11 SEPTIEMBRE", "26 AGOSTO").replace("N° 16", "N° 15"),
                             CREDITOS_IT_16.replace("N° 16, 11 de septiembre", "N° 15, 26 de agosto"),
                             TABLA_ICEN_IT_16)
        red = _Red(paginas, {URL_IT_GOBPE: viejo})
        with self.assertLogs(enfen.log, "WARNING"):
            with self.assertRaisesRegex(enfen.InformeDescartado, "anterior"):
                self.correr(red, leido=LEIDO_16)

    def test_senamhi_atrasado_usa_gobpe(self):
        # SENAMHI sigue mostrando el N° 15 (ya leído); gob.pe ya publicó el N° 16
        paginas = dict(self.PAGINAS)
        paginas[enfen.SENAMHI_NINO] = SENAMHI_SOLO_IT_15_HTML
        red = _Red(paginas, {URL_IT_GOBPE: self.IT_16})
        r = self.correr(red, leido=LEIDO_15)
        self.assertEqual((r.informe.url, r.informe.numero), (URL_IT_GOBPE, 16))
        self.assertEqual((r.leido.url, r.leido.publicado), (URL_IT_GOBPE, date(2026, 9, 14)))
        self.assertEqual(self.pdfs_pedidos(red), [URL_IT_GOBPE])

    def test_si_senamhi_falla_usa_gobpe_con_aviso(self):
        paginas = dict(self.PAGINAS)
        del paginas[enfen.SENAMHI_NINO]
        red = _Red(paginas, {URL_IT_GOBPE: self.IT_16})
        with self.assertLogs(enfen.log, "WARNING"):
            r = self.correr(red)
        self.assertEqual(r.informe.url, URL_IT_GOBPE)
        self.assertTrue(any("SENAMHI" in a for a in r.avisos))

    def test_si_falla_la_descarga_prueba_la_copia_de_la_otra_fuente(self):
        red = _Red(self.PAGINAS, {URL_IT_GOBPE: self.IT_16})   # el PDF de SENAMHI da 404
        with self.assertLogs(enfen.log, "WARNING"):
            r = self.correr(red)
        self.assertEqual(r.informe.url, URL_IT_GOBPE)
        self.assertEqual(self.pdfs_pedidos(red), [URL_IT_SENAMHI, URL_IT_GOBPE])
        self.assertTrue(any("informe SENAMHI: HTTPError" in a for a in r.avisos))

    def test_falla_de_red_en_las_dos_copias_no_se_descarta(self):
        # red: RuntimeError (se reintenta en la próxima corrida), no InformeDescartado
        with self.assertLogs(enfen.log, "WARNING"):
            with self.assertRaises(RuntimeError) as ctx:
                self.correr(_Red(self.PAGINAS, {}))
        self.assertNotIsInstance(ctx.exception, ValueError)
        self.assertEqual(ctx.exception.args[0].count("HTTPError"), 2)

    def test_sin_tabla_se_descarta_y_no_baja_la_otra_copia(self):
        sin_tabla = _pdf_paginas(PORTADA_IT_16, TEXTO_ICEN_IT_16)
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: sin_tabla, URL_IT_GOBPE: sin_tabla})
        with self.assertLogs(enfen.log, "ERROR"):
            with self.assertRaisesRegex(enfen.InformeDescartado, "tabla del ICEN") as ctx:
                self.correr(red)
        self.assertEqual(self.pdfs_pedidos(red), [URL_IT_SENAMHI])
        ref = ctx.exception.referencia
        self.assertEqual((ref.url, ref.publicado, ref.ts), (URL_IT_SENAMHI, date(2026, 9, 14), AHORA))
        self.assertIn("tabla del ICEN", ref.error)

    def test_pdf_que_pypdf_no_lee_se_descarta_sin_bajar_la_otra_copia(self):
        # antes se trataba como falla de red: bajaba la otra copia del mismo archivo
        for pdf in (b"%PDF-ROTO", self.IT_16):
            pypdf = (lambda: _pypdf_falso(pagina_rota=2)) if pdf == self.IT_16 else _pypdf_falso
            red = _Red(self.PAGINAS, {URL_IT_SENAMHI: pdf, URL_IT_GOBPE: self.IT_16})
            with self.subTest(pdf=pdf[:9]), mock.patch.object(enfen, "_importar_pypdf", pypdf), \
                 mock.patch.object(_http, "get", red.get), mock.patch.object(_http, "get_bytes", red.get_bytes), \
                 mock.patch.object(enfen, "_hoy", lambda: date(2026, 9, 22)):
                with self.assertLogs(enfen.log, "ERROR"):
                    with self.assertRaisesRegex(enfen.InformeDescartado, "PDF ilegible"):
                        enfen.informe_tecnico_icen()
                self.assertEqual(self.pdfs_pedidos(red), [URL_IT_SENAMHI])

    def test_excede_el_tope_se_descarta(self):
        tope = ValueError(f"La descarga supera el limite de {enfen.MAX_INFORME_BYTES} bytes")
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: tope, URL_IT_GOBPE: self.IT_16})
        with self.assertLogs(enfen.log, "ERROR"):
            with self.assertRaisesRegex(enfen.InformeDescartado, f"limite.*{URL_IT_SENAMHI}"):
                self.correr(red)
        self.assertEqual(self.pdfs_pedidos(red), [URL_IT_SENAMHI])

    def test_copia_que_no_es_pdf_prueba_la_otra(self):
        # SENAMHI responde 200 con una página de mantenimiento
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: b"<html>mantenimiento</html>", URL_IT_GOBPE: self.IT_16})
        with self.assertLogs(enfen.log, "WARNING"):
            r = self.correr(red)
        self.assertEqual(r.informe.url, URL_IT_GOBPE)
        self.assertEqual(self.pdfs_pedidos(red), [URL_IT_SENAMHI, URL_IT_GOBPE])
        self.assertTrue(any("no es un PDF" in a for a in r.avisos))

    def test_ninguna_copia_es_pdf_se_descarta(self):
        html = b"<html>mantenimiento</html>"
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: html, URL_IT_GOBPE: html})
        with self.assertLogs(enfen.log, "WARNING"):
            with self.assertRaisesRegex(enfen.InformeDescartado, "Ninguna copia.*es un PDF") as ctx:
                self.correr(red)
        self.assertEqual(self.pdfs_pedidos(red), [URL_IT_SENAMHI, URL_IT_GOBPE])
        self.assertEqual(ctx.exception.referencia.publicado, date(2026, 9, 14))

    def test_una_copia_no_es_pdf_y_la_otra_falla_por_red(self):
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: b"<html>mantenimiento</html>"})   # gob.pe: 404
        with self.assertLogs(enfen.log, "WARNING"):
            with self.assertRaisesRegex(RuntimeError, "HTTPError.*no es un PDF"):
                self.correr(red)

    def fallido(self, hace, url=URL_IT_SENAMHI, publicado=date(2026, 9, 14)):
        return enfen.ReferenciaInforme(url=url, publicado=publicado, ts=AHORA - hace,
                                       error="No se encontró la tabla del ICEN")

    def test_descartado_hace_menos_de_24_h_no_se_baja_de_ninguna_fuente(self):
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: self.IT_16, URL_IT_GOBPE: self.IT_16})
        with self.assertLogs(enfen.log, "WARNING"):
            r = self.correr(red, leido=LEIDO_15, fallido=self.fallido(timedelta(hours=6)))
        self.assertEqual((r.informe, r.en_espera, r.leido), (None, True, LEIDO_15))
        self.assertEqual(self.pdfs_pedidos(red), [])   # ni la copia de gob.pe (otra URL, misma fecha)
        [aviso] = r.avisos
        self.assertIn("en espera hasta 2026-09-23 11:00 UTC", aviso)
        self.assertIn("tabla del ICEN", aviso)

    def test_descartado_hace_24_h_se_vuelve_a_intentar(self):
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: self.IT_16})
        r = self.correr(red, leido=LEIDO_15, fallido=self.fallido(timedelta(hours=24)))
        self.assertEqual((r.informe.url, r.en_espera), (URL_IT_SENAMHI, False))

    def test_un_descartado_viejo_no_frena_al_informe_nuevo(self):
        fallido = self.fallido(timedelta(hours=1), url=URL_IT_15_SENAMHI, publicado=date(2026, 8, 28))
        red = _Red(self.PAGINAS, {URL_IT_SENAMHI: self.IT_16})
        r = self.correr(red, leido=None, fallido=fallido)
        self.assertEqual(r.informe.url, URL_IT_SENAMHI)

    def test_todas_las_fuentes_fallan(self):
        with self.assertLogs(enfen.log, "WARNING"):
            with self.assertRaisesRegex(RuntimeError, "SENAMHI.*gob.pe"):
                self.correr(_Red({}, {}))

    def test_tope_de_descarga_y_host_propio(self):
        self.assertGreaterEqual(enfen.MAX_INFORME_BYTES, 2 * 17_186_810)   # el IT 16-2026 pesa 17.2 MB
        with self.assertRaisesRegex(ValueError, "no permitida"):
            enfen.leer_informe("https://evil.example/informe.pdf")


class TestReferenciaInforme(unittest.TestCase):
    def test_ida_y_vuelta_por_el_latido(self):
        for ref in (LEIDO_16, enfen.ReferenciaInforme(url="u", publicado=date(2026, 9, 14), ts=AHORA, error="x")):
            datos = ref.a_json()
            self.assertEqual(enfen.ReferenciaInforme.de_json(datos), ref)
        self.assertEqual(LEIDO_16.a_json(), {"url": URL_IT_SENAMHI, "publicado": "2026-09-14", "numero": 16,
                                             "fecha": "2026-09-11"})   # sin claves vacías

    def test_latido_anterior_y_datos_danados(self):
        self.assertEqual(enfen.ReferenciaInforme.de_json(URL_IT_SENAMHI), enfen.ReferenciaInforme(url=URL_IT_SENAMHI))
        for malo in (None, "", {}, {"url": 5}, [URL_IT_SENAMHI]):
            self.assertIsNone(enfen.ReferenciaInforme.de_json(malo))
        ref = enfen.ReferenciaInforme.de_json({"url": "u", "publicado": "14/09/2026", "numero": "16",
                                               "ts": "2026-09-22T17:00:00", "error": 3})
        self.assertEqual(ref, enfen.ReferenciaInforme(url="u", ts=AHORA))   # hora sin zona: UTC


if __name__ == "__main__":
    unittest.main()
