// Capas del mapa, agrupadas en el panel por `grupo` (en el orden de GRUPOS) y, dentro de
// cada grupo, en el orden de LAYERS. (El apilado lo decide Leaflet: las áreas sombreadas
// van en el pane "areas", debajo de zonas y puntos; los marcadores siempre encima.)
//
// Cada capa exporta la misma forma, así sumar una nueva es crear su archivo y agregarla aquí:
//   id             clave en el estado de visibilidad
//   grupo          uno de GRUPOS
//   label, Icon    cómo se ve en el panel de capas
//   defaultVisible si arranca encendida
//   legend         [{ color, label, zona?, gota? }] bajo el switch, o fn(opcion) que la devuelve
//   opciones       opcional: { etiqueta, valores: [{ valor, etiqueta }], defecto } (un selector)
//   fuente         opcional: de dónde sale el dato (y la atribución que pida la licencia)
//   load(opcion)   Promise con los datos (al encenderla y cada vez que cambia la opción)
//   render(group, datos, { opcion, map, avisar })  dibuja en un L.layerGroup vacío; puede
//                  devolver un texto corto que el panel muestra bajo el switch, y avisar(texto)
//                  lo cambia después (p. ej. si el servidor de imágenes no responde)
//   refreshMs      opcional: cada cuánto recargar mientras esté encendida
import estaciones from "./estaciones";
import zonasCaudal from "./zonasCaudal";
import anomalias from "./anomalias";
import rios from "./rios";
import incidentes from "./incidentes";
import huaycos from "./huaycos";
import lluviaObservada from "./lluviaObservada";
import lluviaSatelite from "./lluviaSatelite";
import fenHistorico from "./fenHistorico";
import avisos from "./avisos";
import lluviaAhora from "./lluviaAhora";

export const GRUPOS = ["Alertas y avisos", "Lluvia", "Ríos y estaciones", "El Niño", "Comunidad"];

export const LAYERS = [
  avisos,
  zonasCaudal,
  huaycos,
  lluviaAhora,
  lluviaObservada,
  lluviaSatelite,
  anomalias,
  rios,
  estaciones,
  fenHistorico,
  incidentes,
];
