-- Comunidad: la foto de un reporte solo puede ser una foto del bucket "reportes" de este proyecto.
--
-- Antes, report.foto_url aceptaba cualquier URL https (check foto_url ~ '^https://') y
-- authenticated puede insertarla y editarla: un usuario con sesión podía guardar un enlace a
-- cualquier dominio, que la tarjeta del reporte pinta como <a href> e <img src> (enlace malicioso
-- dentro de Comunidad y, en la app Android, carga de imágenes de terceros con fuga de IP).
--
-- Ahora se exige, en dos capas:
--   1) CHECK report_foto_url_check: la URL pública del bucket "reportes" de ESTE proyecto
--      (https://clrnommkjyksnyrtnisf.supabase.co/storage/v1/object/public/reportes/<uuid>/<archivo>.jpg|jpeg|png|webp),
--      con el nombre de archivo solo en [A-Za-z0-9_-] (tal como lo genera lib/queries.js:subirFotoReporte).
--      Si el proyecto cambia de ref, hay que actualizar este patrón.
--   2) Trigger report_foto_validar (before insert / update of foto_url): la carpeta <uuid> debe ser
--      el autor del reporte (la política de storage ya obliga a subir solo dentro de la carpeta del
--      propio uid) y el archivo debe existir de verdad en storage.objects (bucket reportes).
--      La función vive en el esquema privado (no la expone el Data API) y es security definer
--      para poder leer storage.objects.
--
-- Las fotos que ya estuvieran guardadas con otra URL no son fotos del bucket (son exactamente el
-- caso que se cierra) y se anulan antes de poner el CHECK; el reporte se conserva.

update public.report
   set foto_url = null
 where foto_url is not null
   and foto_url !~ '^https://clrnommkjyksnyrtnisf\.supabase\.co/storage/v1/object/public/reportes/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[A-Za-z0-9_-]{1,80}\.(jpg|jpeg|png|webp)$';

alter table public.report drop constraint if exists report_foto_url_check;
alter table public.report add constraint report_foto_url_check check (
  foto_url ~ '^https://clrnommkjyksnyrtnisf\.supabase\.co/storage/v1/object/public/reportes/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[A-Za-z0-9_-]{1,80}\.(jpg|jpeg|png|webp)$'
);

create or replace function privado.report_foto_validar()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  ruta text;   -- <uuid>/<archivo> dentro del bucket
begin
  if new.foto_url is null then
    return new;
  end if;
  if tg_op = 'UPDATE' and new.foto_url is not distinct from old.foto_url then
    return new;
  end if;
  ruta := substring(new.foto_url from '/storage/v1/object/public/reportes/(.+)$');
  if ruta is null or split_part(ruta, '/', 1) <> new.autor::text then
    raise exception 'La foto debe estar en la carpeta del autor del reporte.'
      using errcode = 'check_violation';
  end if;
  if not exists (select 1 from storage.objects o where o.bucket_id = 'reportes' and o.name = ruta) then
    raise exception 'La foto no existe en el bucket reportes.'
      using errcode = 'check_violation';
  end if;
  return new;
end $$;
revoke all on function privado.report_foto_validar() from public, anon, authenticated;

drop trigger if exists report_foto_validar on public.report;
create trigger report_foto_validar before insert or update of foto_url on public.report
  for each row execute function privado.report_foto_validar();
