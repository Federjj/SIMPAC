// Zonas que un río vigilado podría afectar (primero el Mashcón): de qué nivel se pinta la zona hoy
// y por qué, en lenguaje claro. Módulo puro (sin React ni Leaflet): lo prueba node --test.
//
// Entradas: el río (vista rio_vigilado_mapa), su fila de caudal_actual (ANA) y su fila de rio_senal
// (avisos de lluvia que tocan la cuenca, lluvia medida en la cuenca y avisos hidrológicos vigentes).
//
// Nivel de la zona = el más alto de sus señales:
//   emergencia  ANA: el río pasó su nivel de emergencia (de crecida)  · o aviso hidrológico ROJO de SENAMHI
//   alerta      ANA: pasó su nivel de alerta                          · o aviso hidrológico NARANJA de SENAMHI
//   atentos     ANA: cerca de su nivel de alerta (criterio SIMPAC)    · o aviso hidrológico AMARILLO de SENAMHI
//               · o aviso de SENAMHI por lluvias NARANJA o ROJO, en curso, sobre la cuenca
//               · o una estación de SENAMHI de la cuenca midió más lluvia que su referencia (1 h o 6 h)
//   sin_senales nada de lo anterior
// Solo lo que trata del río mismo (ANA o el aviso hidrológico de SENAMHI) sube a naranja o rojo: la
// lluvia sola deja "atentos". Un aviso amarillo de lluvia o uno de mañana se menciona, no sube. La
// zona refleja siempre hoy (no sigue el selector de día). Ningún nivel dice hasta dónde llegará el
// agua: no hay relación entre m³/s y la extensión de la zona.
import { referenciaLluvia, textoRio } from "./lenguaje.js";
import { MESES } from "./tiempo.js";

// los colores viven en la paleta del mapa; se reexportan para quien solo importa este módulo
export { CAUCE_HEX, ZONA_HEX, ZONA_OSCURO } from "../map/palette.js";

export const ORDEN = ["sin_senales", "atentos", "alerta", "emergencia"];
export const TITULO_NIVEL = {
  emergencia: "El río pasó su nivel de emergencia",
  alerta: "El río pasó su nivel de alerta",
  atentos: "Atentos",
  sin_senales: "Sin señales ahora",
};
const COLOR = { 2: "amarillo", 3: "naranja", 4: "rojo" };
const DE_AVISO = { 2: "atentos", 3: "alerta", 4: "emergencia" };
const PERU = "America/Lima";
// enlace oficial de un aviso de lluvia (lluvia24h no trae página propia)
export const urlAvisoLluvia = (a) =>
  a.url ?? (a.tipo === "lluvia24h" ? "https://www.senamhi.gob.pe/?p=aviso-24H" : "https://www.senamhi.gob.pe/?p=aviso-meteorologico");
const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });
const mayor = (a, b) => (ORDEN.indexOf(a) >= ORDEN.indexOf(b) ? a : b);
// cierra una frase con punto, sin duplicarlo ("1:00 p. m." ya lo trae)
const conPunto = (t) => (t.endsWith(".") ? t : `${t}.`);
const sinTildes = (s) => (s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

// "3 de octubre, 1:00 p. m." en hora de Perú (con el año si no es el de hoy)
export function diaHora(fecha) {
  const d = new Date(fecha);
  const [a, m, dd] = d.toLocaleDateString("en-CA", { timeZone: PERU }).split("-").map(Number);
  const h = d.toLocaleTimeString("es-PE", { timeZone: PERU, hour: "numeric", minute: "2-digit", hour12: true });
  return `${dd} de ${MESES[m - 1]}${a !== new Date().getFullYear() ? ` de ${a}` : ""}, ${h}`;
}

// Fila de caudal_actual de la estación del río (mismo nombre de estación y de río, sin tildes).
export function caudalDelRio(rio, caudales = []) {
  return (
    caudales.find(
      (c) => sinTildes(c.estacion) === sinTildes(rio.estacion_ana) && sinTildes(c.rio) === sinTildes(rio.rio_ana)
    ) ?? null
  );
}

// { nivel, t, senales: [{clave, nivel, titulo, texto, url?}], menciones: [{clave, texto, url?}], avisoHidro }
export function estadoZona({ caudal = null, senal = null, ahora = new Date() } = {}) {
  const senales = [];
  const menciones = [];
  const t = caudal ? textoRio(caudal) : null;

  // 1. ANA (crecida; un río muy bajo no se desborda)
  if (t && !t.bajo) {
    const medida = caudal.valor != null ? `${num(caudal.valor)} ${caudal.unidad}` : null;
    if (t.estado === "emergencia")
      senales.push({ clave: "ana", nivel: "emergencia", titulo: "El río pasó su nivel de emergencia (ANA)",
        texto: `Lleva ${medida}; su nivel de emergencia es ${num(t.ue)} ${caudal.unidad}.` });
    else if (t.estado === "alerta")
      senales.push({ clave: "ana", nivel: "alerta", titulo: "El río pasó su nivel de alerta (ANA)",
        texto: `Lleva ${medida}; su nivel de alerta es ${num(t.ua)} ${caudal.unidad}.` });
    else if (t.estado === "atento")
      senales.push({ clave: "ana", nivel: "atentos", titulo: "El río está cerca de su nivel de alerta",
        texto: `${t.frase} “Cerca” es un criterio de SIMPAC, no un aviso de ANA.` });
  }
  if (!caudal) menciones.push({ clave: "sin_ana", texto: "ANA no tiene una medición reciente de la estación de este río." });

  // 2. aviso hidrológico de SENAMHI para la estación del río (solo crecida, vigente)
  const hidro = (senal?.avisos_hidro ?? [])
    .filter((h) => h.sentido === "crecida" && DE_AVISO[h.nivel] && !(h.fin && new Date(h.fin) <= ahora))
    .sort((a, b) => b.nivel - a.nivel)[0] ?? null;
  if (hidro) {
    const valor = hidro.valor != null ? ` La estación registró ${num(hidro.valor)} ${hidro.unidad === "m3/s" ? "m³/s" : hidro.unidad}.` : "";
    senales.push({ clave: "hidro", nivel: DE_AVISO[hidro.nivel], titulo: `Aviso hidrológico ${COLOR[hidro.nivel]} de SENAMHI para el río`,
      texto: `${conPunto(`Aviso N.º ${hidro.numero}${hidro.fin ? `, vigente hasta el ${diaHora(hidro.fin)}` : ""}`)}${valor}`, url: hidro.url });
    // con SENAMHI caído el aviso sigue hasta su fin (vista aviso_hidrologico_vigente): se avisa que
    // es el último conocido
    if (hidro.visto_en && ahora - new Date(hidro.visto_en) > 3 * 3_600_000)
      menciones.push({ clave: "hidro_viejo", texto: `La web de SENAMHI no responde desde el ${diaHora(hidro.visto_en)}: este es su último aviso conocido para el río.`, url: hidro.url });
  }
  // un aviso de crecida que la lista publica sin nivel: no sube la zona (no se sabe cuánto), se menciona
  const sinNivel = (senal?.avisos_hidro ?? []).find(
    (h) => h.sentido === "crecida" && h.nivel == null && !(h.fin && new Date(h.fin) <= ahora)
  );
  if (sinNivel && !hidro)
    menciones.push({ clave: "hidro_sin_nivel", texto: `SENAMHI publicó un aviso hidrológico para el río (N.º ${sinNivel.numero}) sin indicar su nivel.`, url: sinNivel.url });

  // 3. avisos de lluvia sobre la cuenca
  const lluvia = senal?.avisos_lluvia ?? [];
  const fuerteHoy = lluvia.filter((a) => a.en_curso && a.nivel >= 3).sort((a, b) => b.nivel - a.nivel)[0];
  if (fuerteHoy)
    senales.push({ clave: "aviso_lluvia", nivel: "atentos", titulo: `Aviso ${COLOR[fuerteHoy.nivel]} de SENAMHI por lluvias sobre la cuenca`,
      texto: conPunto(`Vigente hasta el ${diaHora(fuerteHoy.fin)}`), url: urlAvisoLluvia(fuerteHoy) });
  const manana = lluvia.filter((a) => !a.en_curso && a.nivel >= 3).sort((a, b) => b.nivel - a.nivel)[0];
  if (manana)
    menciones.push({ clave: "aviso_manana", texto: `Desde el ${diaHora(manana.inicio)} rige un aviso ${COLOR[manana.nivel]} de SENAMHI por lluvias sobre la cuenca.`, url: urlAvisoLluvia(manana) });
  if (!fuerteHoy && lluvia.some((a) => a.en_curso && a.nivel === 2))
    menciones.push({ clave: "aviso_amarillo", texto: "Hay un aviso amarillo de SENAMHI por lluvias sobre la cuenca." });

  // 4. lluvia medida en la cuenca sobre la referencia de SENAMHI
  const pasan = (senal?.lluvia_cuenca ?? []).filter((e) => referenciaLluvia(e).pasa);
  if (pasan.length) {
    const una = (e) => {
      const r = referenciaLluvia(e);
      return r.pasa1
        ? `${e.nombre}: ${num(e.pp_1h)} mm en la última hora (referencia de SENAMHI: ${num(e.umbral_1h)} mm)`
        : `${e.nombre}: ${num(e.pp_6h)} mm en 6 horas (referencia de SENAMHI: ${num(e.umbral_6h)} mm)`;
    };
    senales.push({ clave: "lluvia_medida", nivel: "atentos", titulo: "Lluvia fuerte medida en la cuenca",
      texto: `${pasan.slice(0, 2).map(una).join("; ")}${pasan.length > 2 ? ` y ${pasan.length - 2} más` : ""}. No es un aviso oficial.` });
  }

  senales.sort((a, b) => ORDEN.indexOf(b.nivel) - ORDEN.indexOf(a.nivel));
  const nivel = senales.reduce((n, s) => mayor(s.nivel, n), "sin_senales");
  return { nivel, t, senales, menciones, avisoHidro: hidro };
}

// Estado que muestran el cauce y el disco de un río vigilado (capa `rio`): el de su estación de
// ANA o, si es más alto, el del aviso hidrológico de SENAMHI para el río (estado.avisoHidro). El
// aviso puede llegar antes que la nueva lectura de ANA (que es horaria y a veces llega con horas de
// atraso): sin esto la zona saldría roja y el río "tranquilo". Un río muy bajo cuenta como normal.
// -> { estado: normal|atento|alerta|emergencia|sd, porAviso, color: "amarillo"|"naranja"|"rojo"|null }
const ORDEN_CAUCE = ["sd", "normal", "atento", "alerta", "emergencia"];
const CAUCE_DE_AVISO = { 2: "atento", 3: "alerta", 4: "emergencia" };
export function estadoCauce(t, avisoHidro = null) {
  const ana = !t ? "sd" : t.bajo ? "normal" : t.estado;
  const aviso = avisoHidro ? CAUCE_DE_AVISO[avisoHidro.nivel] : null;
  if (aviso && ORDEN_CAUCE.indexOf(aviso) > ORDEN_CAUCE.indexOf(ana))
    return { estado: aviso, porAviso: true, color: COLOR[avisoHidro.nivel] };
  return { estado: ana, porAviso: false, color: null };
}

const ACCION = {
  atentos: "Mira la zona que podría afectar.",
  alerta: "Aléjate de la orilla y no cruces el río.",
  emergencia: "Aléjate de la orilla, no cruces el río y sigue las indicaciones de Defensa Civil.",
};

// Frase corta para la nota de la capa y el panel de estado: "Río Mashcón: ..." + qué hacer.
export function fraseCorta(rio, estado) {
  const { nivel, senales, t } = estado;
  const principal = senales[0];
  const n = rio.nombre;
  if (nivel === "sin_senales") return { texto: `${n}: sin señales de crecida ahora.`, accion: null };
  if (principal.clave === "ana" || principal.clave === "hidro") {
    const quien = principal.clave === "ana"
      ? { emergencia: "pasó su nivel de emergencia (ANA)", alerta: "pasó su nivel de alerta (ANA)", atentos: "cerca de su nivel de alerta (ANA)" }[nivel]
      : `aviso hidrológico ${{ emergencia: "rojo", alerta: "naranja", atentos: "amarillo" }[nivel]} de SENAMHI`;
    return { texto: `${n}: ${quien}.`, accion: ACCION[nivel] };
  }
  // la lluvia: si es un aviso (pronóstico) no se dice que "llueve fuerte"; si se midió, sí
  const tranquilo = t && !t.bajo && t.estado === "normal";
  const que = principal.clave === "lluvia_medida"
    ? `${tranquilo ? "tranquilo, pero llovió" : "llovió"} fuerte en su cuenca`
    : `${tranquilo ? "tranquilo, pero hay" : "hay"} aviso de SENAMHI por lluvia fuerte sobre su cuenca`;
  return { texto: `${n}: ${que}.`, accion: ACCION.atentos };
}

// Nota bajo el switch de la capa (todos los ríos vigilados que se cargaron: [{rio, estado}]).
export function notaZonas(rios) {
  const activos = rios.filter((r) => r.estado.nivel !== "sin_senales")
    .sort((a, b) => ORDEN.indexOf(b.estado.nivel) - ORDEN.indexOf(a.estado.nivel));
  if (!activos.length) return "Ningún río vigilado tiene señales ahora. Toca una zona para ver qué pasó antes.";
  const { texto } = fraseCorta(activos[0].rio, activos[0].estado);
  return activos.length > 1 ? `${texto} Y ${activos.length - 1} río más con señales.` : texto;
}

// "’14" (año corto) de un incidente
export function anioCorto(i) {
  const m = String(i.fecha ?? i.fecha_texto ?? "").match(/(\d{4})/);
  return m ? `’${m[1].slice(2)}` : "";
}

// Distancia en metros entre dos puntos (haversine).
export function metrosEntre(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180;
  const a =
    Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.sqrt(a));
}

// Incidentes que se dibujan, del más nuevo al más viejo, juntos los que quedan a menos de `radioM`
// metros del más nuevo de un grupo (el grupo va en el punto de ese). layers/desbordes.js pasa el
// radio que mide un rombo en pantalla con el zoom de ese momento: con el mapa alejado se juntan más.
export function agruparIncidentes(incidentes = [], radioM = 10) {
  const grupos = [];
  const orden = (i) => i.fecha ?? `${(String(i.fecha_texto).match(/(\d{4})(?!.*\d{4})/) ?? [, "0000"])[1]}-12-31`;
  for (const i of [...incidentes].sort((a, b) => orden(b).localeCompare(orden(a)))) {
    if (i.lat == null || i.lon == null) continue;
    const g = grupos.find((x) => metrosEntre(x.lat, x.lon, i.lat, i.lon) < radioM);
    if (g) g.incidentes.push(i);
    else grupos.push({ lat: i.lat, lon: i.lon, incidentes: [i] });
  }
  return grupos;
}

// Metros de un punto a una zona (GeoJSON Polygon o MultiPolygon, o Feature con uno): 0 si cae
// dentro. Con una proyección plana local (alcanza para unos pocos km).
export function distanciaAZona(lat, lon, geojson) {
  const g = geojson?.type === "Feature" ? geojson.geometry : geojson;
  const poligonos = g?.type === "Polygon" ? [g.coordinates] : g?.type === "MultiPolygon" ? g.coordinates : [];
  if (!poligonos.length) return null;
  const kx = 111_320 * Math.cos((lat * Math.PI) / 180);
  const ky = 110_574;
  const xy = ([x, y]) => [(x - lon) * kx, (y - lat) * ky]; // el punto queda en (0, 0)
  let dentro = false;
  let min = Infinity;
  for (const pol of poligonos) {
    let enEste = false;
    for (const anillo of pol) {
      const pts = anillo.map(xy);
      for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
        const [x1, y1] = pts[j];
        const [x2, y2] = pts[i];
        if (y1 > 0 !== y2 > 0 && 0 < ((x2 - x1) * (0 - y1)) / (y2 - y1) + x1) enEste = !enEste;
        const dx = x2 - x1;
        const dy = y2 - y1;
        const t = dx || dy ? Math.max(0, Math.min(1, -(x1 * dx + y1 * dy) / (dx * dx + dy * dy))) : 0;
        min = Math.min(min, Math.hypot(x1 + t * dx, y1 + t * dy));
      }
    }
    dentro ||= enEste;
  }
  return dentro ? 0 : min;
}

// "Pasó antes" del popup de la zona: desbordes y daños, y las crecidas medidas. Con la zona tocada
// (`geojson`), primero los más cercanos a ella, cada uno con su distancia en metros (`distM`; los
// que solo tienen el distrito van al final, sin distancia); sin zona, del más nuevo al más viejo.
// Devuelve los n primeros y cuántos quedan fuera (`mas`).
export const CERCA_M = 1000;
export function pasoAntes(incidentes = [], n = 4, geojson = null) {
  const porFecha = (a, b) => String(b.fecha ?? b.fecha_texto).localeCompare(String(a.fecha ?? a.fecha_texto));
  const crecidas = incidentes.filter((i) => i.tipo === "crecida").sort(porFecha);
  const distancia = (i) => (geojson && i.lat != null && i.lon != null ? distanciaAZona(i.lat, i.lon, geojson) : null);
  const clave = (i) => (i.distM == null ? Infinity : i.distM);
  const danos = incidentes
    .filter((i) => i.tipo !== "crecida")
    .map((i) => ({ ...i, distM: distancia(i) }))
    .sort((a, b) => clave(a) - clave(b) || porFecha(a, b));
  return { danos: danos.slice(0, n), mas: Math.max(0, danos.length - n), crecidas };
}

// ---------------------------------------------------------------------------
// Simulación (solo desarrollo: quien la llama decide si aplica, ver lib/simulacion.js)
// ---------------------------------------------------------------------------

// Estación de lluvia de la cuenca del Mashcón (lluvia_senamhi_actual) con su referencia real.
const GORE = { clave: "RIO GRANDE GORE@-7.09094,-78.52073", nombre: "RIO GRANDE GORE", umbral_1h: 5, umbral_6h: 15 };

// Aviso hidrológico vigente falso (crecida, de 6 horas) con los textos de los avisos reales.
function avisoFalso(rio, nivel, ahora) {
  const lugares = (rio.lugares_aviso ?? []).map((l) => l.nombre.toUpperCase());
  const lista = lugares.length > 1 ? `${lugares.slice(0, -1).join(", ")} y ${lugares[lugares.length - 1]}` : lugares[0] ?? "";
  return {
    ca: -nivel, numero: 0, titulo: "SIMULACIÓN", nivel, sentido: "crecida",
    inicio: new Date(ahora).toISOString(), fin: new Date(new Date(ahora).getTime() + 6 * 3_600_000).toISOString(),
    valor: 15, unidad: "m3/s", umbral_rojo: 18,
    areas: lista ? `Las potenciales áreas de afectación serían los centros poblados de ${lista}. (SIMULACIÓN)` : null,
    significado_rojo: "Se espera desborde del río. (SIMULACIÓN)",
    url: "#",
  };
}

// Aplica `param` ("mashcon:15.4", "mashcon:hidro2" a "hidro4", "mashcon:lluvia", "mashcon:calma";
// varios separados por comas) al río: cambia el caudal de ANA, agrega un aviso hidrológico vigente
// falso (valor 15) o la estación RIO GRANDE GORE con 7,2 mm, o quita todas las señales de la cuenca
// (un día sin señales). Devuelve { rio, caudal, senal, activa }.
export function simular({ rio, caudal = null, senal = null }, param, ahora = new Date()) {
  let c = caudal;
  let s = senal;
  let activa = false;
  for (const parte of String(param ?? "").split(",")) {
    const [id, que = ""] = parte.trim().split(":");
    if (!rio || !id || id !== rio.id) continue;
    const base = { avisos_lluvia: [], lluvia_cuenca: [], avisos_hidro: [], ...(s ?? { rio: rio.id }) };
    if (/^\d+(\.\d+)?$/.test(que)) {
      if (!c) continue; // sin fila de ANA no hay umbrales con qué comparar
      c = { ...c, valor: Number(que) };
    } else if (/^hidro[234]$/.test(que)) {
      s = { ...base, avisos_hidro: [avisoFalso(rio, Number(que.slice(5)), ahora), ...base.avisos_hidro] };
    } else if (que === "calma") {
      s = { ...base, avisos_lluvia: [], lluvia_cuenca: [], avisos_hidro: [] }; // un día sin señales
    } else if (que === "lluvia") {
      const gore = { ...GORE, pp_1h: 7.2, pp_6h: 7.2, medido_en: new Date(ahora).toISOString() };
      s = { ...base, lluvia_cuenca: [gore, ...base.lluvia_cuenca.filter((e) => e.clave !== GORE.clave)] };
    } else continue;
    activa = true;
  }
  return { rio, caudal: c, senal: s, activa };
}
