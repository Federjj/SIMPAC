create table if not exists mapa (
  id         bigint generated always as identity primary key,
  uuid       text,
  titulo     text not null,
  variable   text,
  periodo    text,
  fuente     text default 'SENAMHI/IDESEP',
  geojson    jsonb not null,
  ts_captura timestamptz default now()
);
alter table mapa enable row level security;
grant select on mapa to anon, authenticated;
drop policy if exists "lectura publica mapa" on mapa;
create policy "lectura publica mapa" on mapa for select using (true);
