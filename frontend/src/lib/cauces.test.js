import test from "node:test";
import assert from "node:assert/strict";
import {
  GEOMETRIAS, aLatLngs, aligerar, avisosDe, cajaConMargen, cajaDeLineas, cajasSeCruzan, detallePorZoom, elegirRotulados, emparejarCauces,
  enVista, esFuerte, estadoRio, guardarDetalle, latLngsTramo, lecturasDelCauce, licenciaCorta, lista, notaAuras, notaCauces, peorLectura, tramoCubre, tramoVisible,
} from "./cauces.js";

// filas reales de rio_cauce_mapa y caudal_actual (14-10-2026), recortadas
const HUALLAGA = {
  rio_ana: "huallaga", rio: "Huallaga", nombre: "Río Huallaga", departamento: "Huánuco, Loreto, San Martín",
  estaciones: ["Lagunas", "Picota", "Puente Pérez", "Tingo María"], estaciones_senamhi: ["230603"], vigilado: false,
  cauce_lejos: { type: "MultiLineString", coordinates: [[[-76.2, -9.9], [-76.0, -9.5], [-75.8, -9.0]], [[-75.5, -6.0], [-75.3, -5.5]]] },
};
const JEQUETEPEQUE = {
  rio_ana: "jequetepeque", rio: "Jequetepeque", nombre: "Río Jequetepeque", departamento: "Cajamarca, La Libertad",
  estaciones: ["Yonán"], estaciones_senamhi: [], vigilado: false,
  cauce_lejos: { type: "MultiLineString", coordinates: [[[-79.2, -7.3], [-79.0, -7.25], [-78.8, -7.2]]] },
};
const MASHCON_CAUCE = { rio_ana: "mashcon", rio: "Mashcon", nombre: "Río Mashcón", estaciones: ["Mashcón"], vigilado: true, cauce_lejos: { type: "MultiLineString", coordinates: [[[-78.5, -7.1], [-78.51, -7.15]]] } };
const LAGUNAS = { estacion: "Lagunas", rio: "Huallaga", valor: 111.84, unidad: "m.s.n.m", umbral_alerta: 111.95, umbral_emergencia: 111.21, tendencia: "Ascendente", lat: -5.23, lon: -75.67 };
const PICOTA = { estacion: "Picota", rio: "Huallaga", valor: 938.54, unidad: "m³/s", umbral_alerta: 8130.38, umbral_emergencia: 9883.48, tendencia: "Ascendente", lat: -6.92, lon: -76.33 };
const TINGO = { estacion: "Tingo Maria", rio: "Huallaga", valor: 159.9, unidad: "m³/s", umbral_alerta: 1010, umbral_emergencia: 1178, lat: -9.3, lon: -76.0 };
const YONAN = { estacion: "Yonán", rio: "Jequetepeque", valor: 12, unidad: "m³/s", umbral_alerta: 400, umbral_emergencia: 600, lat: -7.25, lon: -79.0 };
const MASHCON = { estacion: "Mashcón", rio: "Mashcon", valor: 0.13, unidad: "m³/s", umbral_alerta: 14, umbral_emergencia: 18, lat: -7.1, lon: -78.5 };
const SUMBAY = { estacion: "Sumbay", rio: "Sumbay", valor: 3, unidad: "m³/s", umbral_alerta: 40, umbral_emergencia: 60, lat: -16.0, lon: -71.4 };
const VIGILADO = { id: "mashcon", nombre: "Río Mashcón", estacion_ana: "Mashcón", rio_ana: "Mashcon" };
const AHORA = new Date("2026-10-14T12:00:00Z");
const AVISO_NARANJA = { ca: 70609, ce: "230603", numero: 1645, titulo: "SITUACIÓN ACTUAL DEL NIVEL DEL RÍO HUALLAGA - ESTACIÓN LAGUNAS", nivel: 3, sentido: "crecida", inicio: "2026-10-12T05:00:00+00:00", fin: null, fin_dia: "2026-10-15", url: "https://www.senamhi.gob.pe/?p=avisos-detalle-hidrologicos&ca=70609&ce=230603", visto_en: "2026-10-14T10:58:09+00:00" };

test("lecturasDelCauce: mismo río y estación de la lista, sin tildes; otra estación del mismo río no entra", () => {
  assert.deepEqual(lecturasDelCauce(HUALLAGA, [LAGUNAS, PICOTA, TINGO, YONAN]), [LAGUNAS, PICOTA, TINGO]);
  assert.deepEqual(lecturasDelCauce(JEQUETEPEQUE, [{ ...YONAN, estacion: "Otra" }, YONAN]), [YONAN]);
});

test("emparejarCauces: salta el río vigilado (Mashcón) y deja aparte las estaciones sin trazo", () => {
  const { rios, conTrazo, sinTrazo } = emparejarCauces([HUALLAGA, JEQUETEPEQUE, MASHCON_CAUCE], [LAGUNAS, PICOTA, YONAN, MASHCON, SUMBAY], [VIGILADO]);
  assert.deepEqual(rios.map((r) => r.fila.rio_ana), ["huallaga", "jequetepeque"]);
  assert.equal(conTrazo.size, 3);
  assert.deepEqual(sinTrazo, [SUMBAY]); // el Mashcón es vigilado: ni "sin trazo" ni trazo nacional
  // un trazo no marcado vigilado pero con la estación de un río vigilado tampoco se dibuja dos veces
  const otra = emparejarCauces([{ ...MASHCON_CAUCE, vigilado: false }], [MASHCON], [VIGILADO]);
  assert.equal(otra.rios.length, 0);
});

test("peorLectura: manda la peor estación de crecida; un umbral de nivel bajo cuenta como normal", () => {
  // Lagunas está en "alerta" por nivel bajo (vaciante): no es crecida, no manda sobre Picota (normal)
  assert.equal(peorLectura([LAGUNAS, PICOTA]), LAGUNAS); // empate normal/normal: la primera
  const crecida = { ...PICOTA, valor: 8500 };
  assert.equal(peorLectura([LAGUNAS, crecida, TINGO]), crecida);
  assert.equal(peorLectura([]), null);
});

test("estadoRio: ANA manda si no hay aviso; el aviso naranja de SENAMHI manda si es más alto; uno vencido no", () => {
  const tranquilo = estadoRio({ lecturas: [PICOTA, TINGO], ahora: AHORA });
  assert.equal(tranquilo.cauce.estado, "normal");
  assert.equal(tranquilo.zona.nivel, "sin_senales");
  assert.equal(esFuerte(tranquilo), false);
  const aviso = estadoRio({ lecturas: [LAGUNAS, PICOTA, TINGO], avisos_hidro: [AVISO_NARANJA], ahora: AHORA });
  assert.equal(aviso.cauce.estado, "alerta");
  assert.equal(aviso.cauce.porAviso, true);
  assert.equal(aviso.cauce.color, "naranja");
  assert.equal(aviso.zona.nivel, "alerta");
  assert.equal(aviso.zona.avisoHidro.numero, 1645);
  assert.equal(esFuerte(aviso), true);
  const vencido = estadoRio({ lecturas: [PICOTA], avisos_hidro: [{ ...AVISO_NARANJA, fin: "2026-10-13T00:00:00Z" }], ahora: AHORA });
  assert.equal(vencido.cauce.estado, "normal");
  // ANA en emergencia por encima de un aviso naranja: manda ANA
  const peorAna = estadoRio({ lecturas: [{ ...PICOTA, valor: 9900 }], avisos_hidro: [AVISO_NARANJA], ahora: AHORA });
  assert.equal(peorAna.cauce.estado, "emergencia");
  assert.equal(peorAna.cauce.porAviso, false);
  // sin estación (río solo con aviso SENAMHI, p. ej. Biabo): sd sin aviso, el aviso si lo hay
  assert.equal(estadoRio({ lecturas: [], ahora: AHORA }).cauce.estado, "sd");
  assert.equal(estadoRio({ lecturas: [], avisos_hidro: [AVISO_NARANJA], ahora: AHORA }).cauce.estado, "alerta");
});

test("detallePorZoom: el trazo de ~50 m hasta el zoom 12 y el fino desde el 13", () => {
  assert.equal(detallePorZoom(6), "lejos");
  assert.equal(detallePorZoom(12), "lejos");
  assert.equal(detallePorZoom(13), "cauce");
  assert.equal(detallePorZoom(16), "cauce");
});

test("aligerar separa la geometría (caja incluida) y guardarDetalle la completa", () => {
  const filas = aligerar([HUALLAGA, JEQUETEPEQUE]);
  assert.equal("cauce_lejos" in filas[0], false);
  assert.equal(filas[0].nombre, "Río Huallaga");
  const g = GEOMETRIAS.get("huallaga");
  assert.equal(g.lejos.length, 2);
  assert.deepEqual(g.caja, [-76.2, -9.9, -75.3, -5.5]);
  assert.equal(g.cauce, null);
  guardarDetalle("huallaga", { type: "MultiLineString", coordinates: [[[-76.2, -9.9], [-76.1, -9.7], [-76.0, -9.5]]] });
  assert.equal(GEOMETRIAS.get("huallaga").cauce[0].length, 3);
  // una recarga de las filas no pierde el detalle ya pedido
  aligerar([HUALLAGA]);
  assert.equal(GEOMETRIAS.get("huallaga").cauce[0].length, 3);
  assert.deepEqual(cajaDeLineas({ type: "LineString", coordinates: [[1, 2], [3, 0]] }), [1, 0, 3, 2]);
  assert.equal(cajaDeLineas([]), null);
});

test("enVista filtra por la caja del río; cajasSeCruzan y cajaConMargen", () => {
  aligerar([HUALLAGA, JEQUETEPEQUE]);
  const rios = [{ fila: HUALLAGA }, { fila: JEQUETEPEQUE }];
  // vista sobre Cajamarca: solo el Jequetepeque
  assert.deepEqual(enVista(rios, [-79.5, -7.6, -78.4, -6.9]).map((r) => r.fila.rio_ana), ["jequetepeque"]);
  // el país entero: los dos
  assert.equal(enVista(rios, [-82, -19, -68, 0]).length, 2);
  assert.equal(cajasSeCruzan([0, 0, 1, 1], [1, 1, 2, 2]), true); // se tocan en la esquina
  assert.equal(cajasSeCruzan([0, 0, 1, 1], [1.1, 0, 2, 1]), false);
  assert.equal(cajasSeCruzan(null, [0, 0, 1, 1]), false);
  assert.deepEqual(cajaConMargen([0, 0, 10, 20], 0.1), [-1, -2, 11, 22]);
});

test("tramoVisible: el tramo más largo con vértices seguidos dentro de la caja; tramoCubre con margen", () => {
  const partes = [
    [[-76.2, -9.9], [-76.0, -9.5], [-75.8, -9.0], [-75.6, -8.0], [-75.5, -7.0]],
    [[-75.5, -6.0], [-75.3, -5.5]],
  ];
  // la caja toma los 3 últimos vértices de la parte 0 y toda la parte 1 (más corta)
  const t = tramoVisible(partes, [-76, -9.2, -75, -5]);
  assert.equal(t.parte, 0);
  assert.equal(t.i0, 2);
  assert.equal(t.i1, 4);
  assert.ok(t.km > 200);
  // un solo vértice dentro no es tramo
  assert.equal(tramoVisible(partes, [-76.3, -10, -76.1, -9.8]), null);
  // caja vacía
  assert.equal(tramoVisible(partes, [0, 0, 1, 1]), null);
  assert.equal(tramoCubre({ parte: 0, i0: 1, i1: 4 }, { parte: 0, i0: 2, i1: 3 }), true);
  assert.equal(tramoCubre({ parte: 0, i0: 1, i1: 4 }, { parte: 0, i0: 0, i1: 3 }), false);
  assert.equal(tramoCubre({ parte: 0, i0: 1, i1: 4 }, { parte: 1, i0: 1, i1: 2 }), false);
  assert.equal(tramoCubre(null, { parte: 0, i0: 1, i1: 2 }), false);
});

test("elegirRotulados: primero los ríos en alerta o emergencia, después el tramo visible más largo, con tope", () => {
  aligerar([HUALLAGA, JEQUETEPEQUE]);
  const rios = [{ fila: JEQUETEPEQUE }, { fila: HUALLAGA }];
  const estados = new Map([
    ["huallaga", estadoRio({ lecturas: [PICOTA], ahora: AHORA })],
    ["jequetepeque", estadoRio({ lecturas: [{ ...YONAN, valor: 450 }], ahora: AHORA })],
  ]);
  const pais = [-82, -19, -68, 0];
  const r = elegirRotulados(rios, pais, estados);
  assert.deepEqual(r.map((x) => x.rio.fila.rio_ana), ["jequetepeque", "huallaga"]); // el Jequetepeque en alerta va primero
  assert.equal(r[1].tramo.parte, 0); // el tramo largo del Huallaga, no la parte corta
  // sin alerta, gana el más largo a la vista; el tope recorta
  estados.set("jequetepeque", estadoRio({ lecturas: [YONAN], ahora: AHORA }));
  assert.deepEqual(elegirRotulados(rios, pais, estados, 1).map((x) => x.rio.fila.rio_ana), ["huallaga"]);
  // fuera de la vista no se rotula
  assert.equal(elegirRotulados(rios, [0, 0, 1, 1], estados).length, 0);
});

test("notaCauces dice cuántos ríos, cuáles están fuertes y cuántas estaciones quedan sin trazo", () => {
  const sinTrazo = [{ rio: "Titicaca", estacion: "Muelle Enafer" }, SUMBAY, { estacion: "Túnel Kovire", rio: "Canopampa" }];
  assert.equal(
    notaCauces({ resaltados: 100, fuertes: ["Río Huallaga"], sinTrazo }),
    "100 ríos del país resaltados con el trazo de ANA; en alerta o emergencia: Río Huallaga; 3 estaciones sin trazo del río (Titicaca, Sumbay y Canopampa)."
  );
  // varias estaciones de un mismo río cuentan una vez en los ejemplos; pasadas 3, "y N más"
  const mantaro = ["Puente Stuart", "La Mejorada", "Pongor"].map((estacion) => ({ rio: "Mantaro", estacion }));
  assert.equal(
    notaCauces({ resaltados: 2, sinTrazo: [...mantaro, ...sinTrazo, { rio: "Yauca", estacion: "Yauca" }] }),
    "2 ríos del país resaltados con el trazo de ANA; 7 estaciones sin trazo del río (Mantaro, Titicaca, Sumbay y 2 más)."
  );
  assert.equal(notaCauces({ resaltados: 1 }), "1 río del país resaltado con el trazo de ANA.");
});

test("notaAuras, lista y licenciaCorta", () => {
  assert.equal(notaAuras([]), "");
  assert.equal(notaAuras(["Río Nanay"]), "Aura en el cauce de 1 río del país en alerta o emergencia: Río Nanay.");
  assert.equal(
    notaAuras(["Río Nanay", "Río Huallaga", "Río Marañón", "Río Amazonas", "Río Napo"]),
    "Aura en el cauce de 5 ríos del país en alerta o emergencia: Río Nanay, Río Huallaga, Río Marañón y 2 más."
  );
  assert.equal(lista(["a", "a", "b"]), "a y b");
  assert.equal(lista([]), "");
  assert.equal(
    licenciaCorta("Información pública del Estado peruano publicada por la ANA (GeoSNIRH) sin texto de licencia; se cita la fuente"),
    "Información pública del Estado peruano publicada por la ANA (GeoSNIRH) sin texto de licencia"
  );
});

test("aLatLngs, latLngsTramo y avisosDe", () => {
  const partes = [[[-76.2, -9.9], [-76.0, -9.5], [-75.8, -9.0]], [[-75.5, -6.0], [-75.3, -5.5]]];
  assert.deepEqual(aLatLngs(partes)[1], [[-6.0, -75.5], [-5.5, -75.3]]);
  assert.deepEqual(latLngsTramo(partes, { parte: 0, i0: 1, i1: 2 }), [[-9.5, -76.0], [-9.0, -75.8]]);
  const senales = [{ rio_ana: "huallaga", avisos_hidro: [AVISO_NARANJA] }, { rio_ana: "mayo", avisos_hidro: [] }];
  assert.deepEqual(avisosDe(senales, "huallaga"), [AVISO_NARANJA]);
  assert.deepEqual(avisosDe(senales, "mayo"), []);
  assert.deepEqual(avisosDe(senales, "napo"), []);
  assert.deepEqual(avisosDe(null, "napo"), []);
});
