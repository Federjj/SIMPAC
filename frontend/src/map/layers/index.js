// Capas del mapa, en el orden en que se listan en el panel. (El apilado lo decide
// Leaflet: zonas y puntos van en el pane de overlays, los marcadores siempre encima.)
//
// Cada capa exporta la misma forma, así sumar una nueva (p. ej. las áreas FEN
// históricas) es crear su archivo y agregarla aquí:
//   id             clave en el estado de visibilidad
//   label, Icon    cómo se ve en el panel de capas
//   defaultVisible si arranca encendida
//   legend         [{ color, label, zona?, gota? }] que el panel muestra bajo el switch
//   load()         Promise con los datos (se llama la primera vez que se enciende)
//   render(group, datos)  dibuja en un L.layerGroup vacío
//   refreshMs      opcional: cada cuánto recargar mientras esté encendida
import estaciones from "./estaciones";
import zonasCaudal from "./zonasCaudal";
import anomalias from "./anomalias";
import rios from "./rios";
import incidentes from "./incidentes";

export const LAYERS = [rios, zonasCaudal, incidentes, estaciones, anomalias];
