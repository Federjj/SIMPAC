// "A dónde acudir": qué hay cerca (salud, comisaría, bomberos) y cómo decirlo en lenguaje claro.
// Lógica pura (sin React ni Supabase: la prueba acudir.test.js la lee con node --test); lo único
// que habla con la base, getPuntosAcudir, carga lib/queries.js solo cuando se llama.
// Los datos salen de la tabla punto_acudir (backend/mapas/cargar_acudir.py): cada punto trae su
// fuente, su enlace y su fecha, y aquí nunca se inventa un horario ni un teléfono.
import { haversineKm } from "./geo.js";

// Cómo se ve cada tipo (colores lejos del semáforo verde/ámbar/naranja/rojo de los niveles).
export const TIPO_ACUDIR = {
  salud: { label: "Salud", plural: "de salud", leyenda: "Hospital, centro o puesto de salud (SUSALUD)", color: "#0F766E" },
  comisaria: { label: "Comisaría", plural: "comisarías", leyenda: "Comisaría PNP (padrón MININTER 2019)", color: "#1D4ED8" },
  bomberos: { label: "Bomberos", plural: "de bomberos", leyenda: "Compañía de bomberos (CGBVP)", color: "#991B1B" },
  zona_segura: { label: "Zona segura", plural: "zonas seguras", leyenda: "Zona segura oficial", color: "#4D7C0F" },
  albergue: { label: "Albergue", plural: "albergues", leyenda: "Albergue oficial", color: "#6D28D9" },
  otro: { label: "Defensa Civil", plural: "de Defensa Civil", leyenda: "Oficina de Defensa Civil, municipalidad o gobierno regional", color: "#475569" },
};
// los tres de la tarjeta, en este orden
export const TIPOS_TARJETA = ["salud", "comisaria", "bomberos"];

// Recomendación general de INDECI, leída el 14-10-2026 en gob.pe. Campaña "Preparados ante lluvias
// intensas": "Identifiquen rutas de evacuación, zonas seguras y puntos de reunión en caso de
// inundaciones. ¡Recuerden que deben estar en zonas altas!". Nota del 25-09-2023 (medidas ante
// lluvias intensas): "Aléjate y no cruces zonas inundadas, ríos, cauces de quebradas o laderas de
// cerros". La zona segura concreta de cada lugar la define la municipalidad (Defensa Civil).
export const ZONA_SEGURA = {
  texto: "Zona segura: terreno alto y lejos del río o la quebrada.",
  detalle:
    "INDECI: las zonas seguras y puntos de reunión ante inundaciones deben estar en zonas altas; aléjate de ríos, cauces de " +
    "quebradas y laderas de cerros. La zona segura oficial de tu barrio la define tu municipalidad: consulta Defensa Civil.",
  fuente: "INDECI, campaña Preparados ante lluvias intensas (gob.pe)",
  url: "https://www.gob.pe/institucion/indeci/campa%C3%B1as/6555-preparados-ante-lluvias-intensas",
  url_nota: "https://www.gob.pe/institucion/indeci/noticias/838989-indeci-recomienda-medidas-de-preparacion-ante-lluvias-intensas-y-peligros-asociados",
};
export const NOTA_MUNICIPALIDAD = "La zona segura oficial la define tu municipalidad; consulta Defensa Civil.";

// Radio por defecto de la búsqueda y hasta dónde se prefiere un hospital 24 h sobre lo más cercano.
export const RADIO_KM = 30;
export const HOSPITAL_HASTA_KM = 15;
export const PASO_CAJA = 0.1; // grados: la caja se redondea a décimas para que la caché se repita

// Caja { oeste, sur, este, norte } redondeada hacia afuera a PASO_CAJA grados.
export function cajaRedondeada({ oeste, sur, este, norte }) {
  const abajo = (v) => Math.floor(v / PASO_CAJA) * PASO_CAJA;
  const arriba = (v) => Math.ceil(v / PASO_CAJA) * PASO_CAJA;
  const r = (v) => Number(v.toFixed(1));
  return { oeste: r(abajo(oeste)), sur: r(abajo(sur)), este: r(arriba(este)), norte: r(arriba(norte)) };
}

// Caja alrededor de un punto: radioKm a cada lado (1 grado de latitud ~ 111 km; la longitud se
// corrige por la latitud), redondeada a décimas.
export function cajaAlrededor(lat, lon, radioKm = RADIO_KM) {
  const dLat = radioKm / 111.32;
  const dLon = radioKm / (111.32 * Math.max(0.2, Math.cos((lat * Math.PI) / 180)));
  return cajaRedondeada({ oeste: lon - dLon, sur: lat - dLat, este: lon + dLon, norte: lat + dLat });
}

// Puntos de la tabla punto_acudir alrededor de un punto (los de la caja de radioKm, con su
// distancia en metros, ordenados del más cercano al más lejano). Nunca la tabla entera; la caché
// de 60 min por caja vive en lib/queries.js (getPuntosAcudirCaja).
export async function getPuntosAcudir({ lat, lon, radioKm = RADIO_KM }) {
  if (lat == null || lon == null) return [];
  const { getPuntosAcudirCaja } = await import("./queries.js");
  const filas = await getPuntosAcudirCaja(cajaAlrededor(lat, lon, radioKm));
  return conDistancia(filas, lat, lon);
}

// Copia de cada punto con distancia_m desde (lat, lon), del más cercano al más lejano.
export function conDistancia(puntos = [], lat, lon) {
  return puntos
    .filter((p) => p.lat != null && p.lon != null)
    .map((p) => ({ ...p, distancia_m: Math.round(haversineKm(lat, lon, p.lat, p.lon) * 1000) }))
    .sort((a, b) => a.distancia_m - b.distancia_m);
}

// Hospital o instituto (no un puesto o centro de salud): por la categoría de RENIPRESS.
export const esHospital = (p) => /^(hospital|instituto)/i.test(p?.categoria ?? "");

// El establecimiento de salud que conviene mostrar: el hospital que atiende 24 h más cercano si
// está a menos de HOSPITAL_HASTA_KM; si no, el más cercano de todos (aunque sea un puesto de salud).
export function mejorSalud(salud = []) {
  if (!salud.length) return null;
  const orden = [...salud].sort((a, b) => a.distancia_m - b.distancia_m);
  const hospital = orden.find((p) => esHospital(p) && p.atiende_24h === true && p.distancia_m < HOSPITAL_HASTA_KM * 1000);
  return hospital ?? orden[0];
}

// Los más cercanos a (lat, lon). Con porTipo (lo normal en la tarjeta): el mejor de cada tipo, en
// el orden salud, comisaría, bomberos y después los demás tipos; sin porTipo: los `maximo` más
// cercanos sin importar el tipo. Siempre con distancia_m. maxKm (opcional) descarta lo que quede
// más lejos.
export function masCercanos(puntos = [], lat, lon, { porTipo = true, maximo = 3, maxKm = null } = {}) {
  let lista = conDistancia(puntos, lat, lon);
  if (maxKm != null) lista = lista.filter((p) => p.distancia_m <= maxKm * 1000);
  if (!porTipo) return lista.slice(0, maximo);
  const porClase = new Map();
  for (const p of lista) {
    const t = TIPO_ACUDIR[p.tipo] ? p.tipo : "otro";
    if (!porClase.has(t)) porClase.set(t, []);
    porClase.get(t).push(p);
  }
  const orden = [...TIPOS_TARJETA, ...Object.keys(TIPO_ACUDIR).filter((t) => !TIPOS_TARJETA.includes(t))];
  const out = [];
  for (const t of orden) {
    const del = porClase.get(t);
    if (!del?.length) continue;
    out.push(t === "salud" ? mejorSalud(del) : del[0]);
  }
  return out.slice(0, maximo);
}

// "a 850 m", "a 2,3 km", "a 23 km" (menos de 1 km, redondeado a 10 m; a menos de 10 km, con un decimal).
export function textoDistancia(metros) {
  if (metros == null || !Number.isFinite(metros)) return null;
  if (metros < 1000) return `a ${Math.max(10, Math.round(metros / 10) * 10)} m`;
  const km = metros / 1000;
  if (km < 10) return `a ${km.toFixed(1).replace(".", ",")} km`; // coma decimal, como se escribe en el Perú (sin depender del ICU del navegador)
  return `a ${Math.round(km)} km`;
}

// "076599040 / 076599030" -> ["076599040", "076599030"]
export function telefonos(texto) {
  return String(texto ?? "")
    .split(/\s*[/;,]\s*/)
    .map((t) => t.trim())
    .filter((t) => /\d{6,}/.test(t.replace(/[\s-]/g, "")));
}
// lo que va en href="tel:" (solo dígitos y +)
export const telHref = (t) => `tel:${String(t).replace(/[^\d+]/g, "")}`;

// Enlaces para llegar: Google Maps (cómo llegar hasta el punto) y geo: para la app de mapas del
// celular (Android). Coordenadas con 6 decimales, siempre con punto decimal.
export function enlacesComoLlegar(lat, lon) {
  const a = Number(lat).toFixed(6);
  const o = Number(lon).toFixed(6);
  return {
    maps: `https://www.google.com/maps/dir/?api=1&destination=${a},${o}`,
    geo: `geo:${a},${o}?q=${a},${o}`,
  };
}

export function esAndroid(ua = typeof navigator !== "undefined" ? navigator.userAgent : "") {
  return /android/i.test(ua ?? "");
}

// "2026-09-30" -> "30-09-2026"
export function fechaCorta(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return m ? `${m[3]}-${m[2]}-${m[1]}` : iso ?? "";
}

// De dónde sale el punto y de cuándo es, con la salvedad del padrón de comisarías (2019).
export function notaFuente(p) {
  if (!p) return "";
  const fecha = p.actualizado ? ` (${fechaCorta(p.actualizado)})` : "";
  if (p.tipo === "comisaria") return `Fuente: MININTER, padrón de comisarías de noviembre de 2019 vía CENEPRED; puede haber cambios.`;
  if (p.tipo === "bomberos") return `Fuente: CGBVP${fecha}; ubicación de CENEPRED/COEN.`;
  if (p.tipo === "salud") return `Fuente: SUSALUD, RENIPRESS${fecha}.`;
  return `Fuente: ${p.fuente ?? "no indicada"}${fecha}.`;
}

// Nombre corto del tipo para la tarjeta ("Hospital", "Comisaría", "Bomberos").
export function tituloTipo(p) {
  if (p?.tipo === "salud") return esHospital(p) ? "Hospital" : /cl[ií]nica/i.test(p.categoria ?? "") ? "Clínica" : "Centro de salud";
  return TIPO_ACUDIR[p?.tipo]?.label ?? "Punto";
}
