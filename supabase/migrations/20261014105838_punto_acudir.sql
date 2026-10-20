-- "A dónde acudir": establecimientos de salud, comisarías, compañías de bomberos y oficinas de
-- Defensa Civil con coordenadas, cargados desde fuentes oficiales con backend/mapas/cargar_acudir.py
-- (carga manual desde backend/data/acudir/, como los ríos vigilados; no corre en el worker).
--
-- Honestidad del dato (se muestra en la web):
--   - Hoy (14-10-2026) no existe ninguna fuente oficial abierta con albergues, zonas seguras ni
--     puntos de reunión georreferenciados, ni para Cajamarca ni para el país (INDECI, CENEPRED,
--     SIGRID y datosabiertos.gob.pe revisados). Los tipos 'albergue' y 'zona_segura' quedan
--     previstos para cuando una municipalidad publique su lista (se cargaría con su fuente_url).
--     Nunca se cargan estimaciones ni colegios como albergues.
--   - atiende_24h solo es true/false cuando la fuente trae el horario (RENIPRESS); las comisarías
--     y los bomberos quedan en null aunque atiendan de corrido: la fuente no lo dice.
--   - Cada fila lleva fuente, fuente_url, licencia, atribución y la fecha del dato (actualizado).
create table public.punto_acudir (
  clave        text primary key check (clave ~ '^[a-z_]+:[A-Za-z0-9_.-]+$'),
                                   -- '<fuente>:<id>': 'renipress:00007686', 'comisarias:5000',
                                   -- 'bomberos:59', 'manual:indeci_cajamarca'
  tipo         text not null check (tipo in ('salud', 'comisaria', 'bomberos', 'zona_segura', 'albergue', 'otro')),
  nombre       text not null,      -- en lenguaje claro ('Hospital Regional Docente Cajamarca')
  categoria    text,               -- 'Hospital II-2', 'Puesto de salud I-1', 'Comisaría tipo A',
                                   -- 'Compañía de bomberos', 'Defensa Civil (INDECI)'
  atiende_24h  boolean,            -- solo si la fuente lo dice; null = no se sabe
  direccion    text,
  distrito     text,
  provincia    text,
  departamento text not null,      -- canónico (backend/ingesta/departamentos.py)
  ubigeo       char(6),
  telefono     text,               -- como lo da la fuente, solo con espacios normalizados; null si no trae dígitos
  lat          double precision not null,
  lon          double precision not null,
  geom         geometry(Point, 4326) generated always as (st_setsrid(st_makepoint(lon, lat), 4326)) stored,
  fuente       text not null,      -- 'SUSALUD RENIPRESS', 'MININTER / CENEPRED', 'CGBVP + CENEPRED', 'gob.pe'
  fuente_url   text not null check (fuente_url ~ '^https://'),
  fuente_id    text,               -- COD_IPRESS, cod_cpnp, número de compañía
  licencia     text,               -- 'ODC-By' | null (información pública del Estado peruano)
  atribucion   text not null,
  detalle      jsonb not null default '{}'::jsonb check (jsonb_typeof(detalle) = 'object'),
                                   -- lo demás que trae la fuente: horario, institucion, clasificacion,
                                   -- tipo_comisaria, comandancia, nota...
  actualizado  date not null,      -- fecha del dato en la fuente (Last-Modified del CSV, fecha del
                                   -- padrón, o de la verificación manual)
  cargado_en   timestamptz not null default now(),
  check (lat between -18.5 and 0.1 and lon between -81.5 and -68.5)   -- dentro del Perú
);
create index punto_acudir_geom_idx on public.punto_acudir using gist (geom);
create index punto_acudir_tipo_idx on public.punto_acudir (tipo, departamento, atiende_24h);

-- Lectura pública; escribe solo el cargador (rol postgres, dueño de la tabla).
alter table public.punto_acudir enable row level security;
revoke all on public.punto_acudir from anon, authenticated;
grant select on public.punto_acudir to anon, authenticated;
create policy "lectura publica punto acudir" on public.punto_acudir for select using (true);

comment on table public.punto_acudir is
  'A dónde acudir: salud (SUSALUD RENIPRESS), comisarías (MININTER vía CENEPRED), bomberos (CGBVP + CENEPRED) y Defensa Civil (gob.pe), con fuente y fecha. Sin albergues ni zonas seguras: no hay fuente oficial abierta (14-10-2026). Carga: backend/mapas/cargar_acudir.py.';
