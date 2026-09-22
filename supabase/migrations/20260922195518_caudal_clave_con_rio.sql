-- ANA tiene estaciones distintas con el mismo nombre en ríos distintos (p. ej. "San
-- Pedro" en el Charanal y en el Santa). Con la clave (estacion, fecha, hora) una pisaba
-- a la otra y caudal_actual mostraba solo una. La estación se identifica con su río.
alter table public.lectura_caudal drop constraint lectura_caudal_estacion_fecha_hora_key;
alter table public.lectura_caudal
  add constraint lectura_caudal_estacion_rio_fecha_hora_key unique (estacion, rio, fecha, hora);

create or replace view public.caudal_actual with (security_invoker = true) as
select distinct on (estacion, rio)
  estacion, rio, departamento, provincia, fecha, hora, valor, unidad,
  umbral_alerta, umbral_emergencia, tendencia, estado, lat, lon, ts_captura
from public.lectura_caudal
where fecha >= (now() at time zone 'America/Lima')::date - 1
order by estacion, rio, fecha desc, hora desc;   -- hora siempre es 'HH:MM', ordena bien como texto
