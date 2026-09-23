import L from "leaflet";
import { Megaphone } from "lucide-react";
import { getAvisosVigentes } from "@/lib/queries";
import { fechaPeru, momentoPeru } from "@/lib/tiempo";
import { popupHtml } from "../markers";
import { FUENTE_SENAMHI } from "../senamhi";

// Avisos oficiales de SENAMHI como áreas sombreadas: los meteorológicos (lluvia, heladas,
// viento...) y el de lluvia acumulada en 24 h. Los trae el worker (tarea 'avisos') a la tabla
// aviso_senamhi; los polígonos van simplificados, así que se rotulan como "basado en el
// aviso de SENAMHI" y enlazan al aviso original (lo piden sus términos de uso).
const NIVELES = {
  2: { color: "#EBEB3B", nombre: "amarillo", label: "Amarillo (nivel 2 de 4)" },
  3: { color: "#F58E27", nombre: "naranja", label: "Naranja (nivel 3 de 4)" },
  4: { color: "#DB0404", nombre: "rojo", label: "Rojo (nivel 4 de 4, el más grave)" },
};

// Un aviso de varios días trae un mapa por día: se muestra un solo momento (ahora, o el
// mediodía de mañana o de pasado mañana) para no apilar los días uno encima de otro.
const CUANDO = {
  ahora: { dias: 0, texto: "vigentes ahora", vacio: "No hay avisos de SENAMHI vigentes ahora." },
  manana: { dias: 1, texto: "para mañana", vacio: "No hay avisos emitidos para mañana." },
  pasado: { dias: 2, texto: "para pasado mañana", vacio: "No hay avisos emitidos para pasado mañana." },
};
function instante(dias) {
  if (!dias) return Date.now();
  return Date.parse(`${fechaPeru(Date.now() + dias * 86_400_000)}T12:00:00-05:00`);
}

const TEMAS = { lluvia: "de lluvia", calor: "de calor", frio: "de frío", viento: "de viento", otro: "de otro tipo" };
// el backend guarda 'temperatura': el título dice si es por calor o por frío
const tema = (a) =>
  a.tema !== "temperatura" ? a.tema : /INCREMENTO|CALOR|ALTA/i.test(a.titulo ?? "") ? "calor" : "frio";

const oracion = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1).toLowerCase() : "");
const recortar = (t, n = 320) => (t && t.length > n ? `${t.slice(0, n).replace(/\s+\S*$/, "")}…` : t);

function titulo(a) {
  if (a.tipo === "lluvia24h") return "Aviso de lluvia para las próximas 24 h";
  return `Aviso N° ${a.numero}: ${oracion(a.titulo)}`;
}

export default {
  id: "avisos",
  grupo: "Alertas y avisos",
  label: "Avisos de SENAMHI (lluvia, calor, frío, viento)",
  Icon: Megaphone,
  defaultVisible: true,
  refreshMs: 15 * 60_000,
  opciones: {
    etiqueta: "Cuándo",
    valores: [
      { valor: "ahora", etiqueta: "Vigentes ahora" },
      { valor: "manana", etiqueta: "Mañana" },
      { valor: "pasado", etiqueta: "Pasado mañana" },
    ],
    defecto: "ahora",
  },
  legend: Object.values(NIVELES).map(({ color, label }) => ({ color, label, zona: true })),
  fuente: "Áreas basadas en los avisos oficiales de SENAMHI (simplificadas). Abre un área para ver el aviso original.",
  load: getAvisosVigentes,
  render(group, avisos, { opcion }) {
    const cuando = CUANDO[opcion] ?? CUANDO.ahora;
    const t = instante(cuando.dias);
    const lista = avisos.filter(
      (a) => a.geojson && NIVELES[a.nivel] && Date.parse(a.inicio) <= t && t < Date.parse(a.fin)
    );
    for (const a of lista) {
      const n = NIVELES[a.nivel];
      L.geoJSON(a.geojson, {
        pane: "areas",
        attribution: FUENTE_SENAMHI,
        style: { color: n.color, weight: 1.2, fillColor: n.color, fillOpacity: a.nivel >= 3 ? 0.4 : 0.3 },
      })
        .bindPopup(
          popupHtml({
            title: titulo(a),
            meta: [`Nivel ${n.nombre}`, a.departamentos?.length ? a.departamentos.join(", ") : null],
            resumen: `Rige desde ${momentoPeru(a.inicio)} hasta ${momentoPeru(a.fin)}.`,
            filas: [],
            nota: `${recortar(a.descripcion) ?? ""} Basado en el aviso de SENAMHI.`.trim(),
            enlace: a.url ? { href: a.url, texto: "Ver el aviso oficial" } : null,
          }),
          { maxWidth: 320 }
        )
        .addTo(group);
    }
    if (!lista.length) return cuando.vacio;
    // por tema: el rojo de la costa puede ser de temperatura y no de lluvia
    const partes = Object.entries(TEMAS).flatMap(([clave, texto]) => {
      const deTema = lista.filter((a) => tema(a) === clave);
      if (!deTema.length) return [];
      const n = new Set(deTema.map((a) => `${a.tipo}:${a.numero}`)).size;
      const peor = NIVELES[Math.max(...deTema.map((a) => a.nivel))].nombre;
      return [`${n} ${texto} (el más alto, ${peor})`];
    });
    const temas = partes.length > 1 ? `${partes.slice(0, -1).join(", ")} y ${partes[partes.length - 1]}` : partes[0];
    return `Avisos ${cuando.texto}: ${temas}. Toca un área para ver de qué trata.`;
  },
};
