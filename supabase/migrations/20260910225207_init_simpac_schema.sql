-- SIMPAC — Esquema inicial (PostgreSQL + PostGIS)

create extension if not exists postgis;

-- A) DATOS OFICIALES (lectura pública, escritura solo del backend/ingesta)
create table if not exists estacion (
  cod          text primary key,
  nombre       text not null,
  tipo         text,
  categoria    text,
  estado       text,
  departamento text default 'Cajamarca',
  fuente       text default 'SENAMHI',
  geom         geometry(Point, 4326)
);
create index if not exists estacion_geom_idx on estacion using gist (geom);

create table if not exists lectura_lluvia (
  id         bigint generated always as identity primary key,
  cod        text references estacion(cod),
  ts         text not null,
  medido_en  timestamptz,
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
  unidad            text,
  umbral_alerta     double precision,
  umbral_emergencia double precision,
  tendencia         text,
  estado            text,
  geom              geometry(Point, 4326),
  ts_captura        timestamptz default now(),
  unique (estacion, fecha, hora)
);
create index if not exists caudal_geom_idx on lectura_caudal using gist (geom);

create table if not exists indice (
  fuente     text primary key,
  periodo    text,
  valor      double precision,
  categoria  text,
  ts_captura timestamptz default now()
);

create table if not exists alerta (
  id       bigint generated always as identity primary key,
  tipo     text,
  referencia text,
  zona     text default 'Cajamarca',
  nivel    text,
  detalle  text,
  valor    double precision,
  umbral   double precision,
  geom     geometry(Point, 4326),
  vigente  boolean default true,
  ts       timestamptz default now()
);
create index if not exists alerta_vigente_idx on alerta (vigente, nivel);

-- B) COMUNIDAD (usuarios, reportes, confirmaciones, chat)
create table if not exists perfil (
  id         uuid primary key references auth.users(id) on delete cascade,
  nombre     text,
  rol        text default 'ciudadano',
  reputacion int  default 0,
  zona       geometry(Point, 4326),
  creado_en  timestamptz default now()
);

create table if not exists report (
  id          bigint generated always as identity primary key,
  autor       uuid references auth.users(id),
  tipo        text not null,
  descripcion text,
  foto_url    text,
  geom        geometry(Point, 4326) not null,
  confianza   double precision default 0,
  estado      text default 'sin_confirmar',
  expira_en   timestamptz,
  creado_en   timestamptz default now()
);
create index if not exists report_geom_idx on report using gist (geom);

create table if not exists confirmation (
  id        bigint generated always as identity primary key,
  report_id bigint references report(id) on delete cascade,
  autor     uuid references auth.users(id),
  sigue     boolean,
  creado_en timestamptz default now(),
  unique (report_id, autor)
);

create table if not exists message (
  id        bigint generated always as identity primary key,
  autor     uuid references auth.users(id),
  zona      text,
  contenido text,
  geom      geometry(Point, 4326),
  expira_en timestamptz,
  creado_en timestamptz default now()
);
create index if not exists message_zona_idx on message (zona, expira_en);

-- C) SEGURIDAD (RLS + grants)
alter table estacion        enable row level security;
alter table lectura_lluvia  enable row level security;
alter table lectura_caudal  enable row level security;
alter table indice          enable row level security;
alter table alerta          enable row level security;

grant select on estacion, lectura_lluvia, lectura_caudal, indice, alerta to anon, authenticated;

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

alter table perfil       enable row level security;
alter table report       enable row level security;
alter table confirmation enable row level security;
alter table message      enable row level security;

grant select, insert, update on perfil, report, confirmation, message to authenticated;
grant select on report to anon;

drop policy if exists "perfil propio select" on perfil;
create policy "perfil propio select" on perfil for select using (auth.uid() = id);
drop policy if exists "perfil propio upsert" on perfil;
create policy "perfil propio upsert" on perfil for insert with check (auth.uid() = id);
drop policy if exists "perfil propio update" on perfil;
create policy "perfil propio update" on perfil for update using (auth.uid() = id);

drop policy if exists "report lectura publica" on report;
create policy "report lectura publica" on report for select using (true);
drop policy if exists "report crea autor" on report;
create policy "report crea autor" on report for insert with check (auth.uid() = autor);
drop policy if exists "report edita autor" on report;
create policy "report edita autor" on report for update using (auth.uid() = autor);

drop policy if exists "conf lectura" on confirmation;
create policy "conf lectura" on confirmation for select using (auth.role() = 'authenticated');
drop policy if exists "conf crea autor" on confirmation;
create policy "conf crea autor" on confirmation for insert with check (auth.uid() = autor);

drop policy if exists "msg lectura vigente" on message;
create policy "msg lectura vigente" on message for select
  using (auth.role() = 'authenticated' and (expira_en is null or expira_en > now()));
drop policy if exists "msg crea autor" on message;
create policy "msg crea autor" on message for insert with check (auth.uid() = autor);
