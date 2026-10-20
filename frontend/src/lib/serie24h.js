// "Lluvia cerca de ti" (components/BarrasLluvia.jsx): qué estaciones de SENAMHI mostrar y la serie
// de 24 barras de la más cercana. Módulo puro (sin React): lo prueba node --test.
//
// Entradas: las filas de lluvia_senamhi_actual (lib/queries.js getLluviaAhora: nombre, departamento,
// lat, lon, pp_1h, pp_6h, umbral_1h, umbral_6h, ts) y las de lectura_lluvia de las últimas 24 h
// (getLluvia24h(depto): cod, medido_en, precip_mm, estacion.nombre). Una hora sin fila es un hueco
// (null), nunca un cero: "no hay dato" no es "no llovió".
import { haversineKm } from "./geo.js";
import { intensidad, nombreEstacion, referenciaLluvia } from "./lenguaje.js";

export const CERCA_KM = 30;
const HORA_MS = 3_600_000;

// Las `n` estaciones evaluables (lluvia de la última hora y referencia de SENAMHI) más cercanas a
// (lat, lon), con km y si pasaron la referencia. Si ninguna queda a menos de CERCA_KM se devuelve
// igual la más cercana con `lejos: true` (la tarjeta lo dice). [] sin estaciones o sin origen.
export function estacionesCercanas(estaciones = [], lat, lon, { n = 3, maxKm = CERCA_KM } = {}) {
  if (lat == null || lon == null) return [];
  const lista = (estaciones ?? [])
    .filter((e) => e.lat != null && e.lon != null && referenciaLluvia(e).evaluable)
    .map((e) => ({ ...e, km: haversineKm(lat, lon, e.lat, e.lon), pasa: referenciaLluvia(e).pasa, corto: nombreEstacion(e.nombre ?? "") }))
    .sort((a, b) => a.km - b.km);
  if (!lista.length) return [];
  const cerca = lista.filter((e) => e.km <= maxKm).slice(0, n);
  return cerca.length ? cerca : [{ ...lista[0], lejos: true }];
}

// "2 km" / "850 m" / "45 km"
export function textoKm(km) {
  if (km == null || !Number.isFinite(km)) return null;
  if (km < 1) return `${Math.max(10, Math.round((km * 1000) / 10) * 10)} m`;
  return `${km < 10 ? km.toLocaleString("es-PE", { maximumFractionDigits: 1 }) : Math.round(km)} km`;
}

// Alto de una barra como fracción 0..1 de la escala: la escala es la referencia x 1,5 o el mayor
// valor visto, lo que sea más (así la marca de la referencia siempre cae dentro del gráfico).
export function escalaBarras(valores = [], referencia = null) {
  const max = Math.max(...valores.filter((v) => v != null), referencia != null ? referencia * 1.5 : 0, 1);
  return { max, fraccion: (v) => (v == null ? 0 : Math.min(1, Math.max(0, v / max))), fraccionRef: referencia != null ? Math.min(1, referencia / max) : null };
}

// Serie de 24 horas de UNA estación (su `cod`), de hace 24 h a ahora, una barra por hora cerrada:
// [{ hora: Date (inicio de la hora, UTC), mm: number|null }]. Las horas sin fila quedan en null.
// Si una hora trae más de una fila (reenvíos de SENAMHI) se toma la última.
export function serie24(filas = [], cod, ahora = Date.now()) {
  const fin = Math.floor(ahora / HORA_MS) * HORA_MS; // la hora en curso no se cuenta: no cerró
  const porHora = new Map();
  for (const f of filas ?? []) {
    if (f.cod !== cod || f.precip_mm == null) continue;
    const t = Date.parse(f.medido_en);
    if (!Number.isFinite(t)) continue;
    // la lectura de las 16:00 cubre la hora que terminó a las 16:00 -> va en la barra 15:00-16:00
    const h = Math.ceil(t / HORA_MS) * HORA_MS - HORA_MS;
    porHora.set(h, Number(f.precip_mm));
  }
  const out = [];
  for (let i = 24; i >= 1; i--) {
    const h = fin - i * HORA_MS;
    out.push({ hora: new Date(h), mm: porHora.has(h) ? porHora.get(h) : null });
  }
  return out;
}

// Resumen de la serie: total, cuántas horas tienen dato, la hora más intensa y su clase.
//   -> { total, conDato, pico: { hora, mm, clase } | null }
export function resumenSerie(serie = []) {
  let total = 0;
  let conDato = 0;
  let pico = null;
  for (const b of serie) {
    if (b.mm == null) continue;
    conDato += 1;
    total += b.mm;
    if (!pico || b.mm > pico.mm) pico = b;
  }
  if (pico && pico.mm <= 0) pico = null;
  return {
    total: Math.round(total * 10) / 10,
    conDato,
    pico: pico ? { hora: pico.hora, mm: pico.mm, clase: intensidad(pico.mm) } : null,
  };
}

// La estación de la serie de 24 h que corresponde a una estación de la última hora: por nombre
// normalizado (lectura_lluvia trae `estacion.nombre` y `cod`; lluvia_senamhi_actual, `nombre`).
const llano = (s) => (s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase().replace(/\s+[MH]$/, "").trim();
export function codDeEstacion(filas = [], nombre) {
  const buscado = llano(nombre);
  if (!buscado) return null;
  const f = (filas ?? []).find((x) => llano(x.estacion?.nombre) === buscado);
  return f?.cod ?? null;
}
