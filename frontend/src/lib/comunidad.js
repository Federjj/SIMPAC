// Lógica pura de la comunidad (reportes, votos, comentarios y chat): orden de los reportes por
// confianza y cercanía, textos de distancia y de vencimiento, validaciones del formulario, el
// filtro local de groserías del chat y los errores de la BD y de Auth en lenguaje claro. Sin
// React ni Supabase, así se prueba con `node --test` (comunidad.test.js). Lo que habla con la
// BD vive en lib/queries.js y lib/sesion.js.
import { haversineKm } from "./geo.js";
import { textoHace } from "./tiempo.js";
import { REPORT_TYPE } from "./reportTypes.js";

export const MAX_DESCRIPCION = 500;
export const MAX_MENSAJE = 500;
export const MAX_FOTO_BYTES = 3 * 1024 * 1024;
export const LADO_FOTO = 1280;

// Texto fijo que va al pie de Alertas, Comunidad y Chat (brief, reglas transversales).
export const DISCLAIMER =
  "Información referencial y comunitaria; no reemplaza los canales oficiales de emergencia (105 / 116).";
export const AVISO_REPORTE = "Es un reporte comunitario, no oficial. Para emergencias llama al 105 o 116.";
export const NORMAS_CHAT = "Mensajes efímeros de 2 horas. Sin insultos. Reporta lo que ves, no rumores.";
export const POR_QUE_CUENTA = "Para consultar no hace falta cuenta. Solo se pide para reportar, votar, comentar y chatear.";

// ---------------------------------------------------------------------------
// Reportes
// ---------------------------------------------------------------------------

// Distancia en km desde `pos` ({lat, lon}) a un reporte; null si falta algo.
export function distanciaKm(r, pos) {
  if (!pos || pos.lat == null || pos.lon == null || r?.lat == null || r?.lon == null) return null;
  return haversineKm(pos.lat, pos.lon, r.lat, r.lon);
}

// "a 350 m", "a 1,2 km", "a 15 km"
export function textoDistancia(km) {
  if (km == null || !Number.isFinite(km)) return null;
  if (km < 1) return `a ${Math.max(10, Math.round(km * 100) * 10)} m`;
  if (km < 10) return `a ${km.toLocaleString("es-PE", { maximumFractionDigits: 1 })} km`;
  return `a ${Math.round(km)} km`;
}

// Puntaje de un reporte: su confianza (la calcula la BD con los votos, 0 a 1) menos un castigo por
// lejanía (50 km restan tanto como pasar de 1 a 0 de confianza; a más de 100 km no se castiga más).
// Sin posición, solo cuenta la confianza. Criterio SIMPAC para ordenar la lista, nada más.
export function puntajeReporte(r, km) {
  const confianza = Number.isFinite(r?.confianza) ? r.confianza : 0.5;
  const lejania = km == null ? 0 : Math.min(km, 100) / 50;
  return confianza - lejania;
}

// Reportes ordenados: mejor puntaje primero; empate, el más nuevo primero. Cada uno sale con
// `distanciaKm` (null si no hay posición) y `puntaje`.
export function ordenarReportes(reportes = [], pos = null) {
  return reportes
    .map((r) => {
      const km = distanciaKm(r, pos);
      return { ...r, distanciaKm: km, puntaje: puntajeReporte(r, km) };
    })
    .sort((a, b) => b.puntaje - a.puntaje || Date.parse(b.creado_en ?? 0) - Date.parse(a.creado_en ?? 0));
}

// "hace 8 min", "hace 2 h 15 min" (lib/tiempo.js textoHace) a partir de una fecha ISO.
export function hace(iso, ahora = Date.now()) {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? textoHace(ahora - t) : "";
}

// "vence en 45 min", "vence en 1 h 20 min", "vence en 2 días" o "vencido".
export function venceEn(expiraEn, ahora = Date.now()) {
  const t = Date.parse(expiraEn);
  if (!Number.isFinite(t)) return "";
  const min = Math.floor((t - ahora) / 60_000);
  if (min <= 0) return "vencido";
  if (min < 60) return `vence en ${min} min`;
  const h = Math.floor(min / 60);
  if (h >= 48) return `vence en ${Math.floor(h / 24)} días`;
  return min % 60 ? `vence en ${h} h ${min % 60} min` : `vence en ${h} h`;
}

export const vigente = (r, ahora = Date.now()) => Date.parse(r?.expira_en ?? 0) > ahora;

// Nombre del tipo con su subtipo: "Atasco detenido", "Inundación".
export function nombreReporte(r) {
  const tipo = REPORT_TYPE[r?.tipo] ?? REPORT_TYPE.otro;
  const sub = tipo.subtipos?.find((s) => s.id === r?.subtipo)?.label;
  return sub ? `${tipo.label} ${sub.toLowerCase()}` : tipo.label;
}

export const ESTADO_REPORTE = {
  sin_confirmar: "Sin confirmar",
  confirmado: "Confirmado por la comunidad",
  descartado: "Descartado por la comunidad",
};

// Validación del formulario de un reporte nuevo. `pos` es la posición GPS ([lat, lon] o {lat, lon}).
// Devuelve { ok, errores: { campo: mensaje } } con mensajes listos para mostrar.
export function validarReporte({ tipo, subtipo, descripcion, pos, foto } = {}) {
  const errores = {};
  const t = REPORT_TYPE[tipo];
  if (!t) errores.tipo = "Elige qué estás viendo.";
  if (t?.subtipos && !t.subtipos.some((s) => s.id === subtipo)) errores.subtipo = "Indica qué tan fuerte es el atasco.";
  if (t && !t.subtipos && subtipo) errores.subtipo = "Ese detalle no corresponde a este tipo de reporte.";
  const d = (descripcion ?? "").trim();
  if (d.length > MAX_DESCRIPCION) errores.descripcion = `La descripción puede tener hasta ${MAX_DESCRIPCION} letras (llevas ${d.length}).`;
  const p = Array.isArray(pos) ? { lat: pos[0], lon: pos[1] } : pos;
  if (!p || !Number.isFinite(p.lat) || !Number.isFinite(p.lon)) {
    errores.pos = "No tenemos tu ubicación. Sin ella no se puede reportar.";
  } else if (!dentroDelPeru(p.lat, p.lon)) {
    errores.pos = "Tu ubicación cae fuera del Perú: solo se reporta desde dentro del país.";
  }
  if (foto && foto.size > MAX_FOTO_BYTES) errores.foto = "La foto pesa más de 3 MB. Prueba con otra.";
  if (foto && !/^image\/(jpeg|png|webp)$/.test(foto.type ?? "")) errores.foto = "La foto tiene que ser JPG, PNG o WebP.";
  return { ok: Object.keys(errores).length === 0, errores };
}

// El mismo recuadro que el CHECK de report.geom (lon -81.5..-68.5, lat -18.5..0.1).
export const dentroDelPeru = (lat, lon) => lon >= -81.5 && lon <= -68.5 && lat >= -18.5 && lat <= 0.1;

// Punto para la BD como EWKT (ojo: primero lon, después lat).
export const ewkt = (lat, lon) => `SRID=4326;POINT(${lon} ${lat})`;

// Punto desde el EWKB en hex que devuelve el Data API para una geometry(Point, 4326)
// (p. ej. perfil.zona): "0101000020E6100000<x><y>" con los dobles en little endian. null si no
// es un punto.
export function puntoDeWkb(hex) {
  if (typeof hex !== "string" || hex.length < 42 || !/^[0-9a-fA-F]+$/.test(hex)) return null;
  const le = hex.slice(0, 2) === "01";
  const leer = (desde, n) => {
    const bytes = [];
    for (let i = 0; i < n; i++) bytes.push(parseInt(hex.slice(desde + i * 2, desde + i * 2 + 2), 16));
    return le ? bytes : bytes.reverse();
  };
  const tipo = leer(2, 4).reduce((acc, b, i) => acc + b * 256 ** i, 0);
  const conSrid = (tipo & 0x20000000) !== 0;
  if ((tipo & 0xff) !== 1) return null; // 1 = Point
  const base = conSrid ? 18 : 10;
  if (hex.length < base + 32) return null;
  const doble = (desde) => {
    const b = leer(desde, 8);
    const buf = new DataView(new ArrayBuffer(8));
    b.forEach((v, i) => buf.setUint8(i, v));
    return buf.getFloat64(0, true);
  };
  const lon = doble(base);
  const lat = doble(base + 16);
  return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null;
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

// Lista corta de groserías comunes en el Perú: solo para avisar antes de enviar (autocontrol,
// no hay moderadores). Se compara sin tildes ni mayúsculas y por palabra completa.
const GROSERIAS = [
  "mierda", "carajo", "concha", "conchatumadre", "conchasumadre", "ctm", "csm", "huevon", "huevona", "weon",
  "cojudo", "cojuda", "imbecil", "idiota", "estupido", "estupida", "pendejo", "pendeja", "maricon",
  "puta", "puto", "cabron", "cabrona", "chucha", "verga", "mrd", "ptm", "pta",
];
const normalizar = (t) => (t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// Palabras del texto que caen en la lista (sin repetir), [] si no hay.
export function groserias(texto) {
  const palabras = normalizar(texto).split(/[^a-z0-9ñ]+/).filter(Boolean);
  return [...new Set(palabras.filter((p) => GROSERIAS.includes(p)))];
}
export const tieneGroserias = (texto) => groserias(texto).length > 0;

// Validación de un mensaje del chat o de un comentario (1 a 500 letras, sin solo espacios).
export function validarTexto(texto, max = MAX_MENSAJE) {
  const t = (texto ?? "").trim();
  if (!t) return { ok: false, error: "Escribe algo antes de enviar." };
  if (t.length > max) return { ok: false, error: `Puede tener hasta ${max} letras (llevas ${t.length}).` };
  return { ok: true, texto: t };
}

// Mensajes vigentes ordenados del más viejo al más nuevo y sin los ocultos por la persona.
export function mensajesVisibles(mensajes = [], ocultos = new Set(), ahora = Date.now()) {
  return mensajes
    .filter((m) => Date.parse(m.expira_en) > ahora && !ocultos.has(m.id))
    .sort((a, b) => Date.parse(a.creado_en) - Date.parse(b.creado_en));
}

// ---------------------------------------------------------------------------
// Errores de la BD y de Auth en lenguaje claro
// ---------------------------------------------------------------------------

// Un error de Supabase (PostgREST, Storage o la red) -> frase para la persona. `que` es la acción
// ("enviar el reporte", "votar") para armar la frase genérica.
export function mensajeErrorBD(error, que = "guardar") {
  const m = `${error?.message ?? ""} ${error?.details ?? ""} ${error?.hint ?? ""}`.toLowerCase();
  const code = String(error?.code ?? "");
  if (/l[ií]mite de \d+ por hora/.test(m)) {
    const n = /l[ií]mite de (\d+)/.exec(m)?.[1];
    return `Llegaste al límite de ${n ?? "envíos"} por hora. Espera un rato antes de volver a ${que}.`;
  }
  if (m.includes("propio reporte")) return "No puedes votar tu propio reporte.";
  if (m.includes("report_geom_check") || (m.includes("geom") && m.includes("check"))) {
    return "Tu ubicación cae fuera del Perú: solo se reporta desde dentro del país.";
  }
  if (m.includes("jwt") || m.includes("expired") || code === "401" || code === "PGRST301") {
    return "Tu sesión venció. Vuelve a entrar para continuar.";
  }
  if (code === "42501" || m.includes("row-level security") || m.includes("permission denied")) {
    return "No tienes permiso para esto. Si acabas de entrar, prueba de nuevo; si no, vuelve a iniciar sesión.";
  }
  if (code === "23505") return "Eso ya estaba guardado.";
  if (m.includes("payload too large") || m.includes("exceeded the maximum allowed size") || code === "413") {
    return "La foto pesa demasiado (máximo 3 MB).";
  }
  if (m.includes("mime type") || m.includes("not supported")) return "La foto tiene que ser JPG, PNG o WebP.";
  if (m.includes("failed to fetch") || m.includes("networkerror") || m.includes("network request failed")) {
    return "No hay conexión. Revisa tu internet e inténtalo de nuevo.";
  }
  if (m.includes("vigente") || m.includes("expira")) return "Este reporte ya venció: no admite votos ni comentarios.";
  return `No se pudo ${que}. Inténtalo de nuevo en un momento.`;
}

// Un error de Supabase Auth -> frase para la persona.
export function mensajeAuth(error) {
  const m = (error?.message ?? "").toLowerCase();
  const code = error?.code ?? "";
  if (code === "invalid_credentials" || m.includes("invalid login credentials")) return "Correo o contraseña incorrectos.";
  if (code === "email_not_confirmed" || m.includes("email not confirmed")) {
    return "Tu correo aún no está confirmado. Busca el mensaje que te enviamos (revisa también la carpeta de spam).";
  }
  if (code === "user_already_exists" || m.includes("already registered") || m.includes("already been registered")) {
    return "Ya hay una cuenta con ese correo. Entra con tu contraseña o pide una nueva.";
  }
  if (code === "weak_password" || m.includes("password should be") || m.includes("at least 6")) {
    return "La contraseña tiene que tener al menos 6 caracteres.";
  }
  if (code === "over_email_send_rate_limit" || m.includes("rate limit")) {
    return "Enviamos demasiados correos en poco tiempo. Espera unos minutos y vuelve a intentar.";
  }
  if (code === "validation_failed" || m.includes("invalid email") || m.includes("unable to validate email")) {
    return "Ese correo no parece válido. Revísalo.";
  }
  if (code === "same_password") return "La contraseña nueva tiene que ser distinta de la actual.";
  if (code === "otp_expired" || m.includes("expired")) return "El enlace venció. Pide uno nuevo.";
  if (m.includes("failed to fetch") || m.includes("network")) return "No hay conexión. Revisa tu internet e inténtalo de nuevo.";
  return "No se pudo completar. Inténtalo de nuevo en un momento.";
}

// Validación de los formularios de Cuenta. Devuelve { ok, errores }.
export function validarCuenta({ email, password, nombre, conNombre = false } = {}) {
  const errores = {};
  const e = (email ?? "").trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) errores.email = "Escribe un correo válido.";
  if ((password ?? "").length < 6) errores.password = "La contraseña tiene que tener al menos 6 caracteres.";
  if (conNombre) {
    const n = (nombre ?? "").trim();
    if (n.length < 2) errores.nombre = "Escribe el nombre con el que quieres aparecer.";
    if (n.length > 80) errores.nombre = "El nombre puede tener hasta 80 letras.";
  }
  return { ok: Object.keys(errores).length === 0, errores };
}

// ---------------------------------------------------------------------------
// Foto del reporte (navegador): se reduce a 1280 px de lado y se pasa a JPEG antes de subirla.
// No es pura (usa canvas); está aquí para no repartir la lógica de la comunidad en más archivos.
// ---------------------------------------------------------------------------
export async function reducirFoto(archivo, lado = LADO_FOTO, calidad = 0.85) {
  if (typeof document === "undefined") return archivo;
  const imagen = await cargarImagen(archivo);
  const k = Math.min(1, lado / Math.max(imagen.width, imagen.height));
  const w = Math.max(1, Math.round(imagen.width * k));
  const h = Math.max(1, Math.round(imagen.height * k));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.getContext("2d").drawImage(imagen, 0, 0, w, h);
  if (typeof imagen.close === "function") imagen.close();
  const blob = await new Promise((ok) => canvas.toBlob(ok, "image/jpeg", calidad));
  if (!blob) throw new Error("No se pudo procesar la foto.");
  return new File([blob], "foto.jpg", { type: "image/jpeg" });
}

function cargarImagen(archivo) {
  if (typeof createImageBitmap === "function") {
    return createImageBitmap(archivo, { imageOrientation: "from-image" }).catch(() => cargarConImg(archivo));
  }
  return cargarConImg(archivo);
}

function cargarConImg(archivo) {
  return new Promise((ok, falla) => {
    const url = URL.createObjectURL(archivo);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      ok(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      falla(new Error("No se pudo leer la foto."));
    };
    img.src = url;
  });
}
