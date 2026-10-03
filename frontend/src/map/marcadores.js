import L from "leaflet";
import { glifoSvg } from "./iconos";
import { escapeHtml } from "./markers";
import { AVISO_ARO, AVISO_HALO, PRONOSTICO_HEX, RIO_HEX } from "./palette";

// Marcadores de las insignias de los avisos, de los discos del pronóstico y de los ríos (y los
// rombos de los desbordes pasados y los lugares de los avisos hidrológicos). El ícono de Leaflet
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

// ---------------------------------------------------------------------------
// Ríos (layers/rios.js): disco blanco con aro del color del estado y una ola doble, con rótulo
// «Mashcón · Tranquilo 0.13 m³/s». Mismo sistema que las insignias: ícono 0x0, el CSS dibuja
// alrededor del punto y el acomodo lo corre (--dx, --dy), lo deja como punto o le pone el rótulo.
// ---------------------------------------------------------------------------

const OLA =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true">' +
  '<path d="M3 9c3 3 5-2 9 0s5 2 9 0"/><path d="M3 15c3 3 5-2 9 0s5 2 9 0"/></svg>';
// color de la ola sobre blanco (el verde y el amarillo de la paleta no se leen sobre blanco)
const GLIFO_RIO = { normal: "#15803D", atento: "#A16207", alerta: "#C2410C", emergencia: "#B91C1C", sd: "#64748B" };
// etiqueta corta del rótulo (lib/lenguaje.js textoRio da `estado`, `bajo` y `etiqueta`)
export const CORTA = { normal: "Tranquilo", atento: "Cerca de alerta", alerta: "En alerta", emergencia: "En emergencia", sd: "Sin nivel de alerta" };

const sinTildes = (s) => (s ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
// "Mashcón" (la estación ya nombra al río) o "Marañón en Balsas"
export function nombreRio(c) {
  if (!c.rio) return c.estacion;
  return sinTildes(c.estacion).includes(sinTildes(c.rio)) ? c.estacion : `${c.rio} en ${c.estacion}`;
}

// Partes del rótulo de una estación (t = textoRio(c)): el valor solo se ve a escala local (CSS).
export function textoRotulo(c, t) {
  const estado =
    t.bajo && (t.estado === "alerta" || t.estado === "emergencia")
      ? "Río muy bajo"
      : t.estado === "sd" && c.valor == null
        ? "Sin medición"
        : CORTA[t.estado];
  const valor = c.valor != null ? `${Number(c.valor).toLocaleString("es-PE", { maximumFractionDigits: 2 })} ${c.unidad}` : "";
  return { nombre: nombreRio(c), estado, valor };
}

// fuerte = en alerta o emergencia por crecida: el aro late y el rótulo va en una pastilla de color.
export function iconoRio({ estado, fuerte, rotulo }) {
  const c = RIO_HEX[estado] ?? RIO_HEX.sd;
  return icono(
    `<div class="mkr mk-rio${fuerte ? " fuerte" : ""}" style="--c:${c};--g:${GLIFO_RIO[estado] ?? GLIFO_RIO.sd}">` +
      `<div class="rio-cuerpo">${OLA}</div>` +
      `<span class="rio-rot"><span class="pt"></span>${escapeHtml(rotulo.nombre)} · ${escapeHtml(rotulo.estado)}` +
      (rotulo.valor ? ` <span class="v">${escapeHtml(rotulo.valor)}</span>` : "") +
      `</span></div>`
  );
}

// Desborde o daño pasado (layers/desbordes.js): rombo pizarra con el año ("’14") y, si en el mismo
// lugar hay más de uno, la insignia "×2". Mide 24x24; el contenido va en .inc, que el acomodo corre
// (--dx/--dy) si el rombo quedaría tapado, con una línea fina hasta su punto (.inc-linea). La clase
// va en el ícono para ocultarlo entero con el mapa alejado (index.css).
export function iconoIncidente({ anio, n = 1 }) {
  return L.divIcon({
    className: "mk-inc",
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -14],
    html:
      `<div class="inc"><span class="inc-linea"></span><span class="inc-rombo"></span>` +
      `<span class="inc-anio">${escapeHtml(anio)}</span>` +
      (n > 1 ? `<span class="inc-n">×${n}</span>` : "") +
      `</div>`,
  });
}

// Lugar que SENAMHI nombra en sus avisos del río (layers/zonasRio.js): punto oscuro con aro blanco
// y su nombre (desde zoom 13, index.css).
export function iconoLugar(nombre) {
  return L.divIcon({
    className: "mk-lugar",
    iconSize: [12, 12],
    iconAnchor: [6, 6],
    popupAnchor: [0, -8],
    html: `<span class="lug-punto"></span><span class="lug-rot">${escapeHtml(nombre)}</span>`,
  });
}
