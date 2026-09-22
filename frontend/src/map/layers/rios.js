import L from "leaflet";
import { Waves } from "lucide-react";
import { getCaudales } from "@/lib/queries";
import { lecturaRio, textoRio } from "@/lib/lenguaje";
import { RIO_HEX } from "../palette";
import { SVG, markerIcon, popupHtml } from "../markers";

const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });

export default {
  id: "rio",
  label: "Ríos",
  Icon: Waves,
  defaultVisible: true,
  refreshMs: 10 * 60_000, // la ingesta es horaria
  legend: [
    { color: RIO_HEX.normal, label: "Tranquilo" },
    { color: RIO_HEX.atento, label: "Cerca del nivel de alerta (criterio SIMPAC)" },
    { color: RIO_HEX.alerta, label: "Pasó el nivel de alerta" },
    { color: RIO_HEX.emergencia, label: "Pasó el nivel de emergencia" },
    { color: RIO_HEX.sd, label: "Sin nivel de alerta publicado" },
  ],
  load: getCaudales,
  render(group, caudales) {
    for (const c of caudales) {
      if (c.lat == null || c.lon == null) continue;
      const t = textoRio(c);
      const umbral = (etiqueta, v) => [
        `${t.bajo ? `${etiqueta} por nivel bajo` : etiqueta}`,
        v != null ? `${num(v)} ${c.unidad}` : null,
      ];
      L.marker([c.lat, c.lon], { icon: markerIcon(RIO_HEX[t.estado] ?? RIO_HEX.sd, SVG.wave) })
        .bindPopup(
          popupHtml({
            title: t.titulo,
            meta: [t.etiqueta, c.departamento],
            resumen: t.frase,
            filas: [
              umbral("Nivel de alerta", t.ua),
              umbral("Nivel de emergencia", t.ue),
              ["Medido", lecturaRio(c)],
            ],
            nota: t.accion,
          })
        )
        .addTo(group);
    }
  },
};
