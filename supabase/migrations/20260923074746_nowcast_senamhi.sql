-- Nowcasting de lluvia de SENAMHI (g_nowcasting:view_nowcasting): manchas de ~2 km para ahora
-- (análisis), +1 h y +2 h. EXPERIMENTAL ("producto referencial y aún en etapa de calibración").
-- Tiene huecos (22-09: detenido desde las 20:40). Lo llena la tarea 'nowcast' (cada 10 min).
-- Nada se borra por una falla: las vistas dejan de mostrar una emisión de más de 30 min.
create table public.nowcast_producto (
  horizonte_min smallint primary key check (horizonte_min in (0, 60, 120)),  -- 0 = análisis (ahora)
  fichero       text not null check (fichero ~ '^nowcasting_\d{8}-\d{4}_(analysis|forecast)_\d{8}-\d{4}_web$'),
  emision       timestamptz not null,   -- hora del nombre del fichero (hora de Lima)
  valido_desde  timestamptz not null,   -- fecha1 del WFS (UTC)
  valido_hasta  timestamptz not null,   -- fecha2 del WFS (UTC)
  manchas       int not null default 0, -- polígonos de nivel 1 a 3 dentro del recuadro del Perú
  ts_captura    timestamptz not null default now()
);
create table public.nowcast_mancha (
  horizonte_min smallint not null references public.nowcast_producto (horizonte_min) on delete cascade,
  nivel         smallint not null check (nivel between 1 and 3),   -- leyenda SENAMHI: moderada, fuerte, extrema
  geom          geometry(MultiPolygon, 4326) not null,             -- unión de las manchas del nivel (~330 m)
  primary key (horizonte_min, nivel)
);
alter table public.nowcast_producto enable row level security;
alter table public.nowcast_mancha enable row level security;
revoke all on public.nowcast_producto, public.nowcast_mancha from anon, authenticated;
grant select on public.nowcast_producto, public.nowcast_mancha to anon, authenticated;
create policy "lectura publica nowcast producto" on public.nowcast_producto for select using (true);
create policy "lectura publica nowcast mancha" on public.nowcast_mancha for select using (true);

-- El umbral de 30 min vive solo aquí (el frontend usa vigente y vence_en; no lo recalcula).
create view public.nowcast_estado with (security_invoker = true) as
select horizonte_min, fichero, emision, valido_desde, valido_hasta, manchas, ts_captura,
       emision + interval '30 minutes' as vence_en,
       emision >= now() - interval '30 minutes' as vigente
from public.nowcast_producto;
create view public.nowcast_vigente with (security_invoker = true) as
select m.horizonte_min, m.nivel, p.emision, p.valido_desde, p.valido_hasta,
       st_asgeojson(m.geom, 3)::json as geojson
from public.nowcast_mancha m join public.nowcast_producto p using (horizonte_min)
where p.emision >= now() - interval '30 minutes'
order by m.horizonte_min, m.nivel;
revoke all on public.nowcast_estado, public.nowcast_vigente from anon, authenticated;
grant select on public.nowcast_estado, public.nowcast_vigente to anon, authenticated;
