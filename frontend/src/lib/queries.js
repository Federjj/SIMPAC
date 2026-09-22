import { supabase } from "./supabaseClient";

// Datos oficiales (lectura pública con la publishable key).
export async function getEstaciones() {
  const { data, error } = await supabase
    .from("estacion")
    .select("cod,nombre,tipo,estado,lat,lon");
  if (error) throw error;
  return data ?? [];
}

export async function getCaudales() {
  const { data, error } = await supabase
    .from("lectura_caudal")
    .select("estacion,rio,valor,unidad,estado,lat,lon");
  if (error) throw error;
  return data ?? [];
}

export async function getIndices() {
  const { data, error } = await supabase
    .from("indice")
    .select("fuente,periodo,valor,categoria");
  if (error) throw error;
  return data ?? [];
}

// Capa de anomalias de precipitacion (FeatureCollection GeoJSON en la tabla mapa).
export async function getMapaAnomalias() {
  const { data, error } = await supabase
    .from("mapa")
    .select("titulo,variable,periodo,fuente,geojson")
    .eq("variable", "precipitacion")
    .order("periodo", { ascending: false })   // el mes más reciente
    .limit(1);
  if (error) throw error;
  return data?.[0] ?? null;
}
