import L from "leaflet";
import { Droplets } from "lucide-react";
import { getMapaAnomalias } from "@/lib/queries";
import { CLASES_ANOMALIA, nombreEstacion, textoAnomalia } from "@/lib/lenguaje";
import { popupHtml } from "../markers";

const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });

// Lluvia del mes por estación frente a lo normal (SENAMHI/IDESEP, tabla mapa). Se usan
// las clases oficiales de SENAMHI (campo PORCENTAJE) traducidas a palabras.
export default {
  id: "anom",
  label: "Lluvia del mes frente a lo normal",
  Icon: Droplets,
  defaultVisible: false,
  legend: CLASES_ANOMALIA.map(({ color, texto }) => ({ color, label: texto })),
  load: getMapaAnomalias,
  render(group, mapa) {
    for (const f of mapa?.geojson?.features ?? []) {
      const coords = f.geometry?.coordinates;
      if (f.geometry?.type !== "Point" || !coords) continue;
      const [lon, lat] = coords;
      const p = f.properties ?? {};
      const t = textoAnomalia(p, mapa.periodo);
      L.circleMarker([lat, lon], {
        radius: 7,
        color: "#fff",
        weight: 1.5,
        fillColor: t.clase.color,
        fillOpacity: 0.9,
      })
        .bindPopup(
          popupHtml({
            title: p.ESTACION ? nombreEstacion(p.ESTACION) : "Estación",
            meta: [p.DISTRITO, p.PROVINCIA],
            resumen: t.frase,
            filas: [
              ["Cayeron", p.PREC != null ? `${num(p.PREC)} mm` : null],
              ["Lo normal para el mes", p.NORMAL != null ? `${num(p.NORMAL)} mm` : null],
              ["Diferencia", p.ANOMALIA != null ? `${num(p.ANOMALIA)} %` : null],
            ],
            nota: "Fuente: SENAMHI (IDESEP).",
          })
        )
        .addTo(group);
    }
  },
};
