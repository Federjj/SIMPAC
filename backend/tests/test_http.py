"""_http: TLS estricto, descargas con tope y reintentos."""
import http.client
import http.server
import io
import logging
import socketserver
import ssl
import threading
import unittest
import urllib.error
from unittest import mock

from backend.connectors import _http


class _Handler(http.server.BaseHTTPRequestHandler):
    """Anuncia 1000 bytes; en /corto manda solo 500 y corta la conexión."""

    def do_GET(self):
        corto = self.path.startswith("/corto")
        self.send_response(200)
        self.send_header("Content-Length", "1000")
        self.end_headers()
        self.wfile.write(b"x" * (500 if corto else 1000))
        if corto:
            self.close_connection = True

    def log_message(self, *args):
        pass


class TestTLS(unittest.TestCase):
    def test_certificado_siempre_verificado(self):
        self.assertEqual(_http._CTX.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(_http._CTX.check_hostname)
        self.assertFalse(hasattr(_http, "_CTX_NOVERIFY"))


class TestDescargas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_bytes_completos(self):
        self.assertEqual(_http.get_bytes(self.base + "/f.zip"), b"x" * 1000)

    def test_tope_holgado(self):
        self.assertEqual(len(_http.get_bytes(self.base + "/f.zip", max_bytes=2000)), 1000)

    def test_tope_excedido(self):
        with self.assertRaises(ValueError):
            _http.get_bytes(self.base + "/f.zip", max_bytes=500)

    def test_cortado_con_tope_es_reintentable(self):
        with self.assertRaises(ConnectionError):
            _http.get_bytes(self.base + "/corto", max_bytes=2000)

    def test_cortado_sin_tope(self):
        with self.assertRaises(http.client.IncompleteRead):
            _http.get_bytes(self.base + "/corto")

    def test_get_texto(self):
        self.assertEqual(_http.get(self.base + "/f"), "x" * 1000)


def _falla_n_veces(*errores):
    """Función que lanza los errores dados, en orden, y luego devuelve 'ok'."""
    estado = {"llamadas": 0}

    def fn():
        estado["llamadas"] += 1
        if estado["llamadas"] <= len(errores):
            raise errores[estado["llamadas"] - 1]
        return "ok"
    return fn, estado


@mock.patch.object(_http.time, "sleep", lambda s: None)
class TestReintentos(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def _http_error(self, codigo):
        e = urllib.error.HTTPError("http://x", codigo, "x", {}, io.BytesIO(b""))
        self.addCleanup(e.close)
        return e

    def test_red_y_descarga_cortada_se_reintentan(self):
        fn, st = _falla_n_veces(OSError("red"), http.client.IncompleteRead(b""))
        self.assertEqual(_http.con_reintentos(fn), "ok")
        self.assertEqual(st["llamadas"], 3)

    def test_5xx_se_reintenta(self):
        fn, st = _falla_n_veces(self._http_error(503))
        self.assertEqual(_http.con_reintentos(fn), "ok")
        self.assertEqual(st["llamadas"], 2)

    def test_4xx_no_se_reintenta(self):
        fn, st = _falla_n_veces(self._http_error(404))
        with self.assertRaises(urllib.error.HTTPError):
            _http.con_reintentos(fn)
        self.assertEqual(st["llamadas"], 1)

    def test_error_de_datos_no_se_reintenta(self):
        fn, st = _falla_n_veces(ValueError("sin zip"))
        with self.assertRaises(ValueError):
            _http.con_reintentos(fn)
        self.assertEqual(st["llamadas"], 1)

    def test_se_rinde_tras_3_intentos(self):
        fn, st = _falla_n_veces(OSError("a"), OSError("b"), OSError("c"))
        with self.assertRaises(OSError):
            _http.con_reintentos(fn)
        self.assertEqual(st["llamadas"], 3)


if __name__ == "__main__":
    unittest.main()
