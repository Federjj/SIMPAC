-- Comunidad: fotos de los reportes y chat en tiempo real.
--
-- 1) Bucket público "reportes" para la foto opcional de un reporte ciudadano. Sube solo quien
--    tiene sesión y solo dentro de la carpeta de su propio uid (<uid>/<archivo>); se lee en
--    público (la foto va en report.foto_url, que ya es pública); nadie edita ni borra desde el
--    cliente. Límite 3 MB y solo imágenes (el cliente la reduce a 1280 px antes de subirla).
-- 2) La tabla message entra en la publicación supabase_realtime: el chat por zona recibe los
--    mensajes nuevos al instante (postgres_changes respeta la RLS: solo con sesión y solo los
--    vigentes). El cliente mantiene además un sondeo cada 10 s para los vencimientos.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('reportes', 'reportes', true, 3145728, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
  set public = excluded.public,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "reportes foto sube autor" on storage.objects;
create policy "reportes foto sube autor" on storage.objects for insert to authenticated
  with check (
    bucket_id = 'reportes'
    and (select auth.uid())::text = (storage.foldername(name))[1]
  );

drop policy if exists "reportes foto lectura publica" on storage.objects;
create policy "reportes foto lectura publica" on storage.objects for select to anon, authenticated
  using (bucket_id = 'reportes');

-- sin políticas de update ni delete: una foto subida no se cambia ni se borra desde el cliente

-- chat en tiempo real (idempotente: si ya estuviera en la publicación, no falla)
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'message'
  ) then
    alter publication supabase_realtime add table public.message;
  end if;
end $$;
