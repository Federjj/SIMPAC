import L from "leaflet";
import { Megaphone } from "lucide-react";
import { getAvisosVigentes } from "@/lib/queries";
import { fechaPeru } from "@/lib/tiempo";
import { dentroDe } from "@/lib/geo";
import { fechaDeOpcion } from "@/lib/pronostico";
import { claveAviso, glifoAviso, temaAviso, tooltipAviso } from "@/lib/avisoTexto";
import { iconoInsignia } from "../marcadores";
import { opcionesPopup, popupAvisos } from "../popups";
import { AVISO_ARO } from "../palette";
import { FUENTE_SENAMHI } from "../senamhi";

// Avisos oficiales de SENAMHI como áreas sombreadas: los meteorológicos (lluvia, heladas,
// viento...) y el de lluvia acumulada en 24 h. Los trae el worker (tarea 'avisos') a la tabla
// aviso_senamhi; los polígonos van simplificados, así que se rotulan como "basado en el
// aviso de SENAMHI" y enlazan al aviso original (lo piden sus términos de uso).
//
// El relleno va en un pane por nivel (aviso2, aviso3, aviso4) con la transparencia en el pane y
// no en cada área: dos avisos amarillos que se superponen no se ven naranja. Encima, por cada
// parte grande de cada aviso, una insignia (disco blanco con aro del color del nivel y el glifo
// del fenómeno) que acomoda map/acomodo.js; sin la migración de íconos (anclas) no hay insignias.
const NIVELES = {
  2: { color: "#EBEB3B", nombre: "amarillo", label: "Amarillo (nivel 2 de 4)" },
  3: { color: "#F58E27", nombre: "naranja", label: "Naranja (nivel 3 de 4)" },
  4: { color: "#DB0404", nombre: "rojo", label: "Rojo (nivel 4 de 4, el más grave)" },
};

// Selector de día compartido con el pronóstico (vinculo "dia": elegir uno cambia los dos).
export const OPCIONES_DIA = {
  etiqueta: "Día",
  valores: [
    { valor: "ahora", etiqueta: "Hoy" },
    { valor: "manana", etiqueta: "Mañana" },
    { valor: "pasado", etiqueta: "Pasado mañana" },
  ],
  defecto: "ahora",
  vinculo: "dia",
};
const PARA = { ahora: "hoy", manana: "mañana", pasado: "pasado mañana" };

// Un aviso de varios días trae un mapa por día: se muestran los que rigen en algún momento del
// día elegido (en hora de Perú) desde ahora. "Hoy" incluye uno que empieza más tarde hoy.
function ventana(opcion, ahora = Date.now()) {
  const inicio = Date.parse(`${fechaDeOpcion(opcion, ahora)}T00:00:00-05:00`);
  return { desde: Math.max(inicio, ahora), hasta: inicio + 86_400_000 };
}

const TEMAS = { lluvia: "de lluvia", calor: "de calor", frio: "de frío", viento: "de viento", otro: "de otro tipo" };

// Qué insignia gana un lugar: el nivel más alto; en el mismo nivel, la del aviso meteorológico
// antes que la de 24 h y la parte más grande primero.
const BASE_PRIORIDAD = { 4: 900, 3: 850, 2: 800 };
const prioridad = (a, ancla) =>
  BASE_PRIORIDAD[a.nivel] + (a.tipo === "lluvia24h" ? 0 : 25) + Math.min(24, Math.log10(1 + (ancla.km2 ?? 0)) * 4);

// Borde exterior de la parte `parte` (desde 1) del MultiPolygon, en el mismo orden que las anclas.
function anilloDe(g, parte) {
  if (g?.type === "MultiPolygon") return g.coordinates[parte - 1]?.[0] ?? null;
  if (g?.type === "Polygon" && parte === 1) return g.coordinates[0];
  return null;
}

// Uno por aviso (el de nivel más alto), del más alto al más bajo; en el mismo nivel, primero la
// lluvia (como en la maqueta) y el meteorológico (que trae más detalle) antes que el de 24 h.
const es24h = (a) => (a.tipo === "lluvia24h" ? 1 : 0);
const noEsLluvia = (a) => (temaAviso(a) === "lluvia" ? 0 : 1);
function unoPorAviso(filas) {
  const porClave = new Map();
  for (const a of filas) {
    const k = claveAviso(a);
    if (!porClave.has(k) || porClave.get(k).nivel < a.nivel) porClave.set(k, a);
  }
  return [...porClave.values()].sort((x, y) => y.nivel - x.nivel || noEsLluvia(x) - noEsLluvia(y) || es24h(x) - es24h(y));
}

export default {
  id: "avisos",
  grupo: "Alertas y avisos",
  label: "Avisos de SENAMHI (lluvia, calor, frío, viento)",
  Icon: Megaphone,
  insignia: "Oficial",
  defaultVisible: true,
  refreshMs: 15 * 60_000,
  opciones: OPCIONES_DIA,
  legend: [
    ...Object.values(NIVELES).map(({ color, label }) => ({ color, label, zona: true })),
    { forma: "insignia", glifo: "gota", color: AVISO_ARO[2], label: "Lluvia: puede llover en algún momento en la zona" },
    { forma: "insignia", glifo: "gota_rayo", color: AVISO_ARO[2], label: "Lluvia con rayos en toda la zona (habitual en sierra y selva)" },
    { forma: "insignia", glifo: "copo", color: AVISO_ARO[2], label: "Nevada en las partes altas" },
    { forma: "insignia", glifo: "termometro", color: AVISO_ARO[2], label: "Calor o frío" },
    { forma: "insignia", glifo: "viento", color: AVISO_ARO[2], label: "Viento" },
  ],
  fuente:
    "Áreas basadas en los avisos oficiales de SENAMHI (simplificadas). El ícono marca la zona del aviso, no el lugar " +
    "exacto donde lloverá; si solo ves la gota, abre el aviso: puede mencionar rayos para una parte.",
  load: getAvisosVigentes,
  render(group, avisos, { opcion, map, acomodo }) {
    const hoy = fechaPeru();
    const { desde, hasta } = ventana(opcion);
    const lista = avisos.filter(
      (a) => a.geojson && NIVELES[a.nivel] && Date.parse(a.inicio) < hasta && Date.parse(a.fin) > desde
    );
    // cuántos días (mapas) tiene cada aviso, para "(día 1 de 2)"
    const mapas = new Map();
    for (const a of avisos) mapas.set(claveAviso(a), Math.max(mapas.get(claveAviso(a)) ?? 0, a.mapa ?? 1));
    const ctx = { hoy, mapasDe: (a) => mapas.get(claveAviso(a)) ?? 1 };
    const abrir = (latlng, filas, offset) =>
      L.popup({ ...opcionesPopup(map, { acento: filas[0].nivel }), ...(offset ? { offset } : {}) })
        .setLatLng(latlng)
        .setContent(popupAvisos(filas, ctx))
        .openOn(map);

    for (const a of lista) {
      const n = NIVELES[a.nivel];
      L.geoJSON(a.geojson, {
        pane: `aviso${a.nivel}`,
        attribution: FUENTE_SENAMHI,
        style: { stroke: false, fillColor: n.color, fillOpacity: 1 },
      })
        // en el punto tocado: todos los avisos a la vista que lo cubren
        .on("click", (e) => {
          const aqui = unoPorAviso(lista.filter((x) => dentroDe(e.latlng.lng, e.latlng.lat, x.geojson)));
          abrir(e.latlng, aqui.length ? aqui : [a]);
        })
        .addTo(group);
      L.geoJSON(a.geojson, { pane: "avisoBorde", interactive: false, style: { color: n.color, weight: 1.2, fill: false } }).addTo(group);
    }

    for (const a of lista) {
      const glifo = glifoAviso(a);
      if (!glifo || !Array.isArray(a.anclas)) continue;
      const tooltip = tooltipAviso(a, { hoy });
      const chip = a.tipo === "lluvia24h" ? "24 h" : "";
      for (const ancla of a.anclas) {
        if (ancla?.lat == null || ancla?.lon == null) continue;
        const meta = {
          tipo: "insignia",
          prioridad: prioridad(a, ancla),
          clave: claveAviso(a),
          fila: a,
          anillo: anilloDe(a.geojson, ancla.parte),
          radioKm: ancla.radio_km ?? 0,
          mayor: Boolean(ancla.mayor),
          chip,
          tooltip,
          juntos: [],
        };
        // aria-label y no title: el title del navegador se encimaría con el tooltip
        const m = L.marker([ancla.lat, ancla.lon], {
          icon: iconoInsignia({ glifo, nivel: a.nivel, chip }),
          keyboard: true,
          zIndexOffset: 800 + a.nivel * 10,
        })
          .bindTooltip(tooltip, { className: "tip", direction: "top", offset: [0, -26] })
          .on("add", (e) => e.target.getElement()?.setAttribute("aria-label", e.target.getTooltip()?.getContent() ?? tooltip))
          .on("click", (e) => {
            // el popup sale sobre la insignia, también si el acomodo la corrió
            const { dx = 0, dy = 0 } = meta.corrido ?? {};
            const p = map.latLngToContainerPoint(e.target.getLatLng()).add([dx, dy]);
            const otros = unoPorAviso(meta.juntos.map((j) => j.fila)).filter((f) => claveAviso(f) !== meta.clave);
            abrir(map.containerPointToLatLng(p), [a, ...otros], [0, -20]);
          })
          .addTo(group);
        acomodo?.registrar(m, meta);
      }
    }

    if (!lista.length) return `No hay avisos de SENAMHI para ${PARA[opcion] ?? "hoy"}.`;
    // por tema: el rojo de la costa puede ser de temperatura y no de lluvia
    const partes = Object.entries(TEMAS).flatMap(([clave, texto]) => {
      const deTema = lista.filter((a) => temaAviso(a) === clave);
      if (!deTema.length) return [];
      const n = new Set(deTema.map(claveAviso)).size;
      const peor = NIVELES[Math.max(...deTema.map((a) => a.nivel))].nombre;
      return [`${n} ${texto} (el más alto, ${peor})`];
    });
    const temas = partes.length > 1 ? `${partes.slice(0, -1).join(", ")} y ${partes[partes.length - 1]}` : partes[0];
    return `Avisos para ${PARA[opcion] ?? "hoy"}: ${temas}. Toca un área o un ícono para ver de qué trata.`;
  },
};
