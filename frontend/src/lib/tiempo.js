// Fechas y horas siempre en hora de Perú (no la del dispositivo: un celular con otra
// zona horaria mostraría las horas corridas).
const PERU = "America/Lima";

const dia = (d) => d.toLocaleDateString("es-PE", { timeZone: PERU });

// "14:05" si es de hoy; "21 sept 14:05" si es de otro día.
export function horaPeru(fecha) {
  const d = new Date(fecha);
  const hhmm = d.toLocaleTimeString("es-PE", { timeZone: PERU, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  if (dia(d) === dia(new Date())) return hhmm;
  return `${d.toLocaleDateString("es-PE", { timeZone: PERU, day: "numeric", month: "short" })} ${hhmm}`;
}

// Horas enteras desde una fecha (para avisar de datos desactualizados).
export function horasDesde(fecha) {
  return Math.floor((Date.now() - new Date(fecha).getTime()) / 3_600_000);
}
