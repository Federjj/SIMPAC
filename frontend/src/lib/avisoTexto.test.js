import test from "node:test";
import assert from "node:assert/strict";
import { claveAviso, glifoAviso, montosAviso, textoAviso, tooltipAviso } from "./avisoTexto.js";

const HOY = "2026-09-23";
// Aviso 376, mapa 1: columnas de siempre más las nuevas del contrato (§3.4 de la especificación).
const A376 = {
  id: 47, tipo: "meteorologico", anio: 2026, numero: 376, mapa: 1, nivel: 2,
  titulo: "PRECIPITACIONES EN LA SIERRA NORTE Y COSTA NORTE", tema: "lluvia",
  descripcion:
    "El SENAMHI informa que, del miércoles 23 al jueves 24 de setiembre, se presentará precipitaciones (lluvia), de ligera a moderada intensidad, en la sierra norte. Estas precipitaciones estarán acompañadas de descargas eléctricas y ráfagas de viento con velocidades cercanas a los 40 km/h. En la costa norte, se esperan lluvias de ligera a moderada intensidad.",
  inicio: "2026-09-23T05:00:00+00:00", fin: "2026-09-24T04:59:59+00:00", en_curso: true,
  departamentos: ["Cajamarca", "La Libertad", "Piura", "Tumbes"],
  url: "https://www.senamhi.gob.pe/?p=aviso-meteorologico-detalle&a=2026&b=376&c=077&d=SENA",
  texto_dia:
    "El miércoles 23 de setiembre se esperan acumulados de lluvia hasta los 12 mm/día en Tumbes, cercanos a los 6 mm/día en la costa de Piura y valores entre los 7 mm/día y 15 mm/día en la sierra norte.",
  icono: "gota",
  lectura: {
    v: 1, fenomeno: "lluvia", donde: "la sierra norte y costa norte", intensidad: "de ligera a moderada intensidad",
    regiones_titulo: ["costa", "sierra"], regiones_parrafo: ["costa", "sierra"], una_region: false, descargas: "si",
    frase_descargas:
      "El SENAMHI informa que, del miércoles 23 al jueves 24 de setiembre, se presentará precipitaciones (lluvia), de ligera a moderada intensidad, en la sierra norte. Estas precipitaciones estarán acompañadas de descargas eléctricas y ráfagas de viento con velocidades cercanas a los 40 km/h.",
    granizo: { menciona: false, sobre_m: null }, nieve: { menciona: false, sobre_m: null },
    rafagas: { forma: "cercanas a", kmh: 40 },
    montos: [
      { lugar: "Tumbes", desde: null, hasta: 12, forma: "hasta", unidad: "mm" },
      { lugar: "Costa de Piura", desde: null, hasta: 6, forma: "cerca", unidad: "mm" },
      { lugar: "Sierra norte", desde: 7, hasta: 15, forma: "rango", unidad: "mm" },
    ],
  },
  anclas: [
    { parte: 1, lon: -78.462, lat: -7.197, radio_km: 48.0, km2: 11865, mayor: true },
    { parte: 2, lon: -79.74, lat: -4.78, radio_km: 30.0, km2: 9100, mayor: false },
  ],
};
const A24 = {
  id: 66, tipo: "lluvia24h", anio: 2026, numero: null, mapa: 1, nivel: 2,
  titulo: "AVISO DE CORTO PLAZO ANTE LLUVIAS INTENSAS", tema: "lluvia",
  descripcion: "Lluvia de intensidad moderada.", inicio: "2026-09-22T18:00:00+00:00", fin: "2026-09-23T18:00:00+00:00",
  departamentos: ["Cajamarca"], url: "https://www.senamhi.gob.pe/?p=aviso-24H",
  texto_dia: null, icono: "gota", lectura: { v: 1, fenomeno: "lluvia" }, anclas: [],
};

test("376: gota, caja de hoy y rayos citados sin afirmar toda la zona", () => {
  const t = textoAviso(A376, { hoy: HOY, mapas: 2 });
  assert.equal(t.glifo, "gota");
  assert.equal(t.forma, "lluvia");
  assert.equal(t.cabecera, "Aviso amarillo de SENAMHI");
  assert.equal(t.subtitulo, "N° 376 · miércoles 23 de setiembre (día 1 de 2)");
  assert.equal(t.titulo, "Lluvias de ligera a moderada intensidad");
  assert.equal(t.donde, "En la sierra norte y costa norte · Cajamarca, La Libertad, Piura, Tumbes");
  assert.equal(t.caja[0], "Puede llover en algún momento en esta zona hoy, miércoles 23 de setiembre.");
  assert.equal(t.caja[1], "No quiere decir que llueva en toda la zona ni todo el día.");
  const rayos = t.filas.find((f) => f.etiqueta === "Rayos");
  assert.ok(rayos.texto.startsWith("SENAMHI los menciona en este aviso, pero no queda claro"));
  assert.ok(rayos.cita.includes("descargas eléctricas"));
  assert.deepEqual(t.filas.find((f) => f.etiqueta === "Viento"), { etiqueta: "Viento", texto: "Ráfagas cercanas a 40 km/h" });
  assert.equal(t.filas.some((f) => f.etiqueta === "Granizo"), false);
  assert.equal(t.oficial.dia, A376.texto_dia);
  assert.equal(claveAviso(A376), "meteorologico-2026-376");
  assert.equal(
    tooltipAviso(A376, { hoy: HOY }),
    "Aviso amarillo de SENAMHI: puede llover en algún momento en esta zona hoy. Toca para ver más."
  );
  assert.equal(
    tooltipAviso(A376, { hoy: "2026-09-22" }),
    "Aviso amarillo de SENAMHI: puede llover en algún momento en esta zona mañana. Toca para ver más."
  );
});

test("gota con rayo en la sierra: rayos habituales en la sierra", () => {
  const a = {
    ...A376, icono: "gota_rayo", titulo: "PRECIPITACIONES EN LA SIERRA",
    lectura: { ...A376.lectura, regiones_titulo: ["sierra"], regiones_parrafo: ["sierra"], una_region: true, granizo: { menciona: true, sobre_m: 2800 } },
  };
  const t = textoAviso(a, { hoy: HOY });
  assert.equal(t.caja[0], "Puede llover, con rayos, en algún momento en esta zona hoy, miércoles 23 de setiembre.");
  assert.equal(t.subtitulo, "N° 376 · miércoles 23 de setiembre");
  const rayos = t.filas.find((f) => f.etiqueta === "Rayos");
  assert.equal(rayos.texto, "Posibles en toda la zona, según SENAMHI. Son habituales en las lluvias de la sierra.");
  assert.equal(t.filas.find((f) => f.etiqueta === "Granizo").texto, "Posible en zonas por encima de los 2800 m de altura");
  const costa = textoAviso({ ...a, lectura: { ...a.lectura, regiones_titulo: ["costa"] } }, { hoy: HOY });
  assert.equal(costa.filas.find((f) => f.etiqueta === "Rayos").texto, "Posibles en toda la zona, según SENAMHI.");
  assert.match(tooltipAviso(a, { hoy: HOY }), /puede llover, con rayos, en algún momento/);
});

test("aviso de 24 h: sin fila de rayos", () => {
  const t = textoAviso(A24, { hoy: HOY });
  assert.equal(t.forma, "24h");
  assert.equal(t.cabecera, "Aviso amarillo de SENAMHI · lluvia en 24 horas");
  assert.equal(t.subtitulo, "Desde las 13:00 del mar 22 set hasta las 13:00 del mié 23 set");
  assert.match(t.caja[0], /en esas 24 horas, con intensidad moderada según SENAMHI\.$/);
  assert.equal(t.filas.some((f) => f.etiqueta === "Rayos"), false);
  assert.equal(t.filas.length, 0);
  assert.equal(textoAviso({ ...A24, nivel: 3 }, { hoy: HOY }).filas[0].texto, "aniegos e inundaciones");
  assert.equal(
    tooltipAviso(A24, { hoy: "2026-09-22" }),
    "Aviso amarillo de SENAMHI: puede llover en algún momento en esta zona hasta las 13:00 de mañana. Toca para ver más."
  );
});

test("montos con barra (escala redonda)", () => {
  const m = textoAviso(A376, { hoy: HOY }).montos;
  assert.equal(m.titulo, "Lluvia que espera SENAMHI ese día (mm)");
  assert.equal(m.escala, 20);
  assert.deepEqual(m.filas.map((f) => [f.lugar, f.texto]), [
    ["Tumbes", "hasta 12 mm"],
    ["Costa de Piura", "cerca de 6 mm"],
    ["Sierra norte", "7 a 15 mm"],
  ]);
  assert.deepEqual(m.filas[0].barra, { tipo: "hasta", desde: 0, hasta: 60 });
  assert.deepEqual(m.filas[1].barra, { tipo: "cerca", desde: 30, hasta: 30 });
  assert.deepEqual(m.filas[2].barra, { tipo: "rango", desde: 35, hasta: 75 });
  const mas = montosAviso([{ lugar: "Selva centro", desde: null, hasta: 45, forma: "mas_de", unidad: "mm" }]);
  assert.equal(mas.escala, 50);
  assert.equal(mas.filas[0].texto, "más de 45 mm");
  assert.deepEqual(mas.filas[0].barra, { tipo: "mas_de", desde: 90, hasta: 100 });
  const cm = montosAviso([{ lugar: "Sierra sur", desde: null, hasta: 5, forma: "cerca", unidad: "cm" }]);
  assert.equal(cm.titulo, "Nieve que espera SENAMHI ese día (cm)");
  assert.equal(cm.filas[0].texto, "cerca de 5 cm");
  assert.equal(cm.filas[0].barra, null);
  assert.equal(montosAviso(null), null);
});

test("montos null con texto del día: la cita literal", () => {
  const a = { ...A376, lectura: { ...A376.lectura, montos: null } };
  const t = textoAviso(a, { hoy: HOY });
  assert.equal(t.montos, null);
  assert.deepEqual(t.literal, { titulo: "Lo que dice SENAMHI para ese día", texto: A376.texto_dia });
  const sinNada = textoAviso({ ...a, texto_dia: null }, { hoy: HOY });
  assert.equal(sinNada.literal, null);
  // sin lectura todavía (el worker no leyó el párrafo): gota y sin filas inventadas
  const sinLectura = textoAviso({ ...A376, lectura: null, texto_dia: null }, { hoy: HOY });
  assert.equal(sinLectura.filas.length, 0);
  assert.equal(sinLectura.titulo, "Lluvias");
});

test("insignias de calor, frío y viento; nevada y llovizna", () => {
  const calor = { ...A376, tema: "temperatura", titulo: "INCREMENTO DE TEMPERATURA DIURNA EN LA COSTA", icono: null, lectura: null };
  assert.equal(glifoAviso(calor), "termometro");
  assert.equal(glifoAviso({ ...calor, titulo: "DESCENSO DE TEMPERATURA NOCTURNA" }), "termometro_frio");
  assert.equal(glifoAviso({ ...calor, tema: "viento" }), "viento");
  assert.equal(glifoAviso({ ...calor, tema: "otro" }), null);
  assert.equal(tooltipAviso({ ...calor, nivel: 4 }, { hoy: HOY }), "Aviso rojo de SENAMHI por calor. Toca para ver más.");
  assert.equal(textoAviso(calor, { hoy: HOY }).forma, "otro");
  const nevada = { ...A376, icono: "copo", lectura: { ...A376.lectura, fenomeno: "nevada", nieve: { menciona: true, sobre_m: 4000 } } };
  const n = textoAviso(nevada, { hoy: HOY });
  assert.equal(n.caja[0], "Puede nevar en algún momento en las partes altas de esta zona hoy, miércoles 23 de setiembre.");
  assert.equal(n.caja[1], "No quiere decir que nieve en toda la zona ni todo el día.");
  assert.equal(n.filas.find((f) => f.etiqueta === "Nieve").texto, "Por encima de los 4000 m de altura, según SENAMHI");
  assert.equal(n.filas.find((f) => f.etiqueta === "Rayos").texto, "SENAMHI también los menciona.");
  const llovizna = { ...A376, lectura: { ...A376.lectura, fenomeno: "llovizna", descargas: "no" } };
  assert.match(tooltipAviso(llovizna, { hoy: "2026-09-21" }), /puede lloviznar en algún momento en esta zona el miércoles 23\./);
  assert.equal(textoAviso(llovizna, { hoy: HOY }).filas.some((f) => f.etiqueta === "Rayos"), false);
});
