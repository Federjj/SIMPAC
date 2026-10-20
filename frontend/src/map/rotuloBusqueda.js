// Búsqueda del lugar para un texto sobre una línea (map/rotuloLinea.js): dónde cabe entero, a la
// vista, lejos de lo que tapa el mapa y sin curvas cerradas. Módulo puro (sin Leaflet ni DOM): lo
// leen también las pruebas con node --test. Las constantes son las mismas que explica rotuloLinea.js.
const ANCHO_LETRA = 7.5; // px por letra (12 px, seminegrita, con espaciado)
const MAX_GIRO = Math.PI / 2; // en todo el texto

// Medio largo del texto sobre la línea, en px.
export const medioTexto = (texto) => (texto.length * ANCHO_LETRA) / 2 + 6;

// punto(l) con memoria por largo entero: en una pasada el mismo punto se pedía unas 5 veces.
export function conMemoria(puntoEn, largo) {
  const memo = new Map();
  return (l) => {
    const k = Math.round(Math.max(0, Math.min(largo, l)));
    let p = memo.get(k);
    if (!p) {
      p = puntoEn(k);
      memo.set(k, p);
    }
    return p;
  };
}

// Busca dónde escribir el texto. Pura: no toca el DOM. Devuelve las posiciones (fracción del largo).
//   ctx: { largo, punto(l) -> {x, y} (en coordenadas de capa), origen {x, y} (la esquina de la vista
//         en esas coordenadas), tam {x, y} (tamaño de la vista), cajas [{x0, y0, x1, y1}] (lo que tapa
//         el mapa, en px de la vista), lejos [{x, y}] (puntos a evitar), lejosPx, entrePx, repetir,
//         medio (medioTexto), dy }
//   previos: las posiciones de la pasada anterior con el mismo zoom; si todas siguen a la vista y
//            libres se devuelven tal cual (unas 40 llamadas a punto en vez de miles) y `iguales` es
//            true, para no tocar el DOM.
export function elegirLugares(ctx, previos = null) {
  const { largo, punto, origen, tam, cajas, lejos, lejosPx, entrePx, repetir, medio, dy } = ctx;
  // todo el texto (cada ~10 px a lo largo, corrido `dy`) a la vista y fuera de chips y paneles
  const libre = (l0) => {
    for (let l = l0 - medio; l <= l0 + medio; l += 10) {
      const q = punto(l);
      const x = q.x - origen.x;
      const y = q.y - origen.y + dy;
      if (x < 8 || y < 8 || x > tam.x - 8 || y > tam.y - 8) return false;
      if (cajas.some((c) => x > c.x0 && x < c.x1 && y > c.y0 && y < c.y1)) return false;
    }
    return true;
  };
  const cerca = (l) => {
    const q = punto(l);
    return lejos.some((p) => Math.hypot(q.x - p.x, q.y - p.y) < lejosPx);
  };
  if (previos?.length && previos.every((f) => !cerca(f * largo) && libre(f * largo))) {
    return { elegidos: previos, iguales: true };
  }
  const rumbo = (l) => {
    const a = punto(l - 3);
    const b = punto(l + 3);
    return Math.atan2(b.y - a.y, b.x - a.x);
  };
  // lo más que puede girar la guía en 16 px sin que las letras se enciman (a la altura de su centro)
  const maxLocal = 2.5 / (Math.abs(dy) + 4);
  // cuánto gira la guía de l a l + 16 (con signo: en la pantalla, negativo = hacia la izquierda del
  // avance, que es el lado del texto si dy < 0)
  const doblez = (l) => {
    const d = rumbo(l + 16) - rumbo(l);
    return Math.atan2(Math.sin(d), Math.cos(d));
  };
  const haciaElTexto = (g) => (dy < 0 ? g < 0 : g > 0);
  // false si entre l0 y l1 la guía tiene un quiebre cerrado o gira demasiado en total
  const recta = (l0, l1) => {
    let total = 0;
    for (let i = 0, l = l0; l + 16 <= l1; i++, l += 8) {
      const g = doblez(l);
      if (Math.abs(g) > (haciaElTexto(g) ? maxLocal : 3 * maxLocal)) return false;
      if (i % 2 === 0) total += Math.abs(g); // tramos de 16 px seguidos, sin contar dos veces
    }
    return total <= MAX_GIRO;
  };
  const elegidos = [];
  for (let f = 0.06; f <= 0.94 && elegidos.length < repetir; f += 0.03) {
    const l = f * largo;
    if (l - medio < 0 || l + medio > largo) continue;
    if (cerca(l)) continue;
    if (elegidos.some((g) => Math.abs(g - f) * largo < entrePx)) continue;
    if (!recta(Math.max(3, l - medio - 6), Math.min(largo - 3, l + medio + 6))) continue;
    if (!libre(l)) continue;
    elegidos.push(f);
  }
  return { elegidos, iguales: false };
}
