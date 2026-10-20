import test from "node:test";
import assert from "node:assert/strict";
import { etiqueta, frasesEstado, nivelDeAlertas } from "./nivel.js";

// filas de alerta_actual como las de Loreto el 19-10-2026: cinco ríos muy bajos (vaciante) que
// ANA publica con nivel 'alerta' y un aviso amarillo de SENAMHI
const BAJO = (referencia) => ({ tipo: "nivel_bajo", referencia, zona: "Loreto", nivel: "alerta", detalle: "Río bajo (vaciante): nivel 117 m.s.n.m, subiendo" });
const BAJOS = ["San Regis (Marañón)", "Lagunas (Huallaga)", "Santa María de Nanay (Nanay)", "TAMSHIYACU (Amazonas)", "Bellavista (Napo)"].map(BAJO);
const AMARILLO = { tipo: "aviso", referencia: "SENAMHI lluvia 24h", zona: "Loreto", nivel: "aviso", detalle: "Lluvia moderada" };
const COBERTURA = { rios: 5, lluvia: 2, lluviaFuera: 10, lluviaRevisada: true };

test("un río muy bajo (vaciante) vale como máximo 'aviso' en el semáforo", () => {
  assert.equal(nivelDeAlertas(BAJOS), "aviso");
  assert.equal(nivelDeAlertas([...BAJOS, AMARILLO]), "aviso");
  assert.equal(nivelDeAlertas([{ tipo: "nivel_bajo", nivel: "emergencia" }]), "aviso");
  // una crecida de verdad sí sube
  assert.equal(nivelDeAlertas([...BAJOS, { tipo: "caudal", nivel: "alerta" }]), "alerta");
  assert.equal(nivelDeAlertas([{ tipo: "aviso", nivel: "emergencia" }]), "emergencia");
  // la lluvia medida sigue siendo 'aviso'
  assert.equal(nivelDeAlertas([{ tipo: "lluvia", nivel: "alerta" }]), "aviso");
});

test("rótulo: 'Ríos muy bajos' cuando el nivel sale solo de la vaciante", () => {
  assert.equal(etiqueta("aviso", BAJOS), "Ríos muy bajos");
  assert.equal(etiqueta("aviso", [BAJOS[0]]), "Río muy bajo");
  assert.equal(etiqueta("aviso", [...BAJOS, AMARILLO]), "Aviso");
  assert.equal(etiqueta("aviso", [AMARILLO]), "Aviso amarillo");
  assert.equal(etiqueta("aviso", [{ tipo: "lluvia", nivel: "aviso" }]), "Atentos a la lluvia");
});

test("frasesEstado: departamento con solo ríos muy bajos -> 'aviso', nunca alerta ni emergencia", () => {
  const p = frasesEstado(BAJOS, "Loreto", COBERTURA);
  assert.equal(p.nivelLocal, "aviso");
  assert.equal(p.nivelOficialAqui, "aviso");
  assert.equal(p.etiquetaLocal, "Ríos muy bajos");
  assert.equal(p.bajosAqui, 5);
  assert.deepEqual(p.riosAqui, []);
  assert.equal(p.local, "En Loreto: 5 ríos muy bajos.");
  // con el aviso amarillo además: sigue en 'aviso' y los ríos por tipo salen aparte
  const q = frasesEstado([...BAJOS, AMARILLO], "Loreto", COBERTURA);
  assert.equal(q.nivelLocal, "aviso");
  assert.equal(q.avisosAqui.length, 1);
  assert.equal(q.bajosAqui, 5);
  // un río que pasó su nivel (tipo caudal) sí va en riosAqui y sube el semáforo
  const r = frasesEstado([...BAJOS, { tipo: "caudal", referencia: "Nauta (Marañón)", zona: "Loreto", nivel: "alerta", detalle: "x" }], "Loreto", COBERTURA);
  assert.equal(r.nivelLocal, "alerta");
  assert.deepEqual(r.riosAqui, [{ nivel: "alerta", detalle: "x", referencia: "Nauta (Marañón)" }]);
  // sin datos: las listas existen vacías
  assert.deepEqual(frasesEstado(null, "Loreto").riosAqui, []);
  assert.equal(frasesEstado(null, "Loreto").bajosAqui, 0);
});
