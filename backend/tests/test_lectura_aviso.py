"""
Lectura del texto oficial de los avisos de SENAMHI (backend/ingesta/lectura_aviso.py): ícono,
descargas, granizo, ráfagas y mm/día por subregión. Sin red: los párrafos son reales.
  - muestras/aviso_vigente_20260922.html: recorte de la página de avisos vigentes del
    22-09-2026 (avisos 375 y 376, con el 376 repetido como en la página).
  - muestras/avisos_parrafos.jsonl.gz: los 439 avisos de lluvia, llovizna y nevada de 2024 a
    2026 (nro, emision, inicio, titulo, general, dias), bajados de sus páginas de detalle el
    22-09-2026.
"""
import gzip
import json
import re
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from backend.connectors import senamhi_avisos as fuente
from backend.ingesta import lectura_aviso as L

MUESTRAS = Path(__file__).parent / "muestras"
TITULO_376 = "PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE"


def _corpus() -> list[dict]:
    with gzip.open(MUESTRAS / "avisos_parrafos.jsonl.gz", "rt", encoding="utf-8") as f:
        return [json.loads(linea) for linea in f]


CORPUS = _corpus()
TEXTOS = fuente.parse_textos((MUESTRAS / "aviso_vigente_20260922.html").read_text(encoding="utf-8"))


def _aviso(numero: int, anio: int) -> dict:
    [r] = [r for r in CORPUS if int(re.match(r"0*(\d+)", r["nro"]).group(1)) == numero
           and r["emision"].startswith(str(anio))]
    return r


class TestIcono(unittest.TestCase):
    def test_376_de_hoy(self):
        # "sierra norte y costa norte": las descargas se dicen solo para la sierra, así que va gota
        general = TEXTOS[(2026, 376)].general
        leido = L.leer_general(TITULO_376, general)
        self.assertEqual((leido["regiones_titulo"], leido["regiones_parrafo"]), (["costa", "sierra"], ["costa", "sierra"]))
        self.assertFalse(leido["una_region"])
        self.assertEqual(leido["descargas"], "si")
        self.assertEqual(L.icono_aviso("meteorologico", TITULO_376, leido), "gota")
        self.assertTrue(leido["frase_descargas"].startswith("El SENAMHI informa que"))
        self.assertIn("descargas eléctricas", leido["frase_descargas"])
        self.assertEqual(leido["rafagas"], {"forma": "cercanas a", "kmh": 40})
        self.assertEqual(leido["intensidad"], "de ligera a moderada intensidad")
        self.assertEqual(L.donde(TITULO_376), "la sierra norte y costa norte")

    def test_una_sola_region_con_descargas_lleva_rayo(self):
        r = _aviso(365, 2026)
        self.assertEqual(r["titulo"], "PRECIPITACIONES EN LA SIERRA")
        leido = L.leer_general(r["titulo"], r["general"])
        self.assertEqual(L.icono_aviso("meteorologico", r["titulo"], leido), "gota_rayo")

    def test_otra_region_en_el_parrafo_no_lleva_rayo(self):
        # el 353 es "en la sierra", pero el párrafo agrega "lluvia dispersa en la costa norte"
        r = _aviso(353, 2026)
        leido = L.leer_general(r["titulo"], r["general"])
        self.assertEqual((leido["regiones_titulo"], leido["regiones_parrafo"]), (["sierra"], ["costa", "sierra"]))
        self.assertEqual(L.icono_aviso("meteorologico", r["titulo"], leido), "gota")

    def test_descargas_condicionales(self):
        r = _aviso(141, 2026)   # "no se descarta la ocurrencia de descargas eléctricas"
        leido = L.leer_general(r["titulo"], r["general"])
        self.assertEqual(leido["descargas"], "condicional")
        self.assertIn("no se descarta la ocurrencia de descargas eléctricas", leido["frase_descargas"])
        self.assertEqual(L.icono_aviso("meteorologico", r["titulo"], leido), "gota")

    def test_podrian_de_las_rafagas_no_vuelve_condicionales_las_descargas(self):
        # 024 de 2025 y 398 de 2024: "Estas precipitaciones estarán acompañadas de descargas eléctricas
        # y ráfagas de viento, con velocidades que podrían alcanzar hasta los 50 km/h."
        for numero, anio in ((24, 2025), (398, 2024)):
            r = _aviso(numero, anio)
            leido = L.leer_general(r["titulo"], r["general"])
            self.assertIn("podrían alcanzar", leido["frase_descargas"])
            self.assertEqual((leido["descargas"], leido["una_region"]), ("si", True), numero)
            self.assertEqual(L.icono_aviso("meteorologico", r["titulo"], leido), "gota_rayo", numero)
        self.assertTrue(L.condicional("Asimismo, se prevé nubosidad; no se descarta la ocurrencia de descargas "
                                      "eléctricas en los distritos más alejados del litoral."))
        self.assertTrue(L.condicional("Las lluvias podrían estar acompañadas de descargas eléctricas, con ráfagas."))
        self.assertFalse(L.condicional("Estarán acompañadas de descargas eléctricas, con ráfagas que podrían llegar a 40 km/h."))

    def test_una_oracion_firme_basta(self):
        # 'condicional' solo si TODAS las oraciones que nombran las descargas lo son
        firme = "Estas lluvias estarán acompañadas de descargas eléctricas."
        dudosa = "No se descarta la ocurrencia de descargas eléctricas en la selva alta."
        base = "El SENAMHI informa que se presentarán lluvias en la selva."
        self.assertEqual(L.leer_general("LLUVIA EN LA SELVA", f"{base} {dudosa} {firme}")["descargas"], "si")
        self.assertEqual(L.leer_general("LLUVIA EN LA SELVA", f"{base} {dudosa}")["descargas"], "condicional")
        self.assertEqual(L.leer_general("LLUVIA EN LA SELVA", base)["descargas"], "no")

    def test_regiones_del_titulo_solo_despues_de_en(self):
        general = "El SENAMHI informa que se presentarán lluvias en la sierra, con descargas eléctricas."
        leido = L.leer_general("LLUVIA DE ORIGEN AMAZÓNICO EN LA SIERRA NORTE", general)
        self.assertEqual((leido["regiones_titulo"], leido["una_region"]), (["sierra"], True))

    def test_llovizna_y_nevada(self):
        r = _aviso(374, 2026)
        leido = L.leer_general(r["titulo"], r["general"])
        self.assertEqual((L.fenomeno(r["titulo"]), leido["descargas"]), ("llovizna", "no"))
        self.assertEqual(L.icono_aviso("meteorologico", r["titulo"], leido), "gota")
        r = _aviso(371, 2026)
        leido = L.leer_general(r["titulo"], r["general"])
        self.assertEqual(L.fenomeno(r["titulo"]), "nevada")
        self.assertEqual(L.icono_aviso("meteorologico", r["titulo"], leido), "copo")
        self.assertEqual(leido["nieve"], {"menciona": True, "sobre_m": 4000})

    def test_sin_parrafo_general_no_se_inventa_el_rayo(self):
        self.assertEqual(L.icono_aviso("meteorologico", "PRECIPITACIONES EN LA SIERRA", None), "gota")
        self.assertIsNone(L.lectura("meteorologico", "PRECIPITACIONES EN LA SIERRA", None, "El lunes 14..."))
        self.assertIsNone(L.lectura("meteorologico", "PRECIPITACIONES EN LA SIERRA", "", None))

    def test_24h_y_avisos_que_no_son_de_lluvia(self):
        self.assertEqual(L.icono_aviso("lluvia24h", "AVISO DE CORTO PLAZO ANTE LLUVIAS INTENSAS", None), "gota")
        self.assertEqual(L.lectura("lluvia24h", "AVISO DE CORTO PLAZO ANTE LLUVIAS INTENSAS", None, None),
                         {"v": 1, "fenomeno": "lluvia"})
        for titulo in ("INCREMENTO DE TEMPERATURA DIURNA EN LA SELVA", "INCREMENTO DE VIENTO EN LA COSTA"):
            self.assertIsNone(L.icono_aviso("meteorologico", titulo, None))
            self.assertIsNone(L.lectura("meteorologico", titulo, "El SENAMHI informa que...", None))

    def test_fenomeno_del_titulo(self):
        casos = {
            "NEVADA EN LA SIERRA SUR": "nevada",
            "NEVADAS Y LLUVIA EN LA SIERRA SUR": "lluvia",
            "LLOVIZNA EN LA COSTA CENTRO Y SUR": "llovizna",
            "LLOVIZNA Y LLUVIA EN LA COSTA NORTE": "lluvia",
            "LLUVIA EN LA SELVA - VIGÉSIMO CUARTO FRIAJE": "lluvia",
            "GRANIZADA EN LA SIERRA": "lluvia",
            "DÉCIMO FRIAJE EN LA SELVA": None,
        }
        for titulo, esperado in casos.items():
            self.assertEqual(L.fenomeno(titulo), esperado, titulo)

    def test_granizo_y_nieve_con_su_altura(self):
        r = _aviso(365, 2026)
        leido = L.leer_general(r["titulo"], r["general"])
        self.assertEqual(leido["granizo"], {"menciona": True, "sobre_m": 2800})
        self.assertEqual(leido["nieve"], {"menciona": True, "sobre_m": 3800})
        # "4 000" (con espacio) es 4000; "m s. n. m." no parte la oración
        leido = L.leer_general("NEVADA EN LA SIERRA SUR", "El SENAMHI informa que se presentarán nevadas en zonas "
                               "por encima de los 4 000 m s. n. m. de la sierra sur. Además, granizo en localidades "
                               "sobre los 3.500 m.")
        self.assertEqual(leido["nieve"]["sobre_m"], 4000)
        self.assertEqual(leido["granizo"]["sobre_m"], 3500)

    def test_frase_de_descargas_con_la_oracion_anterior_y_recortada(self):
        general = ("El SENAMHI informa que se presentarán lluvias en la selva. Estas lluvias estarán acompañadas de "
                   "descargas eléctricas.")
        leido = L.leer_general("LLUVIA EN LA SELVA", general)
        self.assertEqual(leido["frase_descargas"], general)
        largo = "El SENAMHI informa que habrá descargas eléctricas " + "en la selva norte " * 40 + "."
        frase = L.leer_general("LLUVIA EN LA SELVA", largo)["frase_descargas"]
        self.assertLessEqual(len(frase), L.MAX_FRASE + 1)
        self.assertTrue(frase.endswith("…"))
        self.assertTrue(largo.startswith(frase[:-1] + " "))   # cortada en una palabra

    def test_rafagas_en_sus_formas(self):
        casos = {
            "ráfagas de viento con velocidades superiores a los 50 km/h": ("de más de", 50),
            "ráfagas de viento con velocidades próximas a 45 km/h": ("cercanas a", 45),
            "ráfagas de viento que podrían alcanzar hasta 60 km/h": ("de hasta", 60),
            "ráfagas de viento de alrededor de 35 km/h": ("de alrededor de", 35),
        }
        for frase, (forma, kmh) in casos.items():
            leido = L.leer_general("LLUVIA EN LA SELVA", f"El SENAMHI informa que habrá {frase}.")
            self.assertEqual(leido["rafagas"], {"forma": forma, "kmh": kmh}, frase)

    def test_corpus(self):
        # 439 avisos de 2024 a 2026: la regla da 245 gota con rayo, 182 gota y 12 copos
        iconos = Counter()
        for r in CORPUS:
            leido = L.leer_general(r["titulo"], r["general"]) if r["general"] else None
            iconos[L.icono_aviso("meteorologico", r["titulo"], leido)] += 1
        self.assertEqual(len(CORPUS), 439)
        self.assertEqual(iconos, {"gota_rayo": 245, "gota": 182, "copo": 12})

    def test_el_senamhi_en_minusculas(self):
        # el 180 de 2026 dice "El Senamhi informa": su párrafo se lee igual
        r = _aviso(180, 2026)
        self.assertTrue(r["general"].startswith("El Senamhi informa"))
        pagina = f'<div class="tab-pane" id="tabs-1802026"><div>{r["general"]}</div></div>'
        self.assertEqual(fuente.parse_descripciones(pagina), {(2026, 180): r["general"]})


class TestIntensidad(unittest.TestCase):
    def test_primera_oracion_y_erratas(self):
        self.assertEqual(L.intensidad("se presentará lluvia de moderad a fuerte intensidad en la sierra."),
                         "de moderada a fuerte intensidad")
        self.assertEqual(L.intensidad("Lluvia de ligero a moderado intensidad en la costa."),
                         "de ligera a moderada intensidad")
        self.assertEqual(L.intensidad("Nevadas de muy fuerte   intensidad."), "de muy fuerte intensidad")
        self.assertIsNone(L.intensidad("Se prevé lluvia en la sierra. Vientos de fuerte intensidad."))
        self.assertIsNone(L.intensidad(None))


class TestFechaDelDia(unittest.TestCase):
    def test_fechas(self):
        casos = {
            "El martes 22 de setiembre, se prevén temperaturas máximas...": date(2026, 9, 22),
            "El miércoles 23 de septiembre se esperan acumulados...": date(2026, 9, 23),
            "Para el viernes 10 de julio, se estiman acumulados de lluvia...": date(2026, 7, 10),
            "El sábado 28de febrero se prevén acumulados...": date(2026, 2, 28),
            "El jueves, 1 de enero se esperan...": date(2026, 1, 1),
        }
        for texto, esperado in casos.items():
            self.assertEqual(L.fecha_texto_dia(texto, 2026), esperado, texto)
        for texto in ("Se esperan acumulados de lluvia...", "El martes 31 de setiembre...", "", None):
            self.assertIsNone(L.fecha_texto_dia(texto, 2026), texto)

    def test_es_del_dia(self):
        sab14 = date(2024, 12, 14)   # sábado
        casos = [
            ("El sábado 14 de diciembre se prevén...", sab14, True),
            # errata de mes (377 de 2024): coinciden el número y el día de la semana
            ("El sábado 14 de noviembre se prevén acumulados de lluvia...", sab14, True),
            # mes y día de la semana distintos: es otra fecha
            ("El jueves 14 de noviembre se prevén...", sab14, False),
            # el número manda: "martes 22" en el mapa del jueves 24 (375 de 2026, mapa 2)
            ("El martes 22 de setiembre se esperan...", date(2026, 9, 24), False),
            # sin mes (058 de 2025): basta el número, pero se exige
            ("El domingo 23 se esperan acumulados...", date(2025, 2, 23), True),
            ("El domingo 23 se esperan acumulados...", date(2025, 2, 24), False),
            ("El miércoles 06, se prevén acumulados...", date(2024, 3, 6), True),
            ("El miércoles 06, se prevén acumulados...", date(2024, 3, 7), False),
            # sin fecha: no se puede comprobar
            ("Se esperan acumulados de lluvia...", sab14, True),
        ]
        for texto, fecha, esperado in casos:
            self.assertEqual(L.es_del_dia(texto, fecha), esperado, (texto, fecha))

    def test_corpus_todos_los_dias_coinciden(self):
        # la fecha de cada mapa es inicio + (mapa - 1): con las erratas de mes (377 y 381 de 2024)
        # y los párrafos sin mes (058 y 060), ningún párrafo real se descarta
        for r in CORPUS:
            inicio = date.fromisoformat(r["inicio"])
            for i, d in enumerate(r["dias"]):
                self.assertTrue(L.es_del_dia(d, inicio + timedelta(days=i)), (r["nro"], r["emision"], i + 1))

    def test_375_mapa_2_es_de_otro_dia(self):
        # en la página del 22-09-2026 el párrafo del mapa 2 del 375 (jueves 24) dice "martes 22"
        dias = TEXTOS[(2026, 375)].dias
        self.assertEqual([L.fecha_texto_dia(dias[m], 2026) for m in (1, 2, 3)],
                         [date(2026, 9, 23), date(2026, 9, 22), date(2026, 9, 25)])


class TestMontos(unittest.TestCase):
    def test_376_dia_1(self):
        self.assertEqual(L.montos(TEXTOS[(2026, 376)].dias[1]), [
            {"lugar": "Tumbes", "desde": None, "hasta": 12, "forma": "hasta", "unidad": "mm"},
            {"lugar": "Costa de Piura", "desde": None, "hasta": 6, "forma": "cerca", "unidad": "mm"},
            {"lugar": "Sierra norte", "desde": 7, "hasta": 15, "forma": "rango", "unidad": "mm"},
        ])

    def test_lugar_antes_del_monto_y_mientras_que(self):
        m = L.montos("Para el martes 9 de junio, se estiman acumulados de lluvia de hasta 13 mm/día en Tumbes. En la "
                     "costa de Piura se prevén valores cercanos a 6 mm/día, mientras que en la sierra norte se "
                     "registrarán valores entre los 5 y 18 mm/día.")
        self.assertEqual([(x["lugar"], x["desde"], x["hasta"], x["forma"]) for x in m], [
            ("Tumbes", None, 13, "hasta"), ("Costa de Piura", None, 6, "cerca"), ("Sierra norte", 5, 18, "rango")])

    def test_cuatro_tramos_con_decimales(self):
        m = L.montos("El miércoles 18 de febrero se prevén acumulados de lluvia entre 50 y 85 mm/día en Tumbes y "
                     "Piura, y registros entre 5 y 12 mm/día en el resto de la costa norte. En la costa central se "
                     "esperan acumulados entre 0.2 y 4 mm/día, y valores entre 0.5 y 2 mm/día en la costa sur.")
        self.assertEqual([(x["lugar"], x["desde"], x["hasta"]) for x in m], [
            ("Tumbes y Piura", 50, 85), ("Resto de la costa norte", 5, 12), ("Costa central", 0.2, 4),
            ("Costa sur", 0.5, 2)])

    def test_nieve_en_cm(self):
        m = L.montos("El domingo 23 de agosto, se esperan acumulados de nieve de alrededor de 4 cm en la sierra "
                     "centro y de alrededor de 7 cm en la sierra sur.")
        self.assertEqual(m, [{"lugar": "Sierra centro", "desde": None, "hasta": 4, "forma": "cerca", "unidad": "cm"},
                             {"lugar": "Sierra sur", "desde": None, "hasta": 7, "forma": "cerca", "unidad": "cm"}])

    def test_todo_o_nada(self):
        casos = {
            "sin lugar": "Para el viernes 10 de julio, se estiman acumulados de lluvia entre los 5 y 14 mm/día.",
            "'de 55 mm' suelto": "El lunes 5 de enero se esperan valores de 55 mm/día en la selva norte.",
            "sin montos": "El lunes 5 de enero se esperan lluvias en la selva norte.",
        }
        for caso, texto in casos.items():
            self.assertIsNone(L.montos(texto), caso)
        self.assertIsNone(L.montos(None))

    def test_y_cercanos_a_corta_el_tramo(self):
        # 27-04: "y cercanos a" (CERCAN, PROXIM, SUPERIOR y MAYOR son comienzos de palabra)
        m = L.montos("El lunes 27 de abril se prevén acumulados de lluvia cercanos a los 60 mm/día en la selva "
                     "norte, valores próximos a los 70 mm/día en la selva centro y cercanos a los 80 mm/día en la "
                     "selva sur.")
        self.assertEqual([(x["lugar"], x["hasta"], x["forma"]) for x in m], [
            ("Selva norte", 60, "cerca"), ("Selva centro", 70, "cerca"), ("Selva sur", 80, "cerca")])
        for resto in ("y próximos a 3", "y superiores a 3", "y mayores a 3", "y cercanos a los 80"):
            self.assertIsNotNone(L.CORTE.search(L.plano(f" en la costa {resto}")), resto)

    def test_decimal_con_coma(self):
        m = L.montos("El lunes 17 de agosto se esperan acumulados de llovizna entre 0,5 y 2 mm/día en la costa de Lima.")
        self.assertEqual(m, [{"lugar": "Costa de Lima", "desde": 0.5, "hasta": 2, "forma": "rango", "unidad": "mm"}])
        # un rango al revés no se muestra
        self.assertIsNone(L.montos("El lunes 17 de agosto se esperan acumulados entre 18 y 5 mm/día en la sierra."))

    def test_frases_que_no_son_lugares(self):
        m = L.montos("El jueves 24 de setiembre, en la sierra norte se esperan acumulados de hasta 20 mm/día en promedio.")
        self.assertEqual([(x["lugar"], x["hasta"]) for x in m], [("Sierra norte", 20)])
        m = L.montos("El jueves 24 de setiembre se esperan acumulados de hasta 20 mm/día en horas de la tarde en la "
                     "sierra norte.")
        self.assertEqual([(x["lugar"], x["hasta"]) for x in m], [("Sierra norte", 20)])
        # si la frase queda pegada al lugar, el párrafo va literal
        self.assertIsNone(L.montos("El jueves 24 de setiembre se esperan acumulados de hasta 20 mm/día en la sierra "
                                   "norte en su mayoría."))

    def test_todo_o_nada_por_tramo_y_por_numero(self):
        casos = {
            # dos montos en un tramo: no se sabe de qué lugar es el primero
            "2 montos en un tramo": "El lunes 5 de enero se esperan acumulados de hasta 20 mm/día hasta 30 mm/día "
                                    "en la sierra norte.",
            # un número sin unidad queda suelto: la selva norte no es "30 a 40"
            "número suelto": "El lunes 5 de enero se esperan valores de 20, 30 y 40 mm/día en la selva norte, centro "
                             "y sur, respectivamente.",
            "lugar largo": "El lunes 5 de enero se esperan acumulados de hasta 20 mm/día en " + "la sierra norte " * 5,
        }
        for caso, texto in casos.items():
            self.assertIsNone(L.montos(texto), caso)
        # los números de la fecha (con el año) no cuentan
        m = L.montos("El domingo 11 de enero del 2026 se esperan acumulados entre los 12 y 26 mm/día en la sierra norte.")
        self.assertEqual([(x["lugar"], x["desde"], x["hasta"]) for x in m], [("Sierra norte", 12, 26)])

    def test_la_libertad_conserva_el_articulo(self):
        m = L.montos("El lunes 17 de agosto se prevén acumulados de llovizna en la costa norte, centro y sur del país. "
                     "En La Libertad y Áncash se estiman valores cercanos a 0.5 mm/día, mientras que en Lima e Ica "
                     "alrededor de 1 mm/día. En Arequipa se esperan acumulados próximos a 3.7 mm/día, y en Tacna y "
                     "Moquegua alrededor de 2 mm/día.")
        self.assertEqual([x["lugar"] for x in m], ["La Libertad y Áncash", "Lima e Ica", "Arequipa", "Tacna y Moquegua"])
        self.assertEqual(m[0]["hasta"], 0.5)

    def test_corpus(self):
        dias = [d for r in CORPUS for d in r["dias"]]
        leidos = [m for m in map(L.montos, dias) if m]
        self.assertEqual(len(dias), 1027)
        self.assertEqual(len(leidos), 945)
        malo = re.compile(r"\d|\bMM\b|\bCM\b|\bCOMO\b|\b(?:LUNES|MARTES|MIERCOLES|JUEVES|VIERNES|SABADO|DOMINGO)\b")
        lugares = {x["lugar"] for m in leidos for x in m}
        self.assertEqual([x for x in lugares if malo.search(L.plano(x)) or len(x) > L.MAX_LUGAR], [])
        self.assertEqual({x["forma"] for m in leidos for x in m} - {"rango", "hasta", "cerca", "mas_de"}, set())


class TestLectura(unittest.TestCase):
    def test_376_completo(self):
        t = TEXTOS[(2026, 376)]
        leido = L.lectura("meteorologico", TITULO_376, t.general, t.dias[1])
        self.assertEqual((leido["v"], leido["fenomeno"], leido["donde"]), (1, "lluvia", "la sierra norte y costa norte"))
        self.assertEqual(leido["intensidad"], "de ligera a moderada intensidad")
        self.assertEqual([x["lugar"] for x in leido["montos"]], ["Tumbes", "Costa de Piura", "Sierra norte"])
        self.assertEqual(json.loads(json.dumps(leido, ensure_ascii=False)), leido)   # cabe en jsonb tal cual
        # sin párrafo del día: todo lo demás igual, sin montos
        self.assertIsNone(L.lectura("meteorologico", TITULO_376, t.general, None)["montos"])

    def test_donde_con_departamentos(self):
        self.assertEqual(L.donde("LLUVIA EN TUMBES Y PIURA (ACTUALIZACIÓN DEL AVISO 90)"), "Tumbes y Piura")
        self.assertEqual(L.donde("LLOVIZNA EN LA COSTA DE LIMA-ICA"), "la costa de Lima, Ica")
        self.assertIsNone(L.donde("OLEAJE ANÓMALO"))


if __name__ == "__main__":
    unittest.main()
