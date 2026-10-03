import { test } from "node:test";
import assert from "node:assert/strict";
import { aplicar, serializar, normalizar, leerLocal, guardarLocal, borrarLocal, masReciente, CLAVE } from "./preferencias.js";

// Mismos ids, defectos y opciones que frontend/src/map/layers (2026-10-02).
const DIA = { valores: [{ valor: "ahora" }, { valor: "manana" }, { valor: "pasado" }], defecto: "ahora", vinculo: "dia" };
const LAYERS = [
  { id: "avisos", defaultVisible: true, opciones: DIA },
  { id: "pronostico", defaultVisible: true, opciones: DIA },
  { id: "nowcast", defaultVisible: false, opciones: { valores: [{ valor: "30" }, { valor: "60" }, { valor: "120" }], defecto: "60" } },
  { id: "zona", defaultVisible: true },
  { id: "huaycos", defaultVisible: false },
  { id: "lluviaAhora", defaultVisible: false },
  { id: "lluviaObservada", defaultVisible: false, opciones: { valores: [{ valor: "ayer" }, { valor: "7d" }], defecto: "ayer" } },
  { id: "satelite", defaultVisible: false },
  { id: "anom", defaultVisible: false },
  { id: "rio", defaultVisible: true },
  { id: "est", defaultVisible: false },
  { id: "fen", defaultVisible: false, opciones: { valores: [{ valor: "1982-1983" }, { valor: "1997-1998" }, { valor: "2017" }], defecto: "1997-1998" } },
  { id: "inc", defaultVisible: true },
];
const HOY = "2026-10-02";

function memoria() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), m };
}

test("primera visita: defectos, sin 'nuevas' ni cambios", () => {
  const r = aplicar(LAYERS, null, { hoy: HOY });
  assert.equal(r.visible.avisos, true);
  assert.equal(r.visible.est, false);
  assert.equal(r.opciones.fen, "1997-1998");
  assert.deepEqual(r.nuevas, []);
  assert.equal(r.cambios, false);
});

test("el caso de Kevin: apaga estaciones y deja solo ríos; vuelve y lo ve igual", () => {
  const visible = { ...aplicar(LAYERS, null, { hoy: HOY }).visible, avisos: false, pronostico: false, zona: false, inc: false, est: false, rio: true };
  const a = memoria();
  guardarLocal(serializar(LAYERS, { visible, opciones: {} }, { hoy: HOY }), a);
  const guardado = JSON.parse(a.m.get(CLAVE));
  // solo las diferencias con el defecto (est ya venía apagada: no se guarda)
  assert.deepEqual(guardado.capas, { avisos: false, pronostico: false, zona: false, inc: false });
  const r = aplicar(LAYERS, leerLocal(a), { hoy: HOY });
  assert.equal(r.visible.rio, true);
  assert.equal(r.visible.avisos, false);
  assert.equal(r.visible.est, false);
  assert.equal(r.cambios, true);
});

test("capa nueva: arranca con su defecto y se marca 'Nueva'", () => {
  const viejo = serializar(LAYERS, { visible: { rio: true }, opciones: {} }, { hoy: HOY });
  const conNueva = [...LAYERS, { id: "zonaRio", defaultVisible: true }];
  const r = aplicar(conNueva, viejo, { hoy: HOY });
  assert.equal(r.visible.zonaRio, true);
  assert.deepEqual(r.nuevas, ["zonaRio"]);
});

test("capa que ya no existe: se ignora", () => {
  const r = aplicar(LAYERS, { v: 1, capas: { vieja: true, rio: false }, conocidas: ["vieja", "rio"] }, { hoy: HOY });
  assert.equal("vieja" in r.visible, false);
  assert.equal(r.visible.rio, false);
});

test("opciones: solo valores que existen; el evento FEN elegido vuelve", () => {
  const g = serializar(LAYERS, { visible: { fen: true }, opciones: { fen: "2017", nowcast: "999" } }, { hoy: HOY });
  assert.deepEqual(g.opciones, { fen: "2017" });
  assert.equal(aplicar(LAYERS, g, { hoy: HOY }).opciones.fen, "2017");
  assert.equal(aplicar(LAYERS, { v: 1, opciones: { fen: "1600" } }, { hoy: HOY }).opciones.fen, "1997-1998");
});

test("día: 'Mañana' vale solo hoy; al día siguiente vuelve a 'Hoy' en avisos y pronóstico", () => {
  const g = serializar(LAYERS, { visible: {}, opciones: { avisos: "manana", pronostico: "manana" } }, { hoy: HOY });
  assert.deepEqual(g.dia, { valor: "manana", fecha: HOY });
  assert.equal(g.opciones.avisos, undefined);
  const mismoDia = aplicar(LAYERS, g, { hoy: HOY });
  assert.equal(mismoDia.opciones.avisos, "manana");
  assert.equal(mismoDia.opciones.pronostico, "manana");
  const otroDia = aplicar(LAYERS, g, { hoy: "2026-10-03" });
  assert.equal(otroDia.opciones.avisos, "ahora");
  assert.equal(otroDia.opciones.pronostico, "ahora");
});

test("versión desconocida o basura: defectos", () => {
  for (const crudo of [{ v: 99, capas: { rio: false } }, "x", 3, [], { v: 1, capas: "no" }]) {
    const r = aplicar(LAYERS, crudo, { hoy: HOY });
    assert.equal(r.visible.rio, true);
  }
});

test("localStorage que lanza (ventana privada / bloqueado): no rompe", () => {
  const roto = { getItem() { throw new Error("SecurityError"); }, setItem() { throw new Error("QuotaExceeded"); }, removeItem() { throw new Error("x"); } };
  assert.equal(leerLocal(roto), null);
  assert.equal(guardarLocal({ v: 1 }, roto), false);
  borrarLocal(roto);
  assert.equal(leerLocal(undefined), null);
});

test("JSON corrupto en el almacén: null", () => {
  const a = memoria();
  a.setItem(CLAVE, "{no es json");
  assert.equal(leerLocal(a), null);
});

test("restablecer: borrar deja los defectos", () => {
  const a = memoria();
  guardarLocal(serializar(LAYERS, { visible: { rio: false }, opciones: {} }, { hoy: HOY }), a);
  borrarLocal(a);
  assert.equal(aplicar(LAYERS, leerLocal(a), { hoy: HOY }).visible.rio, true);
});

test("cuenta vs navegador: gana la guardada más tarde", () => {
  const local = { v: 1, guardado: "2026-10-02T10:00:00Z" };
  const cuenta = { v: 1, guardado: "2026-10-02T12:00:00Z" };
  assert.equal(masReciente(local, cuenta), cuenta);
  assert.equal(masReciente({ ...local, guardado: "2026-10-02T13:00:00Z" }, cuenta).guardado, "2026-10-02T13:00:00Z");
  assert.equal(masReciente(null, cuenta), cuenta);
  assert.equal(masReciente(local, null), local);
});

test("tamaño: lo guardado es chico (cabe holgado en el límite de 4 KB de la tabla)", () => {
  const todo = Object.fromEntries(LAYERS.map((l) => [l.id, !l.defaultVisible]));
  const g = serializar(LAYERS, { visible: todo, opciones: { fen: "2017", nowcast: "120", lluviaObservada: "7d", avisos: "pasado" } }, { hoy: HOY });
  assert.ok(JSON.stringify(g).length < 700, JSON.stringify(g).length);
});

test("normalizar descarta capas iguales al defecto (no fija defectos viejos)", () => {
  const p = normalizar(LAYERS, { v: 1, capas: { rio: true, est: true } }, { hoy: HOY });
  assert.deepEqual(p.capas, { est: true });
});

test("celular nuevo sin cambios no pisa la cuenta; con cambios recientes, sí", () => {
  const cuenta = serializar(LAYERS, { visible: { rio: true, est: true }, opciones: {} }, { hoy: HOY, guardado: "2026-09-30T20:00:00Z" });
  const nuevo = serializar(LAYERS, aplicar(LAYERS, null, { hoy: HOY }), { hoy: HOY }); // guardado: null
  assert.equal(nuevo.guardado, null);
  assert.equal(masReciente(nuevo, cuenta), cuenta);
  const tocado = serializar(LAYERS, { visible: { rio: false }, opciones: {} }, { hoy: HOY, guardado: "2026-10-02T23:00:00Z" });
  assert.equal(masReciente(tocado, cuenta), tocado);
});

test("si leer window.localStorage ya lanza (datos del sitio bloqueados) o no existe, no rompe", () => {
  const previo = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", { configurable: true, get() { throw new Error("SecurityError"); } });
  try {
    assert.equal(leerLocal(), null);
    assert.equal(guardarLocal({ v: 1 }), false);
    borrarLocal();
  } finally {
    if (previo) Object.defineProperty(globalThis, "localStorage", previo);
    else delete globalThis.localStorage;
  }
  assert.equal(guardarLocal({ v: 1 }, null), false); // sin almacén no se guarda
});
