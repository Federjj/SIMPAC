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

// ---------------------------------------------------------------------------
// Discos de río (tipo "rio") con rótulo en el acomodo
// ---------------------------------------------------------------------------
const rio = (id, x, y, extra = {}) => ({ id, x, y, w: 40, h: 40, prioridad: 700, tipo: "rio", rotulo: { w: anchoRotulo("Mashcón · Tranquilo"), h: 22 }, ...extra });

test("río tranquilo: se ve con su rótulo y el disco del pronóstico que lo tapa pasa a punto", () => {
  const r = colocar([rio("mash", 300, 200), disco("caj", 300 + 60, 200, { prioridad: 650 })]);
  assert.equal(r.get("mash").estado, "visible");
  assert.equal(r.get("mash").rotulo, "der");
  assert.equal(r.get("caj").estado, "punto");
});

test("río tranquilo bajo una insignia: pasa a punto (el aviso no se mueve)", () => {
  const r = colocar([insignia("av", 300, 200), rio("mash", 305, 205)]);
  assert.equal(r.get("av").estado, "visible");
  assert.deepEqual([r.get("av").dx, r.get("av").dy], [0, 0]);
  assert.equal(r.get("mash").estado, "punto");
  assert.equal(r.get("mash").rotulo, null);
});

test("río en alerta: nunca se oculta, su rótulo se ve y la insignia encima tampoco se pierde", () => {
  const r = colocar([insignia("av", 300, 200, { candidatos: [] }), rio("mash", 305, 205, { fuerte: true, prioridad: 950 })]);
  assert.equal(r.get("mash").estado, "visible");
  assert.ok(r.get("mash").rotulo);
  assert.equal(r.get("av").estado, "visible");
});

test("río en alerta junto al borde derecho: el rótulo va a la izquierda", () => {
  const r = colocar([rio("mash", 780, 200, { fuerte: true })], { ancho: 800 });
  assert.equal(r.get("mash").rotulo, "izq");
});

test("dos ríos tranquilos juntos: gana el de mayor prioridad, el otro es punto", () => {
  const r = colocar([rio("a", 300, 200, { prioridad: 710 }), rio("b", 320, 210, { prioridad: 700 })]);
  assert.equal(r.get("a").estado, "visible");
  assert.equal(r.get("b").estado, "punto");
});

test("rótulo del río que no cabe a ningún lado (paneles): el disco se ve sin rótulo", () => {
  const r = colocar([rio("mash", 300, 200)], { obstaculos: [{ x: 420, y: 200, w: 120, h: 60 }, { x: 180, y: 200, w: 120, h: 60 }] });
  assert.equal(r.get("mash").estado, "visible");
  assert.equal(r.get("mash").rotulo, null);
});

test("el rótulo del usuario esquiva el disco de un río (va a la izquierda) y el río se ve", () => {
  const r = colocar([
    disco("tuyo", 455, 390, { tipo: "usuario", rotulo: { w: anchoRotulo("Cajamarca 24°/11°"), h: 20 } }),
    rio("mash", 550, 374),
  ]);
  assert.equal(r.get("tuyo").rotulo, "izq");
  assert.equal(r.get("mash").estado, "visible");
});

test("un marcador fijo de otra capa (rombo de desborde) no vuelve punto a un río; su rótulo lo esquiva", () => {
  const rombo = { x: 300, y: 185, w: 24, h: 24 };
  const r = colocar([rio("mash", 300, 200)], { fijos: [rombo, { x: 400, y: 200, w: 24, h: 24 }] });
  assert.equal(r.get("mash").estado, "visible");
  assert.equal(r.get("mash").rotulo, "izq");
});

test("río vigilado tapado por el disco de tu localidad: se pega a un lado en vez de quedar como punto", () => {
  const tuyo = disco("tuyo", 300, 200, { tipo: "usuario", rotulo: { w: anchoRotulo("Cajamarca 24°/11°"), h: 20 } });
  const r = colocar([tuyo, rio("mash", 306, 204, { vigilado: true, prioridad: 850 })]);
  assert.equal(r.get("mash").estado, "visible");
  assert.notDeepEqual([r.get("mash").dx, r.get("mash").dy], [0, 0]);
  // sin tocar el disco del usuario
  const m = r.get("mash");
  assert.ok(Math.abs(306 + m.dx - 300) >= (40 + 28) / 2 || Math.abs(204 + m.dy - 200) >= (40 + 28) / 2);
  // una estación cualquiera en el mismo lugar sigue pasando a punto
  assert.equal(colocar([tuyo, rio("otra", 306, 204)]).get("otra").estado, "punto");
});

test("río vigilado de más prioridad gana al disco de otra estación cercana", () => {
  const r = colocar([rio("jesus", 300, 200, { prioridad: 700 }), rio("mash", 320, 205, { prioridad: 850, vigilado: true })]);
  assert.equal(r.get("mash").estado, "visible");
  assert.deepEqual([r.get("mash").dx, r.get("mash").dy], [0, 0]);
});

test("el rótulo del río prueba arriba y abajo antes de rendirse", () => {
  // paneles a la izquierda y a la derecha, libre arriba
  const r = colocar([rio("mash", 300, 200)], { obstaculos: [{ x: 440, y: 205, w: 160, h: 40 }, { x: 160, y: 205, w: 160, h: 40 }] });
  assert.equal(r.get("mash").estado, "visible");
  assert.equal(r.get("mash").rotulo, "arr");
});

test("rombos: el que cae bajo el disco de un río o de otro rombo se corre alrededor; nunca se oculta", () => {
  const rombo = (id, x, y, extra = {}) => ({ id, x, y, w: 24, h: 24, prioridad: 101, tipo: "rombo", ...extra });
  const r = colocar([rio("mash", 300, 200, { rotulo: null }), rombo("9913", 304, 196), rombo("libre", 500, 200)]);
  assert.equal(r.get("mash").estado, "visible");
  assert.deepEqual([r.get("mash").dx, r.get("mash").dy], [0, 0]); // el río no se mueve
  const a = r.get("9913");
  assert.equal(a.estado, "visible");
  assert.ok(Math.abs(304 + a.dx - 300) >= 32 || Math.abs(196 + a.dy - 200) >= 32, "fuera del disco");
  assert.deepEqual([r.get("libre").dx, r.get("libre").dy], [0, 0]);
  // dos rombos encimados: el segundo se corre
  const dos = colocar([rombo("a", 100, 100, { prioridad: 102 }), rombo("b", 104, 102)]);
  assert.deepEqual([dos.get("a").dx, dos.get("a").dy], [0, 0]);
  assert.notDeepEqual([dos.get("b").dx, dos.get("b").dy], [0, 0]);
  // sin cadena: el rombo tapado por el río se corre sin empujar a los vecinos que estaban libres
  const cadena = colocar([
    rio("mash", 459, 429, { rotulo: null }),
    rombo("22", 458, 425, { prioridad: 102 }),
    rombo("16", 449, 370),
    rombo("14", 431, 328),
  ]);
  assert.deepEqual([cadena.get("16").dx, cadena.get("16").dy], [0, 0]);
  assert.deepEqual([cadena.get("14").dx, cadena.get("14").dy], [0, 0]);
  assert.notDeepEqual([cadena.get("22").dx, cadena.get("22").dy], [0, 0]);
  // un disco del pronóstico sobre un rombo pasa a punto (el rombo ocupa su lugar)
  assert.equal(colocar([rombo("a", 100, 100), disco("d", 105, 100)]).get("d").estado, "punto");
  // rodeado por todos lados: se queda en su lugar, visible
  const tapado = colocar([rombo("a", 100, 100)], { fijos: [{ x: 100, y: 100, w: 200, h: 200 }] });
  assert.equal(tapado.get("a").estado, "visible");
  assert.deepEqual([tapado.get("a").dx, tapado.get("a").dy], [0, 0]);
});
