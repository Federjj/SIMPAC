-- Lluvia 'ahora' en todo el Perú: última lectura horaria de cada estación de la capa WFS
-- g_umbrales:umbrales_precipitacion de SENAMHI (GeoServer de IDESEP), ~216 estaciones
-- automáticas de 24 departamentos. La llena la tarea 'lluvia_nacional' del worker
-- (backend/ingesta/lluvia_nacional.py), cada 30 min (las estaciones reportan cada hora, no
-- todas a la misma hora).
--
-- Una fila por estación. Cada corrida reemplaza las estaciones que vinieron (nunca con una
-- lectura más vieja que la guardada) y NO borra las que no vinieron: quedan con su
-- medido_en viejo y la vista lluvia_senamhi_actual las deja fuera pasadas 3 h. Solo se
-- purgan las que la capa dejó de publicar hace 30 días.
--
-- Fuente: SENAMHI. Sus términos exigen mostrar la leyenda literal "Información recopilada y
-- trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. El uso que se le
-- da a esta información es de mi (nuestra) entera responsabilidad" (también viene en el
-- latido 'lluvia_nacional', campo atribucion).

create table public.lluvia_senamhi (
  clave        text primary key,                -- 'NOMBRE@lat,lon': la capa no trae código y
                                                -- repite nombres (dos 'CABO INGA' a 400 m)
  nombre       text not null,
  cod          text references public.estacion(cod) on delete set null,
                                                -- nuestra estación, si se emparejó (< 1,5 km y
                                                -- mismo nombre sin GORE/M/H, o automática en el
                                                -- mismo punto); null = no está en la tabla
  departamento text,                            -- nombre canónico ('Cajamarca', 'San Martín')
  provincia    text,                            -- como vienen de SENAMHI (mayúsculas)
  distrito     text,
  cuenca       text,
  altitud_m    double precision,
  pp_1h        double precision check (pp_1h >= 0),
                                                -- mm en la hora que termina en medido_en
  umbral_1h    double precision,                -- mm/h: umbral de REFERENCIA de SENAMHI para la
                                                -- estación (1 a 25). Su visor marca 'Alerta' al
                                                -- superarlo, pero no está documentado como umbral
                                                -- oficial de alerta
  pp_6h        double precision check (pp_6h >= 0),
                                                -- mm en las 6 h que terminan en medido_en (campo
                                                -- pp_acum; NO es el acumulado del día ni de 3 h)
  umbral_6h    double precision,                -- referencia SENAMHI para esas 6 h (= 3 x umbral_1h)
  medido_en    timestamptz not null,            -- fecha + hora de la estación (hora de Perú)
  ts_captura   timestamptz not null default now(),   -- última vez que la capa la trajo
  geom         geometry(Point, 4326) not null,
  lat          double precision generated always as (st_y(geom)) stored,  -- comodidad para el frontend
  lon          double precision generated always as (st_x(geom)) stored
);
create index lluvia_senamhi_geom_idx   on public.lluvia_senamhi using gist (geom);
create index lluvia_senamhi_medido_idx on public.lluvia_senamhi (medido_en);
create index lluvia_senamhi_cod_idx    on public.lluvia_senamhi (cod);   -- lo usa el 'on delete set null'

-- Solo lectura para el Data API; escribe solo el worker (rol postgres, dueño de la tabla).
alter table public.lluvia_senamhi enable row level security;
revoke all on public.lluvia_senamhi from anon, authenticated;
grant select on public.lluvia_senamhi to anon, authenticated;
create policy "lectura publica lluvia senamhi" on public.lluvia_senamhi for select using (true);

-- Lo que se muestra como 'lloviendo ahora': solo lecturas de las últimas 3 horas (una
-- estación trabada o que la capa dejó de publicar no queda fija en el mapa).
-- security_invoker: respeta el RLS de lluvia_senamhi.
create view public.lluvia_senamhi_actual with (security_invoker = true) as
select clave, nombre, cod, departamento, provincia, distrito, cuenca, altitud_m,
       pp_1h, umbral_1h, pp_6h, umbral_6h, medido_en, ts_captura, lat, lon
from public.lluvia_senamhi
where medido_en >= now() - interval '3 hours';

revoke all on public.lluvia_senamhi_actual from anon, authenticated;
grant select on public.lluvia_senamhi_actual to anon, authenticated;
