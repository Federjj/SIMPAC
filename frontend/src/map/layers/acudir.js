import L from "leaflet";
import { LifeBuoy } from "lucide-react";
import { getPuntosAcudirCaja } from "@/lib/queries";
import { TIPO_ACUDIR, cajaRedondeada, enlacesComoLlegar, esAndroid, fechaCorta, notaFuente, telefonos } from "@/lib/acudir";
import { escapeHtml, popupHtml } from "../markers";
import { opcionesPopup } from "../popups";

// A dónde acudir (tabla punto_acudir): establecimientos de salud (SUSALUD RENIPRESS), comisarías
// (padrón MININTER 2019 vía CENEPRED), compañías de bomberos (CGBVP, ubicación de CENEPRED) y las
// oficinas de Defensa Civil de Cajamarca (fichas de gob.pe). Apagada por defecto: la enciende la
// tarjeta "A dónde acudir" (verPunto en pages/Mapa.jsx) o el panel de capas.
//
// Rendimiento: el país tiene 12 915 puntos (11 376 de salud). La capa no pide la tabla entera:
// con cada movimiento del mapa pide la caja a la vista redondeada a 0,1 grados (lib/queries.js
// getPuntosAcudirCaja, caché de 60 min por caja) y dibuja solo lo que cae en la pantalla con un
// margen; los marcadores ya puestos se reusan por clave (al moverse un poco no se rehace nada).
// Con el mapa más alejado que el zoom 11 no se dibuja (habría miles de puntos sin sentido: un
// marcador por manzana); entre 11 y 12 se omiten los puestos y centros de salud que no atienden
// 24 h (en Lima a zoom 11 caben ~1500 puntos en pantalla; así quedan ~400); desde zoom 13 van
// todos (Cajamarca ciudad a zoom 14: 87 puntos). Los íconos son un SVG chico por tipo, sin
// filtros ni degradados.
export const ZOOM_MIN = 11;
const ZOOM_TODOS = 13;
const MARGEN = 0.25; // fracción de la pantalla que se dibuja de más a cada lado
const ESPERA_MOVIMIENTO_MS = 400; // cuánto se espera a que el mapa empiece a moverse antes de abrir un popup pedido

const svg = (d) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
// glifos de lucide (cross, shield, flame, house, tent, building): constantes, nunca datos
export const GLIFO_ACUDIR = {
  salud: svg('<path d="M11 2a2 2 0 0 0-2 2v5H4a2 2 0 0 0-2 2v2c0 1.1.9 2 2 2h5v5c0 1.1.9 2 2 2h2a2 2 0 0 0 2-2v-5h5a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2h-5V4a2 2 0 0 0-2-2z"/>'),
  comisaria: svg('<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'),
  bomberos: svg('<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>'),
  zona_segura: svg('<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'),
  albergue: svg('<path d="M3.5 21 14 3"/><path d="M20.5 21 10 3"/><path d="M15.5 21 12 15l-3.5 6"/><path d="M2 21h20"/>'),
  otro: svg('<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>'),
};

// Pedido de la tarjeta "A dónde acudir" (components/AcudirCercanos.jsx) que llegó antes de que la
// capa estuviera montada (se enciende y se centra el mapa en el mismo clic): se guarda hasta que
// render() lo consuma.
let pedidoPendiente = null;
if (typeof window !== "undefined") {
  window.addEventListener("simpac:acudir-ver", (e) => {
    pedidoPendiente = e.detail?.clave ?? null;
  });
}

const iconos = {};
function iconoAcudir(tipo) {
  const t = TIPO_ACUDIR[tipo] ? tipo : "otro";
  // un L.divIcon por tipo, compartido por todos sus marcadores
  iconos[t] ??= L.divIcon({
    className: "",
    html: `<div class="mk-acudir ac-${t}" style="--c:${TIPO_ACUDIR[t].color}">${GLIFO_ACUDIR[t]}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -14],
  });
  return iconos[t];
}

// Popup en lenguaje claro: qué es, si atiende 24 h (solo si la fuente lo dice), dónde queda,
// teléfono (enlace tel:), cómo llegar, y de dónde sale el dato y de cuándo es.
export function popupAcudir(p) {
  const t = TIPO_ACUDIR[p.tipo] ?? TIPO_ACUDIR.otro;
  const meta = [t.label, p.categoria && p.categoria !== t.label ? p.categoria : null];
  const donde = [p.direccion, p.distrito && p.distrito !== p.direccion ? p.distrito : null].filter(Boolean).join(", ");
  const tels = telefonos(p.telefono);
  const { maps, geo } = enlacesComoLlegar(p.lat, p.lon);
  const notas = [notaFuente(p), p.detalle?.nota].filter(Boolean);
  return (
    popupHtml({
      title: p.nombre,
      meta,
      resumen: p.atiende_24h === true ? "Atiende las 24 horas, según la fuente." : p.detalle?.horario ? `Horario según la fuente: ${p.detalle.horario}.` : null,
      filas: [["Dónde", donde || null]],
    }) +
    `<div class="pop pop-acudir">` +
    (tels.length
      ? `<p class="tel">Teléfono: ${tels.map((x) => `<a href="#" data-copiar="${escapeHtml(x.replace(/[^\d+]/g, ""))}" title="Tocar para copiar">${escapeHtml(x)}</a>`).join(" · ")} <span class="nota">(toca el número para copiarlo)</span></p>`
      : `<p class="nota">Sin teléfono en la fuente: si es urgente llama al 105 o al 116.</p>`) +
    `<p class="enl"><a href="${escapeHtml(maps)}" target="_blank" rel="noopener noreferrer">Cómo llegar (Google Maps)</a>` +
    (esAndroid() ? ` · <a href="${escapeHtml(geo)}">Abrir en el mapa del celular</a>` : "") +
    `</p>` +
    notas.map((n) => `<p class="nota">${escapeHtml(n)}</p>`).join("") +
    (p.fuente_url
      ? `<p class="nota"><a href="${escapeHtml(p.fuente_url)}" target="_blank" rel="noopener noreferrer">Ver la fuente (${escapeHtml(fechaCorta(p.actualizado))})</a></p>`
      : "") +
    `</div>`
  );
}

// Lo que se dibuja según el zoom: desde ZOOM_TODOS todo; antes, lo que atiende urgencias
// (hospitales y clínicas 24 h, comisarías, bomberos, Defensa Civil).
export const seDibuja = (p, zoom) => zoom >= ZOOM_TODOS || p.tipo !== "salud" || p.atiende_24h === true;

function resumen(n, zoom, caja) {
  const partes = Object.entries(TIPO_ACUDIR)
    .map(([k, t]) => [n[k] ?? 0, t.plural])
    .filter(([c]) => c > 0)
    .map(([c, l]) => `${c} ${l}`);
  const total = Object.values(n).reduce((a, b) => a + b, 0);
  const que = partes.length ? partes.join(", ") : "ningún punto registrado en esta parte del mapa";
  const omitidos = zoom < ZOOM_TODOS && caja > total ? ` Acércate más para ver también los ${caja - total} puestos y centros de salud sin atención 24 h.` : "";
  return {
    texto:
      `A la vista: ${que}.${omitidos} Salud: SUSALUD RENIPRESS (30-09-2026). Comisarías: padrón MININTER de 2019 vía CENEPRED, ` +
      `puede haber cambios. Bomberos: CGBVP con la ubicación de CENEPRED. Toca un punto para ver su fuente.`,
    corto: `A la vista: ${que}.`,
  };
}

export default {
  id: "acudir",
  grupo: "A dónde acudir",
  label: "Salud, comisarías y bomberos",
  Icon: LifeBuoy,
  defaultVisible: false,
  legend: Object.entries(TIPO_ACUDIR)
    .filter(([k]) => k !== "zona_segura" && k !== "albergue") // todavía no hay fuente oficial abierta
    .map(([, t]) => ({ color: t.color, label: t.leyenda })),
  fuente:
    "Salud: SUSALUD, Registro Nacional de IPRESS (RENIPRESS), datosabiertos.gob.pe (ODC-By). Comisarías: MININTER, " +
    "padrón de comisarías básicas de noviembre de 2019, servido por CENEPRED/COEN (ODC-By). Bomberos: CGBVP " +
    "(portal.bomberosperu.gob.pe), ubicación de CENEPRED/COEN. Defensa Civil de Cajamarca: fichas de gob.pe. " +
    "Las zonas seguras y albergues oficiales los define tu municipalidad: no hay una lista oficial abierta todavía.",
  // los datos se piden según lo que se ve (en render): load solo confirma que la capa está lista
  load: () => Promise.resolve({ porVista: true }),
  render(group, _datos, { map, avisar }) {
    const puntos = L.layerGroup();
    const puestos = new Map(); // clave -> marker ya en el mapa
    let claveAbrir = null; // punto que la tarjeta "A dónde acudir" pidió ver
    let turno = 0;

    let recienAbierto = null; // marcador cuyo popup se abrió por pedido: se reacomoda si el mapa se mueve
    const abrirSiToca = () => {
      const m = claveAbrir && puestos.get(claveAbrir);
      if (!m) return;
      claveAbrir = null;
      m.openPopup();
      recienAbierto = m;
    };

    const dibujar = async () => {
      const miTurno = ++turno;
      const zoom = map.getZoom();
      if (zoom < ZOOM_MIN) {
        if (puestos.size) {
          puntos.clearLayers();
          puestos.clear();
        }
        avisar({ texto: `Acércate al mapa (zoom ${ZOOM_MIN} o más) para ver los hospitales, comisarías y bomberos de esa zona.`, corto: "Acércate para ver los puntos." });
        return;
      }
      const b = map.getBounds().pad(MARGEN);
      const caja = cajaRedondeada({ oeste: b.getWest(), sur: b.getSouth(), este: b.getEast(), norte: b.getNorth() });
      let filas;
      try {
        filas = await getPuntosAcudirCaja(caja);
      } catch (e) {
        console.error("capa acudir", e);
        if (miTurno === turno) avisar("No se pudieron cargar los puntos de esta zona. Mueve un poco el mapa para volver a intentar.");
        return;
      }
      if (miTurno !== turno || !map.hasLayer(puntos)) return; // el mapa se movió otra vez o la capa se apagó
      const vistos = new Set();
      const n = {};
      let enCaja = 0;
      for (const p of filas) {
        if (p.lat == null || p.lon == null || !b.contains([p.lat, p.lon])) continue;
        enCaja++;
        if (!seDibuja(p, zoom)) continue;
        vistos.add(p.clave);
        n[p.tipo] = (n[p.tipo] ?? 0) + 1;
        if (puestos.has(p.clave)) continue;
        const m = L.marker([p.lat, p.lon], { icon: iconoAcudir(p.tipo), keyboard: true, zIndexOffset: 200 })
          .bindTooltip(escapeHtml(p.nombre), { className: "tip", direction: "top", offset: [0, -12] })
          // alto y relleno del autoPan según lo que dejan libre la hoja y la atribución (map/popups.js)
          .bindPopup(() => popupAcudir(p), opcionesPopup(map))
          .on("add", (e) => e.target.getElement()?.setAttribute("aria-label", `${TIPO_ACUDIR[p.tipo]?.label ?? "Punto"}: ${p.nombre}`));
        m.addTo(puntos);
        puestos.set(p.clave, m);
      }
      for (const [clave, m] of puestos) {
        if (vistos.has(clave)) continue;
        puntos.removeLayer(m);
        puestos.delete(clave);
      }
      avisar(resumen(n, zoom, enCaja));
      abrirSiToca();
    };

    // La tarjeta "A dónde acudir" (components/AcudirCercanos.jsx) avisa qué punto quiere ver. Lo
    // pide en el mismo clic en que mueve el mapa hasta el punto (setFocus → fitBounds recién en el
    // cuadro siguiente): si el popup se abriera ya, se acomodaría a la vista vieja y al moverse el
    // mapa quedaba con el título fuera de la pantalla. Se espera a que el mapa se asiente: si
    // empieza a moverse, lo abre dibujar() después del moveend; si en ESPERA_MOVIMIENTO_MS no se
    // movió (ya estaba encuadrado), se abre aquí.
    let esperaAbrir = 0;
    let moviendo = false;
    const alMover = () => {
      moviendo = true;
    };
    const alParar = () => {
      moviendo = false;
      // si el mapa igual se movió después de abrirlo (un encuadre que tardó en empezar), el popup
      // se vuelve a acomodar a la vista nueva (update: medidas y autoPan otra vez)
      if (recienAbierto?.isPopupOpen()) recienAbierto.getPopup().update();
      recienAbierto = null;
    };
    const pedido = (e) => {
      claveAbrir = e.detail?.clave ?? null;
      pedidoPendiente = null;
      clearTimeout(esperaAbrir);
      esperaAbrir = setTimeout(() => !moviendo && abrirSiToca(), ESPERA_MOVIMIENTO_MS);
    };
    puntos.on("add", () => {
      map.on("movestart", alMover);
      map.on("moveend", alParar);
      map.on("moveend", dibujar);
      window.addEventListener("simpac:acudir-ver", pedido);
      claveAbrir = pedidoPendiente; // el pedido que llegó mientras la capa se encendía
      pedidoPendiente = null;
      dibujar();
    });
    puntos.on("remove", () => {
      map.off("movestart", alMover);
      map.off("moveend", alParar);
      map.off("moveend", dibujar);
      clearTimeout(esperaAbrir);
      window.removeEventListener("simpac:acudir-ver", pedido);
      turno++;
      puntos.clearLayers(); // MapView no recarga la capa al reencenderla: sin esto se dibujarían encima otra vez
      puestos.clear();
    });
    puntos.addTo(group);
    return { texto: "Cargando los puntos de esta zona…", corto: "Cargando…" };
  },
};
