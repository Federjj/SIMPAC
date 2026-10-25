"""
Avisador push (HU-20): tarea Celery 'push', cada 5 min.

Lee titular_zona (departamento, nivel, titular_corto, generado_en) y manda una notificación por
Firebase Cloud Messaging (FCM, API HTTP v1) cuando el nivel de una zona CAMBIA de verdad:
  - sube a alerta o emergencia (o pasa de alerta a emergencia): "SIMPAC: ALERTA en Cajamarca" con
    el titular_corto de cuerpo;
  - baja de alerta o emergencia a normal o aviso: "SIMPAC: vuelve la calma en Cajamarca".
Nunca por un aviso amarillo ni por lluvia medida (esos niveles nunca llegan a 'alerta' en
titular_zona: lib/nivel.js y titular.py _nivel_efectivo), y nunca el mismo mensaje dos veces: la
tabla push_estado recuerda el último nivel que se notificó por zona (migración push_estado).

Temas (el contrato con la app): 'pais' y 'zona_<slug>' donde slug es el departamento en minúsculas,
sin tildes y con los espacios como guion bajo (zona_cajamarca, zona_la_libertad, zona_madre_de_dios,
zona_callao). Cada mensaje va UNA vez a quien esté en cualquiera de los dos temas (condición
"'pais' in topics || 'zona_cajamarca' in topics"), así quien se suscribió a los dos no lo recibe
doble. data = {nivel, zona, generado_en, ruta: "/alertas"} (todo texto, como exige FCM).

Reglas de decisión (decidir()):
  previo = último nivel en push_estado; sin fila, línea base 'normal' (una alerta vigente al
  activar el avisador se notifica una vez; nada que esté por debajo de alerta se notifica nunca).
  actual 'sin_dato'      -> no se toca nada: la fuente cayó, eso no es calma ni alerta.
  igual que el previo    -> nada (ni aunque cambie el texto del titular).
  sube a alerta/emerg.   -> mensaje de alerta.
  alerta/emerg. -> normal o aviso -> mensaje de calma.
  cualquier otro cambio (normal<->aviso, emergencia->alerta) -> se anota el nivel sin enviar.

Credenciales: FIREBASE_CREDENCIALES (backend/config.py ajustes_push) es la ruta al JSON de la cuenta
de servicio del proyecto Firebase o ese JSON en base64. El token OAuth2 se obtiene firmando un JWT
RS256 con la clave de la cuenta (google-auth solo para firmar; el POST a oauth2.googleapis.com y a
FCM van con urllib, como en titular.py). El token vive ~1 h y se guarda en memoria del worker. La
clave nunca se registra: los avisos del latido solo llevan el código HTTP y el motivo.

Sin credenciales la tarea NO falla: escribe su latido con el aviso "push sin credenciales de
Firebase: no se envía nada" y la lista de lo que habría mandado (pendientes); tampoco toca
push_estado, así al poner las credenciales las alertas vigentes se avisan una vez.

Todo va en una transacción con candado (pg_advisory_xact_lock): leer, enviar, anotar y el latido;
dos corridas no se pisan. PLAZO_S corta los envíos antes del soft limit de 60 s (celery_app).

Resumen del latido 'push':
  zonas        filas de titular_zona evaluadas
  enviados     mensajes que FCM aceptó en esta corrida
  mensajes     [{zona, nivel, tema, tipo: alerta|calma, mensaje_id}]
  temas        temas zona_<slug> a los que se envió
  anotados     cambios de nivel por debajo de alerta anotados sin enviar
  pendientes   [{zona, nivel, tipo}] lo que tocaba enviar y no se envió (sin credenciales, falla o plazo)
  proyecto     id del proyecto Firebase (null sin credenciales)
  credenciales true si se pudieron leer
  fallas       'migracion' (falta push_estado), 'credenciales' (ilegibles o FCM las rechazó: 401/403),
               'token' (no se obtuvo el token OAuth2), 'envio' (FCM respondió error o no respondió)
  avisos       detalle de las fallas (nunca la clave ni el token)

Corridas sueltas (dentro del contenedor worker o con SUPABASE_DB_URL en el entorno):
    python -m backend.ingesta.push                          una corrida de la tarea
    python -m backend.ingesta.push --prueba --zona Cajamarca   mensaje de prueba al tema zona_cajamarca
                                                               (no toca la BD; solo con credenciales)
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import logging
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from backend.config import ajustes_push
from backend.connectors.senamhi import HORA_PERU
from backend.db import conectar
from backend.ingesta.departamentos import nombre_departamento
from backend.ingesta.guardar import SQL_LATIDO

log = logging.getLogger(__name__)

SERVICIO = "push"
FCM_URL = "https://fcm.googleapis.com/v1/projects/{proyecto}/messages:send"
ALCANCE = "https://www.googleapis.com/auth/firebase.messaging"
TOKEN_URL_DEFECTO = "https://oauth2.googleapis.com/token"
TIMEOUT_S = 15
# No se empieza otro envío pasados estos segundos: la tarea tiene 60 s de soft limit (celery_app) y
# el latido se escribe siempre. Lo que quede sale en la corrida siguiente (su nivel no se anotó).
PLAZO_S = 40
# Tras estas fallas seguidas de FCM (caído, 5xx) no se insiste en la corrida.
MAX_FALLAS_SEGUIDAS = 3
MAX_AVISOS = 20
TOKEN_MARGEN_S = 60
TEMA_PAIS = "pais"
RUTA = "/alertas"
ORDEN_NIVEL = ("sin_dato", "normal", "aviso", "alerta", "emergencia")
NIVELES_AVISAR = ("alerta", "emergencia")
NIVELES_CALMA = ("normal", "aviso")
AVISO_SIN_CREDENCIALES = "push sin credenciales de Firebase: no se envía nada"
AVISO_SIN_TABLA = "push_estado: falta la tabla (migración pendiente); no se envió nada"

SQL_HAY_TABLA = ("select to_regclass('public.push_estado') is not null "
                 "and to_regclass('public.titular_zona') is not null")
SQL_CANDADO = "select pg_advisory_xact_lock(hashtext('push'))"
SQL_TITULARES = "select departamento, nivel, titular_corto, titular, generado_en from titular_zona"
SQL_PREVIOS = "select zona, nivel, titular, enviado_en, mensaje_id from push_estado"
SQL_ENVIADO = """
insert into push_estado (zona, nivel, titular, enviado_en, mensaje_id, actualizado_en)
values (%(zona)s, %(nivel)s, %(titular)s, now(), %(mensaje_id)s, now())
on conflict (zona) do update set
  nivel = excluded.nivel, titular = excluded.titular, enviado_en = now(), mensaje_id = excluded.mensaje_id,
  actualizado_en = now()
"""
# Cambio por debajo de alerta: solo el nivel; el último mensaje enviado se conserva.
SQL_NIVEL = ("insert into push_estado (zona, nivel) values (%(zona)s, %(nivel)s) "
             "on conflict (zona) do update set nivel = excluded.nivel, actualizado_en = now()")


class CredencialesInvalidas(ValueError):
    """FIREBASE_CREDENCIALES no se pudo leer o FCM las rechazó (401/403): no tiene sentido insistir."""


class FallaEnvio(RuntimeError):
    """FCM respondió con error o no respondió; la zona queda pendiente para la próxima corrida."""


def _error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _recortar(lista: list, maximo: int) -> list:
    if len(lista) <= maximo:
        return lista
    return [*lista[:maximo], f"... y {len(lista) - maximo} más"]


def _filas(cur) -> list[dict]:
    columnas = [c[0] for c in cur.description]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


# ---------------------------------------------------------------------------------------
# Temas y decisión
# ---------------------------------------------------------------------------------------
def slug_zona(nombre: str) -> str:
    """'Madre de Dios' -> 'madre_de_dios'; 'Áncash' -> 'ancash'; 'San Martín' -> 'san_martin'."""
    sin_tildes = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes.lower()).strip("_")


def tema_zona(nombre: str) -> str:
    return f"zona_{slug_zona(nombre)}"


def condicion(nombre: str) -> str:
    """Quien esté en 'pais' o en el tema de la zona recibe el mensaje una sola vez."""
    return f"'{TEMA_PAIS}' in topics || '{tema_zona(nombre)}' in topics"


def decidir(nivel_previo: str | None, nivel_actual: str | None) -> str | None:
    """
    'alerta'  hay que avisar: subió a alerta o emergencia (o de alerta a emergencia)
    'calma'   hay que avisar que bajó de alerta/emergencia a normal o aviso
    'nivel'   cambió por debajo de alerta (o bajó de emergencia a alerta): anotar sin enviar
    None      nada que hacer (igual que antes, nivel desconocido o fuente caída)
    """
    if nivel_actual not in ORDEN_NIVEL or nivel_actual == "sin_dato":
        return None
    previo = nivel_previo if nivel_previo in ORDEN_NIVEL else "normal"
    if previo == nivel_actual:
        return None
    if nivel_actual in NIVELES_AVISAR and ORDEN_NIVEL.index(nivel_actual) > ORDEN_NIVEL.index(previo):
        return "alerta"
    if previo in NIVELES_AVISAR and nivel_actual in NIVELES_CALMA:
        return "calma"
    return "nivel"


# ---------------------------------------------------------------------------------------
# Mensaje
# ---------------------------------------------------------------------------------------
def _hora_iso(momento) -> str:
    if isinstance(momento, datetime):
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=timezone.utc)
        return momento.astimezone(timezone.utc).isoformat(timespec="seconds")
    return str(momento or "")


def cuerpo_mensaje(fila: dict) -> str:
    """titular_corto; si aún no está (filas anteriores a esa columna), el titular completo."""
    texto = (fila.get("titular_corto") or fila.get("titular") or "").strip()
    return texto or f"{fila.get('departamento') or 'Tu zona'}: hay un cambio en las fuentes oficiales. Abre SIMPAC."


def armar_mensaje(zona: str, nivel: str, cuerpo: str, generado_en, tipo: str) -> dict:
    """
    El objeto `message` de la API v1 de FCM, sin destino (lo pone quien envía: condición o tema).
    tipo: 'alerta' (subió), 'calma' (bajó) o 'prueba' (--prueba).
    """
    if tipo == "calma":
        titulo = f"SIMPAC: vuelve la calma en {zona}"
    elif tipo == "prueba":
        titulo = f"SIMPAC: prueba en {zona}"
    else:
        titulo = f"SIMPAC: {nivel.upper()} en {zona}"
    return {
        "notification": {"title": titulo, "body": cuerpo},
        "data": {"nivel": str(nivel), "zona": str(zona), "generado_en": _hora_iso(generado_en), "ruta": RUTA},
        # alta prioridad solo para lo que pide actuar; la calma puede esperar a que el teléfono despierte
        "android": {"priority": "high" if tipo == "alerta" else "normal"},
    }


# ---------------------------------------------------------------------------------------
# Credenciales y token OAuth2 de la cuenta de servicio
# ---------------------------------------------------------------------------------------
def cargar_credenciales(valor: str | None) -> dict | None:
    """
    FIREBASE_CREDENCIALES -> dict de la cuenta de servicio; None si está vacía.
    Acepta la ruta a un archivo JSON, el JSON en base64 (una línea para el .env) o el JSON tal cual.
    Los errores nunca repiten el valor recibido.
    """
    valor = (valor or "").strip()
    if not valor:
        return None
    try:
        if valor.startswith("{"):
            texto = valor
        elif os.path.isfile(valor):
            with open(valor, encoding="utf-8") as f:
                texto = f.read()
        else:
            texto = base64.b64decode(valor, validate=True).decode("utf-8")
        info = json.loads(texto)
    except (OSError, ValueError, binascii.Error, UnicodeDecodeError) as e:
        raise CredencialesInvalidas(f"no es una ruta a un JSON, un JSON ni base64 válido ({type(e).__name__})") from e
    if not isinstance(info, dict):
        raise CredencialesInvalidas("el JSON no es un objeto")
    for campo in ("client_email", "private_key", "project_id"):
        if not info.get(campo):
            raise CredencialesInvalidas(f"a la cuenta de servicio le falta {campo}")
    return info


def _firmar(info: dict, carga: dict) -> str:
    """JWT RS256 firmado con la clave de la cuenta de servicio (google-auth, solo para firmar)."""
    try:
        from google.auth import crypt, jwt
    except ImportError as e:
        raise RuntimeError("falta google-auth (pip install -r backend/requirements.txt)") from e
    firmado = jwt.encode(crypt.RSASigner.from_service_account_info(info), carga)
    return firmado.decode("ascii") if isinstance(firmado, bytes) else firmado


def obtener_token(info: dict, abrir=urllib.request.urlopen, ahora_s: float | None = None) -> tuple[str, float]:
    """Token de acceso para FCM y cuándo vence (segundos de time.time())."""
    ahora_s = time.time() if ahora_s is None else ahora_s
    token_uri = info.get("token_uri") or TOKEN_URL_DEFECTO
    carga = {"iss": info["client_email"], "scope": ALCANCE, "aud": token_uri,
             "iat": int(ahora_s), "exp": int(ahora_s) + 3600}
    datos = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                    "assertion": _firmar(info, carga)}).encode("ascii")
    pedido = urllib.request.Request(token_uri, data=datos, method="POST",
                                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    with abrir(pedido, timeout=TIMEOUT_S) as r:
        respuesta = json.loads(r.read().decode("utf-8"))
    token = respuesta.get("access_token")
    if not token:
        raise CredencialesInvalidas("la respuesta del token no trae access_token")
    return token, ahora_s + float(respuesta.get("expires_in") or 3600)


_token_cache: dict = {"token": None, "vence": 0.0, "correo": None}


def token_vigente(info: dict, abrir=urllib.request.urlopen) -> str:
    """El token guardado si le queda más de TOKEN_MARGEN_S; si no, uno nuevo."""
    ahora_s = time.time()
    if (_token_cache["token"] and _token_cache["correo"] == info["client_email"]
            and _token_cache["vence"] - ahora_s > TOKEN_MARGEN_S):
        return _token_cache["token"]
    token, vence = obtener_token(info, abrir, ahora_s)
    _token_cache.update(token=token, vence=vence, correo=info["client_email"])
    return token


# ---------------------------------------------------------------------------------------
# Envío
# ---------------------------------------------------------------------------------------
def _detalle_http(e: urllib.error.HTTPError) -> str:
    try:
        cuerpo = e.read().decode("utf-8", "replace")
        datos = json.loads(cuerpo)
        err = datos.get("error") or {}
        texto = err.get("status") or err.get("message") or cuerpo
    except Exception:
        texto = ""
    finally:
        e.close()
    texto = re.sub(r"\s+", " ", str(texto)).strip()
    return f"HTTP {e.code}" + (f" {texto[:160]}" if texto else "")


def enviar(mensaje: dict, proyecto: str, token: str, abrir=urllib.request.urlopen) -> str:
    """POST a FCM v1; devuelve el nombre del mensaje (projects/<p>/messages/<id>)."""
    datos = json.dumps({"message": mensaje}, ensure_ascii=False).encode("utf-8")
    pedido = urllib.request.Request(FCM_URL.format(proyecto=proyecto), data=datos, method="POST",
                                    headers={"Authorization": f"Bearer {token}",
                                             "Content-Type": "application/json; charset=utf-8"})
    try:
        with abrir(pedido, timeout=TIMEOUT_S) as r:
            respuesta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = _detalle_http(e)
        if e.code in (401, 403):
            raise CredencialesInvalidas(f"FCM rechazó las credenciales ({detalle})") from e
        raise FallaEnvio(detalle) from e
    except (OSError, ValueError) as e:        # URLError, timeout, JSON ilegible
        raise FallaEnvio(_error(e)) from e
    return str(respuesta.get("name") or "")


# ---------------------------------------------------------------------------------------
# La tarea
# ---------------------------------------------------------------------------------------
def _resumen(fallas: list[str], avisos: list[str], **datos) -> dict:
    base = {"zonas": 0, "enviados": 0, "mensajes": [], "temas": [], "anotados": 0, "pendientes": [],
            "proyecto": None, "credenciales": False}
    vistas = []
    for f in fallas:
        if f not in vistas:
            vistas.append(f)
    return {**base, **datos, "fallas": vistas, "avisos": _recortar(avisos, MAX_AVISOS)}


def _latido(cur, resumen: dict) -> None:
    cur.execute(SQL_LATIDO, (SERVICIO, json.dumps(resumen, ensure_ascii=False)))


def actualizar(ahora: datetime | None = None, abrir=urllib.request.urlopen) -> dict:
    """Tarea 'push' (Celery la llama sin argumentos; `ahora` y `abrir` son para las pruebas)."""
    ahora = ahora or datetime.now(timezone.utc)
    inicio = time.monotonic()
    cfg = ajustes_push()
    fallas: list[str] = []
    avisos: list[str] = []
    try:
        info = cargar_credenciales(cfg.credenciales)
    except CredencialesInvalidas as e:
        info = None
        fallas.append("credenciales")
        avisos.append(f"FIREBASE_CREDENCIALES ilegible: {e}")
    proyecto = cfg.proyecto or (info or {}).get("project_id")

    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_HAY_TABLA)
        if not cur.fetchone()[0]:
            resumen = _resumen(["migracion", *fallas], [AVISO_SIN_TABLA, *avisos])
            _latido(cur, resumen)
            log.warning("Push: %s", AVISO_SIN_TABLA)
            return resumen
        cur.execute(SQL_CANDADO)
        cur.execute(SQL_TITULARES)
        titulares = _filas(cur)
        cur.execute(SQL_PREVIOS)
        previos = {p["zona"]: p for p in _filas(cur)}

        decisiones = []
        for fila in titulares:
            previo = previos.get(fila["departamento"])
            accion = decidir(previo["nivel"] if previo else None, fila["nivel"])
            if accion:
                decisiones.append((fila, accion))
        por_enviar = [(f, a) for f, a in decisiones if a in ("alerta", "calma")]
        pendientes = [{"zona": f["departamento"], "nivel": f["nivel"], "tipo": a} for f, a in por_enviar]

        if info is None:
            if not fallas:
                avisos.append(AVISO_SIN_CREDENCIALES)
            resumen = _resumen(fallas, avisos, zonas=len(titulares), pendientes=pendientes)
            _latido(cur, resumen)
            log.info("Push: %s", resumen)
            return resumen

        # Primero lo que no depende de FCM: los cambios de nivel por debajo de alerta (línea base).
        anotados = 0
        for fila, accion in decisiones:
            if accion == "nivel":
                cur.execute(SQL_NIVEL, {"zona": fila["departamento"], "nivel": fila["nivel"]})
                anotados += 1

        mensajes, enviados_zonas = [], set()
        fallas_seguidas = 0
        for fila, accion in por_enviar:
            zona = fila["departamento"]
            if fallas_seguidas >= MAX_FALLAS_SEGUIDAS:
                continue
            if time.monotonic() - inicio > PLAZO_S:
                if "plazo" not in avisos[-1:]:
                    avisos.append("plazo")
                continue
            try:
                token = token_vigente(info, abrir)
            except CredencialesInvalidas as e:
                fallas.append("credenciales")
                avisos.append(f"token OAuth2: {e}")
                break
            except (OSError, ValueError, KeyError, RuntimeError) as e:
                fallas.append("token")
                avisos.append(f"token OAuth2: {_error(e)}")
                break
            mensaje = {**armar_mensaje(zona, fila["nivel"], cuerpo_mensaje(fila), fila.get("generado_en"), accion),
                       "condition": condicion(zona)}
            try:
                mensaje_id = enviar(mensaje, proyecto, token, abrir)
            except CredencialesInvalidas as e:
                fallas.append("credenciales")
                avisos.append(f"{zona}: {e}")
                break
            except FallaEnvio as e:
                fallas_seguidas += 1
                fallas.append("envio")
                avisos.append(f"{zona}: {e}")
                continue
            fallas_seguidas = 0
            cur.execute(SQL_ENVIADO, {"zona": zona, "nivel": fila["nivel"], "titular": mensaje["notification"]["body"],
                                      "mensaje_id": mensaje_id or None})
            mensajes.append({"zona": zona, "nivel": fila["nivel"], "tema": tema_zona(zona), "tipo": accion,
                             "mensaje_id": mensaje_id or None})
            enviados_zonas.add(zona)

        if fallas_seguidas >= MAX_FALLAS_SEGUIDAS:
            avisos.append(f"FCM falló {MAX_FALLAS_SEGUIDAS} veces seguidas: el resto queda para la próxima corrida")
        if "plazo" in avisos:
            avisos[avisos.index("plazo")] = f"se pasó el plazo de {PLAZO_S} s: el resto queda para la próxima corrida"
        resumen = _resumen(fallas, avisos, zonas=len(titulares), enviados=len(mensajes), mensajes=mensajes,
                           temas=[m["tema"] for m in mensajes], anotados=anotados,
                           pendientes=[p for p in pendientes if p["zona"] not in enviados_zonas],
                           proyecto=proyecto, credenciales=True)
        _latido(cur, resumen)
    if resumen["fallas"]:
        log.warning("Push con fallas: %s", resumen)
    else:
        log.info("Push: %s", resumen)
    return resumen


# ---------------------------------------------------------------------------------------
# Modo de prueba: un mensaje al tema de una zona, sin tocar la BD
# ---------------------------------------------------------------------------------------
def prueba(zona: str, abrir=urllib.request.urlopen, ahora: datetime | None = None) -> int:
    """Manda un mensaje de prueba al tema zona_<slug>; 0 si FCM lo aceptó, 2 sin credenciales, 1 si falló."""
    ahora = ahora or datetime.now(timezone.utc)
    zona = nombre_departamento(zona) or zona
    cfg = ajustes_push()
    try:
        info = cargar_credenciales(cfg.credenciales)
    except CredencialesInvalidas as e:
        print(f"FIREBASE_CREDENCIALES ilegible: {e}")
        return 2
    if info is None:
        print(AVISO_SIN_CREDENCIALES)
        return 2
    proyecto = cfg.proyecto or info["project_id"]
    hora = ahora.astimezone(HORA_PERU).strftime("%d/%m %H:%M")
    cuerpo = f"Mensaje de prueba del avisador de SIMPAC ({hora}). Si lo ves, las notificaciones de tu zona funcionan."
    mensaje = {**armar_mensaje(zona, "prueba", cuerpo, ahora, "prueba"), "topic": tema_zona(zona)}
    try:
        token = token_vigente(info, abrir)
        mensaje_id = enviar(mensaje, proyecto, token, abrir)
    except (CredencialesInvalidas, FallaEnvio, OSError, ValueError, KeyError, RuntimeError) as e:
        print(f"no se pudo enviar al tema {tema_zona(zona)} del proyecto {proyecto}: {e}")
        return 1
    print(f"enviado al tema {tema_zona(zona)} del proyecto {proyecto}: {mensaje_id or '(sin id)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avisador push de SIMPAC (FCM).")
    parser.add_argument("--prueba", action="store_true", help="manda un mensaje de prueba al tema de --zona y no toca la BD")
    parser.add_argument("--zona", default="Cajamarca", help="departamento para --prueba (por defecto Cajamarca)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.prueba:
        return prueba(args.zona)
    resumen = actualizar()
    print(json.dumps(resumen, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
