import L from "leaflet";
import { History } from "lucide-react";
import { getMapaFEN } from "@/lib/queries";
import { popupHtml } from "../markers";
import { FUENTE_SENAMHI } from "../senamhi";

// Mapas de eventos El Niño pasados: cuánto más (o menos) llovió que lo normal en mm
// acumulados (SENAMHI/IDESEP, tabla mapa con variable 'FEN'). Cada registro de IDESEP trae
// varios trimestres; el cargador guardó el primero: diciembre a febrero (en 2023, enero a
// marzo), no todo el evento. Por eso cada evento dice sus meses.
const EVENTOS = [
  { valor: "1982-1983", etiqueta: "El Niño 1982-1983 (dic a feb)", meses: "diciembre de 1982 y febrero de 1983" },
  { valor: "1997-1998", etiqueta: "El Niño 1997-1998 (dic a feb)", meses: "diciembre de 1997 y febrero de 1998" },
  { valor: "2017", etiqueta: "El Niño costero 2017 (dic a feb)", meses: "diciembre de 2016 y febrero de 2017" },
  { valor: "2023", etiqueta: "El Niño costero 2023 (ene a mar)", meses: "enero y marzo de 2023" },
  { valor: "2023-2024", etiqueta: "El Niño 2023-2024 (dic a feb)", meses: "diciembre de 2023 y febrero de 2024" },
];

// Rangos de SENAMHI ("300 - 550", "< -800", "> 2,500") agrupados en 6 clases por su punto medio.
// "Cerca de lo normal" es solo +-30 mm: en la costa desértica 30 a 60 mm más ya es mucho
// (en Chiclayo llueven ~30 mm en todo un año normal).
const CLASES = [
  { hasta: -300, color: "#8C510A", label: "Mucha menos lluvia (más de 300 mm menos)" },
  { hasta: -60, color: "#D8B365", label: "Menos lluvia (60 a 300 mm menos)" },
  { hasta: -30, color: "#F0DDB0", label: "Algo menos de lluvia (30 a 60 mm menos)" },
  { hasta: 30, color: "#E5E5E5", label: "Cerca de lo normal (hasta 30 mm de diferencia)" },
  { hasta: 60, color: "#D4ECFA", label: "Algo más de lluvia (30 a 60 mm más)" },
  { hasta: 300, color: "#95CEF4", label: "Más lluvia (60 a 300 mm más)" },
  { hasta: 1000, color: "#3B3BEB", label: "Mucha más lluvia (300 a 1000 mm más)" },
  { hasta: Infinity, color: "#7B2FBE", label: "Muchísima más lluvia (más de 1000 mm más)" },
];

// Un solo renderer canvas por mapa: Leaflet lo agrega al mapa (no al grupo) y no lo quita al
// limpiar la capa, así que crear uno por dibujo dejaba un canvas extra en cada cambio de evento.
const renderers = new WeakMap();
function renderer(map) {
  if (!renderers.has(map)) renderers.set(map, L.canvas({ pane: "areas" }));
  return renderers.get(map);
}

const numeros = (rango) => (rango ?? "").replace(/,/g, "").match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];

function medio(rango) {
  const n = numeros(rango);
  if (!n.length) return null;
  return n.length === 1 ? n[0] : (n[0] + n[1]) / 2;
}

function clase(rango) {
  const m = medio(rango);
  return m == null ? null : CLASES.find((c) => m < c.hasta) ?? CLASES[CLASES.length - 1];
}

// "300 - 550" -> "entre 300 y 550 mm más de lo normal"
function frase(rango) {
  const r = (rango ?? "").trim();
  const n = numeros(r);
  if (r.startsWith("<")) return `más de ${Math.abs(n[0])} mm menos de lo normal`;
  if (r.startsWith(">")) return `más de ${Math.abs(n[0])} mm más de lo normal`;
  if (n.length < 2) return r;
  const [a, b] = n;
  if (b <= 0) return a === -30 && b === 0 ? "hasta 30 mm menos de lo normal (casi normal)" : `entre ${Math.abs(b)} y ${Math.abs(a)} mm menos de lo normal`;
  if (a === 0) return `hasta ${b} mm más de lo normal (casi normal)`;
  return `entre ${a} y ${b} mm más de lo normal`;
}

export default {
  id: "fen",
  grupo: "El Niño",
  label: "Eventos El Niño pasados",
  Icon: History,
  defaultVisible: false,
  opciones: { etiqueta: "Evento", valores: EVENTOS, defecto: "1997-1998" },
  legend: CLASES.map(({ color, label }) => ({ color, label, zona: true })),
  fuente:
    "Lluvia de un trimestre del evento frente a lo normal (el primero que publica SENAMHI: su verano, cuando más llueve). SENAMHI (IDESEP).",
  load: getMapaFEN,
  render(group, mapa, { opcion, map }) {
    if (!mapa?.geojson) return "No hay mapa para ese evento.";
    const ev = EVENTOS.find((e) => e.valor === opcion);
    const evento = ev?.etiqueta ?? mapa.titulo;
    L.geoJSON(mapa.geojson, {
      pane: "areas",
      attribution: FUENTE_SENAMHI,
      renderer: renderer(map), // miles de polígonos: canvas es mucho más liviano que SVG
      style: (f) => {
        const c = clase(f.properties?.RANGO);
        return { stroke: false, fillColor: c?.color ?? "#9CA3AF", fillOpacity: c?.hasta === 30 ? 0.25 : 0.6 };
      },
      onEachFeature: (f, capa) =>
        capa.bindPopup(
          popupHtml({
            title: evento,
            resumen: ev
              ? `Entre ${ev.meses} aquí llovió ${frase(f.properties?.RANGO)}.`
              : `Aquí llovió ${frase(f.properties?.RANGO)}.`,
            nota: "Fuente: SENAMHI (IDESEP).",
          })
        ),
    }).addTo(group);
    return `${evento}: dónde llovió más (azul) o menos (marrón) que lo normal en esos meses. Cada evento fue distinto.`;
  },
};
