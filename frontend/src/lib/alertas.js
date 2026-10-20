// Lógica pura de la página Alertas: prioridad, filtros y textos de cada alerta de la vista
// alerta_actual (y de la tabla alerta para las pasadas). Sin React ni Supabase (node --test).
//
// Una fila de alerta_actual: { tipo, referencia, zona, nivel, detalle, valor, umbral, ventana_h, ts }
//   tipo 'caudal' | 'nivel_bajo' (ANA) · 'aviso' (SENAMHI, una fila por departamento que cubre)
//        · 'lluvia' (una estación pasó la referencia de SENAMHI; NO es aviso oficial)
import { NIVEL } from "./nivel.js";
import { COLOR_NIVEL, claveAviso, fechaMapa } from "./avisoTexto.js";

export const ORDEN_NIVEL = ["emergencia", "alerta", "aviso"];
export const OFICIAL = (a) => a.tipo !== "lluvia";
// la lluvia medida es siempre "aviso", venga como venga (misma regla que lib/nivel.js)
export const nivelDe = (a) => (a.tipo === "lluvia" ? "aviso" : ORDEN_NIVEL.includes(a.nivel) ? a.nivel : "aviso");

// Grupo para el filtro por tipo: ríos (ANA), avisos (SENAMHI) o lluvia medida.
export const GRUPOS_TIPO = [
  { id: "todos", label: "Todo" },
  { id: "rios", label: "Ríos" },
  { id: "avisos", label: "Avisos de SENAMHI" },
  { id: "lluvia", label: "Lluvia medida" },
];
export const grupoDe = (a) => (a.tipo === "aviso" ? "avisos" : a.tipo === "lluvia" ? "lluvia" : "rios");

export const NIVELES_FILTRO = [
  { id: "todos", label: "Todos los niveles" },
  { id: "emergencia", label: NIVEL.emergencia.label },
  { id: "alerta", label: NIVEL.alerta.label },
  { id: "aviso", label: NIVEL.aviso.label },
];

// Un aviso de SENAMHI llega una vez por departamento que cubre: se junta en una sola tarjeta con
// todas sus zonas. Las demás (una por estación) quedan como están. Cada salida lleva `zonas`.
export function agruparAlertas(alertas = []) {
  const porClave = new Map();
  for (const a of alertas) {
    const clave = a.tipo === "aviso" ? `aviso:${a.referencia}:${a.nivel}` : `${a.tipo}:${a.referencia}:${a.zona}`;
    const previa = porClave.get(clave);
    if (!previa) {
      porClave.set(clave, { ...a, zonas: a.zona ? [a.zona] : [] });
    } else {
      if (a.zona && !previa.zonas.includes(a.zona)) previa.zonas.push(a.zona);
      if (Date.parse(a.ts) > Date.parse(previa.ts)) previa.ts = a.ts;
    }
  }
  return [...porClave.values()];
}

// Prioridad: emergencia -> alerta -> aviso; dentro del nivel, las oficiales antes que la lluvia
// medida; después la más reciente.
export function ordenarAlertas(alertas = []) {
  return [...alertas].sort(
    (a, b) =>
      ORDEN_NIVEL.indexOf(nivelDe(a)) - ORDEN_NIVEL.indexOf(nivelDe(b)) ||
      Number(OFICIAL(b)) - Number(OFICIAL(a)) ||
      Date.parse(b.ts ?? 0) - Date.parse(a.ts ?? 0)
  );
}

// Filtros de la página: nivel ("todos" | emergencia | alerta | aviso), tipo (GRUPOS_TIPO) y zona
// ("mia" = solo el departamento `depto`, "pais" = todo). Para las agrupadas mira `zonas`.
export function filtrarAlertas(alertas = [], { nivel = "todos", tipo = "todos", zona = "pais", depto = null } = {}) {
  return alertas.filter((a) => {
    if (nivel !== "todos" && nivelDe(a) !== nivel) return false;
    if (tipo !== "todos" && grupoDe(a) !== tipo) return false;
    if (zona === "mia" && depto) {
      const zonas = a.zonas ?? (a.zona ? [a.zona] : []);
      if (!zonas.includes(depto)) return false;
    }
    return true;
  });
}

// Lista priorizada y agrupada, lista para pintar.
export const prepararAlertas = (alertas, filtros) => ordenarAlertas(filtrarAlertas(agruparAlertas(alertas), filtros));

// Avisos de SENAMHI vigentes (vista aviso_vigente): llega una fila por área (nivel) de cada mapa
// (día) del aviso, en cualquier orden. Se junta una tarjeta por aviso (claveAviso) con:
//   nivel        el más alto de todas sus áreas y días (el nivel oficial del aviso)
//   dias         los días que cubre (ISO, en orden)
//   nivelPorDia  { dia: nivel más alto de ese día }, para decir "hoy naranja, mañana rojo"
//   departamentos  la unión de los de todas sus áreas, en orden alfabético
//   inicio/fin   desde el primer día hasta el último; en_curso si alguno ya empezó
//   texto_dia, descripcion, lectura, icono  los del área de nivel más alto (el primer día que lo alcanza)
// Nunca se toma el nivel de la primera fila: la vista llega ordenada por nivel ascendente y así
// un aviso naranja o rojo salía como amarillo.
export function agruparAvisosVigentes(avisos = []) {
  const porClave = new Map();
  for (const a of avisos) {
    const k = claveAviso(a);
    const dia = fechaMapa(a);
    let g = porClave.get(k);
    if (!g) {
      g = { ...a, dias: [], nivelPorDia: {}, departamentos: [], en_curso: false };
      porClave.set(k, g);
    }
    if (!g.dias.includes(dia)) g.dias.push(dia);
    if (a.nivel > (g.nivelPorDia[dia] ?? 0)) g.nivelPorDia[dia] = a.nivel;
    if (a.nivel > g.nivel) {
      // sube al nivel oficial y se queda con los textos de esa área
      Object.assign(g, {
        nivel: a.nivel,
        texto_dia: a.texto_dia ?? g.texto_dia ?? null,
        descripcion: a.descripcion ?? g.descripcion ?? null,
        lectura: a.lectura ?? g.lectura ?? null,
        icono: a.icono ?? g.icono ?? null,
        url: a.url ?? g.url ?? null,
      });
    }
    for (const d of a.departamentos ?? []) if (!g.departamentos.includes(d)) g.departamentos.push(d);
    if (a.inicio < g.inicio) g.inicio = a.inicio;
    if (a.fin > g.fin) g.fin = a.fin;
    if (a.en_curso) g.en_curso = true;
  }
  for (const g of porClave.values()) {
    g.dias.sort();
    g.departamentos.sort((x, y) => x.localeCompare(y, "es"));
  }
  return [...porClave.values()];
}

// "hoy (naranja), mañana (rojo)" cuando el nivel cambia entre días; si es el mismo todos los días,
// solo los días: "hoy, mañana". `cuando` convierte el ISO al texto ("hoy", "el viernes 25").
export function textoDiasAviso(g, cuando) {
  const niveles = new Set(g.dias.map((d) => g.nivelPorDia?.[d]));
  const varia = niveles.size > 1;
  return g.dias.map((d) => (varia ? `${cuando(d)} (${COLOR_NIVEL[g.nivelPorDia[d]] ?? "nivel " + g.nivelPorDia[d]})` : cuando(d))).join(", ");
}

const COLOR_AVISO = { aviso: "amarillo", alerta: "naranja", emergencia: "rojo" };

// Rótulo del nivel: "Aviso naranja" para SENAMHI, "Atentos a la lluvia" para la lluvia medida,
// y el del semáforo para los ríos.
export function etiquetaAlerta(a) {
  const n = nivelDe(a);
  if (a.tipo === "aviso") return `Aviso ${COLOR_AVISO[n]}`;
  if (a.tipo === "lluvia") return "Atentos a la lluvia";
  if (a.tipo === "nivel_bajo") return "Río muy bajo";
  return NIVEL[n].label;
}

// Título de la tarjeta (la referencia en palabras).
export function tituloAlerta(a) {
  if (a.tipo === "aviso") {
    if (a.referencia === "SENAMHI lluvia 24h") return "Aviso de SENAMHI por lluvia en las próximas 24 horas";
    const n = /(\d+)/.exec(a.referencia ?? "")?.[1];
    return n ? `Aviso N° ${n} de SENAMHI` : "Aviso de SENAMHI";
  }
  if (a.tipo === "lluvia") return `Estación ${a.referencia ?? ""}`.trim();
  // "Estación (río)" -> "Río X · estación Y"
  const m = /^(.*?)\s*\((.*)\)\s*$/.exec(a.referencia ?? "");
  if (m) return `Río ${m[2]} · estación ${m[1]}`;
  return a.referencia ?? "Alerta";
}

// Fuente oficial y su enlace (la lluvia medida no es oficial: enlaza a la página de SENAMHI
// de la estación solo como referencia).
export function fuenteAlerta(a) {
  if (a.tipo === "aviso") {
    return {
      nombre: "SENAMHI (aviso oficial)",
      oficial: true,
      url: a.referencia === "SENAMHI lluvia 24h" ? "https://www.senamhi.gob.pe/?p=aviso-24H" : "https://www.senamhi.gob.pe/?p=aviso-meteorologico",
    };
  }
  if (a.tipo === "lluvia") {
    return { nombre: "Lluvia medida por una estación de SENAMHI; no es un aviso oficial", oficial: false, url: "https://www.senamhi.gob.pe/?p=estaciones" };
  }
  return { nombre: "ANA (niveles de alerta de la estación)", oficial: true, url: "https://snirh.ana.gob.pe/observatorioSNIRH/" };
}

// "Cajamarca", "Cajamarca y La Libertad", "Cajamarca, Piura y 3 más"
export function textoZonas(zonas = []) {
  if (!zonas.length) return "";
  if (zonas.length === 1) return zonas[0];
  if (zonas.length === 2) return `${zonas[0]} y ${zonas[1]}`;
  if (zonas.length === 3) return `${zonas[0]}, ${zonas[1]} y ${zonas[2]}`;
  return `${zonas[0]}, ${zonas[1]} y ${zonas.length - 2} más`;
}

// Rango por defecto de las alertas pasadas: los últimos 7 días, nunca más de 30.
export const MAX_DIAS_PASADAS = 30;
export function rangoPasadas({ desde, hasta } = {}, hoy) {
  const fin = hasta && /^\d{4}-\d{2}-\d{2}$/.test(hasta) ? hasta : hoy;
  const porDefecto = sumarDias(fin, -7);
  let ini = desde && /^\d{4}-\d{2}-\d{2}$/.test(desde) ? desde : porDefecto;
  let aviso = null;
  if (ini > fin) {
    ini = porDefecto;
    aviso = "La fecha de inicio era posterior a la de fin: se tomaron los últimos 7 días.";
  } else if (diasEntre(ini, fin) > MAX_DIAS_PASADAS) {
    ini = sumarDias(fin, -MAX_DIAS_PASADAS);
    aviso = `Solo se guardan ${MAX_DIAS_PASADAS} días de alertas: se recortó el rango.`;
  }
  return { desde: ini, hasta: fin, aviso };
}
const DIA_MS = 86_400_000;
const sumarDias = (iso, n) => new Date(Date.parse(`${iso}T12:00:00-05:00`) + n * DIA_MS).toLocaleDateString("en-CA", { timeZone: "America/Lima" });
const diasEntre = (a, b) => Math.round((Date.parse(`${b}T12:00:00-05:00`) - Date.parse(`${a}T12:00:00-05:00`)) / DIA_MS);
