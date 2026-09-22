-- Datos oficiales: vista del último caudal por estación, horas de lluvia en hora de
-- Perú y sin valores por defecto que inventen un lugar.

-- lectura_caudal guarda el historial (una fila por estación y hora). El mapa, las
-- alertas y el snapshot quieren solo la última lectura de cada estación.
-- security_invoker: la vista respeta el RLS de lectura_caudal (lectura pública).
create or replace view public.caudal_actual with (security_invoker = true) as
select distinct on (estacion)
  estacion, rio, departamento, provincia, fecha, hora, valor, unidad,
  umbral_alerta, umbral_emergencia, tendencia, estado, lat, lon, ts_captura
from public.lectura_caudal
order by estacion, fecha desc, hora desc;   -- hora siempre es 'HH:MM', ordena bien como texto

revoke all on public.caudal_actual from anon, authenticated;
grant select on public.caudal_actual to anon, authenticated;

-- ts ("YYYY/MM/DD - HH") es hora de Perú; la ingesta anterior guardaba medido_en como
-- si fuera UTC (5 h antes). Idempotente: solo toca las filas que no coinciden.
update public.lectura_lluvia
set medido_en = to_timestamp(ts, 'YYYY/MM/DD - HH24')::timestamp at time zone 'America/Lima'
where medido_en is distinct from (to_timestamp(ts, 'YYYY/MM/DD - HH24')::timestamp at time zone 'America/Lima');

-- 'Cajamarca' por defecto hacía que toda estación o alerta sin dato pareciera de Cajamarca.
alter table public.estacion alter column departamento drop default;
alter table public.alerta   alter column zona         drop default;
