// Incidentes DEMO (en producción vienen de la tabla `report` de Supabase).
// tipo: inundacion | lluvia | huayco | via
export const DEMO_INCIDENTS = [
  { tipo: "via", titulo: "Vía bloqueada", lat: -7.15, lon: -78.505, autor: "Rosa T.", hace: "Hace 1 hora", km: "2.3 km", desc: "La vía a Baños del Inca está bloqueada por derrumbe.", up: 8, down: 0 },
  { tipo: "lluvia", titulo: "Lluvia intensa", lat: -7.163, lon: -78.498, autor: "Carlos M.", hace: "Hace 15 min", km: "0.8 km", desc: "Lluvia muy fuerte en el Jr. Inca. Hay charcos grandes.", up: 12, down: 1 },
  { tipo: "inundacion", titulo: "Inundación", lat: -7.172, lon: -78.515, autor: "María L.", hace: "Hace 3 horas", km: "1.5 km", desc: "El río desbordó en el sector Los Baños.", up: 15, down: 1 },
  { tipo: "huayco", titulo: "Huayco", lat: -7.145, lon: -78.53, autor: "Jorge P.", hace: "Hace 2 horas", km: "4.1 km", desc: "Deslizamiento de lodo en la carretera.", up: 6, down: 0 },
];

export const DEMO_USERS = [
  [-7.16, -78.507], [-7.168, -78.503], [-7.155, -78.518],
];
