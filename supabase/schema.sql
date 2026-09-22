-- ============================================================================
-- SIMPAC — Esquema inicial (PostgreSQL + PostGIS) para Supabase
-- Pegar en: Supabase → SQL Editor → New query → Run.
-- Idempotente (se puede volver a correr). Comentarios en español.
-- ============================================================================

create extension if not exists postgis;

-- ===========================================================================
-- A) DATOS OFICIALES (lectura pública, escritura solo del backend/ingesta)
-- ===========================================================================

create table if not exists estacion (
  cod          text primary key,
  nombre       text not null,
  tipo         text,                    -- 'M' meteorológica | 'H' hidrológica
  categoria    text,                    -- CO, PLU, EMA, EHA, HLG, ...
  estado       text,                    -- REAL | DIFERIDO | AUTOMATICA
  departamento text default 'Cajamarca',
  fuente       text default 'SENAMHI',
  geom         geometry(Point, 4326),
  lat          double precision generated always as (st_y(geom)) stored,  -- comodidad para el frontend
  lon          double precision generated always as (st_x(geom)) stored
);
create index if not exists estacion_geom_idx on estacion using gist (geom);

create table if not exists lectura_lluvia (
  id         bigint generated always as identity primary key,
  cod        text references estacion(cod),
  ts         text not null,             -- "YYYY/MM/DD - HH" (clave de dedup del conector)
  medido_en  timestamptz,               -- ts parseado (para consultas por tiempo)
  precip_mm  double precision,
  temp_c     double precision,
  ts_captura timestamptz default now(),
  unique (cod, ts)
);
create index if not exists lluvia_cod_idx on lectura_lluvia (cod, medido_en);

create table if not exists lectura_caudal (
  id                bigint generated always as identity primary key,
  estacion          text not null,
  rio               text,
  departamento      text,
  provincia         text,
  fecha             date not null,
  hora              text not null,
  valor             double precision,
  unidad            text,               -- 'm³/s' | 'm'
  umbral_alerta     double precision,
  umbral_emergencia double precision,
  tendencia         text,               -- Ascendente | Descendente | Estable
  estado            text,               -- normal | alerta | emergencia | s.d.
  geom              geometry(Point, 4326),
  lat               double precision generated always as (st_y(geom)) stored,
  lon               double precision generated always as (st_x(geom)) stored,
  ts_captura        timestamptz default now(),
  unique (estacion, fecha, hora)
);
create index if not exists caudal_geom_idx on lectura_caudal using gist (geom);

create table if not exists indice (
  fuente     text primary key,          -- 'ONI' | 'ICEN'
  periodo    text,
  valor      double precision,
  categoria  text,
  ts_captura timestamptz default now()
);

create table if not exists alerta (
  id       bigint generated always as identity primary key,
  tipo     text,                        -- 'lluvia' | 'caudal' | 'aviso'
  referencia text,
  zona     text default 'Cajamarca',
  nivel    text,                        -- normal | aviso | alerta | emergencia
  detalle  text,
  valor    double precision,
  umbral   double precision,
  geom     geometry(Point, 4326),
  vigente  boolean default true,
  ts       timestamptz default now()
);
create index if not exists alerta_vigente_idx on alerta (vigente, nivel);

create table if not exists mapa (
  id         bigint generated always as identity primary key,
  uuid       text,                        -- identificador del registro en GeoNetwork (opcional)
  titulo     text not null,
  variable   text,                        -- 'precipitacion' = anomalía mensual; 'FEN' = eventos El Niño históricos
  periodo    text,                        -- ej. "2026-08" (mensual) o "1982-1983" (evento)
  fuente     text default 'SENAMHI/IDESEP',
  geojson    jsonb not null,              -- FeatureCollection (shapefile -> GeoJSON)
  ts_captura timestamptz default now()
);
-- uuid único (se permiten varios null) para que backend/mapas/cargar_fen.py haga upsert idempotente
create unique index if not exists mapa_uuid_key on mapa (uuid);

-- ===========================================================================
-- B) COMUNIDAD (usuarios, reportes, confirmaciones, chat) — fases v2/v3
--    La autenticación la maneja Supabase Auth (tabla auth.users).
-- ===========================================================================

create table if not exists perfil (
  id         uuid primary key references auth.users(id) on delete cascade,
  nombre     text,
  rol        text default 'ciudadano',  -- ciudadano | tecnico | admin
  reputacion int  default 0,
  zona       geometry(Point, 4326),
  creado_en  timestamptz default now()
);

create table if not exists report (
  id          bigint generated always as identity primary key,
  autor       uuid references auth.users(id),
  tipo        text not null,            -- inundacion | huaico | lluvia | deslizamiento | otro
  descripcion text,
  foto_url    text,
  geom        geometry(Point, 4326) not null,
  confianza   double precision default 0,
  estado      text default 'sin_confirmar', -- sin_confirmar | confirmado | descartado
  expira_en   timestamptz,
  creado_en   timestamptz default now()
);
create index if not exists report_geom_idx on report using gist (geom);

create table if not exists voto (
  id        bigint generated always as identity primary key,
  report_id bigint references report(id) on delete cascade,
  autor     uuid references auth.users(id),
  valor     smallint not null check (valor in (-1, 1)),  -- 1 = like, -1 = dislike
  creado_en timestamptz default now(),
  unique (report_id, autor)
);

create table if not exists comentario (
  id        bigint generated always as identity primary key,
  report_id bigint references report(id) on delete cascade,
  autor     uuid references auth.users(id),
  texto     text not null,
  creado_en timestamptz default now()
);

create table if not exists message (
  id        bigint generated always as identity primary key,
  autor     uuid references auth.users(id),
  zona      text,
  contenido text,
  geom      geometry(Point, 4326),
  expira_en timestamptz,               -- mensajes efímeros
  creado_en timestamptz default now()
);
create index if not exists message_zona_idx on message (zona, expira_en);

-- ===========================================================================
-- C) SEGURIDAD (RLS + grants)  — "Automatically expose new tables" está OFF,
--    así que hay que dar acceso explícito a los roles del Data API.
-- ===========================================================================

-- Roles del Data API: anon (visitante), authenticated (con sesión).
-- El backend/ingesta usa la service_role, que IGNORA RLS y grants (escribe todo).

-- --- Datos oficiales: lectura pública ---
alter table estacion        enable row level security;
alter table lectura_lluvia  enable row level security;
alter table lectura_caudal  enable row level security;
alter table indice          enable row level security;
alter table alerta          enable row level security;

grant select on estacion, lectura_lluvia, lectura_caudal, indice, alerta to anon, authenticated;

do $$
begin
  perform 1;
  -- políticas de solo-lectura (idempotencia manual con drop-if-exists)
end $$;

drop policy if exists "lectura publica estacion"  on estacion;
create policy "lectura publica estacion"  on estacion       for select using (true);
drop policy if exists "lectura publica lluvia"    on lectura_lluvia;
create policy "lectura publica lluvia"    on lectura_lluvia for select using (true);
drop policy if exists "lectura publica caudal"    on lectura_caudal;
create policy "lectura publica caudal"    on lectura_caudal for select using (true);
drop policy if exists "lectura publica indice"    on indice;
create policy "lectura publica indice"    on indice        for select using (true);
drop policy if exists "lectura publica alerta"    on alerta;
create policy "lectura publica alerta"    on alerta        for select using (true);
alter table mapa enable row level security;
grant select on mapa to anon, authenticated;
drop policy if exists "lectura publica mapa" on mapa;
create policy "lectura publica mapa" on mapa for select using (true);

-- --- Comunidad ---
alter table perfil     enable row level security;
alter table report     enable row level security;
alter table voto       enable row level security;
alter table comentario enable row level security;
alter table message    enable row level security;

grant select, insert, update on perfil, report, message to authenticated;
grant select, insert, update, delete on voto to authenticated;
grant insert on comentario to authenticated;
grant select on report, voto, comentario to anon;   -- reportes, votos y comentarios visibles en el mapa público

-- perfil: cada quien ve/edita el suyo
drop policy if exists "perfil propio select" on perfil;
create policy "perfil propio select" on perfil for select using (auth.uid() = id);
drop policy if exists "perfil propio upsert" on perfil;
create policy "perfil propio upsert" on perfil for insert with check (auth.uid() = id);
drop policy if exists "perfil propio update" on perfil;
create policy "perfil propio update" on perfil for update using (auth.uid() = id);

-- report: lectura pública; crea/edita el autor
drop policy if exists "report lectura publica" on report;
create policy "report lectura publica" on report for select using (true);
drop policy if exists "report crea autor" on report;
create policy "report crea autor" on report for insert with check (auth.uid() = autor);
drop policy if exists "report edita autor" on report;
create policy "report edita autor" on report for update using (auth.uid() = autor);

-- voto (like/dislike) y comentario: lectura pública; escribe el autor
drop policy if exists "voto lectura" on voto;
create policy "voto lectura" on voto for select using (true);
drop policy if exists "voto crea autor" on voto;
create policy "voto crea autor" on voto for insert with check (auth.uid() = autor);
drop policy if exists "voto edita autor" on voto;
create policy "voto edita autor" on voto for update using (auth.uid() = autor);
drop policy if exists "voto borra autor" on voto;
create policy "voto borra autor" on voto for delete using (auth.uid() = autor);
drop policy if exists "coment lectura" on comentario;
create policy "coment lectura" on comentario for select using (true);
drop policy if exists "coment crea autor" on comentario;
create policy "coment crea autor" on comentario for insert with check (auth.uid() = autor);

-- message (chat efímero): autenticados leen los no expirados; crea el autor
drop policy if exists "msg lectura vigente" on message;
create policy "msg lectura vigente" on message for select
  using (auth.role() = 'authenticated' and (expira_en is null or expira_en > now()));
drop policy if exists "msg crea autor" on message;
create policy "msg crea autor" on message for insert with check (auth.uid() = autor);

-- ============================================================================
-- Fin del esquema. La ingesta (service_role) inserta en A); el frontend usa el
-- Data API con anon/authenticated según estas políticas.
-- ============================================================================
