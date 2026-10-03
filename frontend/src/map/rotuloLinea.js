import L from "leaflet";

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
const SVG_NS = "http://www.w3.org/2000/svg";
const TAPA_MAPA = "[data-tapa-mapa], .leaflet-control-zoom";
const ANCHO_LETRA = 7.5; // px por letra (12 px, seminegrita, con espaciado)
const MAX_GIRO = Math.PI / 2; // en todo el texto

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

  const borrar = () => {
    nodo?.remove();
    nodo = null;
  };

  const dibujar = () => {
    borrar();
    const path = guia._path;
    const svg = path?.ownerSVGElement;
    if (!svg || !guia._map) return;
    // de izquierda a derecha en la pantalla (si no, el texto queda cabeza abajo)
    const pts = guia.getLatLngs();
    if (pts.length < 2) return;
    if (map.latLngToLayerPoint(pts[0]).x > map.latLngToLayerPoint(pts[pts.length - 1]).x) {
      guia.setLatLngs([...pts].reverse()); // vuelve a armar el trazo (mismo <path>)
    }
    const id = `simpac-guia-${L.stamp(guia)}`;
    path.id = id;
    const largo = path.getTotalLength();
    if (!largo) return;
    const tam = map.getSize();
    const origen = map.containerPointToLayerPoint([0, 0]); // el SVG usa coordenadas de capa
    const lejos = evitar.map((ll) => map.latLngToLayerPoint(ll));
    const cajas = tapas(map);
    const medio = (texto.length * ANCHO_LETRA) / 2 + 6; // medio largo del texto sobre la línea
    const punto = (l) => path.getPointAtLength(Math.max(0, Math.min(largo, l)));
    const rumbo = (l) => {
      const a = punto(l - 3);
      const b = punto(l + 3);
      return Math.atan2(b.y - a.y, b.x - a.x);
    };
    // lo más que puede girar la guía en 16 px sin que las letras se enciman (a la altura de su centro)
    const maxLocal = 2.5 / (Math.abs(dy) + 4);
    // cuánto gira la guía de l a l + 16 (con signo: en la pantalla, negativo = hacia la izquierda del
    // avance, que es el lado del texto si dy < 0)
    const doblez = (l) => {
      const d = rumbo(l + 16) - rumbo(l);
      return Math.atan2(Math.sin(d), Math.cos(d));
    };
    const haciaElTexto = (g) => (dy < 0 ? g < 0 : g > 0);
    // false si entre l0 y l1 la guía tiene un quiebre cerrado o gira demasiado en total
    const recta = (l0, l1) => {
      let total = 0;
      for (let i = 0, l = l0; l + 16 <= l1; i++, l += 4) {
        const g = doblez(l);
        if (Math.abs(g) > (haciaElTexto(g) ? maxLocal : 3 * maxLocal)) return false;
        if (i % 4 === 0) total += Math.abs(g); // tramos de 16 px seguidos, sin contar dos veces
      }
      return total <= MAX_GIRO;
    };
    // todo el texto (cada ~10 px a lo largo, corrido `dy`) a la vista y fuera de chips y paneles
    const libre = (l0) => {
      for (let l = l0 - medio; l <= l0 + medio; l += 10) {
        const q = punto(l);
        const x = q.x - origen.x;
        const y = q.y - origen.y + dy;
        if (x < 8 || y < 8 || x > tam.x - 8 || y > tam.y - 8) return false;
        if (cajas.some((c) => x > c.x0 && x < c.x1 && y > c.y0 && y < c.y1)) return false;
      }
      return true;
    };
    const elegidos = [];
    for (let f = 0.06; f <= 0.94 && elegidos.length < repetir; f += 0.02) {
      const l = f * largo;
      if (l - medio < 0 || l + medio > largo) continue;
      const q = punto(l);
      if (lejos.some((p) => Math.hypot(q.x - p.x, q.y - p.y) < lejosPx)) continue;
      if (elegidos.some((g) => Math.abs(g - f) * largo < entrePx)) continue;
      if (!recta(Math.max(3, l - medio - 6), Math.min(largo - 3, l + medio + 6))) continue;
      if (!libre(l)) continue;
      elegidos.push(f);
    }
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
  };

  // en el cuadro siguiente: el SVG ya rehízo el trazo con la vista nueva
  let cuadro = 0;
  const pedir = () => {
    cancelAnimationFrame(cuadro);
    cuadro = requestAnimationFrame(dibujar);
  };
  guia.on("add", () => {
    map.on("moveend", pedir);
    pedir();
  });
  guia.on("remove", () => {
    map.off("moveend", pedir);
    cancelAnimationFrame(cuadro);
    borrar();
  });
  return guia;
}
