import L from "leaflet";
import { TriangleAlert } from "lucide-react";
import { getReportesVigentes } from "@/lib/queries";
import { REPORT_TYPE, REPORT_TYPES } from "@/lib/reportTypes";
import { horaPeru } from "@/lib/tiempo";
import { SVG, markerIcon, popupHtml } from "../markers";

const ESTADO = { sin_confirmar: "Sin confirmar", confirmado: "Confirmado", descartado: "Descartado" };

// Reportes ciudadanos vigentes (tabla report). Un reporte descartado por la
// comunidad se sigue viendo, pero atenuado.
export default {
  id: "inc",
  grupo: "Comunidad",
  label: "Reportes ciudadanos",
  Icon: TriangleAlert,
  defaultVisible: true,
  refreshMs: 2 * 60_000,
  legend: REPORT_TYPES.map(({ color, label }) => ({ color, label, gota: true })),
  load: getReportesVigentes,
  render(group, reportes) {
    for (const r of reportes) {
      if (r.lat == null || r.lon == null) continue;
      const tipo = REPORT_TYPE[r.tipo] ?? REPORT_TYPE.otro;
      const subtipo = tipo.subtipos?.find((s) => s.id === r.subtipo)?.label;
      L.marker([r.lat, r.lon], {
        icon: markerIcon(tipo.color, SVG[tipo.id] ?? SVG.otro, { forma: "gota" }),
        opacity: r.estado === "descartado" ? 0.45 : 1,
      })
        .bindPopup(
          popupHtml({
            title: subtipo ? `${tipo.label} ${subtipo.toLowerCase()}` : tipo.label,
            meta: [ESTADO[r.estado], `reportado ${horaPeru(r.creado_en)}`],
            filas: [
              ["A favor", r.likes],
              ["En contra", r.dislikes],
              ["Vence", horaPeru(r.expira_en)],
            ],
            nota: r.descripcion,
          })
        )
        .addTo(group);
    }
  },
};
