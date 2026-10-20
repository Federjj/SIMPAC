import test from "node:test";
import assert from "node:assert/strict";
import { NIVEL_HEX } from "../map/palette.js";
import { COLOR_ESTADO, GRIS, anguloAguja, escalaMedidor, puntoArco, trazoArco } from "./medidor.js";

const MASHCON = { valor: 0.13, unidad: "m³/s", umbral_alerta: 14, umbral_emergencia: 18 };

test("escala de crecida: 0 a 1,25 veces la emergencia, con 4 tramos y 2 marcas", () => {
  const e = escalaMedidor(MASHCON);
  assert.equal(e.modo, "crecida");
  assert.equal(e.max, 22.5);
  assert.ok(Math.abs(e.fraccion - 0.13 / 22.5) < 1e-9);
  assert.deepEqual(
    e.tramos.map((t) => [t.desde, t.hasta, t.color]),
    [
      [0, 11.2, NIVEL_HEX.normal],
      [11.2, 14, NIVEL_HEX.aviso],
      [14, 18, NIVEL_HEX.alerta],
      [18, 22.5, NIVEL_HEX.emergencia],
    ]
  );
  assert.deepEqual(
    e.marcas.map((m) => [m.texto, m.fraccion]),
    [
      ["alerta 14", 14 / 22.5],
      ["emergencia 18", 18 / 22.5],
    ]
  );
  // los tramos cubren la escala sin huecos
  for (let i = 1; i < e.tramos.length; i++) assert.equal(e.tramos[i].desde, e.tramos[i - 1].hasta);
});

test("escala: un valor por encima de la escala la estira (nunca se sale del arco)", () => {
  const e = escalaMedidor({ ...MASHCON, valor: 30 });
  assert.equal(e.max, 33);
  assert.ok(e.fraccion <= 1);
  assert.equal(e.tramos.at(-1).hasta, 33);
  // sin umbral de emergencia: naranja hasta el final y una sola marca
  const sinUe = escalaMedidor({ ...MASHCON, umbral_emergencia: null });
  assert.equal(sinUe.max, 17.5);
  assert.equal(sinUe.tramos.length, 3);
  assert.equal(sinUe.tramos.at(-1).color, NIVEL_HEX.alerta);
  assert.equal(sinUe.marcas.length, 1);
});

test("escala de nivel bajo (vaciante): el rojo queda a la izquierda", () => {
  const e = escalaMedidor({ valor: 2.4, unidad: "m", umbral_alerta: 2, umbral_emergencia: 1.5 });
  assert.equal(e.modo, "bajo");
  assert.equal(e.tramos[0].color, NIVEL_HEX.emergencia);
  assert.equal(e.tramos[0].hasta, 1.5);
  assert.equal(e.tramos[1].color, NIVEL_HEX.alerta);
  assert.equal(e.tramos.at(-1).color, NIVEL_HEX.normal);
  assert.match(e.marcas[1].texto, /^emergencia 1[,.]5$/); // la coma depende del ICU de Node
});

test("escala: sin medición y sin umbral de alerta", () => {
  const sin = escalaMedidor({ ...MASHCON, valor: null });
  assert.equal(sin.modo, "sin_medicion");
  assert.equal(sin.fraccion, 0);
  assert.equal(sin.tramos.length, 0);
  const sinUa = escalaMedidor({ valor: 3.2, unidad: "m", umbral_alerta: null, umbral_emergencia: null });
  assert.equal(sinUa.modo, "sin_umbral");
  assert.equal(sinUa.tramos.length, 0);
  assert.equal(sinUa.marcas.length, 0);
  assert.ok(sinUa.fraccion > 0.79 && sinUa.fraccion < 0.81);
  assert.equal(escalaMedidor(null).modo, "sin_medicion");
});

test("geometría del semicírculo: extremos, centro, aguja y trazo", () => {
  const [x0, y0] = puntoArco(160, 160, 100, 0);
  assert.ok(Math.abs(x0 - 60) < 1e-9 && Math.abs(y0 - 160) < 1e-9);
  const [x1, y1] = puntoArco(160, 160, 100, 1);
  assert.ok(Math.abs(x1 - 260) < 1e-9 && Math.abs(y1 - 160) < 1e-9);
  const [xm, ym] = puntoArco(160, 160, 100, 0.5);
  assert.ok(Math.abs(xm - 160) < 1e-9 && Math.abs(ym - 60) < 1e-9);
  assert.equal(anguloAguja(0), -90);
  assert.equal(anguloAguja(0.5), 0);
  assert.equal(anguloAguja(1), 90);
  assert.equal(anguloAguja(7), 90); // se corta en el tope
  assert.equal(trazoArco(160, 160, 100, 0, 0.5), "M 60.00 160.00 A 100 100 0 0 1 160.00 60.00");
  assert.equal(COLOR_ESTADO.sd, GRIS);
  assert.equal(COLOR_ESTADO.emergencia, NIVEL_HEX.emergencia);
});
