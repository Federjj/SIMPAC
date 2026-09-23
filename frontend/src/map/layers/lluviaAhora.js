import L from "leaflet";
import { CloudRainWind } from "lucide-react";
import { getLluviaAhora } from "@/lib/queries";
import { intensidad, nombreEstacion, referenciaLluvia } from "@/lib/lenguaje";
import { horaPeru } from "@/lib/tiempo";
import { popupHtml } from "../markers";
import { NIVEL_HEX } from "../palette";
import { FUENTE_SENAMHI } from "../senamhi";

// Lluvia de la última hora en las estaciones automáticas de SENAMHI de todo el país (tarea
// 'lluvia_nacional' del worker). Solo se muestran lecturas de las últimas 3 h. El color es la
// intensidad (AEMET); el borde amarillo, que la estación pasó la referencia de SENAMHI en 1 h
// o en 6 h (la misma regla que las alertas de lluvia; no es un aviso oficial).
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
const NO_OFICIAL = "Es lo que midió la estación, no un aviso oficial. Fuente: SENAMHI.";

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
    {
      color: NIVEL_HEX.aviso,
      label: "Borde amarillo: pasó la referencia de SENAMHI de esa estación (1 h o 6 h); no es un aviso oficial",
      anillo: true,
    },
  ],
  fuente:
    "Lluvia de la última hora en estaciones automáticas de SENAMHI. Escala de intensidad orientativa (AEMET). " +
    "La referencia es la que SENAMHI usa para cada estación; no es un aviso oficial.",
  load: getLluviaAhora,
  render(group, estaciones) {
    // las que llueven al final, para que queden encima de los puntos grises, y encima de todas
    // las que pasaron la referencia
    const pasaAl = (e) => (referenciaLluvia(e).pasa ? 1 : 0);
    const orden = [...estaciones].sort((a, b) => pasaAl(a) - pasaAl(b) || (a.pp_1h ?? 0) - (b.pp_1h ?? 0));
    let conLluvia = 0;
    let sobreReferencia = 0;
    for (const e of orden) {
      if (e.lat == null || e.lon == null || e.pp_1h == null) continue;
      const i = intensidad(e.pp_1h);
      if (e.pp_1h > 0) conLluvia++;
      const { pasa1, pasa6, pasa } = referenciaLluvia(e);
      if (pasa) sobreReferencia++;
      L.circleMarker([e.lat, e.lon], {
        radius: pasa ? Math.max(RADIO[i], 7) : RADIO[i],
        color: pasa ? NIVEL_HEX.aviso : "#fff",
        weight: pasa ? 3 : 1,
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
              [
                "Referencia de SENAMHI",
                e.umbral_1h != null
                  ? `${num(e.umbral_1h)} mm en 1 h${e.umbral_6h != null ? ` · ${num(e.umbral_6h)} mm en 6 h` : ""}`
                  : null,
              ],
            ],
            nota: pasa1
              ? `Pasó la referencia de SENAMHI para esta estación en la última hora. ${NO_OFICIAL}`
              : pasa6
                ? `Pasó la referencia de SENAMHI para esta estación sumando las últimas 6 horas. ${NO_OFICIAL}`
                : "Fuente: SENAMHI.",
          })
        )
        .addTo(group);
    }
    const total = estaciones.length;
    if (!total) return "Sin lecturas de las últimas 3 horas.";
    const referencia = sobreReferencia ? ` En ${sobreReferencia} pasó la referencia de SENAMHI.` : "";
    return conLluvia
      ? `Llovió en ${conLluvia} de ${total} estaciones en su última hora medida.${referencia}`
      : `No llovió en ninguna de las ${total} estaciones en su última hora medida.${referencia}`;
  },
};
