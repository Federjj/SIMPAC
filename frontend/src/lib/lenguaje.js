// Lenguaje claro: un solo diccionario para el panel, la barra lateral, los popups y las
// leyendas, así lo mismo se dice igual en todas partes. Cada dato va en tres capas: qué
// pasa (frase), qué significa para mí, y el número con su fuente como respaldo.
//
// Reglas y fuentes (detalle en frontend/README.md):
//   ICEN        Nota Técnica ENFEN 01-2024 (neutra -0.7..+0.5, débil..+1.3, moderada..+2.1, fuerte..+3.5)
//   RONI        NOAA CPC, índice oficial desde feb-2026 (magnitud en pasos de 0.5)
//   ENFEN       estado del Sistema de Alerta según el comunicado oficial vigente
//   Ríos        umbrales de alerta y emergencia de ANA (crecida o nivel bajo)
//   Lluvia      escala horaria de AEMET como referencia (no hay escala oficial internacional)
//   "Atento" (80 % del umbral o menos de 0.5 m) y lo de meses secos son criterios de SIMPAC.
import { MESES, diaLegible, diasDesde, fechaPeru } from "./tiempo";

const TRIMESTRES = {
  DJF: "dic–feb", JFM: "ene–mar", FMA: "feb–abr", MAM: "mar–may", AMJ: "abr–jun", MJJ: "may–jul",
  JJA: "jun–ago", JAS: "jul–set", ASO: "ago–oct", SON: "set–nov", OND: "oct–dic", NDJ: "nov–ene",
};

export const TENDENCIA = { Ascendente: "subiendo", Descendente: "bajando", Estable: "estable" };

const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });
const signo = (v) => (v >= 0 ? "+" : "") + num(v);

// "2026-07" -> "julio 2026"
export function mesLegible(periodo) {
  const m = /^(\d{4})-(\d{2})/.exec(periodo ?? "");
  return m ? `${MESES[Number(m[2]) - 1]} ${m[1]}` : periodo ?? "";
}

// "JJA 2026" -> "jun–ago 2026"
export function trimestreLegible(periodo) {
  const [t, anio] = (periodo ?? "").split(" ");
  return TRIMESTRES[t] ? `${TRIMESTRES[t]} ${anio}` : periodo ?? "";
}

function mesesDesde(periodo) {
  const m = /^(\d{4})-(\d{2})/.exec(periodo ?? "");
  if (!m) return 0;
  const [anio, mes] = fechaPeru().split("-").map(Number);
  return (anio - Number(m[1])) * 12 + (mes - Number(m[2]));
}

// ---------------------------------------------------------------------------
// El Niño
// ---------------------------------------------------------------------------

// Estado oficial del ENFEN (comunicado vigente).
export function textoEnfen(c) {
  if (!c) return null;
  const e = c.estado.toLowerCase();
  const nina = e.includes("niña");
  const quien = nina ? "La Niña costera" : "El Niño costero";
  let corto;
  let explica;
  if (e.includes("no activo")) {
    corto = "Sin alerta";
    explica = "El sistema de alerta del ENFEN no está activo.";
  } else if (e.includes("alerta")) {
    corto = "Alerta";
    explica = `${quien} está en curso o es inminente.`;
  } else if (e.includes("vigilancia")) {
    corto = "Vigilancia";
    explica = `${quien} podría desarrollarse en los próximos meses.`;
  } else {
    corto = c.estado;
    explica = c.estado;
  }
  const accion = e.includes("niño") && (e.includes("alerta") || e.includes("vigilancia"))
    ? "Mantén limpios techos, canaletas y acequias, ubica las quebradas cercanas y sigue los avisos de SENAMHI."
    : null;
  const fecha = diaLegible(c.fecha);
  const atrasado = diasDesde(c.fecha) > 16; // salen cada ~2 semanas
  return {
    corto,
    quien,
    titulo: `${quien}: ${corto.toLowerCase()}`,
    explica,
    accion,
    fuente: `Comunicado ${c.extraordinario ? "extraordinario " : ""}ENFEN ${c.numero}-${c.anio}, ${fecha}` +
      (c.proximo ? `. Próximo: ${diaLegible(c.proximo)}` : ""),
    atrasado,
  };
}

// ICEN: la temperatura del mar frente a la costa norte del Perú.
export function textoMar(icen, icenTmp) {
  if (!icen) return null;
  const v = icen.valor;
  const cat = (icen.categoria ?? "").toLowerCase();
  const fuerte = /fuerte|extraordinari/.test(cat);
  let corto;
  let frase;
  if (cat.startsWith("cálid") || cat.startsWith("calid")) {
    corto = fuerte ? "Muy caliente" : "Más caliente";
    frase = `El mar frente al Perú está ${fuerte ? "mucho " : ""}más caliente de lo normal.`;
  } else if (cat.startsWith("frí") || cat.startsWith("fri")) {
    corto = fuerte ? "Muy frío" : "Más frío";
    frase = `El mar frente al Perú está ${fuerte ? "mucho " : ""}más frío de lo normal.`;
  } else {
    corto = "Normal";
    frase = "El mar frente al Perú está en su temperatura normal.";
  }
  const tmp = icenTmp && icenTmp.periodo > icen.periodo
    ? ` Estimado de ${MESES[Number(icenTmp.periodo.slice(5, 7)) - 1]}: ${signo(icenTmp.valor)}, ${icenTmp.categoria.toLowerCase()}.`
    : "";
  return {
    corto,
    frase,
    detalle: `Índice costero ${signo(v)} · ${icen.categoria.toLowerCase()} · ${mesLegible(icen.periodo)}${icen.origen ? ` (${icen.origen})` : ""}.${tmp}`,
    atrasado: mesesDesde(icen.periodo) > 3 ? `Último dato disponible: ${mesLegible(icen.periodo)}.` : null,
  };
}

// RONI: El Niño en el Pacífico central (índice mundial).
export function textoPacifico(roni) {
  if (!roni) return null;
  const neutro = roni.categoria === "Neutro";
  return {
    corto: neutro ? "Normal" : roni.categoria,
    frase: neutro ? "Pacífico central: sin El Niño ni La Niña." : `Pacífico central: ${roni.categoria}.`,
    detalle: `Índice NOAA ${signo(roni.valor)} · promedio ${trimestreLegible(roni.periodo)}`,
  };
}

// ---------------------------------------------------------------------------
// Ríos (ANA)
// ---------------------------------------------------------------------------

const ETIQUETA = {
  normal: "Tranquilo",
  atento: "Atento",
  alerta: "En alerta",
  emergencia: "En emergencia",
  sd: "Sin nivel de alerta",
};

// "Cerca del nivel de alerta" no es de ANA: es un criterio de SIMPAC y se dice.
const NOTA_ATENTO = "“Cerca” es un criterio de SIMPAC (80 % del caudal de alerta, o menos de 50 cm del nivel), no un aviso de ANA.";

// Todo lo que el mapa dice de una estación de río. `estado` decide el color.
export function textoRio(c) {
  const esCaudal = c.unidad === "m³/s";
  const que = c.rio === "Titicaca" ? "Lago" : "Río";
  const titulo = c.rio ? `${que} ${c.rio} (${c.estacion})` : c.estacion;
  const medida = c.valor == null ? null : `${num(c.valor)} ${c.unidad}`;
  const tendencia = TENDENCIA[c.tendencia];
  const va = tendencia ? ` Está ${tendencia}.` : "";
  const ua = c.umbral_alerta;
  const ue = c.umbral_emergencia;
  const base = { titulo, esCaudal, bajo: false, accion: null, ua, ue };

  if (c.valor == null) {
    return { ...base, estado: "sd", etiqueta: "Sin medición", frase: "ANA no tiene una medición reciente de esta estación." };
  }
  if (ua == null) {
    return { ...base, estado: "sd", etiqueta: ETIQUETA.sd, frase: `ANA no publica un nivel de alerta para esta estación. Medida: ${medida}.${va}` };
  }

  // Umbrales de nivel bajo (vaciante): el peligro es que el río baje.
  if (ue != null && ue < ua) {
    const bajo = { ...base, bajo: true };
    if (c.valor <= ue) {
      return { ...bajo, estado: "emergencia", etiqueta: "Río muy bajo", frase: `Río muy bajo por la temporada seca: está por debajo de su nivel de emergencia por nivel bajo (${num(ue)} ${c.unidad}).${va}`, accion: "Puede dificultar la navegación y el transporte por río." };
    }
    if (c.valor <= ua) {
      return { ...bajo, estado: "alerta", etiqueta: "Río muy bajo", frase: `Río muy bajo por la temporada seca: está por debajo de su nivel de alerta por nivel bajo (${num(ua)} ${c.unidad}).${va}`, accion: "Puede dificultar la navegación y el transporte por río." };
    }
    // Por encima del umbral de nivel bajo: para ANA está normal. Solo se avisa si está
    // cerca y bajando (criterio SIMPAC); no se atribuye una causa que no se mide.
    const sobra = c.valor - ua;
    const atento = sobra <= 0.5 && c.tendencia === "Descendente";
    return {
      ...bajo,
      estado: atento ? "atento" : "normal",
      etiqueta: atento ? ETIQUETA.atento : ETIQUETA.normal,
      frase: `${atento ? "Cerca de su nivel de alerta por nivel bajo" : "Tranquilo"}. Esta estación vigila que el río no baje demasiado: está ${distancia(sobra)} por encima de ese nivel (${num(ua)} ${c.unidad}).${va}`,
      accion: atento ? `Revisa los avisos de SENAMHI por ríos bajos. ${NOTA_ATENTO}` : null,
    };
  }

  // Umbrales de crecida
  if (ue != null && c.valor >= ue) {
    return { ...base, estado: "emergencia", etiqueta: ETIQUETA.emergencia, frase: `Pasó su nivel de emergencia (${num(ue)} ${c.unidad}). Lleva ${medida}.${va}`, accion: "Aléjate de la orilla, no cruces el río y sigue las indicaciones de Defensa Civil." };
  }
  if (c.valor >= ua) {
    return { ...base, estado: "alerta", etiqueta: ETIQUETA.alerta, frase: `Pasó su nivel de alerta (${num(ua)} ${c.unidad}). Lleva ${medida}.${va}`, accion: "Aléjate de la orilla y no cruces el río." };
  }
  if (esCaudal) {
    const pct = (c.valor / ua) * 100;
    const pctTxt = pct < 1 ? "menos del 1 %" : `el ${Math.round(pct)} %`;
    const atento = pct >= 80;
    return { ...base, estado: atento ? "atento" : "normal", etiqueta: atento ? ETIQUETA.atento : ETIQUETA.normal, frase: `${atento ? "Cerca del nivel de alerta" : "Tranquilo"}. Lleva ${medida}, ${pctTxt} del caudal que activa la alerta (${num(ua)} m³/s).${va}`, accion: atento ? NOTA_ATENTO : null };
  }
  // niveles (m, m s. n. m.): el porcentaje engaña, se dice cuánto falta. En un lago (el
  // Titicaca varía ~1 m en toda la temporada) medio metro no es "cerca": no se usa "atento".
  const faltan = ua - c.valor;
  const atento = faltan <= 0.5 && c.rio !== "Titicaca";
  return { ...base, estado: atento ? "atento" : "normal", etiqueta: atento ? ETIQUETA.atento : ETIQUETA.normal, frase: `${atento ? "Cerca del nivel de alerta" : "Tranquilo"}. El agua está a ${medida}; le faltan ${distancia(faltan)} para el nivel de alerta (${num(ua)} ${c.unidad}).${va}`, accion: atento ? NOTA_ATENTO : null };
}

function distancia(metros) {
  return metros < 1 ? `${Math.round(metros * 100)} cm` : `${num(metros)} m`;
}

export function lecturaRio(c) {
  return c.fecha ? `${diaLegible(c.fecha)} ${c.hora ?? ""} (ANA)`.replace("  ", " ") : null;
}

// ---------------------------------------------------------------------------
// Lluvia
// ---------------------------------------------------------------------------

// Intensidad por hora (escala orientativa, tomada de AEMET).
export function intensidad(mmHora) {
  if (mmHora == null) return null;
  if (mmHora <= 0) return "sin lluvia";
  if (mmHora <= 2) return "ligera";
  if (mmHora <= 15) return "moderada";
  if (mmHora <= 30) return "fuerte";
  if (mmHora <= 60) return "muy fuerte";
  return "torrencial";
}

const ORDEN_INTENSIDAD = ["sin lluvia", "ligera", "moderada", "fuerte", "muy fuerte", "torrencial"];

// Resumen de las últimas 24 h de las estaciones de un departamento.
// filas: [{ cod, medido_en, precip_mm, estacion: { nombre } }]. Un precip_mm nulo es
// "sin dato", no "no llovió".
const RECIENTE_MS = 2 * 3_600_000;

export function resumenLluvia(filas, depto) {
  if (!filas?.length) return null;
  const porEstacion = new Map();
  for (const f of filas) {
    const e = porEstacion.get(f.cod) ?? { nombre: f.estacion?.nombre ?? f.cod, total: 0, max: 0, datos: 0, ultima: null };
    if (f.precip_mm != null) {
      e.total += f.precip_mm;
      e.max = Math.max(e.max, f.precip_mm);
      e.datos += 1;
      if (!e.ultima || f.medido_en > e.ultima.medido_en) e.ultima = f;
    }
    porEstacion.set(f.cod, e);
  }
  const estaciones = [...porEstacion.values()].filter((e) => e.datos > 0);
  if (!estaciones.length) return null;
  const n = estaciones.length;
  const conLluvia = estaciones.filter((e) => e.total > 0).sort((a, b) => b.total - a.total);
  const peor = conLluvia.reduce((acc, e) => {
    const i = intensidad(e.max);
    return ORDEN_INTENSIDAD.indexOf(i) > ORDEN_INTENSIDAD.indexOf(acc) ? i : acc;
  }, "sin lluvia");
  const cuantas = (k) => `${k} ${k === 1 ? "estación" : "estaciones"}`;
  let frase;
  if (!conLluvia.length) {
    frase = n === 1
      ? `No llovió en las últimas 24 h en la estación de SENAMHI de ${depto}.`
      : `No llovió en las últimas 24 h en las ${n} estaciones de SENAMHI de ${depto}.`;
  } else {
    const top = conLluvia.slice(0, 3).map((e) => `${nombreEstacion(e.nombre)} ${num(Math.round(e.total * 10) / 10)} mm`).join(", ");
    frase = `En las últimas 24 h llovió en ${conLluvia.length} de ${cuantas(n)} (lo más intenso: lluvia ${peor}). Más lluvia: ${top}.`;
  }
  // "ahora" = la última lectura de cada estación, si es de las últimas 2 h
  const recientes = estaciones.filter((e) => Date.now() - Date.parse(e.ultima.medido_en) <= RECIENTE_MS);
  let ahoraTxt;
  if (!recientes.length) {
    ahoraTxt = "No hay lecturas de las últimas 2 horas.";
  } else {
    const lloviendo = recientes.filter((e) => e.ultima.precip_mm > 0).length;
    const de = recientes.length === n ? "" : ` de las ${recientes.length} con dato reciente`;
    ahoraTxt = lloviendo
      ? `En su última lectura llovía en ${cuantas(lloviendo)}${de}.`
      : `En su última lectura no llovía en ninguna${de}.`;
  }
  const ultima = estaciones.reduce((m, e) => (e.ultima.medido_en > m ? e.ultima.medido_en : m), "");
  return { frase: `${frase} ${ahoraTxt}`, estaciones: n, conLluvia: conLluvia.length, ultima };
}

// "UNC CAJAMARCA" -> "UNC Cajamarca" (los nombres de SENAMHI vienen en mayúsculas; algunos
// llevan al final la letra del tipo de estación, "BAMBAMARCA M", que no le dice nada a nadie)
export function nombreEstacion(nombre) {
  return nombre
    .replace(/\s+[MH]$/i, "")
    .toLowerCase()
    .replace(/(^|[\s(-])([a-záéíóúñü])/g, (_, a, b) => a + b.toUpperCase())
    .replace(/\b(Unc|Gore|Senamhi)\b/g, (s) => s.toUpperCase());
}

// ---------------------------------------------------------------------------
// Anomalía mensual de lluvia (capa de SENAMHI/IDESEP)
// ---------------------------------------------------------------------------

// Clases oficiales de SENAMHI (campo PORCENTAJE, p. ej. "-60 - -30") en palabras.
export const CLASES_ANOMALIA = [
  { desde: -100, texto: "Llovió mucho menos de lo normal", color: "#DB0404" },
  { desde: -60, texto: "Llovió bastante menos de lo normal", color: "#F58E27" },
  { desde: -30, texto: "Llovió algo menos de lo normal", color: "#EBEB3B" },
  { desde: -15, texto: "Llovió cerca de lo normal", color: "#D4D4D4" },
  { desde: 15, texto: "Llovió algo más de lo normal", color: "#95CEF4" },
  { desde: 30, texto: "Llovió bastante más de lo normal", color: "#3BA5EB" },
  { desde: 60, texto: "Llovió mucho más de lo normal", color: "#3B3BEB" },
];

export function claseAnomalia(p) {
  const m = /^\s*(-?\d+(?:\.\d+)?)/.exec(p?.PORCENTAJE ?? "");
  const desde = m ? Number(m[1]) : null;
  if (desde != null) {
    const exacta = CLASES_ANOMALIA.find((c) => c.desde === desde);
    if (exacta) return exacta;
  }
  const a = p?.ANOMALIA ?? 0; // sin clase oficial: se ubica el % en los mismos tramos
  return [...CLASES_ANOMALIA].reverse().find((c) => a >= c.desde) ?? CLASES_ANOMALIA[0];
}

export function textoAnomalia(p, periodo) {
  const clase = claseAnomalia(p);
  const mes = mesLegible(periodo);
  const nombreMes = mes.split(" ")[0];
  const prec = p.PREC != null ? `${num(p.PREC)} mm` : null;
  const normal = p.NORMAL != null ? `${num(p.NORMAL)} mm` : null;
  // en meses casi secos el porcentaje exagera: se habla en milímetros (criterio SIMPAC)
  if (p.NORMAL != null && p.NORMAL < 10) {
    return {
      clase,
      frase: `${mes}: ${p.PREC ? `cayeron ${prec}` : "no llovió"}. Aquí ${nombreMes} casi no tiene lluvia (lo normal es ${normal}), así que esto solo no indica sequía ni exceso.`,
    };
  }
  return {
    clase,
    frase: `${mes}: ${clase.texto.toLowerCase()}.${prec && normal ? ` Cayeron ${prec}; en un ${nombreMes} típico caen ${normal}.` : ""}`,
  };
}

// Tipo de transmisión de una estación SENAMHI (código del inventario).
export const TRANSMISION = { AUTOMATICA: "automática", REAL: "en tiempo real", DIFERIDO: "diferida" };
