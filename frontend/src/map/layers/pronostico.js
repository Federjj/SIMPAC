import L from "leaflet";
import { CloudSun } from "lucide-react";
import { getPronosticoVigente } from "@/lib/queries";
import { fechaPeru } from "@/lib/tiempo";
import { aspecto, fechaDeOpcion, notaPronostico, temps } from "@/lib/pronostico";
import { iconoLocalidad } from "../marcadores";
import { escapeHtml } from "../markers";
import { opcionesPopup, popupLocalidad } from "../popups";
import { FUENTE_SENAMHI } from "../senamhi";
import { OPCIONES_DIA } from "./avisos";

// Pronóstico oficial de SENAMHI por localidad (vista pronostico_vigente, tarea 'pronostico' del
// worker): un disco blanco por localidad con el glifo del tiempo del día elegido (el mismo día que
// los avisos). Es un PUNTO: vale para esa localidad, no para el distrito. Sin fila no hay disco:
// nunca se pinta "sin lluvia" donde SENAMHI no publica. Los discos que chocan quedan como punto
// de color y los nombres se muestran según la escala (map/acomodo.js).
export default {
  id: "pronostico",
  grupo: "Pronóstico",
  label: "Pronóstico por localidad (SENAMHI)",
  Icon: CloudSun,
  insignia: "Oficial",
  defaultVisible: true,
  refreshMs: 30 * 60_000,
  opciones: OPCIONES_DIA,
  legend: [
    { forma: "disco", glifo: "lluvia", label: "Lluvia" },
    { forma: "disco", glifo: "tendencia", punteado: true, label: "Puede llover (SENAMHI: «tendencia a»)" },
    { forma: "disco", glifo: "tormenta", label: "Tormenta" },
    { forma: "disco", glifo: "nieve", label: "Nieve o granizo" },
    { forma: "disco", glifo: "sol_nube", label: "Sin lluvia" },
  ],
  fuente:
    "Pronóstico oficial de SENAMHI para cada localidad (hoy, mañana y pasado), no para toda la zona. Donde no hay " +
    "ícono, SENAMHI no publica pronóstico: no quiere decir que no llueva. Ícono y resumen de SIMPAC.",
  load: getPronosticoVigente,
  render(group, filas, { opcion, map, acomodo }) {
    // null: la vista aún no existe en la base (falta la migración)
    if (filas == null) return "No se pudo cargar: el pronóstico por localidad aún no está disponible.";
    const hoy = fechaPeru();
    const fecha = fechaDeOpcion(opcion);
    const porCodigo = new Map();
    for (const f of filas) porCodigo.set(f.codigo, [...(porCodigo.get(f.codigo) ?? []), f]);
    for (const f of filas) {
      if (f.fecha !== fecha || f.lat == null || f.lon == null) continue;
      const a = aspecto(f);
      const t = temps(f);
      const tooltip = `${f.nombre}: ${a.corto} · ${t}`;
      const m = L.marker([f.lat, f.lon], {
        icon: iconoLocalidad({ glifo: a.glifo, clase: a.clase, tono: a.tono, posible: a.posible, nombre: f.nombre, temps: t }),
        keyboard: true,
        zIndexOffset: a.prioridad,
        attribution: FUENTE_SENAMHI,
      })
        // Leaflet inserta el tooltip como HTML y el nombre viene de la página de SENAMHI
        .bindTooltip(escapeHtml(tooltip), { className: "tip", direction: "top", offset: [0, -20] })
        .bindPopup(() => popupLocalidad(f, porCodigo.get(f.codigo), { hoy }), opcionesPopup(map))
        .on("add", (e) => e.target.getElement()?.setAttribute("aria-label", tooltip))
        .addTo(group);
      acomodo?.registrar(m, {
        tipo: "disco",
        prioridad: a.prioridad,
        codigo: f.codigo,
        departamento: f.departamento,
        clase: a.clase,
        rotulo: `${f.nombre} ${t}`,
        zIndex: a.prioridad,
      });
    }
    return notaPronostico(filas, fecha, hoy);
  },
};
