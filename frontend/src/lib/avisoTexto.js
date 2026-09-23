// Textos de los avisos de SENAMHI en lenguaje claro: el tooltip de la insignia y el contenido del
// popup (map/popups.js lo pasa a HTML escapado). Lo que sale del texto oficial va citado tal cual;
// lo que resume SIMPAC se rotula "basado en el aviso de SENAMHI". El ícono y la lectura (lectura,
// texto_dia) los calcula el worker (backend/ingesta/lectura_aviso.py). Módulo puro (node --test).
import { DIAS, diaMesCorto, diaSemana, fechaLarga, fechaPeru, hhmmPeru, momentoPeru } from "./tiempo.js";

const DIA_MS = 86_400_000;
const sumarDias = (iso, n) => fechaPeru(Date.parse(`${iso}T12:00:00-05:00`) + n * DIA_MS);
const numero = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 1 });

export const COLOR_NIVEL = { 2: "amarillo", 3: "naranja", 4: "rojo" };
const FENOMENO = { lluvia: "Lluvias", llovizna: "Llovizna", nevada: "Nevadas" };
const INTENSIDAD_24H = { 2: "moderada", 3: "fuerte", 4: "extrema" };
export const FIRMA_AVISO = "Ícono, zona simplificada y resumen de SIMPAC, basados en el aviso de SENAMHI.";
const NO_TODA = "No quiere decir que llueva en toda la zona ni todo el día.";

// El backend guarda 'temperatura': el título dice si es por calor o por frío.
export const temaAviso = (a) =>
  a.tema !== "temperatura" ? a.tema : /INCREMENTO|CALOR|ALTA/i.test(a.titulo ?? "") ? "calor" : "frio";

// Glifo de la insignia: el del worker (gota, gota_rayo, copo) o, en calor, frío y viento, el del
// tema (para no confundir su amarillo con el de la lluvia). null = sin insignia.
export function glifoAviso(a) {
  if (a.icono) return a.icono;
  const t = temaAviso(a);
  return t === "calor" ? "termometro" : t === "frio" ? "termometro_frio" : t === "viento" ? "viento" : null;
}

// Un aviso es uno por tipo, año y número (sus mapas son los días).
export const claveAviso = (a) => `${a.tipo}-${a.anio ?? ""}-${a.numero ?? ""}`;

// Día del mapa (el día que cubre esa fila), en hora de Perú.
export const fechaMapa = (a) => fechaPeru(a.inicio);

const fenomenoDe = (a) => a.lectura?.fenomeno ?? (a.icono === "copo" ? "nevada" : "lluvia");

// "hoy", "mañana" o "el viernes 25"
export function cuando(fecha, hoy = fechaPeru()) {
  if (fecha === hoy) return "hoy";
  if (fecha === sumarDias(hoy, 1)) return "mañana";
  return `el ${DIAS[diaSemana(fecha)]} ${Number(fecha.split("-")[2])}`;
}

// "hoy, miércoles 23 de setiembre", "mañana, jueves 24 de setiembre" o "el viernes 25 de setiembre"
export function cuandoLargo(fecha, hoy = fechaPeru()) {
  if (fecha === hoy) return `hoy, ${fechaLarga(fecha)}`;
  if (fecha === sumarDias(hoy, 1)) return `mañana, ${fechaLarga(fecha)}`;
  return `el ${fechaLarga(fecha)}`;
}

// "de hoy", "de mañana" o "del viernes 25" (hasta cuándo rige el aviso de 24 h)
function deDia(fecha, hoy) {
  const c = cuando(fecha, hoy);
  return c.startsWith("el ") ? `del ${c.slice(3)}` : `de ${c}`;
}

export function tooltipAviso(a, { hoy = fechaPeru() } = {}) {
  const cab = `Aviso ${COLOR_NIVEL[a.nivel]} de SENAMHI`;
  const mas = "Toca para ver más.";
  if (a.tipo === "lluvia24h")
    return `${cab}: puede llover en algún momento en esta zona hasta las ${hhmmPeru(a.fin)} ${deDia(fechaPeru(a.fin), hoy)}. ${mas}`;
  const t = temaAviso(a);
  if (t === "calor") return `${cab} por calor. ${mas}`;
  if (t === "frio") return `${cab} por frío. ${mas}`;
  if (t === "viento") return `${cab} por viento. ${mas}`;
  if (t !== "lluvia") return `${cab}. ${mas}`;
  const c = cuando(fechaMapa(a), hoy);
  const f = fenomenoDe(a);
  if (f === "nevada") return `${cab}: puede nevar en algún momento en las partes altas de esta zona ${c}. ${mas}`;
  if (f === "llovizna") return `${cab}: puede lloviznar en algún momento en esta zona ${c}. ${mas}`;
  if (a.icono === "gota_rayo") return `${cab}: puede llover, con rayos, en algún momento en esta zona ${c}. ${mas}`;
  return `${cab}: puede llover en algún momento en esta zona ${c}. ${mas}`;
}

export const tooltipJuntos = (n) => `${n} avisos de SENAMHI en esta zona. Toca para verlos.`;

// Montos por subregión que da SENAMHI para ese día (lectura.montos, "todo o nada"): el texto y,
// solo en mm, una barra sobre una escala redonda.
const ESCALAS = [10, 20, 30, 50, 80, 100, 150, 200];
function textoMonto(m) {
  const u = m.unidad === "cm" ? "cm" : "mm";
  if (m.forma === "rango") return `${numero(m.desde)} a ${numero(m.hasta)} ${u}`;
  if (m.forma === "hasta") return `hasta ${numero(m.hasta)} ${u}`;
  if (m.forma === "cerca") return `cerca de ${numero(m.hasta)} ${u}`;
  return `más de ${numero(m.hasta ?? m.desde)} ${u}`;
}
function barra(m, escala) {
  const pct = (v) => Math.max(0, Math.min(100, (v / escala) * 100));
  const v = m.hasta ?? m.desde ?? 0;
  if (m.forma === "rango") return { tipo: "rango", desde: pct(m.desde ?? 0), hasta: pct(m.hasta ?? 0) };
  if (m.forma === "hasta") return { tipo: "hasta", desde: 0, hasta: pct(v) };
  if (m.forma === "cerca") return { tipo: "cerca", desde: pct(v), hasta: pct(v) };
  return { tipo: "mas_de", desde: pct(v), hasta: 100 };
}
export function montosAviso(montos) {
  if (!Array.isArray(montos) || !montos.length) return null;
  const enCm = montos.every((m) => m.unidad === "cm");
  const valores = montos.filter((m) => m.unidad !== "cm").flatMap((m) => [m.desde, m.hasta]).filter((v) => v != null);
  const max = valores.length ? Math.max(...valores) : 0;
  const escala = ESCALAS.find((e) => e >= max) ?? ESCALAS[ESCALAS.length - 1];
  return {
    titulo: enCm ? "Nieve que espera SENAMHI ese día (cm)" : "Lluvia que espera SENAMHI ese día (mm)",
    escala: enCm ? null : escala,
    filas: montos.map((m) => ({
      lugar: m.lugar,
      texto: textoMonto(m),
      barra: m.unidad === "cm" ? null : barra(m, escala),
    })),
    nota: enCm
      ? "Por subregión de todo el aviso, no solo de esta zona."
      : "Por subregión de todo el aviso, no solo de esta zona. 1 mm = 1 litro de agua por metro cuadrado.",
  };
}

// Fila "Rayos": solo lo que el texto permite decir. El rayo en toda la zona (gota_rayo) sale de un
// aviso de una sola región con la frase de descargas afirmativa; si no, se cita a SENAMHI.
function filaRayos(a, lec) {
  if (a.icono === "gota_rayo") {
    const region = lec?.regiones_titulo?.[0];
    const habitual = region === "sierra" || region === "selva" ? ` Son habituales en las lluvias de la ${region}.` : "";
    return { etiqueta: "Rayos", texto: `Posibles en toda la zona, según SENAMHI.${habitual}` };
  }
  if (!lec?.descargas || lec.descargas === "no") return null;
  if (lec.descargas === "condicional") return { etiqueta: "Rayos", texto: "SENAMHI no los descarta:", cita: lec.frase_descargas };
  if (a.icono === "copo") return { etiqueta: "Rayos", texto: "SENAMHI también los menciona." };
  return {
    etiqueta: "Rayos",
    texto: "SENAMHI los menciona en este aviso, pero no queda claro si para toda la zona. Lo que dice:",
    cita: lec.frase_descargas,
  };
}

const sobre = (m) => `Posible en zonas por encima de los ${m} m de altura`;

function filasLectura(a, lec, fen) {
  const filas = [];
  if (lec?.rafagas?.kmh) filas.push({ etiqueta: "Viento", texto: `Ráfagas ${lec.rafagas.forma} ${lec.rafagas.kmh} km/h` });
  const rayos = filaRayos(a, lec);
  if (rayos) filas.push(rayos);
  if (lec?.granizo?.menciona)
    filas.push({ etiqueta: "Granizo", texto: lec.granizo.sobre_m ? sobre(lec.granizo.sobre_m) : "SENAMHI lo menciona" });
  if (fen === "nevada") {
    if (lec?.nieve?.sobre_m) filas.push({ etiqueta: "Nieve", texto: `Por encima de los ${lec.nieve.sobre_m} m de altura, según SENAMHI` });
  } else if (lec?.nieve?.menciona)
    filas.push({ etiqueta: "Nieve", texto: lec.nieve.sobre_m ? sobre(lec.nieve.sobre_m) : "SENAMHI lo menciona" });
  return filas;
}

const oracion = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1).toLowerCase() : "");
export const recortar = (t, n = 320) => (t && t.length > n ? `${t.slice(0, n).replace(/\s+\S*$/, "")}…` : t);
export function tituloAviso(a) {
  if (a.tipo === "lluvia24h") return "Aviso de lluvia para las próximas 24 h";
  return `Aviso N° ${a.numero}: ${oracion(a.titulo)}`;
}

// Contenido del popup de un aviso. forma: "lluvia" (meteorológico de lluvia, llovizna o nevada),
// "24h" (aviso de corto plazo) u "otro" (calor, frío, viento: el popup de siempre con su insignia).
// `mapas` = cuántos días (mapas) tiene el aviso, para "(día 1 de 2)".
export function textoAviso(a, { hoy = fechaPeru(), mapas = 1 } = {}) {
  const color = COLOR_NIVEL[a.nivel];
  // en el popup, un aviso de lluvia aún sin ícono (sin leer o sin la migración) lleva la gota
  const glifo = glifoAviso(a) ?? (a.tema === "lluvia" ? "gota" : null);
  const base = { clave: claveAviso(a), nivel: a.nivel, color, glifo, url: a.url ?? null };
  const deptos = a.departamentos?.length ? a.departamentos.join(", ") : null;

  if (a.tipo === "lluvia24h") {
    const ini = fechaPeru(a.inicio);
    const fin = fechaPeru(a.fin);
    return {
      ...base,
      forma: "24h",
      cabecera: `Aviso ${color} de SENAMHI · lluvia en 24 horas`,
      subtitulo: `Desde las ${hhmmPeru(a.inicio)} del ${diaMesCorto(ini)} hasta las ${hhmmPeru(a.fin)} del ${diaMesCorto(fin)}`,
      caja: [
        `Puede llover en algún momento en esta zona en esas 24 horas, con intensidad ${INTENSIDAD_24H[a.nivel]} según SENAMHI.`,
        "No quiere decir que llueva en toda la zona.",
      ],
      filas:
        a.nivel >= 3
          ? [{ etiqueta: "Puede causar", texto: a.nivel === 3 ? "aniegos e inundaciones" : "inundaciones" }]
          : [],
      oficial: { general: a.descripcion ?? null, dia: null },
      firma: FIRMA_AVISO,
    };
  }

  if (a.tema !== "lluvia") {
    return {
      ...base,
      forma: "otro",
      cabecera: tituloAviso(a),
      meta: [`Nivel ${color}`, deptos].filter(Boolean).join(" · "),
      resumen: `Rige desde ${momentoPeru(a.inicio)} hasta ${momentoPeru(a.fin)}.`,
      nota: `${recortar(a.descripcion) ?? ""} Basado en el aviso de SENAMHI.`.trim(),
    };
  }

  const lec = a.lectura ?? null;
  const fen = fenomenoDe(a);
  const fecha = fechaMapa(a);
  const cl = cuandoLargo(fecha, hoy);
  const caja =
    fen === "nevada"
      ? [`Puede nevar en algún momento en las partes altas de esta zona ${cl}.`, "No quiere decir que nieve en toda la zona ni todo el día."]
      : fen === "llovizna"
        ? [`Puede lloviznar en algún momento en esta zona ${cl}.`, NO_TODA]
        : a.icono === "gota_rayo"
          ? [`Puede llover, con rayos, en algún momento en esta zona ${cl}.`, NO_TODA]
          : [`Puede llover en algún momento en esta zona ${cl}.`, NO_TODA];
  const montos = montosAviso(lec?.montos);
  return {
    ...base,
    forma: "lluvia",
    cabecera: `Aviso ${color} de SENAMHI`,
    subtitulo: `N° ${a.numero} · ${fechaLarga(fecha)}${mapas > 1 ? ` (día ${a.mapa} de ${mapas})` : ""}`,
    titulo: `${FENOMENO[fen] ?? "Lluvias"}${lec?.intensidad ? ` ${lec.intensidad}` : ""}`,
    donde: [lec?.donde ? `En ${lec.donde}` : null, deptos].filter(Boolean).join(" · ") || null,
    caja,
    montos,
    literal: !montos && a.texto_dia ? { titulo: "Lo que dice SENAMHI para ese día", texto: a.texto_dia } : null,
    filas: filasLectura(a, lec, fen),
    oficial: { general: a.descripcion ?? null, dia: a.texto_dia ?? null },
    firma: FIRMA_AVISO,
  };
}
