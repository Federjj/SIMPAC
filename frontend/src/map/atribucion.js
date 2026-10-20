// Atribución corta del mapa en el celular (map/baseMap.js Atribucion): una sola línea con quién
// hace el mapa base y de quién son los datos de las capas encendidas, armada con los textos de
// atribución que Leaflet junta (el del mapa base y el `attribution` de cada capa). El texto
// completo, con sus enlaces, se despliega al tocar "más" y sigue en el panel de capas y en la hoja.
// Módulo puro (sin Leaflet): lo prueba node --test (atribucion.test.js).
const sinEtiquetas = (h) => String(h ?? "").replace(/<[^>]*>/g, "");

export const BASE_CORTA = "© Stadia Maps · OpenMapTiles · OSM";

// a quién nombran los textos de las capas, en este orden
const ORGANISMOS = [
  ["SENAMHI", /SENAMHI/],
  ["ANA", /\bANA\b/],
  ["NASA", /NASA/],
  ["ENFEN", /ENFEN/],
  ["IGP", /\bIGP\b/],
  ["INDECI", /INDECI/],
  ["CENEPRED", /CENEPRED/],
  ["OpenStreetMap", /OpenStreetMap/],
];

// Nombres cortos de las fuentes de datos que aparecen en los textos (sin el mapa base), sin repetir.
export function fuentesDe(textos = []) {
  const deCapas = textos.map(sinEtiquetas).filter((t) => !/Stadia Maps/.test(t)); // el mapa base va aparte
  return ORGANISMOS.filter(([, re]) => deCapas.some((t) => re.test(t))).map(([nombre]) => nombre);
}

// "© Stadia Maps · OpenMapTiles · OSM · Datos: SENAMHI, ANA"
export function lineaCorta(textos = []) {
  const partes = [];
  if (textos.some((t) => /Stadia Maps/.test(sinEtiquetas(t)))) partes.push(BASE_CORTA);
  const fuentes = fuentesDe(textos);
  if (fuentes.length) partes.push(`Datos: ${fuentes.join(", ")}`);
  return partes.join(" · ");
}
