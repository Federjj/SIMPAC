"""
API JSON de SIMPAC (prototipo) — servidor de la librería estándar, sin deps.

    python backend/api.py            # sirve en http://localhost:8000

Endpoints (todos GET, JSON, con CORS abierto para el frontend en desarrollo):
    GET /api/snapshot          panorama: contexto + resumen + alertas + caudales
    GET /api/estaciones        inventario de estaciones (Cajamarca)
    GET /api/caudales          última lectura de caudal por estación, con estado
    GET /api/lluvia?cod=107028 serie horaria (lluvia/temp) de una estación
    GET /api/alertas           alertas vigentes
    GET /api/contexto          índices El Niño (ONI / ICEN)

La lógica de datos vive en store.py; migrar a FastAPI es envolver estas mismas
consultas en rutas async (ver docs/README-tecnico.md).
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, __file__.rsplit("backend", 1)[0])
from backend import store

PORT = 8000


def _snapshot(conn) -> dict:
    ctx = {r["fuente"]: r for r in store.indices(conn)}
    caud = store.caudales_ultimos(conn)
    aler = store.alertas(conn)
    return {
        "contexto": ctx,
        "resumen": {
            "estaciones": len(store.estaciones(conn)),
            "caudales": len(caud),
            "alertas": len(aler),
            "en_alerta": [c["estacion"] for c in caud if c["estado"] in ("alerta", "emergencia")],
        },
        "alertas": aler,
        "caudales": caud,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        conn = store.connect()
        try:
            if u.path in ("/", "/api", "/api/"):
                self._send({"ok": True, "endpoints": [
                    "/api/snapshot", "/api/estaciones", "/api/caudales",
                    "/api/lluvia?cod=", "/api/alertas", "/api/contexto"]})
            elif u.path == "/api/snapshot":
                self._send(_snapshot(conn))
            elif u.path == "/api/estaciones":
                self._send(store.estaciones(conn))
            elif u.path == "/api/caudales":
                self._send(store.caudales_ultimos(conn))
            elif u.path == "/api/alertas":
                self._send(store.alertas(conn))
            elif u.path == "/api/contexto":
                self._send(store.indices(conn))
            elif u.path == "/api/lluvia":
                cod = (q.get("cod") or [""])[0]
                if not cod:
                    self._send({"error": "falta ?cod="}, 400)
                else:
                    self._send({"cod": cod, "serie": store.lluvia_serie(conn, cod)})
            else:
                self._send({"error": "not found", "path": u.path}, 404)
        finally:
            conn.close()

    def log_message(self, *a):  # silencio en consola
        pass


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"SIMPAC API en http://localhost:{PORT}  (Ctrl+C para parar)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
