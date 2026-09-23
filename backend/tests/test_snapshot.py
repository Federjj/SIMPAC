"""
Snapshot de la API (backend/snapshot.py): de dónde salen las alertas (vista alerta_actual, o la
tabla alerta si la migración aún no está), la marca `oficial` de cada una y los conteos que
separan lo oficial de la lluvia medida. Sin red, Redis ni httpx: se cargan con stubs y se
simula la lectura de Supabase (_leer).
"""
import asyncio
import importlib
import sys
import types
import unittest
from unittest import mock

import backend
# Antes del patch.dict: lo que se importe por primera vez dentro de él sale de sys.modules al
# terminar, y otra prueba lo volvería a importar como un módulo distinto.
from backend import alerts, config  # noqa: F401


class _HTTPError(Exception):
    pass


class _HTTPStatusError(_HTTPError):
    def __init__(self, message, *, request=None, response=None):
        super().__init__(message)
        self.request, self.response = request, response


class _AsyncClient:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _importar_snapshot():
    """backend.snapshot con httpx y redis de mentira (fuera de esta prueba no quedan)."""
    httpx = types.ModuleType("httpx")
    httpx.AsyncClient, httpx.HTTPError, httpx.HTTPStatusError = _AsyncClient, _HTTPError, _HTTPStatusError
    redis, redis_asyncio = types.ModuleType("redis"), types.ModuleType("redis.asyncio")
    redis_asyncio.Redis, redis_asyncio.from_url = object, lambda *a, **k: None
    redis.asyncio = redis_asyncio
    previo = getattr(backend, "snapshot", None)
    with mock.patch.dict(sys.modules, {"httpx": httpx, "redis": redis, "redis.asyncio": redis_asyncio}):
        sys.modules.pop("backend.snapshot", None)
        modulo = importlib.import_module("backend.snapshot")
    if previo is not None:
        backend.snapshot = previo
    return modulo


snapshot = _importar_snapshot()

VISTA = "tipo,referencia,zona,nivel,detalle,valor,umbral,ventana_h,ts,lat,lon"
TS = "2026-09-22T19:00:00-05:00"
AVISO = {"tipo": "aviso", "referencia": "SENAMHI aviso 377", "zona": "Cajamarca", "nivel": "aviso",
         "detalle": "Lluvias en la sierra", "valor": None, "umbral": None, "ts": TS}
CAUDAL = {"tipo": "caudal", "referencia": "Chilete (Jequetepeque)", "zona": "Cajamarca", "nivel": "alerta",
          "detalle": "Caudal 80 m³/s, subiendo", "valor": 80.0, "umbral": 70.0, "ts": TS}
LLUVIA = {"tipo": "lluvia", "referencia": "CHOTA GORE@-6.55405,-78.67588", "zona": "Cajamarca", "nivel": "aviso",
          "detalle": "En Chota GORE (provincia de Chota) llovió 12.4 mm en la hora que terminó a las 18:00. ...",
          "valor": 12.4, "umbral": 10.0, "ts": TS}


def _de_la_vista(a, ventana_h=None, lat=None, lon=None):
    return {**a, "ventana_h": ventana_h, "lat": lat, "lon": lon}


class TestAlertasDelSnapshot(unittest.TestCase):
    def armar(self, alerta_actual=(), alerta=(), error_vista=None):
        """Corre _armar con Supabase simulado -> (snapshot, lecturas [(tabla, select, filtros)])."""
        leidas = []

        async def falso_leer(c, tabla, select, **filtros):
            leidas.append((tabla, select, filtros))
            if tabla == "alerta_actual":
                if error_vista:
                    raise _HTTPStatusError(f"Client error '{error_vista}'",
                                           response=types.SimpleNamespace(status_code=error_vista))
                return [dict(a) for a in alerta_actual]
            if tabla == "alerta":
                return [dict(a) for a in alerta]
            return []

        with mock.patch.object(snapshot, "_leer", falso_leer):
            data = asyncio.run(snapshot._armar())
        return data, leidas

    def test_lee_la_vista_y_marca_lo_oficial(self):
        vista = [_de_la_vista(AVISO), _de_la_vista(CAUDAL, lat=-7.2, lon=-78.9),
                 _de_la_vista(LLUVIA, ventana_h=1, lat=-6.55405, lon=-78.67588)]
        data, leidas = self.armar(alerta_actual=vista)
        # la vista ya deja fuera las no vigentes y la lluvia de más de 3 h: sin filtro vigente
        [(select, filtros)] = [(s, f) for t, s, f in leidas if t == "alerta_actual"]
        self.assertEqual(select, VISTA)
        self.assertEqual(filtros, {"order": "ts.desc"})
        self.assertNotIn("alerta", [t for t, _, _ in leidas])
        # la lluvia medida nunca es oficial (la app y las push no la tratan como alerta)
        self.assertEqual([(a["tipo"], a["oficial"]) for a in data["alertas"]],
                         [("aviso", True), ("caudal", True), ("lluvia", False)])
        self.assertEqual(data["alertas"][2]["ventana_h"], 1)   # su umbral se lee con ventana_h
        resumen = data["resumen"]
        self.assertEqual((resumen["alertas"], resumen["alertas_oficiales"], resumen["lluvia_sobre_referencia"]),
                         (3, 2, 1))

    def test_sin_alertas(self):
        data, _ = self.armar()
        self.assertEqual(data["alertas"], [])
        self.assertEqual({k: data["resumen"][k] for k in ("alertas", "alertas_oficiales", "lluvia_sobre_referencia")},
                         {"alertas": 0, "alertas_oficiales": 0, "lluvia_sobre_referencia": 0})

    def test_sin_migracion_lee_la_tabla_sin_la_lluvia(self):
        # el worker o la API salieron antes que la migración: no hay vista y PostgREST da 404
        with self.assertLogs("backend.snapshot", "WARNING"):
            data, leidas = self.armar(error_vista=404, alerta=[AVISO, CAUDAL, LLUVIA])
        [(select, filtros)] = [(s, f) for t, s, f in leidas if t == "alerta"]
        self.assertEqual(select, "tipo,referencia,zona,nivel,detalle,valor,umbral,ts")   # sin columnas nuevas
        self.assertEqual(filtros, {"vigente": "eq.true", "order": "ts.desc"})
        # la lluvia del formato viejo (sin ventana_h) tampoco la mostraría la vista
        self.assertEqual([a["referencia"] for a in data["alertas"]], [AVISO["referencia"], CAUDAL["referencia"]])
        self.assertEqual(set(data["alertas"][0]), set(VISTA.split(",")) | {"oficial"})   # mismas claves
        self.assertTrue(all(a["oficial"] for a in data["alertas"]))
        self.assertEqual((data["resumen"]["alertas_oficiales"], data["resumen"]["lluvia_sobre_referencia"]), (2, 0))

    def test_otro_error_de_la_vista_no_se_tapa(self):
        # Supabase caído no es migración pendiente: el error sube y get_snapshot sirve el respaldo
        with self.assertRaises(_HTTPStatusError):
            self.armar(error_vista=503)


if __name__ == "__main__":
    unittest.main()
