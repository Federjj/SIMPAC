import test from "node:test";
import assert from "node:assert/strict";
import { DEFS_SVG, ESTILO_GLIFOS, GLIFOS, glifoClave, glifoDataUri, svgDataUri } from "./iconos.js";
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

test("cada glifo como imagen es un SVG suelto que trae adentro todo lo que referencia (url(#...))", () => {
  for (const k of Object.keys(GLIFOS)) {
    const uri = glifoDataUri(k);
    assert.ok(uri.startsWith("data:image/svg+xml;utf8,"));
    const svg = decodeURIComponent(uri.slice("data:image/svg+xml;utf8,".length));
    assert.match(svg, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 32 32">/);
    // el mismo dibujo que el SVG en línea
    assert.ok(svg.includes(GLIFOS[k].replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "")));
    for (const [, id] of svg.matchAll(/url\(#([^)]+)\)/g)) assert.ok(svg.includes(`id="${id}"`), `${k}: falta #${id} dentro de la imagen`);
    assert.ok(!uri.includes("'"), "sin comillas simples: va dentro de url('...') o de un style=\"\"");
  }
  assert.equal(glifoDataUri("lluvia"), glifoDataUri("lluvia")); // memoria: la misma cadena
  assert.equal(glifoClave("no-existe"), "nube");
  assert.equal(glifoClave("tormenta"), "tormenta");
});

test("ESTILO_GLIFOS tiene una regla .glifo-img[data-g] por glifo, y svgDataUri no deja comillas simples", () => {
  for (const k of Object.keys(GLIFOS)) assert.ok(ESTILO_GLIFOS.includes(`.glifo-img[data-g="${k}"]{background-image:url("data:image/svg+xml;utf8,`));
  assert.equal(ESTILO_GLIFOS.split("\n").length, Object.keys(GLIFOS).length);
  assert.ok(!svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg"><path d='M0 0'/></svg>`).includes("'"));
});
