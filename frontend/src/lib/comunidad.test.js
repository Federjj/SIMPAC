import test from "node:test";
import assert from "node:assert/strict";
import {
  ewkt,
  groserias,
  hace,
  mensajeAuth,
  mensajeErrorBD,
  mensajesVisibles,
  nombreReporte,
  ordenarReportes,
  puntoDeWkb,
  textoDistancia,
  validarCuenta,
  validarReporte,
  validarTexto,
  venceEn,
} from "./comunidad.js";

const AHORA = Date.parse("2026-10-14T15:00:00-05:00");
const iso = (min) => new Date(AHORA + min * 60_000).toISOString();

test("ordenar reportes: más confianza primero; a igual confianza, el más cercano", () => {
  const cajamarca = { lat: -7.1617, lon: -78.5127 };
  const reportes = [
    { id: "lejos", confianza: 0.9, lat: -12.0464, lon: -77.0428, creado_en: iso(-10) }, // Lima, 570 km
    { id: "cerca_malo", confianza: 0.2, lat: -7.165, lon: -78.515, creado_en: iso(-5) },
    { id: "cerca_bueno", confianza: 0.8, lat: -7.17, lon: -78.52, creado_en: iso(-30) },
    { id: "cerca_bueno_nuevo", confianza: 0.8, lat: -7.17, lon: -78.52, creado_en: iso(-1) },
  ];
  const ids = ordenarReportes(reportes, cajamarca).map((r) => r.id);
  assert.deepEqual(ids, ["cerca_bueno_nuevo", "cerca_bueno", "cerca_malo", "lejos"]);
  // la distancia sale calculada (Lima a Cajamarca, unos 570 km)
  const lima = ordenarReportes(reportes, cajamarca).find((r) => r.id === "lejos");
  assert.ok(lima.distanciaKm > 500 && lima.distanciaKm < 650, `${lima.distanciaKm}`);
  // sin posición: solo la confianza y, en empate, el más nuevo
  assert.deepEqual(ordenarReportes(reportes, null).map((r) => r.id), ["lejos", "cerca_bueno_nuevo", "cerca_bueno", "cerca_malo"]);
  assert.equal(ordenarReportes(reportes, null)[0].distanciaKm, null);
});

test("texto de distancia", () => {
  assert.equal(textoDistancia(0.35), "a 350 m");
  assert.equal(textoDistancia(0.004), "a 10 m");
  assert.equal(textoDistancia(1.23), `a ${(1.2).toLocaleString("es-PE")} km`); // es-PE usa punto decimal
  assert.equal(textoDistancia(15.4), "a 15 km");
  assert.equal(textoDistancia(null), null);
});

test("hace X y vence en X", () => {
  assert.equal(hace(iso(-8), AHORA), "hace 8 min");
  assert.equal(hace(iso(-135), AHORA), "hace 2 h 15 min");
  assert.equal(hace("nada", AHORA), "");
  assert.equal(venceEn(iso(45), AHORA), "vence en 45 min");
  assert.equal(venceEn(iso(80), AHORA), "vence en 1 h 20 min");
  assert.equal(venceEn(iso(120), AHORA), "vence en 2 h");
  assert.equal(venceEn(iso(-1), AHORA), "vencido");
  assert.equal(venceEn(iso(3 * 24 * 60), AHORA), "vence en 3 días");
});

test("validar el formulario del reporte", () => {
  const pos = [-7.16, -78.51];
  assert.equal(validarReporte({ tipo: "inundacion", pos }).ok, true);
  assert.equal(validarReporte({ tipo: "atasco", pos }).errores.subtipo, "Indica qué tan fuerte es el atasco.");
  assert.equal(validarReporte({ tipo: "atasco", subtipo: "leve", pos }).ok, true);
  assert.ok(validarReporte({ tipo: "bache", subtipo: "leve", pos }).errores.subtipo);
  assert.ok(validarReporte({ pos }).errores.tipo);
  assert.ok(validarReporte({ tipo: "otro", pos: null }).errores.pos.includes("ubicación"));
  assert.ok(validarReporte({ tipo: "otro", pos: [40.4, -3.7] }).errores.pos.includes("fuera del Perú"));
  assert.ok(validarReporte({ tipo: "otro", pos, descripcion: "x".repeat(501) }).errores.descripcion.includes("501"));
  assert.ok(validarReporte({ tipo: "otro", pos, foto: { size: 4e6, type: "image/jpeg" } }).errores.foto.includes("3 MB"));
  assert.ok(validarReporte({ tipo: "otro", pos, foto: { size: 1e5, type: "image/gif" } }).errores.foto.includes("JPG"));
  assert.equal(ewkt(-7.16, -78.51), "SRID=4326;POINT(-78.51 -7.16)");
  assert.equal(nombreReporte({ tipo: "atasco", subtipo: "detenido" }), "Atasco detenido");
  assert.equal(nombreReporte({ tipo: "inundacion" }), "Inundación");
});

test("punto desde el EWKB hex del Data API", () => {
  // POINT(-78.5127 -7.1617) con SRID 4326, little endian (lo que devuelve PostgREST)
  const p = puntoDeWkb("0101000020E6100000302AA913D0A053C0840D4FAF94A51CC0");
  assert.ok(Math.abs(p.lon - -78.5127) < 1e-4 && Math.abs(p.lat - -7.1617) < 1e-4, JSON.stringify(p));
  assert.equal(puntoDeWkb("zz"), null);
  assert.equal(puntoDeWkb(null), null);
});

test("groserías y textos del chat", () => {
  assert.deepEqual(groserias("Qué MIERDA de pista, carajo"), ["mierda", "carajo"]);
  assert.deepEqual(groserias("Se desbordó la acequia en Baños del Inca"), []);
  assert.equal(validarTexto("   ").ok, false);
  assert.equal(validarTexto(" hola ").texto, "hola");
  assert.equal(validarTexto("a".repeat(501)).ok, false);
  const msgs = [
    { id: "a", creado_en: iso(-30), expira_en: iso(90) },
    { id: "b", creado_en: iso(-200), expira_en: iso(-80) }, // vencido
    { id: "c", creado_en: iso(-60), expira_en: iso(60) },
  ];
  assert.deepEqual(mensajesVisibles(msgs, new Set(), AHORA).map((m) => m.id), ["c", "a"]);
  assert.deepEqual(mensajesVisibles(msgs, new Set(["c"]), AHORA).map((m) => m.id), ["a"]);
});

test("errores de la BD y de Auth en lenguaje claro", () => {
  assert.ok(mensajeErrorBD({ message: "límite de 5 por hora alcanzado" }, "reportar").includes("límite de 5 por hora"));
  assert.equal(mensajeErrorBD({ message: "no se puede votar el propio reporte" }), "No puedes votar tu propio reporte.");
  assert.ok(mensajeErrorBD({ code: "23514", message: 'new row violates check constraint "report_geom_check"' }).includes("fuera del Perú"));
  assert.ok(mensajeErrorBD({ message: "JWT expired", code: "PGRST301" }).includes("sesión venció"));
  assert.ok(mensajeErrorBD({ code: "42501", message: "new row violates row-level security policy" }).includes("permiso"));
  assert.ok(mensajeErrorBD({ message: "TypeError: Failed to fetch" }).includes("conexión"));
  assert.equal(mensajeErrorBD(null, "votar"), "No se pudo votar. Inténtalo de nuevo en un momento.");
  assert.equal(mensajeAuth({ code: "invalid_credentials", message: "Invalid login credentials" }), "Correo o contraseña incorrectos.");
  assert.ok(mensajeAuth({ code: "email_not_confirmed", message: "Email not confirmed" }).includes("no está confirmado"));
  assert.ok(mensajeAuth({ code: "user_already_exists", message: "User already registered" }).includes("Ya hay una cuenta"));
  assert.ok(mensajeAuth({ message: "Password should be at least 6 characters" }).includes("6 caracteres"));
  assert.equal(validarCuenta({ email: "nadie@example.com", password: "123456" }).ok, true);
  assert.ok(validarCuenta({ email: "nadie", password: "123" }).errores.email);
  assert.ok(validarCuenta({ email: "nadie@example.com", password: "123456", conNombre: true, nombre: " " }).errores.nombre);
});
