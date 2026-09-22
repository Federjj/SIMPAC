-- Igual que estacion y lectura_caudal: el Data API devuelve geometry como hex (EWKB),
-- así que el frontend lee lat/lon de columnas generadas. No se pueden escribir.
alter table public.report add column lat double precision generated always as (st_y(geom)) stored;
alter table public.report add column lon double precision generated always as (st_x(geom)) stored;
