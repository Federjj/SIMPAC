import test from "node:test";
import assert from "node:assert/strict";
import { conMemoria, elegirLugares, medioTexto } from "./rotuloBusqueda.js";

// Una guía recta horizontal de `largo` px que empieza en (x0, y0), en coordenadas de capa.
const recta = (x0, y0) => (l) => ({ x: x0 + l, y: y0 });

function contexto(extra = {}) {
  let llamadas = 0;
  const base = recta(100, 300);
  const punto = conMemoria((l) => {
    llamadas++;
    return base(l);
  }, 1000);
  return {
    ctx: {
      largo: 1000,
      punto,
      origen: { x: 0, y: 0 },
      tam: { x: 1200, y: 800 },
      cajas: [],
      lejos: [],
      lejosPx: 90,
      entrePx: 260,
      repetir: 2,
      medio: medioTexto("Mashcón"),
      dy: -9,
      ...extra,
    },
    llamadas: () => llamadas,
  };
}

test("sobre una recta a la vista elige hasta `repetir` lugares, separados entrePx o más", () => {
  const { ctx } = contexto();
  const { elegidos, iguales } = elegirLugares(ctx);
  assert.equal(elegidos.length, 2);
  assert.equal(iguales, false);
  assert.ok(Math.abs(elegidos[1] - elegidos[0]) * ctx.largo >= 260);
  for (const f of elegidos) assert.ok(f >= 0.06 && f <= 0.94);
});

test("la memoria por largo entero evita repetir getPointAtLength: una pasada pide cada punto una vez", () => {
  const { ctx, llamadas } = contexto();
  elegirLugares(ctx);
  // recta() mira cada 8 px (rumbo en l-3 y l+3) y libre() cada 10 px: con 1000 px de guía no puede
  // haber más puntos distintos que largo + 1, y sin memoria serían miles
  assert.ok(llamadas() <= 1001, `pidió ${llamadas()} puntos`);
  assert.ok(llamadas() > 0);
});

test("evita los puntos a evitar (lejosPx) y lo que tapa el mapa (cajas)", () => {
  // una caja que tapa la mitad izquierda de la vista y un punto a evitar en el centro del trazo
  const { ctx } = contexto({ cajas: [{ x0: 0, y0: 0, x1: 600, y1: 800 }], lejos: [{ x: 850, y: 300 }] });
  const { elegidos } = elegirLugares(ctx);
  assert.ok(elegidos.length >= 1);
  for (const f of elegidos) {
    const x = 100 + f * 1000;
    assert.ok(x - ctx.medio > 600, "el texto no entra en la caja");
    assert.ok(Math.abs(x - 850) >= 90, "queda lejos del punto a evitar");
  }
});

test("tras un arrastre, si los rótulos previos siguen libres los devuelve iguales con pocas llamadas", () => {
  const { ctx } = contexto();
  const { elegidos } = elegirLugares(ctx);
  const otra = contexto();
  const { elegidos: e2, iguales } = elegirLugares(otra.ctx, elegidos);
  assert.equal(iguales, true);
  assert.deepEqual(e2, elegidos);
  assert.ok(otra.llamadas() < 60, `pidió ${otra.llamadas()} puntos`);
});

test("si un rótulo previo quedó fuera de la vista o tapado, vuelve a buscar", () => {
  const { ctx } = contexto();
  const { elegidos } = elegirLugares(ctx);
  // la vista se corrió: el primero queda fuera
  const movida = contexto({ origen: { x: 100 + elegidos[0] * 1000 + 40, y: 0 } });
  const r = elegirLugares(movida.ctx, elegidos);
  assert.equal(r.iguales, false);
  for (const f of r.elegidos) assert.ok(100 + f * 1000 - movida.ctx.medio > movida.ctx.origen.x + 8);
  // o un panel se abrió encima del segundo
  const x1 = 100 + elegidos[1] * 1000;
  const tapada = contexto({ cajas: [{ x0: x1 - 20, y0: 0, x1: x1 + 20, y1: 800 }] });
  assert.equal(elegirLugares(tapada.ctx, elegidos).iguales, false);
});

test("en una curva cerrada no escribe (las letras se encimarían)", () => {
  // un círculo de radio 40 px: largo ~251 px, gira más de 90° en cualquier tramo del texto
  const R = 40;
  const circulo = (l) => ({ x: 300 + R * Math.cos(l / R), y: 300 + R * Math.sin(l / R) });
  const { ctx } = contexto();
  ctx.largo = Math.round(2 * Math.PI * R);
  ctx.punto = conMemoria(circulo, ctx.largo);
  ctx.medio = medioTexto("Mashcón");
  assert.deepEqual(elegirLugares(ctx).elegidos, []);
});
