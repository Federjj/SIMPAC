-- Comunidad: ids UUID, lo que decide la comunidad lo calcula la BD, y cada rol solo
-- puede escribir las columnas que le tocan.
--
--  * report, voto, comentario y message pasan a id uuid (no enumerables: con ids
--    1, 2, 3... cualquiera recorre todos los reportes). Los usuarios ya eran uuid
--    (auth.users.id) y perfil.id lo referencia.
--  * estado, confianza, likes, dislikes, expira_en y creado_en los pone la BD, no el
--    cliente: nadie puede auto-confirmar su reporte ni hacer un mensaje eterno.
--  * No se puede votar el propio reporte ni uno vencido, ni mover un voto a otro.
--  * El perfil se crea solo al registrarse; la reputación solo la cambian los votos.
--
-- Se recrean las tablas porque estaban vacías (el guard aborta si hay filas).

do $$
begin
  if exists (select 1 from public.report) or exists (select 1 from public.voto)
     or exists (select 1 from public.comentario) or exists (select 1 from public.message) then
    raise exception 'Abortado: hay filas en las tablas de comunidad; hace falta migrar los datos';
  end if;
end $$;

drop table if exists public.comentario;
drop table if exists public.voto;
drop table if exists public.message;
drop table if exists public.report;

-- Tipos estilo Waze (foco: clima/agua e impacto en vías). subtipo solo para atasco.
create table public.report (
  id          uuid primary key default gen_random_uuid(),
  autor       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  tipo        text not null check (tipo in ('inundacion', 'huayco', 'lluvia_intensa', 'via_bloqueada',
                                            'atasco', 'bache', 'accidente', 'otro')),
  -- (con coalesce: un CHECK que da NULL cuenta como válido y dejaría pasar un atasco sin subtipo)
  subtipo     text check (case when tipo = 'atasco'
                               then coalesce(subtipo in ('leve', 'moderado', 'detenido'), false)
                               else subtipo is null end),
  descripcion text check (char_length(descripcion) <= 500),
  foto_url    text check (foto_url ~ '^https://'),
  -- solo dentro del Perú (caja aproximada)
  geom        geometry(Point, 4326) not null
              check (st_x(geom) between -81.5 and -68.5 and st_y(geom) between -18.5 and 0.1),
  likes       int  not null default 0,
  dislikes    int  not null default 0,
  confianza   double precision not null default 0.5 check (confianza between 0 and 1),
  estado      text not null default 'sin_confirmar'
              check (estado in ('sin_confirmar', 'confirmado', 'descartado')),
  expira_en   timestamptz not null default now() + interval '12 hours',
  creado_en   timestamptz not null default now()
);
create index report_geom_idx  on public.report using gist (geom);
create index report_autor_idx on public.report (autor, creado_en);
create index report_expira_idx on public.report (expira_en);

create table public.voto (
  id        uuid primary key default gen_random_uuid(),
  report_id uuid not null references public.report(id) on delete cascade,
  autor     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  valor     smallint not null check (valor in (-1, 1)),   -- 1 = like, -1 = dislike
  creado_en timestamptz not null default now(),
  unique (report_id, autor)
);
create index voto_autor_idx on public.voto (autor);

create table public.comentario (
  id        uuid primary key default gen_random_uuid(),
  report_id uuid not null references public.report(id) on delete cascade,
  autor     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  texto     text not null check (char_length(texto) between 1 and 500),
  creado_en timestamptz not null default now()
);
create index comentario_report_idx on public.comentario (report_id, creado_en);
create index comentario_autor_idx  on public.comentario (autor);

create table public.message (
  id        uuid primary key default gen_random_uuid(),
  autor     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  zona      text,
  contenido text not null check (char_length(contenido) between 1 and 500),
  geom      geometry(Point, 4326),
  expira_en timestamptz not null default now() + interval '2 hours',
  creado_en timestamptz not null default now()
);
create index message_zona_idx  on public.message (zona, expira_en);
create index message_autor_idx on public.message (autor, creado_en);

alter table public.report     enable row level security;
alter table public.voto       enable row level security;
alter table public.comentario enable row level security;
alter table public.message    enable row level security;

-- perfil: sin roles (la validación es comunitaria); reputación la mueven los votos.
alter table public.perfil drop column if exists rol;
update public.perfil set reputacion = 0 where reputacion is null;
alter table public.perfil alter column reputacion set not null;
alter table public.perfil add constraint perfil_nombre_largo check (char_length(nombre) <= 80);

-- ---------------------------------------------------------------------------
-- Permisos por columna: lo que no está aquí, el cliente no lo puede escribir.
-- ---------------------------------------------------------------------------
revoke all on public.report, public.voto, public.comentario, public.message, public.perfil
  from anon, authenticated;

grant select on public.report, public.comentario to anon, authenticated;
grant select on public.voto, public.message, public.perfil to authenticated;

grant insert (autor, tipo, subtipo, descripcion, foto_url, geom) on public.report to authenticated;
grant update (descripcion, foto_url)                   on public.report     to authenticated;
grant insert (report_id, autor, valor)                 on public.voto       to authenticated;
-- el upsert de supabase-js reescribe la clave; el trigger impide cambiarla de verdad
grant update (report_id, autor, valor)                 on public.voto       to authenticated;
grant delete                                           on public.voto       to authenticated;
grant insert (report_id, autor, texto)                 on public.comentario to authenticated;
grant insert (autor, zona, contenido, geom)            on public.message    to authenticated;
grant update (nombre, zona)                            on public.perfil     to authenticated;

-- report
drop policy if exists "report lectura publica" on public.report;
create policy "report lectura publica" on public.report for select to anon, authenticated using (true);
drop policy if exists "report crea autor" on public.report;
create policy "report crea autor" on public.report for insert to authenticated
  with check (autor = (select auth.uid()));
drop policy if exists "report edita autor" on public.report;
create policy "report edita autor" on public.report for update to authenticated
  using (autor = (select auth.uid()) and likes + dislikes = 0)   -- ya votado, ya no se edita
  with check (autor = (select auth.uid()));

-- voto: cada quien ve y cambia solo el suyo; el público ve report.likes / dislikes
drop policy if exists "voto lectura" on public.voto;
create policy "voto lectura" on public.voto for select to authenticated
  using (autor = (select auth.uid()));
drop policy if exists "voto crea autor" on public.voto;
create policy "voto crea autor" on public.voto for insert to authenticated
  with check (
    autor = (select auth.uid())
    and exists (select 1 from public.report r
                where r.id = voto.report_id
                  and r.autor <> (select auth.uid())   -- no votar el propio reporte
                  and r.expira_en > now())             -- ni uno vencido
  );
drop policy if exists "voto edita autor" on public.voto;
create policy "voto edita autor" on public.voto for update to authenticated
  using (autor = (select auth.uid()))
  with check (
    autor = (select auth.uid())
    and exists (select 1 from public.report r
                where r.id = voto.report_id and r.expira_en > now())
  );
drop policy if exists "voto borra autor" on public.voto;
create policy "voto borra autor" on public.voto for delete to authenticated
  using (autor = (select auth.uid()));

-- comentario
drop policy if exists "coment lectura" on public.comentario;
create policy "coment lectura" on public.comentario for select to anon, authenticated using (true);
drop policy if exists "coment crea autor" on public.comentario;
create policy "coment crea autor" on public.comentario for insert to authenticated
  with check (autor = (select auth.uid()));

-- message: expira_en lo pone la BD, así que siempre vence
drop policy if exists "msg lectura vigente" on public.message;
create policy "msg lectura vigente" on public.message for select to authenticated
  using (expira_en > now());
drop policy if exists "msg crea autor" on public.message;
create policy "msg crea autor" on public.message for insert to authenticated
  with check (autor = (select auth.uid()));

-- perfil: select y update del propio; el insert lo hace el trigger de registro
drop policy if exists "perfil propio upsert" on public.perfil;
drop policy if exists "perfil propio select" on public.perfil;
create policy "perfil propio select" on public.perfil for select to authenticated
  using (id = (select auth.uid()));
drop policy if exists "perfil propio update" on public.perfil;
create policy "perfil propio update" on public.perfil for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- ---------------------------------------------------------------------------
-- Funciones de trigger: en un esquema que el Data API no expone, SECURITY DEFINER
-- con search_path vacío. No se pueden llamar por RPC.
-- ---------------------------------------------------------------------------
create schema if not exists privado;
revoke all on schema privado from public, anon, authenticated;

-- Cada voto actualiza el reporte y la reputación de su autor. Incrementos atómicos
-- sobre la fila del reporte: votos simultáneos no se pisan.
-- confianza = (likes + 1) / (likes + dislikes + 2): arranca en 0.5 y se mueve con los votos.
-- Saldo neto de 3 confirma o descarta (umbral provisional, a calibrar con el equipo).
create or replace function privado.voto_aplicar()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_report uuid;
  d_like   int := 0;
  d_dis    int := 0;
begin
  if tg_op = 'UPDATE' and (new.report_id <> old.report_id or new.autor <> old.autor) then
    raise exception 'un voto no puede cambiar de reporte ni de autor';
  end if;
  if tg_op in ('UPDATE', 'DELETE') then
    d_like := d_like - (old.valor = 1)::int;
    d_dis  := d_dis  - (old.valor = -1)::int;
    v_report := old.report_id;
  end if;
  if tg_op in ('INSERT', 'UPDATE') then
    d_like := d_like + (new.valor = 1)::int;
    d_dis  := d_dis  + (new.valor = -1)::int;
    v_report := new.report_id;
  end if;
  if d_like = 0 and d_dis = 0 then
    return null;
  end if;

  update public.report r set
    likes     = r.likes + d_like,
    dislikes  = r.dislikes + d_dis,
    confianza = (r.likes + d_like + 1)::double precision
                / (r.likes + d_like + r.dislikes + d_dis + 2),
    estado    = case
                  when (r.likes + d_like) - (r.dislikes + d_dis) >= 3 then 'confirmado'
                  when (r.dislikes + d_dis) - (r.likes + d_like) >= 3 then 'descartado'
                  else 'sin_confirmar'
                end
  where r.id = v_report;

  update public.perfil p set reputacion = p.reputacion + (d_like - d_dis)
  where p.id = (select r.autor from public.report r where r.id = v_report);

  return null;
end $$;
revoke all on function privado.voto_aplicar() from public, anon, authenticated;

create trigger voto_aplicar after insert or update or delete on public.voto
  for each row execute function privado.voto_aplicar();

-- Límite por autor y por hora (reportes 5/h, mensajes 30/h), contra el spam.
create or replace function privado.limite_por_hora()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  n int;
begin
  execute format('select count(*) from public.%I where autor = $1 and creado_en > now() - interval ''1 hour''',
                 tg_table_name)
    into n using new.autor;
  if n >= tg_argv[0]::int then
    raise exception 'límite de % por hora alcanzado', tg_argv[0];
  end if;
  return new;
end $$;
revoke all on function privado.limite_por_hora() from public, anon, authenticated;

create trigger report_limite before insert on public.report
  for each row execute function privado.limite_por_hora('5');
create trigger message_limite before insert on public.message
  for each row execute function privado.limite_por_hora('30');

-- Perfil automático al registrarse (supabase.auth.signUp con options.data.nombre).
create or replace function privado.crear_perfil()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.perfil (id, nombre)
  values (new.id, left(new.raw_user_meta_data ->> 'nombre', 80))
  on conflict (id) do nothing;
  return new;
end $$;
revoke all on function privado.crear_perfil() from public, anon, authenticated;

drop trigger if exists crear_perfil on auth.users;
create trigger crear_perfil after insert on auth.users
  for each row execute function privado.crear_perfil();
