// Colores del mapa (paleta del equipo). Un mismo color puede aparecer en dos capas:
// la forma del marcador (círculo con ícono = estación/río, gota = reporte, punto = anomalía)
// y la leyenda de cada capa los distinguen.
export const NIVEL_HEX = { normal: "#3BEB40", alerta: "#F58E27", emergencia: "#DB0404", sin_dato: "#9CA3AF" };
// Estados de un río en el mapa (lib/lenguaje.js textoRio). "atento" es criterio de SIMPAC.
export const RIO_HEX = {
  normal: NIVEL_HEX.normal,
  atento: "#EBEB3B",
  alerta: NIVEL_HEX.alerta,
  emergencia: NIVEL_HEX.emergencia,
  sd: "#9CA3AF",
};
export const ESTACION_HEX = { M: "#3BA5EB", H: "#3B3BEB" };
export const SIN_DATO_HEX = "#9CA3AF";

// Las clases de la anomalía mensual de lluvia viven en lib/lenguaje.js (CLASES_ANOMALIA),
// junto con su texto: son las clases oficiales de SENAMHI.
