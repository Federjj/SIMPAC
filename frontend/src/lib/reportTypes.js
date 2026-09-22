// Tipos de reporte ciudadano (estilo Waze). Única fuente de la taxonomía en el
// frontend: los ids y subtipos deben coincidir con el CHECK de report.tipo y
// report.subtipo en la BD (supabase/migrations/20260922191903_comunidad_uuid_y_permisos.sql).
export const REPORT_TYPES = [
  { id: "inundacion", label: "Inundación", color: "#3B3BEB" },
  { id: "huayco", label: "Huayco / deslizamiento", color: "#EB3B3B" },
  { id: "lluvia_intensa", label: "Lluvia intensa", color: "#3BEBEB" },
  { id: "via_bloqueada", label: "Vía bloqueada", color: "#111111" },
  {
    id: "atasco",
    label: "Atasco",
    color: "#EBEB3B",
    subtipos: [
      { id: "leve", label: "Leve" },
      { id: "moderado", label: "Moderado" },
      { id: "detenido", label: "Detenido" },
    ],
  },
  { id: "bache", label: "Bache", color: "#F58E27" },
  { id: "accidente", label: "Accidente", color: "#DB0404" },
  { id: "otro", label: "Otro", color: "#6B7280" },
];

export const REPORT_TYPE = Object.fromEntries(REPORT_TYPES.map((t) => [t.id, t]));
