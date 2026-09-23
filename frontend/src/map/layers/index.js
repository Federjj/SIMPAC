// Capas del mapa, agrupadas en el panel por `grupo` (en el orden de GRUPOS) y, dentro de
// cada grupo, en el orden de LAYERS. (El apilado lo decide Leaflet: las áreas sombreadas
// van en los panes "areas" y "aviso2..4" (MapView), debajo de zonas y puntos; el nowcasting en
// "nowcast"; los marcadores siempre encima.)
//
// Cada capa exporta la misma forma, así sumar una nueva es crear su archivo y agregarla aquí:
//   id             clave en el estado de visibilidad
//   grupo          uno de GRUPOS
//   label, Icon    cómo se ve en el panel de capas
//   insignia       opcional: "Oficial" | "Experimental" (junto al nombre en el panel)
//   defaultVisible si arranca encendida
//   legend         [{ color, label, zona?, gota?, anillo?, forma?, glifo?, punteado? }] bajo el switch,
//                  o fn(opcion) que la devuelve (forma: "insignia" | "disco" | "mancha")
//   opciones       opcional: { etiqueta, valores: [{ valor, etiqueta }], defecto, vinculo? } (un
//                  selector); las capas con el mismo `vinculo` comparten la opción (el día)
//   fuente         opcional: de dónde sale el dato (y la atribución que pida la licencia)
//   load(opcion)   Promise con los datos (al encenderla y cada vez que cambia la opción)
//   render(group, datos, { opcion, map, avisar, acomodo })  dibuja en un L.layerGroup vacío;
//                  puede devolver un texto corto (o {texto, corto, estado}) que el panel muestra
//                  bajo el switch, y avisar(nota) lo cambia después (p. ej. si el servidor de
//                  imágenes no responde). acomodo.registrar(marker, meta) suma un marcador al
//                  acomodo en pantalla (map/acomodo.js)
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
import pronostico from "./pronostico";
import nowcast from "./nowcast";
import lluviaAhora from "./lluviaAhora";

export const GRUPOS = ["Alertas y avisos", "Pronóstico", "Lluvia", "Ríos y estaciones", "El Niño", "Comunidad"];

export const LAYERS = [
  avisos,
  pronostico,
  nowcast,
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
