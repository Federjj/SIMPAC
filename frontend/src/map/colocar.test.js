import test from "node:test";
import assert from "node:assert/strict";
import { anchoRotulo, colocar } from "./colocar.js";

const insignia = (id, x, y, extra = {}) => ({ id, x, y, w: 40, h: 40, prioridad: 800, tipo: "insignia", ...extra });
const disco = (id, x, y, extra = {}) => ({ id, x, y, w: 28, h: 28, prioridad: 600, tipo: "disco", ...extra });

test("el usuario nunca se oculta, aunque todo lo tape", () => {
  const r = colocar([
    insignia("a", 100, 100, { prioridad: 900 }),
    disco("tuyo", 100, 100, { tipo: "usuario", prioridad: 0, rotulo: { w: 80, h: 20 } }),
    disco("otro", 102, 101, { prioridad: 700 }),
  ]);
  assert.equal(r.get("tuyo").estado, "visible");
  assert.equal(r.get("tuyo").rotulo, "der");
  assert.equal(r.get("otro").estado, "punto");
  // sin candidatos y chocando con el usuario: se pega a su izquierda, sin taparlo
  assert.equal(r.get("a").estado, "visible");
  assert.deepEqual([r.get("a").dx, r.get("a").dy], [-37, 0]);
});

test("escala país: la insignia de tu zona, sin candidatos, se pega a tu punto y no desaparece", () => {
  // punto del usuario de 10 px y la insignia de 30 px con su ancla casi encima (376 a zoom 5)
  const tuyo = { id: "tuyo", x: 451, y: 393, w: 10, h: 10, prioridad: 0, tipo: "usuario", rotulo: { w: 110, h: 20 } };
  const r = colocar([
    tuyo,
    { id: "376", x: 451, y: 392, w: 30, h: 30, prioridad: 849, tipo: "insignia", candidatos: [] },
    { id: "24h", x: 452, y: 402, w: 30, h: 48, prioridad: 824, tipo: "insignia", candidatos: [] },
  ]);
  assert.equal(r.get("tuyo").rotulo, "der");
  assert.equal(r.get("376").estado, "visible");
  assert.deepEqual([r.get("376").dx, r.get("376").dy], [-23, 1]); // a la izquierda del punto
  assert.equal(r.get("24h").estado, "fusionado"); // "2 avisos"
  // si tampoco hay lugar a su lado (paneles alrededor), se oculta
  const tapado = colocar(
    [tuyo, { id: "376", x: 451, y: 392, w: 30, h: 30, prioridad: 849, tipo: "insignia", candidatos: [] }],
    { obstaculos: [{ x: 400, y: 393, w: 50, h: 200 }, { x: 451, y: 350, w: 60, h: 40 }, { x: 451, y: 436, w: 60, h: 40 }] }
  );
  assert.equal(tapado.get("376").estado, "oculto");
});

test("el rótulo del usuario se corre ante una insignia, pero siempre se ve", () => {
  const rot = { w: 120, h: 20 };
  const izq = colocar([
    disco("tuyo", 200, 100, { tipo: "usuario", rotulo: rot }),
    insignia("a", 290, 100), // sobre el lado derecho del rótulo
  ]);
  assert.equal(izq.get("a").estado, "visible");
  assert.equal(izq.get("tuyo").rotulo, "izq");
  const forzado = colocar([
    disco("tuyo", 200, 100, { tipo: "usuario", rotulo: rot }),
    insignia("a", 290, 100),
    insignia("b", 110, 100),
  ]);
  assert.equal(forzado.get("tuyo").rotulo, "der");
  // la insignia que solo tapa el rótulo no se pierde
  assert.equal(forzado.get("a").estado, "visible");
  assert.equal(forzado.get("b").estado, "visible");
});

test("los paneles: rótulos e insignias los evitan; un disco debajo no cambia", () => {
  const panel = { x: 300, y: 100, w: 100, h: 60 }; // de 250 a 350
  const r = colocar(
    [
      disco("a", 200, 100, { rotulo: { w: 80, h: 20 } }),
      insignia("b", 320, 100, { candidatos: [{ dx: 0, dy: 60 }] }),
      disco("c", 300, 110),
    ],
    { obstaculos: [panel] }
  );
  assert.equal(r.get("a").rotulo, "izq");
  assert.equal(r.get("b").estado, "visible");
  assert.deepEqual([r.get("b").dx, r.get("b").dy], [0, 60]);
  assert.equal(r.get("c").estado, "visible");
});

test("marcadores de otras capas (ríos): el disco encima pasa a punto, los rótulos los evitan, la insignia no se mueve", () => {
  const rio = { x: 100, y: 100, w: 34, h: 34 };
  const r = colocar(
    [
      disco("encima", 110, 105),
      disco("al_lado", 220, 100, { rotulo: { w: 80, h: 20 } }), // su rótulo a la derecha caería sobre el otro río
      insignia("a", 100, 300),
    ],
    { fijos: [rio, { x: 280, y: 100, w: 34, h: 34 }, { x: 100, y: 300, w: 34, h: 34 }] }
  );
  assert.equal(r.get("encima").estado, "punto");
  assert.equal(r.get("al_lado").estado, "visible");
  assert.equal(r.get("al_lado").rotulo, "izq");
  assert.equal(r.get("a").estado, "visible");
  assert.deepEqual([r.get("a").dx, r.get("a").dy], [0, 0]);
});

test("dos insignias que se tocan dan una sola, con la otra fusionada", () => {
  const r = colocar([insignia("376", 100, 100, { prioridad: 820 }), insignia("24h", 120, 110, { prioridad: 800 })]);
  assert.equal(r.get("376").estado, "visible");
  assert.equal(r.get("24h").estado, "fusionado");
  assert.equal(r.get("24h").en, "376");
  assert.equal(r.get("376").fusionados.length, 1);
  assert.deepEqual(r.get("376").fusionados, ["24h"]);
});

test("una insignia que choca con el usuario usa su primer candidato libre", () => {
  const r = colocar([
    disco("tuyo", 100, 100, { tipo: "usuario" }),
    insignia("a", 105, 100, {
      candidatos: [
        { dx: 0, dy: 10 }, // sigue chocando
        { dx: 0, dy: -44 }, // libre
        { dx: 44, dy: 0 },
      ],
    }),
  ]);
  assert.equal(r.get("a").estado, "visible");
  assert.deepEqual([r.get("a").dx, r.get("a").dy], [0, -44]);
});

test("un disco que choca pasa a punto; el de más prioridad queda", () => {
  const r = colocar([disco("seco", 100, 100, { prioridad: 300 }), disco("tormenta", 110, 100, { prioridad: 700 })]);
  assert.equal(r.get("tormenta").estado, "visible");
  assert.equal(r.get("seco").estado, "punto");
  const lejos = colocar([disco("a", 0, 0), disco("b", 200, 0)]);
  assert.equal(lejos.get("b").estado, "visible");
});

test("un rótulo que no cabe a la derecha pasa a la izquierda", () => {
  const rot = { w: anchoRotulo("Bambamarca 22°/10°"), h: 20 };
  const r = colocar([
    disco("a", 200, 100, { rotulo: rot, prioridad: 600 }),
    disco("b", 260, 100, { prioridad: 700 }), // a la derecha de "a", tapa su rótulo
  ]);
  assert.equal(r.get("a").estado, "visible");
  assert.equal(r.get("a").rotulo, "izq");
  // tampoco a la izquierda: sin rótulo
  const sin = colocar([
    disco("a", 200, 100, { rotulo: rot }),
    disco("b", 260, 100, { prioridad: 700 }),
    disco("c", 140, 100, { prioridad: 700 }),
  ]);
  assert.equal(sin.get("a").rotulo, null);
  // borde derecho de la vista
  const borde = colocar([disco("a", 300, 100, { rotulo: rot })], { ancho: 320 });
  assert.equal(borde.get("a").rotulo, "izq");
});
