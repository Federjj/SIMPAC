import L from "leaflet";
import { Radio } from "lucide-react";
import { getEstaciones } from "@/lib/queries";
import { ESTACION_HEX } from "../palette";
import { SVG, markerIcon, popupHtml } from "../markers";

export default {
  id: "est",
  label: "Estaciones",
  Icon: Radio,
  defaultVisible: false,
  legend: [
    { color: ESTACION_HEX.M, label: "Meteorológica" },
    { color: ESTACION_HEX.H, label: "Hidrológica" },
  ],
  load: getEstaciones,
  render(group, estaciones) {
    for (const e of estaciones) {
      if (e.lat == null || e.lon == null) continue;
      const hid = e.tipo === "H";
      L.marker([e.lat, e.lon], { icon: markerIcon(hid ? ESTACION_HEX.H : ESTACION_HEX.M, SVG.station) })
        .bindPopup(
          popupHtml({
            title: e.nombre,
            meta: [hid ? "Estación hidrológica" : "Estación meteorológica", e.departamento],
            filas: [["Transmisión", e.estado]],
          })
        )
        .addTo(group);
    }
  },
};
