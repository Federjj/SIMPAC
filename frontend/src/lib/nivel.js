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
  // Sin datos para evaluar (cargando, error, o SIMPAC no vigila nada en la zona): nunca
  // se muestra "Normal" en verde por algo que no se midió.
  sin_dato: {
    label: "Sin datos",
    text: "text-muted-foreground",
    border: "border-border",
    softbg: "bg-muted",
    dot: "bg-muted-foreground",
    strip: "bg-muted-foreground/40",
  },
};

// Nivel a partir de las alertas vigentes (tabla alerta: lluvia, caudal y nivel bajo).
// Las de lluvia salen de umbrales provisionales de SIMPAC: suben la zona a "Alerta" como
// mucho, nunca a "Emergencia" (eso queda para los niveles oficiales de ANA).
const nivelEfectivo = (a) => (a.tipo === "lluvia" && a.nivel === "emergencia" ? "alerta" : a.nivel);

export function nivelDeAlertas(alertas) {
  if (alertas.some((a) => nivelEfectivo(a) === "emergencia")) return "emergencia";
  if (alertas.some((a) => nivelEfectivo(a) === "alerta")) return "alerta";
  return "normal";
}

const n = (k, uno, varios) => `${k} ${k === 1 ? uno : varios}`;

// "1 río en emergencia, 2 ríos muy bajos y lluvia fuerte en 3 estaciones"
function describir(alertas) {
  const partes = [];
  for (const nivel of ["emergencia", "alerta"]) {
    const rios = alertas.filter((a) => a.tipo === "caudal" && a.nivel === nivel).length;
    if (rios) partes.push(`${n(rios, "río", "ríos")} en ${nivel}`);
  }
  const bajos = alertas.filter((a) => a.tipo === "nivel_bajo").length;
  if (bajos) partes.push(n(bajos, "río muy bajo", "ríos muy bajos"));
  // la alerta de 1 h (más de 15 mm/h) es lluvia fuerte; la de 24 h es acumulada (referencial)
  const lluvia1h = alertas.filter((a) => a.tipo === "lluvia" && a.umbral != null && a.umbral <= 15).length;
  const lluvia24h = alertas.filter((a) => a.tipo === "lluvia").length - lluvia1h;
  if (lluvia1h) partes.push(`lluvia fuerte en la última hora en ${n(lluvia1h, "estación", "estaciones")}`);
  if (lluvia24h) partes.push(`mucha lluvia acumulada en 24 h en ${n(lluvia24h, "estación", "estaciones")} (umbral referencial de SIMPAC)`);
  const otras = alertas.length - alertas.filter((a) => ["caudal", "nivel_bajo", "lluvia"].includes(a.tipo)).length;
  if (otras) partes.push(n(otras, "aviso", "avisos"));
  return partes.length > 1 ? `${partes.slice(0, -1).join(", ")} y ${partes.at(-1)}` : partes[0];
}

// Primero la zona del usuario, después el resto del país. Solo afirma lo que SIMPAC
// mide en esa zona: `cobertura` = { rios, lluvia } (ríos con nivel de alerta de ANA y
// estaciones de lluvia horaria del departamento). `alertas` null = aún no hay dato.
export function frasesEstado(alertas, depto, cobertura = { rios: 0, lluvia: 0 }, error = false) {
  if (alertas == null) {
    return {
      nivelLocal: "sin_dato",
      cuantasAqui: 0,
      cuantasFuera: 0,
      local: error ? "No se pudo consultar las alertas. Revisa tu conexión." : "Consultando las alertas…",
      pais: "",
    };
  }
  const aqui = depto ? alertas.filter((a) => a.zona === depto) : [];
  const fuera = depto ? alertas.filter((a) => a.zona !== depto) : alertas;
  const zonas = [...new Set(fuera.map((a) => a.zona).filter(Boolean))];
  const donde = zonas.length === 1 ? ` (${zonas[0]})` : zonas.length > 1 ? ` (${zonas.length} departamentos)` : "";
  const { rios, lluvia } = cobertura;
  const sinCobertura = !rios && !lluvia;

  let local = null;
  if (depto && aqui.length) {
    local = `En ${depto}: ${describir(aqui)}.`;
  } else if (depto && sinCobertura) {
    local = `En ${depto}: SIMPAC aún no tiene ríos con nivel de alerta ni estaciones de lluvia que vigilar aquí.`;
  } else if (depto) {
    const r = rios
      ? rios === 1
        ? "su río vigilado no pasa su nivel de alerta"
        : `ninguno de sus ${rios} ríos vigilados pasa su nivel de alerta`
      : null;
    const l = lluvia
      ? lluvia === 1
        ? "su estación de lluvia no marca lluvia fuerte"
        : `ninguna de sus ${lluvia} estaciones de lluvia marca lluvia fuerte`
      : null;
    local = `En ${depto}: ${[r, l].filter(Boolean).join(", y ")}.`;
    if (!lluvia) local += " SIMPAC aún no mide la lluvia aquí.";
    if (!rios) local += " No hay ríos con nivel de alerta de ANA aquí.";
  }
  const resto = depto ? "En el resto del país" : "En el país";
  return {
    nivelLocal: aqui.length ? nivelDeAlertas(aqui) : sinCobertura ? "sin_dato" : "normal",
    nivelPais: nivelDeAlertas(fuera),
    cuantasAqui: aqui.length,
    cuantasFuera: fuera.length,
    local,
    pais: fuera.length
      ? `${resto}: ${describir(fuera)}${donde}.`
      : `${resto}: ninguna alerta en los ríos y estaciones que SIMPAC vigila.`,
  };
}
