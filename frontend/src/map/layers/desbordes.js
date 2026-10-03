import L from "leaflet";
import { History } from "lucide-react";
import { getIncidentesRio, getRiosVigilados } from "@/lib/queries";
import { agruparIncidentes, anioCorto } from "@/lib/zonaRio";
import { escapeHtml } from "../markers";
import { iconoIncidente } from "../marcadores";
import { opcionesPopup, popupIncidentes } from "../popups";

// Desbordes y daños pasados de los ríos vigilados (tabla rio_incidente, primero el Mashcón): solo
// los que nombran al río en su fuente (ANA, INDECI, SENAMHI, municipio, prensa, tesis), cada uno
// con su enlace. Un rombo pizarra con el año ("×2" si junta más de uno): con cada zoom se juntan
// los que en pantalla quedarían encimados (a menos de RADIO_PX del más nuevo del grupo) y el popup
// los lista todos. El acomodo (map/acomodo.js) corre el rombo que quedaría bajo el disco de un río,
// una insignia u otro rombo, con una línea fina hasta su punto. Los que solo tienen el distrito y
// las crecidas medidas en la estación no van en el mapa (las crecidas se citan en el popup de la
// zona). Con el mapa alejado (zoom 11 o menos) no se ven.
const RADIO_PX = 26; // un rombo mide 24 px
const minuscula = (t) => t.charAt(0).toLowerCase() + t.slice(1);
const metrosPorPixel = (lat, zoom) => (156543.03 * Math.cos((lat * Math.PI) / 180)) / 2 ** zoom;
const anio = (i) => Number(String(i.fecha ?? i.fecha_texto ?? "").match(/(\d{4})/)?.[1]) || null;

// "10 incidentes documentados del río Mashcón con lugar (2012–2025). ... Otro (1974) solo tiene el distrito."
function nota(incidentes, rios) {
  const danos = incidentes.filter((i) => i.tipo !== "crecida");
  const conLugar = danos.filter((i) => i.lat != null);
  const sinLugar = danos.filter((i) => i.lat == null);
  if (!conLugar.length) return "No hay desbordes documentados con lugar para los ríos vigilados.";
  const ids = new Set(danos.map((i) => i.rio));
  const deQuien = ids.size === 1 ? `del ${minuscula(rios.find((r) => ids.has(r.id))?.nombre ?? "río")}` : "de los ríos vigilados";
  const anios = conLugar.map(anio).filter(Boolean);
  const rango = anios.length ? ` (${Math.min(...anios)}–${Math.max(...anios)})` : "";
  const otros = sinLugar.map(anio).filter(Boolean).join(", ");
  const resto = !sinLugar.length
    ? ""
    : sinLugar.length === 1
      ? ` Otro${otros ? ` (${otros})` : ""} solo tiene el distrito.`
      : ` Otros ${sinLugar.length}${otros ? ` (${otros})` : ""} solo tienen el distrito.`;
  return (
    `${conLugar.length} ${conLugar.length === 1 ? "incidente documentado" : "incidentes documentados"} ${deQuien} con lugar${rango}. ` +
    `La ubicación es aproximada: toca un rombo para ver la fuente.${resto}`
  );
}

export default {
  id: "desbordes",
  grupo: "Ríos y estaciones",
  label: "Desbordes y daños pasados",
  Icon: History,
  defaultVisible: true,
  legend: [{ forma: "rombo", color: "#334155", label: "Desborde, erosión o puente caído documentado (con su año)" }],
  fuente:
    "Solo incidentes que nombran al río Mashcón en su fuente: ANA, INDECI, SENAMHI, Municipalidad Provincial de " +
    "Cajamarca, Red Integrada de Salud Cajamarca, DesInventar, RPP, SOLTV y tesis UNC. Cada rombo cita la suya.",
  load: () =>
    Promise.all([getIncidentesRio(), getRiosVigilados()]).then(([incidentes, rios]) => ({ incidentes, rios: rios ?? [] })),
  render(group, { incidentes, rios }, { map, acomodo }) {
    if (incidentes == null) return "Los desbordes del río Mashcón aún no están cargados.";
    const danos = incidentes.filter((i) => i.tipo !== "crecida");
    const conLugar = danos.filter((i) => i.lat != null && i.lon != null);
    const lat0 = conLugar.length ? conLugar.reduce((s, i) => s + i.lat, 0) / conLugar.length : 0;
    // los rombos se rehacen al cambiar el zoom (mientras la capa esté en el mapa)
    const rombos = L.layerGroup();
    let zoomHecho = null;
    const dibujar = () => {
      const zoom = map.getZoom();
      if (zoom === zoomHecho) return;
      zoomHecho = zoom;
      rombos.clearLayers();
      acomodo?.limpiar();
      for (const g of agruparIncidentes(conLugar, RADIO_PX * metrosPorPixel(lat0, zoom))) {
        const [i] = g.incidentes; // el más nuevo
        const n = g.incidentes.length;
        const rio = rios.find((r) => r.id === i.rio) ?? null;
        const tooltip = `${i.titulo} (${i.fecha_texto})${n > 1 ? ` y ${n - 1} más` : ""}`;
        // debajo de los discos de los ríos y del pronóstico (lo de hoy va encima de lo pasado)
        const m = L.marker([g.lat, g.lon], { icon: iconoIncidente({ anio: anioCorto(i), n }), keyboard: true, zIndexOffset: -500 })
          .bindTooltip(escapeHtml(tooltip), { className: "tip", direction: "top", offset: [0, -14] })
          .bindPopup(() => popupIncidentes(g.incidentes, rio), opcionesPopup(map))
          .on("add", (e) => e.target.getElement()?.setAttribute("aria-label", tooltip))
          .addTo(rombos);
        acomodo?.registrar(m, { tipo: "rombo", prioridad: 100 + n });
      }
    };
    rombos.on("add", () => {
      map.on("zoomend", dibujar);
      zoomHecho = null;
      dibujar();
    });
    rombos.on("remove", () => map.off("zoomend", dibujar));
    rombos.addTo(group);
    return nota(incidentes, rios);
  },
};
