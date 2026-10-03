-- Ríos vigilados (primero el Mashcón, Cajamarca): el trazo del río resaltado, las zonas que podría
-- afectar si se desborda, sus incidentes pasados documentados y las señales de hoy (avisos de
-- lluvia sobre su cuenca, lluvia medida en su cuenca y avisos hidrológicos de SENAMHI).
--
-- rio_vigilado, rio_zona y rio_incidente se cargan UNA vez con backend/mapas/cargar_rios.py desde
-- backend/data/rios/<id>/ (como los mapas FEN): no cambian solos. aviso_hidrologico lo llena la
-- tarea 'rios' del worker (backend/ingesta/rios.py, cada hora).
--
-- Honestidad del dato (se muestra en la web):
--   rio_zona.tipo = 'estimada'  estimación SIMPAC por relieve (HAND, Copernicus GLO-30): no es oficial
--                   'estudio'   mapa de un estudio oficial pasado a coordenadas por SIMPAC (INDECI-PNUD 2005)
--                   'faja'      límite de la faja marginal aprobada por ANA (no es un mapa de inundación)
-- Licencias: el trazo (OSM) y lo derivado de él van con ODbL 1.0 y atribución; Copernicus con su aviso;
-- ANA, INDECI y SENAMHI como información pública con la fuente citada (columnas fuente/atribucion).

create table public.rio_vigilado (
  id               text primary key check (id ~ '^[a-z0-9_]+$'),  -- 'mashcon'
  nombre           text not null,                -- 'Río Mashcón'
  departamento     text not null,                -- canónico (backend/ingesta/departamentos.py)
  estacion_ana     text,                         -- caudal_actual.estacion ('Mashcón')
  rio_ana          text,                         -- caudal_actual.rio ('Mashcon')
  estacion_senamhi text,                         -- código de la estación hidrológica SENAMHI ('220213'):
                                                 -- empareja los avisos hidrológicos (aviso_hidrologico.ce)
  centro_lat       double precision not null,    -- a dónde lleva "Ver en el mapa"
  centro_lon       double precision not null,
  zoom             smallint not null default 13,
  cauce            geometry(MultiLineString, 4326) not null,  -- tronco del río (OSM)
  afluentes        geometry(MultiLineString, 4326),           -- formadores y afluente urbano (OSM), finos
  guia_rotulo      geometry(LineString, 4326),                -- tronco simplificado (~120 m): nombre sobre la línea
  cuenca           geometry(MultiPolygon, 4326) not null,     -- estimación SIMPAC; no se dibuja: decide qué avisos
                                                              -- de lluvia y qué estaciones cuentan para el río
  lugares_aviso    jsonb not null default '[]'::jsonb check (jsonb_typeof(lugares_aviso) = 'array'),
                                                 -- centros poblados que SENAMHI nombra en sus avisos del río:
                                                 -- [{nombre, lat, lon, mapa, dist_rio_m, nota, fuente_coord}]
  fuentes          jsonb not null default '{}'::jsonb,
  ts_carga         timestamptz not null default now()
);
create index rio_vigilado_cuenca_idx on public.rio_vigilado using gist (cuenca);

create table public.rio_zona (
  clave        text primary key,                 -- 'mashcon:relieve:2', 'mashcon:indeci2005:mayor:norte'
  rio          text not null references public.rio_vigilado(id) on delete cascade,
  tipo         text not null check (tipo in ('estimada', 'estudio', 'faja')),
  subtipo      text not null,                    -- bajo_1m|bajo_2m|bajo_3m · mayor|menor · derecha|izquierda
  orden        smallint not null default 0,      -- se dibuja de menor a mayor
  nombre       text not null,
  texto        text not null,                    -- explicación en lenguaje claro (popup)
  fuente       text not null,
  fuente_url   text check (fuente_url ~ '^https://'),
  licencia     text not null,
  atribucion   text not null,
  metodo       text not null,
  fecha_fuente text,                             -- '2005-12', '2021-01-11', '2026-10-02'
  area_km2     numeric,
  geom         geometry(Geometry, 4326) not null
               check (st_geometrytype(geom) in ('ST_MultiPolygon', 'ST_MultiLineString')),
  ts_carga     timestamptz not null default now()
);
create index rio_zona_rio_idx on public.rio_zona (rio, orden);

create table public.rio_incidente (
  id              text primary key,              -- 'MAS-2014-03-26', 'ANA-EEH-9913', 'SEN-2021-0987'
  rio             text not null references public.rio_vigilado(id) on delete cascade,
  fecha           date,                          -- null si la fuente solo da años
  fecha_texto     text not null,                 -- '26 de marzo de 2014', '2012–2013'
  tipo            text not null check (tipo in ('desborde', 'erosion', 'puente', 'infraestructura', 'crecida')),
  titulo          text not null,
  lugar           text not null,
  detalle         text,
  precision       text not null check (precision in ('punto', 'sector', 'distrito', 'estacion')),
  precision_texto text not null,
  caudal_m3s      numeric,                       -- solo tipo 'crecida' (medido en la estación)
  fuente_tipo     text not null check (fuente_tipo in ('oficial', 'prensa', 'academica', 'base_historica')),
  fuente          text not null,
  fuente_url      text not null check (fuente_url ~ '^https://'),
  otras_fuentes   jsonb not null default '[]'::jsonb check (jsonb_typeof(otras_fuentes) = 'array'),
  lat             double precision,              -- null: no se dibuja (solo distrito, o crecida en la estación)
  lon             double precision,
  ts_carga        timestamptz not null default now(),
  check ((lat is null) = (lon is null)),
  check (precision not in ('punto', 'sector') or lat is not null)
);
create index rio_incidente_rio_idx on public.rio_incidente (rio, fecha desc);

-- Avisos hidrológicos de SENAMHI (https://www.senamhi.gob.pe/?p=avisos-hidrologicos): la lista de
-- los últimos 12 meses, de todo el país (una fila por aviso). El detalle (hora, caudal, áreas que
-- podrían verse afectadas, umbral rojo) solo se lee para las estaciones de rio_vigilado.
create table public.aviso_hidrologico (
  ca          int primary key,                   -- id del aviso en la web (?ca=)
  ce          text not null,                     -- código de la estación ('220213' = Mashcón)
  numero      int not null,
  titulo      text not null,                     -- literal ('INCREMENTO DEL CAUDAL DEL RÍO MASHCÓN - ESTACIÓN MASHCÓN')
  nivel       smallint check (nivel between 2 and 4),  -- 2 amarillo, 3 naranja, 4 rojo (como aviso_senamhi);
                                                 -- null si la lista no trae nivel
  sentido     text not null check (sentido in ('crecida', 'descenso')),  -- 'descenso' si el título dice DESCENSO
  inicio_dia  date not null,                     -- columnas de la lista
  fin_dia     date not null,
  duracion_h  int,
  vigente     boolean not null default false,    -- "(vigente)" en la lista la última vez que se leyó
  emision     timestamptz,                       -- del detalle (solo estaciones vigiladas)
  inicio      timestamptz,
  fin         timestamptz,
  valor       numeric,                           -- caudal o nivel que registró la estación
  unidad      text,                              -- 'm3/s' | 'm.s.n.m' | 'm'
  umbral_rojo numeric,
  areas       text,                              -- literal: 'Las potenciales áreas de afectación serían ...'
  significado_rojo text,                         -- literal de la leyenda del nivel rojo: 'Se espera desborde del río. ...'
  url         text not null check (url ~ '^https://'),
  visto_en    timestamptz not null default now(),  -- última vez que vino en la lista
  ts_captura  timestamptz not null default now()
);
create index aviso_hidrologico_ce_idx on public.aviso_hidrologico (ce, fin_dia desc);

-- Lectura pública; escribe solo el worker / el cargador (rol postgres, dueño de las tablas).
alter table public.rio_vigilado      enable row level security;
alter table public.rio_zona          enable row level security;
alter table public.rio_incidente     enable row level security;
alter table public.aviso_hidrologico enable row level security;
revoke all on public.rio_vigilado, public.rio_zona, public.rio_incidente, public.aviso_hidrologico from anon, authenticated;
grant select on public.rio_vigilado, public.rio_zona, public.rio_incidente, public.aviso_hidrologico to anon, authenticated;
create policy "lectura publica rio vigilado"      on public.rio_vigilado      for select using (true);
create policy "lectura publica rio zona"          on public.rio_zona          for select using (true);
create policy "lectura publica rio incidente"     on public.rio_incidente     for select using (true);
create policy "lectura publica aviso hidrologico" on public.aviso_hidrologico for select using (true);

-- Para el frontend (PostgREST devuelve geometry en hex): GeoJSON con 5 decimales (~1 m).
create view public.rio_vigilado_mapa with (security_invoker = true) as
select id, nombre, departamento, estacion_ana, rio_ana, estacion_senamhi, centro_lat, centro_lon, zoom,
       st_asgeojson(cauce, 5)::json as cauce,
       st_asgeojson(afluentes, 5)::json as afluentes,
       st_asgeojson(guia_rotulo, 5)::json as guia_rotulo,
       lugares_aviso, fuentes
from public.rio_vigilado;

create view public.rio_zona_mapa with (security_invoker = true) as
select clave, rio, tipo, subtipo, orden, nombre, texto, fuente, fuente_url, licencia, atribucion, metodo,
       fecha_fuente, area_km2, st_asgeojson(geom, 5)::json as geojson
from public.rio_zona
order by rio, orden;

-- Avisos hidrológicos vigentes: "(vigente)" en la última lectura de la lista, lista leída hace
-- menos de 3 h (con la tarea caída no queda un aviso viejo encendido) y que no terminó.
create view public.aviso_hidrologico_vigente with (security_invoker = true) as
select ca, ce, numero, titulo, nivel, sentido, inicio_dia, fin_dia, emision, inicio, fin,
       valor, unidad, umbral_rojo, areas, significado_rojo, url, visto_en
from public.aviso_hidrologico
where vigente
  and visto_en > now() - interval '3 hours'
  and fin_dia >= (now() at time zone 'America/Lima')::date
  and (fin is null or fin > now());

-- Señales de hoy por río (una fila por río vigilado). Las cruza la BD con PostGIS; el nivel de la
-- zona lo decide el frontend (lib/zonaRio.js) con estas señales y caudal_actual.
--   avisos_lluvia   avisos de SENAMHI de tema lluvia que no terminaron y tocan la cuenca
--   lluvia_cuenca   estaciones de lluvia de lluvia_senamhi_actual (últimas 3 h) dentro de la cuenca
--   avisos_hidro    avisos hidrológicos vigentes de la estación SENAMHI del río
create view public.rio_senal with (security_invoker = true) as
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
            'significado_rojo', h.significado_rojo, 'url', h.url)
          order by h.nivel desc nulls last, h.inicio_dia desc), '[]'::json)
     from public.aviso_hidrologico_vigente h
    where h.ce = r.estacion_senamhi) as avisos_hidro
from public.rio_vigilado r;

revoke all on public.rio_vigilado_mapa, public.rio_zona_mapa, public.aviso_hidrologico_vigente, public.rio_senal
  from anon, authenticated;
grant select on public.rio_vigilado_mapa, public.rio_zona_mapa, public.aviso_hidrologico_vigente, public.rio_senal
  to anon, authenticated;

comment on table public.rio_zona is
  'Zonas que un río vigilado podría afectar. tipo: estimada (relieve, SIMPAC) | estudio (INDECI-PNUD 2005 digitalizado) | faja (faja marginal ANA). Ninguna es un mapa oficial de inundación vigente.';
comment on table public.rio_incidente is
  'Incidentes pasados que nombran al río en su fuente (desbordes, erosión, puentes) y crecidas medidas en rojo. Carga única: backend/mapas/cargar_rios.py.';
