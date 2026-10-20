import test from "node:test";
import assert from "node:assert/strict";
import { BASE_CORTA, fuentesDe, lineaCorta } from "./atribucion.js";

const BASE =
  '© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const SENAMHI = "Datos: SENAMHI";
const NASA = "Lluvia: NASA GPM IMERG, imágenes NASA GIBS (ESDIS)";
const ANA = "Niveles de ríos: ANA";

test("lineaCorta: el mapa base en corto y las fuentes de las capas encendidas, sin repetir", () => {
  assert.equal(lineaCorta([BASE]), BASE_CORTA);
  assert.equal(lineaCorta([BASE, SENAMHI, ANA]), `${BASE_CORTA} · Datos: SENAMHI, ANA`);
  // el satélite suma NASA una sola vez aunque su texto la nombre dos veces
  assert.equal(lineaCorta([BASE, SENAMHI, NASA, ANA]), `${BASE_CORTA} · Datos: SENAMHI, ANA, NASA`);
  // sin mapa base (no debería pasar) la línea no lo inventa
  assert.equal(lineaCorta([SENAMHI]), "Datos: SENAMHI");
  assert.equal(lineaCorta([]), "");
});

test("fuentesDe: deja fuera el mapa base y no confunde 'ANA' con palabras que la contienen", () => {
  assert.deepEqual(fuentesDe([BASE]), []);
  assert.deepEqual(fuentesDe(["Trazo: © colaboradores de OpenStreetMap (ODbL)"]), ["OpenStreetMap"]);
  assert.deepEqual(fuentesDe(["Zonas de CENEPRED y SANACIÓN"]), ["CENEPRED"]);
  assert.deepEqual(fuentesDe([ANA, SENAMHI]), ["SENAMHI", "ANA"]); // siempre en el mismo orden
});
