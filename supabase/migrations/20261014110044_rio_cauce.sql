-- Trazo (cauce) de los ríos con estación de caudal de ANA (caudal_actual) y de los ríos con avisos
-- hidrológicos de SENAMHI, para resaltarlos en el mapa como ya se hace con el Mashcón (rio_vigilado).
--
-- Fuente: ANA - GeoSNIRH, dos capas ArcGIS REST (backend/connectors/ana_rios.py):
--   ana_rj056  red hidrográfica oficial R.J. N.º 056-2018-ANA (línea central por tramo Pfafstetter, 2018)
--   ana_ign    ríos y quebradas de la Carta Nacional 1:100 000 del IGN publicada por la ANA (abril 2026)
--   osm        reservado para un trazo curado a mano (hoy el Mashcón vive en rio_vigilado, no aquí)
-- GeoSNIRH no publica texto de licencia: se trata como información pública del Estado con la fuente
-- citada (columnas fuente, licencia, atribucion, visibles en el popup).
--
-- Carga ÚNICA con backend/mapas/cargar_cauces.py (prueba en seco y --aplicar): una fila por río
-- (rio_ana = caudal_actual.rio normalizado; el Huallaga son 8 estaciones y una sola fila), con el río
-- completo tal como lo dibuja la capa. Honestidad del dato: el trazo es la línea central de 2018 o
-- la Carta Nacional, no la orilla de hoy (en selva el Napo queda a 282 m de la estación); no se deriva
-- de él ninguna zona inundable, y un río sin trazo no se inventa (no hay fila: la web dibuja el disco
-- de la estación y dice que el trazo no está disponible).

create table public.rio_cauce (
  rio_ana            text primary key check (rio_ana ~ '^[a-z0-9_]+$'),  -- 'jequetepeque', 'chancay_lambayeque'
  rio                text not null,            -- caudal_actual.rio literal ('Jequetepeque'); si el río solo tiene
                                               -- avisos de SENAMHI, el nombre del título del aviso ('Chilete')
  nombre             text not null,            -- para mostrar: 'Río Jequetepeque' (el de la capa, o el alias 'mostrar')
  departamento       text not null,            -- de sus estaciones, canónico; varios separados por ', '
  estaciones         text[] not null default '{}',   -- caudal_actual.estacion (vacío si solo tiene aviso SENAMHI)
  estaciones_senamhi text[] not null default '{}',   -- aviso_hidrologico.ce de sus estaciones
  capa               text not null check (capa in ('ana_rj056', 'ana_ign', 'osm')),
  nombre_capa        text not null,            -- nombre literal en la capa ('Río Chancay')
  codigos            text[] not null,          -- CODIGO_CA (Pfafstetter) o IDE_CUERPO_AGUA de los tramos
  tramos             int not null,
  km                 numeric not null,         -- largo del trazo guardado (haversine)
  km_declarado       numeric,                  -- LONG_KM / NUM_LONGITUD que declara la capa
  dist_estacion_m    numeric,                  -- la estación más cercana al trazo
  distancias         jsonb not null default '[]'::jsonb check (jsonb_typeof(distancias) = 'array'),
                                               -- [{estacion, origen: 'ana'|'senamhi', codigo, m}]
  alias              text,                     -- nombre buscado cuando no es el de ANA (cauces_alias.json)
  nota               text,                     -- avisos de la carga ('estación Jesús Túnel a 865 m del trazo')
  geom               geometry(MultiLineString, 4326) not null,  -- ~6 m (maxAllowableOffset del servidor)
  geom_lejos         geometry(MultiLineString, 4326) not null,  -- ~50 m (st_simplifypreservetopology 0.00045)
  fuente             text not null,
  fuente_url         text not null check (fuente_url ~ '^https://'),
  licencia           text not null,
  atribucion         text not null,
  fecha_fuente       text,                     -- '2018-01-30' (RJ056) | '2026-04' (IGN)
  url_consulta       text check (url_consulta ~ '^https://'),   -- la consulta que trajo el río (reproducible)
  bytes              int,                      -- lo descargado para este río
  ts_carga           timestamptz not null default now()
);
create index rio_cauce_geom_idx on public.rio_cauce using gist (geom);
create index rio_cauce_geom_lejos_idx on public.rio_cauce using gist (geom_lejos);

alter table public.rio_cauce enable row level security;
revoke all on public.rio_cauce from anon, authenticated;
grant select on public.rio_cauce to anon, authenticated;
create policy "lectura publica rio cauce" on public.rio_cauce for select using (true);

-- Para el frontend: GeoJSON con 5 decimales en dos niveles. cauce_lejos (~50 m) para todo el país de
-- una vez (zoom bajo); cauce (~6 m) se pide por río (.eq('rio_ana', ...)) al acercarse. PostgREST solo
-- calcula las columnas que se piden. vigilado = ya tiene trazo revisado a mano en rio_vigilado
-- (el Mashcón): el mapa lo dibuja desde rio_vigilado_mapa y salta este.
create view public.rio_cauce_mapa with (security_invoker = true) as
select c.rio_ana, c.rio, c.nombre, c.departamento, c.estaciones, c.estaciones_senamhi, c.capa, c.nombre_capa,
       c.km, c.dist_estacion_m, c.nota, c.fuente, c.fuente_url, c.licencia, c.atribucion, c.fecha_fuente, c.ts_carga,
       exists (select 1 from public.rio_vigilado v
                where v.rio_ana = c.rio or v.estacion_ana = any (c.estaciones)) as vigilado,
       st_asgeojson(c.geom_lejos, 5)::json as cauce_lejos,
       st_asgeojson(c.geom, 5)::json as cauce
from public.rio_cauce c;

-- Señales de hoy por río, una fila por río (como rio_senal para los vigilados): las últimas lecturas de
-- sus estaciones de ANA y los avisos hidrológicos vigentes de sus estaciones SENAMHI. El nivel del río
-- lo decide el frontend con la misma regla del Mashcón (lib/zonaRio.js estadoCauce: el peor entre sus
-- estaciones; el aviso de SENAMHI manda si es más alto; un umbral de nivel bajo no es crecida).
create view public.rio_cauce_senal with (security_invoker = true) as
select c.rio_ana,
  (select coalesce(json_agg(json_build_object(
            'estacion', a.estacion, 'departamento', a.departamento, 'valor', a.valor, 'unidad', a.unidad,
            'umbral_alerta', a.umbral_alerta, 'umbral_emergencia', a.umbral_emergencia, 'estado', a.estado,
            'tendencia', a.tendencia, 'fecha', a.fecha, 'hora', a.hora, 'ts_captura', a.ts_captura)
          order by a.estacion), '[]'::json)
     from public.caudal_actual a
    where a.rio = c.rio and a.estacion = any (c.estaciones)) as lecturas,
  (select coalesce(json_agg(json_build_object(
            'ca', h.ca, 'ce', h.ce, 'numero', h.numero, 'titulo', h.titulo, 'nivel', h.nivel, 'sentido', h.sentido,
            'inicio', coalesce(h.inicio, h.inicio_dia::timestamp at time zone 'America/Lima'),
            'fin', h.fin, 'fin_dia', h.fin_dia, 'valor', h.valor, 'unidad', h.unidad, 'umbral_rojo', h.umbral_rojo,
            'url', h.url, 'visto_en', h.visto_en)
          order by h.nivel desc nulls last, h.inicio_dia desc), '[]'::json)
     from public.aviso_hidrologico_vigente h
    where h.ce = any (c.estaciones_senamhi)) as avisos_hidro
from public.rio_cauce c;

revoke all on public.rio_cauce_mapa, public.rio_cauce_senal from anon, authenticated;
grant select on public.rio_cauce_mapa, public.rio_cauce_senal to anon, authenticated;

comment on table public.rio_cauce is
  'Trazo de los ríos con estación de caudal de ANA o aviso hidrológico de SENAMHI (ANA - GeoSNIRH: RJ056 o Carta Nacional IGN). Carga única: backend/mapas/cargar_cauces.py. Línea de referencia, no la orilla de hoy ni una zona inundable.';
