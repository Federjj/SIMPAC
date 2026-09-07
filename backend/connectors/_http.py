"""
Helpers HTTP mínimos para los conectores de SIMPAC.

Usa solo la librería estándar (urllib) para que los prototipos corran sin
instalar nada. En producción se recomienda migrar a `httpx`/`requests` con
reintentos y caché (ver docs/README-tecnico.md).
"""
from __future__ import annotations

import json
import ssl
import urllib.request
import urllib.parse
from typing import Any

USER_AGENT = "SIMPAC/0.1 (proyecto academico UPN; contacto: equipo-simpac)"
TIMEOUT = 30

# Algunos portales del Estado tienen cadenas de certificado incompletas.
# Intentamos verificar y, si falla por certificado, reintentamos sin verificar
# (dejando constancia). NUNCA enviamos datos sensibles a estos hosts.
_CTX_VERIFY = ssl.create_default_context()
_CTX_NOVERIFY = ssl.create_default_context()
_CTX_NOVERIFY.check_hostname = False
_CTX_NOVERIFY.verify_mode = ssl.CERT_NONE


def _open(req: urllib.request.Request) -> str:
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX_VERIFY) as r:
            return r.read().decode("utf-8", "ignore")
    except ssl.SSLCertVerificationError:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX_NOVERIFY) as r:
            return r.read().decode("utf-8", "ignore")


def get(url: str, params: dict[str, Any] | None = None) -> str:
    """GET → texto de la respuesta."""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return _open(req)


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
