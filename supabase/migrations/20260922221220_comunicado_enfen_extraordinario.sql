-- Los comunicados extraordinarios del ENFEN comparten numeración con los oficiales
-- (CE 01-2025 y CO 01-2025): la clave incluye si es extraordinario.
alter table public.comunicado_enfen add column extraordinario boolean not null default false;
alter table public.comunicado_enfen drop constraint comunicado_enfen_pkey;
alter table public.comunicado_enfen add primary key (anio, numero, extraordinario);
