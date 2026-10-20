import test from "node:test";
import assert from "node:assert/strict";
import { estadoZona } from "./zonaRio.js";
import { fechaPeru, horaPeru } from "./tiempo.js";
import {
  botonPrincipal,
  cajaTuYRio,
  chipsDistancia,
  distancias,
  gpsVisto,
  lineaFuentes,
  marcarGpsVisto,
  metrosAlCauce,
  nivelMaximo,
  puntoCercanoDelCauce,
  rioPrincipal,
  textoMetros,
  titularCorto,
} from "./zonaAhora.js";

// Cauce de prueba: una línea norte-sur por el meridiano -78.50 entre -7.20 y -7.10 (unos 11 km),
// y una zona de 4 puntos (un cuadrado de ~400 m de lado pegado al río, hacia el este).
const CAUCE = { type: "LineString", coordinates: [[-78.5, -7.2], [-78.5, -7.15], [-78.5, -7.1]] };
const ZONA = {
  rio: "mashcon",
  clave: "z1",
  geojson: { type: "Polygon", coordinates: [[[-78.5, -7.162], [-78.4964, -7.162], [-78.4964, -7.158], [-78.5, -7.158], [-78.5, -7.162]]] },
};
const RIO = { id: "mashcon", nombre: "Río Mashcón", estacion_ana: "Mashcón", rio_ana: "Mashcón", cauce: CAUCE };
const CAUDAL = { estacion: "Mashcón", rio: "Mashcón", valor: 0.13, unidad: "m³/s", umbral_alerta: 14, umbral_emergencia: 18, tendencia: "Estable" };
// Las horas de las pruebas son de HOY en Perú (02:00 y 02:03): horaPeru agrega el día cuando la
// fecha no es de hoy, y con fechas fijas las pruebas pasaban solo el día en que se escribieron.
const HOY = fechaPeru();
const AHORA = new Date(`${HOY}T02:00:00-05:00`);
const HOY_0203 = new Date(`${HOY}T02:03:00-05:00`).toISOString();
const conCaudal = (valor) => ({ rio: RIO, estado: estadoZona({ caudal: { ...CAUDAL, valor }, ahora: AHORA }) });

// panorama mínimo (usePanorama) en calma
const P_CALMA = { alertas: [], nivelLocal: "normal", etiquetaLocal: "Normal", avisosAqui: [], lluviaAqui: [], local: "En Cajamarca: su río vigilado no pasa su nivel de alerta.", actualizado: HOY_0203, desactualizado: false, avisos: [] };

test("metros al cauce: a 380 m al este del río, sobre el río, y lejos", () => {
  // 380 m al este de -78.5 a esa latitud son 0.00344 grados
  const m = metrosAlCauce(-7.16, -78.5 + 0.00344, CAUCE);
  assert.ok(Math.abs(m - 380) < 5, `${m}`);
  assert.ok(metrosAlCauce(-7.16, -78.5, CAUCE) < 1);
  // más allá del extremo sur: distancia al vértice, no a la prolongación de la recta
  const sur = metrosAlCauce(-7.21, -78.5, CAUCE);
  assert.ok(sur > 1_050 && sur < 1_150, `${sur}`);
  // a ~100 km sigue dando una distancia razonable (haversine a los vértices)
  const lejos = metrosAlCauce(-7.16, -79.4, CAUCE);
  assert.ok(lejos > 95_000 && lejos < 105_000, `${lejos}`);
  assert.equal(metrosAlCauce(-7.16, -78.5, null), null);
  assert.equal(metrosAlCauce(-7.16, -78.5, { type: "Feature", geometry: CAUCE }) < 1, true);
  assert.deepEqual(puntoCercanoDelCauce(-7.151, -78.49, CAUCE), [-7.15, -78.5]);
});

test("distancias: dentro de la zona, fuera a X m, y sin zonas del río", () => {
  const dentro = distancias([-7.16, -78.498], RIO, [ZONA]);
  assert.equal(dentro.zona.dentro, true);
  assert.equal(dentro.zona.metros, 0);
  assert.ok(dentro.metrosRio > 200 && dentro.metrosRio < 240, `${dentro.metrosRio}`);
  const fuera = distancias([-7.16, -78.494], RIO, [ZONA]);
  assert.equal(fuera.zona.dentro, false);
  assert.ok(fuera.zona.metros > 240 && fuera.zona.metros < 290, `${fuera.zona.metros}`);
  // zonas de otro río no cuentan
  assert.equal(distancias([-7.16, -78.498], RIO, [{ ...ZONA, rio: "otro" }]).zona, null);
  assert.equal(distancias(null, RIO, [ZONA]), null);
});

test("chips: metros al río, dentro/fuera de la zona en el color del nivel, y lejos", () => {
  const d = distancias([-7.16, -78.498], RIO, [ZONA]);
  const chips = chipsDistancia(d, RIO, "alerta");
  assert.equal(chips[0].texto, "A 220 m del río Mashcón");
  assert.equal(chips[1].texto, "Dentro de la zona que podría inundarse");
  assert.equal(chips[1].nivel, "alerta");
  const f = chipsDistancia(distancias([-7.16, -78.494], RIO, [ZONA]), RIO, "sin_senales");
  assert.match(f[1].texto, /^Fuera de la zona que podría inundarse \(a 2\d0 m\)$/);
  assert.equal(f[1].nivel, "normal");
  const lejos = chipsDistancia({ metrosRio: 42_000, zona: { dentro: false, metros: 41_000 } }, RIO, "sin_senales");
  assert.equal(lejos.length, 1);
  assert.equal(lejos[0].texto, "El río vigilado más cercano está a 42 km (Mashcón)");
  assert.equal(chipsDistancia(null, RIO).length, 0);
  assert.match(textoMetros(1234), /^1[,.]2 km$/); // la coma depende del ICU de Node
  assert.equal(textoMetros(15_600), "16 km");
  assert.equal(textoMetros(null), null);
});

test("nivel máximo: el río vigilado sube el semáforo aunque alerta_actual diga aviso", () => {
  assert.equal(nivelMaximo("aviso", [conCaudal(19)]), "emergencia");
  assert.equal(nivelMaximo("aviso", [conCaudal(15.4)]), "alerta");
  assert.equal(nivelMaximo("normal", [conCaudal(11.5)]), "aviso"); // atentos (80 %)
  assert.equal(nivelMaximo("normal", [conCaudal(0.13)]), "normal");
  assert.equal(nivelMaximo("sin_dato", []), "sin_dato");
  assert.equal(nivelMaximo("emergencia", [conCaudal(0.13)]), "emergencia");
});

test("río principal: el de nivel más alto; a igual nivel, el más cercano", () => {
  const lejano = { ...RIO, id: "otro", nombre: "Río Otro", cauce: { type: "LineString", coordinates: [[-78.9, -7.2], [-78.9, -7.1]] } };
  const rios = [conCaudal(0.13), { rio: lejano, estado: estadoZona({ caudal: { ...CAUDAL, valor: 15 }, ahora: AHORA }) }];
  assert.equal(rioPrincipal(rios, [-7.16, -78.5]).rio.id, "otro");
  const iguales = [{ rio: lejano, estado: estadoZona({ ahora: AHORA }) }, conCaudal(0.13)];
  assert.equal(rioPrincipal(iguales, [-7.16, -78.5]).rio.id, "mashcon");
  assert.equal(rioPrincipal(iguales, null).rio.id, "otro"); // sin origen, el primero
  assert.equal(rioPrincipal([], null), null);
});

test("titular: calma, aviso amarillo, lluvia medida, río en alerta y en emergencia", () => {
  const calma = titularCorto(P_CALMA, [conCaudal(0.13)], "Cajamarca");
  assert.equal(calma.nivel, "normal");
  assert.equal(calma.texto, "Tranquilo en Cajamarca: el río Mashcón está tranquilo y no hay avisos de SENAMHI.");
  assert.equal(calma.instruccion, null);

  const aviso = titularCorto({ ...P_CALMA, nivelLocal: "aviso", avisosAqui: [{ nivel: "aviso", detalle: "x", referencia: "r" }] }, [conCaudal(0.13)], "Cajamarca");
  assert.equal(aviso.nivel, "aviso");
  assert.equal(aviso.texto, "Hoy en Cajamarca: aviso amarillo de SENAMHI por lluvias.");

  const lluvia = titularCorto({ ...P_CALMA, nivelLocal: "aviso", lluviaAqui: [{ referencia: "a" }, { referencia: "b" }] }, [], "Cajamarca");
  assert.equal(lluvia.etiqueta, "ATENTOS");
  assert.equal(lluvia.texto, "Hoy en Cajamarca: llovió más que la referencia de SENAMHI en 2 estaciones.");

  const atentos = titularCorto(P_CALMA, [conCaudal(11.5)], "Cajamarca");
  assert.equal(atentos.nivel, "aviso");
  assert.equal(atentos.texto, "Atentos en Cajamarca: hay señales en la cuenca del río Mashcón.");

  const alerta = titularCorto({ ...P_CALMA, nivelLocal: "aviso" }, [conCaudal(15.4)], "Cajamarca");
  assert.equal(alerta.nivel, "alerta");
  assert.equal(alerta.texto, "ALERTA: el río Mashcón pasó su nivel de alerta (ANA, 02:03).");
  assert.equal(alerta.instruccion, "Aléjate de la orilla y no cruces el río.");

  const emergencia = titularCorto({ ...P_CALMA, nivelLocal: "aviso" }, [conCaudal(19)], "Cajamarca");
  assert.equal(emergencia.nivel, "emergencia");
  assert.equal(emergencia.etiqueta, "EMERGENCIA");
  assert.equal(emergencia.texto, "EMERGENCIA: el río Mashcón pasó su nivel de emergencia (ANA, 02:03).");
  assert.match(emergencia.instruccion, /Defensa Civil/);

  // aviso hidrológico rojo de SENAMHI
  const h = { numero: 1, sentido: "crecida", nivel: 4, fin: new Date(AHORA.getTime() + 21 * 3_600_000).toISOString() };
  const hidro = titularCorto(P_CALMA, [{ rio: RIO, estado: estadoZona({ caudal: CAUDAL, senal: { avisos_hidro: [h] }, ahora: AHORA }) }], "Cajamarca");
  assert.equal(hidro.nivel, "emergencia");
  assert.equal(hidro.texto, "EMERGENCIA: aviso hidrológico rojo de SENAMHI para el río Mashcón.");
});

test("titular: aviso naranja de SENAMHI y río de ANA sin mapa de zonas", () => {
  const naranja = titularCorto({ ...P_CALMA, nivelLocal: "alerta", avisosAqui: [{ nivel: "alerta", detalle: "x", referencia: "r" }] }, [], "Piura");
  assert.equal(naranja.texto, "ALERTA en Piura: aviso naranja de SENAMHI por lluvias.");
  assert.match(naranja.instruccion, /quebradas/);
  // el aviso que explica el nivel no es el primero de la lista (Piura: amarillo 421 y naranja 426)
  const amarilloPrimero = titularCorto(
    { ...P_CALMA, nivelLocal: "alerta", riosAqui: [], avisosAqui: [{ nivel: "aviso", detalle: "a", referencia: "SENAMHI aviso 421" }, { nivel: "alerta", detalle: "n", referencia: "SENAMHI aviso 426" }] },
    [],
    "Piura"
  );
  assert.equal(amarilloPrimero.texto, "ALERTA en Piura: aviso naranja de SENAMHI por lluvias.");
  assert.equal(amarilloPrimero.origen, "aviso");
  assert.match(amarilloPrimero.instruccion, /quebradas/);
  assert.doesNotMatch(amarilloPrimero.texto, /río/);
  // un río de ANA (fila tipo caudal) que pasó su nivel: ahí sí "un río pasó su nivel"
  const rioAna = titularCorto({ ...P_CALMA, nivelLocal: "emergencia", etiquetaLocal: "Emergencia", riosAqui: [{ nivel: "emergencia", referencia: "Nauta (Marañón)" }] }, [], "Loreto");
  assert.equal(rioAna.texto, "EMERGENCIA en Loreto: un río pasó su nivel de emergencia (ANA).");
  assert.match(rioAna.instruccion, /Defensa Civil/);
  const dosRios = titularCorto({ ...P_CALMA, nivelLocal: "alerta", riosAqui: [{ nivel: "alerta", referencia: "a" }, { nivel: "alerta", referencia: "b" }] }, [], "Tumbes");
  assert.equal(dosRios.texto, "ALERTA en Tumbes: 2 ríos pasaron su nivel de alerta (ANA).");
  // el río pesa más que el aviso del mismo nivel
  const ambos = titularCorto({ ...P_CALMA, nivelLocal: "alerta", riosAqui: [{ nivel: "alerta", referencia: "a" }], avisosAqui: [{ nivel: "alerta", referencia: "r" }] }, [], "Tumbes");
  assert.equal(ambos.origen, "rio");
  // sin filas por tipo (panorama viejo) se mantiene la lectura de antes
  assert.equal(titularCorto({ ...P_CALMA, nivelLocal: "emergencia" }, [], "Loreto").origen, "rio");
  // con filas por tipo pero sin río ni aviso que lo explique no se inventa un río
  const otra = titularCorto({ ...P_CALMA, nivelLocal: "alerta", riosAqui: [], avisosAqui: [{ nivel: "aviso", referencia: "r" }] }, [], "Piura");
  assert.doesNotMatch(otra.texto, /río pasó/);
  assert.equal(otra.nivel, "alerta");
});

test("titular: ríos muy bajos (vaciante) nunca son una crecida", () => {
  // Loreto hoy: 5 filas nivel_bajo (lib/nivel.js las deja en "aviso") y sin aviso de SENAMHI
  const bajos = titularCorto({ ...P_CALMA, nivelLocal: "aviso", etiquetaLocal: "Ríos muy bajos", bajosAqui: 5, riosAqui: [] }, [], "Loreto");
  assert.equal(bajos.nivel, "aviso");
  assert.equal(bajos.etiqueta, "RÍOS MUY BAJOS");
  assert.equal(bajos.texto, "En Loreto: 5 ríos están muy bajos según ANA (vaciante).");
  assert.equal(bajos.origen, "bajo");
  assert.equal(bajos.instruccion, null);
  assert.doesNotMatch(bajos.texto, /pasó su nivel|orilla/);
  assert.deepEqual(botonPrincipal(bajos.nivel, { hayRios: false }), { texto: "Ver avisos del mapa", accion: "avisos" });
  const uno = titularCorto({ ...P_CALMA, nivelLocal: "aviso", bajosAqui: 1, riosAqui: [] }, [], "Ucayali");
  assert.equal(uno.etiqueta, "RÍO MUY BAJO");
  assert.equal(uno.texto, "En Ucayali: un río está muy bajo según ANA (vaciante).");
  // con un aviso amarillo además, manda el aviso
  const conAviso = titularCorto({ ...P_CALMA, nivelLocal: "aviso", bajosAqui: 5, avisosAqui: [{ nivel: "aviso", referencia: "SENAMHI lluvia 24h" }] }, [], "Loreto");
  assert.equal(conAviso.texto, "Hoy en Loreto: aviso amarillo de SENAMHI por lluvias.");
});

test("titular: degradaciones (sin datos, error, fuente caída, sin cobertura)", () => {
  const sin = titularCorto({ alertas: null, nivelLocal: "sin_dato", local: "Consultando las alertas…" }, [], "Cajamarca");
  assert.equal(sin.nivel, "sin_dato");
  assert.equal(sin.etiqueta, "SIN DATOS");
  assert.equal(sin.texto, "Consultando las alertas…");
  const error = titularCorto({ alertas: null, nivelLocal: "sin_dato", local: "No se pudo consultar las alertas. Revisa tu conexión." }, [], "Cajamarca");
  assert.equal(error.origen, "error");
  // la emergencia del río se dispara aunque alerta_actual no haya cargado
  const soloRio = titularCorto({ alertas: null, nivelLocal: "sin_dato" }, [conCaudal(19)], "Cajamarca");
  assert.equal(soloRio.nivel, "emergencia");
  // fuente caída: lo dice y mantiene el nivel
  const caida = titularCorto({ ...P_CALMA, desactualizado: true, avisos: ["ANA no respondió en la última actualización: los ríos pueden estar atrasados."] }, [conCaudal(19)], "Cajamarca");
  assert.match(caida.texto, /Último dato de ANA a las 02:03; puede haber cambiado\.$/);
  const viejo = titularCorto({ ...P_CALMA, desactualizado: true }, [conCaudal(0.13)], "Cajamarca");
  assert.match(viejo.texto, /Puede haber cambiado\.$/);
  // sin cobertura: nunca verde
  const nada = titularCorto({ ...P_CALMA, nivelLocal: "sin_dato" }, [], "Madre de Dios");
  assert.equal(nada.nivel, "sin_dato");
  assert.match(nada.texto, /todavía no vigila/);
  // calma sin río vigilado
  assert.equal(titularCorto(P_CALMA, [], "Lima").texto, "Tranquilo en Lima: no hay alertas de ríos ni avisos de SENAMHI.");
});

test("botón por nivel y línea de fuentes", () => {
  assert.deepEqual(botonPrincipal("normal"), { texto: "Ver mi zona en el mapa", accion: "zona" });
  assert.deepEqual(botonPrincipal("aviso"), { texto: "Ver qué puede pasar", accion: "pasar" });
  assert.deepEqual(botonPrincipal("emergencia"), { texto: "A dónde acudir", accion: "acudir" });
  assert.deepEqual(botonPrincipal("alerta", { hayAcudir: false }), { texto: "Ver la zona en el mapa", accion: "pasar" });
  assert.deepEqual(botonPrincipal("aviso", { hayRios: false }), { texto: "Ver avisos del mapa", accion: "avisos" });
  const l = lineaFuentes({ porGps: true, actualizado: HOY_0203, desactualizado: true, lluviaActualizada: AHORA.toISOString() });
  assert.equal(l[0].texto, "Tu ubicación (GPS)");
  assert.equal(l[1].texto, "ríos ANA sin actualizar desde 02:03");
  assert.equal(l[1].mal, true);
  assert.equal(l[2].texto, "lluvia SENAMHI 02:00");
  assert.equal(lineaFuentes({ porGps: false, ciudad: "Cajamarca" })[0].texto, "Desde el centro de Cajamarca");
  // de otro día, la hora lleva el día ("14 oct 02:03"), en la línea de fuentes y en el titular
  const otroDia = "2026-10-14T07:03:00Z";
  assert.equal(horaPeru(otroDia), "14 oct 02:03");
  assert.equal(lineaFuentes({ porGps: true, actualizado: otroDia, desactualizado: true })[1].texto, "ríos ANA sin actualizar desde 14 oct 02:03");
  const viejo = titularCorto({ ...P_CALMA, actualizado: otroDia }, [conCaudal(15.4)], "Cajamarca");
  assert.equal(viejo.texto, "ALERTA: el río Mashcón pasó su nivel de alerta (ANA, 14 oct 02:03).");
});

test("la pantalla del GPS se recuerda y nunca rompe sin almacenamiento", () => {
  const memoria = new Map();
  const almacen = { getItem: (k) => memoria.get(k) ?? null, setItem: (k, v) => memoria.set(k, v) };
  assert.equal(gpsVisto(almacen), false);
  marcarGpsVisto(almacen);
  assert.equal(gpsVisto(almacen), true);
  const roto = { getItem: () => { throw new Error("bloqueado"); }, setItem: () => { throw new Error("bloqueado"); } };
  assert.equal(gpsVisto(roto), false);
  assert.doesNotThrow(() => marcarGpsVisto(roto));
  assert.equal(gpsVisto(null), false);
});

test("caja para encuadrar a la persona y el tramo más cercano del río", () => {
  // 380 m al este del cauce: la caja cubre a los dos con margen y no es más chica que ~600 m
  const caja = cajaTuYRio([-7.16, -78.5 + 0.00344], CAUCE);
  assert.ok(caja[0][1] < -78.5 && caja[1][1] > -78.5 + 0.00344, JSON.stringify(caja));
  assert.ok(caja[1][0] - caja[0][0] >= 0.0027 - 1e-9);
  assert.ok(caja[1][1] - caja[0][1] >= 0.0027 - 1e-9);
  // sobre el río: igual hay caja mínima
  const sobre = cajaTuYRio([-7.15, -78.5], CAUCE);
  assert.ok(sobre[1][0] - sobre[0][0] >= 0.0027 - 1e-9);
  assert.equal(cajaTuYRio(null, CAUCE), null);
  assert.equal(cajaTuYRio([-7.15, -78.5], null), null);
  // el chip del río trae los metros aparte para contar el número
  const chips = chipsDistancia(distancias([-7.16, -78.498], RIO, [ZONA]), RIO, "sin_senales");
  assert.ok(chips[0].metros > 200 && chips[0].metros < 240);
  assert.equal(chips[0].antes, "A ");
  assert.equal(chips[0].despues, " del río Mashcón");
});
