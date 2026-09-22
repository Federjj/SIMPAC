// Ciudades del Perú (capitales departamentales + Callao) con sus coordenadas y su
// departamento (nombre canónico, igual que backend/ingesta/departamentos.py).
// Cajamarca va primero porque es el foco del proyecto (ciudad por defecto).
export const CITIES = [
  { name: "Cajamarca", depto: "Cajamarca", lat: -7.1617, lon: -78.5127 },
  { name: "Lima", depto: "Lima", lat: -12.0464, lon: -77.0428 },
  { name: "Callao", depto: "Callao", lat: -12.0566, lon: -77.1181 },
  { name: "Arequipa", depto: "Arequipa", lat: -16.409, lon: -71.5375 },
  { name: "Trujillo", depto: "La Libertad", lat: -8.1091, lon: -79.0215 },
  { name: "Chiclayo", depto: "Lambayeque", lat: -6.7714, lon: -79.8409 },
  { name: "Piura", depto: "Piura", lat: -5.1945, lon: -80.6328 },
  { name: "Iquitos", depto: "Loreto", lat: -3.7491, lon: -73.2538 },
  { name: "Cusco", depto: "Cusco", lat: -13.532, lon: -71.9675 },
  { name: "Huancayo", depto: "Junín", lat: -12.0686, lon: -75.2103 },
  { name: "Pucallpa", depto: "Ucayali", lat: -8.3791, lon: -74.5539 },
  { name: "Tacna", depto: "Tacna", lat: -18.0066, lon: -70.2463 },
  { name: "Ica", depto: "Ica", lat: -14.0678, lon: -75.7286 },
  { name: "Puno", depto: "Puno", lat: -15.8402, lon: -70.0219 },
  { name: "Ayacucho", depto: "Ayacucho", lat: -13.1587, lon: -74.2239 },
  { name: "Huánuco", depto: "Huánuco", lat: -9.9306, lon: -76.2422 },
  { name: "Huaraz", depto: "Áncash", lat: -9.5278, lon: -77.5278 },
  { name: "Moyobamba", depto: "San Martín", lat: -6.0341, lon: -76.9711 },
  { name: "Abancay", depto: "Apurímac", lat: -13.6339, lon: -72.8814 },
  { name: "Huancavelica", depto: "Huancavelica", lat: -12.7861, lon: -74.9736 },
  { name: "Cerro de Pasco", depto: "Pasco", lat: -10.6828, lon: -76.2565 },
  { name: "Moquegua", depto: "Moquegua", lat: -17.1934, lon: -70.9355 },
  { name: "Tumbes", depto: "Tumbes", lat: -3.5669, lon: -80.4515 },
  { name: "Chachapoyas", depto: "Amazonas", lat: -6.2299, lon: -77.8688 },
  { name: "Puerto Maldonado", depto: "Madre de Dios", lat: -12.5933, lon: -69.1891 },
];

export const DEFAULT_CITY = CITIES[0]; // Cajamarca (foco del proyecto)

// Ciudad más cercana a unas coordenadas (para la ubicación detectada).
export function nearestCity(lat, lon) {
  let best = DEFAULT_CITY, bestD = Infinity;
  for (const c of CITIES) {
    const d = (c.lat - lat) ** 2 + (c.lon - lon) ** 2;
    if (d < bestD) { bestD = d; best = c; }
  }
  return best;
}
