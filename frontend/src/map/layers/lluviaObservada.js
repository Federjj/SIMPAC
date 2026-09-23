import { CloudRain } from "lucide-react";
import { getLatido } from "@/lib/queries";
import { MESES_CORTOS } from "@/lib/tiempo";
import { sldLluvia, wmsSenamhi } from "../senamhi";

// Lluvia observada de ayer y de los últimos 7 días en todo el Perú: la superficie que
// interpola SENAMHI con cientos de estaciones (no la calculamos nosotros). Se pinta con un
// estilo propio: transparente donde casi no llovió.
const CAPAS = {
  ayer: { capa: "monitoreo_meteorologico:prec_1", cortes: [1, 5, 15, 30], titulo: "en el último día procesado" },
  semana: { capa: "monitoreo_meteorologico:prec_1_ac07d", cortes: [5, 25, 75, 150], titulo: "en los últimos 7 días procesados" },
};

// "2026-09-21" -> "21 set" (sin "hoy" ni "ayer": el día procesado no siempre es ayer)
const dia = (iso) => {
  const [, m, d] = iso.split("-").map(Number);
  return `${d} ${MESES_CORTOS[m - 1]}`;
};

const leyenda = (opcion) => {
  const [c1, c2, c3, c4] = CAPAS[opcion].cortes;
  return [
    { color: "#95CEF4", label: `${c1} a ${c2} mm`, zona: true },
    { color: "#3BA5EB", label: `${c2} a ${c3} mm`, zona: true },
    { color: "#3B3BEB", label: `${c3} a ${c4} mm`, zona: true },
    { color: "#7B2FBE", label: `más de ${c4} mm`, zona: true },
  ];
};

export default {
  id: "lluviaObservada",
  grupo: "Lluvia",
  label: "Lluvia de ayer / de la semana",
  Icon: CloudRain,
  defaultVisible: false,
  refreshMs: 60 * 60_000, // SENAMHI procesa el día nuevo en la mañana
  opciones: {
    etiqueta: "Periodo",
    valores: [
      { valor: "ayer", etiqueta: "Ayer" },
      { valor: "semana", etiqueta: "Últimos 7 días" },
    ],
    defecto: "ayer",
  },
  legend: leyenda,
  fuente: "Lluvia medida por SENAMHI e interpolada entre sus estaciones.",
  // De qué días son las capas: el worker lo lee del visor de SENAMHI (latido 'lluvia_nacional').
  load: async () => (await getLatido().catch(() => [])).find((l) => l.servicio === "lluvia_nacional")?.resumen ?? null,
  render(group, resumen, { opcion, avisar }) {
    const { capa, cortes, titulo } = CAPAS[opcion] ?? CAPAS.ayer;
    const dias =
      opcion === "semana"
        ? resumen?.prec_1_ac07d_desde && resumen?.prec_1_ac07d
          ? `del ${dia(resumen.prec_1_ac07d_desde)} al ${dia(resumen.prec_1_ac07d)}`
          : titulo
        : resumen?.prec_1
          ? `el ${dia(resumen.prec_1)}`
          : titulo;
    // SENAMHI cuenta el día de lluvia de 7:00 a 7:00 del día siguiente
    const nota = `Cuánta lluvia cayó ${dias} (cada día va de 7:00 a 7:00), según SENAMHI.`;
    wmsSenamhi("monitoreo_meteorologico", capa, { sld_body: sldLluvia(capa, cortes) }, { avisar, nota }).addTo(group);
    return nota;
  },
};
