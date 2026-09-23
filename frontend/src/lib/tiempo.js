// Fechas y horas siempre en hora de Perú (no la del dispositivo: un celular con otra
// zona horaria mostraría las horas corridas).
const PERU = "America/Lima";

export const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre",
];
export const MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"];

// "AAAA-MM-DD" de hoy (o de una fecha) en Perú.
export function fechaPeru(d = new Date()) {
  return new Date(d).toLocaleDateString("en-CA", { timeZone: PERU });
}

const dia = (d) => d.toLocaleDateString("es-PE", { timeZone: PERU });

// "14:05" si es de hoy; "21 set 14:05" si es de otro día.
export function horaPeru(fecha) {
  const d = new Date(fecha);
  const hhmm = d.toLocaleTimeString("es-PE", { timeZone: PERU, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  if (dia(d) === dia(new Date())) return hhmm;
  const [, m, dd] = fechaPeru(d).split("-").map(Number);
  return `${dd} ${MESES_CORTOS[m - 1]} ${hhmm}`;
}

// "AAAA-MM-DD" -> "hoy", "ayer" o "14 set" (fechas que ya vienen en hora de Perú).
export function diaLegible(iso) {
  if (!iso) return "";
  const hoy = fechaPeru();
  const ayer = fechaPeru(Date.now() - 86_400_000);
  if (iso === hoy) return "hoy";
  if (iso === ayer) return "ayer";
  const [, m, d] = iso.split("-").map(Number);
  return `${d} ${MESES_CORTOS[m - 1]}`;
}

// "hoy 13:00", "mañana 13:00" o "24 set 23:59" (inicio y fin de un aviso).
export function momentoPeru(fecha) {
  const d = new Date(fecha);
  const hhmm = d.toLocaleTimeString("es-PE", { timeZone: PERU, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const iso = fechaPeru(d);
  const dia = iso === fechaPeru(Date.now() + 86_400_000) ? "mañana" : diaLegible(iso);
  return `${dia} ${hhmm}`;
}

// Horas enteras desde una fecha (para avisar de datos desactualizados).
export function horasDesde(fecha) {
  return Math.floor((Date.now() - new Date(fecha).getTime()) / 3_600_000);
}

// Días enteros desde una fecha "AAAA-MM-DD".
export function diasDesde(iso) {
  return Math.floor((Date.parse(fechaPeru()) - Date.parse(iso)) / 86_400_000);
}

export const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
export const DIAS_CORTOS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

// Día de la semana de una fecha "AAAA-MM-DD" de Perú (al mediodía: nunca cae en otro día).
export const diaSemana = (iso) => new Date(`${iso}T12:00:00-05:00`).getUTCDay();

// "AAAA-MM-DD" -> "miércoles 23 de setiembre"
export function fechaLarga(iso) {
  const [, m, d] = iso.split("-").map(Number);
  return `${DIAS[diaSemana(iso)]} ${d} de ${MESES[m - 1]}`;
}

// "AAAA-MM-DD" -> "mié 23"
export function diaCorto(iso) {
  const d = Number(iso.split("-")[2]);
  return `${DIAS_CORTOS[diaSemana(iso)]} ${d}`;
}

// "AAAA-MM-DD" -> "mié 23 set"
export function diaMesCorto(iso) {
  const m = Number(iso.split("-")[1]);
  return `${diaCorto(iso)} ${MESES_CORTOS[m - 1]}`;
}

// "13:10" en hora de Perú, siempre sin la fecha.
export function hhmmPeru(fecha) {
  return new Date(fecha).toLocaleTimeString("es-PE", { timeZone: PERU, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
}

// Milisegundos -> "hace 8 min", "hace 2 h 45 min", "hace 3 días".
export function textoHace(ms) {
  const min = Math.max(0, Math.floor(ms / 60_000));
  if (min < 1) return "hace menos de 1 min";
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  if (h >= 48) return `hace ${Math.floor(h / 24)} días`;
  return min % 60 ? `hace ${h} h ${min % 60} min` : `hace ${h} h`;
}
