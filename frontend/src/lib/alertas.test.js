import test from "node:test";
import assert from "node:assert/strict";
import {
  agruparAlertas,
  agruparAvisosVigentes,
  textoDiasAviso,
  etiquetaAlerta,
  filtrarAlertas,
  fuenteAlerta,
  ordenarAlertas,
  prepararAlertas,
  rangoPasadas,
  textoZonas,
  tituloAlerta,
} from "./alertas.js";

const t = (h) => `2026-10-14T${String(h).padStart(2, "0")}:00:00-05:00`;
const ALERTAS = [
  { tipo: "lluvia", referencia: "47E35522", zona: "Cajamarca", nivel: "aviso", detalle: "Llovió 12 mm en 1 h", ts: t(14) },
  { tipo: "aviso", referencia: "SENAMHI aviso 280", zona: "Cajamarca", nivel: "alerta", detalle: "Lluvia fuerte", ts: t(9) },
  { tipo: "aviso", referencia: "SENAMHI aviso 280", zona: "Piura", nivel: "alerta", detalle: "Lluvia fuerte", ts: t(10) },
  { tipo: "caudal", referencia: "Mashcón (Mashcón)", zona: "Cajamarca", nivel: "emergencia", detalle: "Pasó 18", ts: t(13) },
  { tipo: "nivel_bajo", referencia: "Nauta (Marañón)", zona: "Loreto", nivel: "alerta", detalle: "Muy bajo", ts: t(8) },
  { tipo: "lluvia", referencia: "AAA", zona: "Lima", nivel: "emergencia", detalle: "x", ts: t(12) }, // la lluvia nunca pasa de aviso
];

test("agrupar: un aviso de SENAMHI por referencia con todas sus zonas", () => {
  const g = agruparAlertas(ALERTAS);
  assert.equal(g.length, 5);
  const aviso = g.find((a) => a.tipo === "aviso");
  assert.deepEqual(aviso.zonas, ["Cajamarca", "Piura"]);
  assert.equal(aviso.ts, t(10)); // la hora más nueva
  assert.deepEqual(g.find((a) => a.tipo === "caudal").zonas, ["Cajamarca"]);
});

test("ordenar: emergencia, alerta, aviso; oficiales antes que la lluvia; luego la más reciente", () => {
  const o = ordenarAlertas(agruparAlertas(ALERTAS)).map((a) => `${a.tipo}:${a.referencia}`);
  assert.deepEqual(o, [
    "caudal:Mashcón (Mashcón)",
    "aviso:SENAMHI aviso 280",
    "nivel_bajo:Nauta (Marañón)",
    "lluvia:47E35522",
    "lluvia:AAA",
  ]);
});

test("filtros por nivel, tipo y zona", () => {
  const g = agruparAlertas(ALERTAS);
  assert.equal(filtrarAlertas(g, { nivel: "emergencia" }).length, 1);
  assert.equal(filtrarAlertas(g, { nivel: "aviso" }).length, 2); // las dos de lluvia
  assert.equal(filtrarAlertas(g, { tipo: "rios" }).length, 2);
  assert.equal(filtrarAlertas(g, { tipo: "avisos" }).length, 1);
  assert.equal(filtrarAlertas(g, { zona: "mia", depto: "Cajamarca" }).length, 3);
  assert.equal(filtrarAlertas(g, { zona: "mia", depto: "Piura" }).length, 1); // el aviso agrupado cubre Piura
  assert.equal(filtrarAlertas(g, { zona: "mia", depto: null }).length, 5); // sin zona conocida no se filtra
  assert.equal(prepararAlertas(ALERTAS, { tipo: "lluvia", zona: "mia", depto: "Lima" })[0].referencia, "AAA");
});

test("textos de la tarjeta", () => {
  assert.equal(etiquetaAlerta(ALERTAS[0]), "Atentos a la lluvia");
  assert.equal(etiquetaAlerta(ALERTAS[1]), "Aviso naranja");
  assert.equal(etiquetaAlerta(ALERTAS[3]), "Emergencia");
  assert.equal(etiquetaAlerta(ALERTAS[4]), "Río muy bajo");
  assert.equal(tituloAlerta(ALERTAS[1]), "Aviso N° 280 de SENAMHI");
  assert.equal(tituloAlerta(ALERTAS[3]), "Río Mashcón · estación Mashcón");
  assert.equal(tituloAlerta({ tipo: "aviso", referencia: "SENAMHI lluvia 24h" }), "Aviso de SENAMHI por lluvia en las próximas 24 horas");
  assert.equal(fuenteAlerta(ALERTAS[0]).oficial, false);
  assert.equal(fuenteAlerta(ALERTAS[3]).nombre.startsWith("ANA"), true);
  assert.equal(textoZonas(["Cajamarca"]), "Cajamarca");
  assert.equal(textoZonas(["Cajamarca", "Piura"]), "Cajamarca y Piura");
  assert.equal(textoZonas(["A", "B", "C", "D", "E"]), "A, B y 3 más");
});

test("rango de las alertas pasadas", () => {
  assert.deepEqual(rangoPasadas({}, "2026-10-14"), { desde: "2026-10-07", hasta: "2026-10-14", aviso: null });
  assert.equal(rangoPasadas({ desde: "2026-10-20", hasta: "2026-10-14" }, "2026-10-14").desde, "2026-10-07");
  const r = rangoPasadas({ desde: "2026-08-01", hasta: "2026-10-14" }, "2026-10-14");
  assert.equal(r.desde, "2026-09-14");
  assert.ok(r.aviso.includes("30 días"));
  assert.equal(rangoPasadas({ desde: "ayer" }, "2026-10-14").desde, "2026-10-07");
});

// Filas de aviso_vigente: una por área (nivel) de cada mapa (día), ordenadas por nivel ascendente
// como las entrega la vista. El 419 de 2026 es rojo (nivel 4) en SENAMHI aunque su primera fila sea amarilla.
const AV = (numero, mapa, nivel, dia, extra = {}) => ({
  tipo: "meteorologico",
  anio: 2026,
  numero,
  mapa,
  nivel,
  titulo: "INCREMENTO DE TEMPERATURA DIURNA",
  inicio: `${dia}T05:00:00+00:00`,
  fin: `${dia.slice(0, 8)}${String(Number(dia.slice(8)) + 1).padStart(2, "0")}T04:59:59+00:00`,
  en_curso: dia === "2026-10-19",
  departamentos: ["Cajamarca"],
  texto_dia: `texto nivel ${nivel} dia ${mapa}`,
  ...extra,
});
const VIGENTES = [
  AV(419, 3, 2, "2026-10-19", { departamentos: ["Cajamarca", "Piura"] }),
  AV(419, 3, 3, "2026-10-19"),
  AV(419, 3, 4, "2026-10-19", { departamentos: ["Lambayeque"] }),
  AV(426, 1, 2, "2026-10-20"),
  AV(426, 1, 3, "2026-10-20"),
  AV(426, 2, 2, "2026-10-21"),
  AV(426, 3, 2, "2026-10-22"),
  AV(426, 3, 3, "2026-10-22"),
  AV(426, 3, 4, "2026-10-22"),
];

test("avisos vigentes: una tarjeta por aviso con el nivel más alto de sus áreas, nunca el de la primera fila", () => {
  const g = agruparAvisosVigentes(VIGENTES);
  assert.equal(g.length, 2);
  const a419 = g.find((a) => a.numero === 419);
  assert.equal(a419.nivel, 4);
  assert.equal(a419.texto_dia, "texto nivel 4 dia 3"); // el texto del área de nivel más alto
  assert.deepEqual(a419.departamentos, ["Cajamarca", "Lambayeque", "Piura"]); // la unión, en orden
  assert.deepEqual(a419.dias, ["2026-10-19"]);
  assert.equal(a419.en_curso, true);
  const a426 = g.find((a) => a.numero === 426);
  assert.equal(a426.nivel, 4);
  assert.deepEqual(a426.dias, ["2026-10-20", "2026-10-21", "2026-10-22"]);
  assert.deepEqual(a426.nivelPorDia, { "2026-10-20": 3, "2026-10-21": 2, "2026-10-22": 4 });
  assert.equal(a426.inicio, "2026-10-20T05:00:00+00:00");
  assert.equal(a426.fin, "2026-10-23T04:59:59+00:00");
  assert.equal(a426.en_curso, false);
});

test("avisos vigentes: el orden de llegada no cambia el nivel ni los días", () => {
  const g = agruparAvisosVigentes([...VIGENTES].reverse());
  assert.equal(g.find((a) => a.numero === 419).nivel, 4);
  assert.equal(g.find((a) => a.numero === 426).nivel, 4);
  assert.deepEqual(g.find((a) => a.numero === 426).dias, ["2026-10-20", "2026-10-21", "2026-10-22"]);
});

test("avisos vigentes: una sola fila queda igual", () => {
  const [g] = agruparAvisosVigentes([AV(422, 2, 2, "2026-10-19")]);
  assert.equal(g.nivel, 2);
  assert.deepEqual(g.dias, ["2026-10-19"]);
  assert.deepEqual(g.nivelPorDia, { "2026-10-19": 2 });
});

test("textoDiasAviso: el color por día solo cuando cambia entre días", () => {
  const g = agruparAvisosVigentes(VIGENTES);
  const cuando = (d) => ({ "2026-10-19": "hoy", "2026-10-20": "mañana", "2026-10-21": "el miércoles 21", "2026-10-22": "el jueves 22" })[d];
  assert.equal(textoDiasAviso(g.find((a) => a.numero === 419), cuando), "hoy");
  assert.equal(textoDiasAviso(g.find((a) => a.numero === 426), cuando), "mañana (naranja), el miércoles 21 (amarillo), el jueves 22 (rojo)");
});
