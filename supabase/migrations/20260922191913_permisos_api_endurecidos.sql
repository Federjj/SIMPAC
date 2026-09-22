-- Permisos del Data API: cerrar lo que no se usa.

-- rls_auto_enable() es la función del event trigger que activa RLS en tablas nuevas.
-- El trigger sigue funcionando (corre como su dueño); solo se quita que el API la llame.
-- La crea la plataforma (opción de auto-RLS), no una migración: en una BD sin ella se salta.
do $$
begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
  end if;
end $$;

-- Por defecto anon/authenticated recibían TRUNCATE, TRIGGER, REFERENCES y MAINTAIN en
-- cada tabla. TRUNCATE se salta el RLS. Nadie los usa: se quitan, también para las
-- tablas que se creen después.
revoke truncate, trigger, references, maintain
  on public.estacion, public.lectura_lluvia, public.lectura_caudal, public.indice,
     public.alerta, public.mapa, public.perfil, public.report, public.voto,
     public.comentario, public.message, public.caudal_actual
  from anon, authenticated;

alter default privileges for role postgres in schema public
  revoke truncate, trigger, references, maintain on tables from anon, authenticated;

-- spatial_ref_sys es de PostGIS (dueño supabase_admin) y el Data API lo deja escribible
-- por anon. postgres no puede quitar ese grant ni activar RLS, pero sí puede poner un
-- trigger que rechace cualquier escritura que venga de anon o authenticated.
create schema if not exists privado;
revoke all on schema privado from public, anon, authenticated;

create or replace function privado.srs_solo_lectura()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if current_user in ('anon', 'authenticated') then
    raise exception 'spatial_ref_sys es de solo lectura para el Data API';
  end if;
  return coalesce(new, old);
end $$;

drop trigger if exists srs_solo_lectura on public.spatial_ref_sys;
create trigger srs_solo_lectura before insert or update or delete on public.spatial_ref_sys
  for each row execute function privado.srs_solo_lectura();
drop trigger if exists srs_no_truncate on public.spatial_ref_sys;
create trigger srs_no_truncate before truncate on public.spatial_ref_sys
  for each statement execute function privado.srs_solo_lectura();
