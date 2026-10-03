import test from "node:test";
import assert from "node:assert/strict";
import { DEFS_SVG, GLIFOS } from "./iconos.js";
import { ZONA_OSCURO } from "./palette.js";

test("DEFS_SVG trae los 4 rayados de las zonas de los ríos, con el tono oscuro de cada nivel", () => {
  for (const nivel of ["emergencia", "alerta", "atentos", "sin_senales"]) {
    const m = DEFS_SVG.match(new RegExp(`<pattern id="simpac-rayado-${nivel}"[^>]*>(.*?)</pattern>`));
    assert.ok(m, `falta simpac-rayado-${nivel}`);
    assert.match(m[0], /width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate\(45\)"/);
    assert.ok(m[1].includes(`fill="${ZONA_OSCURO[nivel]}"`));
  }
  // sin señales: azul de agua, franjas algo más suaves (la zona igual se lee como zona que podría inundarse)
  assert.match(DEFS_SVG, /simpac-rayado-sin_senales"[^>]*><rect width="8" height="8" fill="#fff" fill-opacity=".45"\/><rect width="3.2" height="8" fill="#1E3A8A" fill-opacity=".55"\/>/);
  assert.equal((DEFS_SVG.match(/<pattern /g) ?? []).length, 4);
});

test("los glifos siguen siendo constantes con ids simpac-", () => {
  assert.ok(Object.keys(GLIFOS).length >= 10);
  for (const id of DEFS_SVG.match(/id="[^"]+"/g)) assert.match(id, /^id="simpac-/);
});
