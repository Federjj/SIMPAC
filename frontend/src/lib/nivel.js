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
  // Aviso amarillo de SENAMHI (nivel 2) o lluvia medida sobre la referencia de SENAMHI
  // (rótulo "Atentos a la lluvia"): estar atentos. El texto va en un amarillo oscuro para que
  // se lea sobre fondo claro.
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

// Nivel a partir de las alertas vigentes (vista alerta_actual: lluvia, caudal, nivel bajo y
// avisos de SENAMHI). La lluvia (una estación que pasó la referencia de SENAMHI; no es aviso
// oficial) es siempre "aviso", venga como venga de la BD. Los avisos de SENAMHI: amarillo =
// aviso, naranja = alerta, rojo = emergencia.
const nivelEfectivo = (a) => (a.tipo === "lluvia" ? "aviso" : a.nivel);

export function nivelDeAlertas(alertas) {
  if (alertas.some((a) => nivelEfectivo(a) === "emergencia")) return "emergencia";
  if (alertas.some((a) => nivelEfectivo(a) === "alerta")) return "alerta";
  if (alertas.some((a) => nivelEfectivo(a) === "aviso")) return "aviso";
  return "normal";
}

const n = (k, uno, varios) => `${k} ${k === 1 ? uno : varios}`;

// Cuántas alertas y avisos oficiales hay: una alerta por río, pero los avisos de SENAMHI
// llegan uno por departamento que cubren, así que cada aviso se cuenta una sola vez. La lluvia
// medida sobre la referencia no cuenta: no es un aviso oficial (y en temporada serían decenas).
const contar = (lista) =>
  lista.filter((a) => a.tipo !== "aviso" && a.tipo !== "lluvia").length +
  new Set(lista.filter((a) => a.tipo === "aviso").map((a) => a.referencia)).size;
const COLOR_AVISO = { aviso: "amarillo", alerta: "naranja", emergencia: "rojo" };

// "1 río en emergencia, 2 ríos muy bajos y lluvia por encima de la referencia de SENAMHI en 3 estaciones"
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
  // una fila por estación que pasó la referencia de SENAMHI (en 1 h o en 6 h)
  const lluvia = new Set(alertas.filter((a) => a.tipo === "lluvia").map((a) => a.referencia)).size;
  if (lluvia) partes.push(`lluvia por encima de la referencia de SENAMHI en ${n(lluvia, "estación", "estaciones")}`);
  const otras = alertas.length - alertas.filter((a) => ["aviso", "caudal", "nivel_bajo", "lluvia"].includes(a.tipo)).length;
  if (otras) partes.push(n(otras, "alerta de otro tipo", "alertas de otro tipo"));
  return partes.length > 1 ? `${partes.slice(0, -1).join(", ")} y ${partes[partes.length - 1]}` : partes[0];
}

// Rótulo de la zona: "Aviso naranja" si su nivel sale solo de avisos de SENAMHI (con o sin
// lluvia medida), "Atentos a la lluvia" si sale solo de estaciones que pasaron la referencia
// de SENAMHI (que no es un aviso oficial), y si no, el del semáforo.
function etiqueta(nivel, alertas) {
  const deEse = alertas.filter((a) => nivelEfectivo(a) === nivel);
  if (!deEse.length || deEse.some((a) => a.tipo !== "aviso" && a.tipo !== "lluvia")) return NIVEL[nivel].label;
  if (deEse.some((a) => a.tipo === "aviso")) return `Aviso ${COLOR_AVISO[nivel]}`;
  return "Atentos a la lluvia";
}

// Primero la zona del usuario, después el resto del país. Solo afirma lo que SIMPAC
// revisa en esa zona: `cobertura` = { rios, lluvia, lluviaFuera, lluviaRevisada } (ríos con
// nivel de alerta de ANA; estaciones de SENAMHI del departamento, y del resto del país, con
// lluvia de la última hora y referencia; y si esas lecturas ya pasaron por la regla del
// worker). `alertas` null = aún no hay dato.
export function frasesEstado(alertas, depto, cobertura = { rios: 0, lluvia: 0, lluviaFuera: 0, lluviaRevisada: false }, error = false) {
  if (alertas == null) {
    return {
      nivelLocal: "sin_dato",
      nivelOficialAqui: "sin_dato",
      etiquetaLocal: NIVEL.sin_dato.label,
      cuantasAqui: 0,
      cuantasFuera: 0,
      cuantasTotal: 0,
      avisosAqui: [],
      lluviaAqui: [],
      local: error ? "No se pudo consultar las alertas. Revisa tu conexión." : "Consultando las alertas…",
      pais: "",
    };
  }
  const aqui = depto ? alertas.filter((a) => a.zona === depto) : [];
  const fuera = depto ? alertas.filter((a) => a.zona !== depto) : alertas;
  const zonas = [...new Set(fuera.map((a) => a.zona).filter(Boolean))];
  const donde = zonas.length === 1 ? ` (${zonas[0]})` : zonas.length > 1 ? ` (${zonas.length} departamentos)` : "";
  const { rios, lluvia, lluviaFuera, lluviaRevisada } = cobertura;
  // sin revisar no se afirma "ninguna pasa": puede que la regla aún no haya corrido
  const hayLluvia = lluviaRevisada && lluvia > 0;
  const sinCobertura = !rios && !hayLluvia;

  let local = null;
  if (depto && aqui.length) {
    local = `En ${depto}: ${describir(aqui)}.`;
  } else if (depto && sinCobertura) {
    local = lluviaRevisada
      ? `En ${depto}: SIMPAC no tiene aquí ríos con nivel de alerta ni estaciones de SENAMHI con lluvia de las últimas 3 horas que pueda revisar.`
      : `En ${depto}: no se pudo revisar la lluvia de las estaciones de SENAMHI. No hay ríos con nivel de alerta de ANA aquí.`;
  } else if (depto) {
    const r = rios
      ? rios === 1
        ? "su río vigilado no pasa su nivel de alerta"
        : `ninguno de sus ${rios} ríos vigilados pasa su nivel de alerta`
      : null;
    const l = hayLluvia
      ? lluvia === 1
        ? "su estación de lluvia con dato reciente no pasa la referencia de SENAMHI"
        : `ninguna de sus ${lluvia} estaciones de lluvia con dato reciente pasa la referencia de SENAMHI`
      : null;
    local = `En ${depto}: ${[r, l].filter(Boolean).join(", y ")}.`;
    if (!hayLluvia) {
      local += lluviaRevisada
        ? " Aquí no hay estaciones de SENAMHI con lluvia de las últimas 3 horas que SIMPAC pueda revisar."
        : " No se pudo revisar la lluvia de las estaciones de SENAMHI.";
    }
    if (!rios) local += " No hay ríos con nivel de alerta de ANA aquí.";
  }
  const resto = depto ? "En el resto del país" : "En el país";
  const nivelLocal = aqui.length ? nivelDeAlertas(aqui) : sinCobertura ? "sin_dato" : "normal";
  return {
    nivelLocal,
    // el de lo oficial (ríos de ANA y avisos de SENAMHI), sin la lluvia medida: el color de
    // la métrica "alertas y avisos", que tampoco la cuenta
    nivelOficialAqui: nivelLocal === "sin_dato" ? "sin_dato" : nivelDeAlertas(aqui.filter((a) => a.tipo !== "lluvia")),
    etiquetaLocal: etiqueta(nivelLocal, aqui),
    nivelPais: nivelDeAlertas(fuera),
    cuantasAqui: contar(aqui),
    cuantasFuera: contar(fuera),
    cuantasTotal: contar(alertas), // un aviso que cubre tu zona y otras cuenta una vez
    // qué dicen los avisos de SENAMHI que cubren la zona (ya en lenguaje claro, desde el worker)
    avisosAqui: aqui.filter((a) => a.tipo === "aviso").map((a) => ({ nivel: a.nivel, detalle: a.detalle, referencia: a.referencia })),
    // estaciones de la zona que pasaron la referencia de SENAMHI, la que más la pasó primero
    // (el detalle ya viene del worker listo para mostrar)
    lluviaAqui: aqui
      .filter((a) => a.tipo === "lluvia")
      .sort((a, b) => b.valor / b.umbral - a.valor / a.umbral)
      .map(({ referencia, detalle, ts }) => ({ referencia, detalle, ts })),
    local,
    // "ninguna pasa" solo si hubo estaciones que revisar fuera de la zona
    pais: fuera.length
      ? `${resto}: ${describir(fuera)}${donde}.`
      : `${resto}: no hay avisos de SENAMHI ni alertas de ríos${lluviaRevisada && lluviaFuera > 0 ? ", y ninguna estación de lluvia pasa la referencia de SENAMHI" : ""}.`,
  };
}
