-- HU-15: mapas FEN por evento Y trimestre.
-- Cada registro de IDESEP trae un .zip por trimestre (DEF = diciembre a febrero, EFM = enero a
-- marzo, FMA = febrero a abril). Hasta hoy se guardaba solo el primero (una fila por evento);
-- desde ahora backend/mapas/cargar_fen.py guarda una fila por evento y trimestre.
--   trimestre  código de SENAMHI ('DEF', 'EFM', 'FMA'); null en el mapa mensual de precipitación
--   meses      texto legible que calcula el cargador ("diciembre de 1997 a febrero de 1998")
-- El índice único pasa de (uuid) a (uuid, coalesce(trimestre, '')): el upsert es por evento y
-- trimestre, y null cuenta como un valor (el mapa mensual sigue cabiendo una sola vez por uuid).
-- Las 5 filas que ya existían reciben su trimestre real (el primer .zip de cada registro:
-- DEF salvo el Niño Costero 2023, cuyo primer .zip es EFM) y se conservan.

alter table mapa add column if not exists trimestre text;
alter table mapa add column if not exists meses text;

comment on column mapa.trimestre is
  'Trimestre del mapa como lo nombra SENAMHI (DEF, EFM, FMA); null en el mapa mensual. Con uuid forma la clave del upsert.';
comment on column mapa.meses is
  'Meses que cubre el mapa, en palabras ("diciembre de 1997 a febrero de 1998"); lo calcula backend/mapas/cargar_fen.py.';

update mapa set trimestre = 'DEF', meses = 'diciembre de 1982 a febrero de 1983'
 where variable = 'FEN' and uuid = '5e888752-5eea-487f-91bc-f3281489bb33' and trimestre is null;
update mapa set trimestre = 'DEF', meses = 'diciembre de 1997 a febrero de 1998'
 where variable = 'FEN' and uuid = '25c9f90e-d845-43f0-ad6c-9aa32dcecf7c' and trimestre is null;
update mapa set trimestre = 'DEF', meses = 'diciembre de 2016 a febrero de 2017'
 where variable = 'FEN' and uuid = 'd57bba7e-cbb4-4f2d-9d8e-7bd013dae5d9' and trimestre is null;
update mapa set trimestre = 'DEF', meses = 'diciembre de 2023 a febrero de 2024'
 where variable = 'FEN' and uuid = 'd6e9a47a-2b78-4f8e-ad07-2c3e6f8f7b9e' and trimestre is null;
update mapa set trimestre = 'EFM', meses = 'enero a marzo de 2023'
 where variable = 'FEN' and uuid = '85118c06-f2bb-46a8-9432-bb0e0a67be8e' and trimestre is null;

drop index if exists mapa_uuid_key;
create unique index if not exists mapa_uuid_trimestre_key on mapa (uuid, (coalesce(trimestre, '')));
