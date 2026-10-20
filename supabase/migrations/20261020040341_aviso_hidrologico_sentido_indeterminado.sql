-- Sentido de los avisos hidrológicos de SENAMHI: 'crecida' | 'descenso' | 'indeterminado'.
--
-- Hasta hoy el sentido salía solo del título ('descenso' si decía DESCENSO; si no, 'crecida'), y
-- los avisos "SITUACIÓN ACTUAL DEL NIVEL DEL RÍO ..." de la selva (Amazonas, Marañón, Huallaga,
-- Napo, Ucayali, Nanay) quedaban como crecida cuando son de vaciante: el 19-10-2026 los 8 vigentes
-- del país se mostraban como "río en alerta o emergencia" y pintaban 6 ríos de naranja en plena
-- vaciante. El título de esos avisos no dice si el río sube o baja; sí lo dice la leyenda del nivel
-- rojo de su detalle ("mayor descenso en el nivel del río ... encallamiento de naves" en una
-- vaciante; "Se espera desborde del río. Probable inundación" en una crecida).
--
-- Regla (la misma que backend/connectors/senamhi_avisos_hidro.py sentido_del_titulo /
-- sentido_del_detalle y backend/ingesta/rios.py _sentido):
--   1. título con DESCENSO -> 'descenso'; con INCREMENTO o CRECIDA -> 'crecida';
--   2. si no, la leyenda del nivel rojo (significado_rojo): descenso/encallamiento/estiaje/vaciante
--      -> 'descenso'; desborde/inundación -> 'crecida' (si dice las dos o ninguna, nada);
--   3. si no, 'indeterminado': el frontend (lib/zonaRio.js, lib/cauces.js) y titular.py solo
--      encienden un río con sentido 'crecida', así que un aviso sin sentido conocido no pinta nada.
-- La función aviso_hidrologico_sentido aplica la regla y el trigger la impone en cada escritura:
-- la BD nunca guarda 'crecida' sin esa evidencia, ni siquiera si la escribe un worker con código
-- viejo (el upsert hourly de la lista no puede devolver a 'crecida' un aviso que el detalle fijó
-- como vaciante). La tarea 'rios' ahora lee el detalle de TODOS los avisos vigentes del país.

alter table public.aviso_hidrologico drop constraint aviso_hidrologico_sentido_check;
alter table public.aviso_hidrologico add constraint aviso_hidrologico_sentido_check
  check (sentido in ('crecida', 'descenso', 'indeterminado'));
comment on column public.aviso_hidrologico.sentido is
  'crecida | descenso (vaciante) | indeterminado. Lo fija aviso_hidrologico_sentido(titulo, significado_rojo): el título '
  'si dice INCREMENTO/CRECIDA o DESCENSO; si no, la leyenda del nivel rojo del detalle; si no, indeterminado. '
  'Solo crecida enciende la zona o el cauce de un río.';

create or replace function public.aviso_hidrologico_sentido(titulo text, significado_rojo text)
returns text
language sql
immutable
set search_path = ''
as $$
  select case
    when upper(coalesce(titulo, '')) like '%DESCENSO%' then 'descenso'
    when upper(coalesce(titulo, '')) like '%INCREMENTO%' or upper(coalesce(titulo, '')) like '%CRECIDA%' then 'crecida'
    when coalesce(significado_rojo, '') ~* '(descenso|encallamiento|estiaje|vaciante)'
     and coalesce(significado_rojo, '') !~* '(desbord|inundaci)' then 'descenso'
    when coalesce(significado_rojo, '') ~* '(desbord|inundaci)'
     and coalesce(significado_rojo, '') !~* '(descenso|encallamiento|estiaje|vaciante)' then 'crecida'
    else 'indeterminado'
  end
$$;
comment on function public.aviso_hidrologico_sentido(text, text) is
  'Sentido de un aviso hidrológico de SENAMHI por su título y, si este no lo dice, por la leyenda del nivel rojo de su detalle.';

create or replace function public.aviso_hidrologico_fijar_sentido()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.sentido := public.aviso_hidrologico_sentido(new.titulo, new.significado_rojo);
  return new;
end
$$;

drop trigger if exists aviso_hidrologico_sentido on public.aviso_hidrologico;
create trigger aviso_hidrologico_sentido
  before insert or update of titulo, significado_rojo, sentido on public.aviso_hidrologico
  for each row execute function public.aviso_hidrologico_fijar_sentido();

-- Reclasificación de lo guardado con la regla vieja (el 19-10-2026: 1665 'crecida', de los cuales
-- 679 son "SITUACIÓN ACTUAL ..." sin detalle -> 'indeterminado'; ninguno tenía significado_rojo).
update public.aviso_hidrologico
   set sentido = public.aviso_hidrologico_sentido(titulo, significado_rojo)
 where sentido is distinct from public.aviso_hidrologico_sentido(titulo, significado_rojo);
