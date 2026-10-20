import test from "node:test";
import assert from "node:assert/strict";
import { codDeEstacion, escalaBarras, estacionesCercanas, resumenSerie, serie24, textoKm } from "./serie24h.js";

const CAJ = [-7.1617, -78.5127];
const EST = [
  { nombre: "AUGUSTO WEBERBAUER", departamento: "Cajamarca", lat: -7.167, lon: -78.495, pp_1h: 0, pp_6h: 0.4, umbral_1h: 1, umbral_6h: 4 },
  { nombre: "CELENDIN", departamento: "Cajamarca", lat: -7.0, lon: -78.45, pp_1h: 2.2, pp_6h: 9.1, umbral_1h: 1, umbral_6h: 4 },
  { nombre: "SIN REFERENCIA", departamento: "Cajamarca", lat: -7.16, lon: -78.51, pp_1h: 0.5, pp_6h: null, umbral_1h: null, umbral_6h: null },
  { nombre: "PIURA M", departamento: "Piura", lat: -5.19, lon: -80.63, pp_1h: 0, pp_6h: 0, umbral_1h: 1, umbral_6h: 5 },
];

test("estaciones cercanas: evaluables, ordenadas por distancia, con km y si pasaron la referencia", () => {
  const c = estacionesCercanas(EST, ...CAJ, { n: 3 });
  assert.equal(c.length, 2); // la sin referencia no cuenta; Piura queda a más de 30 km (Celendín real está a 52 km: aquí se acerca para la prueba)
  assert.equal(c[0].corto, "Augusto Weberbauer");
  assert.ok(c[0].km > 1.5 && c[0].km < 2.5, `${c[0].km}`);
  assert.equal(c[0].pasa, false);
  assert.equal(c[1].corto, "Celendin");
  assert.equal(c[1].pasa, true);
  assert.equal(c[1].lejos, undefined);
  // ninguna a menos de 30 km: la más cercana con lejos: true
  const lejos = estacionesCercanas(EST, -5.4, -80.4);
  assert.equal(lejos.length, 1);
  assert.equal(lejos[0].lejos, true);
  assert.equal(lejos[0].corto, "Piura");
  assert.deepEqual(estacionesCercanas(EST, null, null), []);
  assert.deepEqual(estacionesCercanas([], ...CAJ), []);
});

test("textos y escala de las barras", () => {
  assert.equal(textoKm(0.42), "420 m");
  assert.match(textoKm(2.26), /^2[,.]3 km$/);
  assert.equal(textoKm(45.4), "45 km");
  assert.equal(textoKm(null), null);
  const e = escalaBarras([0, 2.2, null], 1);
  assert.equal(e.max, 2.2);
  assert.equal(e.fraccion(2.2), 1);
  assert.equal(e.fraccion(null), 0);
  assert.ok(Math.abs(e.fraccionRef - 1 / 2.2) < 1e-9);
  // con poca lluvia la escala es la referencia x 1,5 (la marca cae dentro)
  const chica = escalaBarras([0, 0.2], 1);
  assert.equal(chica.max, 1.5);
  assert.equal(escalaBarras([], null).fraccionRef, null);
});

test("serie de 24 h: una barra por hora, huecos en null y la última fila gana", () => {
  const ahora = Date.parse("2026-10-14T07:20:00Z"); // 02:20 en el Perú
  const filas = [
    { cod: "A", medido_en: "2026-10-13T21:00:00Z", precip_mm: 3.5, estacion: { nombre: "CELENDIN" } },
    { cod: "A", medido_en: "2026-10-13T21:00:00Z", precip_mm: 4.0, estacion: { nombre: "CELENDIN" } }, // reenvío
    { cod: "A", medido_en: "2026-10-14T06:00:00Z", precip_mm: 0, estacion: { nombre: "CELENDIN" } },
    { cod: "A", medido_en: "2026-10-14T07:00:00Z", precip_mm: 0.2, estacion: { nombre: "CELENDIN" } },
    { cod: "A", medido_en: "2026-10-14T05:00:00Z", precip_mm: null, estacion: { nombre: "CELENDIN" } }, // sin dato
    { cod: "B", medido_en: "2026-10-14T06:00:00Z", precip_mm: 9, estacion: { nombre: "OTRA" } },
  ];
  const s = serie24(filas, "A", ahora);
  assert.equal(s.length, 24);
  // la última barra es la hora que cerró a las 07:00Z (06:00-07:00)
  assert.equal(s[23].hora.toISOString(), "2026-10-14T06:00:00.000Z");
  assert.equal(s[23].mm, 0.2);
  assert.equal(s[22].mm, 0);
  assert.equal(s[21].mm, null); // 05:00Z venía sin dato
  const de21 = s.find((b) => b.hora.toISOString() === "2026-10-13T20:00:00.000Z");
  assert.equal(de21.mm, 4.0);
  assert.equal(s[0].hora.toISOString(), "2026-10-13T07:00:00.000Z");
  assert.equal(s.filter((b) => b.mm != null).length, 3);
  const r = resumenSerie(s);
  assert.equal(r.total, 4.2);
  assert.equal(r.conDato, 3);
  assert.equal(r.pico.mm, 4.0);
  assert.equal(r.pico.clase, "moderada");
  // sin lluvia no hay pico
  assert.equal(resumenSerie([{ hora: new Date(), mm: 0 }]).pico, null);
  assert.equal(resumenSerie([]).conDato, 0);
  assert.equal(codDeEstacion(filas, "Celendín"), "A");
  assert.equal(codDeEstacion(filas, "OTRA M"), "B");
  assert.equal(codDeEstacion(filas, "NO EXISTE"), null);
});
