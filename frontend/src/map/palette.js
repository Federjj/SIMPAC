// Colores del mapa (paleta del equipo). Un mismo color puede aparecer en dos capas:
// la forma del marcador (círculo con ícono = estación/río, gota = reporte, punto = anomalía)
// y la leyenda de cada capa los distinguen.
export const NIVEL_HEX = { normal: "#3BEB40", alerta: "#F58E27", emergencia: "#DB0404" };
export const ESTACION_HEX = { M: "#3BA5EB", H: "#3B3BEB" };
export const SIN_DATO_HEX = "#9CA3AF";

// Anomalía de precipitación (%): seco (rojo/naranja) <-> húmedo (celeste/azul).
const ANOM = [
  { color: "#DB0404", label: "Muy seco (≤ -50 %)" },
  { color: "#F58E27", label: "Seco (-50 a -20 %)" },
  { color: "#EBEB3B", label: "Normal (-20 a +20 %)" },
  { color: "#3BA5EB", label: "Húmedo (+20 a +50 %)" },
  { color: "#3B3BEB", label: "Muy húmedo (≥ +50 %)" },
];

export function anomColor(a) {
  if (a <= -50) return ANOM[0].color;
  if (a <= -20) return ANOM[1].color;
  if (a < 20) return ANOM[2].color;
  if (a < 50) return ANOM[3].color;
  return ANOM[4].color;
}

export const ANOM_LEYENDA = ANOM;
