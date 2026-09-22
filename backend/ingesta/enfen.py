"""
ENFEN: estado del Sistema de Alerta ante El Niño / La Niña costeros y el ICEN al día.

El comunicado oficial sale cada ~2 semanas como PDF, sin API. La tarea Celery 'enfen'
(cada 6 h, en el mismo worker y beat de la ingesta) descubre el último comunicado, lo lee
y lo guarda en la tabla comunicado_enfen.

Los comunicados no traen el valor del ICEN; el Informe Técnico ENFEN sí (Tabla 3), y
suele ir meses por delante del IGP. La tarea lo baja solo si es posterior al último leído
(pesa ~17 MB) y escribe en indice el ICEN más reciente (si es más nuevo que el que hay) y
el ICEN_TMP (sin retroceder de mes).

Comunicado e informe van por separado: si uno falla, el otro se guarda igual y el problema
queda en 'fallas' y 'avisos' del latido. Si fallan los dos, el latido lo dice y la tarea
termina con excepción, para que Celery la marque como fallida.

Resumen del latido 'enfen':
  comunicado, fecha, estado  del último comunicado leído (si esta vez falló, los de antes)
  informe          último Informe Técnico leído: url, publicado (fecha del listado), numero
                   y fecha (portada). Con esto no se vuelve a bajar el mismo desde otra
                   fuente ni uno más viejo.
  informe_fallido  último informe que se bajó y no sirvió: url, publicado, ts, error. No se
                   vuelve a bajar antes de 24 h (las fallas de red se reintentan siempre).
  icen, icen_tmp   meses que dio el ENFEN
  fallas           "comunicado" y/o "informe" (este también si está en espera)
  avisos           detalle: fuentes caídas, PDF ilegibles, informe en espera...

Corrida suelta, dentro del contenedor worker:
    docker compose run --rm worker python -m backend.ingesta.enfen
"""
from __future__ import annotations

import json
import logging

from backend.connectors import enfen
from backend.db import conectar
from backend.ingesta.guardar import SQL_ICEN, SQL_ICEN_TMP, SQL_LATIDO

log = logging.getLogger(__name__)

SQL_COMUNICADO = (
    "insert into comunicado_enfen (anio, numero, extraordinario, fecha, estado, proximo, resumen, url) "
    "values (%s,%s,%s,%s,%s,%s,%s,%s) "
    "on conflict (anio, numero, extraordinario) do update set fecha=excluded.fecha, "
    "estado=excluded.estado, proximo=excluded.proximo, resumen=excluded.resumen, url=excluded.url, "
    "ts_captura=now()"
)
SQL_LATIDO_PREVIO = "select resumen from latido where servicio = %s"


def _resumen_previo() -> dict:
    """Resumen de la corrida anterior (de ahí salen el informe leído y el descartado)."""
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_LATIDO_PREVIO, ("enfen",))
        fila = cur.fetchone()
    resumen = fila[0] if fila else None
    return resumen if isinstance(resumen, dict) else {}


def _error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def actualizar() -> dict:
    previo = _resumen_previo()
    fallas: list[str] = []
    avisos: list[str] = []   # fuentes caídas o PDF ilegibles (se ven en el latido)

    # 1) Comunicado. Si falla, se sigue con el informe y el latido conserva el anterior.
    c = None
    try:
        c = enfen.ultimo_comunicado()
        avisos += c.avisos
    except Exception as e:
        log.error("ENFEN: no se pudo obtener el comunicado: %s", _error(e))
        fallas.append("comunicado")
        avisos.append(f"comunicado: {_error(e)}")

    # 2) Informe Técnico. Se baja antes de abrir la transacción (no se deja una conexión
    # esperando la descarga). El latido del formato anterior solo traía 'informe_url'.
    leido = enfen.ReferenciaInforme.de_json(previo.get("informe") or previo.get("informe_url"))
    fallido = enfen.ReferenciaInforme.de_json(previo.get("informe_fallido"))
    informe = None
    try:
        consulta = enfen.informe_tecnico_icen(leido, fallido)
    except enfen.InformeDescartado as e:   # se bajó y no sirve: no se vuelve a bajar en 24 h
        fallas.append("informe")
        fallido = e.referencia
        avisos += e.avisos + [f"informe técnico: {_error(e)}"]
    except Exception as e:   # red: se reintenta en la próxima corrida
        log.warning("ENFEN: no se pudo leer el Informe Técnico: %s", _error(e))
        fallas.append("informe")
        avisos.append(f"informe técnico: {_error(e)}")
    else:
        avisos += consulta.avisos
        leido = consulta.leido or leido
        informe = consulta.informe
        if informe:
            fallido = None
        if consulta.en_espera:
            fallas.append("informe")

    # Los comunicados no traen el ICEN: esa rama queda para el día en que lo incluyan.
    # "AAAA-MM" ordena bien: max() es el mes más reciente.
    icen_c = c.icen if c else []
    tmp_c = c.icen_tmp if c else None
    icen = max(icen_c + (informe.icen if informe else []), default=None)
    icen_tmp = max(filter(None, (tmp_c, informe.icen_tmp if informe else None)), default=None)

    if c:
        comunicado = {
            "comunicado": f"{'CE' if c.extraordinario else 'CO'} {c.numero}-{c.anio}",
            "fecha": c.fecha.isoformat(),
            "estado": c.estado,
        }
    else:
        comunicado = {k: previo.get(k) for k in ("comunicado", "fecha", "estado")}
    resumen = {
        **comunicado,
        # informe sin cambios (o fallido): se conserva lo de la corrida anterior, así la
        # próxima no lo vuelve a bajar y el latido sigue diciendo qué ICEN hay
        "informe": leido.a_json() if leido else None,
        "informe_fallido": fallido.a_json() if fallido else None,
        "icen": icen[0] if icen else previo.get("icen"),
        "icen_tmp": icen_tmp[0] if icen_tmp else previo.get("icen_tmp"),
        "fallas": fallas,
        "avisos": avisos,
    }
    with conectar() as conn, conn.cursor() as cur:
        if c:
            cur.execute(SQL_COMUNICADO, (c.anio, c.numero, c.extraordinario, c.fecha, c.estado,
                                         c.proximo, c.resumen, c.url))
        if icen:
            cur.execute(SQL_ICEN, ("ICEN", *icen, "ENFEN"))
        if icen_tmp:
            cur.execute(SQL_ICEN_TMP, ("ICEN_TMP", *icen_tmp, "ENFEN"))
        cur.execute(SQL_LATIDO, ("enfen", json.dumps(resumen)))

    if "comunicado" in fallas and "informe" in fallas:
        # El latido ya lo registró; la excepción hace que Celery marque la tarea como fallida.
        raise RuntimeError("ENFEN: fallaron el comunicado y el Informe Técnico: " + " | ".join(avisos))
    if fallas:
        log.warning("ENFEN con fallas parciales: %s", resumen)
    else:
        log.info("ENFEN: %s", resumen)
    return resumen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    actualizar()
