// Ayudantes de lib/queries.js que no tocan la red ni el cliente de Supabase (módulo puro: lo leen
// también las pruebas con node --test).
//   cached(key, fn, ttl)  una sola promesa por clave mientras dure el TTL: si el panel y dos capas
//                         piden lo mismo a la vez, sale una sola consulta; un error no se queda.
//   filas(query)          desenvuelve {data, error} de PostgREST.
//   todas(armar)          pide por páginas de 1000 (el Data API corta ahí sin avisar).
//   siExiste(fn)          null si la vista o la tabla aún no existe (migración pendiente).

// Exportada para que queries.js pueda olvidar una clave al escribir (p. ej. tras votar un reporte).
export const cache = new Map();

export function cached(key, fn, ttlMs = 60_000) {
  const hit = cache.get(key);
  if (hit && Date.now() - hit.t < ttlMs) return hit.p;
  const p = fn().catch((e) => {
    cache.delete(key); // un error no se queda cacheado
    throw e;
  });
  cache.set(key, { t: Date.now(), p });
  return p;
}

// Solo para las pruebas (y para el modo de simulación): vacía la caché.
export function olvidarCache() {
  cache.clear();
}

export async function filas(query) {
  const { data, error } = await query;
  if (error) throw error;
  return data ?? [];
}

// El Data API corta cada respuesta en 1000 filas sin avisar: las tablas que pueden
// pasar de eso se piden por páginas (con un orden fijo, para no repetir ni saltar filas).
const PAGINA = 1000;
export async function todas(armar) {
  const out = [];
  for (let desde = 0; ; desde += PAGINA) {
    const pagina = await filas(armar().range(desde, desde + PAGINA - 1));
    out.push(...pagina);
    if (pagina.length < PAGINA) return out;
  }
}

// Una vista o columna que aún no existe en la base (migración pendiente): la app sigue sin ella.
export const faltaVista = (e) => e?.code === "PGRST205" || e?.code === "42P01";
export const faltaColumna = (e) => e?.code === "42703";
// null si la vista aún no existe (la capa lo dice y el panel no muestra esa parte)
export async function siExiste(fn) {
  try {
    return await fn();
  } catch (e) {
    if (faltaVista(e)) return null;
    throw e;
  }
}
