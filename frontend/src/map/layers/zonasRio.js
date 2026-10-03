import L from "leaflet";
import { ShieldAlert } from "lucide-react";
import { getCaudales, getIncidentesRio, getRiosVigilados, getSenalesRio, getZonasRio } from "@/lib/queries";
import { textoRio } from "@/lib/lenguaje";
import { caudalDelRio, estadoZona, notaZonas } from "@/lib/zonaRio";
import { NOTA_SIMULACION, conSimulacion } from "@/lib/simulacion";
import { NIVEL_HEX, ZONA_HEX, ZONA_OSCURO } from "../palette";
import { escapeHtml, popupHtml } from "../markers";
import { iconoLugar } from "../marcadores";
import { opcionesPopup, popupZonaRio } from "../popups";
import { rotuloLinea } from "../rotuloLinea";

// Zonas que un río vigilado podría afectar si se desborda (primero el Mashcón; vista rio_zona_mapa):
//   - la franja rayada: estimación de SIMPAC con el relieve (terreno bajo junto al río; Copernicus);
//   - las manchas lisas: el mapa de inundaciones del estudio INDECI-PNUD 2005, pasado a coordenadas.
// Ninguna es un mapa oficial vigente: marcan dónde mirar, no hasta dónde llegará el agua. Se pintan
// del nivel de la zona (lib/zonaRio.js: ANA, avisos hidrológicos y de lluvia de SENAMHI, lluvia
// medida en la cuenca), que siempre es el de hoy (no sigue el selector de día); sin señales, de azul
// (sigue siendo una zona que podría inundarse). Todas llevan borde blanco y trazo oscuro: ámbar,
// naranja y rojo son también los rellenos de las áreas de los avisos, y sin borde se perdían encima.
// Desde zoom 13 se ven los polígonos (con el aura suave debajo en zoom 13, donde aún miden pocos
// píxeles) y desde zoom 14 el rótulo «zona que podría inundarse» junto al río; con el mapa más
// alejado, si hay señales, un "aura" del color del nivel a lo largo del río (index.css:
// [data-zoom-banda]). Con aviso hidrológico, o el río en alerta o emergencia, se marcan los centros
// poblados que SENAMHI nombra en sus avisos del río.
// Un río SIN mapa de zonas que crece hasta su alerta o emergencia (dato ANA) sigue con el círculo
// de 2,5 km alrededor de su estación. Un río muy bajo (vaciante) no enciende nada.
const RADIO_M = 2500;
const ACENTO = { atentos: 2, alerta: 3, emergencia: 4 };
const minuscula = (t) => t.charAt(0).toLowerCase() + t.slice(1);

// Estilo de cada zona por su tipo y subtipo (null: no se dibuja). bajo_1m queda dentro de bajo_2m.
// `borde`: lleva debajo un borde blanco (ver arriba). bajo_3m (la franja exterior, más incierta)
// va lisa con el tono oscuro del nivel, que se distingue sobre el área de un aviso del mismo color.
function estilo(z, nivel) {
  const tenue = nivel === "sin_senales";
  if (z.tipo === "estimada" && z.subtipo === "bajo_3m")
    return { stroke: false, fillColor: ZONA_OSCURO[nivel], fillOpacity: tenue ? 0.12 : 0.2 };
  if (z.tipo === "estimada" && z.subtipo === "bajo_2m")
    return {
      borde: true, color: ZONA_OSCURO[nivel], weight: 2.5, opacity: 1,
      fillColor: `url(#simpac-rayado-${nivel})`, fillOpacity: 1,
    };
  if (z.tipo === "estudio" && z.subtipo === "menor")
    return {
      borde: true, color: ZONA_OSCURO[nivel], weight: 2.5, opacity: 1, dashArray: "3 3",
      fillColor: ZONA_HEX[nivel], fillOpacity: tenue ? 0.22 : 0.3,
    };
  if (z.tipo === "estudio" && z.subtipo === "mayor")
    return { borde: true, color: ZONA_OSCURO[nivel], weight: 2.5, opacity: 1, fillColor: ZONA_HEX[nivel], fillOpacity: tenue ? 0.4 : 0.5 };
  return null;
}

export default {
  id: "zona",
  grupo: "Alertas y avisos",
  label: "Zonas que un río podría afectar",
  Icon: ShieldAlert,
  defaultVisible: true,
  refreshMs: 5 * 60_000, // señales de lluvia y avisos: cada 5 min
  // la forma dice de dónde sale la zona (muestras en gris) y el color, el nivel de hoy
  legend: [
    { forma: "rayado", color: "#475569", label: "Rayada: zona que podría inundarse si el río se desborda (estimación SIMPAC con el relieve)" },
    { zona: true, color: "#475569", label: "Lisa: zona inundable según el estudio INDECI-PNUD 2005" },
    { zona: true, color: ZONA_HEX.emergencia, label: "Rojo: el río pasó su nivel de emergencia (ANA) o hay aviso hidrológico rojo (SENAMHI)" },
    { zona: true, color: ZONA_HEX.alerta, label: "Naranja: pasó su nivel de alerta (ANA) o hay aviso hidrológico naranja" },
    { zona: true, color: ZONA_HEX.atentos, label: "Ámbar, atentos: señales de crecida o de lluvia fuerte en su cuenca" },
    { zona: true, color: ZONA_HEX.sin_senales, label: "Azul: zona que podría inundarse si el río se desborda, hoy sin señales de crecida" },
    { forma: "punto", color: "#0F172A", label: "Lugar que SENAMHI nombra como posible afectado (con aviso del río)" },
    { forma: "circulo", color: NIVEL_HEX.alerta, label: "Círculo: zona a vigilar alrededor de una estación en alerta (ríos sin mapa de zonas)" },
  ],
  fuente:
    "Zona baja: estimación de SIMPAC con el relieve (Copernicus GLO-30 © DLR e.V. 2010-2014 y © Airbus Defence and " +
    "Space GmbH 2014-2018, provisto bajo COPERNICUS por la Unión Europea y la ESA); no es un mapa oficial de " +
    "inundación. Zona inundable: INDECI-PNUD (2005), digitalizado por SIMPAC. Señales: ANA y SENAMHI. Trazo del " +
    "río: © colaboradores de OpenStreetMap (ODbL).",
  load: () =>
    Promise.all([getCaudales(), getRiosVigilados(), getZonasRio(), getSenalesRio(), getIncidentesRio()]).then(
      ([caudales, rios, zonas, senales, incidentes]) => ({ caudales, rios, zonas, senales, incidentes })
    ),
  render(group, { caudales, rios, zonas, senales, incidentes }, { map }) {
    const vigilados = rios ?? [];
    const estados = [];
    let simulada = false;

    for (const r0 of vigilados) {
      const sim = conSimulacion({
        rio: r0,
        caudal: caudalDelRio(r0, caudales),
        senal: senales?.find((s) => s.rio === r0.id) ?? null,
      });
      simulada ||= sim.activa;
      const { rio: r, caudal } = sim;
      const estado = estadoZona({ caudal, senal: sim.senal });
      const { nivel } = estado;
      estados.push({ rio: r, estado });
      const deRio = (zonas ?? []).filter((z) => z.rio === r.id && z.tipo !== "faja");
      const inc = (incidentes ?? []).filter((i) => i.rio === r.id);
      const op = opcionesPopup(map, { acento: ACENTO[nivel] });
      const popup = (zona) => () => popupZonaRio({ rio: r, zona, estado, caudal, incidentes: inc });

      // con el mapa alejado la franja mide pocos píxeles: si hay señales, el aura a lo largo del río
      // (antes que los polígonos: en zoom 13 va debajo de ellos)
      if (nivel !== "sin_senales" && r.cauce) {
        const principal = deRio.find((z) => z.subtipo === "bajo_2m") ?? deRio[0] ?? null;
        L.geoJSON(r.cauce, {
          pane: "zonaRio",
          style: { className: "zona-aura", color: ZONA_HEX[nivel], opacity: 0.55, weight: 20 },
        })
          .bindPopup(popup(principal), op)
          .addTo(group);
      }

      for (const z of deRio) {
        const { borde, ...s } = estilo(z, nivel) ?? {};
        if (!s.fillColor) continue;
        // borde blanco debajo: se lee también sobre el área de un aviso del mismo color
        if (borde)
          L.geoJSON(z.geojson, {
            pane: "zonaRio",
            interactive: false,
            style: { className: "zona-pol", color: "#fff", weight: 5.5, opacity: 0.95, fill: false },
          }).addTo(group);
        L.geoJSON(z.geojson, { pane: "zonaRio", style: { className: "zona-pol", ...s } })
          .bindPopup(popup(z), op)
          .addTo(group);
      }

      // «zona que podría inundarse» escrito junto al río, del lado de abajo (el nombre del río va
      // arriba), desde zoom 14: dice qué es la franja sin abrir la leyenda
      if (deRio.length && r.guia_rotulo?.type === "LineString") {
        const guia = r.guia_rotulo.coordinates.map(([lon, lat]) => [lat, lon]);
        const c = caudal?.lat != null ? [[caudal.lat, caudal.lon]] : [];
        rotuloLinea(map, guia, "zona que podría inundarse", {
          pane: "rioCauce", dy: 23, clase: `zona-nombre n-${nivel}`, repetir: 1, evitar: c,
        }).addTo(group);
      }

      // centros poblados que SENAMHI nombra en sus avisos del río (el punto marca el caserío)
      if (estado.avisoHidro || nivel === "alerta" || nivel === "emergencia") {
        for (const l of r.lugares_aviso ?? []) {
          if (!l.mapa || l.lat == null || l.lon == null) continue;
          L.marker([l.lat, l.lon], { icon: iconoLugar(l.nombre), keyboard: true })
            .bindTooltip(escapeHtml(l.nombre), { className: "tip", direction: "top", offset: [0, -6] })
            .bindPopup(
              popupHtml({
                title: l.nombre,
                resumen: `SENAMHI lo nombra entre las «potenciales áreas de afectación» de sus avisos del ${minuscula(r.nombre)}.`,
                nota: "Punto del centro poblado (INEI/IGN/MINEDU): marca el caserío, no la zona afectada.",
              })
            )
            .addTo(group);
        }
      }
    }

    // ríos sin mapa de zonas: el círculo alrededor de la estación crecida en alerta o emergencia
    // (no se toca: el clic va al disco del río o al aviso de abajo; la leyenda lo explica)
    for (const c of caudales) {
      if (c.lat == null || c.lon == null) continue;
      if (vigilados.some((r) => caudalDelRio(r, [c]))) continue;
      const t = textoRio(c); // se recalcula aquí: no se confía en filas viejas
      if (t.bajo || (t.estado !== "alerta" && t.estado !== "emergencia")) continue;
      const col = NIVEL_HEX[t.estado];
      L.circle([c.lat, c.lon], {
        radius: RADIO_M,
        color: col,
        weight: 1,
        fillColor: col,
        fillOpacity: 0.18,
        interactive: false,
      }).addTo(group);
    }

    const nota = rios == null || zonas == null ? "Las zonas del río Mashcón aún no están cargadas." : notaZonas(estados);
    return simulada ? `${NOTA_SIMULACION} ${nota}` : nota;
  },
};
