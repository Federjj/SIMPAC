// Semáforo de alerta: clases de color por nivel (literales para que Tailwind las genere).
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

// Nivel global a partir de las alertas vigentes (tabla alerta: lluvia y caudal).
export function nivelDeAlertas(alertas) {
  if (alertas.some((a) => a.nivel === "emergencia")) return "emergencia";
  if (alertas.some((a) => a.nivel === "alerta")) return "alerta";
  return "normal";
}

const PLURAL = { alerta: ["alerta", "alertas"], emergencia: ["emergencia", "emergencias"] };

// Frase del panel de estado: "2 emergencias en Loreto", "Sin alertas vigentes"...
export function titularDe(alertas) {
  const nivel = nivelDeAlertas(alertas);
  if (nivel === "normal") return "Sin alertas vigentes";
  const delNivel = alertas.filter((a) => a.nivel === nivel);
  const n = delNivel.length;
  const que = PLURAL[nivel][n === 1 ? 0 : 1];
  const zonas = [...new Set(delNivel.map((a) => a.zona).filter(Boolean))];
  const donde =
    zonas.length === 1 ? ` en ${zonas[0]}` : zonas.length > 1 ? ` en ${zonas.length} departamentos` : "";
  return `${n} ${que}${donde}`;
}
