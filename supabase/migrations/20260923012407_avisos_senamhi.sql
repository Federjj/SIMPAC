-- Avisos oficiales de SENAMHI como áreas sombreadas (polígonos por nivel), para el mapa y
-- para las alertas por departamento. Los llena la tarea 'avisos' del worker
-- (backend/ingesta/avisos.py, cada hora):
--   meteorologico  avisos meteorológicos (WFS g_aviso:view_aviso), un mapa por día de vigencia
--   lluvia24h      aviso de lluvia acumulada en 24 h (WFS g_prono_pp_24h:view_aviso24h): rige
--                  24 h desde las 13:00 de Lima de su fecha
-- Una fila por (aviso, mapa, nivel): los polígonos del mismo nivel se unen y se simplifican
-- (~500 m) al insertar. Solo niveles 2 (amarillo), 3 (naranja) y 4 (rojo): el Nivel 1 es
-- "sin aviso" y cubre el resto del país.
-- Licencia SENAMHI: mostrar la leyenda completa (ATRIBUCION en
-- backend/connectors/senamhi_avisos.py) y rotular como "basado en el aviso de SENAMHI".
create table public.aviso_senamhi (
  id            bigint generated always as identity primary key,
  tipo          text not null check (tipo in ('meteorologico', 'lluvia24h')),
  anio          int not null,
  numero        int,                      -- N° del aviso; null en lluvia24h (el WFS no lo trae)
  mapa          smallint not null default 1 check (mapa >= 1),   -- día del aviso: 1, 2, 3...
  nivel         smallint not null check (nivel between 2 and 4), -- 2 amarillo, 3 naranja, 4 rojo
  titulo        text not null,            -- título oficial, p. ej. 'PRECIPITACIONES EN LA SIERRA NORTE'
  tema          text not null check (tema in ('lluvia', 'temperatura', 'viento', 'otro')),
  descripcion   text,                     -- párrafo oficial ('El SENAMHI informa que...'), si se leyó
  emision       date,
  inicio        timestamptz not null,
  fin           timestamptz not null,
  departamentos text[] not null default '{}',   -- de las estaciones SENAMHI que caen dentro
  url           text,                     -- página oficial del aviso
  geom          geometry(MultiPolygon, 4326) not null,
  ts_captura    timestamptz not null default now(),
  check (fin > inicio),
  constraint aviso_senamhi_clave unique nulls not distinct (tipo, anio, numero, mapa, nivel)
);
create index aviso_senamhi_geom_idx on public.aviso_senamhi using gist (geom);
create index aviso_senamhi_fin_idx on public.aviso_senamhi (fin);

alter table public.aviso_senamhi enable row level security;
revoke all on public.aviso_senamhi from anon, authenticated;
grant select on public.aviso_senamhi to anon, authenticated;
create policy "lectura publica aviso" on public.aviso_senamhi for select using (true);

-- Para el frontend: los avisos que no han terminado, con la geometría en GeoJSON (PostgREST
-- devuelve geometry en hex). 3 decimales (~110 m) bastan: la geometría ya viene simplificada.
-- en_curso = ya empezó; los demás son avisos emitidos para los próximos días. Orden por
-- nivel: si se dibujan en este orden, el rojo queda encima del naranja y del amarillo.
create view public.aviso_vigente with (security_invoker = true) as
select id, tipo, anio, numero, mapa, nivel, titulo, tema, descripcion, emision, inicio, fin,
       inicio <= now() as en_curso, departamentos, url, ts_captura,
       st_asgeojson(geom, 3)::json as geojson
from public.aviso_senamhi
where fin > now()
order by nivel, inicio, tipo, numero, mapa;
revoke all on public.aviso_vigente from anon, authenticated;
grant select on public.aviso_vigente to anon, authenticated;
