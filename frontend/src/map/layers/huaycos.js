import { Mountain } from "lucide-react";
import { sldNiveles, wmsSenamhi } from "../senamhi";

// SILVIA de SENAMHI: pronóstico diario, por microcuenca, de posible activación de
// quebradas (huaycos: flujos de agua y lodo rápidos por lluvias intensas). Clave para la
// sierra de Cajamarca. Niveles de SENAMHI: 2 moderado, 3 fuerte, 4 extremo.
const CAPA = "silvia:cuencas_nivel_12_prono1_silvia";
const COLORES = { 2: "#EBEB3B", 3: "#F58E27", 4: "#DB0404" };

export default {
  id: "huaycos",
  grupo: "Alertas y avisos",
  label: "Quebradas que podrían activarse (huaycos)",
  Icon: Mountain,
  defaultVisible: false,
  refreshMs: 60 * 60_000, // pronóstico diario: pasada la medianoche cambia
  legend: [
    { color: COLORES[2], label: "Posible huayco moderado (nivel 2)", zona: true },
    { color: COLORES[3], label: "Posible huayco fuerte (nivel 3)", zona: true },
    { color: COLORES[4], label: "Posible huayco extremo (nivel 4)", zona: true },
  ],
  fuente: "Pronóstico SILVIA de SENAMHI: posible activación de quebradas por lluvias intensas.",
  load: async () => null,
  render(group, _datos, { avisar }) {
    const nota = "Microcuencas donde el pronóstico diario más reciente de SENAMHI prevé posible activación de quebradas (huaycos).";
    wmsSenamhi("silvia", CAPA, { sld_body: sldNiveles(CAPA, "silvia", COLORES) }, { avisar, nota }).addTo(group);
    return nota;
  },
};
