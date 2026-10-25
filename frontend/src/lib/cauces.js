// Ríos del país con trazo (vista rio_cauce_mapa; backend/mapas/cargar_cauces.py desde ANA - GeoSNIRH:
// red hidrográfica R.J. 056-2018-ANA o Carta Nacional del IGN). Qué estaciones de caudal_actual
// corresponden a cada trazo, de qué color va (la peor de sus estaciones de ANA o, si es más alto, el
// aviso hidrológico de SENAMHI: la misma regla del Mashcón), qué detalle del trazo se pide según el
// zoom, cuáles caen en la vista y en qué tramo cabe el nombre. Módulo puro (sin React ni Leaflet):
// lo prueba node --test (cauces.test.js). El Mashcón no entra: rio_vigilado manda (layers/rios.js lo
// dibuja desde rio_vigilado_mapa con su mapa de zonas); un río sin trazo tampoco se inventa.
import { textoRio } from "./lenguaje.js";
import { caudalDelRio, estadoCauce, estadoZona } from "./zonaRio.js";

const sinTildes = (s) => (s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const ORDEN_CAUCE = ["sd", "normal", "atento", "alerta", "emergencia"];

// Desde qué zoom se pide el trazo fino (~6 m) de los ríos a la vista (antes alcanza el de ~50 m:
// en zoom 12 el error es de ~1 px), desde cuál se escriben los nombres y cuántos a la vez.
export const DETALLE_DESDE = 13;
export const ROTULOS_DESDE = 10;
export const MAX_ROTULOS = 8;
export const detallePorZoom = (zoom) => (zoom >= DETALLE_DESDE ? "cauce" : "lejos");

// Las geometrías no viajan con los datos de la capa: MapView saca una huella JSON de ellos para no
// redibujar lo mismo en cada refresco, y los 750 KB de trazos la pasarían de largo (se redibujaría
// todo cada 10 min). Quedan aquí por río y aligerar() las separa de las filas.
//   rio_ana -> { lejos: coordenadas MultiLineString (~50 m), cauce: las finas (~6 m) o null, caja }
export const GEOMETRIAS = new Map();

// Caja [oeste, sur, este, norte] de las coordenadas de una MultiLineString (o LineString).
export function cajaDeLineas(coords) {
  let o = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  for (const parte of partesDe(coords)) {
    for (const [x, y] of parte) {
      if (x < o) o = x;
      if (x > e) e = x;
      if (y < s) s = y;
      if (y > n) n = y;
    }
  }
  return o === Infinity ? null : [o, s, e, n];
}

// Coordenadas de un GeoJSON de línea como lista de partes [[[lon, lat], ...], ...].
export function partesDe(geo) {
  const g = geo?.type === "Feature" ? geo.geometry : geo;
  if (Array.isArray(g)) return typeof g[0]?.[0] === "number" ? [g] : g;
  if (g?.type === "LineString") return [g.coordinates];
  if (g?.type === "MultiLineString") return g.coordinates;
  return [];
}

// Separa el trazo de cada fila (queda en GEOMETRIAS) y devuelve las filas sin él.
export function aligerar(filas = []) {
  return filas.map(({ cauce_lejos, cauce, ...f }) => {
    const lejos = partesDe(cauce_lejos);
    const previa = GEOMETRIAS.get(f.rio_ana);
    GEOMETRIAS.set(f.rio_ana, { lejos, cauce: cauce ? partesDe(cauce) : previa?.cauce ?? null, caja: cajaDeLineas(lejos) });
    return f;
  });
}

export function guardarDetalle(rioAna, cauce) {
  const g = GEOMETRIAS.get(rioAna);
  if (g && cauce) g.cauce = partesDe(cauce);
}

// Filas de caudal_actual de un trazo: mismo río (rio_cauce.rio es caudal_actual.rio literal) y la
// estación en su lista, sin tildes ni mayúsculas.
export function lecturasDelCauce(fila, caudales = []) {
  const rio = sinTildes(fila.rio);
  const estaciones = (fila.estaciones ?? []).map(sinTildes);
  return caudales.filter((c) => sinTildes(c.rio) === rio && estaciones.includes(sinTildes(c.estacion)));
}

// Empareja los trazos con las estaciones de ANA. Se saltan los trazos marcados `vigilado` y los que
// tengan una estación de un río vigilado (el Mashcón se dibuja desde rio_vigilado_mapa).
//   -> { rios: [{ fila, lecturas }], conTrazo: Set<caudal>, sinTrazo: [caudal] (con punto, sin
//        trazo ni río vigilado) }
export function emparejarCauces(cauces = [], caudales = [], vigilados = []) {
  const conTrazo = new Set();
  const rios = [];
  for (const fila of cauces) {
    if (fila.vigilado) continue;
    const lecturas = lecturasDelCauce(fila, caudales);
    if (lecturas.some((c) => vigilados.some((v) => caudalDelRio(v, [c])))) continue;
    for (const c of lecturas) conTrazo.add(c);
    rios.push({ fila, lecturas });
  }
  const sinTrazo = caudales.filter(
    (c) => c.lat != null && c.lon != null && !conTrazo.has(c) && !vigilados.some((v) => caudalDelRio(v, [c]))
  );
  return { rios, conTrazo, sinTrazo };
}

// La estación que manda en un río con varias (el Huallaga tiene 8): la de peor estado de crecida
// (un umbral de nivel bajo cuenta como normal: estadoCauce); en empate, la primera.
export function peorLectura(lecturas = []) {
  let peor = null;
  let orden = -1;
  for (const c of lecturas) {
    const i = ORDEN_CAUCE.indexOf(estadoCauce(textoRio(c)).estado);
    if (i > orden) {
      peor = c;
      orden = i;
    }
  }
  return peor;
}

// Estado de un río con trazo: `zona` es estadoZona (ANA de la peor estación + aviso hidrológico
// vigente de SENAMHI: nivel sin_senales|atentos|alerta|emergencia y las señales en palabras) y
// `cauce` es estadoCauce (color del trazo: normal|atento|alerta|emergencia|sd y si manda el aviso).
export function estadoRio({ lecturas = [], avisos_hidro = [], ahora = new Date() } = {}) {
  const peor = peorLectura(lecturas);
  const zona = estadoZona({ caudal: peor, senal: { avisos_lluvia: [], lluvia_cuenca: [], avisos_hidro }, ahora });
  const t = peor ? textoRio(peor) : null;
  return { peor, t, zona, cauce: estadoCauce(t, zona.avisoHidro) };
}

// en alerta o emergencia de crecida (el trazo lleva aura y se ve de color aun con el mapa alejado)
export const esFuerte = (estado) => estado.cauce.estado === "alerta" || estado.cauce.estado === "emergencia";

export const cajasSeCruzan = (a, b) => Boolean(a && b) && a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];

// Ríos cuya caja toca la vista `caja` [oeste, sur, este, norte].
export function enVista(rios, caja) {
  return rios.filter((r) => cajasSeCruzan(GEOMETRIAS.get(r.fila.rio_ana)?.caja, caja));
}

// Caja con un margen proporcional a cada lado (0.3 = 30 % del ancho y del alto).
export function cajaConMargen([o, s, e, n], k) {
  const dx = (e - o) * k;
  const dy = (n - s) * k;
  return [o - dx, s - dy, e + dx, n + dy];
}

const dentro = ([x, y], [o, s, e, n]) => x >= o && x <= e && y >= s && y <= n;
// largo aproximado en km de un tramo de una parte (plano local; alcanza para comparar tramos)
function kmDe(parte, i0, i1) {
  let km = 0;
  for (let i = i0; i < i1; i++) {
    const [x1, y1] = parte[i];
    const [x2, y2] = parte[i + 1];
    km += Math.hypot((x2 - x1) * 111.32 * Math.cos((y1 * Math.PI) / 180), (y2 - y1) * 110.57);
  }
  return km;
}

// El tramo más largo del río que cae dentro de `caja` (vértices seguidos de una misma parte):
// sobre él se escribe el nombre (map/rotuloLinea.js) en vez de sobre los 1700 km del Marañón.
//   -> { parte, i0, i1, km } o null si ningún tramo de 2 o más vértices cae en la caja
export function tramoVisible(partes, caja) {
  let mejor = null;
  partes.forEach((parte, p) => {
    let i0 = -1;
    const cerrar = (fin) => {
      if (i0 < 0 || fin - i0 < 1) return;
      const km = kmDe(parte, i0, fin);
      if (!mejor || km > mejor.km) mejor = { parte: p, i0, i1: fin, km };
    };
    for (let i = 0; i < parte.length; i++) {
      if (dentro(parte[i], caja)) {
        if (i0 < 0) i0 = i;
      } else if (i0 >= 0) {
        cerrar(i - 1);
        i0 = -1;
      }
    }
    cerrar(parte.length - 1);
  });
  return mejor;
}

// Alarga un tramo hacia los dos lados mientras los vértices sigan dentro de `caja` (la vista con
// margen): el rótulo se arma sobre el tramo largo y sobrevive a los arrastres cortos.
export function extenderTramo(partes, tramo, caja) {
  const parte = partes[tramo.parte];
  let { i0, i1 } = tramo;
  while (i0 > 0 && dentro(parte[i0 - 1], caja)) i0--;
  while (i1 < parte.length - 1 && dentro(parte[i1 + 1], caja)) i1++;
  return { parte: tramo.parte, i0, i1, km: kmDe(parte, i0, i1) };
}

// Si el tramo que ya tiene rótulo (armado con margen) sigue cubriendo el tramo visible de ahora:
// entonces no se vuelve a armar (el rótulo no parpadea con cada arrastre corto).
export const tramoCubre = (grande, chico) =>
  Boolean(grande && chico) && grande.parte === chico.parte && chico.i0 >= grande.i0 && chico.i1 <= grande.i1;

// Qué ríos a la vista llevan nombre: primero los que están en alerta o emergencia, después los de
// tramo visible más largo; como máximo `maximo`. `estados` da el estado por rio_ana.
//   -> [{ rio, tramo }]
export function elegirRotulados(visibles, caja, estados, maximo = MAX_ROTULOS) {
  const con = [];
  for (const rio of visibles) {
    const g = GEOMETRIAS.get(rio.fila.rio_ana);
    const tramo = g ? tramoVisible(g.lejos, caja) : null;
    if (tramo && tramo.km >= 1) con.push({ rio, tramo, fuerte: esFuerte(estados.get(rio.fila.rio_ana)) });
  }
  con.sort((a, b) => Number(b.fuerte) - Number(a.fuerte) || b.tramo.km - a.tramo.km);
  return con.slice(0, maximo).map(({ rio, tramo }) => ({ rio, tramo }));
}

// Partes [[lon, lat], ...] -> [[lat, lon], ...] por parte (lo que pide L.polyline).
export const aLatLngs = (partes) => partes.map((p) => p.map(([x, y]) => [y, x]));

// Los vértices de un tramo como [lat, lon] (la guía del nombre).
export const latLngsTramo = (partes, { parte, i0, i1 }) => partes[parte].slice(i0, i1 + 1).map(([x, y]) => [y, x]);

// Avisos hidrológicos vigentes de un río (vista rio_cauce_senal) o ninguno.
export const avisosDe = (senales, rioAna) => (senales ?? []).find((s) => s.rio_ana === rioAna)?.avisos_hidro ?? [];

// La licencia de la fila, corta para el popup: hasta el primer punto y coma ("Información pública
// del Estado peruano publicada por la ANA (GeoSNIRH) sin texto de licencia").
export const licenciaCorta = (licencia) => (licencia ?? "").split(";")[0].trim();

// "A, B y C" / "A, B, C y 3 más" (hasta `maximo` nombres, sin repetir)
export function lista(xs, maximo = Infinity) {
  const u = [...new Set(xs.filter(Boolean))];
  const vistos = u.slice(0, maximo);
  const resto = u.length - vistos.length;
  if (resto > 0) return `${vistos.join(", ")} y ${resto} más`;
  return vistos.length > 1 ? `${vistos.slice(0, -1).join(", ")} y ${vistos[vistos.length - 1]}` : vistos[0] ?? "";
}

// Nota bajo el switch de la capa `rio`: cuántos ríos se resaltan, cuáles están en alerta o
// emergencia y cuántas estaciones quedan sin trazo (con hasta 3 ríos de ejemplo).
export function notaCauces({ resaltados, fuertes = [], sinTrazo = [] }) {
  const partes = [`${resaltados} ${resaltados === 1 ? "río del país resaltado" : "ríos del país resaltados"} con el trazo de ANA`];
  if (fuertes.length) partes.push(`en alerta o emergencia: ${lista(fuertes, 4)}`);
  if (sinTrazo.length) {
    const n = sinTrazo.length;
    partes.push(`${n} ${n === 1 ? "estación sin trazo del río" : "estaciones sin trazo del río"} (${lista(sinTrazo.map((c) => c.rio ?? c.estacion), 3)})`);
  }
  return `${partes.join("; ")}.`;
}

// Nota de la capa `zona` por los ríos del país con aura (en alerta o emergencia): "" si no hay.
export function notaAuras(fuertes = []) {
  if (!fuertes.length) return "";
  const n = fuertes.length;
  return `Aura en el cauce de ${n} ${n === 1 ? "río del país" : "ríos del país"} en alerta o emergencia: ${lista(fuertes, 3)}.`;
}

// ---------------------------------------------------------------------------
// Zonas estimadas (vista rio_cauce_zona_mapa) y franja de atención (rio_cauce_mapa.franja) de los
// ríos del país. Las dibuja layers/zonasRio.js y las lee "Tu zona ahora" (lib/zonaAhora.js).
// ---------------------------------------------------------------------------

// Desde qué zoom la capa `zona` pide y dibuja las zonas estimadas de los ríos a la vista (antes
// miden pocos píxeles y pedirlas para todo el país no tiene sentido).
export const ZONAS_DESDE = 12;

// Ancho (m) de la franja de atención a cada lado del trazo: la misma regla que la vista
// rio_cauce_mapa (migración rio_cauce_mapa_franja). Referencial, no es un mapa de inundación.
export const anchoFranja = (km) => (km < 50 ? 60 : km < 200 ? 120 : 250);

// La franja se dibuja solo con el río en alerta o emergencia (ANA o aviso hidrológico de SENAMHI).
export const conFranja = (estado) => Boolean(estado) && esFuerte(estado);

// Filas de rio_cauce_zona_mapa con la forma de las zonas del Mashcón (rio_zona_mapa): `rio` es el
// rio_ana, `tipo` siempre "estimada" (bajo_2m rayada, bajo_3m lisa), así layers/zonasRio.js y
// lib/zonaAhora.js distancias() las tratan igual.
export function zonasDeCauce(filas = []) {
  return (filas ?? [])
    .filter((z) => z?.geojson && (z.subtipo === "bajo_2m" || z.subtipo === "bajo_3m"))
    .map((z) => ({ ...z, rio: z.rio_ana, tipo: "estimada", orden: z.subtipo === "bajo_3m" ? 0 : 1 }))
    .sort((a, b) => a.orden - b.orden);
}

// Qué ríos (rio_ana) piden sus zonas con la vista en `caja` y ese `zoom`: los que tocan la vista,
// desde ZONAS_DESDE; con el mapa más lejos, ninguno (nunca el país entero de golpe).
export function riosParaZonas(rios, caja, zoom) {
  if (zoom < ZONAS_DESDE || !caja) return [];
  return enVista(rios, caja).map((r) => r.fila.rio_ana);
}

// Nota de la capa `zona` por los ríos del país: cuántos tienen zonas estimadas (y cuáles, hasta 3)
// y cuántos llevan franja de atención (en alerta o emergencia). "" si no hay nada que decir.
export function notaZonasPais({ conZonas = [], franjas = [], sinVista = false } = {}) {
  const partes = [];
  if (conZonas.length) {
    const n = conZonas.length;
    partes.push(`${n} ${n === 1 ? "río del país con zonas estimadas" : "ríos del país con zonas estimadas"} con el relieve (${lista(conZonas, 3)}; desde zoom ${ZONAS_DESDE})`);
  } else if (!sinVista) partes.push("Ningún río del país a la vista tiene zonas estimadas todavía");
  if (franjas.length) {
    const n = franjas.length;
    partes.push(`franja de atención referencial en ${n} ${n === 1 ? "río" : "ríos"} en alerta o emergencia: ${lista(franjas, 3)}`);
  }
  return partes.length ? `${partes.join("; ")}.` : "";
}
