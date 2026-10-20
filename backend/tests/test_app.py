"""
API (backend/app.py): CORS cerrado a los orígenes de la web (SIMPAC_CORS_ORIGENES; plan de
seguridad). Sin Redis ni red: redis se carga con un stub si no está instalado y la app se
ejercita con el cliente de pruebas de FastAPI (sin lifespan, así no abre ninguna conexión).
"""
import importlib
import importlib.util
import sys
import types
import unittest
from unittest import mock

from backend import config

HAY_FASTAPI = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None


def _importar_app():
    """backend.app con redis de mentira si no está instalado (la API solo lo usa al arrancar)."""
    stubs = {}
    if importlib.util.find_spec("redis") is None:
        redis, redis_asyncio = types.ModuleType("redis"), types.ModuleType("redis.asyncio")
        redis_asyncio.Redis, redis_asyncio.from_url = object, lambda *a, **k: None
        redis.asyncio = redis_asyncio
        stubs = {"redis": redis, "redis.asyncio": redis_asyncio}
    with mock.patch.dict(sys.modules, stubs):
        sys.modules.pop("backend.app", None)
        return importlib.import_module("backend.app")


class TestOrigenesCors(unittest.TestCase):
    def test_lista_separada_por_comas(self):
        self.assertEqual(config.origenes_cors("https://simpac.pe, http://localhost:8080/ ,,"),
                         ("https://simpac.pe", "http://localhost:8080"))

    def test_vacio_o_comodin_dan_los_de_desarrollo(self):
        for texto in (None, "", " , ", "*", "*, *"):
            self.assertEqual(config.origenes_cors(texto), config.CORS_ORIGENES_DEFECTO, repr(texto))
        self.assertIn("http://localhost:8080", config.CORS_ORIGENES_DEFECTO)
        self.assertIn("capacitor://localhost", config.CORS_ORIGENES_DEFECTO)

    def test_desde_el_entorno(self):
        config.ajustes.cache_clear()
        self.addCleanup(config.ajustes.cache_clear)
        with mock.patch.dict("os.environ", {"SIMPAC_CORS_ORIGENES": "https://simpac.pe"}):
            self.assertEqual(config.ajustes().cors_origenes, ("https://simpac.pe",))
        config.ajustes.cache_clear()
        with mock.patch.dict("os.environ", {"SIMPAC_CORS_ORIGENES": ""}):
            self.assertEqual(config.ajustes().cors_origenes, config.CORS_ORIGENES_DEFECTO)


@unittest.skipUnless(HAY_FASTAPI, "fastapi y httpx no están instalados")
class TestCors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        config.ajustes.cache_clear()
        with mock.patch.dict("os.environ", {"SIMPAC_CORS_ORIGENES": ""}):
            cls.app = _importar_app()
        config.ajustes.cache_clear()
        cls.cliente = TestClient(cls.app.app)     # sin `with`: no corre el lifespan (ni abre Redis)

    def test_origen_de_la_web_si(self):
        r = self.cliente.get("/health", headers={"Origin": "http://localhost:8080"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:8080")
        self.assertEqual(r.json(), {"ok": True, "service": "simpac-api"})

    def test_otro_origen_no(self):
        r = self.cliente.get("/health", headers={"Origin": "https://ejemplo.com"})
        self.assertEqual(r.status_code, 200)              # la API responde igual; el navegador es el que no entrega
        self.assertNotIn("access-control-allow-origin", r.headers)

    def test_preflight_solo_get(self):
        cabeceras = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"}
        r = self.cliente.options("/api/snapshot", headers=cabeceras)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:5173")
        r = self.cliente.options("/api/snapshot", headers={**cabeceras, "Access-Control-Request-Method": "POST"})
        self.assertEqual(r.status_code, 400)
        r = self.cliente.options("/api/snapshot", headers={**cabeceras, "Origin": "https://ejemplo.com"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
