import test from "node:test";
import assert from "node:assert/strict";
import { haversineKm } from "./geo.js";
import {
  aspecto,
  atrasado,
  centroCiudad,
  emitidoTexto,
  etiquetaDia,
  fechaDeOpcion,
  franja,
  localidadCercana,
  notaPronostico,
  pronosticoLocal,
  temps,
} from "./pronostico.js";

// Fila de ejemplo de pronostico_vigente (contrato §3.4 de la especificación).
const CAJAMARCA = {
  codigo: "06-0011", nombre: "Cajamarca", departamento: "Cajamarca", lat: -7.1675, lon: -78.4931, fecha: "2026-09-23",
  emision: "2026-09-22", tmax: 21, tmin: 10,
  texto: "Cielo nublado parcial variando a cielo nublado y cielo cubierto durante el día con lluvia.",
  tipo: "lluvia", posible: false, por: "texto+icono", lluvia_segura: false, granizo: false, intensidad: null,
  momento: null, cielo: null, url: "https://www.senamhi.gob.pe/?p=pronostico-detalle&dp=06&localidad=0011",
};
const fila = (extra) => ({ ...CAJAMARCA, ...extra });

test("aspecto: cada fila de la tabla", () => {
  const casos = [
    [{ tipo: "tormenta", posible: false, momento: "en la tarde" }, "tormenta", "tormenta", false, "Tormenta en la tarde", null],
    [{ tipo: "tormenta", posible: true, lluvia_segura: true }, "tormenta", "tormenta", true, "Lluvia", "puede haber tormenta"],
    [{ tipo: "tormenta", posible: true, lluvia_segura: false }, "tormenta", "tormenta", true, "Puede haber tormenta", null],
    [{ tipo: "nieve", texto: "Cielo cubierto con lluvia y nieve.", granizo: true }, "nieve", "nieve", false, "Nieve", "con granizo"],
    [{ tipo: "nieve", texto: "Cielo nublado con tendencia a nevadas.", posible: true }, "nieve", "nieve", true, "Puede nevar", null],
    [{ tipo: "nieve", texto: "Cielo nublado con granizo en la tarde.", momento: "en la tarde", granizo: true }, "nieve", "nieve", false, "Granizo en la tarde", null],
    [{ tipo: "nieve", texto: "Cielo nublado con tendencia a granizo.", posible: true, granizo: true }, "nieve", "nieve", true, "Puede granizar", null],
    [{ tipo: "lluvia", intensidad: "ligera", momento: "al atardecer" }, "lluvia", "lluvia", false, "Lluvia ligera al atardecer", null],
    [{ tipo: "lluvia" }, "lluvia", "lluvia", false, "Lluvia", null],
    [{ tipo: "lluvia", posible: true, momento: "en la noche" }, "tendencia", "lluvia", true, "Puede llover en la noche", null],
    [{ tipo: "sin_lluvia", cielo: "despejado" }, "sol", "seco", false, "Despejado", null],
    [{ tipo: "sin_lluvia", cielo: "parcial" }, "sol_nube", "seco", false, "Algo nublado", null],
    [{ tipo: "sin_lluvia", cielo: null }, "sol_nube", "seco", false, "Sin lluvia", null],
    [{ tipo: "sin_lluvia", cielo: "nublado" }, "nube", "seco", false, "Nublado", null],
    [{ tipo: "sin_lluvia", cielo: "neblina" }, "nube", "seco", false, "Neblina", null],
  ];
  for (const [datos, glifo, clase, posible, corto, extra] of casos) {
    const a = aspecto(fila(datos));
    assert.deepEqual([a.glifo, a.clase, a.posible, a.corto, a.extra], [glifo, clase, posible, corto, extra], JSON.stringify(datos));
  }
  assert.equal(aspecto(fila({ tipo: "lluvia", posible: true })).tono, "posible");
  assert.equal(aspecto(fila({ tipo: "tormenta" })).prioridad, 700);
  assert.equal(aspecto(fila({ tipo: "sin_lluvia" })).prioridad, 300);
  assert.equal(temps(CAJAMARCA), "21°/10°");
  assert.equal(temps(fila({ tmax: null, tmin: null })), "–");
});

test("fechaDeOpcion usa la hora de Perú", () => {
  const t = Date.parse("2026-09-23T04:30:00Z"); // 23:30 del martes 22 en Lima
  assert.equal(fechaDeOpcion("ahora", t), "2026-09-22");
  assert.equal(fechaDeOpcion("manana", t), "2026-09-23");
  assert.equal(fechaDeOpcion("pasado", t), "2026-09-24");
  assert.equal(fechaDeOpcion("ahora", Date.parse("2026-09-23T05:30:00Z")), "2026-09-23");
  assert.equal(etiquetaDia("2026-09-23", "2026-09-23"), "Hoy");
  assert.equal(etiquetaDia("2026-09-24", "2026-09-23"), "Mañana");
  assert.equal(etiquetaDia("2026-09-25", "2026-09-23"), "Viernes");
});

test("localidadCercana con los cortes de 10 y 30 km", () => {
  const filas = [CAJAMARCA, fila({ codigo: "06-0099", nombre: "Lejana", lat: -6.0, lon: -78.0 })];
  // ~5 km al norte de la estación
  assert.equal(localidadCercana(filas, -7.1225, -78.4931).estado, "ok");
  assert.equal(localidadCercana(filas, -7.1225, -78.4931).codigo, "06-0011");
  // ~20 km
  const c = localidadCercana(filas, -6.9876, -78.4931);
  assert.equal(c.estado, "cercana");
  assert.ok(c.km > 10 && c.km < 30);
  // ~45 km
  assert.equal(localidadCercana(filas, -7.5725, -78.4931).estado, "lejos");
  assert.equal(localidadCercana([], -7, -78), null);
});

test("centroCiudad: cerca del punto de tu localidad, sin salir de la línea hacia la ciudad", () => {
  const ciudad = { lat: -7.1617, lon: -78.5127 }; // data/cities.js
  // la estación de Cajamarca está a 2,3 km: el centro queda a 1 km de ella, hacia la ciudad
  const c = centroCiudad(ciudad, CAJAMARCA);
  assert.ok(Math.abs(haversineKm(c.lat, c.lon, CAJAMARCA.lat, CAJAMARCA.lon) - 1) < 0.01);
  assert.ok(Math.abs(haversineKm(c.lat, c.lon, ciudad.lat, ciudad.lon) - 1.3) < 0.05);
  // a menos de 1 km, o sin punto de la localidad: la ciudad
  assert.deepEqual(centroCiudad(ciudad, { lat: -7.1650, lon: -78.5100 }), ciudad);
  assert.deepEqual(centroCiudad(ciudad, { lat: null, lon: null }), ciudad);
  assert.deepEqual(centroCiudad(ciudad, null), ciudad);
});

test("franja de 3 días con un día faltante", () => {
  const filas = [CAJAMARCA, fila({ fecha: "2026-09-25", tmax: 24, tmin: 8 })];
  const f = franja(filas, "06-0011", "2026-09-23");
  assert.deepEqual(f.map((d) => d.etiqueta), ["Hoy", "Mañana", "Viernes"]);
  assert.deepEqual(f.map((d) => d.fechaCorta), ["mié 23", "jue 24", "vie 25"]);
  assert.equal(f[0].fila.tmax, 21);
  assert.equal(f[1].fila, null);
  assert.equal(f[2].fila.tmax, 24);
  const p = pronosticoLocal({ filas, ciudad: { name: "Cajamarca", localidad: "06-0011" }, hoy: "2026-09-23" });
  assert.equal(p.estado, "ok");
  assert.equal(p.localidad.nombre, "Cajamarca");
  assert.equal(p.dias[1].fila, null);
  assert.equal(pronosticoLocal({ filas: undefined }).estado, "cargando");
  assert.equal(pronosticoLocal({ filas: null }).estado, "sin_servicio");
  assert.equal(pronosticoLocal({ filas, error: new Error("x") }).estado, "error");
  assert.equal(pronosticoLocal({ filas, ciudad: { name: "Lima", localidad: "15-0001" }, hoy: "2026-09-23" }).estado, "sin_datos");
  const gps = pronosticoLocal({ filas, porGps: true, userPos: [-6.9876, -78.4931], hoy: "2026-09-23" });
  assert.equal(gps.estado, "cercana");
  assert.ok(gps.localidad.km > 10);
});

test("emitidoTexto: anoche, hoy o la fecha; atrasado a más de 3 días", () => {
  assert.equal(emitidoTexto("2026-09-22", "2026-09-23"), "Emitido anoche");
  assert.equal(emitidoTexto("2026-09-23", "2026-09-23"), "Emitido hoy");
  assert.equal(emitidoTexto("2026-09-18", "2026-09-23"), "Emitido el vie 18 set");
  assert.equal(atrasado("2026-09-20", "2026-09-23"), false);
  assert.equal(atrasado("2026-09-19", "2026-09-23"), true);
  assert.equal(atrasado(null, "2026-09-23"), false);
});

test("nota de la capa: categorías sin los ceros y aviso de atraso", () => {
  const filas = [
    CAJAMARCA,
    fila({ codigo: "06-0002", tipo: "lluvia", posible: true }),
    fila({ codigo: "06-0003", tipo: "lluvia", posible: true }),
    fila({ codigo: "06-0004", tipo: "sin_lluvia" }),
  ];
  assert.equal(
    notaPronostico(filas, "2026-09-23", "2026-09-23"),
    "Hoy, mié 23: lluvia en 1 localidad, puede llover en 2, sin lluvia en 1."
  );
  assert.equal(notaPronostico(filas, "2026-09-24", "2026-09-23"), "SENAMHI no tiene pronóstico por localidad para ese día.");
  const viejas = filas.map((f) => ({ ...f, emision: "2026-09-18" }));
  assert.match(notaPronostico(viejas, "2026-09-23", "2026-09-23"), /Emitido el vie 18 set: SENAMHI no lo actualiza los fines de semana ni feriados\.$/);
});
