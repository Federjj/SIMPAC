import { simular } from "./zonaRio.js"; // con extensión: lo importan las pruebas con node --test

// Simulación de los ríos vigilados para probar la interfaz sin esperar una crecida, SOLO con el
// servidor de desarrollo (`npm run dev`, import.meta.env.DEV): en la compilación de producción no
// existe. Se pide en la dirección de la página:
//   ?simular=mashcon:15.4     caudal de ANA (m³/s)
//   ?simular=mashcon:hidro3   aviso hidrológico vigente falso (hidro2 amarillo, hidro3 naranja, hidro4 rojo)
//   ?simular=mashcon:lluvia   RIO GRANDE GORE con 7,2 mm en la última hora
//   ?simular=mashcon:calma    sin avisos ni lluvia sobre la cuenca (un día sin señales)
// (varias con coma). La aplican las capas `rio` y `zona` y useRiosVigilados con simular() de
// lib/zonaRio.js; mientras esté activa, la nota de la capa lo dice.
export const NOTA_SIMULACION = "SIMULACIÓN (solo desarrollo).";

export function parametroSimulacion() {
  if (!import.meta.env.DEV) return null;
  try {
    return new URLSearchParams(window.location.search).get("simular");
  } catch {
    return null;
  }
}

// { rio, caudal, senal, activa } con la simulación aplicada (o tal cual, sin parámetro).
export function conSimulacion(datos) {
  const param = parametroSimulacion();
  return param ? simular(datos, param) : { ...datos, activa: false };
}

// Simulación de un río del país con trazo de ANA (lib/cauces.js estadoRio), también solo en
// desarrollo: "?simular=rio:<rio_ana>:alerta" o "?simular=rio:<rio_ana>:emergencia" (p. ej.
// ?simular=rio:rimac:alerta; varias con coma, junto a las del Mashcón). Cambia las ENTRADAS de
// estadoRio, no su resultado: la peor estación de ANA pasa a medir un 5 % más que su nivel de
// alerta o de emergencia (si tiene umbrales de crecida); si el río no tiene estación con umbrales,
// se agrega un aviso hidrológico de crecida falso (naranja o rojo). Así el trazo, la franja, las
// zonas y la tarjeta reaccionan como con un dato real; la nota de la capa dice SIMULACIÓN.
const NIVEL_RIO = { alerta: { factor: "umbral_alerta", aviso: 3 }, emergencia: { factor: "umbral_emergencia", aviso: 4 } };
export function simularCauce({ rioAna, lecturas = [], avisos_hidro = [] }, param = parametroSimulacion(), ahora = new Date()) {
  const base = { lecturas, avisos_hidro, activa: false };
  if (!param || !rioAna) return base;
  for (const parte of String(param).split(",")) {
    const [tipo, id, nivel] = parte.trim().split(":");
    if (tipo !== "rio" || id !== rioAna || !NIVEL_RIO[nivel]) continue;
    const { factor, aviso } = NIVEL_RIO[nivel];
    // una estación con umbrales de crecida (no de nivel bajo: umbral_emergencia > umbral_alerta)
    const i = lecturas.findIndex((c) => c?.[factor] != null && Number(c.umbral_emergencia) > Number(c.umbral_alerta));
    if (i >= 0) {
      const nuevas = lecturas.slice();
      nuevas[i] = { ...lecturas[i], valor: Math.round(Number(lecturas[i][factor]) * 1.05 * 100) / 100, tendencia: "Ascendente" };
      return { lecturas: nuevas, avisos_hidro, activa: true };
    }
    const falso = {
      ca: -aviso, ce: "SIM", numero: 0, titulo: "SIMULACIÓN", nivel: aviso, sentido: "crecida",
      inicio: new Date(ahora).toISOString(), fin: new Date(new Date(ahora).getTime() + 6 * 3_600_000).toISOString(),
      valor: null, unidad: null, url: "#", visto_en: new Date(ahora).toISOString(),
    };
    return { lecturas, avisos_hidro: [falso, ...avisos_hidro], activa: true };
  }
  return base;
}
