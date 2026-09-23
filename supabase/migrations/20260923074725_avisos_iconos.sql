-- Íconos y lectura del texto oficial de los avisos de SENAMHI (tarea 'avisos',
-- backend/ingesta/lectura_aviso.py). Todo es derivado: el frontend lo rotula "basado en el aviso de SENAMHI".
-- Sin CHECK de rangos numéricos: una etiqueta derivada mal calculada no debe tumbar la escritura
-- de los avisos oficiales (Python valida y deja null lo dudoso).
alter table public.aviso_senamhi
  add column texto_dia text,   -- párrafo oficial de ESE día (mapa), literal; null si no se leyó o su fecha no coincide
  add column icono text check (icono in ('gota', 'gota_rayo', 'copo')),   -- null: no es de lluvia, llovizna ni nevada
  add column lectura jsonb check (lectura is null or jsonb_typeof(lectura) = 'object'),
  add column anclas jsonb not null default '[]'::jsonb check (jsonb_typeof(anclas) = 'array');

comment on column public.aviso_senamhi.lectura is
  'v=1: fenomeno, donde, intensidad, regiones_titulo, regiones_parrafo, una_region, descargas (si|condicional|no), '
  'frase_descargas (literal), granizo{menciona,sobre_m}, nieve{menciona,sobre_m}, rafagas{forma,kmh}, montos[] o null. '
  'null en un aviso de lluvia = aún no se leyó el párrafo general (se reintenta).';
comment on column public.aviso_senamhi.anclas is
  'Dónde va el ícono: [{parte, lon, lat, radio_km, km2, mayor}] por parte del MultiPolygon (de 300 km2 o más, '
  'y siempre la más grande), en el centro del mayor círculo inscrito (ST_MaximumInscribedCircle).';

-- anclas de las filas ya guardadas (glifo, textos y lectura los completa el worker en su próxima corrida)
update public.aviso_senamhi a set anclas = (
  select coalesce(jsonb_agg(jsonb_build_object(
           'parte', x.parte, 'lon', round(st_x(x.p)::numeric, 4), 'lat', round(st_y(x.p)::numeric, 4),
           'radio_km', round(x.radio_km::numeric, 1), 'km2', round(x.km2::numeric)::int, 'mayor', x.orden = 1)
         order by x.orden), '[]'::jsonb)
  from (select (d.path)[1] as parte,
               case when st_intersects(d.geom, c.center) then c.center else st_pointonsurface(d.geom) end as p,
               st_distance(c.center::geography, c.nearest::geography) / 1000 as radio_km,
               st_area(d.geom::geography) / 1e6 as km2,
               row_number() over (order by st_area(d.geom::geography) desc) as orden
          from st_dump(a.geom) d
          cross join lateral st_maximuminscribedcircle(d.geom) c) x
  where x.orden = 1 or x.km2 >= 300);

create or replace view public.aviso_vigente with (security_invoker = true) as
select id, tipo, anio, numero, mapa, nivel, titulo, tema, descripcion, emision, inicio, fin,
       inicio <= now() as en_curso, departamentos, url, ts_captura,
       st_asgeojson(geom, 3)::json as geojson,
       texto_dia, icono, lectura, anclas                     -- nuevas, al final
from public.aviso_senamhi
where fin > now()
order by nivel, inicio, tipo, numero, mapa;
revoke all on public.aviso_vigente from anon, authenticated;
grant select on public.aviso_vigente to anon, authenticated;
