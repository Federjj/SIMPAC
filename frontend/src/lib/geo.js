// Geometría mínima en grados (lon, lat), sin Leaflet: distancia entre dos puntos y si un punto
// cae dentro de un polígono GeoJSON. Módulo puro (lo prueban los tests con node --test).

const RADIO_TIERRA_KM = 6371.0088;
const rad = (g) => (g * Math.PI) / 180;

// Distancia sobre la esfera en km.
export function haversineKm(lat1, lon1, lat2, lon2) {
  const dLat = rad(lat2 - lat1);
  const dLon = rad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * RADIO_TIERRA_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

// Par-impar sobre un anillo [[lon, lat], ...] (cerrado o no).
export function dentroDeAnillo(lon, lat, anillo) {
  let dentro = false;
  for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
    const [xi, yi] = anillo[i];
    const [xj, yj] = anillo[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) dentro = !dentro;
  }
  return dentro;
}

// Polygon o MultiPolygon (o un Feature con uno de ellos), con huecos: dentro de un polígono es
// dentro de su borde y fuera de sus huecos (par-impar sobre todos sus anillos).
export function dentroDe(lon, lat, geojson) {
  const g = geojson?.type === "Feature" ? geojson.geometry : geojson;
  if (!g) return false;
  const poligonos = g.type === "MultiPolygon" ? g.coordinates : g.type === "Polygon" ? [g.coordinates] : [];
  return poligonos.some((anillos) => anillos.reduce((d, anillo) => (dentroDeAnillo(lon, lat, anillo) ? !d : d), false));
}

// Caja [oeste, sur, este, norte] de un anillo.
export function cajaDeAnillo(anillo) {
  let o = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  for (const [x, y] of anillo) {
    if (x < o) o = x;
    if (x > e) e = x;
    if (y < s) s = y;
    if (y > n) n = y;
  }
  return [o, s, e, n];
}
