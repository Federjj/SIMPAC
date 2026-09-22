// Fechas y horas siempre en hora de Perú (no la del dispositivo: un celular con otra
// zona horaria mostraría las horas corridas).
const PERU = "America/Lima";

export const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre",
];
const MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"];

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

// Horas enteras desde una fecha (para avisar de datos desactualizados).
export function horasDesde(fecha) {
  return Math.floor((Date.now() - new Date(fecha).getTime()) / 3_600_000);
}

// Días enteros desde una fecha "AAAA-MM-DD".
export function diasDesde(iso) {
  return Math.floor((Date.parse(fechaPeru()) - Date.parse(iso)) / 86_400_000);
}
