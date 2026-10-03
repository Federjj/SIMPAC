-- Avisos hidrológicos: una fuente caída no apaga un aviso vigente (regla "nada se borra por una
-- fuente caída", docs/ESTADO.md).
--
-- Antes, aviso_hidrologico_vigente exigía que la lista de SENAMHI se hubiera leído en las
-- últimas 3 h. Si la web de SENAMHI cae (lo más probable justo en una emergencia), un aviso rojo
-- con fin oficial conocido dejaba de verse y la zona del río decía "sin señales de crecida ahora".
-- Ahora un aviso con fin conocido (del detalle) se muestra hasta ese fin aunque la lista no se haya
-- vuelto a leer, como los avisos meteorológicos (aviso_vigente solo mira fin > now()). Sin fin
-- conocido sigue el tope de 3 h desde la última lectura: fin_dia es solo un día.
--
-- rio_senal.avisos_hidro agrega visto_en (última vez que el aviso vino en la lista): con visto_en
-- de más de 3 h, el frontend puede decir que SENAMHI no responde desde esa hora y que el aviso es
-- el último conocido. Las columnas de las dos vistas no cambian (contrato con el frontend).

create or replace view public.aviso_hidrologico_vigente with (security_invoker = true) as
select ca, ce, numero, titulo, nivel, sentido, inicio_dia, fin_dia, emision, inicio, fin,
       valor, unidad, umbral_rojo, areas, significado_rojo, url, visto_en
from public.aviso_hidrologico
where vigente
  and fin_dia >= (now() at time zone 'America/Lima')::date
  and (fin is null or fin > now())
  and (fin is not null or visto_en > now() - interval '3 hours');

create or replace view public.rio_senal with (security_invoker = true) as
select r.id as rio,
  (select coalesce(json_agg(json_build_object(
            'id', a.id, 'tipo', a.tipo, 'numero', a.numero, 'mapa', a.mapa, 'nivel', a.nivel, 'titulo', a.titulo,
            'inicio', a.inicio, 'fin', a.fin, 'en_curso', a.inicio <= now(), 'url', a.url)
          order by a.nivel desc, a.inicio), '[]'::json)
     from public.aviso_senamhi a
    where a.tema = 'lluvia' and a.fin > now() and st_intersects(a.geom, r.cuenca)) as avisos_lluvia,
  (select coalesce(json_agg(json_build_object(
            'clave', l.clave, 'nombre', l.nombre, 'pp_1h', l.pp_1h, 'umbral_1h', l.umbral_1h,
            'pp_6h', l.pp_6h, 'umbral_6h', l.umbral_6h, 'medido_en', l.medido_en)
          order by l.nombre), '[]'::json)
     from public.lluvia_senamhi_actual l
    where l.lat is not null and l.lon is not null
      and st_intersects(r.cuenca, st_setsrid(st_makepoint(l.lon, l.lat), 4326))) as lluvia_cuenca,
  (select coalesce(json_agg(json_build_object(
            'ca', h.ca, 'numero', h.numero, 'titulo', h.titulo, 'nivel', h.nivel, 'sentido', h.sentido,
            'inicio', coalesce(h.inicio, h.inicio_dia::timestamp at time zone 'America/Lima'),  -- sin detalle: 00:00 de Lima
            'fin', h.fin, 'fin_dia', h.fin_dia,
            'valor', h.valor, 'unidad', h.unidad, 'umbral_rojo', h.umbral_rojo, 'areas', h.areas,
            'significado_rojo', h.significado_rojo, 'url', h.url, 'visto_en', h.visto_en)
          order by h.nivel desc nulls last, h.inicio_dia desc), '[]'::json)
     from public.aviso_hidrologico_vigente h
    where h.ce = r.estacion_senamhi) as avisos_hidro
from public.rio_vigilado r;
