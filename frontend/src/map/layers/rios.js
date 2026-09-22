import L from "leaflet";
import { Waves } from "lucide-react";
import { getCaudales } from "@/lib/queries";
import { NIVEL_HEX, SIN_DATO_HEX } from "../palette";
import { SVG, markerIcon, popupHtml } from "../markers";

const ESTADO = { normal: "Normal", alerta: "Alerta", emergencia: "Emergencia", "s.d.": "Sin umbral" };

export default {
  id: "rio",
  label: "Ríos",
  Icon: Waves,
  defaultVisible: true,
  refreshMs: 10 * 60_000, // la ingesta es horaria
  legend: [
    { color: NIVEL_HEX.normal, label: "Caudal normal" },
    { color: NIVEL_HEX.alerta, label: "Caudal en alerta" },
    { color: NIVEL_HEX.emergencia, label: "Caudal en emergencia" },
    { color: SIN_DATO_HEX, label: "Sin umbral o sin dato" },
  ],
  load: getCaudales,
  render(group, caudales) {
    for (const c of caudales) {
      if (c.lat == null || c.lon == null) continue;
      const valor = c.valor == null ? "sin dato" : `${c.valor} ${c.unidad ?? ""}`.trim();
      L.marker([c.lat, c.lon], { icon: markerIcon(NIVEL_HEX[c.estado] ?? SIN_DATO_HEX, SVG.wave) })
        .bindPopup(
          popupHtml({
            title: c.estacion,
            meta: [c.rio && `Río ${c.rio}`, c.departamento],
            filas: [
              ["Caudal", valor],
              ["Estado", ESTADO[c.estado] ?? c.estado],
              ["Tendencia", c.tendencia],
              ["Lectura", c.fecha && `${c.fecha} ${c.hora ?? ""}`.trim()],
            ],
          })
        )
        .addTo(group);
    }
  },
};
