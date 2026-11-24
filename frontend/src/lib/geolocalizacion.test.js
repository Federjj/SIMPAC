import test from "node:test";
import assert from "node:assert/strict";
import {
  LIMITES,
  avisoPrecision,
  calidadPrecision,
  codigoError,
  contextoSeguro,
  esFalloGps,
  esPrecisa,
  estadoPermiso,
  lecturaDe,
  mejorLectura,
  opcionesFina,
  opcionesRapida,
  peorCodigo,
  revisarEntorno,
  sePuedeReintentar,
  textoBuscando,
  textoFalloCorto,
  textoMetrosPrecision,
  textoPrecision,
  textoSinGps,
  ubicar,
} from "./geolocalizacion.js";

// Cajamarca (plaza de armas), lo que devolvería el navegador.
const posicion = (accuracy, timestamp = 1_700_000_000_000, lat = -7.1638, lon = -78.5003) => ({ coords: { latitude: lat, longitude: lon, accuracy }, timestamp });
const errorNav = (code, message = "") => ({ code, message, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 });

// navigator.geolocation simulado: guarda los callbacks para que la prueba los dispare cuando quiera.
function geoFalsa() {
  const g = {
    pedidos: [], // getCurrentPosition: { ok, error, opciones }
    watches: [], // watchPosition: { id, ok, error, opciones }
    limpiados: [],
    getCurrentPosition(ok, error, opciones) {
      g.pedidos.push({ ok, error, opciones });
    },
    watchPosition(ok, error, opciones) {
      const id = g.watches.length + 1;
      g.watches.push({ id, ok, error, opciones });
      return id;
    },
    clearWatch(id) {
      g.limpiados.push(id);
    },
  };
  return g;
}

// setTimeout simulado: la prueba dispara el temporizador a mano.
function relojFalso() {
  const r = { programados: [], borrados: [] };
  r.programar = (fn, ms) => {
    const id = r.programados.length + 1;
    r.programados.push({ id, fn, ms });
    return id;
  };
  r.desprogramar = (id) => r.borrados.push(id);
  r.disparar = () => r.programados.forEach((t) => !r.borrados.includes(t.id) && t.fn());
  return r;
}

const tick = () => new Promise((r) => setImmediate(r));

test("lecturaDe: coordenadas, precisión redondeada y hora; sin accuracy la precisión es null", () => {
  assert.deepEqual(lecturaDe(posicion(24.6)), { lat: -7.1638, lon: -78.5003, precisionM: 25, hora: 1_700_000_000_000 });
  assert.equal(lecturaDe({ coords: { latitude: -7, longitude: -78 } }).precisionM, null);
  assert.equal(lecturaDe({ coords: { latitude: -7, longitude: -78, accuracy: -1 } }).precisionM, null);
  assert.equal(lecturaDe(null).lat, undefined);
});

test("mejorLectura: gana la de menor precisión, la conocida sobre la desconocida y la más nueva en empate", () => {
  const gruesa = { lat: -7.16, lon: -78.5, precisionM: 1500, hora: 1 };
  const fina = { lat: -7.1638, lon: -78.5003, precisionM: 25, hora: 2 };
  const sinPrecision = { lat: -7.16, lon: -78.5, precisionM: null, hora: 3 };
  const sinPrecisionNueva = { lat: -7.17, lon: -78.5, precisionM: null, hora: 4 };
  assert.equal(mejorLectura(gruesa, fina), fina);
  assert.equal(mejorLectura(fina, gruesa), fina);
  assert.equal(mejorLectura(sinPrecision, gruesa), gruesa);
  assert.equal(mejorLectura(gruesa, sinPrecision), gruesa);
  assert.equal(mejorLectura(sinPrecision, sinPrecisionNueva), sinPrecisionNueva);
  assert.equal(mejorLectura({ ...fina, hora: 9 }, { ...fina, hora: 1 }).hora, 9);
  assert.equal(mejorLectura(null, fina), fina);
  assert.equal(mejorLectura(fina, null), fina);
  assert.equal(mejorLectura(null, { lat: NaN, lon: -78 }), null);
  assert.equal(esPrecisa(fina), true);
  assert.equal(esPrecisa(gruesa), false);
  assert.equal(esPrecisa(sinPrecision), false);
  assert.equal(esPrecisa({ ...gruesa, precisionM: 30 }), true); // el límite incluido
});

test("codigoError, peorCodigo y las opciones de cada lectura", () => {
  assert.equal(codigoError(errorNav(1)), "denied");
  assert.equal(codigoError(errorNav(2)), "unavailable");
  assert.equal(codigoError(errorNav(3)), "timeout");
  assert.equal(codigoError(errorNav(1, "Only secure origins are allowed (see: https://goo.gl/Y0ZkNV).")), "insecure");
  assert.equal(codigoError(undefined), "unavailable");
  assert.equal(peorCodigo("timeout", "unavailable"), "unavailable");
  assert.equal(peorCodigo("unavailable", "timeout"), "unavailable");
  assert.equal(peorCodigo(null, "timeout"), "timeout");
  assert.equal(peorCodigo("timeout", null), "timeout");
  assert.equal(peorCodigo(null, null), null);
  assert.deepEqual(opcionesRapida(), { enableHighAccuracy: false, timeout: 6000, maximumAge: 60_000 });
  assert.deepEqual(opcionesFina(), { enableHighAccuracy: true, timeout: 22_000, maximumAge: 0 });
  assert.equal(LIMITES.precisionBuenaM, 30);
});

test("contextoSeguro y revisarEntorno: https o localhost; sin geolocation no se puede pedir", () => {
  assert.equal(contextoSeguro({ isSecureContext: true }), true);
  assert.equal(contextoSeguro({ isSecureContext: false }), false);
  assert.equal(contextoSeguro({ location: { protocol: "https:", hostname: "simpac-v7nf.vercel.app" } }), true);
  assert.equal(contextoSeguro({ location: { protocol: "http:", hostname: "localhost" } }), true);
  assert.equal(contextoSeguro({ location: { protocol: "http:", hostname: "127.0.0.1" } }), true);
  assert.equal(contextoSeguro({ location: { protocol: "http:", hostname: "192.168.1.20" } }), false);
  assert.equal(contextoSeguro(null), false);
  const geo = {};
  assert.equal(revisarEntorno({ isSecureContext: true, navigator: { geolocation: geo } }), null);
  assert.equal(revisarEntorno({ isSecureContext: false, navigator: { geolocation: geo } }), "insecure");
  assert.equal(revisarEntorno({ isSecureContext: true, navigator: {} }), "unavailable");
  assert.equal(revisarEntorno(undefined), "unavailable");
});

test("estadoPermiso: con la Permissions API devuelve el estado; sin ella o si falla, null", async () => {
  assert.equal(await estadoPermiso({ permissions: { query: async () => ({ state: "granted" }) } }), "granted");
  assert.equal(await estadoPermiso({ permissions: { query: async () => ({ state: "prompt" }) } }), "prompt");
  assert.equal(await estadoPermiso({ permissions: { query: async () => ({ state: "raro" }) } }), null);
  assert.equal(await estadoPermiso({}), null);
  assert.equal(await estadoPermiso(undefined), null);
  assert.equal(
    await estadoPermiso({
      permissions: {
        query: () => {
          throw new TypeError("no soportado");
        },
      },
    }),
    null
  );
});

test("ubicar con permiso concedido: rápida y GPS a la vez; la primera resuelve ya y el GPS afina hasta bajar de 30 m", async () => {
  const geo = geoFalsa();
  const reloj = relojFalso();
  const mejoras = [];
  let fin = null;
  const s = ubicar(geo, { permiso: "granted", onMejora: (l) => mejoras.push(l.precisionM), onFin: (f) => (fin = f), programar: reloj.programar, desprogramar: reloj.desprogramar });
  assert.equal(geo.pedidos.length, 1);
  assert.equal(geo.watches.length, 1);
  assert.equal(geo.pedidos[0].opciones.enableHighAccuracy, false);
  assert.equal(geo.pedidos[0].opciones.maximumAge, 60_000);
  assert.equal(geo.watches[0].opciones.enableHighAccuracy, true);
  assert.equal(reloj.programados[0].ms, 22_000);

  geo.pedidos[0].ok(posicion(1500, 1)); // la red responde primero, a 1,5 km
  const primera = await s.primera;
  assert.equal(primera.precisionM, 1500);

  geo.watches[0].ok(posicion(80, 2));
  geo.watches[0].ok(posicion(120, 3)); // peor: no cambia nada
  assert.deepEqual(mejoras, [80]);
  assert.equal(fin, null);
  geo.watches[0].ok(posicion(20, 4)); // buena: se para
  assert.deepEqual(mejoras, [80, 20]);
  assert.equal(fin.motivo, "precisa");
  assert.equal(fin.lectura.precisionM, 20);
  assert.deepEqual(geo.limpiados, [1]);
  assert.deepEqual(reloj.borrados, [1]);
  geo.watches[0].ok(posicion(5, 5)); // después del fin ya no se escucha
  assert.deepEqual(mejoras, [80, 20]);
});

test("ubicar con permiso por pedir: el GPS espera a la rápida (un solo pedido de permiso); si la rápida vence, el GPS ubica", async () => {
  const geo = geoFalsa();
  const reloj = relojFalso();
  let fin = null;
  const s = ubicar(geo, { permiso: "prompt", onFin: (f) => (fin = f), programar: reloj.programar, desprogramar: reloj.desprogramar });
  assert.equal(geo.pedidos.length, 1);
  assert.equal(geo.watches.length, 0, "el watch no arranca hasta que la rápida responda");
  geo.pedidos[0].error(errorNav(3));
  assert.equal(geo.watches.length, 1);
  geo.watches[0].ok(posicion(25));
  const primera = await s.primera;
  assert.equal(primera.precisionM, 25);
  assert.equal(fin.motivo, "precisa");
});

test("ubicar sin Permissions API (permiso null) se comporta como con 'prompt'", () => {
  const geo = geoFalsa();
  ubicar(geo, { programar: () => 1, desprogramar: () => {} });
  assert.equal(geo.pedidos.length, 1);
  assert.equal(geo.watches.length, 0);
  geo.pedidos[0].ok(posicion(900));
  assert.equal(geo.watches.length, 1);
});

test("ubicar: permiso negado corta todo y no arranca nada más", async () => {
  const geo = geoFalsa();
  let fin = null;
  const s = ubicar(geo, { permiso: "granted", onFin: (f) => (fin = f), programar: () => 1, desprogramar: () => {} });
  geo.pedidos[0].error(errorNav(1));
  await assert.rejects(s.primera, { code: "denied" });
  assert.equal(fin.motivo, "error");
  assert.equal(fin.code, "denied");
  assert.deepEqual(geo.limpiados, [1]);

  // con la Permissions API diciendo denied no se llama al navegador
  const geo2 = geoFalsa();
  const s2 = ubicar(geo2, { permiso: "denied" });
  await assert.rejects(s2.primera, { code: "denied" });
  assert.equal(geo2.pedidos.length, 0);
  assert.equal(geo2.watches.length, 0);
});

test("ubicar: http sin localhost (Chrome responde 'Only secure origins') da insecure", async () => {
  const geo = geoFalsa();
  const s = ubicar(geo, { permiso: null, programar: () => 1, desprogramar: () => {} });
  geo.pedidos[0].error(errorNav(1, "Only secure origins are allowed"));
  await assert.rejects(s.primera, { code: "insecure" });
});

test("ubicar: si la red y el GPS fallan sin ninguna lectura, rechaza con el código que más dice", async () => {
  // computadora con la ubicación del sistema apagada: las dos responden unavailable enseguida
  const geo = geoFalsa();
  const reloj = relojFalso();
  const s = ubicar(geo, { permiso: "granted", programar: reloj.programar, desprogramar: reloj.desprogramar });
  geo.pedidos[0].error(errorNav(2));
  geo.watches[0].error(errorNav(2));
  await assert.rejects(s.primera, { code: "unavailable" });
  assert.deepEqual(geo.limpiados, [1]);

  // la rápida vence y el GPS nunca contesta: a los 22 s, timeout
  const geo2 = geoFalsa();
  const reloj2 = relojFalso();
  let fin = null;
  const s2 = ubicar(geo2, { permiso: "granted", onFin: (f) => (fin = f), programar: reloj2.programar, desprogramar: reloj2.desprogramar });
  geo2.pedidos[0].error(errorNav(3));
  reloj2.disparar();
  await assert.rejects(s2.primera, { code: "timeout" });
  assert.equal(fin.motivo, "error");

  // el GPS falla con unavailable mientras la rápida sigue pendiente: se espera a la rápida
  const geo3 = geoFalsa();
  const s3 = ubicar(geo3, { permiso: "granted", programar: () => 1, desprogramar: () => {} });
  geo3.watches[0].error(errorNav(2));
  geo3.pedidos[0].ok(posicion(600));
  assert.equal((await s3.primera).precisionM, 600);

  // el GPS falla con timeout después de que la rápida ya venció: unavailable le gana a timeout
  const geo4 = geoFalsa();
  const s4 = ubicar(geo4, { permiso: "granted", programar: () => 1, desprogramar: () => {} });
  geo4.pedidos[0].error(errorNav(2));
  geo4.watches[0].error(errorNav(3));
  await assert.rejects(s4.primera, { code: "unavailable" });
});

test("ubicar: con una lectura, al vencer los 22 s termina por tiempo y la primera ya estaba resuelta", async () => {
  const geo = geoFalsa();
  const reloj = relojFalso();
  let fin = null;
  const s = ubicar(geo, { permiso: "granted", onFin: (f) => (fin = f), programar: reloj.programar, desprogramar: reloj.desprogramar });
  geo.watches[0].ok(posicion(45));
  assert.equal((await s.primera).precisionM, 45);
  reloj.disparar();
  assert.equal(fin.motivo, "tiempo");
  assert.equal(fin.lectura.precisionM, 45);
  assert.deepEqual(geo.limpiados, [1]);
});

test("ubicar sin rápida (Mejorar precisión): parte de la lectura que había y solo avisa si mejora", async () => {
  const geo = geoFalsa();
  const desde = { lat: -7.1638, lon: -78.5003, precisionM: 40, hora: 1 };
  const mejoras = [];
  let fin = null;
  const s = ubicar(geo, { rapida: false, desde, onMejora: (l) => mejoras.push(l.precisionM), onFin: (f) => (fin = f), programar: () => 1, desprogramar: () => {} });
  assert.equal(geo.pedidos.length, 0, "sin lectura rápida");
  assert.equal(geo.watches.length, 1);
  geo.watches[0].ok(posicion(60, 2)); // peor que la que había
  assert.equal((await s.primera).precisionM, 40);
  assert.deepEqual(mejoras, []);
  geo.watches[0].ok(posicion(10, 3));
  assert.deepEqual(mejoras, [10]);
  assert.equal(fin.motivo, "precisa");
});

test("ubicar: cancelar corta el watch y el temporizador; la primera pendiente rechaza con cancelado", async () => {
  const geo = geoFalsa();
  const reloj = relojFalso();
  let fin = null;
  const s = ubicar(geo, { permiso: "granted", onFin: (f) => (fin = f), programar: reloj.programar, desprogramar: reloj.desprogramar });
  s.cancelar();
  await assert.rejects(s.primera, { code: "cancelado" });
  assert.equal(fin.motivo, "cancelado");
  assert.deepEqual(geo.limpiados, [1]);
  assert.deepEqual(reloj.borrados, [1]);
  s.cancelar(); // dos veces no pasa nada
  await tick();
});

test("ubicar sin watchPosition (navegador raro) usa una sola lectura de alta precisión", async () => {
  const geo = geoFalsa();
  delete geo.watchPosition;
  const s = ubicar(geo, { permiso: "granted", programar: () => 1, desprogramar: () => {} });
  assert.equal(geo.pedidos.length, 2);
  assert.equal(geo.pedidos[1].opciones.enableHighAccuracy, true);
  geo.pedidos[1].ok(posicion(12));
  assert.equal((await s.primera).precisionM, 12);
});

test("textos de precisión: redondeo legible, calidad y aviso", () => {
  assert.equal(textoMetrosPrecision(4.4), "4 m");
  assert.equal(textoMetrosPrecision(0.2), "1 m");
  assert.equal(textoMetrosPrecision(24.6), "25 m");
  assert.equal(textoMetrosPrecision(63), "65 m");
  assert.equal(textoMetrosPrecision(184), "180 m");
  assert.equal(textoMetrosPrecision(1540), "1,5 km");
  assert.equal(textoMetrosPrecision(12_400), "12 km");
  assert.equal(textoMetrosPrecision(null), null);
  assert.equal(textoMetrosPrecision(-3), null);
  assert.equal(calidadPrecision(25), "buena");
  assert.equal(calidadPrecision(30), "buena");
  assert.equal(calidadPrecision(90), "regular");
  assert.equal(calidadPrecision(151), "baja");
  assert.equal(calidadPrecision(null), null);
  assert.equal(textoPrecision(25), "Precisión: unos 25 m (buena)");
  assert.equal(textoPrecision(1540), "Precisión: unos 1,5 km (baja)");
  assert.equal(textoPrecision(undefined), "Precisión desconocida");
  assert.equal(avisoPrecision(25), null);
  assert.equal(avisoPrecision(120), null);
  assert.match(avisoPrecision(900), /lejos de donde estás/);
  assert.match(avisoPrecision(null), /no informó la precisión/);
});

test("textos por estado y reintento", () => {
  // desde el primer intento se avisa que puede tardar hasta medio minuto; al reintentar, que se busca de nuevo
  assert.match(textoBuscando(), /medio minuto/);
  assert.doesNotMatch(textoBuscando(), /de nuevo/);
  assert.match(textoBuscando(true), /de nuevo/);
  assert.match(textoBuscando(true), /medio minuto/);
  assert.match(textoFalloCorto("denied"), /permiso/);
  assert.match(textoFalloCorto("insecure"), /https/);
  assert.match(textoFalloCorto("timeout", "Jaén"), /Jaén/);
  assert.match(textoFalloCorto("unavailable"), /Cajamarca/);
  assert.match(textoFalloCorto("otro"), /No se pudo determinar/);
  assert.equal(sePuedeReintentar("timeout"), true);
  assert.equal(sePuedeReintentar("unavailable"), true);
  assert.equal(sePuedeReintentar("denied"), false);
  assert.equal(sePuedeReintentar("insecure"), false);
  for (const s of ["denied", "unavailable", "timeout", "insecure"]) assert.equal(esFalloGps(s), true, s);
  for (const s of ["idle", "pending", "granted", undefined]) assert.equal(esFalloGps(s), false, String(s));
});

test("textoSinGps (Tu zona ahora): qué pasó por estado y qué enlace va", () => {
  // sin https no sirve pedir de nuevo: el texto del estado, sin enlace, y que las distancias salen del centro
  const insecure = textoSinGps("insecure");
  assert.match(insecure.texto, /https/);
  assert.match(insecure.texto, /centro de la ciudad/);
  assert.equal(insecure.enlace, null);
  assert.equal(textoSinGps("denied").enlace, null);
  assert.match(textoSinGps("denied").texto, /centro de la ciudad/);
  // el GPS que tarda y el "sin señal" invitan a salir a cielo abierto y a reintentar
  assert.match(textoSinGps("timeout").texto, /tardó.*cielo abierto/);
  assert.equal(textoSinGps("timeout").enlace, "Volver a intentar");
  assert.match(textoSinGps("unavailable").texto, /centro de la ciudad.*cielo abierto/);
  assert.equal(textoSinGps("unavailable").enlace, "Volver a intentar");
  // todavía no se pidió (o se está pidiendo): invitación a activarla
  for (const s of ["idle", "pending", undefined]) {
    assert.match(textoSinGps(s).texto, /^Activa tu ubicación/);
    assert.equal(textoSinGps(s).enlace, "Usar mi ubicación");
  }
});
