// Colores del mapa (paleta del equipo). Un mismo color puede aparecer en dos capas:
// la forma del marcador (círculo con ícono = estación/río, gota = reporte, punto = anomalía)
// y la leyenda de cada capa los distinguen.
// aviso: amarillo más oscuro que el de las áreas del mapa (#EBEB3B), para que un ícono blanco
// encima o un ícono amarillo sobre fondo blanco se lean.
export const NIVEL_HEX = { normal: "#3BEB40", aviso: "#EAB308", alerta: "#F58E27", emergencia: "#DB0404", sin_dato: "#9CA3AF" };
// Estados de un río en el mapa (lib/lenguaje.js textoRio). "atento" es criterio de SIMPAC.
export const RIO_HEX = {
  normal: NIVEL_HEX.normal,
  atento: "#EBEB3B",
  alerta: NIVEL_HEX.alerta,
  emergencia: NIVEL_HEX.emergencia,
  sd: "#9CA3AF",
};
// Estado del Sistema de Alerta ENFEN: alerta en naranja, vigilancia en amarillo, sin alerta en verde.
export const ENFEN_HEX = { Alerta: NIVEL_HEX.alerta, Vigilancia: "#EBEB3B", "Sin alerta": NIVEL_HEX.normal };
export const ESTACION_HEX = { M: "#3BA5EB", H: "#3B3BEB" };
export const SIN_DATO_HEX = "#9CA3AF";

// Las clases de la anomalía mensual de lluvia viven en lib/lenguaje.js (CLASES_ANOMALIA),
// junto con su texto: son las clases oficiales de SENAMHI.
