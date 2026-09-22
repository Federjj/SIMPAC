import { getEstaciones } from "./queries";

// Departamento de un punto GPS = el de la estación SENAMHI más cercana (hay 982, todas con
// departamento). Con la capital más cercana, 4 de 10 pueblos de frontera caían en otro
// departamento (Jaén quedaba en Amazonas); con la estación más cercana acertó 15 de 15.
// En un borde exacto puede fallar: el selector de ciudad deja corregirlo.
export async function departamentoEn(lat, lon) {
  const estaciones = await getEstaciones(); // ya en caché (capa de estaciones)
  const k = Math.cos((lat * Math.PI) / 180); // la longitud "encoge" hacia los polos
  let mejor = null;
  let distMin = Infinity;
  for (const e of estaciones) {
    if (e.lat == null || !e.departamento) continue;
    const d = (e.lat - lat) ** 2 + ((e.lon - lon) * k) ** 2;
    if (d < distMin) {
      distMin = d;
      mejor = e.departamento;
    }
  }
  return mejor;
}
