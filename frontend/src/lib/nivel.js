// Semaforo de alerta: clases de color por nivel (literales para que Tailwind las genere).
export const NIVEL = {
  normal: {
    label: "Normal",
    text: "text-nivel-normal",
    border: "border-nivel-normal/50",
    softbg: "bg-nivel-normal/10",
    dot: "bg-nivel-normal",
    strip: "bg-nivel-normal",
  },
  alerta: {
    label: "Alerta",
    text: "text-nivel-alerta",
    border: "border-nivel-alerta/50",
    softbg: "bg-nivel-alerta/10",
    dot: "bg-nivel-alerta",
    strip: "bg-nivel-alerta",
  },
  emergencia: {
    label: "Emergencia",
    text: "text-nivel-emergencia",
    border: "border-nivel-emergencia/50",
    softbg: "bg-nivel-emergencia/10",
    dot: "bg-nivel-emergencia",
    strip: "bg-nivel-emergencia",
  },
};

// Nivel global a partir de las lecturas de caudal.
export function nivelDeCaudales(caudales) {
  if (caudales.some((c) => c.estado === "emergencia")) return "emergencia";
  if (caudales.some((c) => c.estado === "alerta")) return "alerta";
  return "normal";
}
