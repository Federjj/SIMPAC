"""
Tarea 'titular' (backend/ingesta/titular.py): los insumos que calcula Python, el respaldo
determinista, el pedido al modelo (armado igual que en producción, con la llamada HTTP
simulada), la validación de lo que responde y la corrida completa con la BD simulada. Sin red
ni psycopg: solo librería estándar.
"""
import io
import json
import logging
import re
import time
import types
import unittest
import urllib.error
from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest import mock

from backend.ingesta import titular as tarea
from backend.ingesta.guardar import SQL_LATIDO

AHORA = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)      # 07:00 del 14-10 en Lima
TS = datetime(2026, 10, 14, 11, 30, tzinfo=timezone.utc)        # 06:30 en Lima
HOY = date(2026, 10, 14)
MODELO = "claude-haiku-4-5-20251001"

AVISO = {"tipo": "aviso", "referencia": "SENAMHI aviso 377", "zona": "Cajamarca", "nivel": "alerta",
         "detalle": "Lluvias de moderada a fuerte intensidad en la sierra norte del 14 al 16 de octubre",
         "valor": None, "umbral": None, "ventana_h": None, "ts": TS}
AVISO_AMARILLO = {**AVISO, "referencia": "SENAMHI aviso 380", "nivel": "aviso", "detalle": "Lluvias ligeras en la sierra"}
CAUDAL_ALERTA = {"tipo": "caudal", "referencia": "Chilete (Jequetepeque)", "zona": "Cajamarca", "nivel": "alerta",
                 "detalle": "Caudal 80 m³/s, subiendo (nivel de alerta de ANA: 70 m³/s)", "valor": 80.0, "umbral": 70.0,
                 "ventana_h": None, "ts": TS}
LLUVIA = {"tipo": "lluvia", "referencia": "CHOTA GORE@-6.55405,-78.67588", "zona": "Cajamarca", "nivel": "aviso",
          "detalle": "En Chota GORE llovió 12.4 mm en la hora que terminó a las 06:00 (referencia de SENAMHI: 10 mm)",
          "valor": 12.4, "umbral": 10.0, "ventana_h": 1, "ts": TS}
# vaciante de ANA (umbral_emergencia < umbral_alerta): el Nanay en emergencia por lo BAJO que está
NIVEL_BAJO = {"tipo": "nivel_bajo", "referencia": "Santa María de Nanay (Nanay)", "zona": "Loreto", "nivel": "emergencia",
              "detalle": "Río bajo (vaciante): nivel 122.42 m.s.n.m, bajando", "valor": 122.42, "umbral": 122.5,
              "ventana_h": None, "ts": TS}
AVISO_LORETO = {**AVISO_AMARILLO, "zona": "Loreto", "referencia": "SENAMHI lluvia 24h"}


def _caudal(estacion, rio, depto, valor, ua, ue, unidad="m³/s", hora="06:00"):
    return {"estacion": estacion, "rio": rio, "departamento": depto, "fecha": HOY, "hora": hora, "valor": valor,
            "unidad": unidad, "umbral_alerta": ua, "umbral_emergencia": ue, "tendencia": "Estable", "estado": None}


def _lluvia(nombre, depto, pp_1h, umbral_1h=10.0, pp_6h=0.0, umbral_6h=40.0):
    return {"nombre": nombre, "departamento": depto, "pp_1h": pp_1h, "umbral_1h": umbral_1h, "pp_6h": pp_6h,
            "umbral_6h": umbral_6h, "medido_en": TS}


CAUDALES = [
    _caudal("Chilete", "Jequetepeque", "CAJAMARCA", 80.0, 70.0, 120.0),
    _caudal("Mashcón", "Mashcon", "Cajamarca", 0.13, 1.5, 2.0, unidad="m", hora="05:00"),
    _caudal("Tambogrande", "Piura", "PIURA", 25.0, 400.0, 600.0),
]
LLUVIA_ESTACIONES = [
    _lluvia("CHOTA GORE", "CAJAMARCA", 12.4),
    _lluvia("WEBERBAUER", "Cajamarca", 0.0),
    _lluvia("MIRAFLORES", "PIURA", 0.0),
]
AVISOS = [{"id": 1, "tipo": "meteorologico", "numero": 377, "nivel": 3, "titulo": "Lluvias en la sierra", "tema": "lluvia",
           "inicio": TS, "fin": datetime(2026, 10, 16, 5, 0, tzinfo=timezone.utc), "en_curso": True,
           "departamentos": ["Cajamarca"], "ts_captura": TS}]
ENFEN = {"anio": 2026, "numero": 17, "extraordinario": False, "fecha": date(2026, 10, 9),
         "estado": "Alerta de El Niño Costero", "proximo": date(2026, 10, 23)}
ENFEN_NO_ACTIVO = {**ENFEN, "estado": "No activo"}
RIOS = [{"id": "mashcon", "nombre": "Río Mashcón", "departamento": "Cajamarca", "estacion_ana": "Mashcón",
         "rio_ana": "Mashcon",
         "avisos_lluvia": [{"id": 1, "numero": 377, "nivel": 3, "en_curso": True}],
         "lluvia_cuenca": [{"nombre": "WEBERBAUER", "pp_1h": 0.0, "umbral_1h": 10.0, "pp_6h": 0.0, "umbral_6h": 40.0}],
         "avisos_hidro": []}]


def _crudo(alertas=(AVISO, CAUDAL_ALERTA, LLUVIA), caudales=CAUDALES, lluvia=LLUVIA_ESTACIONES, avisos=AVISOS,
           rios=RIOS, enfen=ENFEN, previos=None):
    return {"alertas": [dict(a) for a in alertas], "caudales": [dict(c) for c in caudales],
            "lluvia": [dict(e) for e in lluvia], "avisos": [dict(a) for a in avisos], "rios": [dict(r) for r in rios],
            "enfen": dict(enfen) if enfen else None, "previos": dict(previos or {})}


def _insumos(depto="Cajamarca", **kw):
    i = tarea.armar_insumos(depto, _crudo(**kw), AHORA)
    return {**i, "huella": tarea.huella(i)}


def _estado():
    return {"inicio": time.monotonic(), "fallas_seguidas": 0, "descartados": [], "avisos": []}


# ---------------------------------------------------------------------------------------
# API simulada: lo que recibe y lo que devuelve
# ---------------------------------------------------------------------------------------
class _Respuesta:
    def __init__(self, cuerpo: dict):
        self.cuerpo = json.dumps(cuerpo).encode("utf-8")

    def read(self):
        return self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _ok(texto, stop_reason="end_turn"):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": MODELO,
            "content": [{"type": "text", "text": texto}], "stop_reason": stop_reason,
            "usage": {"input_tokens": 500, "output_tokens": 60}}


class _Api:
    """Un urlopen de mentira: anota cada pedido y responde con `redactar(departamento)` o lanza `falla`."""

    def __init__(self, redactar=None, falla=None):
        self.redactar = redactar or (lambda d: f"{d}: SIMPAC revisó las fuentes oficiales de hoy.")
        self.falla = falla
        self.pedidos = []

    def __call__(self, pedido, timeout=None):
        cuerpo = json.loads(pedido.data.decode("utf-8"))
        self.pedidos.append((pedido, cuerpo, timeout))
        if self.falla:
            raise self.falla
        depto = re.search(r"Departamento: (.+)", cuerpo["messages"][0]["content"]).group(1)
        return _Respuesta(_ok(self.redactar(depto)))


def _http_error(codigo=429, cuerpo=b'{"type":"error","error":{"type":"rate_limit_error"}}'):
    return urllib.error.HTTPError(tarea.API_URL, codigo, "simulado", {}, io.BytesIO(cuerpo))


# ---------------------------------------------------------------------------------------
# BD simulada
# ---------------------------------------------------------------------------------------
def _columnas(sql: str) -> list[str]:
    """Nombres de columna de un 'select a, b as c, t.d from ...' (para cur.description)."""
    campos = re.search(r"select\s+(.*?)\s+from\s", sql, re.S | re.I).group(1)
    salida = []
    for campo in campos.split(","):
        campo = campo.strip()
        if " as " in campo:
            campo = campo.split(" as ")[-1]
        salida.append(campo.split(".")[-1].strip())
    return salida


class _Cursor:
    def __init__(self, conn):
        self.conn, self.ultima, self.description = conn, None, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.registro.append((sql, params))
        self.ultima = sql
        tabla = self.conn.tablas.get(sql)
        if tabla is not None:
            self.description = [(c,) for c in _columnas(sql)]

    def executemany(self, sql, filas):
        self.conn.registro.append((sql, list(filas)))

    def fetchone(self):
        assert self.ultima == tarea.SQL_HAY_TABLA, self.ultima
        return (self.conn.migrada,)

    def fetchall(self):
        filas = self.conn.tablas[self.ultima]
        return [tuple(f.get(c) for c in _columnas(self.ultima)) for f in filas]


class _Conexion:
    """Anota cada sentencia; `crudo` son las filas que devuelven las consultas de lectura."""

    def __init__(self, crudo=None, migrada=True):
        self.migrada, self.registro = migrada, []
        crudo = crudo or _crudo()
        self.tablas = {
            tarea.SQL_ALERTAS: crudo["alertas"], tarea.SQL_CAUDAL: crudo["caudales"], tarea.SQL_LLUVIA: crudo["lluvia"],
            tarea.SQL_AVISOS: crudo["avisos"], tarea.SQL_RIOS_VIGILADOS: crudo["rios"],
            tarea.SQL_ENFEN: [crudo["enfen"]] if crudo.get("enfen") else [],
            tarea.SQL_PREVIOS: list(crudo.get("previos", {}).values()),
        }

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]


# ---------------------------------------------------------------------------------------
# Insumos
# ---------------------------------------------------------------------------------------
class TestInsumos(unittest.TestCase):
    def test_cajamarca_con_aviso_rio_y_lluvia(self):
        i = tarea.armar_insumos("Cajamarca", _crudo(), AHORA)
        self.assertEqual((i["nivel"], i["etiqueta"]), ("alerta", "Alerta"))
        # un aviso de SENAMHI y un río cuentan; la lluvia medida no es oficial
        self.assertEqual(i["alertas_oficiales"], 2)
        self.assertEqual([(a["referencia"], a["color"]) for a in i["avisos_senamhi"]], [("SENAMHI aviso 377", "naranja")])
        self.assertEqual([r["referencia"] for r in i["rios_crecida"]], ["Chilete (Jequetepeque)"])
        self.assertEqual([e["estacion"] for e in i["lluvia_sobre_referencia"]], ["CHOTA GORE"])
        self.assertEqual(i["rios"], {"estaciones": 2, "con_nivel_de_alerta": 2, "pasan_su_nivel": 1,
                                     "cerca_de_su_nivel": 0, "muy_bajos": 0})
        self.assertEqual(i["lluvia"], {"estaciones": 2, "con_lluvia": 1, "max_mm_hora": 12.4,
                                       "estacion_max": "CHOTA GORE", "sobre_referencia": 1})
        # el río vigilado: aviso naranja sobre su cuenca = atentos (su estación está tranquila)
        rio = i["rio_vigilado"]
        self.assertEqual((rio["nombre"], rio["nivel"], rio["medicion_ana"]), ("Río Mashcón", "atentos", True))
        self.assertIn("aviso naranja de SENAMHI por lluvias sobre su cuenca", rio["senales"][0])
        e = i["enfen"]
        self.assertEqual((e["corto"], e["quien"], e["comunicado"], e["fecha_legible"], e["atrasado"]),
                         ("alerta", "El Niño costero", "CO 17-2026", "9 oct", False))
        # horas en hora de Perú: la última lectura real de caudal, no la mayor por texto
        self.assertEqual(i["horas"]["caudal"], "14 oct 06:00")
        self.assertEqual(i["horas"]["lluvia"], "14 oct 06:30")
        self.assertEqual(i["horas"]["revisado"], "14 oct 07:00")

    def test_piura_sin_alertas_con_cobertura_es_normal(self):
        i = tarea.armar_insumos("Piura", _crudo(), AHORA)
        self.assertEqual((i["nivel"], i["etiqueta"], i["alertas_oficiales"]), ("normal", "Normal", 0))
        self.assertEqual((i["rios"]["con_nivel_de_alerta"], i["lluvia"]["estaciones"]), (1, 1))
        self.assertIsNone(i["rio_vigilado"])

    def test_sin_nada_que_revisar_es_sin_dato(self):
        i = tarea.armar_insumos("Loreto", _crudo(), AHORA)
        self.assertEqual((i["nivel"], i["etiqueta"]), ("sin_dato", "Sin datos"))
        self.assertEqual(i["lluvia"]["estaciones"], 0)

    def test_solo_lluvia_medida_es_aviso_atentos(self):
        i = tarea.armar_insumos("Cajamarca", _crudo(alertas=[LLUVIA]), AHORA)
        self.assertEqual((i["nivel"], i["etiqueta"], i["alertas_oficiales"]), ("aviso", "Atentos a la lluvia", 0))

    def test_solo_aviso_amarillo(self):
        i = tarea.armar_insumos("Cajamarca", _crudo(alertas=[AVISO_AMARILLO]), AHORA)
        self.assertEqual((i["nivel"], i["etiqueta"], i["alertas_oficiales"]), ("aviso", "Aviso amarillo", 1))

    def test_rio_muy_bajo_no_pasa_de_aviso(self):
        # un río en vaciante no es una crecida: aunque ANA lo publique en emergencia, el semáforo dice 'aviso'
        # (la misma regla que nivelDeAlertas en lib/nivel.js) y se sigue contando y diciendo "río muy bajo"
        self.assertEqual(tarea.nivel_de_alertas([NIVEL_BAJO]), "aviso")
        self.assertEqual(tarea.nivel_de_alertas([NIVEL_BAJO, {**NIVEL_BAJO, "nivel": "alerta"}]), "aviso")
        self.assertEqual(tarea.nivel_de_alertas([NIVEL_BAJO, AVISO]), "alerta")          # el aviso naranja sí manda
        i = tarea.armar_insumos("Loreto", _crudo(alertas=[NIVEL_BAJO]), AHORA)
        self.assertEqual((i["nivel"], i["etiqueta"], i["alertas_oficiales"], i["rios"]["muy_bajos"]),
                         ("aviso", "Río muy bajo", 1, 1))
        self.assertEqual(i["rios_bajos"][0]["nivel"], "emergencia")   # el dato de ANA se conserva tal cual
        titular, _ = tarea.titular_reglas({**i, "huella": tarea.huella(i)})
        self.assertTrue(titular.startswith("Loreto: 1 río muy bajo según ANA."), titular)
        # Loreto con aviso amarillo + 5 ríos muy bajos (el caso real del 19-10-2026): aviso, no alerta ni emergencia
        bajos = [{**NIVEL_BAJO, "referencia": f"Estación {k} (Río)", "nivel": "alerta" if k else "emergencia"} for k in range(5)]
        i = tarea.armar_insumos("Loreto", _crudo(alertas=[AVISO_LORETO, *bajos]), AHORA)
        self.assertEqual((i["nivel"], i["etiqueta"], i["alertas_oficiales"]), ("aviso", "Aviso", 6))   # como lib/nivel.js
        self.assertIn("5 ríos muy bajos según ANA", tarea.titular_reglas({**i, "huella": tarea.huella(i)})[0])
        # el modelo no recibe la palabra "emergencia" por un río bajo
        self.assertNotIn("emergencia", tarea.hechos(i).split("Río muy bajo")[1].split("\n")[0])
        self.assertIn("Río muy bajo (vaciante) según ANA (Estación 0 (Río))", tarea.hechos(i))

    def test_rio_vigilado_en_alerta_por_su_estacion(self):
        caudales = [_caudal("Mashcón", "Mashcon", "Cajamarca", 1.7, 1.5, 2.0, unidad="m")]
        i = tarea.armar_insumos("Cajamarca", _crudo(alertas=[], caudales=caudales, rios=RIOS), AHORA)
        rio = i["rio_vigilado"]
        self.assertEqual(rio["nivel"], "alerta")
        self.assertIn("pasó su nivel de alerta según ANA: lleva 1,7 m", rio["senales"][0])

    def test_enfen_atrasado_y_no_activo(self):
        viejo = {**ENFEN_NO_ACTIVO, "fecha": date(2026, 9, 1)}
        e = tarea.armar_insumos("Lima", _crudo(enfen=viejo), AHORA)["enfen"]
        self.assertEqual((e["corto"], e["atrasado"]), ("sin alerta", True))
        self.assertIsNone(tarea.armar_insumos("Lima", _crudo(enfen=None), AHORA)["enfen"])

    def test_huella_ignora_las_horas(self):
        a = tarea.armar_insumos("Cajamarca", _crudo(), AHORA)
        b = tarea.armar_insumos("Cajamarca", _crudo(), datetime(2026, 10, 14, 13, 0, tzinfo=timezone.utc))
        self.assertNotEqual(a["horas"], b["horas"])
        self.assertEqual(tarea.huella(a), tarea.huella(b))
        self.assertEqual(tarea.huella({**a, "huella": "x", "llm_descartado": "y"}), tarea.huella(a))
        self.assertNotEqual(tarea.huella(a), tarea.huella({**a, "nivel": "normal"}))


# ---------------------------------------------------------------------------------------
# Respaldo determinista
# ---------------------------------------------------------------------------------------
class TestReglas(unittest.TestCase):
    def test_cajamarca(self):
        i = _insumos()
        titular, detalle = tarea.titular_reglas(i)
        self.assertTrue(titular.startswith("Cajamarca: aviso naranja de SENAMHI por lluvias, vigente o por empezar, "
                                           "1 río en alerta según ANA y lluvia por encima de la referencia de SENAMHI "
                                           "en 1 estación."), titular)
        self.assertLessEqual(len(titular), tarea.MAX_CARACTERES)
        self.assertIn("Río Mashcón: hay aviso naranja de SENAMHI por lluvias sobre su cuenca.", detalle)
        self.assertIn("En la última hora llovió en 1 de sus 2 estaciones de SENAMHI (lo más: 12,4 mm en CHOTA GORE).", detalle)
        self.assertIn("El Niño costero: alerta según el ENFEN (comunicado).", detalle)
        self.assertIn("Fuentes (hora de Perú): avisos de SENAMHI leídos el 14 oct 06:30; caudales de ANA del 14 oct 06:00; "
                      "lluvia de SENAMHI hasta las 06:30 del 14 oct; comunicado ENFEN CO 17-2026 del 9 oct.", detalle)

    def test_normal_dice_que_se_reviso(self):
        titular, _ = tarea.titular_reglas(_insumos("Piura"))
        self.assertTrue(titular.startswith("Piura: sin avisos de SENAMHI; su río con nivel de alerta de ANA no lo pasa, "
                                           "y su estación de lluvia con dato reciente no pasa la referencia de SENAMHI."),
                        titular)

    def test_sin_datos_nunca_dice_normal(self):
        titular, detalle = tarea.titular_reglas(_insumos("Loreto", enfen=ENFEN_NO_ACTIVO))
        self.assertIn("SIMPAC no tiene aquí ríos con nivel de alerta de ANA ni estaciones de SENAMHI", titular)
        self.assertIn("ENFEN: sin alerta de El Niño ni La Niña", titular)
        for palabra in ("normal", "tranquil", "calma"):
            self.assertNotIn(palabra, titular.lower())
            self.assertNotIn(palabra, detalle.lower())

    def test_todos_los_departamentos_caben_y_pasan_la_validacion(self):
        # el titular de reglas cumple las mismas reglas que se le exigen al modelo
        for depto in tarea.ZONAS:
            i = _insumos(depto)
            titular, _ = tarea.titular_reglas(i)
            self.assertLessEqual(len(titular), tarea.MAX_CARACTERES, depto)
            self.assertEqual(tarea.validar(titular, i), titular, depto)

    def test_titular_corto_cabe_en_la_tarjeta(self):
        # <= 110 caracteres, sin El Niño ni fuentes, y pasa la misma validación que se le exige al modelo
        for depto in tarea.ZONAS:
            i = _insumos(depto)
            corto = tarea.titular_corto(i)
            self.assertLessEqual(len(corto), tarea.MAX_CORTO, (depto, corto))
            self.assertTrue(corto.startswith(depto + ":"), corto)
            self.assertNotIn("ENFEN", corto)
            self.assertNotIn("Niño", corto)
            self.assertNotIn("…", corto)
            self.assertEqual(tarea.validar(corto, i), corto, depto)
        # con las tres partes mide 131: se suelta la de menor nivel (la lluvia medida, que no es aviso oficial)
        self.assertEqual(tarea.titular_corto(_insumos()),
                         "Cajamarca: aviso naranja de SENAMHI por lluvias y 1 río en alerta según ANA.")
        self.assertEqual(tarea.titular_corto(_insumos(alertas=[AVISO, LLUVIA])),
                         "Cajamarca: aviso naranja de SENAMHI por lluvias y lluvia sobre la referencia de SENAMHI en 1 estación.")
        self.assertEqual(tarea.titular_corto(_insumos("Piura")),
                         "Piura: sin avisos de SENAMHI; 1 río de ANA y 1 estación de lluvia sin pasar su nivel.")
        self.assertEqual(tarea.titular_corto(_insumos("Loreto")),
                         "Loreto: sin avisos de SENAMHI; SIMPAC no tiene aquí ríos ni estaciones de lluvia que pueda revisar.")
        for palabra in ("normal", "tranquil"):
            self.assertNotIn(palabra, tarea.titular_corto(_insumos("Loreto")).lower())
        # lo más grave primero y, si no cabe, se quitan las partes de menor nivel desde el final
        muchos = [{**AVISO, "referencia": f"SENAMHI aviso {k}"} for k in range(3)]
        rios = [{**CAUDAL_ALERTA, "referencia": f"Río {k}", "nivel": "emergencia"} for k in range(2)]
        bajos = [{**NIVEL_BAJO, "zona": "Cajamarca", "referencia": f"Bajo {k}"} for k in range(4)]
        i = _insumos(alertas=[*muchos, *rios, *bajos, LLUVIA])
        corto = tarea.titular_corto(i)
        self.assertLessEqual(len(corto), tarea.MAX_CORTO)
        self.assertEqual(corto, "Cajamarca: 2 ríos en emergencia según ANA y 3 avisos de SENAMHI por lluvias (el más alto, naranja).")
        # el nombre más largo con los dos conteos sigue cabiendo
        largo = _insumos("Madre de Dios", alertas=[], caudales=[_caudal(f"E{k}", f"R{k}", "MADRE DE DIOS", 1.0, 10.0, 20.0) for k in range(12)],
                         lluvia=[_lluvia(f"L{k}", "MADRE DE DIOS", 0.0) for k in range(25)])
        self.assertEqual(tarea.titular_corto(largo), "Madre de Dios: sin avisos de SENAMHI; 12 ríos de ANA y 25 estaciones "
                                                     "de lluvia sin pasar su nivel.")

    def test_recorta_frases_opcionales_antes_que_la_principal(self):
        i = _insumos()
        with mock.patch.object(tarea, "MAX_CARACTERES", 160):
            titular, _ = tarea.titular_reglas(i)
        self.assertLessEqual(len(titular), 160)
        self.assertTrue(titular.startswith("Cajamarca: aviso naranja"))
        self.assertNotIn("ENFEN", titular)


# ---------------------------------------------------------------------------------------
# Pedido al modelo y validación de su texto
# ---------------------------------------------------------------------------------------
class TestPedido(unittest.TestCase):
    def test_cuerpo_con_las_cifras_fijadas(self):
        i = _insumos()
        cuerpo = tarea.cuerpo_pedido(i, MODELO)
        self.assertEqual((cuerpo["model"], cuerpo["max_tokens"], cuerpo["temperature"]), (MODELO, 200, 0))
        self.assertEqual([m["role"] for m in cuerpo["messages"]], ["user"])
        hechos = cuerpo["messages"][0]["content"]
        for linea in ("Departamento: Cajamarca", "Nivel general calculado por SIMPAC: alerta (rótulo: Alerta)",
                      "Alertas y avisos oficiales vigentes: 2", "Aviso de SENAMHI (SENAMHI aviso 377), color naranja",
                      "Río que pasó su nivel de alerta según ANA (Chilete (Jequetepeque))",
                      "máximo 12,4 mm en CHOTA GORE", "Río vigilado Río Mashcón: nivel atentos",
                      "ENFEN: Alerta de El Niño Costero", "Titular de referencia escrito por reglas"):
            self.assertIn(linea, hechos)
        self.assertIn("no calcules", cuerpo["system"])
        self.assertIn("240 caracteres", cuerpo["system"])

    def test_pedido_http(self):
        api = _Api()
        texto = tarea.pedir_llm(_insumos(), "sk-prueba", MODELO, abrir=api)
        self.assertEqual(texto, "Cajamarca: SIMPAC revisó las fuentes oficiales de hoy.")
        [(pedido, cuerpo, timeout)] = api.pedidos
        self.assertEqual((pedido.full_url, pedido.get_method(), timeout), (tarea.API_URL, "POST", tarea.TIMEOUT_S))
        cabeceras = {k.lower(): v for k, v in pedido.header_items()}
        self.assertEqual(cabeceras["x-api-key"], "sk-prueba")
        self.assertEqual(cabeceras["anthropic-version"], "2023-06-01")
        self.assertEqual(cabeceras["content-type"], "application/json")
        self.assertEqual(cuerpo["model"], MODELO)

    def test_error_http_sale_como_runtimeerror(self):
        with self.assertRaises(RuntimeError) as ctx:
            tarea.pedir_llm(_insumos(), "sk", MODELO, abrir=_Api(falla=_http_error(429)))
        self.assertIn("HTTP 429", str(ctx.exception))
        self.assertIn("rate_limit_error", str(ctx.exception))

    def test_respuesta_cortada_o_vacia(self):
        with self.assertRaises(tarea.RespuestaInvalida):
            tarea.texto_de_respuesta(_ok("Cajamarca: ...", stop_reason="max_tokens"))
        with self.assertRaises(tarea.RespuestaInvalida):
            tarea.texto_de_respuesta({**_ok(""), "content": []})
        self.assertEqual(tarea.texto_de_respuesta(_ok(" Cajamarca: x ")), " Cajamarca: x ")


class TestValidar(unittest.TestCase):
    BUENO = ("Cajamarca: aviso naranja de SENAMHI por lluvias y el río Jequetepeque pasó su nivel de alerta según ANA "
             "(80 m³/s). El Niño costero: alerta según el ENFEN.")

    def rechaza(self, texto, i=None, motivo=""):
        with self.assertRaises(tarea.RespuestaInvalida) as ctx:
            tarea.validar(texto, i or _insumos())
        self.assertIn(motivo, str(ctx.exception))

    def test_acepta_y_limpia(self):
        self.assertEqual(tarea.validar(f"  “{self.BUENO}”\n", _insumos()), self.BUENO)

    def test_largo_url_emoji_y_formato(self):
        self.rechaza(self.BUENO + " x" * 100, motivo="caracteres")
        self.rechaza("Cajamarca: aviso naranja. Más en https://senamhi.gob.pe", motivo="URL")
        self.rechaza("Cajamarca: aviso naranja. Más en senamhi.gob.pe", motivo="URL")
        self.rechaza("Cajamarca: aviso naranja de SENAMHI \U0001F327", motivo="emojis")
        self.rechaza("**Cajamarca**: aviso naranja", motivo="emojis")
        self.rechaza("", motivo="vacío")

    def test_empieza_con_el_departamento(self):
        self.rechaza("Hoy en Cajamarca hay aviso naranja de SENAMHI.", motivo="departamento")
        # con o sin tilde, da igual
        tarea.validar("Ancash: aviso naranja de SENAMHI.", _insumos("Áncash", alertas=[{**AVISO, "zona": "Áncash"}]))

    def test_cifras_solo_de_los_insumos(self):
        self.rechaza("Cajamarca: aviso naranja de SENAMHI; cayeron 95 mm en Chota.", motivo="95")
        self.rechaza("Cajamarca: el río Jequetepeque lleva 80,5 m³/s según ANA.", motivo="80.5")
        # las que sí están: 80, 70, 12,4 (del detalle y los valores), 377, el año del comunicado
        tarea.validar("Cajamarca: aviso naranja 377 de SENAMHI; el Jequetepeque lleva 80 m³/s (alerta: 70). "
                      "En Chota GORE llovió 12,4 mm.", _insumos())
        # la huella (hexadecimal) no cuenta como cifra permitida
        i = _insumos()
        i["huella"] = "99887766aabbccdd"
        self.rechaza("Cajamarca: aviso naranja de SENAMHI; 99 avisos.", i, motivo="99")

    def test_no_afirma_mas_peligro_que_las_fuentes(self):
        self.rechaza("Cajamarca: emergencia por lluvias de SENAMHI.", motivo="grave")
        self.rechaza("Cajamarca: el río Jequetepeque se desbordó según ANA.", motivo="grave")
        self.rechaza("Cajamarca: inundaciones en Chota.", motivo="grave")
        # con un río en emergencia, sí puede decirlo
        em = _insumos(alertas=[{**CAUDAL_ALERTA, "nivel": "emergencia"}])
        tarea.validar("Cajamarca: el río Jequetepeque pasó su nivel de emergencia según ANA (80 m³/s).", em)
        # sin ninguna alerta no habla de peligro ni riesgo
        self.rechaza("Piura: riesgo de lluvias.", _insumos("Piura"), motivo="peligro")

    def test_sin_datos_no_dice_normal(self):
        i = _insumos("Loreto", enfen=ENFEN_NO_ACTIVO)
        self.rechaza("Loreto: todo normal.", i, motivo="normal")
        self.rechaza("Loreto: sin alertas.", i, motivo="sin alertas")
        self.rechaza("Loreto: tranquilo según SENAMHI.", i, motivo="tranquil")
        # el estado del ENFEN no es una afirmación sobre la zona
        tarea.validar("Loreto: SIMPAC no tiene aquí ríos ni estaciones que revisar. ENFEN: sin alerta de El Niño ni La Niña.", i)

    def test_con_alertas_no_dice_que_no_hay(self):
        self.rechaza("Cajamarca: sin alertas de ANA; aviso naranja de SENAMHI.", motivo="sí los hay")
        self.rechaza("Cajamarca: sin avisos de SENAMHI.", motivo="sí los hay")
        tarea.validar("Cajamarca: aviso naranja de SENAMHI por lluvias. ENFEN: sin alerta de El Niño ni La Niña.",
                      _insumos(enfen=ENFEN_NO_ACTIVO))


# ---------------------------------------------------------------------------------------
# Qué se escribe para un departamento
# ---------------------------------------------------------------------------------------
class TestRedactar(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.ERROR)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.i = tarea.armar_insumos("Cajamarca", _crudo(), AHORA)
        self.h = tarea.huella(self.i)

    def redactar(self, previo=None, clave="sk", api=None, estado=None):
        self.api = api or _Api()
        self.estado = estado or _estado()
        return tarea.redactar(self.i, previo, clave, MODELO, self.estado, abrir=self.api)

    def test_sin_clave_sale_por_reglas(self):
        r = self.redactar(clave="")
        self.assertEqual((r["origen"], r["modelo"], r["nivel"]), ("reglas", None, "alerta"))
        self.assertTrue(r["titular"].startswith("Cajamarca: aviso naranja"))
        self.assertEqual(r["titular_corto"], tarea.titular_corto(self.i))
        self.assertEqual(json.loads(r["insumos"])["huella"], self.h)
        self.assertEqual(self.api.pedidos, [])

    def test_con_clave_y_cambio_redacta_el_modelo(self):
        r = self.redactar()
        self.assertEqual((r["origen"], r["modelo"], r["titular"]),
                         ("llm", MODELO, "Cajamarca: SIMPAC revisó las fuentes oficiales de hoy."))
        self.assertTrue(r["titular_corto"].startswith("Cajamarca: aviso naranja"))   # el corto siempre es por reglas
        self.assertEqual(len(self.api.pedidos), 1)
        self.assertEqual(self.estado["fallas_seguidas"], 0)

    def test_texto_invalido_se_descarta_y_no_se_repite(self):
        api = _Api(redactar=lambda d: f"{d}: cayeron 95 mm; más en https://x.pe")
        r = self.redactar(api=api)
        self.assertEqual((r["origen"], r["modelo"]), ("reglas", None))
        self.assertEqual([d["departamento"] for d in self.estado["descartados"]], ["Cajamarca"])
        insumos = json.loads(r["insumos"])
        self.assertIn("URL", insumos["llm_descartado"])
        self.assertEqual(insumos["huella"], self.h)
        # la corrida siguiente, con los mismos insumos, no vuelve a pedir (temperature 0: saldría igual)
        previo = {"departamento": "Cajamarca", "origen": "reglas", "huella": self.h, "llm_descartado": insumos["llm_descartado"]}
        r2 = self.redactar(previo=previo)
        self.assertTrue(r2.get("sin_cambio"))
        self.assertEqual(self.api.pedidos, [])

    def test_api_caida_con_cambio_escribe_reglas(self):
        r = self.redactar(api=_Api(falla=_http_error(500)))
        self.assertEqual(r["origen"], "reglas")
        self.assertNotIn("llm_descartado", json.loads(r["insumos"]))
        self.assertEqual(self.estado["fallas_seguidas"], 1)
        self.assertIn("HTTP 500", self.estado["avisos"][0])

    def test_api_caida_sin_cambio_conserva_el_anterior(self):
        previo = {"departamento": "Cajamarca", "origen": "reglas", "huella": self.h, "llm_descartado": None}
        r = self.redactar(previo=previo, api=_Api(falla=OSError("sin red")))
        self.assertIsNone(r)
        self.assertEqual(self.estado["fallas_seguidas"], 1)

    def test_sin_cambio_con_titular_del_modelo_no_llama(self):
        previo = {"departamento": "Cajamarca", "origen": "llm", "huella": self.h, "llm_descartado": None}
        r = self.redactar(previo=previo)
        self.assertEqual(set(r), {"departamento", "titular_corto", "detalle", "insumos", "sin_cambio"})
        self.assertLessEqual(len(r["titular_corto"]), tarea.MAX_CORTO)
        self.assertEqual(self.api.pedidos, [])

    def test_sin_cambio_pero_por_reglas_reintenta_al_tener_clave(self):
        # el titular guardado salió por reglas (no había clave o la API falló) y nada cambió: se intenta
        previo = {"departamento": "Cajamarca", "origen": "reglas", "huella": self.h, "llm_descartado": None}
        r = self.redactar(previo=previo)
        self.assertEqual(r["origen"], "llm")
        self.assertEqual(len(self.api.pedidos), 1)

    def test_tras_tres_fallas_seguidas_o_pasado_el_plazo_no_insiste(self):
        estado = {**_estado(), "fallas_seguidas": tarea.MAX_FALLAS_SEGUIDAS}
        r = self.redactar(estado=estado)
        self.assertEqual(r["origen"], "reglas")
        self.assertEqual(self.api.pedidos, [])
        with mock.patch.object(tarea, "PLAZO_S", -1):
            r = self.redactar()
        self.assertEqual(r["origen"], "reglas")
        self.assertEqual(self.api.pedidos, [])


# ---------------------------------------------------------------------------------------
# La tarea completa con la BD simulada
# ---------------------------------------------------------------------------------------
class TestTarea(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.ERROR)
        self.addCleanup(logging.disable, logging.NOTSET)

    def correr(self, conn=None, clave="", api=None):
        conn = conn or _Conexion()
        conn.registro.clear()
        self.api = api or _Api()

        @contextmanager
        def falso_conectar():
            yield conn

        ajustes = types.SimpleNamespace(llm_key=clave, llm_modelo=MODELO)
        with mock.patch.object(tarea, "conectar", falso_conectar), mock.patch.object(tarea, "ajustes", lambda: ajustes):
            devuelto = tarea.actualizar(AHORA, abrir=self.api)
        [(servicio, datos)] = conn.params(SQL_LATIDO)      # el latido se escribe siempre
        self.assertEqual(servicio, "titular")
        resumen = json.loads(datos)
        self.assertEqual(resumen, devuelto)
        return conn, resumen

    def test_sin_migracion_solo_latido(self):
        conn, resumen = self.correr(_Conexion(migrada=False))
        self.assertEqual(resumen["fallas"], ["migracion"])
        self.assertEqual(conn.params(tarea.SQL_TITULAR), [])

    def test_primera_corrida_por_reglas(self):
        conn, resumen = self.correr()
        [filas] = conn.params(tarea.SQL_TITULAR)
        self.assertEqual(len(filas), 25)
        self.assertEqual({f["departamento"] for f in filas}, set(tarea.ZONAS))
        for f in filas:
            self.assertEqual((f["origen"], f["modelo"]), ("reglas", None))
            self.assertLessEqual(len(f["titular"]), tarea.MAX_CARACTERES)
            self.assertLessEqual(len(f["titular_corto"]), tarea.MAX_CORTO)
            self.assertIn(f["nivel"], ("normal", "aviso", "alerta", "emergencia", "sin_dato"))
            self.assertTrue(f["titular"].startswith(f["departamento"] + ":"), f["titular"])
            self.assertIn("huella", json.loads(f["insumos"]))
        por = {f["departamento"]: f for f in filas}
        self.assertEqual((por["Cajamarca"]["nivel"], por["Piura"]["nivel"], por["Loreto"]["nivel"], por["Callao"]["nivel"]),
                         ("alerta", "normal", "sin_dato", "sin_dato"))
        self.assertEqual({k: resumen[k] for k in ("departamentos", "llm", "reglas", "sin_cambio", "conservados", "modelo", "fallas")},
                         {"departamentos": 25, "llm": 0, "reglas": 25, "sin_cambio": 0, "conservados": 0, "modelo": None,
                          "fallas": []})
        self.assertIn("sin clave de API (SIMPAC_LLM_KEY): titulares por reglas", resumen["avisos"])
        # las escrituras van después del candado y en la misma conexión que el latido
        sentencias = [s for s, _ in conn.registro]
        self.assertLess(sentencias.index(tarea.SQL_CANDADO), sentencias.index(tarea.SQL_TITULAR))
        self.assertEqual(sentencias[-1], SQL_LATIDO)

    def test_segunda_corrida_sin_cambios_conserva_los_titulares(self):
        conn, _ = self.correr()
        [filas] = conn.params(tarea.SQL_TITULAR)
        previos = {f["departamento"]: {"departamento": f["departamento"], "titular": f["titular"], "origen": f["origen"],
                                       "huella": json.loads(f["insumos"])["huella"], "llm_descartado": None} for f in filas}
        conn2 = _Conexion(_crudo(previos=previos))
        _, resumen = self.correr(conn2)
        self.assertEqual(conn2.params(tarea.SQL_TITULAR), [])
        [filas2] = conn2.params(tarea.SQL_SIN_CAMBIO)
        self.assertEqual(len(filas2), 25)
        self.assertTrue(all(len(f["titular_corto"]) <= tarea.MAX_CORTO for f in filas2))   # también sin cambios
        self.assertEqual((resumen["reglas"], resumen["sin_cambio"]), (0, 25))

    def test_sql_escribe_el_corto(self):
        self.assertIn("titular_corto = excluded.titular_corto", tarea.SQL_TITULAR)
        self.assertIn("titular_corto = %(titular_corto)s", tarea.SQL_SIN_CAMBIO)

    def test_con_clave_redacta_el_modelo_una_vez_por_departamento(self):
        conn, resumen = self.correr(clave="sk")
        self.assertEqual(len(self.api.pedidos), 25)
        [filas] = conn.params(tarea.SQL_TITULAR)
        self.assertTrue(all(f["origen"] == "llm" and f["modelo"] == MODELO for f in filas))
        self.assertEqual((resumen["llm"], resumen["reglas"], resumen["modelo"], resumen["fallas"]), (25, 0, MODELO, []))
        # cada pedido lleva las cifras del departamento y temperature 0
        for _, cuerpo, _ in self.api.pedidos:
            self.assertEqual((cuerpo["temperature"], cuerpo["max_tokens"]), (0, 200))

    def test_api_caida_no_borra_nada(self):
        conn, _ = self.correr()
        [filas] = conn.params(tarea.SQL_TITULAR)
        previos = {f["departamento"]: {"departamento": f["departamento"], "titular": f["titular"], "origen": "llm",
                                       "huella": json.loads(f["insumos"])["huella"], "llm_descartado": None} for f in filas}
        # Cajamarca cambió (se fue el aviso); el resto sigue igual y con titular del modelo
        conn2 = _Conexion(_crudo(alertas=[CAUDAL_ALERTA, LLUVIA], previos=previos))
        _, resumen = self.correr(conn2, clave="sk", api=_Api(falla=_http_error(529)))
        [nuevos] = conn2.params(tarea.SQL_TITULAR)
        self.assertEqual([(f["departamento"], f["origen"]) for f in nuevos], [("Cajamarca", "reglas")])
        [iguales] = conn2.params(tarea.SQL_SIN_CAMBIO)
        self.assertEqual(len(iguales), 24)
        self.assertEqual((resumen["reglas"], resumen["sin_cambio"], resumen["conservados"], resumen["fallas"]),
                         (1, 24, 0, ["llm"]))
        self.assertTrue(any("HTTP 529" in a for a in resumen["avisos"]))

    def test_descartados_en_el_latido(self):
        api = _Api(redactar=lambda d: f"{d}: emergencia total, cayeron 999 mm.")
        conn, resumen = self.correr(clave="sk", api=api)
        [filas] = conn.params(tarea.SQL_TITULAR)
        self.assertTrue(all(f["origen"] == "reglas" for f in filas))
        self.assertEqual(len(resumen["descartados"]), 25)
        self.assertEqual(resumen["descartados"][0]["departamento"], "Amazonas")
        self.assertEqual(resumen["fallas"], [])   # descartar no es una falla de la API


if __name__ == "__main__":
    unittest.main()
