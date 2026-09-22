import { supabase } from "./supabaseClient";

// Todas las lecturas usan la publishable key (lectura pública por RLS).
// Las que piden varias partes de la app a la vez (el panel y dos capas del mapa
// leen los caudales) pasan por cached(): una sola request cada TTL.

const cache = new Map();

function cached(key, fn, ttlMs = 60_000) {
  const hit = cache.get(key);
  if (hit && Date.now() - hit.t < ttlMs) return hit.p;
  const p = fn().catch((e) => {
    cache.delete(key); // un error no se queda cacheado
    throw e;
  });
  cache.set(key, { t: Date.now(), p });
  return p;
}

async function filas(query) {
  const { data, error } = await query;
  if (error) throw error;
  return data ?? [];
}

// El Data API corta cada respuesta en 1000 filas sin avisar: las tablas que pueden
// pasar de eso se piden por páginas (con un orden fijo, para no repetir ni saltar filas).
const PAGINA = 1000;
async function todas(armar) {
  const out = [];
  for (let desde = 0; ; desde += PAGINA) {
    const pagina = await filas(armar().range(desde, desde + PAGINA - 1));
    out.push(...pagina);
    if (pagina.length < PAGINA) return out;
  }
}

export function getEstaciones() {
  return cached("estaciones", () =>
    todas(() =>
      supabase.from("estacion").select("cod,nombre,tipo,estado,departamento,lat,lon").order("cod")
    ),
    10 * 60_000
  );
}

// Última lectura de cada estación, de ayer u hoy (vista caudal_actual; lectura_caudal
// es el historial).
export function getCaudales() {
  return cached("caudales", () =>
    filas(
      supabase
        .from("caudal_actual")
        .select("estacion,rio,departamento,fecha,hora,valor,unidad,tendencia,estado,lat,lon")
    )
  );
}

// ts_captura se renueva en cada corrida de la ingesta: sirve para saber si los datos
// están al día.
export function getIndices() {
  return cached("indices", () =>
    filas(supabase.from("indice").select("fuente,periodo,valor,categoria,ts_captura"))
  );
}

// Alertas que calcula la ingesta (lluvia y caudal), con su departamento en `zona`.
export function getAlertasVigentes() {
  return cached("alertas", () =>
    filas(
      supabase
        .from("alerta")
        .select("tipo,referencia,zona,nivel,detalle,valor,umbral,ts")
        .eq("vigente", true)
        .order("ts", { ascending: false })
    )
  );
}

// Reportes ciudadanos vigentes (los más recientes primero). El filtro de vencidos lo
// hace la BD (RLS), no el reloj del celular. Columnas explícitas: `autor` no es legible.
export function getReportesVigentes() {
  return cached("reportes", () =>
    filas(
      supabase
        .from("report")
        .select("id,tipo,subtipo,descripcion,likes,dislikes,estado,creado_en,expira_en,lat,lon")
        .order("creado_en", { ascending: false })
        .limit(500)
    )
  );
}

// Capa de anomalías de precipitación (FeatureCollection GeoJSON en la tabla mapa).
export async function getMapaAnomalias() {
  const [m] = await filas(
    supabase
      .from("mapa")
      .select("titulo,variable,periodo,fuente,geojson")
      .eq("variable", "precipitacion")
      .order("periodo", { ascending: false }) // el mes más reciente
      .limit(1)
  );
  return m ?? null;
}
