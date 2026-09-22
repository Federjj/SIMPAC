-- Comunidad: privacidad y límites (hallazgos de la revisión del 22 sep).
--
--  * Con autor + GPS + hora de cada reporte se arma el historial de ubicación de una
--    persona. Ya nadie lee la columna autor (ni de report ni de comentario), y los
--    reportes vencidos dejan de ser públicos. Cada quien ve los suyos con
--    rpc('mis_reportes'). message deja de exponer geom.
--  * "No votar el propio reporte" pasa a un trigger (la policy necesitaba leer autor).
--  * Tampoco se puede borrar un voto de un reporte vencido.
--  * comentario: límite por hora y solo sobre reportes vigentes.
--  * El límite por hora se serializa por autor: con requests en paralelo se colaban de más.

-- report: lectura por columna (sin autor) y solo de los vigentes
revoke select on public.report from anon, authenticated;
grant select (id, tipo, subtipo, descripcion, foto_url, geom, lat, lon, likes, dislikes,
              confianza, estado, expira_en, creado_en)
  on public.report to anon, authenticated;
drop policy if exists "report lectura publica" on public.report;
create policy "report lectura vigente" on public.report for select to anon, authenticated
  using (expira_en > now());

-- comentario: sin autor; solo se comenta un reporte vigente
revoke select on public.comentario from anon, authenticated;
grant select (id, report_id, texto, creado_en) on public.comentario to anon, authenticated;
drop policy if exists "coment crea autor" on public.comentario;
create policy "coment crea autor" on public.comentario for insert to authenticated
  with check (
    autor = (select auth.uid())
    and exists (select 1 from public.report r where r.id = comentario.report_id and r.expira_en > now())
  );

-- message: el chat muestra zona y texto; la posición exacta no se expone
revoke select on public.message from authenticated;
grant select (id, autor, zona, contenido, expira_en, creado_en) on public.message to authenticated;

-- voto: la policy ya no mira report.autor (no es legible); lo revisa un trigger
drop policy if exists "voto crea autor" on public.voto;
create policy "voto crea autor" on public.voto for insert to authenticated
  with check (
    autor = (select auth.uid())
    and exists (select 1 from public.report r where r.id = voto.report_id and r.expira_en > now())
  );
drop policy if exists "voto borra autor" on public.voto;
create policy "voto borra autor" on public.voto for delete to authenticated
  using (
    autor = (select auth.uid())
    and exists (select 1 from public.report r where r.id = voto.report_id and r.expira_en > now())
  );

create or replace function privado.voto_validar()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if exists (select 1 from public.report r where r.id = new.report_id and r.autor = new.autor) then
    raise exception 'no se puede votar el propio reporte';
  end if;
  return new;
end $$;
revoke all on function privado.voto_validar() from public, anon, authenticated;

drop trigger if exists voto_validar on public.voto;
create trigger voto_validar before insert on public.voto
  for each row execute function privado.voto_validar();

-- límite por hora: un lock por (tabla, autor) hasta el fin de la transacción, así dos
-- inserts simultáneos del mismo autor no cuentan a la vez
create or replace function privado.limite_por_hora()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  n int;
begin
  perform pg_advisory_xact_lock(hashtextextended(tg_table_name || ':' || new.autor::text, 0));
  execute format('select count(*) from public.%I where autor = $1 and creado_en > now() - interval ''1 hour''',
                 tg_table_name)
    into n using new.autor;
  if n >= tg_argv[0]::int then
    raise exception 'límite de % por hora alcanzado', tg_argv[0];
  end if;
  return new;
end $$;
revoke all on function privado.limite_por_hora() from public, anon, authenticated;

drop trigger if exists comentario_limite on public.comentario;
create trigger comentario_limite before insert on public.comentario
  for each row execute function privado.limite_por_hora('20');

-- mis reportes (vigentes y vencidos), para la pantalla de cuenta: supabase.rpc('mis_reportes')
create or replace function public.mis_reportes()
returns setof public.report
language sql
stable
security definer
set search_path = ''
as $$
  select * from public.report where autor = (select auth.uid()) order by creado_en desc
$$;
revoke all on function public.mis_reportes() from public, anon, authenticated;
grant execute on function public.mis_reportes() to authenticated;
