import test from "node:test";
import assert from "node:assert/strict";
import {
  agruparIncidentes, anioCorto, caudalDelRio, distanciaAZona, estadoCauce, estadoZona, fraseCorta, metrosEntre, notaZonas,
  pasoAntes, simular,
} from "./zonaRio.js";
import { textoRio } from "./lenguaje.js";

const RIO = { id: "mashcon", nombre: "Río Mashcón", estacion_ana: "Mashcón", rio_ana: "Mashcon" };
// datos reales del 2026-10-02/03 (caudal_actual, aviso_vigente id 296, lluvia_senamhi_actual)
const CAUDAL = { estacion: "Mashcón", rio: "Mashcon", valor: 0.13, unidad: "m³/s", umbral_alerta: 14, umbral_emergencia: 18, tendencia: "Descendente" };
const AVISO_NARANJA_HOY = { id: 296, tipo: "lluvia24h", nivel: 3, titulo: "AVISO DE CORTO PLAZO ANTE LLUVIAS INTENSAS", inicio: "2026-10-02T18:00:00+00:00", fin: "2026-10-03T18:00:00+00:00", en_curso: true, url: null };
const AVISO_AMARILLO_HOY = { ...AVISO_NARANJA_HOY, id: 295, nivel: 2 };
const AVISO_NARANJA_MANANA = { ...AVISO_NARANJA_HOY, id: 277, tipo: "meteorologico", inicio: "2026-10-04T05:00:00+00:00", fin: "2026-10-05T04:59:59+00:00", en_curso: false };
const GORE_SECO = { clave: "RIO GRANDE GORE@-7.09094,-78.52073", nombre: "RIO GRANDE GORE", pp_1h: 0, umbral_1h: 5, pp_6h: 0, umbral_6h: 15 };
const AHORA = new Date("2026-10-03T06:00:00Z");
const senal = (x = {}) => ({ avisos_lluvia: [], lluvia_cuenca: [], avisos_hidro: [], ...x });

test("aviso hidrológico: el último conocido con SENAMHI caído se menciona; uno sin nivel no sube la zona", () => {
  const rojo = { ca: 1, numero: 1169, nivel: 4, sentido: "crecida", fin: "2026-10-03T21:00:00Z", url: "https://www.senamhi.gob.pe/x", visto_en: "2026-10-03T01:00:00Z" };
  const e = estadoZona({ caudal: CAUDAL, senal: senal({ avisos_hidro: [rojo] }), ahora: AHORA });
  assert.equal(e.nivel, "emergencia");
  assert.deepEqual(e.menciones.map((m) => m.clave), ["hidro_viejo"]);
  const fresco = estadoZona({ caudal: CAUDAL, senal: senal({ avisos_hidro: [{ ...rojo, visto_en: "2026-10-03T05:30:00Z" }] }), ahora: AHORA });
  assert.equal(fresco.menciones.length, 0);
  const sin = estadoZona({ caudal: CAUDAL, senal: senal({ avisos_hidro: [{ ...rojo, nivel: null }] }), ahora: AHORA });
  assert.equal(sin.nivel, "sin_senales");
  assert.deepEqual(sin.menciones.map((m) => m.clave), ["hidro_sin_nivel"]);
});

test("caudalDelRio empareja estación y río sin tildes", () => {
  assert.equal(caudalDelRio(RIO, [{ estacion: "Otra", rio: "Mashcon" }, CAUDAL]), CAUDAL);
  assert.equal(caudalDelRio(RIO, [{ estacion: "Mashcón", rio: "Chonta" }]), null);
});

test("hoy (caso real): río tranquilo + aviso naranja de lluvia sobre la cuenca = atentos", () => {
  const e = estadoZona({ caudal: CAUDAL, senal: senal({ avisos_lluvia: [AVISO_NARANJA_HOY, AVISO_AMARILLO_HOY], lluvia_cuenca: [GORE_SECO] }), ahora: AHORA });
  assert.equal(e.nivel, "atentos");
  assert.deepEqual(e.senales.map((s) => s.clave), ["aviso_lluvia"]);
  assert.match(e.senales[0].titulo, /Aviso naranja de SENAMHI por lluvias sobre la cuenca/);
  assert.equal(e.menciones.length, 0); // el amarillo no se menciona si ya hay uno naranja
  assert.equal(e.senales[0].url, "https://www.senamhi.gob.pe/?p=aviso-24H");
  assert.match(e.senales[0].texto, /^Vigente hasta el 3 de octubre( de 2026)?, 1:00\sp\.\sm\.$/); // un solo punto al final
  // el aviso es un pronóstico: no se dice que llueve fuerte
  assert.equal(fraseCorta(RIO, e).texto, "Río Mashcón: tranquilo, pero hay aviso de SENAMHI por lluvia fuerte sobre su cuenca.");
});

test("solo aviso amarillo de lluvia o aviso naranja de mañana: no sube, se menciona", () => {
  const e = estadoZona({ caudal: CAUDAL, senal: senal({ avisos_lluvia: [AVISO_AMARILLO_HOY, AVISO_NARANJA_MANANA] }), ahora: AHORA });
  assert.equal(e.nivel, "sin_senales");
  assert.deepEqual(e.menciones.map((m) => m.clave).sort(), ["aviso_amarillo", "aviso_manana"]);
  assert.equal(notaZonas([{ rio: RIO, estado: e }]), "Ningún río vigilado tiene señales ahora. Toca una zona para ver qué pasó antes.");
});

test("lluvia medida sobre la referencia en la cuenca = atentos (no es aviso oficial)", () => {
  const e = estadoZona({ caudal: CAUDAL, senal: senal({ lluvia_cuenca: [{ ...GORE_SECO, pp_1h: 7.2, pp_6h: 7.2 }] }), ahora: AHORA });
  assert.equal(e.nivel, "atentos");
  assert.match(e.senales[0].texto, /RIO GRANDE GORE: 7,2 mm en la última hora \(referencia de SENAMHI: 5 mm\)|RIO GRANDE GORE: 7.2 mm/);
  assert.match(e.senales[0].texto, /No es un aviso oficial/);
  assert.equal(fraseCorta(RIO, e).texto, "Río Mashcón: tranquilo, pero llovió fuerte en su cuenca.");
});

test("ANA: 80 % del caudal de alerta = atentos; 14 = alerta; 18 = emergencia (la lluvia no sube más)", () => {
  const conLluvia = senal({ avisos_lluvia: [AVISO_NARANJA_HOY] });
  assert.equal(estadoZona({ caudal: { ...CAUDAL, valor: 11.5 }, senal: conLluvia, ahora: AHORA }).nivel, "atentos");
  const a = estadoZona({ caudal: { ...CAUDAL, valor: 15.4 }, senal: conLluvia, ahora: AHORA });
  assert.equal(a.nivel, "alerta");
  assert.equal(a.senales[0].clave, "ana");
  assert.equal(fraseCorta(RIO, a).texto, "Río Mashcón: pasó su nivel de alerta (ANA).");
  const e = estadoZona({ caudal: { ...CAUDAL, valor: 19 }, ahora: AHORA });
  assert.equal(e.nivel, "emergencia");
  assert.match(fraseCorta(RIO, e).accion, /Defensa Civil/);
});

test("umbrales de vaciante (río muy bajo) no encienden la zona", () => {
  const bajo = { ...CAUDAL, valor: 1, umbral_alerta: 3, umbral_emergencia: 2 };
  assert.equal(estadoZona({ caudal: bajo, ahora: AHORA }).nivel, "sin_senales");
});

test("aviso hidrológico de SENAMHI: amarillo atentos, naranja alerta, rojo emergencia; descenso y vencido no cuentan", () => {
  const h = { ca: 1, numero: 1700, sentido: "crecida", nivel: 4, valor: 30.17, unidad: "m3/s", fin: "2026-10-03T21:00:00Z", url: "https://www.senamhi.gob.pe/?p=x" };
  const e = estadoZona({ caudal: CAUDAL, senal: senal({ avisos_hidro: [h] }), ahora: AHORA });
  assert.equal(e.nivel, "emergencia");
  assert.match(e.senales[0].texto, /30,17 m³\/s|30.17 m³\/s/);
  assert.equal(fraseCorta(RIO, e).texto, "Río Mashcón: aviso hidrológico rojo de SENAMHI.");
  assert.equal(estadoZona({ senal: senal({ avisos_hidro: [{ ...h, nivel: 2 }] }), ahora: AHORA }).nivel, "atentos");
  assert.equal(estadoZona({ senal: senal({ avisos_hidro: [{ ...h, sentido: "descenso" }] }), ahora: AHORA }).nivel, "sin_senales");
  assert.equal(estadoZona({ senal: senal({ avisos_hidro: [{ ...h, fin: "2026-10-03T01:00:00Z" }] }), ahora: AHORA }).nivel, "sin_senales");
});

test("sin caudal ni señales: sin_senales y se dice que ANA no tiene medición", () => {
  const e = estadoZona({ ahora: AHORA });
  assert.equal(e.nivel, "sin_senales");
  assert.equal(e.menciones[0].clave, "sin_ana");
});

test("incidentes: año corto, agrupados por punto y del más nuevo al más viejo", () => {
  assert.equal(anioCorto({ fecha: "2014-03-26" }), "’14");
  assert.equal(anioCorto({ fecha: null, fecha_texto: "2012–2013" }), "’12");
  const g = agruparIncidentes([
    { id: "a", fecha: "2025-03-16", lat: -7.18001, lon: -78.47235 },
    { id: "b", fecha: "2025-03-20", lat: -7.18001, lon: -78.47235 },
    { id: "c", fecha: "1974-02-22", lat: null, lon: null },
    { id: "d", fecha: null, fecha_texto: "2012–2013", lat: -7.11526, lon: -78.52733 },
  ]);
  assert.equal(g.length, 2);
  assert.deepEqual(g[0].incidentes.map((i) => i.id), ["b", "a"]);
  const p = pasoAntes([{ id: "x", tipo: "desborde", fecha: "2016-03-20" }, { id: "y", tipo: "crecida", fecha: "2021-12-06" }, { id: "z", tipo: "puente", fecha: "2025-03-20" }], 1);
  assert.deepEqual(p.danos.map((i) => i.id), ["z"]);
  assert.equal(p.mas, 1);
  assert.deepEqual(p.crecidas.map((i) => i.id), ["y"]);
});

const RIO_SIM = { ...RIO, lugares_aviso: [{ nombre: "Bambamarca Chico" }, { nombre: "Tartar Grande" }] };

test("simular: el caudal de ANA cambia solo para ese río; sin parámetro no se activa", () => {
  const datos = { rio: RIO_SIM, caudal: CAUDAL, senal: senal() };
  const a = simular(datos, "mashcon:15.4", AHORA);
  assert.equal(a.activa, true);
  assert.equal(a.caudal.valor, 15.4);
  assert.equal(CAUDAL.valor, 0.13); // no toca la fila original
  assert.equal(estadoZona({ caudal: a.caudal, senal: a.senal, ahora: AHORA }).nivel, "alerta");
  assert.equal(simular(datos, "chonta:19", AHORA).activa, false);
  assert.equal(simular(datos, null, AHORA).activa, false);
  assert.equal(simular(datos, "mashcon:nada", AHORA).activa, false);
  // sin fila de ANA no hay umbrales: no se inventa
  assert.equal(simular({ ...datos, caudal: null }, "mashcon:19", AHORA).activa, false);
});

test("simular: aviso hidrológico vigente falso (valor 15, url #) y lluvia fuerte en RIO GRANDE GORE", () => {
  const h = simular({ rio: RIO_SIM, caudal: CAUDAL, senal: null }, "mashcon:hidro3", AHORA);
  const e = estadoZona({ caudal: h.caudal, senal: h.senal, ahora: AHORA });
  assert.equal(e.nivel, "alerta");
  assert.equal(e.avisoHidro.valor, 15);
  assert.equal(e.avisoHidro.url, "#");
  assert.match(e.avisoHidro.areas, /^Las potenciales áreas de afectación serían los centros poblados de BAMBAMARCA CHICO y TARTAR GRANDE/);
  assert.equal(fraseCorta(RIO, e).texto, "Río Mashcón: aviso hidrológico naranja de SENAMHI.");
  const l = simular({ rio: RIO_SIM, caudal: CAUDAL, senal: senal({ lluvia_cuenca: [GORE_SECO] }) }, "mashcon:lluvia", AHORA);
  assert.equal(l.senal.lluvia_cuenca.length, 1); // reemplaza la lectura real de la estación
  const el = estadoZona({ caudal: l.caudal, senal: l.senal, ahora: AHORA });
  assert.equal(el.nivel, "atentos");
  assert.match(el.senales[0].texto, /RIO GRANDE GORE: 7.2 mm en la última hora/);
  // calma: sin señales en la cuenca (con el río tranquilo, la zona queda sin señales)
  const c = simular({ rio: RIO_SIM, caudal: CAUDAL, senal: senal({ avisos_lluvia: [AVISO_NARANJA_HOY] }) }, "mashcon:calma", AHORA);
  assert.equal(c.activa, true);
  assert.equal(estadoZona({ caudal: c.caudal, senal: c.senal, ahora: AHORA }).nivel, "sin_senales");
  // varias a la vez
  const dos = simular({ rio: RIO_SIM, caudal: CAUDAL, senal: null }, "mashcon:19,mashcon:hidro2", AHORA);
  assert.equal(estadoZona({ caudal: dos.caudal, senal: dos.senal, ahora: AHORA }).nivel, "emergencia");
});

test("incidentes cercanos: con un radio en metros se juntan en el punto del más nuevo", () => {
  // Huacariz (2 de 2025) y la bocatoma de ANA (2022) a ~63 m; El Molino y el muro de 2022 a ~51 m
  const inc = [
    { id: "huac1", fecha: "2025-03-16", lat: -7.18001, lon: -78.47235 },
    { id: "huac2", fecha: "2025-03-20", lat: -7.18001, lon: -78.47235 },
    { id: "8759", fecha: "2022-03-08", lat: -7.17961, lon: -78.47275 },
    { id: "muro", fecha: "2022-03-07", lat: -7.11483, lon: -78.5275 },
    { id: "molino", fecha: null, fecha_texto: "2012–2013", lat: -7.11526, lon: -78.52733 },
  ];
  assert.ok(Math.abs(metrosEntre(-7.18001, -78.47235, -7.17961, -78.47275) - 63) < 3);
  assert.equal(agruparIncidentes(inc).length, 4); // por defecto (~10 m) solo el mismo punto
  const g = agruparIncidentes(inc, 150);
  assert.equal(g.length, 2);
  assert.deepEqual(g[0].incidentes.map((i) => i.id), ["huac2", "huac1", "8759"]);
  assert.deepEqual([g[0].lat, g[0].lon], [-7.18001, -78.47235]);
  assert.deepEqual(g[1].incidentes.map((i) => i.id), ["muro", "molino"]);
});

test("pasó antes: con la zona tocada, primero los más cercanos y con su distancia", () => {
  // cuadrado de ~1,1 km alrededor de (-7.145, -78.515)
  const zona = { type: "Polygon", coordinates: [[[-78.52, -7.15], [-78.51, -7.15], [-78.51, -7.14], [-78.52, -7.14], [-78.52, -7.15]]] };
  assert.equal(distanciaAZona(-7.145, -78.515, zona), 0);
  assert.ok(Math.abs(distanciaAZona(-7.145, -78.5, zona) - 1105) < 15); // ~1,1 km al este
  assert.equal(distanciaAZona(-7.145, -78.5, null), null);
  const inc = [
    { id: "lejos", tipo: "puente", fecha: "2025-03-20", lat: -7.18001, lon: -78.47235 },
    { id: "dentro", tipo: "erosion", fecha: "2019-03-06", lat: -7.14402, lon: -78.51848 },
    { id: "cerca", tipo: "puente", fecha: "2012-11-28", lat: -7.14216, lon: -78.50904 },
    { id: "distrito", tipo: "desborde", fecha: "1974-02-22", lat: null, lon: null },
    { id: "rojo", tipo: "crecida", fecha: "2021-12-06" },
  ];
  const p = pasoAntes(inc, 3, { type: "MultiPolygon", coordinates: [zona.coordinates] });
  assert.deepEqual(p.danos.map((i) => i.id), ["dentro", "cerca", "lejos"]);
  assert.equal(p.danos[0].distM, 0);
  assert.ok(p.danos[1].distM > 0 && p.danos[1].distM < 1000);
  assert.ok(p.danos[2].distM > 4000);
  assert.equal(p.mas, 1);
  assert.deepEqual(p.crecidas.map((i) => i.id), ["rojo"]);
  // sin zona: del más nuevo al más viejo
  assert.deepEqual(pasoAntes(inc, 3).danos.map((i) => i.id), ["lejos", "dentro", "cerca"]);
});

test("estadoCauce: el aviso hidrológico de SENAMHI pinta el río si es más alto que lo que mide ANA", () => {
  const t = textoRio(CAUDAL); // tranquilo, 0.13 m³/s
  assert.deepEqual(estadoCauce(t, null), { estado: "normal", porAviso: false, color: null });
  assert.deepEqual(estadoCauce(t, { nivel: 4 }), { estado: "emergencia", porAviso: true, color: "rojo" });
  assert.deepEqual(estadoCauce(t, { nivel: 2 }), { estado: "atento", porAviso: true, color: "amarillo" });
  // ANA ya en emergencia: manda ANA
  assert.equal(estadoCauce(textoRio({ ...CAUDAL, valor: 19 }), { nivel: 3 }).porAviso, false);
  // sin medición: el aviso igual se ve
  assert.equal(estadoCauce(null, { nivel: 3 }).estado, "alerta");
  assert.equal(estadoCauce(null, null).estado, "sd");
});
