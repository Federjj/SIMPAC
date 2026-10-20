"""
Cargador de "A dónde acudir" (backend/mapas/cargar_acudir.py): parseo de muestras reales pequeñas
(backend/tests/muestras/acudir/, filas de verdad de RENIPRESS, CENEPRED, CGBVP y gob.pe),
normalización de nombres, teléfonos y horarios, validaciones, clasificación de tipo y de
atiende_24h, los números de emergencia (y su copia del frontend) y el --aplicar con la BD simulada.
Sin red ni psycopg: solo librería estándar.
"""
import copy
import json
import logging
import re
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from backend.mapas import cargar_acudir as ca

MUESTRAS = Path(__file__).parent / "muestras" / "acudir"
RAIZ = Path(__file__).resolve().parents[2]
FUENTES = json.loads((MUESTRAS / "fuentes.json").read_text(encoding="utf-8"))


def setUpModule():
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(logging.NOTSET)


def _json(nombre):
    return json.loads((MUESTRAS / nombre).read_text(encoding="utf-8"))


def _csv():
    return (MUESTRAS / "renipress_cajamarca.csv").read_text(encoding="utf-8-sig")


def _por_clave(filas):
    return {f["clave"]: f for f in filas}


class TestHorario(unittest.TestCase):
    def test_24_horas(self):
        for h in ("24 HORAS", "24 horas", "24HRS", "24 H", "00:00 - 24:00", "0:00-24:00 HRS", "L-D 00 -24",
                  "7:00 - 7:00", "07:30 - 07:30", "7:30-7:30 (24 HORAS) DE LUNES A DOMINGO", "07:00 a.m. a 7 a.m.",
                  "LAS 24 HORAS", "24:00 HORAS", "24:00", "EMERGENCIA 24 HRS", "LUNES A DOMINGO 24 HORAS",
                  "8:00 - 8:00 L-D 24 horas", "LUNES A DOMINGO: 24"):
            self.assertIs(ca.atiende_24h(h), True, h)

    def test_no_es_24_horas(self):
        for h in ("8:00 - 20:00", "08:00 - 14:00", "6:00 - 24:00", "1:00 - 24:00", "05.00-24:00", "07:00 A 07:00 PM",
                  "9:30 - 9 PM", "12 HORAS", "7:00 A 19:00", "08:00 - 14:00 L-D", "10- 16", "07:00 - 07:30",
                  "7:30 -18:00", "8.00 - 20.00"):
            self.assertIs(ca.atiende_24h(h), False, h)

    def test_no_se_sabe(self):
        for h in ("", "   ", None, "LUNES A SABADO DE 08", "SEGUN PROGRAMACION", "ATENCION CONTINUA"):
            self.assertIsNone(ca.atiende_24h(h), repr(h))


class TestNormalizacion(unittest.TestCase):
    def test_nombre_bonito(self):
        casos = {
            "HOSPITAL REGIONAL DOCENTE CAJAMARCA": "Hospital Regional Docente Cajamarca",
            "HOSPITAL REGIONAL DE CAJAMARCA": "Hospital Regional de Cajamarca",
            "CLINICA LOS FRESNOS": "Clínica Los Fresnos",
            "LOS BAÑOS DEL INCA": "Los Baños del Inca",
            "VIRGEN DE LA PUERTA": "Virgen de la Puerta",
            "HOSPITAL II-1 CLINICA JAEN": "Hospital II-1 Clínica Jaén",
            "POSTA MEDICA SAN MARCOS - ESSALUD": "Posta Médica San Marcos - EsSalud",
            "CLINICA LIMATAMBO CAJAMARCA S.A.C.": "Clínica Limatambo Cajamarca S.A.C.",
            "SIMON BOLIVAR": "Simón Bolívar",
            "DE APOYO CELENDIN": "De Apoyo Celendín",
            "ventura centro odontologico": "Ventura Centro Odontológico",
            "HOSPITAL  III  EsSalud": "Hospital III EsSalud",
            "P.S CUMBE CHONTABAMBA": "P.S Cumbe Chontabamba",
            "SANIDAD PNP CAJAMARCA": "Sanidad PNP Cajamarca",
            "XXIII Comandancia Departamental Cajamarca": "XXIII Comandancia Departamental Cajamarca",
            "AV. MARIO URTEAGA N° 500": "Av. Mario Urteaga N° 500",
            "Av. Manco Cápac No. 140": "Av. Manco Cápac No. 140",
            "JR. DOS DE MAYO NO. 1298 CELENDIN": "Jr. Dos de Mayo No. 1298 Celendín",
            "E.I.R.L.": "E.I.R.L.",
        }
        for crudo, esperado in casos.items():
            self.assertEqual(ca.nombre_bonito(crudo), esperado)
        self.assertIsNone(ca.nombre_bonito(""))
        self.assertIsNone(ca.nombre_bonito("   "))
        self.assertIsNone(ca.nombre_bonito(None))

    def test_nombres_de_comisaria_y_bomberos(self):
        self.assertEqual(ca.nombre_comisaria("CPNP CENTRAL CAJAMARCA"), "Comisaría Central Cajamarca")
        self.assertEqual(ca.nombre_comisaria("CPNP BAÑOS DEL INCA"), "Comisaría Baños del Inca")
        self.assertEqual(ca.nombre_comisaria("COMISARIA PNP SAN JOSE"), "Comisaría San José")
        self.assertEqual(ca.nombre_bomberos("Cajamarca Nº59"), "Compañía de Bomberos Cajamarca Nº 59")
        self.assertEqual(ca.nombre_bomberos("Los Baños Del Inca Nº159"), "Compañía de Bomberos Los Baños del Inca Nº 159")
        self.assertEqual(ca.nombre_bomberos("Manuel Ugarte Y Moscoso Nº69"), "Compañía de Bomberos Manuel Ugarte y Moscoso Nº 69")
        self.assertEqual(ca.nombre_bomberos("LA UNION Nº240"), "Compañía de Bomberos La Unión Nº 240")

    def test_telefono(self):
        self.assertEqual(ca.telefono_limpio("076 - 363333"), "076-363333")
        self.assertEqual(ca.telefono_limpio("076599040; 076599030"), "076599040 / 076599030")
        self.assertEqual(ca.telefono_limpio("044-233333 - 044-294104"), "044-233333 / 044-294104")
        self.assertEqual(ca.telefono_limpio("427-0489 - 427-5392 - 7577670"), "427-0489 / 427-5392 / 7577670")
        self.assertEqual(ca.telefono_limpio("436-4582 / 436-4584"), "436-4582 / 436-4584")
        self.assertEqual(ca.telefono_limpio("  953  320 778 "), "953 320 778")
        self.assertEqual(ca.telefono_limpio("(51)76603710"), "(51)76603710")
        for vacio in ("0", "", None, "S/N", "976"):
            self.assertIsNone(ca.telefono_limpio(vacio), repr(vacio))

    def test_numero_de_compania(self):
        self.assertEqual(ca._numero_compania("B-59"), "59")
        self.assertEqual(ca._numero_compania("Cajamarca Nº59"), "59")
        self.assertEqual(ca._numero_compania("LA UNION Nº240"), "240")
        self.assertIsNone(ca._numero_compania(""))
        self.assertIsNone(ca._numero_compania(None))


class TestRenipress(unittest.TestCase):
    def test_muestra_real(self):
        filas, descartes = ca.parsear_renipress(_csv(), FUENTES["renipress"])
        f = _por_clave(filas)
        # 14 filas en la muestra: 10 entran; se descartan la penitenciaria, la que no tiene coordenadas,
        # el consultorio y la de baja
        self.assertEqual(len(filas), 10)
        self.assertEqual(dict(descartes), {"penitenciario (no es de acceso público)": 1, "sin coordenadas": 1,
                                           "no es hospital, centro, puesto ni policlínico": 1, "no activo": 1})
        self.assertNotIn("renipress:00018156", f)       # Establecimiento Penitenciario Cajamarca
        self.assertNotIn("renipress:00038800", f)       # Posta San Marcos EsSalud, sin coordenadas
        self.assertNotIn("renipress:00029108", f)       # consultorio
        self.assertNotIn("renipress:00033854", f)       # baja definitiva
        h = f["renipress:00007686"]
        self.assertEqual((h["tipo"], h["nombre"], h["categoria"], h["atiende_24h"]),
                         ("salud", "Hospital Regional Docente Cajamarca", "Hospital II-2", True))
        self.assertEqual((h["telefono"], h["departamento"], h["provincia"], h["distrito"], h["ubigeo"]),
                         ("076599040 / 076599030", "Cajamarca", "Cajamarca", "Cajamarca", "060101"))
        self.assertEqual((h["lat"], h["lon"]), (-7.183407, -78.487692))
        self.assertEqual((h["fuente"], h["fuente_url"], h["fuente_id"], h["licencia"], h["actualizado"]),
                         ("SUSALUD RENIPRESS", FUENTES["renipress"]["url"], "00007686", "ODC-By", "2026-09-30"))
        self.assertEqual(h["detalle"], {"institucion": "GOBIERNO REGIONAL", "clasificacion": "HOSPITALES O CLINICAS DE ATENCION GENERAL",
                                        "nivel": "II-2", "horario": "24 HORAS", "con_internamiento": True})
        # EsSalud, privadas (Clínica), especializado, con camas, puesto
        self.assertEqual(f["renipress:00010272"]["nombre"], "Hospital II Cajamarca")
        self.assertEqual(f["renipress:00010272"]["detalle"]["institucion"], "ESSALUD")
        self.assertEqual((f["renipress:00009234"]["nombre"], f["renipress:00009234"]["categoria"]), ("Clínica Los Fresnos", "Clínica II-1"))
        self.assertEqual((f["renipress:00004655"]["nombre"], f["renipress:00004655"]["categoria"]), ("Simón Bolívar", "Hospital especializado II-E"))
        self.assertEqual(f["renipress:00004501"]["categoria"], "Centro de salud con camas I-4")
        self.assertEqual(f["renipress:00004521"]["categoria"], "Puesto de salud I-1")
        # atiende_24h sale del texto libre: 'L-D 00 -24' y '7:30-7:30 (24 HORAS)' y '07:00 a.m. a 7 a.m.' sí;
        # '12 HORAS' y '07:30 - 13:30' no
        self.assertIs(f["renipress:00004466"]["atiende_24h"], True)
        self.assertIs(f["renipress:00004501"]["atiende_24h"], True)
        self.assertIs(f["renipress:00004593"]["atiende_24h"], True)
        self.assertIs(f["renipress:00004521"]["atiende_24h"], False)
        self.assertIs(f["renipress:00004647"]["atiende_24h"], False)
        # teléfono '0' queda en null; el horario crudo se conserva en detalle
        self.assertIsNone(f["renipress:00011258"]["telefono"])
        self.assertEqual(f["renipress:00004593"]["detalle"]["horario"], "07:00 a.m. a 7 a.m.")
        self.assertEqual(f["renipress:00004593"]["distrito"], "Los Baños del Inca")
        self.assertTrue(all(x["tipo"] == "salud" and x["departamento"] == "Cajamarca" for x in filas))

    def test_falta_columna(self):
        texto = _csv().replace("COD_IPRESS", "CODIGO")
        with self.assertRaisesRegex(ValueError, "faltan columnas"):
            ca.parsear_renipress(texto, FUENTES["renipress"])

    def test_coordenadas_fuera_del_peru(self):
        texto = _csv().replace("-7.183407;-78.487692", "-78.487692;-7.183407")   # lat y lon invertidas
        filas, descartes = ca.parsear_renipress(texto, FUENTES["renipress"])
        self.assertNotIn("renipress:00007686", _por_clave(filas))
        self.assertEqual(descartes["coordenadas fuera del Perú"], 1)

    def test_filtrar_csv(self):
        texto = _csv().replace("CAJAMARCA;CAJAMARCA;CAJAMARCA;060101", "LIMA;LIMA;LIMA;150101", 1)
        filtrado = ca.filtrar_csv(texto)
        self.assertEqual(filtrado.count("\n"), 14)                 # cabecera + 13 (una se fue a Lima)
        self.assertEqual(ca.filtrar_csv(texto, "LIMA").count("\n"), 2)
        self.assertTrue(filtrado.startswith("INSTITUCION;COD_IPRESS;"))

    def test_ultimo_csv_de_la_ficha(self):
        html = ('<a href="/sites/default/files/RENIPRESS_30-04-2026.csv">x</a> '
                '<a href="/sites/default/files/RENIPRESS_30-09-2026.csv">y</a> '
                '<a href="/sites/default/files/RENIPRESS_31-07-2026.csv">z</a>')
        self.assertEqual(ca.ultimo_csv_renipress(html), "RENIPRESS_30-09-2026.csv")
        with self.assertRaisesRegex(ValueError, "no enlaza"):
            ca.ultimo_csv_renipress("<html>sin csv</html>")


class TestComisariasYBomberos(unittest.TestCase):
    def test_comisarias(self):
        filas, descartes = ca.parsear_comisarias(_json("comisarias_cenepred.json"), FUENTES["comisarias"])
        self.assertEqual(len(filas), 4)
        self.assertEqual(dict(descartes), {})
        f = _por_clave(filas)
        c = f["comisarias:5000"]
        self.assertEqual((c["tipo"], c["nombre"], c["categoria"], c["atiende_24h"], c["telefono"], c["direccion"]),
                         ("comisaria", "Comisaría Central Cajamarca", "Comisaría tipo A", None, None, None))
        self.assertAlmostEqual(c["lat"], -7.16019, places=4)
        self.assertAlmostEqual(c["lon"], -78.51291, places=4)
        self.assertEqual((c["departamento"], c["provincia"], c["distrito"], c["ubigeo"]), ("Cajamarca", "Cajamarca", "Cajamarca", "060101"))
        self.assertEqual((c["fuente_id"], c["licencia"], c["actualizado"]), ("5000", "ODC-By", "2019-11-30"))
        self.assertEqual(c["detalle"]["tipo_comisaria"], "A")
        self.assertIn("2019", c["detalle"]["nota"])
        self.assertEqual((f["comisarias:5010"]["nombre"], f["comisarias:5010"]["distrito"]),
                         ("Comisaría Baños del Inca", "Los Baños del Inca"))
        self.assertEqual(f["comisarias:6024"]["departamento"], "Callao")

    def test_comisaria_sin_codigo_ni_punto(self):
        geo = _json("comisarias_cenepred.json")
        geo["features"][0]["properties"]["cod_cpnp"] = ""
        geo["features"][1]["geometry"] = None
        filas, descartes = ca.parsear_comisarias(geo, FUENTES["comisarias"])
        self.assertEqual(len(filas), 2)
        self.assertEqual(dict(descartes), {"sin cod_cpnp": 1, "sin coordenadas": 1})

    def test_bomberos(self):
        filas, descartes = ca.parsear_bomberos(_json("bomberos_cenepred.json"), _json("bomberos_cgbvp.json"),
                                               FUENTES["bomberos_cenepred"], FUENTES["bomberos_cgbvp"])
        self.assertEqual(sorted(f["clave"] for f in filas), ["bomberos:158", "bomberos:159", "bomberos:25", "bomberos:59", "bomberos:69"])
        # la comandancia de Piura de la muestra tiene 13 compañías y solo una con punto en CENEPRED
        self.assertEqual(dict(descartes), {"compañía CGBVP sin punto en CENEPRED (no se carga)": 12})
        b = _por_clave(filas)["bomberos:59"]
        self.assertEqual((b["tipo"], b["nombre"], b["categoria"], b["direccion"], b["telefono"], b["atiende_24h"]),
                         ("bomberos", "Compañía de Bomberos Cajamarca Nº 59", "Compañía de bomberos", "Av Atahualpa 107",
                          "076-363333", None))
        self.assertAlmostEqual(b["lat"], -7.164544, places=5)
        self.assertAlmostEqual(b["lon"], -78.509765, places=5)
        self.assertEqual((b["departamento"], b["provincia"], b["distrito"], b["fuente_id"]), ("Cajamarca", "Cajamarca", "Cajamarca", "59"))
        self.assertEqual(b["detalle"]["comandancia"], "XXIII Comandancia Departamental Cajamarca")
        self.assertEqual((b["detalle"]["cia"], b["detalle"]["codidenest"]), ("B-59", "305900"))
        self.assertEqual(b["detalle"]["coordenadas_de"], FUENTES["bomberos_cenepred"]["url"])
        self.assertIsNone(b["detalle"]["sin_directorio_cgbvp"])
        b159 = _por_clave(filas)["bomberos:159"]
        self.assertEqual((b159["nombre"], b159["direccion"], b159["distrito"]),
                         ("Compañía de Bomberos Los Baños del Inca Nº 159", "Av. Manco Cápac No. 140", "Los Baños del Inca"))

    def test_bomberos_sin_ficha_cgbvp(self):
        cg = _json("bomberos_cgbvp.json")
        cg["companias"]["223000"] = [c for c in cg["companias"]["223000"] if ca._numero_compania(c["nombre"]) != "59"]
        filas, descartes = ca.parsear_bomberos(_json("bomberos_cenepred.json"), cg,
                                               FUENTES["bomberos_cenepred"], FUENTES["bomberos_cgbvp"])
        b = _por_clave(filas)["bomberos:59"]          # el punto se carga igual, sin dirección ni teléfono
        self.assertEqual((b["nombre"], b["direccion"], b["telefono"]), ("Compañía de Bomberos Cajamarca Nº 59", None, None))
        self.assertIs(b["detalle"]["sin_directorio_cgbvp"], True)
        self.assertEqual(descartes["punto CENEPRED sin ficha en el portal CGBVP (sin dirección ni teléfono)"], 1)


class TestManualYValidacion(unittest.TestCase):
    def test_defensa_civil(self):
        filas = ca.parsear_manual(_json("defensa_civil.json"))
        self.assertEqual([f["clave"] for f in filas], ["manual:indeci_cajamarca", "manual:municipalidad_cajamarca", "manual:gore_cajamarca"])
        i = filas[0]
        self.assertEqual((i["tipo"], i["nombre"], i["categoria"], i["telefono"], i["lat"], i["lon"]),
                         ("otro", "Dirección Desconcentrada INDECI Cajamarca", "Defensa Civil (INDECI)",
                          "988061992 / 950090534", -7.15886, -78.508295))
        self.assertEqual(i["fuente_url"], "https://www.gob.pe/institucion/indeci/sedes")
        self.assertEqual(i["detalle"]["verificado_en"], "2026-10-14")
        for f in filas:
            ca.validar_fila(f)        # pasan las mismas reglas que la BD

    def test_manual_incompleto(self):
        d = _json("defensa_civil.json")
        d["puntos"][0]["fuente_url"] = ""
        with self.assertRaisesRegex(ValueError, "faltan"):
            ca.parsear_manual(d)
        d = _json("defensa_civil.json")
        del d["puntos"][1]["detalle"]["verificado_en"]
        with self.assertRaisesRegex(ValueError, "verificado_en"):
            ca.parsear_manual(d)
        d = _json("defensa_civil.json")
        d["puntos"][2]["clave"] = "gore:cajamarca"
        with self.assertRaisesRegex(ValueError, "manual:"):
            ca.parsear_manual(d)

    def test_validar_fila(self):
        base = ca.parsear_manual(_json("defensa_civil.json"))[0]
        fila = ca.validar_fila(base)
        self.assertEqual(sorted(fila), sorted(ca.CAMPOS_FILA))
        self.assertEqual(json.loads(fila["detalle"])["verificado_en"], "2026-10-14")
        malos = [
            ({"lat": -78.508295, "lon": -7.15886}, "no cae en el Perú"),
            ({"lat": None}, "no cae en el Perú"),
            ({"tipo": "hospital"}, "tipo"),
            ({"departamento": "CAJAMARCA"}, "no es canónico"),
            ({"fuente_url": "http://www.gob.pe/institucion/indeci/sedes"}, "https"),
            ({"telefono": "sin número"}, "sin dígitos"),
            ({"clave": "INDECI Cajamarca"}, "clave inválida"),
            ({"ubigeo": "0601"}, "ubigeo"),
            ({"atiende_24h": "sí"}, "atiende_24h"),
            ({"nombre": ""}, "falta nombre"),
            ({"actualizado": "14/10/2026"}, "AAAA-MM-DD"),
        ]
        for cambio, mensaje in malos:
            with self.assertRaisesRegex(ValueError, mensaje, msg=str(cambio)):
                ca.validar_fila({**base, **cambio})

    def test_numeros_de_emergencia_y_copia_del_frontend(self):
        numeros = ca.validar_numeros(json.loads((ca.DATOS / "numeros.json").read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(numeros), 14)
        por_numero = {n["numero"]: n for n in numeros}
        for basico in ("105", "116", "115", "106", "113"):
            self.assertEqual(por_numero[basico]["ambito"], "nacional")
            self.assertEqual(por_numero[basico]["fuente_url"], "https://www.gob.pe/547")
        self.assertIn("Cajamarca no figura", por_numero["106"]["nota"])      # SAMU con su salvedad
        self.assertTrue(any(n["ambito"] == "Cajamarca" and "988061992" in n["numero"] for n in numeros))
        self.assertFalse(any("COER" in n["servicio"] and n["numero"].startswith("076-3458") for n in numeros))
        # la copia del frontend tiene la misma lista, en el mismo orden
        js = (RAIZ / "frontend" / "src" / "data" / "emergencias.js").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'numero: "([^"]*)"', js), [n["numero"] for n in numeros])
        self.assertEqual(re.findall(r'servicio: "([^"]*)"', js), [n["servicio"] for n in numeros])
        self.assertEqual(re.findall(r'fuente_url: "([^"]*)"', js), [n["fuente_url"] for n in numeros])

    def test_numeros_invalidos(self):
        with self.assertRaisesRegex(ValueError, "sin números"):
            ca.validar_numeros({"numeros": []})
        with self.assertRaisesRegex(ValueError, "ambito"):
            ca.validar_numeros({"numeros": [{"ambito": "Lima", "servicio": "x", "numero": "105",
                                             "fuente_url": "https://www.gob.pe/547", "verificado": "2026-10-14"}]})
        with self.assertRaisesRegex(ValueError, "https"):
            ca.validar_numeros({"numeros": [{"ambito": "nacional", "servicio": "x", "numero": "105",
                                             "fuente_url": "http://www.gob.pe/547", "verificado": "2026-10-14"}]})


class TestCargar(unittest.TestCase):
    def test_carpeta_de_muestras(self):
        filas, descartes = ca.cargar(MUESTRAS)
        self.assertEqual(len(filas), 10 + 4 + 5 + 3)
        self.assertEqual(descartes["salud"]["no activo"], 1)
        c = ca.conteo(filas)
        self.assertEqual(c["por_tipo"], {"salud": 10, "comisaria": 4, "bomberos": 5, "otro": 3})
        self.assertEqual(c["salud_24h"], 7)
        self.assertEqual(c["por_departamento"]["Cajamarca"], {"salud": 10, "comisaria": 3, "bomberos": 4, "otro": 3})
        self.assertEqual(c["por_departamento"]["Callao"], {"comisaria": 1})
        self.assertEqual(c["por_departamento"]["Piura"], {"bomberos": 1})
        self.assertEqual(c["cajamarca"], {"region": 20, "provincia": 14, "ciudad": 14,
                                          "salud_24h_region": 7, "salud_24h_provincia": 5})
        self.assertEqual(ca.resumen(filas), "22 puntos: salud 10 (24 h: 7), comisaria 4, bomberos 5, otro 3 | "
                                            "Cajamarca: región 20, provincia 14, ciudad 14")
        # todas las filas van listas para SQL: detalle como texto JSON, fechas ISO, departamento canónico
        for f in filas:
            self.assertIsInstance(json.loads(f["detalle"]), dict)
            self.assertIn(f["departamento"], ca.CANONICOS)
            self.assertRegex(f["actualizado"], r"^\d{4}-\d{2}-\d{2}$")

    def _copia(self):
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        for a in ca.ARCHIVOS.values():
            shutil.copy(MUESTRAS / a, carpeta / a)
        return carpeta

    def test_falta_archivo(self):
        carpeta = self._copia()
        (carpeta / "bomberos_cgbvp.json").unlink()
        with self.assertRaisesRegex(ValueError, "faltan archivos.*bomberos_cgbvp.json"):
            ca.cargar(carpeta)

    def test_fuente_vacia_no_pasa(self):
        carpeta = self._copia()
        texto = _csv()
        (carpeta / "renipress_cajamarca.csv").write_text(texto.split("\n", 1)[0] + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "salud no dio ningún punto"):
            ca.cargar(carpeta)

    def test_clave_repetida(self):
        carpeta = self._copia()
        d = _json("defensa_civil.json")
        d["puntos"].append(dict(d["puntos"][0]))
        (carpeta / "defensa_civil.json").write_text(json.dumps(d), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "claves repetidas"):
            ca.cargar(carpeta)

    def test_fuentes_sin_fecha(self):
        carpeta = self._copia()
        fu = copy.deepcopy(FUENTES)
        del fu["comisarias"]["actualizado"]
        (carpeta / "fuentes.json").write_text(json.dumps(fu), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "comisarias.*url y actualizado"):
            ca.cargar(carpeta)

    def test_pais_sin_cache(self):
        with mock.patch.object(ca, "CACHE_PAIS", Path(tempfile.mkdtemp()) / "no_existe"):
            with self.assertRaisesRegex(ValueError, "--descargar --pais"):
                ca.cargar(MUESTRAS, pais=True)


class _Cursor:
    """punto_acudir en memoria ({clave: departamento}) con la semántica de las sentencias."""

    def __init__(self, conn):
        self.conn, self.rowcount, self.filas = conn, -1, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _sobran(self, p):
        prefijo = p["prefijo"][:-1]
        return [k for k, d in self.conn.tabla.items()
                if k.startswith(prefijo) and d in p["deptos"] and k not in p["claves"]]

    def execute(self, sql, params=None):
        self.conn.registro.append((sql, params))
        self.rowcount = 0
        if sql == ca.SQL_HAY_TABLA:
            self.filas = [(self.conn.migrada,)]
        elif sql == ca.SQL_CONTAR_PODA:
            self.filas = [(len(self._sobran(params)),)]
        elif sql == ca.SQL_PODAR:
            for k in self._sobran(params):
                del self.conn.tabla[k]
                self.rowcount += 1

    def executemany(self, sql, filas):
        filas = list(filas)
        self.conn.registro.append((sql, filas))
        if sql == ca.SQL_UPSERT:
            self.conn.tabla.update({f["clave"]: f["departamento"] for f in filas})

    def fetchone(self):
        return self.filas[0]


class _Conexion:
    def __init__(self, migrada=True, tabla=None):
        self.migrada, self.registro, self.tabla = migrada, [], dict(tabla or {})

    def cursor(self):
        return _Cursor(self)


def _conectar(conn):
    @contextmanager
    def falso_conectar():
        yield conn
    return falso_conectar


class TestAplicar(unittest.TestCase):
    def setUp(self):
        self.filas, _ = ca.cargar(MUESTRAS)

    def test_upsert_idempotente(self):
        conn = _Conexion()
        self.assertEqual(ca.aplicar(conn, self.filas), (22, 0))
        self.assertEqual(ca.aplicar(conn, self.filas), (22, 0))
        self.assertEqual(len(conn.tabla), 22)
        self.assertEqual(conn.tabla["comisarias:6024"], "Callao")

    def test_sin_podar_conserva_y_avisa(self):
        conn = _Conexion(tabla={"renipress:00000001": "Cajamarca", "renipress:00000002": "Lima", "comisarias:1": "Cajamarca"})
        logging.disable(logging.NOTSET)
        try:
            with self.assertLogs("cargar_acudir", level="WARNING") as registro:
                self.assertEqual(ca.aplicar(conn, self.filas), (22, 0))
        finally:
            logging.disable(logging.CRITICAL)
        self.assertEqual(len(conn.tabla), 25)
        self.assertTrue(any("renipress" in m and "--podar" in m for m in registro.output))
        self.assertNotIn(ca.SQL_PODAR, [s for s, _ in conn.registro])

    def test_podar_solo_dentro_de_lo_cargado(self):
        conn = _Conexion(tabla={"renipress:00000001": "Cajamarca",      # misma fuente y departamento: se va
                                "renipress:00000002": "Lima",           # Lima no vino en la carga: se queda
                                "comisarias:1": "Cajamarca",            # se va
                                "manual:viejo": "Cajamarca",            # se va
                                "albergues:1": "Cajamarca"})            # fuente que no se cargó: se queda
        self.assertEqual(ca.aplicar(conn, self.filas, podar=True), (22, 3))
        self.assertEqual(sorted(k for k in conn.tabla if k not in {f["clave"] for f in self.filas}),
                         ["albergues:1", "renipress:00000002"])


class TestMain(unittest.TestCase):
    def test_prueba_en_seco_no_conecta(self):
        with mock.patch.object(ca, "conectar", side_effect=AssertionError("no debe conectar")):
            self.assertEqual(ca.main(["--datos", str(MUESTRAS)]), 0)

    def test_datos_invalidos(self):
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        self.assertEqual(ca.main(["--datos", str(carpeta)]), 1)

    def test_aplicar(self):
        conn = _Conexion()
        with mock.patch.object(ca, "conectar", _conectar(conn)):
            self.assertEqual(ca.main(["--datos", str(MUESTRAS), "--aplicar"]), 0)
        self.assertEqual(len(conn.tabla), 22)

    def test_sin_migracion_ni_db_url(self):
        with mock.patch.object(ca, "conectar", _conectar(_Conexion(migrada=False))):
            self.assertEqual(ca.main(["--datos", str(MUESTRAS), "--aplicar"]), 2)
        with mock.patch.object(ca, "conectar", side_effect=RuntimeError("Falta SUPABASE_DB_URL")):
            self.assertEqual(ca.main(["--datos", str(MUESTRAS), "--aplicar"]), 2)

    def test_descargar_no_borra_si_falla(self):
        """Si una fuente no responde, --descargar deja el archivo anterior y la carga sigue con él."""
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        for a in ca.ARCHIVOS.values():
            shutil.copy(MUESTRAS / a, carpeta / a)
        antes = {a: (carpeta / a).read_bytes() for a in ca.ARCHIVOS.values()}
        with mock.patch.object(ca, "_bajar", side_effect=OSError("sin red")):
            fallas = ca.descargar(carpeta)
        self.assertEqual(fallas, ["renipress", "comisarias", "bomberos_cenepred", "bomberos_cgbvp"])
        for a, contenido in antes.items():
            if a != "fuentes.json":
                self.assertEqual((carpeta / a).read_bytes(), contenido, a)
        self.assertEqual(json.loads((carpeta / "fuentes.json").read_text(encoding="utf-8")), FUENTES)
        filas, _ = ca.cargar(carpeta)
        self.assertEqual(len(filas), 22)


if __name__ == "__main__":
    unittest.main()
