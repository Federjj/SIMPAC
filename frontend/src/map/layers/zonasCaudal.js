import L from "leaflet";
import { ShieldAlert } from "lucide-react";
import { getCaudales } from "@/lib/queries";
import { textoRio } from "@/lib/lenguaje";
import { NIVEL_HEX } from "../palette";

// Zona sombreada alrededor de cada río CRECIDO en alerta o emergencia (dato ANA). No es
// un polígono oficial de inundación: marca dónde mirar, no hasta dónde llega el agua.
// Un río muy bajo (vaciante) no se dibuja: no hay nada que se desborde.
const RADIO_M = 2500;

export default {
  id: "zona",
  label: "Zonas a vigilar (río crecido)",
  Icon: ShieldAlert,
  defaultVisible: true,
  refreshMs: 10 * 60_000,
  legend: [
    { color: NIVEL_HEX.alerta, label: "Río crecido en alerta", zona: true },
    { color: NIVEL_HEX.emergencia, label: "Río crecido en emergencia", zona: true },
  ],
  load: getCaudales,
  render(group, caudales) {
    for (const c of caudales) {
      if (c.lat == null || c.lon == null) continue;
      const t = textoRio(c); // se recalcula aquí: no se confía en filas viejas
      if (t.bajo || (t.estado !== "alerta" && t.estado !== "emergencia")) continue;
      const col = NIVEL_HEX[t.estado];
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
