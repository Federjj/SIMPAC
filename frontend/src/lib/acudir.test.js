import test from "node:test";
import assert from "node:assert/strict";
import {
  cajaAlrededor,
  cajaRedondeada,
  conDistancia,
  enlacesComoLlegar,
  esHospital,
  masCercanos,
  mejorSalud,
  notaFuente,
  telefonos,
  textoDistancia,
  tituloTipo,
} from "./acudir.js";

// Centro de Cajamarca (Plaza de Armas) y puntos reales de la tabla punto_acudir (14-10-2026).
const CENTRO = { lat: -7.1617, lon: -78.5127 };
const HOSPITAL = { clave: "renipress:00007686", tipo: "salud", nombre: "Hospital Regional Docente Cajamarca", categoria: "Hospital II-2", atiende_24h: true, lat: -7.183407, lon: -78.487692 };
const ESSALUD = { clave: "renipress:00010272", tipo: "salud", nombre: "Hospital II Cajamarca", categoria: "Hospital II-2", atiende_24h: true, lat: -7.15988333, lon: -78.50902167 };
const CLINICA = { clave: "renipress:00009591", tipo: "salud", nombre: "Clínica Limatambo", categoria: "Clínica II-1", atiende_24h: true, lat: -7.15157, lon: -78.523573 };
const PUESTO = { clave: "renipress:p1", tipo: "salud", nombre: "Puesto cercano", categoria: "Puesto de salud I-1", atiende_24h: null, lat: -7.1612, lon: -78.5122 };
const COMISARIA = { clave: "comisarias:5000", tipo: "comisaria", nombre: "Comisaría Central Cajamarca", categoria: "Comisaría tipo A", atiende_24h: null, lat: -7.160195, lon: -78.512912 };
const COMISARIA2 = { clave: "comisarias:5006", tipo: "comisaria", nombre: "Comisaría San José", categoria: "Comisaría tipo B", lat: -7.15011, lon: -78.519764 };
const BOMBEROS = { clave: "bomberos:59", tipo: "bomberos", nombre: "Compañía de Bomberos Cajamarca Nº 59", categoria: "Compañía de bomberos", lat: -7.164544, lon: -78.509765 };
const INDECI = { clave: "manual:indeci_cajamarca", tipo: "otro", nombre: "INDECI Cajamarca", lat: -7.15886, lon: -78.508295 };
const TODOS = [HOSPITAL, PUESTO, COMISARIA2, BOMBEROS, COMISARIA, INDECI, CLINICA, ESSALUD];

test("conDistancia: la Comisaría Central queda a unos 168 m del centro y la lista va del más cercano al más lejano", () => {
  const l = conDistancia(TODOS, CENTRO.lat, CENTRO.lon);
  const c = l.find((p) => p.clave === "comisarias:5000");
  assert.ok(Math.abs(c.distancia_m - 168) <= 5, `distancia ${c.distancia_m}`);
  for (let i = 1; i < l.length; i++) assert.ok(l[i - 1].distancia_m <= l[i].distancia_m);
  // el hospital regional está a unos 3,7 km (sureste)
  const h = l.find((p) => p.clave === "renipress:00007686");
  assert.ok(h.distancia_m > 3500 && h.distancia_m < 3900, `hospital ${h.distancia_m}`);
});

test("masCercanos por tipo: uno de cada tipo, en el orden salud, comisaría, bomberos, y máximo 3", () => {
  const r = masCercanos(TODOS, CENTRO.lat, CENTRO.lon);
  assert.equal(r.length, 3);
  assert.deepEqual(
    r.map((p) => p.tipo),
    ["salud", "comisaria", "bomberos"]
  );
  assert.equal(r[1].clave, "comisarias:5000"); // la más cercana de las dos comisarías
  assert.equal(r[2].clave, "bomberos:59");
  assert.ok(r.every((p) => Number.isInteger(p.distancia_m)));
});

test("masCercanos: con maximo 4 entra también Defensa Civil; sin porTipo son los más cercanos sin importar el tipo", () => {
  const r = masCercanos(TODOS, CENTRO.lat, CENTRO.lon, { maximo: 4 });
  assert.equal(r.length, 4);
  assert.equal(r[3].tipo, "otro");
  const sinTipo = masCercanos(TODOS, CENTRO.lat, CENTRO.lon, { porTipo: false, maximo: 2 });
  assert.deepEqual(
    sinTipo.map((p) => p.clave),
    ["renipress:p1", "comisarias:5000"]
  );
});

test("masCercanos: maxKm descarta lo lejano; sin puntos devuelve una lista vacía", () => {
  assert.deepEqual(masCercanos([], CENTRO.lat, CENTRO.lon), []);
  const r = masCercanos([HOSPITAL, COMISARIA], CENTRO.lat, CENTRO.lon, { maxKm: 1 });
  assert.deepEqual(
    r.map((p) => p.clave),
    ["comisarias:5000"]
  );
});

test("salud: el hospital 24 h a menos de 15 km gana al puesto de salud de la esquina; sin hospital cerca, el más cercano", () => {
  const r = masCercanos(TODOS, CENTRO.lat, CENTRO.lon);
  assert.equal(r[0].clave, "renipress:00010272"); // EsSalud: hospital 24 h más cercano (no la clínica ni el puesto)
  // sin hospitales: el más cercano aunque sea un puesto
  const lejos = conDistancia([PUESTO, CLINICA], CENTRO.lat, CENTRO.lon);
  assert.equal(mejorSalud(lejos).clave, "renipress:p1");
  // un hospital a más de 15 km no gana
  const hospitalLejos = { ...HOSPITAL, distancia_m: 16_000 };
  assert.equal(mejorSalud([{ ...PUESTO, distancia_m: 60 }, hospitalLejos]).clave, "renipress:p1");
  assert.equal(mejorSalud([]), null);
  assert.equal(esHospital(HOSPITAL), true);
  assert.equal(esHospital(CLINICA), false);
  assert.equal(esHospital({ categoria: "Instituto especializado III-2" }), true);
});

test("textoDistancia: metros redondeados a 10, km con un decimal hasta 10 km, enteros después", () => {
  assert.equal(textoDistancia(168), "a 170 m");
  assert.equal(textoDistancia(3), "a 10 m");
  assert.equal(textoDistancia(850), "a 850 m");
  assert.equal(textoDistancia(999), "a 1000 m");
  assert.equal(textoDistancia(2300), "a 2,3 km");
  assert.equal(textoDistancia(1000), "a 1,0 km");
  assert.equal(textoDistancia(23_400), "a 23 km");
  assert.equal(textoDistancia(null), null);
  assert.equal(textoDistancia(NaN), null);
});

test("cajas: redondeo hacia afuera a décimas y caja de 30 km alrededor de un punto", () => {
  assert.deepEqual(cajaRedondeada({ oeste: -78.53, sur: -7.19, este: -78.48, norte: -7.12 }), { oeste: -78.6, sur: -7.2, este: -78.4, norte: -7.1 });
  const c = cajaAlrededor(CENTRO.lat, CENTRO.lon, 30);
  assert.ok(c.sur <= -7.1617 - 0.26 && c.norte >= -7.1617 + 0.26);
  assert.ok(c.oeste <= -78.5127 - 0.27 && c.este >= -78.5127 + 0.27);
  // la misma clave de caché al moverse menos de una décima
  assert.deepEqual(cajaAlrededor(-7.165, -78.515, 30), cajaAlrededor(-7.168, -78.518, 30));
});

test("teléfonos, enlaces y textos de la fuente", () => {
  assert.deepEqual(telefonos("076599040 / 076599030"), ["076599040", "076599030"]);
  assert.deepEqual(telefonos("076-363333"), ["076-363333"]);
  assert.deepEqual(telefonos(null), []);
  assert.deepEqual(telefonos("sin número"), []);
  const e = enlacesComoLlegar(-7.183407, -78.487692);
  assert.equal(e.maps, "https://www.google.com/maps/dir/?api=1&destination=-7.183407,-78.487692");
  assert.equal(e.geo, "geo:-7.183407,-78.487692?q=-7.183407,-78.487692");
  assert.match(notaFuente({ tipo: "comisaria" }), /2019/);
  assert.match(notaFuente({ tipo: "salud", actualizado: "2026-09-30" }), /RENIPRESS \(30-09-2026\)/);
  assert.equal(tituloTipo(HOSPITAL), "Hospital");
  assert.equal(tituloTipo(CLINICA), "Clínica");
  assert.equal(tituloTipo(PUESTO), "Centro de salud");
  assert.equal(tituloTipo(BOMBEROS), "Bomberos");
});
