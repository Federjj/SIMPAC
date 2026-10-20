-- Titular interpretado por departamento (HU-16): una frase en lenguaje claro, de 240 caracteres
-- como mucho, que resume lo que dicen HOY las fuentes oficiales (avisos de SENAMHI, ríos de ANA,
-- lluvia medida, río vigilado y estado ENFEN) para cada uno de los 24 departamentos y el Callao.
-- La escribe la tarea 'titular' del worker (backend/ingesta/titular.py) cada 30 min: con clave de
-- API la redacta un modelo de lenguaje a partir de cifras y niveles YA calculados (el modelo no
-- decide el nivel ni calcula nada; su texto se valida antes de guardarse); sin clave, o si el
-- modelo falla o su texto no pasa la validación, la arman reglas fijas en Python (origen 'reglas').
-- El nivel es el mismo semáforo del frontend (lib/nivel.js): 'sin_dato' cuando SIMPAC no tiene
-- nada que revisar en el departamento (nunca "normal" por lo que no se midió).
create table public.titular_zona (
  departamento text primary key,                 -- canónico (backend/ingesta/departamentos.py), incluye 'Callao'
  titular      text not null check (char_length(titular) <= 240),
  detalle      text,                             -- el resumen largo: qué hay, cuántas, el río vigilado,
                                                 -- la lluvia medida y las fuentes con su hora
  nivel        text not null check (nivel in ('normal', 'aviso', 'alerta', 'emergencia', 'sin_dato')),
  generado_en  timestamptz not null default now(),   -- cuándo se escribió ESTE titular
  revisado_en  timestamptz not null default now(),   -- última corrida que confirmó que sus insumos siguen iguales
  modelo       text,                             -- id del modelo (origen 'llm'); null con reglas
  origen       text not null check (origen in ('llm', 'reglas')),
  insumos      jsonb not null default '{}'::jsonb check (jsonb_typeof(insumos) = 'object')
                                                 -- las cifras y niveles que recibió el redactor, con la
                                                 -- hora de cada fuente y la huella (hash) que decide si
                                                 -- hay que volver a redactar
);
comment on table public.titular_zona is
  'Titular en lenguaje claro por departamento, generado por el worker (tarea titular) a partir de los datos oficiales; '
  'origen llm = lo redactó un modelo de lenguaje con las cifras fijadas y validado; reglas = respaldo determinista.';

-- Lectura pública (es un resumen de datos públicos); escribe solo el worker (rol postgres).
alter table public.titular_zona enable row level security;
revoke all on public.titular_zona from anon, authenticated;
grant select on public.titular_zona to anon, authenticated;
create policy "lectura publica titular" on public.titular_zona for select using (true);
