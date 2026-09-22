import L from "leaflet";
import { Droplets } from "lucide-react";
import { getMapaAnomalias } from "@/lib/queries";
import { ANOM_LEYENDA, anomColor } from "../palette";
import { popupHtml } from "../markers";

// Anomalía mensual de precipitación por estación (IDESEP/SENAMHI, tabla mapa).
export default {
  id: "anom",
  label: "Anomalías de lluvia",
  Icon: Droplets,
  defaultVisible: false,
  legend: ANOM_LEYENDA,
  load: getMapaAnomalias,
  render(group, mapa) {
    for (const f of mapa?.geojson?.features ?? []) {
      const coords = f.geometry?.coordinates;
      if (f.geometry?.type !== "Point" || !coords) continue;
      const [lon, lat] = coords;
      const p = f.properties ?? {};
      const a = p.ANOMALIA ?? 0;
      L.circleMarker([lat, lon], {
        radius: 7,
        color: "#fff",
        weight: 1.5,
        fillColor: anomColor(a),
        fillOpacity: 0.85,
      })
        .bindPopup(
          popupHtml({
            title: p.ESTACION || "Estación",
            meta: [p.DISTRITO, p.PROVINCIA, mapa.periodo],
            filas: [
              ["Anomalía de lluvia", `${a} %`],
              ["Precipitación", p.PREC != null ? `${p.PREC} mm` : null],
              ["Normal", p.NORMAL != null ? `${p.NORMAL} mm` : null],
            ],
          })
        )
        .addTo(group);
    }
  },
};
