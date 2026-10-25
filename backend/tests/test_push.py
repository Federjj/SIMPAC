"""
Tarea 'push' (backend/ingesta/push.py): la decisión de enviar o no con historias de niveles, el
armado del mensaje y los temas, el token OAuth2 (con la firma simulada), los errores HTTP de FCM
simulados y la corrida completa con la BD simulada. Sin red, sin psycopg ni google-auth: solo
librería estándar. Nada se envía nunca sin credenciales.
"""
import base64
import io
import json
import logging
import re
import types
import unittest
import urllib.error
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest import mock

from backend.ingesta import push as tarea
from backend.ingesta.guardar import SQL_LATIDO

AHORA = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)      # 07:00 del 20-10 en Lima
GENERADO = datetime(2026, 10, 20, 11, 30, tzinfo=timezone.utc)
INFO = {"type": "service_account", "project_id": "appsimpac", "client_email": "fcm@appsimpac.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\nSIMULADA\n-----END PRIVATE KEY-----\n",
        "token_uri": "https://oauth2.googleapis.com/token"}
TOKEN_OK = {"access_token": "ya29.simulado", "expires_in": 3599, "token_type": "Bearer"}


def _titular(depto, nivel, corto=None, titular=None):
    return {"departamento": depto, "nivel": nivel,
            "titular_corto": corto if corto is not None else f"{depto}: 2 avisos de SENAMHI por lluvias (el más alto, naranja).",
            "titular": titular or f"{depto}: titular largo con El Niño.", "generado_en": GENERADO}


def _previo(zona, nivel, titular=None, mensaje_id=None):
    return {"zona": zona, "nivel": nivel, "titular": titular, "enviado_en": None, "mensaje_id": mensaje_id}


TITULARES = [_titular("Cajamarca", "alerta"), _titular("Piura", "emergencia"), _titular("Lima", "aviso"),
             _titular("La Libertad", "normal"), _titular("Callao", "sin_dato"), _titular("Madre de Dios", "alerta")]


class _Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Red:
    """Un urlopen de mentira: responde el token y luego FCM; anota cada pedido y puede fallar por envío."""

    def __init__(self, fallas=None, token=None):
        self.fallas = list(fallas or [])      # excepción (o None) para cada envío a FCM, en orden
        self.token = token or TOKEN_OK
        self.pedidos, self.n = [], 0

    def __call__(self, pedido, timeout=None):
        self.pedidos.append((pedido, timeout))
        if "oauth2" in pedido.full_url or pedido.full_url.endswith("/token"):
            if isinstance(self.token, Exception):
                raise self.token
            return _Respuesta(json.dumps(self.token).encode())
        self.n += 1
        falla = self.fallas.pop(0) if self.fallas else None
        if falla:
            raise falla
        return _Respuesta(json.dumps({"name": f"projects/appsimpac/messages/{self.n}"}).encode())

    def fcm(self):
        return [json.loads(p.data.decode("utf-8"))["message"] for p, _ in self.pedidos if "fcm.googleapis.com" in p.full_url]


def _http_error(codigo, cuerpo=None):
    cuerpo = cuerpo if cuerpo is not None else json.dumps({"error": {"code": codigo, "status": "UNAVAILABLE", "message": "x"}}).encode()
    return urllib.error.HTTPError("https://fcm.googleapis.com/v1/projects/appsimpac/messages:send", codigo, "simulado", {},
                                  io.BytesIO(cuerpo))


# ---------------------------------------------------------------------------------------
# BD simulada
# ---------------------------------------------------------------------------------------
def _columnas(sql):
    campos = re.search(r"select\s+(.*?)\s+from\s", sql, re.S | re.I).group(1)
    return [c.strip().split(" as ")[-1].split(".")[-1] for c in campos.split(",")]


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
        if sql in self.conn.tablas:
            self.description = [(c,) for c in _columnas(sql)]

    def fetchone(self):
        assert self.ultima == tarea.SQL_HAY_TABLA, self.ultima
        return (self.conn.migrada,)

    def fetchall(self):
        return [tuple(f.get(c) for c in _columnas(self.ultima)) for f in self.conn.tablas[self.ultima]]


class _Conexion:
    def __init__(self, titulares=TITULARES, previos=(), migrada=True):
        self.migrada, self.registro = migrada, []
        self.tablas = {tarea.SQL_TITULARES: [dict(t) for t in titulares], tarea.SQL_PREVIOS: [dict(p) for p in previos]}

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]


# ---------------------------------------------------------------------------------------
# Temas y decisión
# ---------------------------------------------------------------------------------------
class TestTemas(unittest.TestCase):
    def test_slug_del_contrato(self):
        casos = {"Cajamarca": "zona_cajamarca", "La Libertad": "zona_la_libertad", "Madre de Dios": "zona_madre_de_dios",
                 "Callao": "zona_callao", "Lima": "zona_lima", "Áncash": "zona_ancash", "San Martín": "zona_san_martin",
                 "Apurímac": "zona_apurimac", "Huánuco": "zona_huanuco", "Junín": "zona_junin"}
        for nombre, esperado in casos.items():
            self.assertEqual(tarea.tema_zona(nombre), esperado, nombre)
        self.assertTrue(all(re.fullmatch(r"[a-z_]+", tarea.tema_zona(n)) for n in casos))

    def test_condicion_une_pais_y_zona(self):
        self.assertEqual(tarea.condicion("La Libertad"), "'pais' in topics || 'zona_la_libertad' in topics")


class TestDecidir(unittest.TestCase):
    def test_sube_a_alerta_o_emergencia(self):
        for previo in (None, "normal", "aviso", "sin_dato"):
            self.assertEqual(tarea.decidir(previo, "alerta"), "alerta", previo)
            self.assertEqual(tarea.decidir(previo, "emergencia"), "alerta", previo)
        self.assertEqual(tarea.decidir("alerta", "emergencia"), "alerta")

    def test_vuelve_la_calma_solo_desde_alerta_o_emergencia(self):
        for previo in ("alerta", "emergencia"):
            self.assertEqual(tarea.decidir(previo, "normal"), "calma", previo)
            self.assertEqual(tarea.decidir(previo, "aviso"), "calma", previo)
        # por debajo de alerta nunca hay mensaje: solo se anota el nivel
        self.assertEqual(tarea.decidir("normal", "aviso"), "nivel")
        self.assertEqual(tarea.decidir("aviso", "normal"), "nivel")
        self.assertEqual(tarea.decidir(None, "aviso"), "nivel")

    def test_nunca_repite_ni_avisa_por_lo_mismo(self):
        for nivel in ("normal", "aviso", "alerta", "emergencia"):
            self.assertIsNone(tarea.decidir(nivel, nivel), nivel)
        self.assertIsNone(tarea.decidir(None, "normal"))        # línea base sin fila: nada que anotar

    def test_fuente_caida_no_es_calma(self):
        for previo in (None, "normal", "aviso", "alerta", "emergencia"):
            self.assertIsNone(tarea.decidir(previo, "sin_dato"), previo)
        self.assertIsNone(tarea.decidir("alerta", "cualquier_cosa"))

    def test_bajar_de_emergencia_a_alerta_se_anota_sin_avisar(self):
        self.assertEqual(tarea.decidir("emergencia", "alerta"), "nivel")


# ---------------------------------------------------------------------------------------
# Mensaje
# ---------------------------------------------------------------------------------------
class TestMensaje(unittest.TestCase):
    def test_alerta_segun_el_contrato(self):
        m = tarea.armar_mensaje("Cajamarca", "alerta", "Cajamarca: 2 avisos de SENAMHI.", GENERADO, "alerta")
        self.assertEqual(m["notification"], {"title": "SIMPAC: ALERTA en Cajamarca", "body": "Cajamarca: 2 avisos de SENAMHI."})
        self.assertEqual(m["data"], {"nivel": "alerta", "zona": "Cajamarca", "generado_en": "2026-10-20T11:30:00+00:00",
                                     "ruta": "/alertas"})
        self.assertTrue(all(isinstance(v, str) for v in m["data"].values()))   # FCM exige texto en data
        self.assertEqual(m["android"]["priority"], "high")
        self.assertNotIn("topic", m)
        self.assertNotIn("condition", m)

    def test_emergencia_y_calma(self):
        m = tarea.armar_mensaje("Madre de Dios", "emergencia", "x", GENERADO, "alerta")
        self.assertEqual(m["notification"]["title"], "SIMPAC: EMERGENCIA en Madre de Dios")
        c = tarea.armar_mensaje("Piura", "normal", "Piura: sin avisos de SENAMHI.", GENERADO, "calma")
        self.assertEqual(c["notification"]["title"], "SIMPAC: vuelve la calma en Piura")
        self.assertEqual((c["data"]["nivel"], c["android"]["priority"]), ("normal", "normal"))

    def test_cuerpo_prefiere_el_corto(self):
        self.assertEqual(tarea.cuerpo_mensaje(_titular("Lima", "alerta", corto="corto", titular="largo")), "corto")
        self.assertEqual(tarea.cuerpo_mensaje(_titular("Lima", "alerta", corto="", titular="largo")), "largo")
        self.assertIn("Lima", tarea.cuerpo_mensaje({"departamento": "Lima", "titular_corto": None, "titular": None}))

    def test_generado_en_sin_zona_horaria_se_toma_como_utc(self):
        m = tarea.armar_mensaje("Lima", "alerta", "x", datetime(2026, 10, 20, 11, 30), "alerta")
        self.assertEqual(m["data"]["generado_en"], "2026-10-20T11:30:00+00:00")


# ---------------------------------------------------------------------------------------
# Credenciales y token
# ---------------------------------------------------------------------------------------
class TestCredenciales(unittest.TestCase):
    def test_vacio_es_none(self):
        self.assertIsNone(tarea.cargar_credenciales(""))
        self.assertIsNone(tarea.cargar_credenciales(None))
        self.assertIsNone(tarea.cargar_credenciales("   "))

    def test_json_directo_y_base64(self):
        texto = json.dumps(INFO)
        self.assertEqual(tarea.cargar_credenciales(texto)["project_id"], "appsimpac")
        b64 = base64.b64encode(texto.encode()).decode()
        self.assertEqual(tarea.cargar_credenciales(b64)["client_email"], INFO["client_email"])

    def test_ruta_a_archivo(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "cuenta.json")
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(INFO, f)
            self.assertEqual(tarea.cargar_credenciales(ruta)["project_id"], "appsimpac")

    def test_invalidas_sin_repetir_el_valor(self):
        for valor in ("no-es-nada", "e30=", json.dumps({"project_id": "x"}), "[1]", "/ruta/que/no/existe.json"):
            with self.assertRaises(tarea.CredencialesInvalidas) as ctx:
                tarea.cargar_credenciales(valor)
            self.assertNotIn(valor, str(ctx.exception))


class TestToken(unittest.TestCase):
    def test_pide_el_token_con_el_jwt_firmado(self):
        red = _Red()
        with mock.patch.object(tarea, "_firmar", lambda info, carga: f"JWT({carga['iss']},{carga['scope']},{carga['aud']})"):
            token, vence = tarea.obtener_token(INFO, red, ahora_s=1_000_000)
        self.assertEqual((token, vence), ("ya29.simulado", 1_000_000 + 3599))
        [(pedido, timeout)] = red.pedidos
        self.assertEqual((pedido.full_url, pedido.get_method(), timeout), (INFO["token_uri"], "POST", tarea.TIMEOUT_S))
        cuerpo = dict(urllib.parse.parse_qsl(pedido.data.decode()))
        self.assertEqual(cuerpo["grant_type"], "urn:ietf:params:oauth:grant-type:jwt-bearer")
        self.assertEqual(cuerpo["assertion"], f"JWT({INFO['client_email']},{tarea.ALCANCE},{INFO['token_uri']})")

    def test_carga_del_jwt(self):
        cargas = []
        with mock.patch.object(tarea, "_firmar", lambda info, carga: cargas.append(carga) or "x"):
            tarea.obtener_token(INFO, _Red(), ahora_s=1_000_000.7)
        [carga] = cargas
        self.assertEqual(carga, {"iss": INFO["client_email"], "scope": tarea.ALCANCE, "aud": INFO["token_uri"],
                                 "iat": 1_000_000, "exp": 1_003_600})

    def test_sin_access_token_son_credenciales_invalidas(self):
        with mock.patch.object(tarea, "_firmar", lambda info, carga: "x"):
            with self.assertRaises(tarea.CredencialesInvalidas):
                tarea.obtener_token(INFO, _Red(token={"error": "invalid_grant"}))

    def test_cache_reutiliza_el_token_vigente(self):
        tarea._token_cache.update(token=None, vence=0.0, correo=None)
        red = _Red()
        with mock.patch.object(tarea, "_firmar", lambda info, carga: "x"):
            t1 = tarea.token_vigente(INFO, red)
            t2 = tarea.token_vigente(INFO, red)
        self.assertEqual((t1, t2), ("ya29.simulado", "ya29.simulado"))
        self.assertEqual(len(red.pedidos), 1)
        tarea._token_cache.update(token=None, vence=0.0, correo=None)

    def test_sin_google_auth_el_error_es_claro(self):
        import builtins
        real = builtins.__import__

        def sin_google(nombre, *a, **k):
            if nombre.startswith("google"):
                raise ImportError("No module named 'google'")
            return real(nombre, *a, **k)

        with mock.patch.object(builtins, "__import__", sin_google):
            with self.assertRaises(RuntimeError) as ctx:
                tarea._firmar(INFO, {})
        self.assertIn("google-auth", str(ctx.exception))


# ---------------------------------------------------------------------------------------
# Envío y errores HTTP
# ---------------------------------------------------------------------------------------
class TestEnviar(unittest.TestCase):
    def test_envio_correcto(self):
        red = _Red()
        mensaje = {**tarea.armar_mensaje("Cajamarca", "alerta", "x", GENERADO, "alerta"), "condition": tarea.condicion("Cajamarca")}
        mid = tarea.enviar(mensaje, "appsimpac", "ya29.simulado", red)
        self.assertEqual(mid, "projects/appsimpac/messages/1")
        [(pedido, timeout)] = red.pedidos
        self.assertEqual(pedido.full_url, "https://fcm.googleapis.com/v1/projects/appsimpac/messages:send")
        self.assertEqual(pedido.get_header("Authorization"), "Bearer ya29.simulado")
        self.assertEqual(json.loads(pedido.data.decode("utf-8")), {"message": mensaje})
        self.assertEqual(timeout, tarea.TIMEOUT_S)

    def test_401_y_403_son_credenciales(self):
        for codigo in (401, 403):
            with self.assertRaises(tarea.CredencialesInvalidas) as ctx:
                tarea.enviar({}, "appsimpac", "t", _Red(fallas=[_http_error(codigo)]))
            self.assertIn(f"HTTP {codigo}", str(ctx.exception))
            self.assertNotIn("Bearer", str(ctx.exception))

    def test_otros_errores_son_falla_de_envio(self):
        for falla in (_http_error(500), _http_error(429), _http_error(400, b"no json"), urllib.error.URLError("caído"),
                      TimeoutError("timed out")):
            with self.assertRaises(tarea.FallaEnvio):
                tarea.enviar({}, "appsimpac", "t", _Red(fallas=[falla]))

    def test_detalle_http_trae_el_status_de_google(self):
        e = _http_error(404, json.dumps({"error": {"status": "NOT_FOUND", "message": "Requested entity was not found."}}).encode())
        self.assertEqual(tarea._detalle_http(e), "HTTP 404 NOT_FOUND")


# ---------------------------------------------------------------------------------------
# La tarea completa con la BD simulada
# ---------------------------------------------------------------------------------------
class TestTarea(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.ERROR)
        self.addCleanup(logging.disable, logging.NOTSET)
        tarea._token_cache.update(token=None, vence=0.0, correo=None)
        self.addCleanup(tarea._token_cache.update, token=None, vence=0.0, correo=None)

    def correr(self, conn=None, credenciales="", red=None, proyecto=""):
        conn = conn or _Conexion()
        self.red = red or _Red()

        @contextmanager
        def falso_conectar():
            yield conn

        ajustes = types.SimpleNamespace(credenciales=credenciales, proyecto=proyecto)
        with mock.patch.object(tarea, "conectar", falso_conectar), mock.patch.object(tarea, "ajustes_push", lambda: ajustes), \
                mock.patch.object(tarea, "_firmar", lambda info, carga: "jwt-simulado"):
            devuelto = tarea.actualizar(AHORA, abrir=self.red)
        [(servicio, datos)] = conn.params(SQL_LATIDO)       # el latido se escribe siempre, y una sola vez
        self.assertEqual(servicio, "push")
        resumen = json.loads(datos)
        self.assertEqual(resumen, devuelto)
        return conn, resumen

    def test_sin_credenciales_no_envia_nada_ni_toca_el_estado(self):
        conn, resumen = self.correr()
        self.assertEqual(self.red.pedidos, [])
        self.assertEqual(conn.params(tarea.SQL_ENVIADO) + conn.params(tarea.SQL_NIVEL), [])
        self.assertEqual(resumen["fallas"], [])
        self.assertIn(tarea.AVISO_SIN_CREDENCIALES, resumen["avisos"])
        self.assertEqual((resumen["zonas"], resumen["enviados"], resumen["credenciales"], resumen["proyecto"]),
                         (6, 0, False, None))
        # lo que habría mandado queda a la vista: las dos alertas y la emergencia, nunca el aviso de Lima
        self.assertEqual(resumen["pendientes"], [{"zona": "Cajamarca", "nivel": "alerta", "tipo": "alerta"},
                                                 {"zona": "Piura", "nivel": "emergencia", "tipo": "alerta"},
                                                 {"zona": "Madre de Dios", "nivel": "alerta", "tipo": "alerta"}])

    def test_credenciales_ilegibles_tampoco_envian(self):
        conn, resumen = self.correr(credenciales="esto-no-es-base64-ni-json")
        self.assertEqual(self.red.pedidos, [])
        self.assertEqual(resumen["fallas"], ["credenciales"])
        self.assertTrue(resumen["avisos"][0].startswith("FIREBASE_CREDENCIALES ilegible"))
        self.assertNotIn("esto-no-es-base64", json.dumps(resumen))

    def test_sin_migracion_solo_latido(self):
        conn, resumen = self.correr(_Conexion(migrada=False), credenciales=json.dumps(INFO))
        self.assertEqual(resumen["fallas"], ["migracion"])
        self.assertEqual(self.red.pedidos, [])
        self.assertEqual([s for s, _ in conn.registro], [tarea.SQL_HAY_TABLA, SQL_LATIDO])

    def test_primera_corrida_avisa_las_alertas_vigentes_una_vez(self):
        conn, resumen = self.correr(credenciales=json.dumps(INFO))
        enviados = self.red.fcm()
        self.assertEqual([m["notification"]["title"] for m in enviados],
                         ["SIMPAC: ALERTA en Cajamarca", "SIMPAC: EMERGENCIA en Piura", "SIMPAC: ALERTA en Madre de Dios"])
        self.assertEqual(enviados[0]["notification"]["body"], TITULARES[0]["titular_corto"])
        self.assertEqual(enviados[0]["condition"], "'pais' in topics || 'zona_cajamarca' in topics")
        self.assertEqual(enviados[0]["data"], {"nivel": "alerta", "zona": "Cajamarca", "generado_en": "2026-10-20T11:30:00+00:00",
                                               "ruta": "/alertas"})
        self.assertNotIn("topic", enviados[0])
        # un solo token para los tres envíos
        self.assertEqual(len(self.red.pedidos), 4)
        # el estado: las tres enviadas con su id, y Lima (aviso) anotada sin mensaje; nada para normal ni sin_dato
        escritos = conn.params(tarea.SQL_ENVIADO)
        self.assertEqual([(e["zona"], e["nivel"], e["mensaje_id"]) for e in escritos],
                         [("Cajamarca", "alerta", "projects/appsimpac/messages/1"), ("Piura", "emergencia", "projects/appsimpac/messages/2"),
                          ("Madre de Dios", "alerta", "projects/appsimpac/messages/3")])
        self.assertEqual(escritos[0]["titular"], TITULARES[0]["titular_corto"])
        self.assertEqual(conn.params(tarea.SQL_NIVEL), [{"zona": "Lima", "nivel": "aviso"}])
        self.assertEqual({k: resumen[k] for k in ("zonas", "enviados", "temas", "anotados", "pendientes", "proyecto", "credenciales", "fallas")},
                         {"zonas": 6, "enviados": 3, "temas": ["zona_cajamarca", "zona_piura", "zona_madre_de_dios"], "anotados": 1,
                          "pendientes": [], "proyecto": "appsimpac", "credenciales": True, "fallas": []})
        self.assertEqual(resumen["mensajes"][0], {"zona": "Cajamarca", "nivel": "alerta", "tema": "zona_cajamarca", "tipo": "alerta",
                                                  "mensaje_id": "projects/appsimpac/messages/1"})
        # todo dentro del candado y el latido al final, en la misma conexión
        sentencias = [s for s, _ in conn.registro]
        self.assertLess(sentencias.index(tarea.SQL_CANDADO), sentencias.index(tarea.SQL_TITULARES))
        self.assertEqual(sentencias[-1], SQL_LATIDO)
        # ni la clave ni el token aparecen en el latido
        texto = json.dumps(resumen)
        self.assertNotIn("SIMULADA", texto)
        self.assertNotIn("ya29", texto)

    def test_segunda_corrida_igual_no_repite_nada(self):
        previos = [_previo("Cajamarca", "alerta"), _previo("Piura", "emergencia"), _previo("Madre de Dios", "alerta"),
                   _previo("Lima", "aviso")]
        conn, resumen = self.correr(_Conexion(previos=previos), credenciales=json.dumps(INFO))
        self.assertEqual(self.red.pedidos, [])
        self.assertEqual(conn.params(tarea.SQL_ENVIADO) + conn.params(tarea.SQL_NIVEL), [])
        self.assertEqual((resumen["enviados"], resumen["anotados"], resumen["pendientes"], resumen["fallas"]), (0, 0, [], []))

    def test_el_texto_del_titular_cambia_pero_el_nivel_no(self):
        previos = [_previo("Cajamarca", "alerta", titular="otro texto de antes")]
        conn, resumen = self.correr(_Conexion(titulares=[_titular("Cajamarca", "alerta")], previos=previos), credenciales=json.dumps(INFO))
        self.assertEqual(self.red.pedidos, [])
        self.assertEqual(resumen["enviados"], 0)

    def test_vuelve_la_calma_y_de_alerta_a_emergencia(self):
        titulares = [_titular("Cajamarca", "normal", corto="Cajamarca: sin avisos de SENAMHI; 3 ríos de ANA sin pasar su nivel."),
                     _titular("Piura", "emergencia"), _titular("Lima", "aviso"), _titular("Tumbes", "alerta")]
        previos = [_previo("Cajamarca", "alerta"), _previo("Piura", "alerta"), _previo("Lima", "alerta"), _previo("Tumbes", "emergencia")]
        conn, resumen = self.correr(_Conexion(titulares=titulares, previos=previos), credenciales=json.dumps(INFO))
        enviados = self.red.fcm()
        self.assertEqual([m["notification"]["title"] for m in enviados],
                         ["SIMPAC: vuelve la calma en Cajamarca", "SIMPAC: EMERGENCIA en Piura", "SIMPAC: vuelve la calma en Lima"])
        self.assertEqual(enviados[0]["notification"]["body"], titulares[0]["titular_corto"])
        self.assertEqual(enviados[0]["data"]["nivel"], "normal")
        self.assertEqual(enviados[2]["data"]["nivel"], "aviso")
        # Tumbes bajó de emergencia a alerta: se anota, no se avisa
        self.assertEqual(conn.params(tarea.SQL_NIVEL), [{"zona": "Tumbes", "nivel": "alerta"}])
        self.assertEqual([m["tipo"] for m in resumen["mensajes"]], ["calma", "alerta", "calma"])

    def test_fuente_caida_no_borra_ni_avisa(self):
        conn, resumen = self.correr(_Conexion(titulares=[_titular("Cajamarca", "sin_dato")], previos=[_previo("Cajamarca", "alerta")]),
                                    credenciales=json.dumps(INFO))
        self.assertEqual(self.red.pedidos, [])
        self.assertEqual(conn.params(tarea.SQL_ENVIADO) + conn.params(tarea.SQL_NIVEL), [])

    def test_fcm_rechaza_las_credenciales_y_se_detiene(self):
        red = _Red(fallas=[_http_error(401, json.dumps({"error": {"status": "UNAUTHENTICATED"}}).encode())])
        conn, resumen = self.correr(credenciales=json.dumps(INFO), red=red)
        self.assertEqual(len(red.fcm()), 1)                  # no insistió con Piura ni Madre de Dios
        self.assertEqual(resumen["fallas"], ["credenciales"])
        self.assertIn("Cajamarca: FCM rechazó las credenciales (HTTP 401 UNAUTHENTICATED)", resumen["avisos"])
        self.assertEqual(conn.params(tarea.SQL_ENVIADO), [])
        self.assertEqual([p["zona"] for p in resumen["pendientes"]], ["Cajamarca", "Piura", "Madre de Dios"])
        self.assertEqual(conn.params(tarea.SQL_NIVEL), [{"zona": "Lima", "nivel": "aviso"}])   # lo anotado no depende de FCM

    def test_falla_de_fcm_en_una_zona_sigue_con_las_otras_y_no_anota_la_fallida(self):
        red = _Red(fallas=[_http_error(503)])
        conn, resumen = self.correr(credenciales=json.dumps(INFO), red=red)
        self.assertEqual(len(red.fcm()), 3)
        self.assertEqual([e["zona"] for e in conn.params(tarea.SQL_ENVIADO)], ["Piura", "Madre de Dios"])
        self.assertEqual(resumen["fallas"], ["envio"])
        self.assertEqual(resumen["pendientes"], [{"zona": "Cajamarca", "nivel": "alerta", "tipo": "alerta"}])
        self.assertEqual((resumen["enviados"], resumen["temas"]), (2, ["zona_piura", "zona_madre_de_dios"]))
        self.assertIn("Cajamarca: HTTP 503 UNAVAILABLE", resumen["avisos"])

    def test_tras_tres_fallas_seguidas_no_insiste(self):
        titulares = [_titular(z, "alerta") for z in ("Cajamarca", "Piura", "Lima", "Tumbes", "Ica")]
        red = _Red(fallas=[urllib.error.URLError("caído")] * 5)
        conn, resumen = self.correr(_Conexion(titulares=titulares), credenciales=json.dumps(INFO), red=red)
        self.assertEqual(len(red.fcm()), tarea.MAX_FALLAS_SEGUIDAS)
        self.assertEqual(len(resumen["pendientes"]), 5)
        self.assertTrue(any("3 veces seguidas" in a for a in resumen["avisos"]))

    def test_no_se_obtiene_el_token(self):
        red = _Red(token=urllib.error.URLError("sin red"))
        conn, resumen = self.correr(credenciales=json.dumps(INFO), red=red)
        self.assertEqual(red.fcm(), [])
        self.assertEqual(resumen["fallas"], ["token"])
        self.assertEqual(conn.params(tarea.SQL_ENVIADO), [])
        self.assertEqual(len(resumen["pendientes"]), 3)

    def test_token_rechazado_son_credenciales(self):
        red = _Red(token={"error": "invalid_grant", "error_description": "Invalid JWT Signature."})
        conn, resumen = self.correr(credenciales=json.dumps(INFO), red=red)
        self.assertEqual(resumen["fallas"], ["credenciales"])
        self.assertEqual(red.fcm(), [])

    def test_pasado_el_plazo_deja_el_resto_para_la_proxima(self):
        with mock.patch.object(tarea, "PLAZO_S", -1):
            conn, resumen = self.correr(credenciales=json.dumps(INFO))
        self.assertEqual(self.red.pedidos, [])
        self.assertEqual(len(resumen["pendientes"]), 3)
        self.assertTrue(any("plazo" in a for a in resumen["avisos"]))
        self.assertEqual(resumen["fallas"], [])

    def test_proyecto_de_la_variable_manda_sobre_el_json(self):
        conn, resumen = self.correr(credenciales=json.dumps(INFO), proyecto="otro-proyecto")
        self.assertEqual(resumen["proyecto"], "otro-proyecto")
        self.assertTrue(all("/projects/otro-proyecto/" in p.full_url for p, _ in self.red.pedidos if "fcm." in p.full_url))

    def test_titulares_vacios(self):
        conn, resumen = self.correr(_Conexion(titulares=[]), credenciales=json.dumps(INFO))
        self.assertEqual((resumen["zonas"], resumen["enviados"], self.red.pedidos), (0, 0, []))


# ---------------------------------------------------------------------------------------
# Modo de prueba
# ---------------------------------------------------------------------------------------
class TestPrueba(unittest.TestCase):
    def setUp(self):
        tarea._token_cache.update(token=None, vence=0.0, correo=None)
        self.addCleanup(tarea._token_cache.update, token=None, vence=0.0, correo=None)

    def _correr(self, credenciales, zona="cajamarca", red=None):
        red = red or _Red()
        ajustes = types.SimpleNamespace(credenciales=credenciales, proyecto="")
        salida = io.StringIO()
        with mock.patch.object(tarea, "ajustes_push", lambda: ajustes), mock.patch.object(tarea, "_firmar", lambda i, c: "x"), \
                mock.patch("sys.stdout", salida):
            codigo = tarea.prueba(zona, abrir=red, ahora=AHORA)
        return codigo, salida.getvalue(), red

    def test_sin_credenciales_no_envia_y_lo_dice(self):
        codigo, salida, red = self._correr("")
        self.assertEqual((codigo, red.pedidos), (2, []))
        self.assertIn(tarea.AVISO_SIN_CREDENCIALES, salida)

    def test_envia_al_tema_de_la_zona(self):
        codigo, salida, red = self._correr(json.dumps(INFO), zona="madre de dios")
        self.assertEqual(codigo, 0)
        [m] = red.fcm()
        self.assertEqual(m["topic"], "zona_madre_de_dios")
        self.assertNotIn("condition", m)
        self.assertEqual(m["notification"]["title"], "SIMPAC: prueba en Madre de Dios")
        self.assertIn("07:00", m["notification"]["body"])          # hora de Perú
        self.assertEqual(m["data"]["ruta"], "/alertas")
        self.assertIn("zona_madre_de_dios", salida)
        self.assertIn("projects/appsimpac/messages/1", salida)

    def test_falla_devuelve_1(self):
        codigo, salida, red = self._correr(json.dumps(INFO), red=_Red(fallas=[_http_error(404)]))
        self.assertEqual(codigo, 1)
        self.assertIn("HTTP 404", salida)

    def test_main_sin_argumentos_corre_la_tarea(self):
        with mock.patch.object(tarea, "actualizar", lambda: {"ok": 1}) as _, mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(tarea.main([]), 0)


if __name__ == "__main__":
    unittest.main()
