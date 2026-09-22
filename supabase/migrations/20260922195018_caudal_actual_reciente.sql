-- caudal_actual: solo lecturas de ayer u hoy (fecha de Perú), la misma ventana que usa
-- la ingesta. Una estación que ANA deja de publicar ya no se queda para siempre en su
-- último estado (p. ej. en emergencia) en el mapa ni en el snapshot.
create or replace view public.caudal_actual with (security_invoker = true) as
select distinct on (estacion)
  estacion, rio, departamento, provincia, fecha, hora, valor, unidad,
  umbral_alerta, umbral_emergencia, tendencia, estado, lat, lon, ts_captura
from public.lectura_caudal
where fecha >= (now() at time zone 'America/Lima')::date - 1
order by estacion, fecha desc, hora desc;   -- hora siempre es 'HH:MM', ordena bien como texto
