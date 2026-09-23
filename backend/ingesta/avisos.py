"""
Avisos oficiales de SENAMHI: áreas sombreadas en el mapa y alertas por departamento.

La tarea 'avisos' (cada hora) llama a actualizar(), que:
  1. Lee la tabla de avisos meteorológicos y se queda con los emitidos o vigentes (sin los
     cancelados, los terminados ni los originales de una actualización vigente: "(ACTUALIZACIÓN
     DEL AVISO 373)" reemplaza al 373, que puede seguir listado a la vez).
  2. Baja por WFS los polígonos de cada aviso nuevo, guardado hace más de REFRESCO_HORAS o
     de lluvia sin ícono (guardado antes de la migración de íconos): el polígono de un aviso
     no cambia una vez emitido (las correcciones salen con otro número) y la GeoServer es
     lenta (un aviso de temperatura pesa 1,3 MB por día). Si a alguno de esos le falta el
     párrafo general o, si es de lluvia, el de algún día, lee la página de avisos vigentes
     (una vez, opcional; si cae se usan los textos guardados). Un texto que falta se reintenta
     así cada REFRESCO_HORAS, no en cada corrida.
  3. Baja el aviso de lluvia de 24 h (siempre, cambia cada día).
  4. En una transacción (con un candado para que dos corridas no se pisen): reemplaza en
     aviso_senamhi lo de las fuentes que respondieron (la geometría se une por nivel y se
     simplifica en SQL, los departamentos salen de las estaciones que caen dentro y las
     anclas del ícono, del mayor círculo inscrito de cada parte), y genera las alertas.

Íconos y lectura del texto (backend/ingesta/lectura_aviso.py; derivados, el frontend los
rotula "basado en el aviso de SENAMHI"): cada fila guarda el párrafo oficial de su día
(texto_dia; None si su fecha no es la del mapa), el ícono (gota, gota con rayo o copo; None si
no es de lluvia) y la lectura del párrafo general (descargas, granizo, ráfagas, mm/día...). Si
la tabla aún no tiene esas columnas (migración de íconos pendiente), los avisos se guardan
igual, sin íconos (SQL_PREVIOS_V1, SQL_AREA_V1), y el latido lo avisa.

Regla de "no borrar lo que no se pudo consultar": si la tabla no responde (o trae una fila
activa que no se entiende, o una sin etiqueta que aún no termina), los avisos meteorológicos
guardados se quedan y solo se reemplaza lo que se volvió a bajar; si falla el WFS de un aviso
(o no trae polígonos), se queda lo suyo; si falla el de 24 h (o su vista está vacía o
detenida), igual. Lo terminado (fin pasado) se borra siempre, y el original de una
actualización también, salvo que la actualización no se haya podido bajar nunca (entonces el
original se queda hasta que se pueda). Con las alertas pasa lo mismo que en
backend/ingesta/guardar.py: se reemplazan las de los avisos re-evaluados y las que no se
refrescan caducan a las SIN_DATOS_HORAS; además, la de un aviso que ya no tiene áreas de
lluvia sin terminar se borra aunque su fuente esté caída.

Alertas: una por aviso de lluvia (tema 'lluvia', o el de 24 h) vigente o que empieza en las
próximas VENTANA_ALERTA_HORAS, y por departamento cubierto. Si un área del aviso cae en la
ventana, cuentan todas sus áreas sin terminar (la alerta dice la vigencia completa, no solo
los primeros días). tipo 'aviso', zona = departamento, nivel: Nivel 2 (amarillo) -> 'aviso',
Nivel 3 (naranja) -> 'alerta', Nivel 4 (rojo) -> 'emergencia'. Referencia estable: 'SENAMHI
aviso 376' o 'SENAMHI lluvia 24h'.

Resumen del latido 'avisos':
  vigentes      números emitidos o vigentes según la tabla (None si la tabla no respondió)
  bajados       avisos cuyos polígonos se bajaron en esta corrida
  reusados      avisos que ya estaban guardados y no se volvieron a bajar
  areas         filas (aviso, mapa, nivel) escritas
  lluvia24h     fecha del aviso de 24 h vigente (None si no hay o si no respondió)
  alertas       alertas escritas
  fallas        'tabla', 'tabla incompleta', 'aviso N' (WFS caído o sin polígonos), 'lluvia24h',
                'migracion' (falta la tabla)
  avisos        detalle: errores, polígonos descartados, actualizaciones, aviso de 24 h
                desactualizado, página de textos caída, migración de íconos pendiente...
  lectura       de las filas escritas: iconos ({"376": "gota", "24h": "gota"}),
                fecha_no_coincide (["aviso 375 mapa 2"]: párrafo de otro día, no se guarda),
                mm_literal (con párrafo del día pero sin mm/día leídos: se muestra literal) y
                sin_general (avisos de lluvia sin párrafo general: se reintentan cada
                REFRESCO_HORAS). None sin la migración de íconos.

Corrida suelta, dentro del contenedor worker:
    docker compose run --rm worker python -m backend.ingesta.avisos
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, time, timedelta, timezone
from typing import NamedTuple

from backend.connectors import senamhi_avisos as fuente
from backend.connectors.senamhi import HORA_PERU
from backend.db import conectar
from backend.ingesta import lectura_aviso
from backend.ingesta.guardar import SIN_DATOS_HORAS, SQL_ALERTA, SQL_LATIDO
from backend.ingesta.lectura_aviso import en_claro, intensidad

log = logging.getLogger(__name__)

TOLERANCIA_GRADOS = 0.005     # simplificación de los polígonos (~550 m)
REFRESCO_HORAS = 6            # un aviso ya guardado se vuelve a bajar pasado este tiempo
VENTANA_ALERTA_HORAS = 48     # alerta si el aviso está vigente o empieza dentro de 48 h
REF_24H = "SENAMHI lluvia 24h"
NIVEL_ALERTA = {2: "aviso", 3: "alerta", 4: "emergencia"}

# Título oficial del producto (encabezado de https://www.senamhi.gob.pe/?p=aviso-24H).
TITULO_24H = "AVISO DE CORTO PLAZO ANTE LLUVIAS INTENSAS"
# Texto oficial de cada nivel en el visor https://www.senamhi.gob.pe/mapas/mapa-24H/
DESCRIPCION_24H = {
    2: "Pronóstico de precipitaciones acumuladas en 24 horas de intensidad moderada.",
    3: "Pronóstico de precipitaciones acumuladas en 24 horas de intensidad fuerte y pueden "
       "producir aniegos e inundaciones pluviales.",
    4: "Pronóstico de precipitaciones acumuladas en 24 horas de intensidad extrema y pueden "
       "producir inundaciones pluviales.",
}
_TEXTO_24H = {
    2: "Lluvia de intensidad moderada",
    3: "Lluvia de intensidad fuerte, con posibles aniegos e inundaciones",
    4: "Lluvia de intensidad extrema, con posibles inundaciones",
}

# Las migraciones de aviso_senamhi pueden no estar aplicadas todavía (el worker se despliega
# aparte): sin la tabla no se hace nada; con la tabla pero sin las columnas de íconos (texto_dia,
# icono, lectura, anclas) los avisos oficiales se siguen guardando, sin íconos.
SQL_HAY_TABLA = (
    "select to_regclass('public.aviso_senamhi') is not null, "
    "exists (select 1 from information_schema.columns where table_schema = 'public' "
    "and table_name = 'aviso_senamhi' and column_name = 'anclas')"
)
AVISO_SIN_TABLA = "aviso_senamhi: falta la tabla (migración pendiente); no se consultó ni se guardó nada"
AVISO_SIN_ICONOS = "aviso_senamhi: falta la migración de íconos; se guardan sin íconos"
# Avisos guardados (para no volver a bajarlos): año, número, captura, párrafo general,
# párrafos por día ({"1": "El miércoles 23..."}) y si es de lluvia y no tiene ícono (se guardó
# antes de la migración de íconos): ese se vuelve a bajar aunque sea reciente. Uno guardado
# después siempre tiene ícono (gota, si no se leyó su párrafo general): no se mira la lectura,
# porque un aviso cuyo párrafo no está en la página se volvería a pedir al WFS cada hora durante
# toda su vigencia; sus textos se reintentan cada REFRESCO_HORAS, con los polígonos.
SQL_PREVIOS = (
    "select anio, numero, min(ts_captura), max(descripcion), "
    "coalesce(jsonb_object_agg(mapa, texto_dia) filter (where texto_dia is not null), '{}'::jsonb), "
    "bool_or(tema = 'lluvia' and icono is null) "
    "from aviso_senamhi where tipo = 'meteorologico' and fin > now() group by anio, numero"
)
SQL_PREVIOS_V1 = (   # sin la migración de íconos
    "select anio, numero, min(ts_captura), max(descripcion) from aviso_senamhi "
    "where tipo = 'meteorologico' and fin > now() group by anio, numero"
)
# Candado de la transacción de escritura: la tabla alerta no tiene clave única, así que dos
# corridas a la vez (beat + una corrida suelta) duplicarían las alertas. Se suelta al commit.
SQL_CANDADO = "select pg_advisory_xact_lock(hashtext('avisos'))"
SQL_BORRAR_TERMINADOS = "delete from aviso_senamhi where fin <= now()"
# Avisos meteorológicos (clave 'año-número'): se van los re-bajados (se vuelven a insertar) y
# los originales de una actualización y, si la tabla se leyó entera, todos los que no se
# conservan (los que fallaron y los reusados se quedan; lo demás ya no está emitido ni
# vigente, o fue cancelado).
SQL_BORRAR_METEOROLOGICO = (
    "delete from aviso_senamhi where tipo = 'meteorologico' and ("
    "concat(anio, '-', numero) = any(%s::text[]) "
    "or (%s::boolean and concat(anio, '-', numero) <> all(%s::text[])))"
)
SQL_BORRAR_24H = "delete from aviso_senamhi where tipo = 'lluvia24h'"
# Une los polígonos del mismo nivel, los simplifica y calcula los departamentos cubiertos:
# los de las estaciones que caen dentro o, si no cae ninguna (un área chica), el de la
# estación más cercana a un punto interior del área, siempre que esté a menos de 0,1° (~11
# km) del área: un área mar adentro o en la frontera se queda sin departamento en vez de
# asignarse al más cercano, aunque esté lejos (un polígono frente a Piura caía en Piura).
_SQL_AREA_VALORES = """
select %(tipo)s::text, %(anio)s::int, %(numero)s::int, %(mapa)s::smallint, %(nivel)s::smallint,
       %(titulo)s::text, %(tema)s::text, %(descripcion)s::text, %(emision)s::date,
       %(inicio)s::timestamptz, %(fin)s::timestamptz, %(url)s::text, g.geom,
       coalesce(
         (select array_agg(distinct e.departamento order by e.departamento) from estacion e
           where e.departamento is not null and st_intersects(g.geom, e.geom)),
         (select array[e.departamento] from estacion e where e.departamento is not null
           and st_dwithin(e.geom, g.geom, 0.1)
           order by e.geom <-> st_pointonsurface(g.geom) limit 1),
         '{}')"""
_SQL_AREA_GEOMETRIA = """
from (
  select st_multi(st_collectionextract(st_union(p.geom), 3)) as geom
  from (
    select st_collectionextract(st_makevalid(st_simplifypreservetopology(
             st_makevalid(st_force2d(st_setsrid(st_geomfromgeojson(e.valor), 4326))),
             %(tolerancia)s::float8)), 3) as geom
    from jsonb_array_elements_text(%(geometrias)s::jsonb) as e(valor)
  ) p
) g
where not st_isempty(g.geom)
on conflict on constraint aviso_senamhi_clave do update set
  titulo = excluded.titulo, tema = excluded.tema, descripcion = excluded.descripcion,
  emision = excluded.emision, inicio = excluded.inicio, fin = excluded.fin, url = excluded.url,
  geom = excluded.geom, departamentos = excluded.departamentos,"""
# Dónde va el ícono (anclas): una entrada por parte del MultiPolygon de 300 km² o más (y
# siempre la más grande), en el centro del mayor círculo inscrito (el centroide de una parte
# en forma de C cae afuera; si el centro quedara fuera por redondeo, un punto interior).
# 'parte' es el índice (desde 1) en geojson.coordinates de aviso_vigente: st_dump y
# st_asgeojson recorren las partes en el mismo orden. radio_km sirve al frontend para ocultar
# el ícono de una parte que en pantalla se ve chica. La misma subconsulta, sobre a.geom, está
# en la migración de íconos para las filas ya guardadas.
_SQL_ANCLAS = """(
         select coalesce(jsonb_agg(jsonb_build_object(
                  'parte', x.parte, 'lon', round(st_x(x.p)::numeric, 4), 'lat', round(st_y(x.p)::numeric, 4),
                  'radio_km', round(x.radio_km::numeric, 1), 'km2', round(x.km2::numeric)::int, 'mayor', x.orden = 1)
                order by x.orden), '[]'::jsonb)
         from (select (d.path)[1] as parte,
                      case when st_intersects(d.geom, c.center) then c.center else st_pointonsurface(d.geom) end as p,
                      st_distance(c.center::geography, c.nearest::geography) / 1000 as radio_km,
                      st_area(d.geom::geography) / 1e6 as km2,
                      row_number() over (order by st_area(d.geom::geography) desc) as orden
                 from st_dump(g.geom) d
                 cross join lateral st_maximuminscribedcircle(d.geom) c) x
         where x.orden = 1 or x.km2 >= 300)"""
# insert + _SQL_AREA_VALORES + columnas de íconos + _SQL_AREA_GEOMETRIA (from, on conflict).
SQL_AREA = (
    "\ninsert into aviso_senamhi (tipo, anio, numero, mapa, nivel, titulo, tema, descripcion, emision,\n"
    "                           inicio, fin, url, geom, departamentos, texto_dia, icono, lectura, anclas)"
    + _SQL_AREA_VALORES + ",\n"
    "       %(texto_dia)s::text, %(icono)s::text, %(lectura)s::jsonb,\n"
    "       " + _SQL_ANCLAS
    + _SQL_AREA_GEOMETRIA
    + "\n  texto_dia = excluded.texto_dia, icono = excluded.icono, lectura = excluded.lectura,"
    "\n  anclas = excluded.anclas, ts_captura = now()\n"
)
SQL_AREA_V1 = (   # sin la migración de íconos: las mismas filas, sin sus columnas
    "\ninsert into aviso_senamhi (tipo, anio, numero, mapa, nivel, titulo, tema, descripcion, emision,\n"
    "                           inicio, fin, url, geom, departamentos)"
    + _SQL_AREA_VALORES + _SQL_AREA_GEOMETRIA + " ts_captura = now()\n"
)
# Todas las áreas de lluvia sin terminar, ya con los borrados e inserciones de esta
# transacción. De aquí salen las alertas (la ventana de 48 h se aplica por aviso en
# en_ventana) y la lista de avisos que aún tienen áreas (sus alertas pueden quedarse).
SQL_LLUVIA_VIGENTE = (
    "select tipo, anio, numero, nivel, titulo, descripcion, inicio, fin, departamentos "
    "from aviso_senamhi where tema = 'lluvia' and fin > now()"
)
# Familia de alertas de esta tarea: tipo 'aviso' con referencia 'SENAMHI ...'. Se borran las
# re-evaluadas, las que no se refrescan hace SIN_DATOS_HORAS, si la tabla se leyó entera las
# de avisos que ya no están emitidos ni vigentes (salvo las de avisos cuyo WFS falló) y, en
# todo caso, las de avisos sin áreas de lluvia sin terminar (el último parámetro: las
# referencias de SQL_LLUVIA_VIGENTE), para que no sigan hasta 6 h si la fuente está caída.
SQL_BORRAR_ALERTAS_AVISO = (
    "delete from alerta where tipo = 'aviso' and starts_with(referencia, 'SENAMHI ') and ("
    "referencia = any(%s::text[]) or ts < now() - make_interval(hours => %s) "
    "or (%s::boolean and starts_with(referencia, 'SENAMHI aviso ') and referencia <> all(%s::text[])) "
    "or referencia <> all(%s::text[]))"
)


def _error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def referencia(tipo: str, numero: int | None) -> str:
    return REF_24H if tipo == "lluvia24h" else f"SENAMHI aviso {numero}"


# ---------------------------------------------------------------------------------------
# Lenguaje claro
# ---------------------------------------------------------------------------------------
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic")
_FENOMENO = (("PRECIPITAC", "Lluvias"), ("LLUVIA", "Lluvias"), ("LLOVIZNA", "Llovizna"),
             ("NEVADA", "Nevadas"), ("NIEVE", "Nevadas"), ("GRANIZ", "Granizo"))


def _dia(d) -> str:
    return f"{d.day} {MESES[d.month - 1]}"


def rango_peru(inicio: datetime, fin: datetime) -> str:
    """
    Vigencia en hora de Perú: 'el 23 set', 'del 23 al 24 set', 'del 30 set al 2 oct',
    'desde las 10:00 del 24 set hasta el 26 set', 'desde las 13:00 del 22 set hasta las
    13:00 del 23 set'. Un fin a las 23:59 (o a medianoche) es "hasta el final de ese día".
    """
    i, f = inicio.astimezone(HORA_PERU), fin.astimezone(HORA_PERU)
    if f.time() == time(0, 0):
        f -= timedelta(seconds=1)
    desde_medianoche = i.time() == time(0, 0)
    hasta_fin_de_dia = (f.hour, f.minute) == (23, 59)
    if desde_medianoche and hasta_fin_de_dia:
        if i.date() == f.date():
            return f"el {_dia(i)}"
        if (i.year, i.month) == (f.year, f.month):
            return f"del {i.day} al {_dia(f)}"
        return f"del {_dia(i)} al {_dia(f)}"
    desde = f"desde el {_dia(i)}" if desde_medianoche else f"desde las {i:%H:%M} del {_dia(i)}"
    hasta = f"hasta el {_dia(f)}" if hasta_fin_de_dia else f"hasta las {f:%H:%M} del {_dia(f)}"
    return f"{desde} {hasta}"


def detalle_meteorologico(titulo: str, descripcion: str | None, inicio: datetime, fin: datetime) -> str:
    """'Lluvias de ligera a moderada intensidad en la sierra norte y costa norte, del 23 al 24 set'."""
    t = re.sub(r"\s*\([^)]*\)", "", titulo).strip()   # sin "(ACTUALIZACIÓN DEL AVISO 373)"
    m = re.match(r"(.+?)\s+EN\s+(.+)$", t, re.I)
    que, donde = (m.group(1), m.group(2)) if m else (t, None)
    que_plano = fuente.plano(que)
    partes = [next((txt for clave, txt in _FENOMENO if clave in que_plano), que.capitalize())]
    fuerza = intensidad(descripcion)
    if fuerza:
        partes.append(fuerza)
    if donde:
        partes.append(f"en {en_claro(donde)}")
    return f"{' '.join(partes)}, {rango_peru(inicio, fin)}"


def detalle_24h(nivel: int, inicio: datetime, fin: datetime) -> str:
    """'Lluvia de intensidad moderada (pronóstico de 24 h), desde las 13:00 del 22 set hasta ...'."""
    return f"{_TEXTO_24H[nivel]} (pronóstico de 24 h), {rango_peru(inicio, fin)}"


# ---------------------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------------------
def en_ventana(filas: list[tuple], ahora: datetime) -> list[tuple]:
    """
    Todas las áreas de los avisos que tienen al menos una que empieza antes de ahora +
    VENTANA_ALERTA_HORAS. Se decide por aviso y no por área: la alerta de un aviso del 23 al
    25 dice "del 23 al 25" aunque el 25 quede fuera de la ventana.
    """
    limite = ahora + timedelta(hours=VENTANA_ALERTA_HORAS)
    dentro = {(tipo, anio, numero) for tipo, anio, numero, _n, _t, _d, inicio, *_ in filas if inicio < limite}
    return [f for f in filas if (f[0], f[1], f[2]) in dentro]


def alertas_de_avisos(filas: list[tuple]) -> list[dict]:
    """
    filas: (tipo, anio, numero, nivel, titulo, descripcion, inicio, fin, departamentos) de las
    áreas de lluvia re-evaluadas. Una alerta por aviso y departamento, con el nivel más alto
    y la vigencia de las áreas que cubren ese departamento.
    """
    grupos: dict[tuple[str, str], dict] = {}
    for tipo, _anio, numero, nivel, titulo, descripcion, inicio, fin, departamentos in filas:
        ref = referencia(tipo, numero)
        for depto in departamentos or []:
            g = grupos.get((ref, depto))
            if g is None:
                grupos[(ref, depto)] = {"tipo": tipo, "nivel": nivel, "titulo": titulo,
                                        "descripcion": descripcion, "inicio": inicio, "fin": fin}
            else:
                g["nivel"] = max(g["nivel"], nivel)
                g["inicio"], g["fin"] = min(g["inicio"], inicio), max(g["fin"], fin)
    out = []
    for (ref, depto), g in sorted(grupos.items()):
        if g["tipo"] == "lluvia24h":
            detalle = detalle_24h(g["nivel"], g["inicio"], g["fin"])
        else:
            detalle = detalle_meteorologico(g["titulo"], g["descripcion"], g["inicio"], g["fin"])
        out.append({"tipo": "aviso", "referencia": ref, "zona": depto,
                    "nivel": NIVEL_ALERTA[g["nivel"]], "detalle": detalle,
                    "valor": None, "umbral": None})
    return out


# ---------------------------------------------------------------------------------------
# Tarea
# ---------------------------------------------------------------------------------------
class Guardado(NamedTuple):
    """Lo que ya está en aviso_senamhi de un aviso meteorológico."""
    ts: datetime                 # primera captura
    general: str | None          # párrafo general
    dias: dict[int, str]         # mapa -> párrafo de ese día
    incompleto: bool             # de lluvia y sin ícono (anterior a la migración): se vuelve a bajar


def _previos() -> tuple[dict[tuple[int, int], Guardado], bool] | None:
    """Avisos meteorológicos guardados y si la tabla ya tiene las columnas de íconos; None
    si la tabla aún no existe."""
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_HAY_TABLA)
        fila = cur.fetchone()
        if not (fila and fila[0]):
            return None
        con_iconos = bool(fila[1])
        cur.execute(SQL_PREVIOS if con_iconos else SQL_PREVIOS_V1)
        previos = {}
        for anio, numero, ts, general, *resto in cur.fetchall():
            dias, incompleto = resto or ({}, False)
            previos[(anio, numero)] = Guardado(ts, general, {int(m): t for m, t in (dias or {}).items()},
                                               bool(incompleto))
        return previos, con_iconos


def _resumen(fallas: list[str], avisos: list[str], **datos) -> dict:
    base = {"vigentes": None, "bajados": [], "reusados": [], "areas": 0, "lluvia24h": None, "alertas": 0,
            "lectura": None}
    return {**base, **datos, "fallas": fallas, "avisos": avisos}


def notas_lectura() -> dict:
    """Bloque 'lectura' del latido (ver el docstring del módulo), vacío."""
    return {"iconos": {}, "fecha_no_coincide": [], "mm_literal": [], "sin_general": []}


def _anotar(lista: list, valor) -> None:
    if valor not in lista:   # un mapa tiene una fila por nivel: se anota una vez
        lista.append(valor)


def _fila_area(area: fuente.Area, aviso: fuente.Aviso | None, texto: fuente.TextoAviso | None,
               notas: dict | None = None) -> dict:
    """
    Parámetros de SQL_AREA para un área. `texto`: los textos oficiales del aviso (None si no
    se leyeron). `notas`: el bloque 'lectura' del latido, donde se anota lo que no se leyó.
    El párrafo de un día se guarda solo si su fecha es la del mapa (lectura_aviso.es_del_dia; o
    si no trae fecha): la página a veces repite el de otro día ("El martes 22..." en el mapa del
    jueves 24).
    """
    notas = notas_lectura() if notas is None else notas
    general = texto_dia = None
    if aviso is None:   # lluvia de 24 h
        titulo, tema, emision, url = TITULO_24H, "lluvia", area.inicio.astimezone(HORA_PERU).date(), fuente.URL_AVISO_24H
        descripcion = DESCRIPCION_24H[area.nivel]
    else:
        titulo, tema, emision, url = aviso.titulo, aviso.tema, aviso.emision, aviso.url
        general = descripcion = texto.general if texto else None
        texto_dia = texto.dias.get(area.mapa) if texto else None
        fecha_mapa = area.inicio.astimezone(HORA_PERU).date()
        if texto_dia and not lectura_aviso.es_del_dia(texto_dia, fecha_mapa):
            _anotar(notas["fecha_no_coincide"], f"aviso {area.numero} mapa {area.mapa}")
            texto_dia = None
    leido = icono = None
    if tema == "lluvia":
        leido = lectura_aviso.lectura(area.tipo, titulo, general, texto_dia)
        icono = lectura_aviso.icono_aviso(area.tipo, titulo, leido)
        if icono:
            notas["iconos"]["24h" if area.numero is None else str(area.numero)] = icono
        if aviso is not None and not general:
            _anotar(notas["sin_general"], area.numero)
        if texto_dia and not (leido or {}).get("montos"):
            _anotar(notas["mm_literal"], f"aviso {area.numero} mapa {area.mapa}")
    return {"tipo": area.tipo, "anio": area.anio, "numero": area.numero, "mapa": area.mapa,
            "nivel": area.nivel, "titulo": titulo, "tema": tema, "descripcion": descripcion,
            "emision": emision, "inicio": area.inicio, "fin": area.fin, "url": url,
            "geometrias": json.dumps(area.geometrias), "tolerancia": TOLERANCIA_GRADOS,
            "texto_dia": texto_dia, "icono": icono,
            "lectura": json.dumps(leido, ensure_ascii=False) if leido else None}


def actualizar(ahora: datetime | None = None) -> dict:
    """La tarea Celery la llama sin argumentos; `ahora` (UTC) es para las pruebas."""
    ahora = ahora or datetime.now(timezone.utc)
    hoy = ahora.astimezone(HORA_PERU).date()
    fallas: list[str] = []
    avisos: list[str] = []
    guardados = _previos()
    if guardados is None:
        resumen = _resumen(["migracion"], [AVISO_SIN_TABLA])
        with conectar() as conn, conn.cursor() as cur:
            cur.execute(SQL_LATIDO, ("avisos", json.dumps(resumen)))
        log.warning("Avisos SENAMHI: %s", AVISO_SIN_TABLA)
        return resumen
    previos, con_iconos = guardados
    if not con_iconos:   # los avisos oficiales se guardan igual, sin íconos
        avisos.append(AVISO_SIN_ICONOS)
        log.warning("Avisos SENAMHI: %s", AVISO_SIN_ICONOS)

    # 1) Qué avisos meteorológicos están emitidos o vigentes.
    tabla = None
    try:
        tabla = fuente.tabla_avisos(hoy)
        if tabla.problemas:   # una fila activa ilegible o sin etiqueta: no se sabe si ese aviso sigue
            fallas.append("tabla incompleta")
            avisos += [f"tabla de avisos: {p}" for p in tabla.problemas]
    except Exception as e:
        log.error("Avisos SENAMHI: no se pudo leer la tabla: %s", _error(e))
        fallas.append("tabla")
        avisos.append(f"tabla de avisos: {_error(e)}")
    listados = [a for a in (tabla.avisos if tabla else []) if not a.cancelado and a.fin_utc > ahora]
    # Una actualización reemplaza a su original, que puede seguir listado como vigente: si se
    # quedara, habría polígonos y alertas duplicados, y los del original con el nivel viejo.
    reemplazos = {a.actualiza: a for a in listados if a.actualiza}
    activos = [a for a in listados if (a.anio, a.numero) not in reemplazos]
    # Un aviso de lluvia guardado sin ícono se vuelve a bajar aunque sea reciente: así los
    # guardados antes de la migración de íconos se completan solos.
    reusar = [a for a in activos if (a.anio, a.numero) in previos
              and ahora - previos[(a.anio, a.numero)].ts < timedelta(hours=REFRESCO_HORAS)
              and not previos[(a.anio, a.numero)].incompleto]
    bajar = [a for a in activos if a not in reusar]

    # 2) Textos oficiales (opcionales): la página de vigentes trae los de todos los avisos y se
    # baja una sola vez, si a algún aviso que se va a bajar le falta el párrafo general o, si es
    # de lluvia, el de alguno de sus días. Lo nuevo se suma a lo guardado; si la página cae,
    # queda lo guardado.
    textos = {k: fuente.TextoAviso(g.general, dict(g.dias)) for k, g in previos.items()}

    def falta_texto(a: fuente.Aviso) -> bool:
        t = textos.get((a.anio, a.numero))
        if t is None or not t.general:
            return True
        return con_iconos and a.tema == "lluvia" and any(m not in t.dias for m in range(1, a.mapas + 1))

    faltan = [a for a in bajar if a.url and falta_texto(a)]
    if faltan:
        try:
            for clave, nuevo in fuente.textos(faltan[0].url).items():
                previo = textos.get(clave) or fuente.TextoAviso(None)
                textos[clave] = fuente.TextoAviso(nuevo.general or previo.general, {**previo.dias, **nuevo.dias})
        except Exception as e:
            log.warning("Avisos SENAMHI: sin textos oficiales: %s", _error(e))
            avisos.append(f"textos oficiales: {_error(e)}")

    # 3) Polígonos de cada aviso. Si falla uno (o no trae polígonos: el aviso sigue en la
    # tabla), lo guardado de ese aviso se conserva.
    filas: list[dict] = []
    fallidos: list[fuente.Aviso] = []
    notas = notas_lectura()
    for a in bajar:
        try:
            areas, descartados = fuente.areas_aviso(a)
            if not areas:   # areas_aviso ya falla con un mapa vacío; esto es por si acaso
                raise ValueError("el WFS no trae polígonos")
        except Exception as e:
            log.warning("Avisos SENAMHI: WFS del aviso %s: %s", a.numero, _error(e))
            fallidos.append(a)
            fallas.append(f"aviso {a.numero}")
            avisos.append(f"aviso {a.numero}: {_error(e)}")
            continue
        if descartados:
            avisos.append(f"aviso {a.numero}: {descartados} polígonos descartados "
                          "(fechas fuera de la vigencia de la tabla o datos incompletos)")
        texto = textos.get((a.anio, a.numero))
        filas += [_fila_area(x, a, texto, notas) for x in areas if x.fin > ahora]

    # Originales de una actualización: se borran (filas y alertas) aunque la tabla no se haya
    # leído entera, salvo que la actualización haya fallado y no esté guardada: sin ella en el
    # mapa, el original se queda hasta que se pueda bajar.
    borrar_originales: list[tuple[int, int]] = []
    conservar_originales: list[tuple[int, int]] = []
    en_tabla = {(a.anio, a.numero) for a in listados}
    for clave, nueva in sorted(reemplazos.items()):
        if nueva in fallidos and (nueva.anio, nueva.numero) not in previos:
            conservar_originales.append(clave)
            if clave in previos:
                avisos.append(f"aviso {clave[1]}: se conserva hasta que se pueda bajar su "
                              f"actualización (aviso {nueva.numero})")
        else:
            borrar_originales.append(clave)
            if clave in en_tabla:
                avisos.append(f"aviso {clave[1]}: reemplazado por su actualización (aviso {nueva.numero})")

    # 4) Aviso de lluvia de 24 h.
    areas_24 = None
    try:
        areas_24 = fuente.aviso_24h(hoy)
    except Exception as e:
        log.warning("Avisos SENAMHI: aviso de lluvia 24 h: %s", _error(e))
        fallas.append("lluvia24h")
        avisos.append(f"lluvia 24 h: {_error(e)}")
    vigentes_24 = [x for x in areas_24 or [] if x.fin > ahora]
    if areas_24 and not vigentes_24:
        fecha = areas_24[0].inicio.astimezone(HORA_PERU).date().isoformat()
        avisos.append(f"lluvia 24 h: el último aviso publicado (del {fecha}) ya terminó")
    filas += [_fila_area(x, None, None, notas) for x in vigentes_24]

    # 5) Escritura, en una sola transacción. Con la tabla entera se sabe qué avisos ya no
    # siguen; si no respondió (o una fila activa no se entendió), solo se reemplaza lo re-bajado.
    tabla_entera = tabla is not None and not tabla.problemas
    ok = {(a.anio, a.numero) for a in activos if a not in fallidos}
    borrar = [f"{a.anio}-{a.numero}" for a in bajar if a not in fallidos]
    borrar += [f"{anio}-{n}" for anio, n in borrar_originales]
    conservar = [f"{a.anio}-{a.numero}" for a in fallidos + reusar]
    conservar += [f"{anio}-{n}" for anio, n in conservar_originales]
    refrescadas = [referencia("meteorologico", n) for _, n in sorted(ok | set(borrar_originales))]
    if areas_24 is not None:
        refrescadas.append(REF_24H)
    alertas_conservar = [referencia("meteorologico", n)
                         for _, n in [(a.anio, a.numero) for a in fallidos] + conservar_originales]
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(SQL_CANDADO)
        cur.execute(SQL_BORRAR_TERMINADOS)
        if borrar or tabla_entera:
            cur.execute(SQL_BORRAR_METEOROLOGICO, (borrar, tabla_entera, conservar))
        if areas_24 is not None:
            cur.execute(SQL_BORRAR_24H)
        if filas:
            cur.executemany(SQL_AREA if con_iconos else SQL_AREA_V1, filas)
        # Después de los borrados e inserciones: lo que queda es lo que se muestra.
        cur.execute(SQL_LLUVIA_VIGENTE)
        sin_terminar = cur.fetchall()
        lluvia = [f for f in en_ventana(sin_terminar, ahora)
                  if (f[0] == "lluvia24h" and areas_24 is not None)
                  or (f[0] == "meteorologico" and (f[1], f[2]) in ok)]
        alertas = alertas_de_avisos(lluvia)
        con_areas = sorted({referencia(f[0], f[2]) for f in sin_terminar})
        cur.execute(SQL_BORRAR_ALERTAS_AVISO, (refrescadas, SIN_DATOS_HORAS, tabla_entera,
                                              alertas_conservar, con_areas))
        if alertas:
            cur.executemany(SQL_ALERTA, [(a["tipo"], a["referencia"], a["zona"], a["nivel"],
                                          a["detalle"], a["valor"], a["umbral"]) for a in alertas])
        resumen = _resumen(
            fallas, avisos,
            vigentes=[a.numero for a in activos] if tabla is not None else None,
            bajados=[a.numero for a in bajar if a not in fallidos],
            reusados=[a.numero for a in reusar],
            areas=len(filas),
            lluvia24h=vigentes_24[0].inicio.astimezone(HORA_PERU).date().isoformat() if vigentes_24 else None,
            alertas=len(alertas),
            lectura=notas if con_iconos else None,
        )
        cur.execute(SQL_LATIDO, ("avisos", json.dumps(resumen)))

    if "tabla" in fallas and "lluvia24h" in fallas:
        # El latido ya lo registró; la excepción hace que Celery marque la tarea como fallida.
        raise RuntimeError("Avisos SENAMHI: fallaron la tabla de avisos y el aviso de 24 h: " + " | ".join(avisos))
    if fallas:
        log.warning("Avisos SENAMHI con fallas parciales: %s", resumen)
    else:
        log.info("Avisos SENAMHI: %s", resumen)
    return resumen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    actualizar()
