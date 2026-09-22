-- Índices El Niño al día, comunicado oficial del ENFEN, latido de las tareas del worker
-- y ríos con umbrales de nivel bajo.

-- indice: de dónde salió cada valor. El ICEN llega del IGP (a veces meses atrasado) y del
-- comunicado ENFEN; la ingesta se queda con el mes más nuevo.
alter table public.indice add column if not exists origen text;   -- IGP | ENFEN | NOAA
update public.indice set origen = 'IGP' where fuente = 'ICEN' and origen is null;
-- NOAA vigila El Niño con el RONI desde feb-2026; la fila del ONI clásico sale.
delete from public.indice where fuente = 'ONI';

-- Comunicado oficial ENFEN: estado del Sistema de Alerta (Vigilancia / Alerta de El Niño
-- o La Niña costeros, No activo). Lo llena la tarea 'enfen' del worker (cada 6 h).
create table public.comunicado_enfen (
  anio       int  not null,
  numero     int  not null,
  fecha      date not null,               -- emisión
  estado     text not null,               -- texto oficial, p. ej. 'Alerta de El Niño Costero'
  proximo    date,                        -- fecha anunciada del próximo comunicado
  resumen    text,                        -- frases oficiales sobre lo esperado
  url        text not null,               -- PDF
  ts_captura timestamptz not null default now(),
  primary key (anio, numero)
);
alter table public.comunicado_enfen enable row level security;
grant select on public.comunicado_enfen to anon, authenticated;
create policy "lectura publica comunicado" on public.comunicado_enfen for select using (true);

-- Latido: cuándo corrió de verdad cada tarea. El frontend avisa "sin actualizar" si la
-- ingesta se detiene (antes se deducía de indice.ts_captura, que no siempre se renueva).
create table public.latido (
  servicio text primary key,              -- 'ingesta' | 'enfen'
  ts       timestamptz not null default now(),
  resumen  jsonb
);
alter table public.latido enable row level security;
grant select on public.latido to anon, authenticated;
create policy "lectura publica latido" on public.latido for select using (true);

-- Ríos con umbrales de nivel bajo (vaciante: el de emergencia es MENOR que el de alerta).
-- Antes se leían como de crecida y salían en "emergencia" sin estarlo.
update public.lectura_caudal
set estado = case
    when valor <= umbral_emergencia then 'emergencia'
    when valor <= umbral_alerta then 'alerta'
    else 'normal'
  end
where umbral_emergencia < umbral_alerta and valor is not null;
