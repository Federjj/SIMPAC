import L from "leaflet";
import { ShieldAlert } from "lucide-react";
import { getCaudales } from "@/lib/queries";
import { NIVEL_HEX } from "../palette";

// Zona sombreada alrededor de cada río en alerta o emergencia (dato ANA). No es
// un polígono oficial de inundación: marca dónde mirar, no hasta dónde llega el agua.
const RADIO_M = 2500;

export default {
  id: "zona",
  label: "Zonas de caudal alto",
  Icon: ShieldAlert,
  defaultVisible: true,
  refreshMs: 10 * 60_000,
  legend: [
    { color: NIVEL_HEX.alerta, label: "Río en alerta", zona: true },
    { color: NIVEL_HEX.emergencia, label: "Río en emergencia", zona: true },
  ],
  load: getCaudales,
  render(group, caudales) {
    for (const c of caudales) {
      if (c.lat == null || c.lon == null) continue;
      if (c.estado !== "alerta" && c.estado !== "emergencia") continue;
      const col = NIVEL_HEX[c.estado];
      L.circle([c.lat, c.lon], {
        radius: RADIO_M,
        color: col,
        weight: 1,
        fillColor: col,
        fillOpacity: 0.18,
        interactive: false, // el clic va al marcador del río
      }).addTo(group);
    }
  },
};
