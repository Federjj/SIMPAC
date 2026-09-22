-- ============================================================================
-- SIMPAC — Esquema consolidado (PostgreSQL + PostGIS) en Supabase
--
-- Es una FOTO del estado final, para leer de un vistazo cómo queda la BD.
-- La historia real (lo que se aplicó y en qué orden) está en supabase/migrations/:
-- cualquier cambio nuevo va como un archivo de migración nuevo, y luego se
-- refleja aquí. Para una BD desde cero, aplicar las migraciones en orden.
-- ============================================================================

create extension if not exists postgis;

-- ===========================================================================
-- A) DATOS OFICIALES: lectura pública; escribe solo la ingesta (worker).
--    La ingesta se conecta con el rol postgres (SUPABASE_DB_URL), que es el
--    dueño de las tablas. service_role no tiene permisos de escritura aquí.
-- ===========================================================================

create table estacion (
  cod          text primary key,
  nombre       text not null,
  tipo         text,                    -- 'M' meteorológica | 'H' hidrológica
  categoria    text,                    -- CO, PLU, EMA, EHA, HLG, ...
  estado       text,                    -- REAL | DIFERIDO | AUTOMATICA
  departamento text,                    -- 'Cajamarca', 'La Libertad'... (nombre canónico)
  fuente       text default 'SENAMHI',
  geom         geometry(Point, 4326),
  lat          double precision generated always as (st_y(geom)) stored,  -- comodidad para el frontend
  lon          double precision generated always as (st_x(geom)) stored
);
create index estacion_geom_idx on estacion using gist (geom);

create table lectura_lluvia (
  id         bigint generated always as identity primary key,
  cod        text references estacion(cod),
  ts         text not null,             -- "YYYY/MM/DD - HH" en hora de Perú (clave de dedup)
  medido_en  timestamptz,               -- ts con zona horaria (para consultas por tiempo)
  precip_mm  double precision,
  temp_c     double precision,
  ts_captura timestamptz default now(),
  unique (cod, ts)
);
create index lluvia_cod_idx on lectura_lluvia (cod, medido_en);

create table lectura_caudal (             -- historial: una fila por estación, fecha y hora
  id                bigint generated always as identity primary key,
  estacion          text not null,
  rio               text,
  departamento      text,
  provincia         text,
  fecha             date not null,        -- fecha de Perú
  hora              text not null,        -- 'HH:MM'
  valor             double precision,
  unidad            text,                 -- 'm³/s' | 'm'
  umbral_alerta     double precision,
  umbral_emergencia double precision,
  tendencia         text,                 -- Ascendente | Descendente | Estable
  estado            text,                 -- normal | alerta | emergencia | s.d. (con umbral de
                                          -- nivel bajo, alerta = el río está demasiado BAJO)
  geom              geometry(Point, 4326),
  lat               double precision generated always as (st_y(geom)) stored,
  lon               double precision generated always as (st_x(geom)) stored,
  ts_captura        timestamptz default now(),
  unique (estacion, rio, fecha, hora)     -- hay estaciones homónimas en ríos distintos
);
create index caudal_geom_idx on lectura_caudal using gist (geom);

-- Última lectura de cada estación (lo que muestran el mapa y el snapshot), solo de
-- ayer u hoy: una estación que ANA deja de publicar no queda fija en su último estado.
create view caudal_actual with (security_invoker = true) as
select distinct on (estacion, rio)
  estacion, rio, departamento, provincia, fecha, hora, valor, unidad,
  umbral_alerta, umbral_emergencia, tendencia, estado, lat, lon, ts_captura
from lectura_caudal
where fecha >= (now() at time zone 'America/Lima')::date - 1
order by estacion, rio, fecha desc, hora desc;

create table indice (
  fuente     text primary key,          -- 'ICEN' | 'ICEN_TMP' (estimado ENFEN) | 'RONI' (NOAA)
  periodo    text,                      -- ICEN: 'AAAA-MM'; RONI: trimestre, p. ej. 'JJA 2026'
  valor      double precision,
  categoria  text,                      -- ICEN: Nota Técnica ENFEN 01-2024; RONI: magnitud CPC
  origen     text,                      -- IGP | ENFEN | NOAA (el ICEN guarda el mes más nuevo)
  ts_captura timestamptz default now()
);

-- Comunicado oficial del ENFEN (cada ~2 semanas, PDF): estado del Sistema de Alerta.
-- Lo llena la tarea 'enfen' del worker (cada 6 h).
create table comunicado_enfen (
  anio       int  not null,
  numero     int  not null,
  extraordinario boolean not null default false,  -- comparten numeración con los oficiales
  fecha      date not null,               -- emisión
  estado     text not null,               -- p. ej. 'Alerta de El Niño Costero'
  proximo    date,                        -- próximo comunicado anunciado
  resumen    text,
  url        text not null,               -- PDF
  ts_captura timestamptz not null default now(),
  primary key (anio, numero, extraordinario)
);

-- Cuándo corrió de verdad cada tarea del worker ('ingesta', 'enfen').
create table latido (
  servicio text primary key,
  ts       timestamptz not null default now(),
  resumen  jsonb
);

-- La ingesta reemplaza cada hora solo las alertas de las estaciones que re-evaluó (con
-- dato); las que no se pudieron re-evaluar caducan a las 6 h (backend/ingesta/guardar.py).
create table alerta (
  id         bigint generated always as identity primary key,
  tipo       text,                      -- 'lluvia' | 'caudal' (crecida) | 'nivel_bajo' (vaciante) | 'aviso'
  referencia text,                      -- "Estación (cod)" o "Estación (río)"
  zona       text,                      -- departamento
  nivel      text,                      -- normal | aviso | alerta | emergencia
  detalle    text,
  valor      double precision,
  umbral     double precision,
  geom       geometry(Point, 4326),
  vigente    boolean default true,
  ts         timestamptz default now()
);
create index alerta_vigente_idx on alerta (vigente, nivel);

create table mapa (
  id         bigint generated always as identity primary key,
  uuid       text,                      -- identificador del registro en GeoNetwork (IDESEP)
  titulo     text not null,
  variable   text,                      -- 'precipitacion' = anomalía mensual; 'FEN' = eventos El Niño históricos
  periodo    text,                      -- ej. "2026-08" (mensual) o "1982-1983" (evento)
  fuente     text default 'SENAMHI/IDESEP',
  geojson    jsonb not null,            -- FeatureCollection (shapefile -> GeoJSON)
  ts_captura timestamptz default now()
);
create unique index mapa_uuid_key on mapa (uuid);   -- upsert idempotente de backend/mapas/cargar_fen.py

-- ===========================================================================
-- B) COMUNIDAD: reportes estilo Waze validados por votos. Usuarios de Supabase
--    Auth (auth.users.id es uuid). Todos los ids son uuid: no se pueden recorrer.
--    Lo que decide la comunidad (estado, confianza, likes, reputación) y los
--    vencimientos los calcula la BD; el cliente no los puede escribir.
-- ===========================================================================

create table perfil (                   -- se crea solo al registrarse (trigger crear_perfil)
  id         uuid primary key references auth.users(id) on delete cascade,
  nombre     text check (char_length(nombre) <= 80),
  reputacion int  not null default 0,   -- saldo de votos recibidos (trigger voto_aplicar)
  zona       geometry(Point, 4326),     -- privada: solo la ve su dueño
  creado_en  timestamptz default now()
);

create table report (
  id          uuid primary key default gen_random_uuid(),
  autor       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  tipo        text not null check (tipo in ('inundacion', 'huayco', 'lluvia_intensa', 'via_bloqueada',
                                            'atasco', 'bache', 'accidente', 'otro')),
  subtipo     text check (case when tipo = 'atasco'
                               then coalesce(subtipo in ('leve', 'moderado', 'detenido'), false)
                               else subtipo is null end),
  descripcion text check (char_length(descripcion) <= 500),
  foto_url    text check (foto_url ~ '^https://'),
  geom        geometry(Point, 4326) not null     -- GPS del usuario; solo dentro del Perú
              check (st_x(geom) between -81.5 and -68.5 and st_y(geom) between -18.5 and 0.1),
  likes       int  not null default 0,
  dislikes    int  not null default 0,
  confianza   double precision not null default 0.5 check (confianza between 0 and 1),
  estado      text not null default 'sin_confirmar'
              check (estado in ('sin_confirmar', 'confirmado', 'descartado')),
  expira_en   timestamptz not null default now() + interval '12 hours',
  creado_en   timestamptz not null default now(),
  lat         double precision generated always as (st_y(geom)) stored,
  lon         double precision generated always as (st_x(geom)) stored
);
create index report_geom_idx   on report using gist (geom);
create index report_autor_idx  on report (autor, creado_en);
create index report_expira_idx on report (expira_en);

create table voto (
  id        uuid primary key default gen_random_uuid(),
  report_id uuid not null references report(id) on delete cascade,
  autor     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  valor     smallint not null check (valor in (-1, 1)),   -- 1 = like, -1 = dislike
  creado_en timestamptz not null default now(),
  unique (report_id, autor)
);
create index voto_autor_idx on voto (autor);

create table comentario (
  id        uuid primary key default gen_random_uuid(),
  report_id uuid not null references report(id) on delete cascade,
  autor     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  texto     text not null check (char_length(texto) between 1 and 500),
  creado_en timestamptz not null default now()
);
create index comentario_report_idx on comentario (report_id, creado_en);
create index comentario_autor_idx  on comentario (autor);

create table message (                  -- chat efímero por zona
  id        uuid primary key default gen_random_uuid(),
  autor     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  zona      text,
  contenido text not null check (char_length(contenido) between 1 and 500),
  geom      geometry(Point, 4326),
  expira_en timestamptz not null default now() + interval '2 hours',
  creado_en timestamptz not null default now()
);
create index message_zona_idx  on message (zona, expira_en);
create index message_autor_idx on message (autor, creado_en);

-- Triggers (funciones en el esquema privado, que el Data API no expone):
--   voto_validar      before insert on voto: no se vota el propio reporte.
--   voto_aplicar      after insert/update/delete on voto: actualiza likes, dislikes,
--                     confianza = (likes+1)/(likes+dislikes+2), estado (saldo ±3) y la
--                     reputación del autor; impide mover un voto a otro reporte.
--   report_limite     before insert on report: máximo 5 reportes por hora y autor.
--   comentario_limite before insert on comentario: máximo 20 por hora y autor.
--   message_limite    before insert on message: máximo 30 mensajes por hora y autor.
--                     (los límites toman un lock por autor: no se evaden en paralelo)
--   crear_perfil      after insert on auth.users: crea el perfil (nombre de options.data).
--   srs_solo_lectura  on spatial_ref_sys: rechaza escrituras de anon/authenticated.
-- Función pública: mis_reportes() (rpc, solo con sesión) devuelve los reportes propios,
-- vigentes y vencidos: es la única forma de verlos, porque autor no es legible.
-- Definición completa en supabase/migrations/ (comunidad_uuid_y_permisos,
-- permisos_api_endurecidos y comunidad_privacidad_y_limites).

-- ===========================================================================
-- C) SEGURIDAD: RLS en todas las tablas y permisos POR COLUMNA.
--    anon = visitante sin sesión; authenticated = con sesión.
--    A anon/authenticated no se les da TRUNCATE, TRIGGER, REFERENCES ni MAINTAIN.
-- ===========================================================================

alter table estacion       enable row level security;
alter table lectura_lluvia enable row level security;
alter table lectura_caudal enable row level security;
alter table indice         enable row level security;
alter table alerta         enable row level security;
alter table mapa           enable row level security;
alter table comunicado_enfen enable row level security;
alter table latido         enable row level security;
alter table perfil         enable row level security;
alter table report         enable row level security;
alter table voto           enable row level security;
alter table comentario     enable row level security;
alter table message        enable row level security;

-- Datos oficiales: solo lectura para todos.
grant select on estacion, lectura_lluvia, lectura_caudal, caudal_actual, indice, alerta, mapa,
  comunicado_enfen, latido to anon, authenticated;
create policy "lectura publica estacion" on estacion       for select using (true);
create policy "lectura publica lluvia"   on lectura_lluvia for select using (true);
create policy "lectura publica caudal"   on lectura_caudal for select using (true);
create policy "lectura publica indice"   on indice         for select using (true);
create policy "lectura publica alerta"   on alerta         for select using (true);
create policy "lectura publica mapa"     on mapa           for select using (true);
create policy "lectura publica comunicado" on comunicado_enfen for select using (true);
create policy "lectura publica latido"   on latido         for select using (true);

-- Comunidad: lo que no aparece aquí, el cliente no lo puede leer ni escribir.
-- autor no se lee (con autor + GPS + hora se arma el historial de ubicación de alguien),
-- ni la posición de los mensajes. Por eso el cliente pide columnas explícitas, nunca '*'.
grant select (id, tipo, subtipo, descripcion, foto_url, geom, lat, lon, likes, dislikes,
              confianza, estado, expira_en, creado_en) on report to anon, authenticated;
grant select (id, report_id, texto, creado_en)                    on comentario to anon, authenticated;
grant select (id, autor, zona, contenido, expira_en, creado_en)   on message to authenticated;
grant select on voto, perfil to authenticated;
grant insert (autor, tipo, subtipo, descripcion, foto_url, geom) on report to authenticated;
grant update (descripcion, foto_url)        on report     to authenticated;
grant insert (report_id, autor, valor)      on voto       to authenticated;
grant update (report_id, autor, valor)      on voto       to authenticated;  -- upsert de supabase-js
grant delete                                on voto       to authenticated;
grant insert (report_id, autor, texto)      on comentario to authenticated;
grant insert (autor, zona, contenido, geom) on message    to authenticated;
grant update (nombre, zona)                 on perfil     to authenticated;

-- report: todos leen los vigentes; crea el autor; edita el autor mientras no tenga votos
create policy "report lectura vigente" on report for select to anon, authenticated
  using (expira_en > now());
create policy "report crea autor" on report for insert to authenticated
  with check (autor = (select auth.uid()));
create policy "report edita autor" on report for update to authenticated
  using (autor = (select auth.uid()) and likes + dislikes = 0)
  with check (autor = (select auth.uid()));

-- voto: cada quien ve y cambia el suyo, y solo mientras el reporte esté vigente
-- (el propio reporte lo bloquea el trigger voto_validar)
create policy "voto lectura" on voto for select to authenticated
  using (autor = (select auth.uid()));
create policy "voto crea autor" on voto for insert to authenticated
  with check (autor = (select auth.uid())
              and exists (select 1 from report r where r.id = voto.report_id and r.expira_en > now()));
create policy "voto edita autor" on voto for update to authenticated
  using (autor = (select auth.uid()))
  with check (autor = (select auth.uid())
              and exists (select 1 from report r where r.id = voto.report_id and r.expira_en > now()));
create policy "voto borra autor" on voto for delete to authenticated
  using (autor = (select auth.uid())
         and exists (select 1 from report r where r.id = voto.report_id and r.expira_en > now()));

-- comentario: todos leen; crea el autor, solo en un reporte vigente
create policy "coment lectura" on comentario for select to anon, authenticated using (true);
create policy "coment crea autor" on comentario for insert to authenticated
  with check (autor = (select auth.uid())
              and exists (select 1 from report r where r.id = comentario.report_id and r.expira_en > now()));

-- message: con sesión se leen los vigentes; crea el autor
create policy "msg lectura vigente" on message for select to authenticated using (expira_en > now());
create policy "msg crea autor" on message for insert to authenticated
  with check (autor = (select auth.uid()));

-- perfil: cada quien ve y edita el suyo
create policy "perfil propio select" on perfil for select to authenticated
  using (id = (select auth.uid()));
create policy "perfil propio update" on perfil for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));
