-- Serie mensual del ICEN (Índice Costero El Niño) para el gráfico del frontend: los
-- últimos ~24 meses coloreados por categoría, para ver cómo se desarrolla El Niño costero.
-- La tabla indice solo guarda el último valor.
--
-- La llenan dos tareas del worker (backend/ingesta):
--   ingesta (cada hora): los últimos 36 meses del ICEN.txt del IGP, origen 'IGP'.
--   enfen (cada 6 h):    todos los meses de la tabla de cada Informe Técnico ENFEN nuevo
--                        (normalmente 12), origen 'ENFEN', con su categoría oficial.
-- Precedencia (guardar.SQL_ICEN_SERIE): un mes del ENFEN nunca lo pisa el IGP; el IGP solo
-- completa los meses que el ENFEN no tiene y corrige los suyos; un informe nuevo corrige
-- al anterior. Nada se borra.
--
-- Tras aplicarla no hay que cargar nada a mano: la próxima corrida de 'enfen' ve que la
-- serie no tiene meses del ENFEN y relee una sola vez el informe vigente; la ingesta
-- horaria completa los meses anteriores con el IGP.

create table public.icen_serie (
  mes        text primary key
             check (mes ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),   -- 'AAAA-MM' (ordena como texto)
  valor      double precision not null,
  categoria  text not null,          -- ENFEN: la oficial de la tabla de su informe. IGP: calculada por
                                     -- SIMPAC con los cortes de la Nota Técnica ENFEN 01-2024 (en los
                                     -- meses fríos solo dice 'Fría': el ENFEN no publica cortes fríos)
  origen     text not null check (origen in ('IGP', 'ENFEN')),
  ts_captura timestamptz not null default now()   -- cuándo llegó el valor vigente de ese mes
);
comment on table public.icen_serie is
  'ICEN mensual (IGP y Tabla del Informe Técnico ENFEN; el ENFEN tiene precedencia). Lo escribe el worker.';
comment on column public.icen_serie.categoria is
  'ENFEN: la oficial de la tabla de su informe. IGP: calculada por SIMPAC con los cortes de la Nota Técnica ENFEN 01-2024 (en los meses fríos solo dice Fría).';

-- Solo lectura para el Data API (el worker escribe con su propia conexión).
alter table public.icen_serie enable row level security;
revoke all on public.icen_serie from anon, authenticated;
grant select on public.icen_serie to anon, authenticated;
create policy "lectura publica icen_serie" on public.icen_serie for select using (true);
