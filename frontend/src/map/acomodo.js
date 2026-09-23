import L from "leaflet";
import { anchoRotulo, colocar } from "./colocar";
import { cajaDeAnillo, dentroDeAnillo } from "@/lib/geo";
import { tooltipJuntos } from "@/lib/avisoTexto";

// Enlace del acomodo (map/colocar.js) con Leaflet: junta las insignias de los avisos y los discos
// del pronóstico que están a la vista, decide qué se ve, qué se corre, qué se junta en "2 avisos",
// qué queda como punto y qué rótulo cabe, y lo aplica con clases y --dx/--dy sobre cada marcador.
// Los marcadores de las otras capas (ríos, estaciones, reportes, tu ubicación) cuentan como fijos:
// un disco encima pasa a punto y los rótulos los esquivan.
// Corre al mover o acercar el mapa y al entrar o salir una capa (una vez por cuadro). Con cientos
// de localidades, cada vuelta evita leer el DOM (las cajas de los paneles se guardan) y solo
// escribe en los marcadores que cambiaron.
//
// crearAcomodo(map) -> { capa(id) -> {registrar(marker, meta), limpiar()}, usuario({codigo, departamento}), recalcular(), destruir() }
//   meta de una insignia: {tipo:"insignia", prioridad, clave, fila, anillo, radioKm, mayor, chip, tooltip}
//   meta de un disco:     {tipo:"disco", prioridad, codigo, departamento, clase, rotulo (texto), zIndex}

// Escala por zoom: país (todo como puntos), región y local (íconos más grandes, con nombres).
export const escalaDeZoom = (z) => (z <= 6 ? "pais" : z <= 8 ? "region" : "local");

// Tamaño de las cajas por escala (igual que el CSS de index.css).
const TAM_INSIGNIA = { pais: 30, region: 40, local: 44 };
// ríos y estaciones (.mk) se achican con el mapa alejado (index.css)
const ESCALA_MK = { pais: 0.45, region: 0.62, local: 1 };
const TAM_DISCO = { pais: 10, region: 28, local: 32 };
const TAM_SECO = { pais: 7, region: 24, local: 28 };
const ALTO_CHIP = 18;
const ALTO_ROTULO = 20;
// una insignia de una parte chica (no la más grande del aviso) se oculta si su círculo mide menos de esto
const RADIO_MIN_PX = 14;
// lugares alternativos de una insignia tapada: 8 direcciones a 44 px, dentro de su zona
const PASO = 44;
const DIAG = Math.round(PASO * Math.SQRT1_2);
const DIRECCIONES = [
  [0, -PASO], [PASO, 0], [0, PASO], [-PASO, 0],
  [DIAG, -DIAG], [DIAG, DIAG], [-DIAG, DIAG], [-DIAG, -DIAG],
];
const Z_TUYA = 900;
const Z_PUNTO = -1000;
// lo que tapa el mapa (chips, paneles: data-tapa-mapa en App/StatusPanel/LayersPanel) y los botones de zoom
const TAPA_MAPA = "[data-tapa-mapa], .leaflet-control-zoom";

const metrosPorPixel = (lat, zoom) => (156543.03 * Math.cos((lat * Math.PI) / 180)) / 2 ** zoom;

export function crearAcomodo(map) {
  const capas = new Map(); // id de la capa -> { entradas: Set<{marker, meta}>, api }
  let usuario = null;
  let cuadro = 0;

  const recalcular = () => {
    if (cuadro) return;
    cuadro = requestAnimationFrame(() => {
      cuadro = 0;
      aplicar();
    });
  };
  const EVENTOS = "zoomend moveend layeradd layerremove";
  map.on(EVENTOS, recalcular);
  // si un panel o el mapa cambian de tamaño (p. ej. el panel se pliega), se vuelven a leer sus
  // cajas y se acomoda de nuevo
  let cajasUi = null; // { els, cajas } de la última lectura
  const observados = new WeakSet();
  const ro =
    typeof ResizeObserver === "function"
      ? new ResizeObserver(() => {
          cajasUi = null;
          recalcular();
        })
      : null;
  ro?.observe(map.getContainer());

  // Cajas de la interfaz sobre el mapa, en píxeles del mapa (con 6 px de aire). Leerlas obliga al
  // navegador a calcular en ese momento el diseño de toda la página (con cientos de marcadores
  // recién movidos es lo más caro de cada vuelta): se guardan hasta que cambie qué elementos hay
  // o el tamaño de alguno (ResizeObserver).
  function obstaculos() {
    const els = [...document.querySelectorAll(TAPA_MAPA)];
    if (ro && cajasUi && cajasUi.els.length === els.length && cajasUi.els.every((e, i) => e === els[i])) return cajasUi.cajas;
    const m = map.getContainer().getBoundingClientRect();
    const out = [];
    for (const el of els) {
      if (ro && !observados.has(el)) {
        observados.add(el);
        ro.observe(el);
      }
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || r.right < m.left || r.left > m.right || r.bottom < m.top || r.top > m.bottom) continue;
      out.push({ x: (r.left + r.right) / 2 - m.left, y: (r.top + r.bottom) / 2 - m.top, w: r.width + 12, h: r.height + 12 });
    }
    cajasUi = { els, cajas: out };
    return out;
  }
  const bajo = (x, y, obs) => obs.some((o) => Math.abs(x - o.x) < o.w / 2 && Math.abs(y - o.y) < o.h / 2);

  // Cajas de los marcadores de las otras capas a la vista, en píxeles del mapa, sin leer el DOM:
  // de su posición y del tamaño y el ancla de su ícono (o del radio de un círculo de radio fijo).
  function fijos(propios, tam) {
    const out = [];
    map.eachLayer((l) => {
      if (propios.has(l)) return;
      let w;
      let h;
      let p;
      if (l instanceof L.Marker) {
        const o = l.options.icon?.options ?? {};
        const s = L.point(o.iconSize ?? [12, 12]);
        if (!s.x || !s.y) return;
        const a = o.iconAnchor ? L.point(o.iconAnchor) : s.divideBy(2);
        p = map.latLngToContainerPoint(l.getLatLng()).subtract(a).add(s.divideBy(2));
        const k = /class="mk[\s"]/.test(o.html ?? "") ? ESCALA_MK[escalaDeZoom(map.getZoom())] : 1;
        [w, h] = [s.x * k, s.y * k];
      } else if (l instanceof L.CircleMarker && !(l instanceof L.Circle)) {
        p = map.latLngToContainerPoint(l.getLatLng());
        w = h = 2 * l.getRadius();
      } else return;
      if (p.x < -w || p.y < -h || p.x > tam.x + w || p.y > tam.y + h) return;
      out.push({ x: p.x, y: p.y, w, h });
    });
    return out;
  }

  function capa(id) {
    if (!capas.has(id)) {
      const entradas = new Set();
      const api = {
        registrar(marker, meta) {
          entradas.add({ marker, meta });
          recalcular();
        },
        limpiar() {
          entradas.clear();
        },
      };
      capas.set(id, { entradas, api });
    }
    return capas.get(id).api;
  }

  // Insignia que sigue a la vista: si su ancla quedó fuera de la pantalla (o bajo un panel) pero
  // su zona sigue a la vista, se muestra en el punto de la zona (fuera de los paneles) más cercano
  // a la parte de arriba al centro. false = no se ve (su zona tampoco está a la vista).
  function seguirVista({ marker, meta }, tam, vista, obs) {
    const ancla = meta.ancla0 ?? marker.getLatLng();
    const restaurar = () => {
      if (meta.ancla0) marker.setLatLng(meta.ancla0);
      meta.ancla0 = null;
    };
    const p = map.latLngToContainerPoint(ancla);
    // bajo un panel cuenta como fuera de la vista
    const adentro = p.x >= 0 && p.y >= 0 && p.x <= tam.x && p.y <= tam.y && !bajo(p.x, p.y, obs);
    let mejor = null;
    if (!adentro && meta.anillo) {
      const [o, s, e, n] = (meta.cajaAnillo ??= cajaDeAnillo(meta.anillo));
      const toca = o <= vista.getEast() && e >= vista.getWest() && s <= vista.getNorth() && n >= vista.getSouth();
      let dMejor = Infinity;
      // grilla de 6x6 dentro de la vista (con 15% de margen)
      for (let i = 0; toca && i < 6; i++) {
        for (let j = 0; j < 6; j++) {
          const x = tam.x * (0.15 + (0.7 * i) / 5);
          const y = tam.y * (0.15 + (0.7 * j) / 5);
          if (bajo(x, y, obs)) continue;
          const ll = map.containerPointToLatLng([x, y]);
          if (!dentroDeAnillo(ll.lng, ll.lat, meta.anillo)) continue;
          const d = (x - tam.x * 0.5) ** 2 + (y - tam.y * 0.35) ** 2;
          if (d < dMejor) {
            dMejor = d;
            mejor = ll;
          }
        }
      }
    }
    if (!mejor) {
      restaurar();
      return adentro;
    }
    meta.ancla0 = ancla;
    marker.setLatLng(mejor);
    return true;
  }

  const candidatos = (meta, p) =>
    meta.anillo
      ? DIRECCIONES.filter(([dx, dy]) => {
          const ll = map.containerPointToLatLng([p.x + dx, p.y + dy]);
          return dentroDeAnillo(ll.lng, ll.lat, meta.anillo);
        }).map(([dx, dy]) => ({ dx, dy }))
      : [];

  function pintar({ marker, meta }, r, tuya = false) {
    const el = marker.getElement();
    const raiz = el?.firstElementChild;
    if (!raiz) return;
    const oculto = r.estado === "oculto" || r.estado === "fusionado";
    meta.corrido = { dx: r.dx, dy: r.dy };
    // solo se escribe si cambió (o si Leaflet rehízo el ícono al volver a encender la capa):
    // cada escritura obliga a recalcular el estilo de ese marcador
    const clave = `${r.estado}|${r.dx}|${r.dy}|${r.rotulo}|${tuya}`;
    if (meta.pintado?.el === el && meta.pintado.clave === clave) return;
    meta.pintado = { el, clave };
    raiz.style.setProperty("--dx", `${r.dx}px`);
    raiz.style.setProperty("--dy", `${r.dy}px`);
    raiz.classList.toggle("es-oculto", oculto);
    raiz.classList.toggle("es-punto", r.estado === "punto");
    raiz.classList.toggle("con-rot", Boolean(r.rotulo));
    raiz.classList.toggle("rot-izq", r.rotulo === "izq");
    el.tabIndex = oculto ? -1 : 0; // lo que no se ve no se alcanza con el teclado
    if (oculto) marker.closeTooltip();
    if (meta.tipo === "disco") {
      raiz.classList.toggle("tuya", tuya);
      // tu localidad encima de todo; un punto, debajo de los marcadores de las otras capas (un río
      // no queda con un punto encima)
      const z = tuya ? Z_TUYA : r.estado === "punto" ? Z_PUNTO : meta.zIndex ?? 0;
      if (meta.z !== z) {
        meta.z = z;
        marker.setZIndexOffset(z);
      }
    }
  }

  // Insignia sobreviviente: el chip dice "N avisos" si junta 2 o más avisos distintos; si no, el suyo.
  function juntar({ marker, meta }, fusionados) {
    meta.juntos = fusionados;
    const claves = new Set([meta.clave, ...fusionados.map((m) => m.clave)]);
    const chip = claves.size >= 2 ? `${claves.size} avisos` : meta.chip ?? "";
    const tooltip = claves.size >= 2 ? tooltipJuntos(claves.size) : meta.tooltip;
    const el = marker.getElement();
    const span = el?.querySelector(".ins-chip");
    if (span && span.textContent !== chip) span.textContent = chip;
    if (tooltip && marker.getTooltip()?.getContent() !== tooltip) {
      marker.setTooltipContent(tooltip);
      el?.setAttribute("aria-label", tooltip);
    }
  }

  function aplicar() {
    if (!map._loaded) return;
    const zoom = map.getZoom();
    const escala = escalaDeZoom(zoom);
    const tam = map.getSize();
    const vista = map.getBounds();
    const holgura = vista.pad(0.1);
    const obs = obstaculos();
    const items = [];
    const porId = new Map();
    const ocultas = [];
    const propios = new Set();
    let n = 0;
    for (const { entradas } of capas.values()) {
      for (const e of entradas) {
        const { marker, meta } = e;
        propios.add(marker);
        if (!marker._map) continue;
        const id = `m${n++}`;
        if (meta.tipo === "insignia") {
          const ll0 = meta.ancla0 ?? marker.getLatLng();
          const chica = !meta.mayor && (meta.radioKm * 1000) / metrosPorPixel(ll0.lat, zoom) < RADIO_MIN_PX;
          if (chica || !seguirVista(e, tam, vista, obs)) {
            ocultas.push(e);
            continue;
          }
          const p = map.latLngToContainerPoint(marker.getLatLng());
          const t = TAM_INSIGNIA[escala];
          const chip = meta.chip ? ALTO_CHIP : 0;
          items.push({
            id, x: p.x, y: p.y + chip / 2, w: t, h: t + chip,
            prioridad: meta.prioridad, tipo: "insignia", clave: meta.clave, candidatos: candidatos(meta, p),
          });
        } else {
          const ll = marker.getLatLng();
          if (!holgura.contains(ll)) continue;
          const p = map.latLngToContainerPoint(ll);
          const tuya = Boolean(usuario?.codigo) && meta.codigo === usuario.codigo;
          const deTuZona = Boolean(usuario?.departamento) && meta.departamento === usuario.departamento;
          const conRotulo = tuya || escala === "local" || (escala === "region" && deTuZona);
          const t = (meta.clase === "seco" ? TAM_SECO : TAM_DISCO)[escala];
          items.push({
            id, x: p.x, y: p.y, w: t, h: t,
            prioridad: meta.prioridad + (deTuZona ? 1 : 0), // a igual clase, primero los de tu departamento
            tipo: tuya ? "usuario" : "disco",
            rotulo: conRotulo && meta.rotulo ? { w: anchoRotulo(meta.rotulo), h: ALTO_ROTULO } : null,
          });
        }
        porId.set(id, e);
      }
    }
    const res = colocar(items, { ancho: tam.x, obstaculos: obs, fijos: items.length ? fijos(propios, tam) : [] });
    for (const e of ocultas) pintar(e, { estado: "oculto", dx: 0, dy: 0, rotulo: null });
    for (const it of items) {
      const e = porId.get(it.id);
      const r = res.get(it.id);
      pintar(e, r, it.tipo === "usuario");
      if (it.tipo === "insignia" && r.estado === "visible") juntar(e, r.fusionados.map((f) => porId.get(f).meta));
    }
  }

  return {
    capa,
    usuario(u) {
      usuario = u;
      recalcular();
    },
    recalcular,
    destruir() {
      cancelAnimationFrame(cuadro);
      map.off(EVENTOS, recalcular);
      ro?.disconnect();
    },
  };
}
