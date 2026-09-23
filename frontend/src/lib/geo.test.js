import test from "node:test";
import assert from "node:assert/strict";
import { cajaDeAnillo, dentroDe, dentroDeAnillo, haversineKm } from "./geo.js";

// Cuadrado de 0 a 10 con un hueco de 4 a 6, más un segundo polígono lejos (MultiPolygon).
const exterior = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]];
const hueco = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]];
const multi = { type: "MultiPolygon", coordinates: [[exterior, hueco], [[[20, 20], [22, 20], [22, 22], [20, 22], [20, 20]]]] };

test("punto dentro, fuera y en un hueco", () => {
  assert.equal(dentroDe(2, 2, multi), true);
  assert.equal(dentroDe(21, 21, multi), true); // segundo polígono
  assert.equal(dentroDe(15, 15, multi), false);
  assert.equal(dentroDe(5, 5, multi), false); // en el hueco
  assert.equal(dentroDe(2, 2, { type: "Polygon", coordinates: [exterior, hueco] }), true);
  assert.equal(dentroDe(5, 5, { type: "Feature", geometry: { type: "Polygon", coordinates: [exterior, hueco] } }), false);
  assert.equal(dentroDe(2, 2, null), false);
  assert.equal(dentroDeAnillo(5, 5, exterior), true);
  assert.deepEqual(cajaDeAnillo(exterior), [0, 0, 10, 10]);
});

test("haversine de Cajamarca a Jaén (puntos de SENAMHI)", () => {
  // Cajamarca (estación Augusto Weberbauer) y Jaén: unos 169 km en línea recta
  const km = haversineKm(-7.1675, -78.4931, -5.67664, -78.77416);
  assert.ok(Math.abs(km - 169) <= 5, `${km}`);
  assert.equal(haversineKm(-7, -78, -7, -78), 0);
});
