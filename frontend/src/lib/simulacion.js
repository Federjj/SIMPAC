import { simular } from "./zonaRio";

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
