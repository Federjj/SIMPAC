import L from "leaflet";
import { glifoSvg } from "./iconos";
import { escapeHtml } from "./markers";
import { AVISO_ARO, AVISO_HALO, PRONOSTICO_HEX } from "./palette";

// Marcadores de las insignias de los avisos y de los discos del pronóstico. El ícono de Leaflet
// mide 0x0 y el CSS (index.css, .mkr) dibuja alrededor del punto: así un cambio de tamaño por
// escala o un corrimiento del acomodo (--dx, --dy) no descuadra el anclaje.
const icono = (html) => L.divIcon({ className: "", iconSize: [0, 0], iconAnchor: [0, 0], popupAnchor: [0, -24], html });

// Insignia: disco blanco con aro del color del nivel, halo suave y el glifo del fenómeno; el chip
// ("24 h" o "2 avisos") lo pone map/acomodo.js.
export function iconoInsignia({ glifo, nivel, chip = "" }) {
  return icono(
    `<div class="mkr mk-ins" style="--aro:${AVISO_ARO[nivel]};--halo:${AVISO_HALO[nivel]}">` +
      `<div class="ins-cuerpo">${glifoSvg(glifo)}</div><span class="ins-chip">${escapeHtml(chip)}</span></div>`
  );
}

// Disco de una localidad: blanco con el glifo del tiempo (punteado si SENAMHI dice "tendencia a");
// cuando no cabe es un punto del color de su clase. clase: lluvia | tormenta | nieve | seco.
export function iconoLocalidad({ glifo, clase, tono = clase, posible = false, nombre, temps }) {
  return icono(
    `<div class="mkr mk-loc loc-${clase}${posible ? " posible" : ""}" style="--c:${PRONOSTICO_HEX[tono] ?? PRONOSTICO_HEX.seco}">` +
      `<div class="loc-cuerpo">${glifoSvg(glifo)}</div>` +
      `<span class="loc-rot">${escapeHtml(nombre)}<span class="t">${escapeHtml(temps)}</span></span></div>`
  );
}
