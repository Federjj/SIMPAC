import L from "leaflet";
import { CloudRainWind } from "lucide-react";
import { getLluviaAhora } from "@/lib/queries";
import { intensidad, nombreEstacion } from "@/lib/lenguaje";
import { horaPeru } from "@/lib/tiempo";
import { popupHtml } from "../markers";
import { FUENTE_SENAMHI } from "../senamhi";

// Lluvia de la última hora en las estaciones automáticas de SENAMHI de todo el país (tarea
// 'lluvia_nacional' del worker). Solo se muestran lecturas de las últimas 3 h.
const COLORES = {
  "sin lluvia": "#9CA3AF",
  ligera: "#95CEF4",
  moderada: "#3BA5EB",
  fuerte: "#3B3BEB",
  "muy fuerte": "#7B2FBE",
  torrencial: "#DB0404",
};
const RADIO = { "sin lluvia": 3, ligera: 6, moderada: 8, fuerte: 10, "muy fuerte": 12, torrencial: 13 };
const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 1 });

export default {
  id: "lluviaAhora",
  grupo: "Lluvia",
  label: "Lluvia de la última hora (estaciones)",
  Icon: CloudRainWind,
  defaultVisible: false,
  refreshMs: 10 * 60_000,
  legend: [
    { color: COLORES["sin lluvia"], label: "No llovió en la última hora" },
    { color: COLORES.ligera, label: "Lluvia ligera (hasta 2 mm)" },
    { color: COLORES.moderada, label: "Moderada (2 a 15 mm)" },
    { color: COLORES.fuerte, label: "Fuerte (15 a 30 mm)" },
    { color: COLORES["muy fuerte"], label: "Muy fuerte (30 a 60 mm)" },
    { color: COLORES.torrencial, label: "Torrencial (más de 60 mm)" },
  ],
  fuente: "Lluvia de la última hora en estaciones automáticas de SENAMHI. Escala de intensidad orientativa (AEMET).",
  load: getLluviaAhora,
  render(group, estaciones) {
    // las que llueven al final, para que queden encima de los puntos grises
    const orden = [...estaciones].sort((a, b) => (a.pp_1h ?? 0) - (b.pp_1h ?? 0));
    let conLluvia = 0;
    for (const e of orden) {
      if (e.lat == null || e.lon == null || e.pp_1h == null) continue;
      const i = intensidad(e.pp_1h);
      if (e.pp_1h > 0) conLluvia++;
      const pasa = e.umbral_1h != null && e.pp_1h > e.umbral_1h;
      L.circleMarker([e.lat, e.lon], {
        radius: RADIO[i],
        color: pasa ? "#DB0404" : "#fff",
        weight: pasa ? 2.5 : 1,
        fillColor: COLORES[i],
        fillOpacity: e.pp_1h > 0 ? 0.9 : 0.5,
        attribution: FUENTE_SENAMHI,
      })
        .bindPopup(
          popupHtml({
            title: nombreEstacion(e.nombre),
            meta: [e.distrito, e.provincia, e.departamento],
            resumen:
              e.pp_1h > 0
                ? `En la hora que terminó a las ${horaPeru(e.medido_en)} llovió ${num(e.pp_1h)} mm (lluvia ${i}).`
                : `No llovió en la hora que terminó a las ${horaPeru(e.medido_en)}.`,
            filas: [
              ["Últimas 6 h", e.pp_6h != null ? `${num(e.pp_6h)} mm` : null],
              ["Referencia de SENAMHI", e.umbral_1h != null ? `${num(e.umbral_1h)} mm en 1 h` : null],
            ],
            nota: pasa
              ? "Pasó la referencia de lluvia de SENAMHI para esta estación. Fuente: SENAMHI."
              : "Fuente: SENAMHI.",
          })
        )
        .addTo(group);
    }
    const total = estaciones.length;
    if (!total) return "Sin lecturas de las últimas 3 horas.";
    return conLluvia
      ? `Llovió en ${conLluvia} de ${total} estaciones en su última hora medida.`
      : `No llovió en ninguna de las ${total} estaciones en su última hora medida.`;
  },
};
