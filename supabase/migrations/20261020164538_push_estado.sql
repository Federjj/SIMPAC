-- Avisador push (HU-20): memoria de lo último que se notificó por Firebase Cloud Messaging (FCM)
-- por departamento, para no repetir nunca el mismo mensaje.
--
-- La tarea 'push' del worker (backend/ingesta/push.py, cada 5 min) lee titular_zona y manda una
-- notificación a los temas 'pais' y 'zona_<slug>' SOLO cuando el nivel de una zona sube a alerta o
-- emergencia (o pasa de alerta a emergencia) y una de "vuelve la calma" cuando baja de alerta o
-- emergencia a normal o aviso. Nunca por aviso ni por lluvia medida. Para saber si el nivel SUBIÓ
-- necesita recordar el último nivel que notificó: eso es esta tabla (una fila por departamento).
--   nivel        último nivel conocido por el avisador (el de titular_zona cuando se revisó); los
--                cambios por debajo de alerta se anotan sin enviar nada (línea base)
--   titular      el cuerpo del último mensaje enviado (titular_zona.titular_corto en ese momento)
--   enviado_en   cuándo se envió el último mensaje a esa zona (null: nunca se envió nada)
--   mensaje_id   el nombre que devuelve FCM (projects/<proyecto>/messages/<id>), para rastrear en Firebase
--   actualizado_en  última corrida que tocó la fila (con o sin envío)
-- Si la fuente cae (nivel 'sin_dato' en titular_zona) la fila no se toca: no es calma, es falta de dato.
-- Sin credenciales de Firebase la tarea no escribe aquí (así, al activar las credenciales, las
-- alertas vigentes se notifican una vez).
create table public.push_estado (
  zona           text primary key,              -- departamento canónico (backend/ingesta/departamentos.py), incluye 'Callao'
  nivel          text not null check (nivel in ('normal', 'aviso', 'alerta', 'emergencia', 'sin_dato')),
  titular        text,
  enviado_en     timestamptz,
  mensaje_id     text,
  actualizado_en timestamptz not null default now()
);
comment on table public.push_estado is
  'Memoria del avisador push (tarea push del worker): último nivel notificado por departamento y el último mensaje '
  'enviado por FCM, para no repetir mensajes. Solo la escribe y lee el worker; no es un dato público.';

-- Sin lectura pública: no es un dato oficial ni un resumen para mostrar, es estado interno del worker
-- (rol postgres, que no pasa por RLS). Ninguna política: anon y authenticated no ven ni tocan nada.
alter table public.push_estado enable row level security;
revoke all on public.push_estado from anon, authenticated;
