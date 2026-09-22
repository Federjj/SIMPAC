alter table estacion add column if not exists lat double precision generated always as (st_y(geom)) stored;
alter table estacion add column if not exists lon double precision generated always as (st_x(geom)) stored;
alter table lectura_caudal add column if not exists lat double precision generated always as (st_y(geom)) stored;
alter table lectura_caudal add column if not exists lon double precision generated always as (st_x(geom)) stored;
