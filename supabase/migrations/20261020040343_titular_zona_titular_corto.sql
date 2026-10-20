-- titular_zona.titular_corto: la versión de 110 caracteres como mucho del titular interpretado.
--
-- La tarjeta "Tu zona ahora" del inicio (frontend/src/hooks/useZonaAhora.js, TITULAR_MAX = 110) solo
-- puede mostrar dos líneas, y el titular de 240 caracteres (frase principal + río vigilado + El Niño)
-- nunca cabía: tras la corrida del 20-10-2026 03:25 UTC los 25 titulares medían entre 119 y 234, así
-- que el trabajo de la tarea no llegaba al vistazo (solo a la altura completa). Contrato único:
--   titular        hasta 240 caracteres (modelo o reglas): la frase completa, con El Niño
--   titular_corto  hasta 110 caracteres, SIEMPRE por reglas (backend/ingesta/titular.py titular_corto):
--                  solo la frase principal (qué hay vigente y de quién: SENAMHI, ANA), sin El Niño,
--                  sin el río vigilado ni las fuentes; con alertas, lo más grave primero y, si no cabe,
--                  se quitan las partes de menor nivel desde el final; sin alertas dice qué se revisó;
--                  sin nada que revisar lo dice (nunca "normal" por lo no medido)
--   detalle        el resumen largo con la lluvia medida y las fuentes con su hora
-- El frontend lee titular_corto para la tarjeta (y sigue sin depender de él para el semáforo ni la
-- instrucción) y titular/detalle para "Qué dicen las fuentes hoy". La tarea lo escribe en cada
-- corrida (también cuando los insumos no cambiaron: SQL_SIN_CAMBIO), así las filas anteriores a
-- esta columna lo reciben en la primera vuelta; hasta entonces es null y la tarjeta usa su frase
-- determinista (lib/zonaAhora.js titularCorto).

alter table public.titular_zona
  add column if not exists titular_corto text check (char_length(titular_corto) <= 110);
comment on column public.titular_zona.titular_corto is
  'Frase principal del titular en 110 caracteres como mucho, siempre por reglas (titular.py titular_corto), para la '
  'tarjeta "Tu zona ahora"; null hasta la primera corrida de la tarea tras esta migración.';
comment on table public.titular_zona is
  'Titular en lenguaje claro por departamento, generado por el worker (tarea titular) a partir de los datos oficiales; '
  'origen llm = lo redactó un modelo de lenguaje con las cifras fijadas y validado; reglas = respaldo determinista. '
  'titular_corto (<= 110) es la frase principal por reglas para la tarjeta de inicio.';
