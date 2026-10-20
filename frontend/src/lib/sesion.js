// Sesión con Supabase Auth (correo y contraseña) y lo que solo existe con sesión: el perfil
// propio, "mi zona" y "mis reportes". Las funciones devuelven { ok, error } con el error ya en
// lenguaje claro (lib/comunidad.js mensajeAuth / mensajeErrorBD); nunca lanzan.
// Nunca se piden ni guardan más datos personales que el correo y el nombre para mostrar.
import { supabase } from "./supabaseClient";
import { ewkt, mensajeAuth, mensajeErrorBD, puntoDeWkb } from "./comunidad";
import { CITIES, nearestCity } from "@/data/cities";

// A dónde vuelve la persona desde el correo de confirmación o de recuperación.
const volverA = () => `${window.location.origin}/cuenta`;

export async function entrar({ email, password }) {
  const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
  return error ? { ok: false, error: mensajeAuth(error) } : { ok: true };
}

// Registro: la BD crea el perfil con el nombre (trigger crear_perfil, options.data.nombre). Como la
// confirmación por correo está activa, no hay sesión hasta confirmar: se devuelve `confirmar`.
// Si el correo ya existía, Supabase responde con un usuario sin identidades (no revela cuentas):
// se avisa igual que "revisa tu correo" pero con la pista de entrar.
export async function registrar({ email, password, nombre }) {
  const { data, error } = await supabase.auth.signUp({
    email: email.trim(),
    password,
    options: { data: { nombre: nombre.trim() }, emailRedirectTo: volverA() },
  });
  if (error) return { ok: false, error: mensajeAuth(error) };
  const yaExistia = Array.isArray(data.user?.identities) && data.user.identities.length === 0;
  return { ok: true, confirmar: !data.session, yaExistia };
}

export async function salir() {
  const { error } = await supabase.auth.signOut();
  return error ? { ok: false, error: mensajeAuth(error) } : { ok: true };
}

// Correo para cambiar la contraseña: el enlace vuelve a /cuenta con el evento PASSWORD_RECOVERY.
export async function pedirNuevaContrasena(email) {
  const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo: volverA() });
  return error ? { ok: false, error: mensajeAuth(error) } : { ok: true };
}

export async function cambiarContrasena(password) {
  const { error } = await supabase.auth.updateUser({ password });
  return error ? { ok: false, error: mensajeAuth(error) } : { ok: true };
}

// Perfil propio: nombre, reputación y la zona guardada (un punto: se traduce a la ciudad más
// cercana de data/cities.js). null si aún no existe (el trigger lo crea al registrarse).
export async function leerPerfil() {
  const { data, error } = await supabase.from("perfil").select("id,nombre,reputacion,zona").maybeSingle();
  if (error) return { ok: false, error: mensajeErrorBD(error, "leer tu perfil") };
  if (!data) return { ok: true, perfil: null };
  const punto = puntoDeWkb(data.zona);
  const ciudad = punto ? nearestCity(punto.lat, punto.lon) : null;
  return { ok: true, perfil: { id: data.id, nombre: data.nombre, reputacion: data.reputacion ?? 0, ciudad: ciudad?.name ?? null } };
}

// "Mi zona": el punto de la ciudad elegida en perfil.zona (geometry Point; solo lo ve su dueño).
export async function guardarZona(nombreCiudad) {
  const c = CITIES.find((x) => x.name === nombreCiudad);
  if (!c) return { ok: false, error: "Esa ciudad no está en la lista." };
  const { error } = await supabase.from("perfil").update({ zona: ewkt(c.lat, c.lon) }).eq("id", (await supabase.auth.getUser()).data.user?.id);
  return error ? { ok: false, error: mensajeErrorBD(error, "guardar tu zona") } : { ok: true };
}

export async function guardarNombre(nombre) {
  const n = (nombre ?? "").trim();
  if (n.length < 2 || n.length > 80) return { ok: false, error: "El nombre tiene que tener entre 2 y 80 letras." };
  const { error } = await supabase.from("perfil").update({ nombre: n }).eq("id", (await supabase.auth.getUser()).data.user?.id);
  return error ? { ok: false, error: mensajeErrorBD(error, "guardar tu nombre") } : { ok: true };
}

// Mis reportes (vigentes y vencidos): la única forma de verlos, porque `autor` no es legible.
export async function misReportes() {
  const { data, error } = await supabase.rpc("mis_reportes");
  if (error) return { ok: false, error: mensajeErrorBD(error, "leer tus reportes") };
  return { ok: true, reportes: data ?? [] };
}

// Ciudad por defecto recordada en este navegador (también sin sesión): clave simpac.zona.
export const CLAVE_ZONA = "simpac.zona";
export function leerZonaLocal() {
  try {
    const v = localStorage.getItem(CLAVE_ZONA);
    return v && CITIES.some((c) => c.name === v) ? v : null;
  } catch {
    return null;
  }
}
export function guardarZonaLocal(nombre) {
  try {
    if (nombre) localStorage.setItem(CLAVE_ZONA, nombre);
    else localStorage.removeItem(CLAVE_ZONA);
  } catch {
    /* sin almacenamiento: nada que hacer */
  }
}
