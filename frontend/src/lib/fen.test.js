import { test } from "node:test";
import assert from "node:assert/strict";
import {
  EVENTOS_FEN, OPCIONES_FEN, DEFECTO_FEN, valorFEN, partirFEN, etiquetaFEN, mesesCortos, migrarValorFEN, esValorFEN,
} from "./fen.js";

test("una opción por evento y trimestre, ordenadas por evento y luego por trimestre", () => {
  assert.equal(OPCIONES_FEN.length, 13); // lo que trae la tabla mapa el 25-10-2026
  assert.deepEqual(
    OPCIONES_FEN.map((o) => o.valor),
    [
      "1982-1983|DEF", "1982-1983|EFM", "1982-1983|FMA",
      "1997-1998|DEF", "1997-1998|EFM", "1997-1998|FMA",
      "2017|DEF", "2017|EFM", "2017|FMA",
      "2023|EFM", "2023|FMA",
      "2023-2024|DEF", "2023-2024|EFM",
    ]
  );
  assert.ok(esValorFEN(DEFECTO_FEN));
  assert.ok(esValorFEN("2017|FMA"), "2017 feb a abr (marzo: desborde del Piura) tiene que ofrecerse");
  assert.equal(new Set(OPCIONES_FEN.map((o) => o.valor)).size, OPCIONES_FEN.length);
});

test("etiquetas con los meses cortos", () => {
  assert.equal(etiquetaFEN("1997-1998", "DEF"), "El Niño 1997-1998, dic a feb");
  assert.equal(etiquetaFEN("2017", "FMA"), "El Niño costero 2017, feb a abr");
  assert.equal(etiquetaFEN("2023", "EFM"), "El Niño costero 2023, ene a mar");
  assert.equal(etiquetaFEN("2023-2024"), "El Niño 2023-2024");
  assert.equal(etiquetaFEN("1900", "DEF"), "El Niño 1900, dic a feb"); // evento desconocido: no rompe
  assert.equal(mesesCortos("XYZ"), "XYZ");
});

test("valor <periodo>|<trimestre> se arma y se parte", () => {
  assert.equal(valorFEN("2017", "FMA"), "2017|FMA");
  assert.deepEqual(partirFEN("2017|FMA"), { periodo: "2017", trimestre: "FMA" });
  assert.deepEqual(partirFEN("2017"), { periodo: "2017", trimestre: null });
  assert.deepEqual(partirFEN(null), { periodo: null, trimestre: null });
});

test("valores viejos (solo el evento) van al primer trimestre del evento", () => {
  assert.equal(migrarValorFEN("1997-1998"), "1997-1998|DEF");
  assert.equal(migrarValorFEN("2023"), "2023|EFM"); // el Costero 2023 no tiene DEF
  assert.equal(migrarValorFEN("2017|FMA"), "2017|FMA"); // ya nuevo: igual
  assert.equal(migrarValorFEN("1600"), "1600"); // desconocido: igual (preferencias lo descarta)
  assert.equal(migrarValorFEN(undefined), undefined);
  for (const e of EVENTOS_FEN) assert.ok(esValorFEN(migrarValorFEN(e.periodo)), e.periodo);
});
