-- Cambio de nombre del producto: SIMPAC pasa a llamarse SIFEC (25-11-2026).
-- Solo textos ya guardados y comentarios de objetos; no cambia ninguna estructura ni dato
-- numérico. Idempotente: cada UPDATE toca solo las filas que todavía dicen SIMPAC y los
-- COMMENT ON se pueden repetir. Los nombres de tablas, vistas, funciones y migraciones
-- anteriores (init_simpac_schema) se conservan a propósito: son identificadores técnicos
-- que nadie ve. Sí se toca titular_zona: la tarea 'titular' del worker solo vuelve a redactar
-- el titular de un departamento cuando cambian sus insumos (huella); si no cambian, refresca
-- titular_corto, detalle e insumos y deja titular intacto (backend/ingesta/titular.py,
-- SQL_SIN_CAMBIO), así que un departamento sin novedades (hoy el Callao) seguiría diciendo
-- SIMPAC durante días o semanas. Solo latido se deja: el worker lo reescribe entero en cada
-- corrida (y su única mención es el nombre de la variable SIMPAC_LLM_KEY, que se conserva).
-- Al 25-11-2026 cambia 13 filas de rio_zona, 40 de rio_cauce_zona, 1 de rio_vigilado y 1 de
-- titular_zona (Callao).

-- Zonas del río vigilado (cargadas desde backend/data/rios/mashcon/): fuente de las zonas
-- estimadas con el relieve, texto y atribución de las digitalizadas de INDECI-PNUD 2005 y
-- método de las fajas marginales de ANA.
update rio_zona
   set fuente     = replace(fuente, 'SIMPAC', 'SIFEC'),
       texto      = replace(texto, 'SIMPAC', 'SIFEC'),
       atribucion = replace(atribucion, 'SIMPAC', 'SIFEC'),
       metodo     = replace(metodo, 'SIMPAC', 'SIFEC')
 where fuente like '%SIMPAC%' or texto like '%SIMPAC%' or atribucion like '%SIMPAC%' or metodo like '%SIMPAC%';

-- Zonas estimadas con el relieve junto a los ríos del país (backend/data/cauces_zonas/*.geojson,
-- campo "fuente": "Estimación SIFEC: altura sobre el cauce (HAND) ...").
update rio_cauce_zona
   set fuente = replace(fuente, 'SIMPAC', 'SIFEC')
 where fuente like '%SIMPAC%';

-- Fuentes del río vigilado (rio.json: la cuenca es "Estimación SIFEC (Copernicus GLO-30)").
update rio_vigilado
   set fuentes = replace(fuentes::text, 'SIMPAC', 'SIFEC')::jsonb
 where fuentes::text like '%SIMPAC%';

-- Titular por departamento (tarea 'titular' del worker; se ve en /api/snapshot y en la tarjeta
-- "Tu zona ahora"). replace() sobre null devuelve null (titular_corto y detalle pueden faltar)
-- y el texto se acorta, así que los CHECK de 240 y 110 caracteres se siguen cumpliendo.
-- generado_en e insumos no se tocan: es el mismo titular con el nombre nuevo.
update titular_zona
   set titular       = replace(titular, 'SIMPAC', 'SIFEC'),
       titular_corto = replace(titular_corto, 'SIMPAC', 'SIFEC'),
       detalle       = replace(detalle, 'SIMPAC', 'SIFEC')
 where titular like '%SIMPAC%' or titular_corto like '%SIMPAC%' or detalle like '%SIMPAC%';

-- Comentarios de objetos que nombraban al producto (mismo texto que supabase/schema.sql).
comment on column icen_serie.categoria is
  'ENFEN: la oficial de la tabla de su informe. IGP: calculada por SIFEC con los cortes de la Nota Técnica ENFEN 01-2024 (en los meses fríos solo dice Fría).';
comment on table rio_zona is
  'Zonas que un río vigilado podría afectar. tipo: estimada (relieve, SIFEC) | estudio (INDECI-PNUD 2005 digitalizado) | faja (faja marginal ANA). Ninguna es un mapa oficial de inundación vigente.';
