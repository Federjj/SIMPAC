import L from "leaflet";
import { conMemoria, elegirLugares, medioTexto } from "./rotuloBusqueda";

// Nombre de un río escrito sobre su trazo (SVG <textPath>), como en los mapas impresos. Va sobre una
// guía: el trazo simplificado a ~120 m (rio_vigilado_mapa.guia_rotulo), porque sobre un cauce que
// serpentea las letras se leen entrecortadas. La guía es una polilínea invisible del pane `pane`;
// el texto se agrega a su mismo SVG y se recalcula al terminar cada movimiento del mapa:
//   - en lugares del trazo donde todo el texto quede a la vista y fuera de lo que tapa el mapa
//     (chips, paneles y botones de zoom: [data-tapa-mapa], como en map/acomodo.js), a `lejosPx` o
//     más de los puntos a evitar (el disco de la estación) y a `entrePx` o más entre sí; como
//     máximo `repetir` veces;
//   - en un tramo sin quiebres cerrados: en una curva las letras del lado de adentro se enciman
//     (tanto más cuanto más corrido está el texto de la línea, `dy`), así que en cada tramo de 16 px
//     a lo largo del texto la guía no puede girar hacia el lado del texto más de lo que encime unos
//     2,5 px a esa distancia (hacia el otro lado las letras solo se separan: se tolera el triple);
//     y en todo el texto, no más de 90°. La guía se suaviza antes (Chaikin, 2 pasadas): sus vértices
//     cada ~120 m son quiebres que con el mapa alejado no dejaban lugar;
//   - en el sentido que se lea de izquierda a derecha.
// `dy` lo corre a un lado de la línea (negativo: arriba) y `clase` es la clase del texto. El del
// río se ve solo desde zoom 13 (index.css: .rio-nombre por [data-zoom-banda]). Al quitar la guía
// del mapa (se apaga la capa o se vuelve a dibujar) se suelta el evento y se borra el texto.
//
// Costo: getPointAtLength es lo más caro de cada zoom y de cada arrastre (era la mitad del tiempo
// de JS de un zoom). Por eso:
//   - los puntos se piden una sola vez por largo entero en cada pasada (memoria);
//   - tras un arrastre (mismo zoom), si los rótulos que ya están siguen a la vista y libres, no se
//     busca ni se toca el DOM; se vuelve a buscar solo si cambió el zoom o alguno quedó tapado;
//   - la búsqueda espera 120 ms después de moveend: un arrastre con paradas cortas no la corre en
//     cada parada;
//   - la búsqueda avanza de a 3 % del trazo y mira la curvatura cada 8 px (antes 2 % y 4 px: el
//     resultado es el mismo).
// La búsqueda en sí (map/rotuloBusqueda.js elegirLugares) no toca el DOM: la prueba rotuloLinea.test.js.
const SVG_NS = "http://www.w3.org/2000/svg";
const TAPA_MAPA = "[data-tapa-mapa], .leaflet-control-zoom";
const ESPERA_MS = 120; // tras moveend

// Chaikin: cada pasada corta las esquinas a 1/4 y 3/4 de cada tramo (las puntas no se mueven)
function suavizar(pts, pasadas = 2) {
  let p = pts;
  for (let k = 0; k < pasadas && p.length > 2; k++) {
    const q = [p[0]];
    for (let i = 0; i < p.length - 1; i++) {
      const [a0, a1] = p[i];
      const [b0, b1] = p[i + 1];
      q.push([0.75 * a0 + 0.25 * b0, 0.75 * a1 + 0.25 * b1], [0.25 * a0 + 0.75 * b0, 0.25 * a1 + 0.75 * b1]);
    }
    q.push(p[p.length - 1]);
    p = q;
  }
  return p;
}

// cajas de lo que tapa el mapa, en píxeles del contenedor del mapa (con 6 px de aire)
function tapas(map) {
  const m = map.getContainer().getBoundingClientRect();
  const out = [];
  for (const el of document.querySelectorAll(TAPA_MAPA)) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    out.push({ x0: r.left - m.left - 6, y0: r.top - m.top - 6, x1: r.right - m.left + 6, y1: r.bottom - m.top + 6 });
  }
  return out;
}

export function rotuloLinea(
  map,
  latlngs,
  texto,
  { evitar = [], pane = "rios", repetir = 2, lejosPx = 90, entrePx = 260, dy = -9, clase = "rio-nombre" } = {}
) {
  // noClip: el trazo entero (no solo la parte a la vista), así el largo y los lugares no saltan
  const guia = L.polyline(suavizar(latlngs), { pane, stroke: false, fill: false, interactive: false, noClip: true });
  let nodo = null;
  let hecho = null; // { zoom, largo, elegidos } de lo que está dibujado

  const borrar = () => {
    nodo?.remove();
    nodo = null;
    hecho = null;
  };

  const dibujar = () => {
    const path = guia._path;
    const svg = path?.ownerSVGElement;
    if (!svg || !guia._map) return borrar();
    // de izquierda a derecha en la pantalla (si no, el texto queda cabeza abajo)
    const pts = guia.getLatLngs();
    if (pts.length < 2) return borrar();
    if (map.latLngToLayerPoint(pts[0]).x > map.latLngToLayerPoint(pts[pts.length - 1]).x) {
      guia.setLatLngs([...pts].reverse()); // vuelve a armar el trazo (mismo <path>)
      borrar();
    }
    const id = `simpac-guia-${L.stamp(guia)}`;
    path.id = id;
    const largo = path.getTotalLength();
    if (!largo) return borrar();
    const zoom = map.getZoom();
    const ctx = {
      largo,
      punto: conMemoria((l) => path.getPointAtLength(l), largo),
      tam: map.getSize(),
      origen: map.containerPointToLayerPoint([0, 0]), // el SVG usa coordenadas de capa
      lejos: evitar.map((ll) => map.latLngToLayerPoint(ll)),
      cajas: tapas(map),
      medio: medioTexto(texto),
      lejosPx,
      entrePx,
      repetir,
      dy,
    };
    // tras un arrastre, si lo dibujado sigue a la vista y libre, no se toca nada
    const previos = nodo && hecho && hecho.zoom === zoom && hecho.largo === largo ? hecho.elegidos : null;
    const { elegidos, iguales } = elegirLugares(ctx, previos);
    if (iguales) return;
    borrar();
    if (!elegidos.length) return;
    nodo = document.createElementNS(SVG_NS, "text");
    nodo.setAttribute("class", clase);
    nodo.setAttribute("dy", String(dy));
    nodo.setAttribute("aria-hidden", "true"); // lo mismo está en el tooltip y el popup
    for (const f of elegidos) {
      const tp = document.createElementNS(SVG_NS, "textPath");
      tp.setAttribute("href", `#${id}`);
      tp.setAttribute("startOffset", `${(f * 100).toFixed(1)}%`);
      tp.setAttribute("text-anchor", "middle");
      tp.textContent = texto; // texto plano: nunca HTML
      nodo.appendChild(tp);
    }
    svg.appendChild(nodo);
    hecho = { zoom, largo, elegidos };
  };

  // La primera vez, en el cuadro siguiente (el SVG ya rehízo el trazo con la vista nueva); después
  // de cada movimiento, 120 ms más tarde: un arrastre con paradas cortas no busca en cada parada.
  let cuadro = 0;
  let espera = 0;
  const cancelar = () => {
    cancelAnimationFrame(cuadro);
    clearTimeout(espera);
  };
  const pedir = () => {
    cancelar();
    cuadro = requestAnimationFrame(dibujar);
  };
  const pedirLuego = () => {
    cancelar();
    espera = setTimeout(pedir, ESPERA_MS);
  };
  guia.on("add", () => {
    map.on("moveend", pedirLuego);
    pedir();
  });
  guia.on("remove", () => {
    map.off("moveend", pedirLuego);
    cancelar();
    borrar();
  });
  return guia;
}
