import L from "leaflet";
import { Radio } from "lucide-react";
import { getEstaciones } from "@/lib/queries";
import { TRANSMISION, nombreEstacion } from "@/lib/lenguaje";
import { ESTACION_HEX } from "../palette";
import { SVG, markerIcon, popupHtml } from "../markers";

export default {
  id: "est",
  label: "Estaciones SENAMHI",
  Icon: Radio,
  defaultVisible: false,
  legend: [
    { color: ESTACION_HEX.M, label: "De lluvia y clima" },
    { color: ESTACION_HEX.H, label: "De río" },
  ],
  load: getEstaciones,
  render(group, estaciones) {
    for (const e of estaciones) {
      if (e.lat == null || e.lon == null) continue;
      const hid = e.tipo === "H";
      L.marker([e.lat, e.lon], { icon: markerIcon(hid ? ESTACION_HEX.H : ESTACION_HEX.M, SVG.station) })
        .bindPopup(
          popupHtml({
            title: nombreEstacion(e.nombre),
            meta: [hid ? "Estación de río" : "Estación de lluvia y clima", e.departamento],
            filas: [["Transmisión", TRANSMISION[e.estado] ?? e.estado]],
            nota: "Red de estaciones de SENAMHI.",
          })
        )
        .addTo(group);
    }
  },
};
