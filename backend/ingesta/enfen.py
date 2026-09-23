"""
ENFEN: estado del Sistema de Alerta ante El Niño / La Niña costeros y el ICEN al día.

El comunicado oficial sale cada ~2 semanas como PDF, sin API. La tarea Celery 'enfen'
(cada 6 h, en el mismo worker y beat de la ingesta) descubre el último comunicado, lo lee
y lo guarda en la tabla comunicado_enfen.

Los comunicados no traen el valor del ICEN; el Informe Técnico ENFEN sí (Tabla 3), y
suele ir meses por delante del IGP. La tarea lo baja solo si es posterior al último leído
(pesa ~17 MB) y escribe en indice el ICEN más reciente (si es más nuevo que el que hay) y
el ICEN_TMP (sin retroceder de mes), y en icen_serie TODOS los meses de la tabla
(normalmente 12) con origen ENFEN y la categoría oficial de la tabla: el IGP ya no los pisa
(guardar.SQL_ICEN_SERIE; la categoría de los meses del IGP la calcula SIMPAC).

Relleno de la serie: si icen_serie existe y no tiene ningún mes del ENFEN (la tabla es
nueva y el informe vigente se leyó antes de que existiera), se relee UNA vez el informe
vigente aunque ya figure como leído. Al escribir sus meses la condición deja de cumplirse,
así que no se vuelve a bajar. Si al releer resulta uno más viejo que el ya leído (un
listado atrasado), sus meses van a la serie, pero ni el indice ni lo "leído" retroceden; a
la serie le faltan los meses más nuevos del vigente, así que queda la marca
'serie_pendiente' (con aviso en el latido) y se relee otra vez cuando pasen 24 h (como con
el informe fallido), hasta que la relectura dé el mismo informe o uno más nuevo, o llegue
un informe nuevo. Si la tabla todavía no existe (migración pendiente), la serie se salta
con un aviso.

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
  icen_serie       meses del informe escritos en icen_serie en esta corrida: insertados o
                   cambiados (los que ya estaban iguales no cuentan; 0 si ninguno)
  serie_pendiente  informe más viejo que el leído que halló la última relectura y cuándo
                   (url, publicado, numero, fecha, ts): la serie quedó incompleta y el
                   vigente se relee cuando pasen 24 h. None si la serie está al día.
  fallas           "comunicado" y/o "informe" (este también si está en espera)
  avisos           detalle: fuentes caídas, PDF ilegibles, informe en espera, falta la
                   tabla icen_serie, serie incompleta...

Corrida suelta, dentro del contenedor worker:
    docker compose run --rm worker python -m backend.ingesta.enfen
"""
from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from backend.connectors import enfen
from backend.db import conectar
from backend.ingesta.guardar import (AVISO_SIN_SERIE, SQL_ICEN, SQL_ICEN_SERIE, SQL_ICEN_TMP, SQL_LATIDO,
                                     filas_serie, hay_icen_serie)

log = logging.getLogger(__name__)

SQL_COMUNICADO = (
    "insert into comunicado_enfen (anio, numero, extraordinario, fecha, estado, proximo, resumen, url) "
    "values (%s,%s,%s,%s,%s,%s,%s,%s) "
    "on conflict (anio, numero, extraordinario) do update set fecha=excluded.fecha, "
    "estado=excluded.estado, proximo=excluded.proximo, resumen=excluded.resumen, url=excluded.url, "
    "ts_captura=now()"
)
SQL_LATIDO_PREVIO = "select resumen from latido where servicio = %s"
SQL_MESES_SERIE = "select count(*) from icen_serie where origen = %s"


def _previo() -> tuple[dict, int | None]:
    """
    Resumen de la corrida anterior (de ahí salen el informe leído y el descartado) y
    cuántos meses del ENFEN tiene icen_serie (None: la tabla todavía no existe).
    """
    meses = None
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_LATIDO_PREVIO, ("enfen",))
        fila = cur.fetchone()
        if hay_icen_serie(cur):
            cur.execute(SQL_MESES_SERIE, ("ENFEN",))
            meses = cur.fetchone()[0]
    resumen = fila[0] if fila else None
    return (resumen if isinstance(resumen, dict) else {}), meses


def _error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _releer(leido: enfen.ReferenciaInforme | None, meses_serie: int | None,
            pendiente: enfen.ReferenciaInforme | None, ahora: datetime) -> bool:
    """
    Si hay que releer el informe vigente (aunque ya figure como leído) para llenar
    icen_serie: la serie no tiene meses del ENFEN, o una relectura anterior halló uno más
    viejo que el leído (`pendiente`). En ese caso, como mucho una vez cada ESPERA_FALLIDO
    (24 h): el informe pesa ~17 MB y un listado atrasado tarda en ponerse al día. Sin
    informe leído no hace falta (la consulta normal ya baja el vigente) y sin la tabla, no
    se puede.
    """
    if leido is None or meses_serie is None:
        return False
    if pendiente is not None:
        return pendiente.ts is None or not timedelta(0) <= ahora - pendiente.ts < enfen.ESPERA_FALLIDO
    return meses_serie == 0


def _aviso_pendiente(pendiente: enfen.ReferenciaInforme) -> str:
    cuando = (f"desde {(pendiente.ts + enfen.ESPERA_FALLIDO).astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC"
              if pendiente.ts else "en la próxima corrida")
    return ("icen_serie incompleta: al releer el Informe Técnico vigente se halló uno anterior al leído "
            f"({pendiente.url}); se vuelve a releer {cuando}")


def _frente(nuevo: enfen.ReferenciaInforme, leido: enfen.ReferenciaInforme) -> str:
    """
    El informe releído para llenar la serie frente al ya leído: 'mismo', 'nuevo' o 'viejo'.
    Por URL, por portada si las dos la tienen y si no por la fecha de los listados (el
    mismo informe aparece en SENAMHI y gob.pe con días de diferencia). Sin fechas no se
    puede saber: 'nuevo', como en el conector (las reglas SQL igual impiden retroceder).
    """
    if nuevo.url == leido.url or nuevo.url in leido.alias:
        return "mismo"
    if nuevo.fecha and leido.fecha:
        a, b, margen = nuevo.fecha, leido.fecha, None
    elif nuevo.publicado and leido.publicado:
        a, b, margen = nuevo.publicado, leido.publicado, enfen.MISMO_INFORME
    else:
        return "nuevo"
    if a == b or (margen is not None and abs(a - b) <= margen):
        return "mismo"
    return "nuevo" if a > b else "viejo"


def _tras_relectura(nuevo: enfen.ReferenciaInforme, leido: enfen.ReferenciaInforme) -> tuple[enfen.ReferenciaInforme, bool]:
    """
    Lo "leído" después de releer el informe vigente para llenar la serie, y si el informe
    releído es uno más viejo que el ya leído (entonces el indice no se toca). El mismo
    informe conserva sus otras URL como alias (y gana número y portada si le faltaban).
    """
    frente = _frente(nuevo, leido)
    if frente == "viejo":
        return leido, True
    if frente == "nuevo":
        return nuevo, False
    publicados = [f for f in (nuevo.publicado, leido.publicado) if f]
    alias = sorted((set(leido.alias) | set(nuevo.alias) | {leido.url}) - {nuevo.url})
    return replace(nuevo, alias=alias, publicado=max(publicados) if publicados else None), False


def actualizar() -> dict:
    previo, meses_serie = _previo()
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
    # icen_serie sin meses del ENFEN (tabla nueva): se relee una vez el informe vigente
    # aunque ya figure como leído. Al guardar sus meses deja de cumplirse. Si esa relectura
    # halló uno más viejo, la marca 'serie_pendiente' la repite cada 24 h hasta dar con él.
    pendiente = enfen.ReferenciaInforme.de_json(previo.get("serie_pendiente"))
    ahora = _ahora()
    releer = _releer(leido, meses_serie, pendiente, ahora)
    if releer:
        log.info("ENFEN: %s: se relee el Informe Técnico vigente",
                 "icen_serie quedó con un informe más viejo" if pendiente else "icen_serie no tiene meses del ENFEN")
    informe = None          # el leído en esta corrida: todos sus meses van a icen_serie
    informe_indice = None   # el que actualiza la tabla indice (nunca uno más viejo que el leído)
    try:
        consulta = enfen.informe_tecnico_icen(None if releer else leido, fallido)
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
        informe = consulta.informe
        viejo = False
        if releer and informe and consulta.leido:
            leido, viejo = _tras_relectura(consulta.leido, leido)
            if viejo:
                log.warning("ENFEN: el informe releído (%s) es anterior al ya leído (%s): solo llena icen_serie "
                            "y se vuelve a releer en %s", consulta.leido.url, leido.url, enfen.ESPERA_FALLIDO)
                pendiente = replace(consulta.leido, ts=ahora)
        else:
            leido = consulta.leido or leido
        if informe and not viejo:
            informe_indice = informe
            fallido = None
            pendiente = None   # el mismo informe o uno más nuevo: la serie queda al día
        if consulta.en_espera:
            fallas.append("informe")
    # Mientras la marca siga, el latido lo dice (no solo en la corrida que la puso).
    if pendiente is not None:
        avisos.append(_aviso_pendiente(pendiente))

    # Los comunicados no traen el ICEN: esa rama queda para el día en que lo incluyan.
    # "AAAA-MM" ordena bien: max() es el mes más reciente.
    icen_c = c.icen if c else []
    tmp_c = c.icen_tmp if c else None
    icen = max(icen_c + (informe_indice.icen if informe_indice else []), default=None)
    icen_tmp = max(filter(None, (tmp_c, informe_indice.icen_tmp if informe_indice else None)), default=None)

    # Serie mensual: todos los meses de la tabla del informe leído en esta corrida, con
    # precedencia sobre el IGP. (No los de un comunicado: se relee cada 6 h y podría
    # deshacer la corrección de un informe posterior.)
    serie = []
    if meses_serie is None:
        avisos.append(AVISO_SIN_SERIE)
    elif informe:
        serie = filas_serie(informe.icen, "ENFEN")

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
        "icen_serie": 0,   # meses escritos: se completa al guardarlos, antes del latido
        "serie_pendiente": pendiente.a_json() if pendiente else None,
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
        if serie:
            cur.executemany(SQL_ICEN_SERIE, serie)
            # psycopg suma las filas afectadas del executemany: los meses sin cambios no cuentan
            resumen["icen_serie"] = cur.rowcount
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
