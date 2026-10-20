import test from "node:test";
import assert from "node:assert/strict";
import {
  aCsv,
  desdeRango,
  escalaY,
  fechaLargaConAnio,
  nombreCsv,
  resumenCaudal,
  serieCaudal,
  serieLluvia,
  ticksTiempo,
  validarParametros,
} from "./historico.js";

const AHORA = Date.parse("2026-10-14T15:00:00-05:00");

test("parámetros de la ruta", () => {
  const p = validarParametros("?tipo=rio&id=Mashc%C3%B3n&rio=Mashc%C3%B3n&rango=30d");
  assert.deepEqual([p.ok, p.tipo, p.id, p.rio, p.rango], [true, "rio", "Mashcón", "Mashcón", "30d"]);
  const q = validarParametros("?tipo=lluvia&id=47E35522&rango=anual");
  assert.equal(q.rango, "7d");
  assert.equal(q.avisos.length, 1);
  const r = validarParametros("?tipo=otro");
  assert.equal(r.ok, false);
  assert.equal(r.errores.length, 2);
  assert.equal(validarParametros("").rio, null);
});

test("desde cuándo según el rango", () => {
  assert.equal(desdeRango("24h", AHORA).fecha, "2026-10-13");
  assert.equal(desdeRango("7d", AHORA).fecha, "2026-10-07");
  assert.equal(desdeRango("30d", AHORA).fecha, "2026-09-14");
  assert.equal(desdeRango("30d", AHORA).ms, AHORA - 30 * 86_400_000);
});

test("serie del caudal con umbrales y resumen", () => {
  const filas = [
    { fecha: "2026-10-13", hora: "18:00", valor: 0.2, unidad: "m³/s", umbral_alerta: 14, umbral_emergencia: 18 },
    { fecha: "2026-10-14", hora: "06:00", valor: null, unidad: "m³/s" },
    { fecha: "2026-10-14", hora: "12:00", valor: 0.9, unidad: "m³/s", umbral_alerta: 14, umbral_emergencia: 18 },
    { fecha: "2026-10-14", hora: "09:00", valor: 0.5, unidad: "m³/s" },
    { fecha: "2026-09-01", hora: "09:00", valor: 3, unidad: "m³/s" }, // fuera del rango
  ];
  const s = serieCaudal(filas, { desdeMs: AHORA - 86_400_000 });
  assert.deepEqual(s.puntos.map((p) => p.v), [0.2, 0.5, 0.9]);
  assert.equal(s.unidad, "m³/s");
  assert.equal(s.umbralAlerta, 14);
  assert.equal(s.umbralEmergencia, 18);
  // la fila de caudal_actual manda sobre el historial
  assert.equal(serieCaudal(filas, { actual: { umbral_alerta: 15, umbral_emergencia: 19, unidad: "m" } }).umbralEmergencia, 19);
  const r = resumenCaudal(s.puntos);
  assert.equal(r.ultimo.v, 0.9);
  assert.equal(r.max.v, 0.9);
  assert.equal(r.min.v, 0.2);
  assert.equal(resumenCaudal([]), null);
  // la hora de Perú se respeta: 12:00 de Lima son las 17:00 UTC
  assert.equal(new Date(s.puntos[2].t).toISOString(), "2026-10-14T17:00:00.000Z");
});

test("serie de la lluvia: nulo es sin dato, no cero", () => {
  const filas = [
    { medido_en: "2026-10-14T14:00:00+00:00", precip_mm: 2.5, temp_c: 14 },
    { medido_en: "2026-10-14T15:00:00+00:00", precip_mm: null, temp_c: null },
    { medido_en: "2026-10-14T16:00:00+00:00", precip_mm: 0, temp_c: 13.2 },
    { medido_en: "2026-10-14T13:00:00+00:00", precip_mm: 1, temp_c: 15 },
  ];
  const s = serieLluvia(filas);
  assert.deepEqual(s.puntos.map((p) => p.mm), [1, 2.5, null, 0]);
  assert.equal(s.totalMm, 3.5);
  assert.equal(s.maxMm, 2.5);
  assert.equal(s.horasConDato, 3);
});

test("escala del eje y marcas del tiempo", () => {
  assert.deepEqual(escalaY([0.2, 0.9, 14, 18]), { min: 0, max: 20, ticks: [0, 5, 10, 15, 20] });
  assert.deepEqual(escalaY([3, 3]).ticks[0], 0);
  assert.deepEqual(escalaY([]).max, 1);
  const e = escalaY([12.4, 15.1], { desdeCero: false });
  assert.ok(e.min <= 12.4 && e.max >= 15.1 && e.ticks.length >= 3);
  const desde = Date.parse("2026-10-13T15:00:00-05:00");
  const t24 = ticksTiempo(desde, AHORA, "24h");
  assert.equal(t24.length, 4); // 18:00, 00:00, 06:00, 12:00 de Perú
  assert.equal(new Date(t24[1]).toISOString(), "2026-10-14T05:00:00.000Z"); // medianoche de Lima
  assert.equal(ticksTiempo(AHORA - 7 * 86_400_000, AHORA, "7d").length, 7);
  assert.deepEqual(ticksTiempo(10, 5, "7d"), []);
});

test("csv y nombres", () => {
  const csv = aCsv(
    [
      { titulo: "fecha", valor: "f" },
      { titulo: "valor; raro", valor: (x) => x.v },
    ],
    [
      { f: "2026-10-14", v: 1.5 },
      { f: 'con "comillas"', v: null },
    ]
  );
  assert.equal(csv, '﻿fecha;"valor; raro"\r\n2026-10-14;1.5\r\n"con ""comillas""";\r\n');
  assert.equal(nombreCsv("rio", "Túnel Chotano", "7d"), "simpac_rio_tunel_chotano_7d.csv");
  assert.equal(nombreCsv("lluvia", "", "24h"), "simpac_lluvia_estacion_24h.csv");
  assert.equal(fechaLargaConAnio("2026-09-22"), "22 de setiembre de 2026");
  assert.equal(fechaLargaConAnio(Date.parse("2026-09-22T23:30:00-05:00")), "22 de setiembre de 2026");
});
