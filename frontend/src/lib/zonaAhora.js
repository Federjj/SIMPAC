// "Tu zona ahora": lo que la tarjeta de inicio dice en 5 segundos. Módulo puro (sin React ni
// Leaflet; lo prueba node --test): el nivel máximo de la zona contando los ríos vigilados, el
// titular corto en lenguaje claro, la instrucción única en alerta o emergencia, la distancia de la
// persona al cauce y a la zona que podría inundarse, y los textos de los chips y del botón.
//
// Entradas: `p` es lo que devuelve hooks/usePanorama.js (frasesEstado de lib/nivel.js más
// avisos, horas y banderas) y `rios` lo que devuelve hooks/useRiosVigilados.js: [{ rio, estado }]
// con estado = estadoZona de lib/zonaRio.js (nivel sin_senales|atentos|alerta|emergencia).
// Las frases de SENAMHI por nivel de aviso viven en lib/lenguaje.js (ACCION_AVISO).
import { ACCION_AVISO, FRASES_RIO_PAIS } from "./lenguaje.js";
import { distanciaAZona, fraseCorta, metrosEntre } from "./zonaRio.js";
import { GEOMETRIAS, avisosDe, emparejarCauces, estadoRio, partesDe } from "./cauces.js";
import { dentroDe } from "./geo.js";
import { horaPeru } from "./tiempo.js";

// qué hacer cuando un río de ANA (sin mapa de zonas) está en alerta o emergencia: las mismas
// frases que lib/zonaRio.js ACCION y lib/lenguaje.js textoRio
const ACCION_RIO = {
  alerta: "Aléjate de la orilla y no cruces el río.",
  emergencia: "Aléjate de la orilla, no cruces el río y sigue las indicaciones de Defensa Civil.",
};

// Semáforo de la tarjeta: los mismos niveles que lib/nivel.js, ordenados.
export const ORDEN_NIVEL = ["sin_dato", "normal", "aviso", "alerta", "emergencia"];
// nivel de la zona de un río (lib/zonaRio.js) -> nivel del semáforo
const DE_ZONA = { sin_senales: "normal", atentos: "aviso", alerta: "alerta", emergencia: "emergencia" };
export const ETIQUETA_NIVEL = { sin_dato: "SIN DATOS", normal: "NORMAL", aviso: "AVISO", alerta: "ALERTA", emergencia: "EMERGENCIA" };

// Colores por nivel: relleno (franja, disco, botón), tinta (texto sobre fondo claro, contraste
// >= 4,5:1) y el texto que va sobre el relleno. Los rellenos son los NIVEL_HEX de map/palette.js.
export const TONOS = {
  normal: { relleno: "#3BEB40", tinta: "#15803D", sobre: "#1F2937" },
  aviso: { relleno: "#EAB308", tinta: "#A16207", sobre: "#1F2937" },
  alerta: { relleno: "#F58E27", tinta: "#C2410C", sobre: "#FFFFFF" },
  emergencia: { relleno: "#DB0404", tinta: "#B91C1C", sobre: "#FFFFFF" },
  sin_dato: { relleno: "#9CA3AF", tinta: "#6B7280", sobre: "#FFFFFF" },
};

export const TELEFONOS = [
  { numero: "105", quien: "Policía" },
  { numero: "116", quien: "Bomberos" },
];
export const PIE_OFICIAL =
  "Información referencial; no reemplaza los canales oficiales (105 / 116). El aviso oficial llega por SISMATE, INDECI y Defensa Civil.";

const mayor = (a, b) => (ORDEN_NIVEL.indexOf(a) >= ORDEN_NIVEL.indexOf(b) ? a : b);
export const esFuerte = (nivel) => nivel === "alerta" || nivel === "emergencia";

// "Río Mashcón" -> "río Mashcón" (para meterlo en una frase)
export const nombreRio = (rio) => String(rio?.nombre ?? "el río").replace(/^R[ií]o\b/, "río");

// Nivel más alto entre el de alerta_actual (p.nivelLocal) y el de las zonas de los ríos vigilados
// (que no suman al contador: un aviso hidrológico naranja o rojo solo se ve aquí).
export function nivelMaximo(nivelLocal = "sin_dato", rios = []) {
  return (rios ?? []).reduce((n, r) => mayor(n, DE_ZONA[r?.estado?.nivel] ?? "normal"), nivelLocal ?? "sin_dato");
}

// El río que manda en la tarjeta: el de nivel más alto; a igual nivel, el más cercano a `origen`
// ([lat, lon]) o el primero (el Mashcón va primero en rio_vigilado_mapa).
export function rioPrincipal(rios = [], origen = null) {
  let mejor = null;
  for (const r of rios ?? []) {
    if (!r?.rio) continue;
    const metros = origen && r.rio.cauce ? metrosAlCauce(origen[0], origen[1], r.rio.cauce) : null;
    const cand = { ...r, metros };
    if (!mejor) {
      mejor = cand;
      continue;
    }
    const a = ORDEN_NIVEL.indexOf(DE_ZONA[cand.estado?.nivel] ?? "normal");
    const b = ORDEN_NIVEL.indexOf(DE_ZONA[mejor.estado?.nivel] ?? "normal");
    if (a > b || (a === b && metros != null && (mejor.metros == null || metros < mejor.metros))) mejor = cand;
  }
  return mejor;
}

// ---------------------------------------------------------------------------
// Distancias
// ---------------------------------------------------------------------------

// Metros de un punto al tramo más cercano de una línea GeoJSON (LineString, MultiLineString o un
// Feature/FeatureCollection con ellas): proyección plana local, alcanza para unos pocos km; con
// el punto a más de ~50 km se mide a los vértices (la proyección se deforma, pero ya es "lejos").
export function metrosAlCauce(lat, lon, geojson) {
  const lineas = [];
  const juntar = (g) => {
    if (!g) return;
    if (g.type === "FeatureCollection") g.features?.forEach((f) => juntar(f.geometry));
    else if (g.type === "Feature") juntar(g.geometry);
    else if (g.type === "GeometryCollection") g.geometries?.forEach(juntar);
    else if (g.type === "LineString") lineas.push(g.coordinates);
    else if (g.type === "MultiLineString") g.coordinates.forEach((l) => lineas.push(l));
    else if (g.type === "Polygon") g.coordinates.forEach((l) => lineas.push(l));
    else if (g.type === "MultiPolygon") g.coordinates.forEach((p) => p.forEach((l) => lineas.push(l)));
  };
  juntar(geojson);
  if (!lineas.length) return null;
  const kx = 111_320 * Math.cos((lat * Math.PI) / 180);
  const ky = 110_574;
  let min = Infinity;
  for (const linea of lineas) {
    for (let i = 0; i < linea.length; i++) {
      const [x2, y2] = [(linea[i][0] - lon) * kx, (linea[i][1] - lat) * ky];
      if (i === 0) {
        min = Math.min(min, Math.hypot(x2, y2));
        continue;
      }
      const [x1, y1] = [(linea[i - 1][0] - lon) * kx, (linea[i - 1][1] - lat) * ky];
      const dx = x2 - x1;
      const dy = y2 - y1;
      const t = dx || dy ? Math.max(0, Math.min(1, -(x1 * dx + y1 * dy) / (dx * dx + dy * dy))) : 0;
      min = Math.min(min, Math.hypot(x1 + t * dx, y1 + t * dy));
    }
  }
  if (min > 50_000) {
    // lejos: la proyección plana ya no vale; haversine a los vértices
    min = Infinity;
    for (const linea of lineas) for (const [x, y] of linea) min = Math.min(min, metrosEntre(lat, lon, y, x));
  }
  return Number.isFinite(min) ? min : null;
}

// El punto del cauce más cercano a (lat, lon) como [lat, lon] (para encuadrar "tú y el río").
export function puntoCercanoDelCauce(lat, lon, geojson) {
  const pts = [];
  const juntar = (c) => (typeof c?.[0] === "number" ? pts.push(c) : c?.forEach?.(juntar));
  const g = geojson?.type === "Feature" ? geojson.geometry : geojson;
  juntar(g?.coordinates);
  let mejor = null;
  let min = Infinity;
  for (const [x, y] of pts) {
    const d = metrosEntre(lat, lon, y, x);
    if (d < min) {
      min = d;
      mejor = [y, x];
    }
  }
  return mejor;
}

// Dónde queda la persona respecto del río vigilado y de sus zonas (rio_zona_mapa filtradas por
// z.rio === rio.id). Devuelve null sin origen o sin río.
//   { metrosRio, zona: { dentro, metros, cual } | null (sin zonas cargadas para el río) }
export function distancias(origen, rio, zonas = []) {
  if (!origen || !rio) return null;
  const [lat, lon] = origen;
  const metrosRio = rio.cauce ? metrosAlCauce(lat, lon, rio.cauce) : null;
  const propias = (zonas ?? []).filter((z) => z.rio === rio.id && z.geojson);
  if (!propias.length) return { metrosRio, zona: null };
  let dentro = null;
  let min = Infinity;
  let cual = null;
  for (const z of propias) {
    if (dentroDe(lon, lat, z.geojson)) {
      dentro = z;
      break;
    }
    const d = distanciaAZona(lat, lon, z.geojson);
    if (d != null && d < min) {
      min = d;
      cual = z;
    }
  }
  return { metrosRio, zona: dentro ? { dentro: true, metros: 0, cual: dentro } : { dentro: false, metros: Number.isFinite(min) ? min : null, cual } };
}

// "380 m" / "1,2 km" / "42 km"
export function textoMetros(m) {
  if (m == null || !Number.isFinite(m)) return null;
  if (m < 1000) return `${Math.max(0, Math.round(m / 10) * 10)} m`;
  const km = m / 1000;
  return `${km.toLocaleString("es-PE", { maximumFractionDigits: km < 10 ? 1 : 0 })} km`;
}

export const LEJOS_M = 30_000;

// Chips de distancia de la tarjeta: [{ clave, texto, nivel? }] (nivel pinta el chip de la zona).
//   d = distancias(...)  rio = el río principal  nivelZona = r.estado.nivel (zonaRio)
// Un río del país con trazo de ANA (rio.trazado, ver riosTrazados) dice "(trazo de ANA)" al lado de
// la distancia y, si tiene zonas en rio_cauce_zona_mapa, "(estimación SIMPAC con el relieve)" en el
// chip de la zona; el Mashcón conserva sus textos de siempre.
export function chipsDistancia(d, rio, nivelZona = "sin_senales") {
  if (!d || !rio) return [];
  const chips = [];
  const corto = rio.nombre.replace(/^R[ií]o /, "");
  const despues = rio.trazado ? ` del ${nombreRio(rio)} (${FRASES_RIO_PAIS.trazo})` : ` del ${nombreRio(rio)}`;
  if (d.metrosRio != null) {
    // `metros` va aparte para que la tarjeta pueda contar el número de 0 al valor
    chips.push(
      d.metrosRio > LEJOS_M
        ? {
            clave: "rio",
            texto: `${rio.trazado ? FRASES_RIO_PAIS.lejosTrazo : "El río vigilado más cercano está a"} ${textoMetros(d.metrosRio)} (${corto})`,
            lejos: true,
            metros: d.metrosRio,
          }
        : { clave: "rio", texto: `A ${textoMetros(d.metrosRio)}${despues}`, metros: d.metrosRio, antes: "A ", despues }
    );
  }
  if (d.zona && d.metrosRio != null && d.metrosRio <= LEJOS_M) {
    const nivel = DE_ZONA[nivelZona] ?? "normal";
    const cerca = d.zona.metros != null && d.zona.metros < 1000;
    if (rio.trazado)
      chips.push(
        d.zona.dentro
          ? { clave: "zona", texto: FRASES_RIO_PAIS.dentroZona, nivel, dentro: true }
          : cerca
            ? { clave: "zona", texto: `Fuera de la zona que podría inundarse, a ${textoMetros(d.zona.metros)} (estimación SIMPAC con el relieve)`, nivel: "normal" }
            : { clave: "zona", texto: FRASES_RIO_PAIS.fueraZona, nivel: "normal" }
      );
    else
      chips.push(
        d.zona.dentro
          ? { clave: "zona", texto: "Dentro de la zona que podría inundarse", nivel, dentro: true }
          : cerca
            ? { clave: "zona", texto: `Fuera de la zona que podría inundarse (a ${textoMetros(d.zona.metros)})`, nivel: "normal" }
            : { clave: "zona", texto: "Fuera de la zona que podría inundarse", nivel: "normal" }
      );
  }
  return chips;
}

// Chip punteado cuando el río más cercano (a menos de LEJOS_M) no tiene zonas cargadas: para un río
// del país, que la franja junto al cauce es solo referencial; para un vigilado sin zonas, que aún no
// hay mapa. null si no corresponde (sin río, lejos, zonas sin cargar todavía o ya hay chip de zona).
export function chipSinZonas(d, rio, zonasCargadas = false) {
  if (!d || !rio || !zonasCargadas || d.zona || d.metrosRio == null || d.metrosRio > LEJOS_M) return null;
  return {
    clave: "sin_zonas",
    punteado: true,
    texto: rio.trazado ? FRASES_RIO_PAIS.sinZonas : "Este río aún no tiene mapa de la zona que podría inundarse",
  };
}

// ---------------------------------------------------------------------------
// Titular corto e instrucción
// ---------------------------------------------------------------------------

const COLOR_AVISO = { aviso: "amarillo", alerta: "naranja", emergencia: "rojo" };
const PREFIJO = { alerta: "ALERTA", emergencia: "EMERGENCIA" };

// Qué dice la tarjeta en una o dos líneas, por prioridad: (1) río vigilado en alerta o
// emergencia, (2) alerta_actual en alerta o emergencia (un río de ANA sin mapa de zonas que pasó
// su nivel, p.riosAqui, o un aviso naranja o rojo), (3) aviso amarillo de la zona, (4) lluvia
// medida sobre la referencia, (4b) ríos muy bajos según ANA, (5) río con señales en la cuenca,
// (6) calma con cobertura, (7) sin cobertura, y sin datos o error.
// Devuelve { nivel, etiqueta, texto, origen: "rio"|"aviso"|"lluvia"|"bajo"|"calma"|
// "sin_cobertura"|"sin_datos"|"error", rio (el principal, si lo hay), instruccion (solo
// alerta/emergencia) }.
export function titularCorto(p, rios = [], depto = "tu zona", { origen = null } = {}) {
  const principal = rioPrincipal(rios, origen);
  const nivelRio = DE_ZONA[principal?.estado?.nivel] ?? "normal";
  const base = { rio: principal, instruccion: null };
  const sufijo = p?.desactualizado ? " Puede haber cambiado." : "";

  // sin datos de alerta_actual y sin ríos con los que afirmar algo
  if (p?.alertas == null && !esFuerte(nivelRio)) {
    const error = /^No se pudo/.test(p?.local ?? "");
    return {
      ...base,
      nivel: "sin_dato",
      etiqueta: ETIQUETA_NIVEL.sin_dato,
      texto: error ? "No se pudo consultar las alertas. Revisa tu conexión." : "Consultando las alertas…",
      origen: error ? "error" : "sin_datos",
    };
  }

  // 1. río vigilado en alerta o emergencia (ANA o aviso hidrológico de SENAMHI)
  if (esFuerte(nivelRio)) {
    const s = principal.estado.senales[0];
    const n = nombreRio(principal.rio);
    const que =
      s?.clave === "hidro"
        ? `aviso hidrológico ${COLOR_AVISO[nivelRio]} de SENAMHI para el ${n}`
        : `el ${n} pasó su nivel de ${nivelRio === "emergencia" ? "emergencia" : "alerta"}`;
    const fuente = s?.clave === "hidro" ? "" : ` (ANA${p?.actualizado ? `, ${horaPeru(p.actualizado)}` : ""})`;
    const caido = (p?.avisos ?? []).some((a) => a.startsWith("ANA no respondió")) && p?.actualizado;
    return {
      ...base,
      nivel: nivelRio,
      etiqueta: ETIQUETA_NIVEL[nivelRio],
      texto: `${PREFIJO[nivelRio]}: ${que}${fuente}.${caido ? ` Último dato de ANA a las ${horaPeru(p.actualizado)}; puede haber cambiado.` : sufijo}`,
      origen: "rio",
      instruccion: fraseCorta(principal.rio, principal.estado).accion,
    };
  }

  const nivelLocal = p?.nivelLocal ?? "sin_dato";
  const avisos = p?.avisosAqui ?? [];
  // el aviso que explica el nivel de la zona (no el primero de la lista: en Piura el primero
  // puede ser amarillo y el nivel venir de un naranja); si ninguno coincide, el más alto
  const aviso = avisos.find((a) => a.nivel === nivelLocal) ?? [...avisos].sort((a, b) => ORDEN_NIVEL.indexOf(b.nivel) - ORDEN_NIVEL.indexOf(a.nivel))[0] ?? null;

  // 2. alerta_actual en alerta o emergencia: la causa se lee de las filas por tipo (ríos de ANA
  // que pasaron su nivel, p.riosAqui, o un aviso naranja o rojo de SENAMHI); los ríos muy bajos
  // (nivel_bajo) nunca llegan aquí: lib/nivel.js los deja en "aviso"
  if (esFuerte(nivelLocal)) {
    const riosAqui = p?.riosAqui;
    const crecidos = (riosAqui ?? []).filter((r) => r.nivel === nivelLocal);
    const porAviso = Boolean(aviso && aviso.nivel === nivelLocal);
    // sin filas por tipo (p viejo) y sin aviso que lo explique se mantiene la lectura de antes: un río
    const causa = crecidos.length || (riosAqui == null && !porAviso) ? "rio" : porAviso ? "aviso" : "otra";
    const queRio =
      crecidos.length > 1
        ? `${crecidos.length} ríos pasaron su nivel de ${nivelLocal} (ANA)`
        : `un río pasó su nivel de ${nivelLocal} (ANA)`;
    const texto =
      causa === "rio"
        ? `${PREFIJO[nivelLocal]} en ${depto}: ${queRio}.${sufijo}`
        : causa === "aviso"
          ? `${PREFIJO[nivelLocal]} en ${depto}: aviso ${COLOR_AVISO[nivelLocal]} de SENAMHI por lluvias.${sufijo}`
          : `${PREFIJO[nivelLocal]} en ${depto}: hay una alerta oficial de nivel ${nivelLocal} vigente.${sufijo}`;
    return {
      ...base,
      nivel: nivelLocal,
      etiqueta: ETIQUETA_NIVEL[nivelLocal],
      texto,
      origen: causa === "otra" ? "aviso" : causa,
      instruccion: causa === "rio" ? ACCION_RIO[nivelLocal] : ACCION_AVISO[nivelLocal],
    };
  }

  // 3. aviso amarillo de SENAMHI que cubre la zona
  if (aviso) {
    return { ...base, nivel: "aviso", etiqueta: ETIQUETA_NIVEL.aviso, texto: `Hoy en ${depto}: aviso ${COLOR_AVISO[aviso.nivel] ?? "amarillo"} de SENAMHI por lluvias.${sufijo}`, origen: "aviso" };
  }

  // 4. lluvia medida sobre la referencia de SENAMHI (no es aviso oficial)
  const lluvia = p?.lluviaAqui ?? [];
  if (lluvia.length) {
    const k = lluvia.length;
    return {
      ...base,
      nivel: "aviso",
      etiqueta: "ATENTOS",
      texto: `Hoy en ${depto}: llovió más que la referencia de SENAMHI en ${k} ${k === 1 ? "estación" : "estaciones"}.${sufijo}`,
      origen: "lluvia",
    };
  }

  // 4b. ríos muy bajos según ANA (vaciante): no es una crecida; sin instrucción de orilla ni
  // teléfonos, y el botón lleva a los avisos del mapa (botonPrincipal con nivel "aviso")
  const bajos = p?.bajosAqui ?? 0;
  if (bajos > 0 && !(principal && nivelRio === "aviso")) {
    return {
      ...base,
      nivel: "aviso",
      etiqueta: bajos === 1 ? "RÍO MUY BAJO" : "RÍOS MUY BAJOS",
      texto: `En ${depto}: ${bajos === 1 ? "un río está muy bajo" : `${bajos} ríos están muy bajos`} según ANA (vaciante).${sufijo}`,
      origen: "bajo",
    };
  }

  // 5. río vigilado con señales en la cuenca (atentos)
  if (principal && nivelRio === "aviso") {
    return { ...base, nivel: "aviso", etiqueta: ETIQUETA_NIVEL.aviso, texto: `Atentos en ${depto}: hay señales en la cuenca del ${nombreRio(principal.rio)}.${sufijo}`, origen: "rio" };
  }

  // 6. calma con cobertura
  if (nivelLocal === "normal" || (principal && nivelLocal !== "sin_dato")) {
    const t = principal?.estado?.t;
    const rioTxt = principal
      ? `el ${nombreRio(principal.rio)} está ${t && !t.bajo && t.estado === "normal" ? "tranquilo" : "sin señales de crecida"}`
      : null;
    const texto = rioTxt
      ? `Tranquilo en ${depto}: ${rioTxt} y no hay avisos de SENAMHI.${sufijo}`
      : `Tranquilo en ${depto}: no hay alertas de ríos ni avisos de SENAMHI.${sufijo}`;
    return { ...base, nivel: "normal", etiqueta: ETIQUETA_NIVEL.normal, texto, origen: "calma" };
  }

  // 7. sin cobertura: SIMPAC no vigila nada aquí (nunca verde)
  return {
    ...base,
    nivel: "sin_dato",
    etiqueta: ETIQUETA_NIVEL.sin_dato,
    texto: `En ${depto} SIMPAC todavía no vigila ríos ni estaciones de lluvia que pueda revisar.`,
    origen: "sin_cobertura",
  };
}

// Texto del botón principal según el nivel y si hay ríos vigilados con mapa de zonas.
//   -> { texto, accion: "zona"|"pasar"|"acudir"|"avisos" }
export function botonPrincipal(nivel, { hayRios = true, hayAcudir = true } = {}) {
  if (esFuerte(nivel)) return hayAcudir ? { texto: "A dónde acudir", accion: "acudir" } : { texto: "Ver la zona en el mapa", accion: "pasar" };
  if (!hayRios) return { texto: "Ver avisos del mapa", accion: "avisos" };
  if (nivel === "aviso") return { texto: "Ver qué puede pasar", accion: "pasar" };
  return { texto: "Ver mi zona en el mapa", accion: "zona" };
}

// "Tu ubicación (GPS) · ríos ANA 02:03 · lluvia SENAMHI 02:03" en partes: [{texto, mal}]
export function lineaFuentes({ porGps, ciudad, actualizado, desactualizado, lluviaActualizada, lluviaDesactualizada }) {
  const partes = [{ texto: porGps ? "Tu ubicación (GPS)" : `Desde el centro de ${ciudad ?? "tu ciudad"}` }];
  if (actualizado) partes.push({ texto: `ríos ANA ${desactualizado ? "sin actualizar desde " : ""}${horaPeru(actualizado)}`, mal: Boolean(desactualizado) });
  if (lluviaActualizada)
    partes.push({ texto: `lluvia SENAMHI ${lluviaDesactualizada ? "sin actualizar desde " : ""}${horaPeru(lluviaActualizada)}`, mal: Boolean(lluviaDesactualizada) });
  return partes;
}

// Caja [[sur, oeste], [norte, este]] que encuadra a la persona y el punto del cauce más cercano
// (botón "Ver mi zona en el mapa"), con un margen del 25 % y nunca más chica que ~600 m de lado
// (si estás sobre el río, igual se ve algo de él). null sin origen o sin cauce.
export function cajaTuYRio(origen, cauce) {
  if (!origen || !cauce) return null;
  const cerca = puntoCercanoDelCauce(origen[0], origen[1], cauce);
  if (!cerca) return null;
  const minLado = 0.0027; // grados, unos 300 m a cada lado
  let [s, n] = [Math.min(origen[0], cerca[0]), Math.max(origen[0], cerca[0])];
  let [o, e] = [Math.min(origen[1], cerca[1]), Math.max(origen[1], cerca[1])];
  const mLat = Math.max((n - s) * 0.25, (minLado - (n - s)) / 2, 0);
  const mLon = Math.max((e - o) * 0.25, (minLado - (e - o)) / 2, 0);
  return [
    [s - mLat, o - mLon],
    [n + mLat, e + mLon],
  ];
}

// La fila de caudal_actual que alimenta el medidor del río principal: por nombre de estación y
// río (caudalDelRio de lib/zonaRio.js); el que llama aplica la simulación de desarrollo.
export { caudalDelRio } from "./zonaRio.js";

// Pantalla de bienvenida del GPS: si ya se mostró (localStorage "simpac.gps"). Nunca rompe.
export const CLAVE_GPS = "simpac.gps";
export function gpsVisto(almacen) {
  try {
    return (almacen === undefined ? globalThis.localStorage : almacen)?.getItem(CLAVE_GPS) === "visto";
  } catch {
    return false;
  }
}
export function marcarGpsVisto(almacen) {
  try {
    (almacen === undefined ? globalThis.localStorage : almacen)?.setItem(CLAVE_GPS, "visto");
  } catch {
    /* ventana privada: volverá a salir, aceptable */
  }
}

// ---------------------------------------------------------------------------
// Ríos del país con trazo de ANA (vista rio_cauce_mapa, lib/cauces.js) como candidatos de la
// tarjeta: el río más cercano se elige entre los vigilados (Mashcón) y estos.
// ---------------------------------------------------------------------------

// [{ rio, estado, est, trazado: true }] con la forma de los vigilados de useRiosVigilados: `rio`
// tiene id (rio_ana), nombre, departamento ("Cajamarca, La Libertad" si cruza varios), rio_ana y
// estacion_ana (la estación que manda: así caudalDelRio encuentra su fila de ANA para el medidor),
// el cauce de ~50 m en GeoJSON y km; `estado` es estadoZona (nivel sin_senales|atentos|alerta|
// emergencia) y `est` el estadoRio completo. Entran solo los ríos que el mapa dibuja: con lectura de
// ANA o aviso hidrológico vigente; el Mashcón no (rio_vigilado manda). `simular` (lib/simulacion.js
// simularCauce, solo desarrollo) cambia las entradas de un río antes de calcular su estado.
export function riosTrazados(cauces, caudales = [], senalesCauces = [], vigilados = [], { simular = null } = {}) {
  if (!cauces?.length) return [];
  const { rios } = emparejarCauces(cauces, caudales, vigilados);
  const out = [];
  for (const { fila, lecturas } of rios) {
    const id = fila.rio_ana;
    const partes = GEOMETRIAS.get(id)?.lejos ?? partesDe(fila.cauce_lejos);
    if (!partes?.length) continue;
    const entradas0 = { rioAna: id, lecturas, avisos_hidro: avisosDe(senalesCauces, id) };
    const entradas = simular ? simular(entradas0) : entradas0;
    const est = estadoRio(entradas);
    if (!entradas.lecturas.length && !est.zona.avisoHidro) continue; // el mapa tampoco lo resalta
    out.push({
      rio: {
        id,
        nombre: fila.nombre,
        departamento: fila.departamento,
        rio_ana: fila.rio,
        estacion_ana: est.peor?.estacion ?? fila.estaciones?.[0] ?? null,
        cauce: { type: "MultiLineString", coordinates: partes },
        km: fila.km,
        fuente: fila.fuente,
        trazado: true,
      },
      estado: est.zona,
      est,
      simulado: Boolean(entradas.activa),
      trazado: true,
    });
  }
  return out;
}

// Si un río del país pasa por el departamento ("Huánuco, Loreto, San Martín").
export const rioEnDepto = (rio, depto) =>
  Boolean(depto) && String(rio?.departamento ?? "").split(",").map((x) => x.trim()).includes(depto);

// El río más cercano al origen ([lat, lon]) entre los vigilados y los trazados, con sus metros al
// cauce; a igual distancia, el vigilado (va primero). Sin origen, el vigilado principal; sin
// candidatos, null.
export function rioCercano(vigilados = [], trazados = [], origen = null) {
  if (!origen) return rioPrincipal(vigilados, null);
  let mejor = null;
  for (const r of [...(vigilados ?? []), ...(trazados ?? [])]) {
    if (!r?.rio?.cauce) continue;
    const metros = metrosAlCauce(origen[0], origen[1], r.rio.cauce);
    if (metros == null) continue;
    if (!mejor || metros < mejor.metros) mejor = { ...r, metros };
  }
  return mejor;
}

// Lo que recibe App.verRio para "Ver el río en el mapa" de un río del país: encuadra a la persona y
// el tramo más cercano del cauce (cajaTuYRio), no los 1700 km del Marañón. Para un río vigilado se
// devuelve tal cual (trae centro, zoom y cauce curado). null sin río.
export function rioParaVer(rio, origen) {
  if (!rio) return null;
  if (!rio.trazado) return rio;
  const caja = cajaTuYRio(origen, rio.cauce);
  const cerca = origen ? puntoCercanoDelCauce(origen[0], origen[1], rio.cauce) : null;
  return {
    ...rio,
    centro_lat: cerca?.[0] ?? origen?.[0] ?? null,
    centro_lon: cerca?.[1] ?? origen?.[1] ?? null,
    zoom: 16,
    // cajaGeo (App.jsx) toma la caja de esta línea: las dos esquinas de "tú y el río"
    cauce: caja ? { type: "LineString", coordinates: [[caja[0][1], caja[0][0]], [caja[1][1], caja[1][0]]] } : rio.cauce,
  };
}
