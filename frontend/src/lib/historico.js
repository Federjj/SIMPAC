// Lógica pura del histórico por estación (/historico): parámetros de la ruta, rangos, series
// para el gráfico, escala del eje y el CSV. Sin React ni Supabase (node --test).
import { MESES, fechaPeru } from "./tiempo.js";

export const RANGOS = [
  { id: "24h", label: "24 horas", dias: 1 },
  { id: "7d", label: "7 días", dias: 7 },
  { id: "30d", label: "30 días", dias: 30 },
];
export const RANGO_DEFECTO = "7d";
const DIA_MS = 86_400_000;

// Parámetros de la ruta (?tipo=rio|lluvia&id=...&rio=...&rango=24h|7d|30d) validados.
// `errores` lista lo que faltó o no se entendió; `avisos` lo que se corrigió solo.
export function validarParametros(search) {
  const q = new URLSearchParams(search ?? "");
  const tipo = q.get("tipo");
  const id = (q.get("id") ?? "").trim();
  const rio = (q.get("rio") ?? "").trim() || null;
  const rangoPedido = q.get("rango");
  const errores = [];
  const avisos = [];
  if (tipo !== "rio" && tipo !== "lluvia") errores.push("Falta decir qué histórico quieres ver: de un río o de la lluvia de una estación.");
  if (!id) errores.push("Falta la estación.");
  if (id.length > 80) errores.push("El nombre de la estación es demasiado largo.");
  let rango = RANGO_DEFECTO;
  if (rangoPedido && RANGOS.some((r) => r.id === rangoPedido)) rango = rangoPedido;
  else if (rangoPedido) avisos.push("Ese rango no existe: se muestran los últimos 7 días.");
  return { tipo, id, rio, rango, errores, avisos, ok: errores.length === 0 };
}

// Desde cuándo pedir (ISO) para un rango, y la fecha de Perú "AAAA-MM-DD" para lectura_caudal.
export function desdeRango(rango, ahora = Date.now()) {
  const dias = RANGOS.find((r) => r.id === rango)?.dias ?? 7;
  const ms = ahora - dias * DIA_MS;
  return { ms, iso: new Date(ms).toISOString(), fecha: fechaPeru(new Date(ms)) };
}

// Fila de lectura_caudal (fecha de Perú + "HH:MM") -> instante en ms.
export const instanteCaudal = (f) => Date.parse(`${f.fecha}T${(f.hora ?? "00:00").slice(0, 5)}:00-05:00`);

// Serie del caudal: [{ t, v }] ordenada, solo con valor y dentro del rango; y los umbrales (de la
// última fila que los traiga, o de `actual` si se pasa la fila de caudal_actual).
export function serieCaudal(filas = [], { desdeMs = 0, actual = null } = {}) {
  const puntos = filas
    .filter((f) => f.valor != null)
    .map((f) => ({ t: instanteCaudal(f), v: Number(f.valor), estado: f.estado ?? null }))
    .filter((p) => Number.isFinite(p.t) && p.t >= desdeMs)
    .sort((a, b) => a.t - b.t);
  const conUmbral = [...filas].reverse().find((f) => f.umbral_alerta != null) ?? null;
  const unidad = actual?.unidad ?? filas.find((f) => f.unidad)?.unidad ?? null;
  return {
    puntos,
    unidad,
    umbralAlerta: actual?.umbral_alerta ?? conUmbral?.umbral_alerta ?? null,
    umbralEmergencia: actual?.umbral_emergencia ?? conUmbral?.umbral_emergencia ?? null,
  };
}

// Serie de la lluvia horaria: [{ t, mm, temp }] ordenada (mm nulo = sin dato, no "no llovió").
export function serieLluvia(filas = [], { desdeMs = 0 } = {}) {
  const puntos = filas
    .map((f) => ({ t: Date.parse(f.medido_en), mm: f.precip_mm == null ? null : Number(f.precip_mm), temp: f.temp_c == null ? null : Number(f.temp_c) }))
    .filter((p) => Number.isFinite(p.t) && p.t >= desdeMs)
    .sort((a, b) => a.t - b.t);
  const conLluvia = puntos.filter((p) => p.mm != null);
  return {
    puntos,
    totalMm: conLluvia.reduce((s, p) => s + p.mm, 0),
    maxMm: conLluvia.length ? Math.max(...conLluvia.map((p) => p.mm)) : null,
    horasConDato: conLluvia.length,
  };
}

// Resumen del caudal: último, máximo y mínimo del rango.
export function resumenCaudal(puntos = []) {
  if (!puntos.length) return null;
  const ultimo = puntos[puntos.length - 1];
  const max = puntos.reduce((m, p) => (p.v > m.v ? p : m), puntos[0]);
  const min = puntos.reduce((m, p) => (p.v < m.v ? p : m), puntos[0]);
  return { ultimo, max, min };
}

// Escala "bonita" del eje Y que cubre los valores (y los umbrales, si hay): {min, max, ticks}.
export function escalaY(valores = [], { desdeCero = true, pasos = 4 } = {}) {
  const v = valores.filter((x) => Number.isFinite(x));
  if (!v.length) return { min: 0, max: 1, ticks: [0, 0.25, 0.5, 0.75, 1] };
  let min = desdeCero ? Math.min(0, ...v) : Math.min(...v);
  let max = Math.max(...v);
  if (max === min) max = min + (min === 0 ? 1 : Math.abs(min) * 0.1);
  const bruto = (max - min) / pasos;
  const pot = 10 ** Math.floor(Math.log10(bruto));
  const paso = [1, 2, 2.5, 5, 10].map((k) => k * pot).find((p) => p >= bruto) ?? 10 * pot;
  min = Math.floor(min / paso) * paso;
  max = Math.ceil(max / paso) * paso;
  const ticks = [];
  for (let y = min; y <= max + paso / 1e6; y += paso) ticks.push(Number(y.toFixed(10)));
  return { min, max, ticks };
}

// Marcas del eje X: una por día (a medianoche de Perú) si el rango es de días; cada 6 h en 24 h.
export function ticksTiempo(desdeMs, hastaMs, rango) {
  const ticks = [];
  if (!(hastaMs > desdeMs)) return ticks;
  const paso = rango === "24h" ? 6 * 3_600_000 : rango === "7d" ? DIA_MS : 5 * DIA_MS;
  // alinear a la hora de Perú (UTC-5)
  const desfase = 5 * 3_600_000;
  let t = Math.ceil((desdeMs - desfase) / paso) * paso + desfase;
  for (; t <= hastaMs; t += paso) ticks.push(t);
  return ticks;
}

// "22 de setiembre de 2026" (fecha de Perú de un instante o de "AAAA-MM-DD")
export function fechaLargaConAnio(x) {
  const iso = typeof x === "string" && /^\d{4}-\d{2}-\d{2}/.test(x) ? x.slice(0, 10) : fechaPeru(new Date(x));
  const [a, m, d] = iso.split("-").map(Number);
  return `${d} de ${MESES[m - 1]} de ${a}`;
}

// "hoy 14:00", "13 oct 09:00" para la tabla y los ejes
export function horaCorta(ms) {
  const d = new Date(ms);
  const hhmm = d.toLocaleTimeString("es-PE", { timeZone: "America/Lima", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const [, m, dd] = fechaPeru(d).split("-").map(Number);
  return `${dd}/${String(m).padStart(2, "0")} ${hhmm}`;
}

// CSV con punto y coma (Excel en español lo abre bien), valores escapados, UTF-8 con BOM.
export function aCsv(columnas, filas) {
  const celda = (v) => {
    if (v == null) return "";
    const s = String(v);
    return /[;"\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lineas = [columnas.map((c) => celda(c.titulo)).join(";")];
  for (const f of filas) lineas.push(columnas.map((c) => celda(typeof c.valor === "function" ? c.valor(f) : f[c.valor])).join(";"));
  return `﻿${lineas.join("\r\n")}\r\n`;
}

// Nombre del archivo: "simpac_rio_mashcon_7d.csv"
export function nombreCsv(tipo, id, rango) {
  const limpio = (id ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  return `simpac_${tipo}_${limpio || "estacion"}_${rango}.csv`;
}
