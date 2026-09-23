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
  // Aviso amarillo de SENAMHI (nivel 2): estar atentos. El texto va en un amarillo oscuro
  // para que se lea sobre fondo claro.
  aviso: {
    label: "Aviso",
    text: "text-yellow-700 dark:text-nivel-aviso",
    border: "border-nivel-aviso/70",
    softbg: "bg-nivel-aviso/15",
    dot: "bg-nivel-aviso",
    strip: "bg-nivel-aviso",
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

// Nivel a partir de las alertas vigentes (tabla alerta: lluvia, caudal, nivel bajo y avisos
// de SENAMHI). Las de lluvia salen de umbrales provisionales de SIMPAC: suben la zona a
// "Alerta" como mucho, nunca a "Emergencia" (eso queda para los niveles oficiales de ANA y
// el aviso rojo de SENAMHI). Los avisos de SENAMHI: amarillo = aviso, naranja = alerta,
// rojo = emergencia.
const nivelEfectivo = (a) => (a.tipo === "lluvia" && a.nivel === "emergencia" ? "alerta" : a.nivel);

export function nivelDeAlertas(alertas) {
  if (alertas.some((a) => nivelEfectivo(a) === "emergencia")) return "emergencia";
  if (alertas.some((a) => nivelEfectivo(a) === "alerta")) return "alerta";
  if (alertas.some((a) => nivelEfectivo(a) === "aviso")) return "aviso";
  return "normal";
}

const n = (k, uno, varios) => `${k} ${k === 1 ? uno : varios}`;

// Cuántas cosas hay que atender: una alerta por río o estación, pero los avisos de SENAMHI
// llegan uno por departamento que cubren, así que cada aviso se cuenta una sola vez.
const contar = (lista) =>
  lista.filter((a) => a.tipo !== "aviso").length +
  new Set(lista.filter((a) => a.tipo === "aviso").map((a) => a.referencia)).size;
const COLOR_AVISO = { aviso: "amarillo", alerta: "naranja", emergencia: "rojo" };

// "1 río en emergencia, 2 ríos muy bajos y lluvia fuerte en 3 estaciones"
function describir(alertas) {
  const partes = [];
  // avisos de SENAMHI: hay una alerta por aviso y departamento, se cuentan los avisos
  const avisos = alertas.filter((a) => a.tipo === "aviso");
  if (avisos.length) {
    const cuantos = new Set(avisos.map((a) => a.referencia)).size;
    const peor = COLOR_AVISO[["emergencia", "alerta", "aviso"].find((nv) => avisos.some((a) => a.nivel === nv))];
    // el worker también cuenta los avisos que empiezan en las próximas 48 h
    partes.push(
      cuantos === 1
        ? `aviso ${peor} de SENAMHI por lluvias, vigente o por empezar`
        : `${cuantos} avisos de SENAMHI por lluvias, vigentes o por empezar (el más alto, ${peor})`
    );
  }
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
  const otras = alertas.length - alertas.filter((a) => ["aviso", "caudal", "nivel_bajo", "lluvia"].includes(a.tipo)).length;
  if (otras) partes.push(n(otras, "aviso", "avisos"));
  return partes.length > 1 ? `${partes.slice(0, -1).join(", ")} y ${partes[partes.length - 1]}` : partes[0];
}

// Primero la zona del usuario, después el resto del país. Solo afirma lo que SIMPAC
// mide en esa zona: `cobertura` = { rios, lluvia } (ríos con nivel de alerta de ANA y
// estaciones de lluvia horaria del departamento). `alertas` null = aún no hay dato.
// "Aviso naranja" si el nivel de la zona sale solo de avisos de SENAMHI; si no, el del semáforo.
function etiqueta(nivel, alertas) {
  const porOtra = alertas.some((a) => a.tipo !== "aviso" && nivelEfectivo(a) === nivel);
  return !porOtra && COLOR_AVISO[nivel] && alertas.length ? `Aviso ${COLOR_AVISO[nivel]}` : NIVEL[nivel].label;
}

export function frasesEstado(alertas, depto, cobertura = { rios: 0, lluvia: 0 }, error = false) {
  if (alertas == null) {
    return {
      nivelLocal: "sin_dato",
      etiquetaLocal: NIVEL.sin_dato.label,
      cuantasAqui: 0,
      cuantasFuera: 0,
      cuantasTotal: 0,
      avisosAqui: [],
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
  const nivelLocal = aqui.length ? nivelDeAlertas(aqui) : sinCobertura ? "sin_dato" : "normal";
  return {
    nivelLocal,
    etiquetaLocal: etiqueta(nivelLocal, aqui),
    nivelPais: nivelDeAlertas(fuera),
    cuantasAqui: contar(aqui),
    cuantasFuera: contar(fuera),
    cuantasTotal: contar(alertas), // un aviso que cubre tu zona y otras cuenta una vez
    // qué dicen los avisos de SENAMHI que cubren la zona (ya en lenguaje claro, desde el worker)
    avisosAqui: aqui.filter((a) => a.tipo === "aviso").map((a) => ({ nivel: a.nivel, detalle: a.detalle, referencia: a.referencia })),
    local,
    pais: fuera.length
      ? `${resto}: ${describir(fuera)}${donde}.`
      : `${resto}: ninguna alerta en los ríos y estaciones que SIMPAC vigila.`,
  };
}
