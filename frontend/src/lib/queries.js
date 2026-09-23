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
        .select("estacion,rio,departamento,fecha,hora,valor,unidad,umbral_alerta,umbral_emergencia,tendencia,estado,lat,lon")
    )
  );
}

// ICEN (IGP o ENFEN, el mes más nuevo), su estimado ICEN_TMP y el RONI de NOAA.
export function getIndices() {
  return cached("indices", () =>
    filas(supabase.from("indice").select("fuente,periodo,valor,categoria,origen"))
  );
}

// Último comunicado oficial del ENFEN (estado del Sistema de Alerta).
export async function getComunicadoENFEN() {
  const [c] = await cached("enfen", () =>
    filas(
      supabase
        .from("comunicado_enfen")
        .select("anio,numero,extraordinario,fecha,estado,proximo,resumen,url")
        .order("fecha", { ascending: false })
        .limit(1)
    ),
    10 * 60_000
  );
  return c ?? null;
}

// ICEN mes a mes (IGP y tabla del Informe Técnico ENFEN), los últimos `meses`, del más viejo
// al más nuevo: para el gráfico de El Niño.
export function getIcenSerie(meses = 24) {
  return cached(`icen_serie:${meses}`, async () =>
    (
      await filas(
        supabase.from("icen_serie").select("mes,valor,categoria,origen").order("mes", { ascending: false }).limit(meses)
      )
    ).reverse(),
    10 * 60_000
  );
}

// Avisos de SENAMHI que no han terminado (vista aviso_vigente), con el polígono en GeoJSON;
// ya vienen ordenados por nivel (el rojo al final, para dibujarlo encima).
export function getAvisosVigentes() {
  return cached(
    "avisos",
    () =>
      filas(
        supabase
          .from("aviso_vigente")
          .select("id,tipo,numero,mapa,nivel,titulo,tema,descripcion,inicio,fin,en_curso,departamentos,url,geojson")
      ),
    5 * 60_000
  );
}

// Lluvia de la última hora en ~200 estaciones automáticas de SENAMHI en todo el país
// (vista lluvia_senamhi_actual: solo lecturas de las últimas 3 h), con la referencia de
// SENAMHI de cada estación en 1 h y en 6 h. La comparten el mapa y el panel de estado.
export function getLluviaAhora() {
  return cached(
    "lluvia_ahora",
    () =>
      filas(
        supabase
          .from("lluvia_senamhi_actual")
          .select("clave,nombre,departamento,provincia,distrito,pp_1h,umbral_1h,pp_6h,umbral_6h,medido_en,lat,lon")
      ),
    5 * 60_000
  );
}

// Cuándo corrió de verdad la ingesta (para avisar "sin actualizar" si se detiene).
export function getLatido() {
  return cached("latido", () => filas(supabase.from("latido").select("servicio,ts,resumen")));
}

// Lluvia horaria de las últimas 24 h de las estaciones de un departamento.
export function getLluvia24h(depto) {
  const desde = new Date(Date.now() - 24 * 3_600_000).toISOString();
  return cached(`lluvia:${depto}`, () =>
    filas(
      supabase
        .from("lectura_lluvia")
        .select("cod,medido_en,precip_mm,estacion!inner(nombre,departamento)")
        .eq("estacion.departamento", depto)
        .gte("medido_en", desde)
        .order("medido_en")
    )
  );
}

// Alertas vigentes, con su departamento en `zona` (ríos: ingesta; avisos: tarea avisos;
// lluvia: tarea lluvia_nacional). La vista alerta_actual ya deja fuera la lluvia medida
// hace más de 3 h; en la de lluvia, `valor` y `umbral` son los de la ventana `ventana_h`.
export function getAlertasVigentes() {
  return cached("alertas", () =>
    filas(
      supabase
        .from("alerta_actual")
        .select("tipo,referencia,zona,nivel,detalle,valor,umbral,ventana_h,ts")
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

// Mapa de un evento El Niño pasado (variable 'FEN'; periodo = "1997-1998", "2017", ...).
// Son mapas fijos: se guardan en memoria toda la sesión.
export async function getMapaFEN(periodo) {
  const [m] = await cached(
    `fen:${periodo}`,
    () =>
      filas(
        supabase
          .from("mapa")
          .select("titulo,periodo,fuente,geojson")
          .eq("variable", "FEN")
          .eq("periodo", periodo)
          .limit(1)
      ),
    Infinity
  );
  return m ?? null;
}
