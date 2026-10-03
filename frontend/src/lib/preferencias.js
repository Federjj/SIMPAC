// Preferencias del mapa: qué capas dejó encendidas la persona y qué opción eligió (las usa
// hooks/useLayerVisibility.js). Puro: sin React ni Leaflet, así se prueba con `node --test` como
// lib/geo.js o lib/pronostico.js.
//
// Qué se guarda (localStorage, clave "simpac.mapa"; con sesión, también la tabla preferencia_mapa):
//   { v: 1,
//     capas:    { [id]: boolean }   solo las que la persona dejó distinto de su defaultVisible
//     opciones: { [id]: valor }     solo las distintas del defecto (evento FEN, "7 días", horizonte del nowcasting)
//     dia:      { valor, fecha }    el día de avisos y pronóstico; vale solo esa fecha de Perú
//     conocidas: [id]               capas que existían la última vez (para marcar "Nueva")
//     guardado: ISO | null }        cuándo la persona cambió algo por última vez (null: nunca). Sirve
//                                   para elegir entre el navegador y la cuenta: un celular nuevo, sin
//                                   cambios, no pisa lo que la cuenta ya tenía.
// Guardar solo las diferencias hace que una capa que la persona nunca tocó siga el defaultVisible
// del código (si el equipo cambia un defecto, le llega), y que una capa nueva arranque con el suyo.

export const CLAVE = "simpac.mapa";
export const VERSION = 1;
// ids que cambiaron de nombre: { viejo: nuevo } (se aplica al leer; p. ej. si "zona" pasara a "zonaRio")
export const RENOMBRADAS = {};

const esObjeto = (x) => x != null && typeof x === "object" && !Array.isArray(x);

// Lo que el mapa usa: { visible, opciones } completos para todas las capas actuales, más
// `nuevas` (ids que la persona aún no conoce) y `cambios` (si hay algo distinto de lo de siempre).
export function aplicar(layers, guardado, { hoy } = {}) {
  const p = normalizar(layers, guardado, { hoy });
  const visible = Object.fromEntries(layers.map((l) => [l.id, p.capas[l.id] ?? Boolean(l.defaultVisible)]));
  const opciones = Object.fromEntries(
    layers.filter((l) => l.opciones).map((l) => [l.id, p.opciones[l.id] ?? l.opciones.defecto])
  );
  if (p.dia) {
    for (const l of layers) if (l.opciones?.vinculo === "dia" && valido(l, p.dia.valor)) opciones[l.id] = p.dia.valor;
  }
  // sin nada guardado (primera visita) no hay "nuevas": todo es nuevo
  const nuevas = p.conocidas ? layers.map((l) => l.id).filter((id) => !p.conocidas.includes(id)) : [];
  const cambios = Object.keys(p.capas).length > 0 || Object.keys(p.opciones).length > 0 || Boolean(p.dia);
  return { visible, opciones, nuevas, cambios };
}

const valido = (layer, valor) => Boolean(layer?.opciones?.valores?.some((v) => v.valor === valor));

// Limpia lo leído: versión, ids que ya no existen, tipos raros, día vencido.
export function normalizar(layers, crudo, { hoy } = {}) {
  const vacio = { capas: {}, opciones: {}, dia: null, conocidas: null };
  if (!esObjeto(crudo)) return vacio;
  const datos = migrar(crudo);
  if (!datos) return vacio;
  const porId = new Map(layers.map((l) => [l.id, l]));
  const capas = {};
  for (const [id0, on] of Object.entries(esObjeto(datos.capas) ? datos.capas : {})) {
    const id = RENOMBRADAS[id0] ?? id0;
    const l = porId.get(id);
    if (!l || typeof on !== "boolean" || on === Boolean(l.defaultVisible)) continue;
    capas[id] = on;
  }
  const opciones = {};
  for (const [id0, valor] of Object.entries(esObjeto(datos.opciones) ? datos.opciones : {})) {
    const id = RENOMBRADAS[id0] ?? id0;
    const l = porId.get(id);
    if (!l?.opciones || l.opciones.vinculo === "dia" || !valido(l, valor) || valor === l.opciones.defecto) continue;
    opciones[id] = valor;
  }
  // el día solo vale la misma fecha (en Perú): mañana, "Mañana" ya no quiere decir lo mismo
  const d = datos.dia;
  const dia = esObjeto(d) && hoy && d.fecha === hoy && typeof d.valor === "string" && d.valor !== "ahora" ? { valor: d.valor, fecha: d.fecha } : null;
  const conocidas = Array.isArray(datos.conocidas)
    ? datos.conocidas.filter((x) => typeof x === "string").map((x) => RENOMBRADAS[x] ?? x)
    : null;
  return { capas, opciones, dia, conocidas };
}

// Versiones viejas -> la actual; null si no se reconoce (se descarta y se usan los defectos).
function migrar(datos) {
  if (datos.v === VERSION) return datos;
  // if (datos.v === 1) return { ...datos, v: 2, ... };  (cuando haya v2)
  return null;
}

// Lo que se escribe a partir del estado completo del mapa.
export function serializar(layers, { visible, opciones }, { hoy, conocidas, guardado = null } = {}) {
  const capas = {};
  for (const l of layers) if (Boolean(visible[l.id]) !== Boolean(l.defaultVisible)) capas[l.id] = Boolean(visible[l.id]);
  const ops = {};
  let dia = null;
  for (const l of layers) {
    if (!l.opciones) continue;
    const v = opciones[l.id];
    if (v == null || v === l.opciones.defecto || !valido(l, v)) continue;
    if (l.opciones.vinculo === "dia") dia = { valor: v, fecha: hoy };
    else ops[l.id] = v;
  }
  return {
    v: VERSION,
    capas,
    opciones: ops,
    ...(dia && hoy ? { dia } : {}),
    conocidas: conocidas ?? layers.map((l) => l.id),
    guardado,
  };
}

// localStorage puede no existir o lanzar (ventana privada, datos bloqueados, cuota): nunca rompe el mapa.
// Con los datos del sitio bloqueados lanza ya al leer window.localStorage: por eso se lee dentro del
// try y no como valor por defecto del parámetro.
const almacenDe = (almacen) => (almacen === undefined ? globalThis.localStorage : almacen);

export function leerLocal(almacen) {
  try {
    const t = almacenDe(almacen)?.getItem(CLAVE);
    return t ? JSON.parse(t) : null;
  } catch {
    return null;
  }
}

// true si quedó guardado
export function guardarLocal(datos, almacen) {
  try {
    const a = almacenDe(almacen);
    if (!a) return false;
    a.setItem(CLAVE, JSON.stringify(datos));
    return true;
  } catch {
    return false;
  }
}

export function borrarLocal(almacen) {
  try {
    almacenDe(almacen)?.removeItem(CLAVE);
  } catch {
    /* nada que hacer */
  }
}

// Con sesión: gana la copia guardada más tarde (la del navegador o la de la cuenta).
export function masReciente(local, cuenta) {
  const t = (x) => (x && Date.parse(x.guardado)) || 0;
  if (!local) return cuenta ?? null;
  if (!cuenta) return local;
  return t(cuenta) >= t(local) ? cuenta : local;
}
