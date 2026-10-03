-- Preferencias del mapa por usuario (capas encendidas/apagadas y opciones elegidas). Sin sesión la
-- app las guarda solo en el navegador (localStorage "simpac.mapa", frontend/src/lib/preferencias.js);
-- con sesión de Supabase Auth también aquí. Solo las ve y cambia su dueño; nada para anon.
-- (El frontend aún no tiene inicio de sesión: la tabla queda lista para cuando lo tenga.)

create table public.preferencia_mapa (
  usuario        uuid primary key default auth.uid() references auth.users(id) on delete cascade,
  version        smallint    not null default 1 check (version between 1 and 100),
  datos          jsonb       not null check (jsonb_typeof(datos) = 'object' and pg_column_size(datos) <= 4096),
  actualizado_en timestamptz not null default now()
);
comment on table public.preferencia_mapa is
  'Capas y opciones del mapa de cada usuario (lib/preferencias.js, esquema v1). Solo las ve y cambia su dueño.';

alter table public.preferencia_mapa enable row level security;
revoke all on public.preferencia_mapa from anon, authenticated;
grant select                           on public.preferencia_mapa to authenticated;
grant insert (usuario, version, datos) on public.preferencia_mapa to authenticated;
grant update (usuario, version, datos) on public.preferencia_mapa to authenticated;  -- upsert de supabase-js
grant delete                           on public.preferencia_mapa to authenticated;

create policy "preferencia lee dueno"   on public.preferencia_mapa for select to authenticated
  using (usuario = (select auth.uid()));
create policy "preferencia crea dueno"  on public.preferencia_mapa for insert to authenticated
  with check (usuario = (select auth.uid()));
create policy "preferencia edita dueno" on public.preferencia_mapa for update to authenticated
  using (usuario = (select auth.uid())) with check (usuario = (select auth.uid()));
create policy "preferencia borra dueno" on public.preferencia_mapa for delete to authenticated
  using (usuario = (select auth.uid()));

-- la hora la pone la BD, no el reloj del celular
create or replace function privado.preferencia_tocar()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.actualizado_en := now();
  return new;
end $$;
revoke all on function privado.preferencia_tocar() from public, anon, authenticated;

create trigger preferencia_tocar before insert or update on public.preferencia_mapa
  for each row execute function privado.preferencia_tocar();
