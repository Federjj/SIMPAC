-- Pronóstico oficial de SENAMHI por localidad (https://www.senamhi.gob.pe/?p=pronostico-meteorologico):
-- 277 localidades (17 en Cajamarca), 3 a 5 días. Lo llena la tarea 'pronostico' (cada hora).
-- Es un PUNTO por localidad: el frontend nunca sombrea el distrito. Upsert por (codigo, fecha):
-- una emisión más vieja no pisa una más nueva; solo se borran fechas pasadas.
-- Coordenadas: catálogo revisado backend/data/localidades_senamhi.json (la página no las trae).
create table public.pronostico_localidad (
  codigo         text not null check (codigo ~ '^\d{2}-\d{4}$'),  -- dp-localidad: '06-0011' = Cajamarca
  fecha          date not null,                 -- día pronosticado (hora de Perú)
  dp             text not null,                 -- '06'
  localidad      text not null,                 -- '0011'
  nombre         text not null,                 -- 'San Miguel de Pallaques' (legible)
  nombre_senamhi text not null,                 -- 'SAN MIGUEL DE PALLAQUES - CAJAMARCA' (literal)
  departamento   text,                          -- canónico (backend/ingesta/departamentos.py)
  emision        date not null,                 -- 'Emisión: martes, 22 de septiembre del 2026' (sin hora)
  icono_senamhi  text check (icono_senamhi ~ '^\d{3}$'),   -- el que eligió el pronosticador; no se dibuja
  tmax           smallint,
  tmin           smallint,
  texto          text not null,                 -- texto del pronosticador, literal
  tipo           text not null check (tipo in ('sin_lluvia', 'lluvia', 'tormenta', 'nieve')),
  posible        boolean not null default false, -- "tendencia a ..." o solo lo dice el ícono
  por            text not null check (por in ('texto', 'icono', 'texto+icono')),
  lluvia_segura  boolean not null default false, -- tormenta posible, pero la lluvia sí la afirma el texto
  granizo        boolean not null default false,
  intensidad     text check (intensidad in ('ligera', 'moderada', 'fuerte')),
  momento        text,                          -- 'en la tarde', 'al atardecer'...; nunca 'durante el día'
  cielo          text check (cielo in ('despejado', 'parcial', 'nublado', 'neblina')),  -- solo en sin_lluvia
  lat            double precision,              -- null = sin ubicar: no se muestra
  lon            double precision,
  ubicacion      text,                          -- de dónde sale el punto ('estación SENAMHI AUGUSTO WEBERBAUER (CO)')
  ts_captura     timestamptz not null default now(),
  primary key (codigo, fecha)
);
create index pronostico_localidad_fecha_idx on public.pronostico_localidad (fecha);
alter table public.pronostico_localidad enable row level security;
revoke all on public.pronostico_localidad from anon, authenticated;
grant select on public.pronostico_localidad to anon, authenticated;
create policy "lectura publica pronostico" on public.pronostico_localidad for select using (true);

create view public.pronostico_vigente with (security_invoker = true) as
select codigo, nombre, departamento, lat, lon, fecha, emision, tmax, tmin, texto,
       tipo, posible, por, lluvia_segura, granizo, intensidad, momento, cielo,
       'https://www.senamhi.gob.pe/?p=pronostico-detalle&dp=' || dp || '&localidad=' || localidad as url
from public.pronostico_localidad
where lat is not null and lon is not null
  and fecha between (now() at time zone 'America/Lima')::date and (now() at time zone 'America/Lima')::date + 2
  and emision >= (now() at time zone 'America/Lima')::date - 5;
revoke all on public.pronostico_vigente from anon, authenticated;
grant select on public.pronostico_vigente to anon, authenticated;
