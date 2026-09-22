-- La validación pasa a ser comunitaria (like/dislike + comentarios); fuera moderación/roles admin.
drop table if exists confirmation;

create table if not exists voto (
  id        bigint generated always as identity primary key,
  report_id bigint references report(id) on delete cascade,
  autor     uuid references auth.users(id),
  valor     smallint not null check (valor in (-1, 1)),  -- 1 = like, -1 = dislike
  creado_en timestamptz default now(),
  unique (report_id, autor)
);

create table if not exists comentario (
  id        bigint generated always as identity primary key,
  report_id bigint references report(id) on delete cascade,
  autor     uuid references auth.users(id),
  texto     text not null,
  creado_en timestamptz default now()
);

alter table voto enable row level security;
alter table comentario enable row level security;

grant select on voto, comentario to anon, authenticated;
grant insert, update, delete on voto to authenticated;
grant insert on comentario to authenticated;

drop policy if exists "voto lectura" on voto;
create policy "voto lectura" on voto for select using (true);
drop policy if exists "voto crea autor" on voto;
create policy "voto crea autor" on voto for insert with check (auth.uid() = autor);
drop policy if exists "voto edita autor" on voto;
create policy "voto edita autor" on voto for update using (auth.uid() = autor);
drop policy if exists "voto borra autor" on voto;
create policy "voto borra autor" on voto for delete using (auth.uid() = autor);

drop policy if exists "coment lectura" on comentario;
create policy "coment lectura" on comentario for select using (true);
drop policy if exists "coment crea autor" on comentario;
create policy "coment crea autor" on comentario for insert with check (auth.uid() = autor);
