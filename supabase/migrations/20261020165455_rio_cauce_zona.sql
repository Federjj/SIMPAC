-- Zonas que podrían inundarse junto a los ríos del país (rio_cauce), ESTIMADAS con el relieve como
-- se hizo a mano para el Mashcón (rio_zona tipo 'estimada'): altura sobre el drenaje más cercano (HAND)
-- sobre el Copernicus DEM GLO-30 con el trazo de ANA grabado, relleno de depresiones y D8, en un tramo
-- de hasta 60 km alrededor de la estación o la ciudad principal (backend/mapas/zonas_relieve.py).
-- Dos umbrales por río: 'bajo_2m' (~2 m sobre el cauce; la web la dibuja rayada) y 'bajo_3m' (~3 m; lisa
-- y tenue). Honestidad del dato: es una estimación, no un mapa oficial de inundación; no considera
-- muros, puentes ni drenajes; el error vertical del modelo (2-3 m) es del orden de los umbrales, por lo
-- que el usuario nunca ve metros, solo "zona que podría inundarse si el río se desborda" y "zona que
-- también podría inundarse" (cada fila lleva metodo, fuente, licencia, atribucion y nota).
--
-- Carga ÚNICA con backend/mapas/cargar_cauces_zonas.py (prueba en seco y --aplicar), upsert por clave;
-- un río sin archivo no tiene zonas y nada se borra sin --podar (una corrida fallida no apaga una zona).

create table public.rio_cauce_zona (
  clave        text primary key check (clave ~ '^[a-z0-9_]+:relieve:[0-9]+$'),  -- 'rimac:relieve:2'
  rio_ana      text not null check (rio_ana ~ '^[a-z0-9_]+$'),   -- = rio_cauce.rio_ana (sin FK: los cargadores son independientes)
  subtipo      text not null check (subtipo in ('bajo_2m', 'bajo_3m')),
  geom         geometry(MultiPolygon, 4326) not null,            -- ~6 m, 5 decimales (ya simplificada por el pipeline)
  area_km2     numeric not null check (area_km2 > 0),
  metodo       text not null,                                    -- 'HAND sobre Copernicus GLO-30, umbral ~2 m / ~3 m, tramo de N km alrededor de X'
  fuente       text not null,
  licencia     text not null,
  atribucion   text not null,                                    -- aviso Copernicus (DLR, Airbus, UE y ESA) + ANA
  fecha_fuente date not null,                                    -- cuándo se bajaron las teselas
  nota         text not null,                                    -- la advertencia de estimación que ve el usuario
  cargado_en   timestamptz not null default now(),
  unique (rio_ana, subtipo)
);
create index rio_cauce_zona_geom_idx on public.rio_cauce_zona using gist (geom);
create index rio_cauce_zona_rio_idx on public.rio_cauce_zona (rio_ana);

alter table public.rio_cauce_zona enable row level security;
revoke all on public.rio_cauce_zona from anon, authenticated;
grant select on public.rio_cauce_zona to anon, authenticated;
create policy "lectura publica rio cauce zona" on public.rio_cauce_zona for select using (true);

-- Para el frontend (capa de zonas de los ríos del país): GeoJSON con 5 decimales de la geometría
-- simplificada a ~6 m (0.00006 grados). Si la vista no existe o está vacía, la web no dibuja nada.
create view public.rio_cauce_zona_mapa with (security_invoker = true) as
select z.clave, z.rio_ana, z.subtipo, z.area_km2, z.metodo, z.fuente, z.licencia, z.atribucion, z.nota,
       st_asgeojson(st_simplifypreservetopology(z.geom, 0.00006), 5)::json as geojson
from public.rio_cauce_zona z;

revoke all on public.rio_cauce_zona_mapa from anon, authenticated;
grant select on public.rio_cauce_zona_mapa to anon, authenticated;

comment on table public.rio_cauce_zona is
  'Zonas que podrían inundarse junto a los ríos del país, estimadas con el relieve (HAND sobre Copernicus GLO-30 con el trazo de ANA; backend/mapas/zonas_relieve.py). Carga única: backend/mapas/cargar_cauces_zonas.py. Estimación, no mapa oficial: nunca se muestra en metros.';
