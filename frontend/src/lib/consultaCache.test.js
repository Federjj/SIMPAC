import test from "node:test";
import assert from "node:assert/strict";
import { cached, filas, olvidarCache, siExiste, todas } from "./consultaCache.js";

test("cached: la misma clave dentro del TTL es una sola llamada (deduplica aunque se pida en paralelo)", async () => {
  olvidarCache();
  let llamadas = 0;
  const fn = () => {
    llamadas++;
    return Promise.resolve([{ a: 1 }]);
  };
  const [x, y] = await Promise.all([cached("k", fn, 1000), cached("k", fn, 1000)]);
  assert.equal(llamadas, 1);
  assert.equal(x, y); // la misma promesa resuelta: el mismo arreglo
  await cached("k", fn, 1000);
  assert.equal(llamadas, 1);
});

test("cached: vencido el TTL vuelve a pedir, y un error no se queda cacheado", async () => {
  olvidarCache();
  let llamadas = 0;
  const fn = () => Promise.resolve(++llamadas);
  assert.equal(await cached("t", fn, 0), 1);
  assert.equal(await cached("t", fn, 0), 2); // TTL 0: siempre vencido

  let falla = true;
  const inestable = () => (falla ? Promise.reject(new Error("red")) : Promise.resolve("ok"));
  await assert.rejects(cached("e", inestable, 60_000));
  falla = false;
  assert.equal(await cached("e", inestable, 60_000), "ok"); // el error anterior no bloqueó la clave
});

test("filas y siExiste: desenvuelven PostgREST y una vista ausente da null (otros errores suben)", async () => {
  assert.deepEqual(await filas(Promise.resolve({ data: [1, 2], error: null })), [1, 2]);
  assert.deepEqual(await filas(Promise.resolve({ data: null, error: null })), []);
  await assert.rejects(filas(Promise.resolve({ data: null, error: { code: "42501" } })));
  assert.equal(await siExiste(() => Promise.reject({ code: "PGRST205" })), null);
  assert.equal(await siExiste(() => Promise.reject({ code: "42P01" })), null);
  await assert.rejects(siExiste(() => Promise.reject({ code: "42501" })));
  assert.deepEqual(await siExiste(() => Promise.resolve([7])), [7]);
});

test("todas: pide por páginas de 1000 con range y junta las filas", async () => {
  const rangos = [];
  const armar = () => ({
    range: (a, b) => {
      rangos.push([a, b]);
      const n = a === 0 ? 1000 : 3;
      return Promise.resolve({ data: Array.from({ length: n }, (_, i) => a + i), error: null });
    },
  });
  const out = await todas(armar);
  assert.equal(out.length, 1003);
  assert.deepEqual(rangos, [
    [0, 999],
    [1000, 1999],
  ]);
});
