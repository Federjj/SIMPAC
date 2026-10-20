// Medidor de caudal frente a sus umbrales (components/MedidorCaudal.jsx): la escala del arco, sus
// tramos de color y las marcas, a partir de la fila de caudal_actual (ANA) y de textoRio de
// lib/lenguaje.js. Módulo puro: lo prueba node --test.
//
// Escala de crecida: 0 .. max(umbral_emergencia x 1,25, valor x 1,1); verde hasta el 80 % del
// umbral de alerta ("cerca" es criterio de SIMPAC), ámbar hasta la alerta, naranja hasta la
// emergencia, rojo después. Umbrales de nivel bajo (vaciante, ue < ua): el arco se invierte, rojo a
// la izquierda. Sin umbral de alerta no hay tramos (solo el número); sin medición, arco gris.
import { NIVEL_HEX } from "../map/palette.js";

const VERDE = NIVEL_HEX.normal;
const AMBAR = NIVEL_HEX.aviso;
const NARANJA = NIVEL_HEX.alerta;
const ROJO = NIVEL_HEX.emergencia;
export const GRIS = NIVEL_HEX.sin_dato;

const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });

// -> { modo: "crecida"|"bajo"|"sin_umbral"|"sin_medicion", max, fraccion (0..1), tramos:
//      [{ desde, hasta, color }], marcas: [{ valor, texto, fraccion }] }
export function escalaMedidor(c) {
  const valor = c?.valor;
  const ua = c?.umbral_alerta;
  const ue = c?.umbral_emergencia;
  if (valor == null) return { modo: "sin_medicion", max: null, fraccion: 0, tramos: [], marcas: [] };
  if (ua == null) {
    const max = Math.max(valor * 1.25, 1e-9);
    return { modo: "sin_umbral", max, fraccion: Math.min(1, valor / max), tramos: [], marcas: [] };
  }
  if (ue != null && ue < ua) {
    // vaciante: el peligro es que baje
    const max = Math.max(ua * 1.5, valor * 1.1);
    const tramos = [
      { desde: 0, hasta: ue, color: ROJO },
      { desde: ue, hasta: ua, color: NARANJA },
      { desde: ua, hasta: Math.min(max, ua + 0.5), color: AMBAR },
      { desde: Math.min(max, ua + 0.5), hasta: max, color: VERDE },
    ];
    const marcas = [
      { valor: ua, texto: `alerta ${num(ua)}`, fraccion: ua / max },
      { valor: ue, texto: `emergencia ${num(ue)}`, fraccion: ue / max },
    ];
    return { modo: "bajo", max, fraccion: Math.min(1, valor / max), tramos, marcas };
  }
  const max = Math.max((ue ?? ua) * 1.25, valor * 1.1);
  const cerca = Math.round(ua * 0.8 * 1000) / 1000; // sin colas de coma flotante (14 x 0,8 = 11,2)
  const tramos = [
    { desde: 0, hasta: cerca, color: VERDE },
    { desde: cerca, hasta: ua, color: AMBAR },
    ue != null ? { desde: ua, hasta: ue, color: NARANJA } : { desde: ua, hasta: max, color: NARANJA },
    ...(ue != null ? [{ desde: ue, hasta: max, color: ROJO }] : []),
  ];
  const marcas = [{ valor: ua, texto: `alerta ${num(ua)}`, fraccion: ua / max }];
  if (ue != null) marcas.push({ valor: ue, texto: `emergencia ${num(ue)}`, fraccion: ue / max });
  return { modo: "crecida", max, fraccion: Math.min(1, valor / max), tramos, marcas };
}

// Punto del semicírculo (de izquierda a derecha por arriba) para una fracción 0..1.
export function puntoArco(cx, cy, r, f) {
  const a = Math.PI * (1 - Math.min(1, Math.max(0, f)));
  return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
}

// Trazo SVG del arco entre dos fracciones del semicírculo.
export function trazoArco(cx, cy, r, f0, f1) {
  const [x0, y0] = puntoArco(cx, cy, r, f0);
  const [x1, y1] = puntoArco(cx, cy, r, f1);
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

// Giro de la aguja en grados (0 = izquierda, 180 = derecha; se aplica con rotate desde -90).
export const anguloAguja = (f) => -90 + 180 * Math.min(1, Math.max(0, f));

// Color del estado del río (textoRio.estado) para el arco de progreso y el número.
export const COLOR_ESTADO = { normal: VERDE, atento: AMBAR, alerta: NARANJA, emergencia: ROJO, sd: GRIS };
