-- Alertas de lluvia con la referencia de SENAMHI por estación (capa g_umbrales:umbrales_precipitacion),
-- escritas solo por la tarea 'lluvia_nacional' (backend/ingesta/lluvia_nacional.py). Reemplazan a las
-- de los umbrales provisionales de SIMPAC (20 y 40 mm en 24 h, 15 mm en 1 h), que se retiran.
-- Una fila por estación que pasó su referencia en 1 h o en 6 h: tipo 'lluvia', nivel siempre 'aviso'
-- (SENAMHI no documenta esa referencia como umbral de alerta; NO es un aviso oficial),
-- referencia = lluvia_senamhi.clave, ts = hora de la medición.

alter table public.alerta add column ventana_h smallint;
alter table public.alerta add column lat double precision generated always as (st_y(geom)) stored;
alter table public.alerta add column lon double precision generated always as (st_x(geom)) stored;

-- ventana_h solo existe en la lluvia medida, y esa lluvia nunca pasa de 'aviso'. El coalesce
-- hace falta: con tipo o nivel NULL la comparación da NULL y un CHECK con NULL deja pasar la fila.
alter table public.alerta add constraint alerta_lluvia_referencia_check
  check (ventana_h is null or coalesce(tipo = 'lluvia' and nivel = 'aviso' and ventana_h in (1, 6), false));

-- Las de los umbrales retirados (hoy no hay ninguna).
delete from public.alerta where tipo = 'lluvia';

-- Una alerta por estación. Solo el formato nuevo: si la ingesta vieja sigue corriendo hasta el
-- despliegue, sus filas (sin ventana_h) no chocan. La tarea usa to_regclass de este índice para
-- saber si la migración ya se aplicó.
create unique index alerta_lluvia_referencia_key on public.alerta (referencia)
  where tipo = 'lluvia' and ventana_h is not null;

-- Lo que se muestra: las vigentes; la lluvia medida, solo mientras su lectura tenga 3 h o menos
-- (igual que lluvia_senamhi_actual y el mapa); las del formato viejo (sin ventana_h), nunca.
create view public.alerta_actual with (security_invoker = true) as
select tipo, referencia, zona, nivel, detalle, valor, umbral, ventana_h, ts, lat, lon
from public.alerta
where vigente
  and (tipo is distinct from 'lluvia'
       or (ventana_h is not null and ts >= now() - interval '3 hours'));

revoke all on public.alerta_actual from anon, authenticated;
grant select on public.alerta_actual to anon, authenticated;

comment on column public.alerta.tipo is
  'caudal | nivel_bajo (niveles de ANA) | aviso (aviso oficial de SENAMHI) | lluvia (una estación midió más que la referencia de SENAMHI; no es aviso oficial)';
comment on column public.alerta.nivel is
  'aviso | alerta | emergencia. aviso SENAMHI: 2 aviso, 3 alerta, 4 emergencia. lluvia: siempre aviso';
comment on column public.alerta.referencia is
  'caudal y nivel_bajo: "Estación (río)"; aviso: "SENAMHI aviso N" o "SENAMHI lluvia 24h"; lluvia: lluvia_senamhi.clave';
comment on column public.alerta.ventana_h is
  'Solo lluvia: 1 = la lluvia de la última hora pasó umbral_1h; 6 = la de las últimas 6 h pasó umbral_6h (y la de 1 h no). valor y umbral son los de esa ventana';
comment on column public.alerta.ts is
  'lluvia: hora de la medición (caduca a las 3 h); los demás tipos: hora en que se escribió';
