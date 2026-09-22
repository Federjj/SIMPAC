"""
Helpers HTTP mínimos para los conectores de SIMPAC.

Usa solo la librería estándar (urllib) para que los prototipos corran sin
instalar nada. En producción se recomienda migrar a `httpx`/`requests` con
reintentos y caché (ver docs/README-tecnico.md).
"""
from __future__ import annotations

import http.client
import json
import logging
import ssl
import time
import urllib.error
import urllib.request
import urllib.parse
from typing import Any

log = logging.getLogger(__name__)

USER_AGENT = "SIMPAC/0.1 (proyecto academico UPN; contacto: equipo-simpac)"
TIMEOUT = 30
INTENTOS = 3   # intentos totales ante fallas transitorias de red

# El certificado TLS SIEMPRE se verifica: si un portal lo tiene mal, la petición
# falla (mejor un error visible que aceptar datos de un servidor no verificado).
# Comprobado el 22-09-2026: SENAMHI, IDESEP, ANA y NOAA verifican bien; IGP usa HTTP.
_CTX = ssl.create_default_context()


def _leer(req: urllib.request.Request, max_bytes: int | None = None) -> bytes:
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as r:
        if max_bytes is None:
            return r.read()  # si el cuerpo llega cortado, lanza IncompleteRead
        datos = r.read(max_bytes + 1)
        if len(datos) > max_bytes:
            raise ValueError(f"La descarga supera el limite de {max_bytes} bytes")
        # read(n) no avisa si el servidor corta antes de tiempo: se compara con
        # Content-Length. ConnectionError es un OSError, así que se puede reintentar.
        esperado = r.headers.get("Content-Length")
        if esperado and esperado.isdigit() and len(datos) < int(esperado):
            raise ConnectionError(f"Descarga incompleta: {len(datos)} de {esperado} bytes")
        return datos


def con_reintentos(fn, *args, intentos: int = INTENTOS):
    """
    Llama fn(*args) reintentando las fallas transitorias de red (timeouts, 5xx,
    descargas cortadas) con espera de 2 s y 4 s. Los errores 4xx (404, 403...) y
    los de datos (ValueError) no se reintentan: repetirlos no los arregla.
    """
    for intento in range(1, intentos + 1):
        try:
            return fn(*args)
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                raise
            error = e
        except (OSError, http.client.IncompleteRead) as e:
            error = e
        if intento == intentos:
            raise error
        espera = 2 ** intento
        log.warning("Falla de red (%s), reintento %d/%d en %ds",
                    type(error).__name__, intento, intentos - 1, espera)
        time.sleep(espera)


def _open(req: urllib.request.Request) -> str:
    return _leer(req).decode("utf-8", "ignore")


def get(url: str, params: dict[str, Any] | None = None) -> str:
    """GET → texto de la respuesta."""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return _open(req)


def get_bytes(url: str, max_bytes: int | None = None) -> bytes:
    """GET -> bytes crudos (p. ej. un .zip). Falla si supera max_bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return _leer(req, max_bytes)


def post_json(url: str, body: str) -> Any:
    """
    POST de un cuerpo JSON (string) a un web service ASMX/ScriptService.
    Devuelve el contenido de la clave "d" ya deserializado.
    """
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="POST",
    )
    raw = _open(req)
    data = json.loads(raw)
    d = data.get("d", data)
    # ASMX a veces devuelve "d" como string JSON anidado.
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except json.JSONDecodeError:
            pass
    return d
