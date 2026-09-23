// Ciudades del Perú (capitales departamentales + Callao) con sus coordenadas, su
// departamento (nombre canónico, igual que backend/ingesta/departamentos.py) y el código de su
// localidad en el pronóstico de SENAMHI ("dp-localidad", verificado en su página del 22-09-2026;
// Callao usa el de Lima).
// Cajamarca va primero porque es el foco del proyecto (ciudad por defecto).
export const CITIES = [
  { name: "Cajamarca", depto: "Cajamarca", lat: -7.1617, lon: -78.5127, localidad: "06-0011" },
  { name: "Lima", depto: "Lima", lat: -12.0464, lon: -77.0428, localidad: "15-0001" },
  { name: "Callao", depto: "Callao", lat: -12.0566, lon: -77.1181, localidad: "15-0001" },
  { name: "Arequipa", depto: "Arequipa", lat: -16.409, lon: -71.5375, localidad: "04-0018" },
  { name: "Trujillo", depto: "La Libertad", lat: -8.1091, lon: -79.0215, localidad: "13-0005" },
  { name: "Chiclayo", depto: "Lambayeque", lat: -6.7714, lon: -79.8409, localidad: "14-0004" },
  { name: "Piura", depto: "Piura", lat: -5.1945, lon: -80.6328, localidad: "20-0003" },
  { name: "Iquitos", depto: "Loreto", lat: -3.7491, lon: -73.2538, localidad: "16-0021" },
  { name: "Cusco", depto: "Cusco", lat: -13.532, lon: -71.9675, localidad: "08-0019" },
  { name: "Huancayo", depto: "Junín", lat: -12.0686, lon: -75.2103, localidad: "12-0028" },
  { name: "Pucallpa", depto: "Ucayali", lat: -8.3791, lon: -74.5539, localidad: "25-0024" },
  { name: "Tacna", depto: "Tacna", lat: -18.0066, lon: -70.2463, localidad: "23-0010" },
  { name: "Ica", depto: "Ica", lat: -14.0678, lon: -75.7286, localidad: "11-0029" },
  { name: "Puno", depto: "Puno", lat: -15.8402, lon: -70.0219, localidad: "21-0030" },
  { name: "Ayacucho", depto: "Ayacucho", lat: -13.1587, lon: -74.2239, localidad: "05-0017" },
  { name: "Huánuco", depto: "Huánuco", lat: -9.9306, lon: -76.2422, localidad: "10-0014" },
  { name: "Huaraz", depto: "Áncash", lat: -9.5278, lon: -77.5278, localidad: "02-0013" },
  { name: "Moyobamba", depto: "San Martín", lat: -6.0341, lon: -76.9711, localidad: "22-0059" },
  { name: "Abancay", depto: "Apurímac", lat: -13.6339, lon: -72.8814, localidad: "03-0031" },
  { name: "Huancavelica", depto: "Huancavelica", lat: -12.7861, lon: -74.9736, localidad: "09-0016" },
  { name: "Cerro de Pasco", depto: "Pasco", lat: -10.6828, lon: -76.2565, localidad: "19-0060" },
  { name: "Moquegua", depto: "Moquegua", lat: -17.1934, lon: -70.9355, localidad: "18-0035" },
  { name: "Tumbes", depto: "Tumbes", lat: -3.5669, lon: -80.4515, localidad: "24-0002" },
  { name: "Chachapoyas", depto: "Amazonas", lat: -6.2299, lon: -77.8688, localidad: "01-0012" },
  { name: "Puerto Maldonado", depto: "Madre de Dios", lat: -12.5933, lon: -69.1891, localidad: "17-0027" },
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
