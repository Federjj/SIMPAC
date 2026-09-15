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
