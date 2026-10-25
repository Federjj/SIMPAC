-- rio_cauce_mapa: columnas nuevas ancho_m y franja (contrato 3 de la fase "ríos del país con zonas").
--
-- La franja es una banda a cada lado del trazo de ~50 m (geom_lejos) de ancho fijo por tamaño del río:
--   60 m  si km < 50      120 m  si km < 200      250 m  si km >= 200
-- Es una FRANJA DE ATENCIÓN REFERENCIAL: dice "este es el río que hay que vigilar y su entorno
-- inmediato", no hasta dónde llegaría el agua. No sale del relieve ni de ningún estudio (eso es
-- rio_cauce_zona, el mapa de zonas estimadas con el DEM, que no todos los ríos tienen) y NUNCA se
-- presenta como mapa de inundación: el frontend (map/layers/zonasRio.js) la dibuja solo cuando el río
-- está en alerta o emergencia (ANA o aviso hidrológico de SENAMHI), con contorno punteado y relleno
-- muy suave, y la leyenda la rotula "Franja de atención junto al río (referencial, no es un mapa de
-- inundación)". Un río sin trazo no tiene franja (no hay fila: queda el círculo de la estación).
--
-- Se calcula al vuelo (ST_Buffer en geografía, simplificado a ~6 m, 5 decimales): PostgREST solo
-- evalúa las columnas que se piden, y el frontend la pide por río (.eq('rio_ana', ...)) únicamente
-- para los que están en alerta o emergencia (medido el 20-10-2026: 4 ríos, Marañón incluido, en
-- ~140 ms; el Marañón pesa 158 KB, el Rímac 11 KB). Las demás columnas no cambian (create or replace
-- solo agrega al final).

create or replace view public.rio_cauce_mapa with (security_invoker = true) as
select c.rio_ana, c.rio, c.nombre, c.departamento, c.estaciones, c.estaciones_senamhi, c.capa, c.nombre_capa,
       c.km, c.dist_estacion_m, c.nota, c.fuente, c.fuente_url, c.licencia, c.atribucion, c.fecha_fuente, c.ts_carga,
       exists (select 1 from public.rio_vigilado v
                where v.rio_ana = c.rio or v.estacion_ana = any (c.estaciones)) as vigilado,
       st_asgeojson(c.geom_lejos, 5)::json as cauce_lejos,
       st_asgeojson(c.geom, 5)::json as cauce,
       a.ancho_m,
       st_asgeojson(st_simplifypreservetopology(st_buffer(c.geom_lejos::geography, a.ancho_m)::geometry, 0.00005), 5)::json as franja
from public.rio_cauce c
cross join lateral (select (case when c.km < 50 then 60 when c.km < 200 then 120 else 250 end)::int as ancho_m) a;

revoke all on public.rio_cauce_mapa from anon, authenticated;
grant select on public.rio_cauce_mapa to anon, authenticated;

comment on view public.rio_cauce_mapa is
  'Trazo de los ríos del país en GeoJSON (cauce_lejos ~50 m, cauce ~6 m) y la franja de atención referencial '
  '(franja: banda de ancho_m a cada lado del trazo: 60 m si km < 50, 120 m si km < 200, 250 m si km >= 200). '
  'La franja no es un mapa de inundación ni sale del relieve: el frontend la muestra solo con el río en alerta o emergencia.';
