// Pronóstico oficial de SENAMHI por localidad (vista pronostico_vigente, tarea 'pronostico' del
// worker): qué ícono y qué frase corta lleva cada día, la franja de 3 días de tu localidad y la
// nota de la capa. El texto de SENAMHI manda; la clasificación (tipo, posible, por...) ya viene
// hecha del backend (backend/ingesta/lectura_pronostico.py). Módulo puro (node --test).
import { DIAS, diaCorto, diaMesCorto, diaSemana, fechaPeru } from "./tiempo.js";
import { haversineKm } from "./geo.js";

const DIA_MS = 86_400_000;
const mayuscula = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : "");
const plano = (t) => (t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();

// "AAAA-MM-DD" más n días (fechas de Perú, sin horario de verano).
export const sumarDias = (iso, n) => fechaPeru(Date.parse(`${iso}T12:00:00-05:00`) + n * DIA_MS);
const diasEntre = (desde, hasta) => Math.round((Date.parse(hasta) - Date.parse(desde)) / DIA_MS);

// Opción del selector de día ("ahora" | "manana" | "pasado") -> "AAAA-MM-DD" en hora de Perú.
export const DIAS_OPCION = { ahora: 0, manana: 1, pasado: 2 };
export function fechaDeOpcion(opcion, ahora = Date.now()) {
  return fechaPeru(ahora + (DIAS_OPCION[opcion] ?? 0) * DIA_MS);
}

// "Hoy", "Mañana" o el día de la semana ("Viernes").
export function etiquetaDia(fecha, hoy = fechaPeru()) {
  if (fecha === hoy) return "Hoy";
  if (fecha === sumarDias(hoy, 1)) return "Mañana";
  return mayuscula(DIAS[diaSemana(fecha)]);
}

// "Hoy, miércoles 23", "Mañana, jueves 24" o "Viernes 25" (título de un día en el popup).
export function diaConFecha(fecha, hoy = fechaPeru(), corto = false) {
  const n = Number(fecha.split("-")[2]);
  const dia = corto ? diaCorto(fecha) : `${DIAS[diaSemana(fecha)]} ${n}`;
  if (fecha === hoy) return `Hoy, ${dia}`;
  if (fecha === sumarDias(hoy, 1)) return `Mañana, ${dia}`;
  return mayuscula(dia);
}

// SENAMHI emite el pronóstico por la noche; la página solo trae la fecha.
export function emitidoTexto(emision, hoy = fechaPeru()) {
  if (!emision) return "";
  if (emision === hoy) return "Emitido hoy";
  if (emision === sumarDias(hoy, -1)) return "Emitido anoche";
  return `Emitido el ${diaMesCorto(emision)}`;
}

// Más de 3 días sin un pronóstico nuevo (SENAMHI no lo actualiza los fines de semana ni feriados).
export function atrasado(emision, hoy = fechaPeru()) {
  return Boolean(emision) && diasEntre(emision, hoy) > 3;
}

// Temperaturas "21°/10°" (o "–" si SENAMHI no las da).
export function temps(f) {
  if (f?.tmax == null && f?.tmin == null) return "–";
  const t = (v) => (v == null ? "–" : `${v}°`);
  return `${t(f.tmax)}/${t(f.tmin)}`;
}

// Color del punto y prioridad en el mapa por clase (tono "posible" = puede llover).
export const PRIORIDAD_DISCO = { tormenta: 700, nieve: 650, lluvia: 600, posible: 500, seco: 300 };
const RX_NIEVE = /\b(?:NEVADAS?|NIEVE|AGUANIEVE)\b/;

// Cómo se dibuja y se dice un día: {glifo, clase, tono, posible (borde punteado), corto, extra, prioridad, sol}.
// Nunca usa amarillo, naranja ni rojo (esos son de los avisos).
export function aspecto(f) {
  const m = f.momento ? ` ${f.momento}` : "";
  const a = (glifo, clase, posible, corto, extra = null, tono = clase) => ({
    glifo,
    clase,
    tono,
    posible,
    corto,
    extra,
    prioridad: PRIORIDAD_DISCO[tono],
    sol: glifo === "sol" || glifo === "sol_nube",
  });
  if (f.tipo === "tormenta") {
    if (!f.posible) return a("tormenta", "tormenta", false, `Tormenta${m}`);
    if (f.lluvia_segura) return a("tormenta", "tormenta", true, `Lluvia${m}`, "puede haber tormenta");
    return a("tormenta", "tormenta", true, `Puede haber tormenta${m}`);
  }
  if (f.tipo === "nieve") {
    const p = Boolean(f.posible);
    if (RX_NIEVE.test(plano(f.texto)))
      return a("nieve", "nieve", p, p ? `Puede nevar${m}` : `Nieve${m}`, f.granizo ? "con granizo" : null);
    return a("nieve", "nieve", p, p ? `Puede granizar${m}` : `Granizo${m}`);
  }
  if (f.tipo === "lluvia") {
    if (f.posible) return a("tendencia", "lluvia", true, `Puede llover${m}`, null, "posible");
    return a("lluvia", "lluvia", false, `Lluvia${f.intensidad ? ` ${f.intensidad}` : ""}${m}`);
  }
  if (f.cielo === "despejado") return a("sol", "seco", false, "Despejado");
  if (f.cielo === "nublado") return a("nube", "seco", false, "Nublado");
  if (f.cielo === "neblina") return a("nube", "seco", false, "Neblina");
  return a("sol_nube", "seco", false, f.cielo === "parcial" ? "Algo nublado" : "Sin lluvia");
}

export const urlLocalidad = (codigo) => {
  const [dp, localidad] = String(codigo).split("-");
  return `https://www.senamhi.gob.pe/?p=pronostico-detalle&dp=${dp}&localidad=${localidad}`;
};

const datosLocalidad = (f) => ({
  codigo: f.codigo,
  nombre: f.nombre,
  departamento: f.departamento,
  lat: f.lat,
  lon: f.lon,
  url: f.url ?? urlLocalidad(f.codigo),
});

// Localidad con pronóstico más cercana a un punto: hasta 10 km "ok", hasta 30 km "cercana",
// más lejos "lejos". null si no hay ninguna con coordenadas.
export const KM_OK = 10;
export const KM_CERCANA = 30;
export function localidadCercana(filas, lat, lon) {
  let mejor = null;
  for (const f of filas ?? []) {
    if (f.lat == null || f.lon == null) continue;
    const km = haversineKm(lat, lon, f.lat, f.lon);
    if (!mejor || km < mejor.km) mejor = { ...datosLocalidad(f), km };
  }
  if (!mejor) return null;
  return { ...mejor, estado: mejor.km <= KM_OK ? "ok" : mejor.km <= KM_CERCANA ? "cercana" : "lejos" };
}

// Centro del mapa al elegir una ciudad: sobre la línea de la ciudad al punto de su localidad del
// pronóstico, a no más de `maxKm` de la localidad (a zoom 14, 1 km son unos 105 px), para que el
// disco de tu localidad se vea también en un celular (en Cajamarca la estación está a 2,3 km del
// centro). Sin punto de la localidad, la ciudad.
export function centroCiudad(ciudad, localidad, maxKm = 1) {
  if (localidad?.lat == null || localidad?.lon == null) return { lat: ciudad.lat, lon: ciudad.lon };
  const km = haversineKm(ciudad.lat, ciudad.lon, localidad.lat, localidad.lon);
  const t = km > maxKm ? maxKm / km : 1; // fracción del camino de la localidad a la ciudad
  return { lat: localidad.lat + (ciudad.lat - localidad.lat) * t, lon: localidad.lon + (ciudad.lon - localidad.lon) * t };
}

// Los 3 días (hoy, mañana y pasado) de una localidad, con su fila o null si falta ese día.
export function franja(filas, codigo, hoy = fechaPeru()) {
  return [0, 1, 2].map((n) => {
    const fecha = sumarDias(hoy, n);
    return {
      fecha,
      etiqueta: etiquetaDia(fecha, hoy),
      fechaCorta: diaCorto(fecha),
      fila: (filas ?? []).find((f) => f.codigo === codigo && f.fecha === fecha) ?? null,
    };
  });
}

const emisionMax = (filas) => filas.reduce((m, f) => (f.emision && (!m || f.emision > m) ? f.emision : m), null);

// Estado de la franja de tu localidad (hooks/usePronosticoLocal):
//   filas undefined = cargando · null = la vista aún no existe · error = falló la carga.
// Sin GPS se usa la localidad de la ciudad elegida; con GPS, la más cercana (ok / cercana / lejos).
export function pronosticoLocal({ filas, error, ciudad, porGps, userPos, hoy = fechaPeru() }) {
  const vacio = { localidad: null, dias: [], emision: null, atrasado: false };
  if (error) return { estado: "error", ...vacio };
  if (filas === undefined) return { estado: "cargando", ...vacio };
  if (filas === null) return { estado: "sin_servicio", ...vacio };
  let localidad;
  let estado = "ok";
  if (porGps && userPos) {
    const c = localidadCercana(filas, userPos[0], userPos[1]);
    if (!c) return { estado: "sin_datos", ...vacio, localidad: { nombre: ciudad?.name ?? "tu zona" } };
    ({ estado, ...localidad } = c);
  } else {
    const codigo = ciudad?.localidad;
    const f = filas.find((x) => x.codigo === codigo);
    localidad = f
      ? { ...datosLocalidad(f), km: null }
      : { codigo, nombre: ciudad?.name ?? "", departamento: ciudad?.depto ?? null, url: codigo ? urlLocalidad(codigo) : null, km: null };
  }
  const dias = franja(filas, localidad.codigo, hoy);
  const propias = filas.filter((f) => f.codigo === localidad.codigo);
  if (estado !== "lejos" && !dias.some((d) => d.fila)) estado = "sin_datos";
  const emision = emisionMax(propias);
  return { estado, localidad, dias, emision, atrasado: atrasado(emision, hoy) };
}

// Nota de la capa: "Hoy, mié 23: lluvia en 57 localidades, puede llover en 42, tormenta en 4,
// sin lluvia en 174." (las categorías en cero no se nombran).
export function notaPronostico(filas, fecha, hoy = fechaPeru()) {
  const deDia = (filas ?? []).filter((f) => f.fecha === fecha);
  if (!deDia.length) return "SENAMHI no tiene pronóstico por localidad para ese día.";
  const n = { lluvia: 0, posible: 0, tormenta: 0, nieve: 0, seco: 0 };
  for (const f of deDia) n[aspecto(f).tono]++;
  const partes = [
    ["lluvia", "lluvia en"],
    ["posible", "puede llover en"],
    ["tormenta", "tormenta en"],
    ["nieve", "nieve o granizo en"],
    ["seco", "sin lluvia en"],
  ]
    .filter(([k]) => n[k])
    .map(([k, t], i) => `${t} ${n[k]}${i === 0 ? (n[k] === 1 ? " localidad" : " localidades") : ""}`);
  let texto = `${diaConFecha(fecha, hoy, true)}: ${partes.join(", ")}.`;
  const emision = emisionMax(deDia);
  if (atrasado(emision, hoy))
    texto += ` Emitido el ${diaMesCorto(emision)}: SENAMHI no lo actualiza los fines de semana ni feriados.`;
  return texto;
}
