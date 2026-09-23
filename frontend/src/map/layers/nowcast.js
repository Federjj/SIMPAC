import L from "leaflet";
import { Radar } from "lucide-react";
import { getNowcast, getNowcastEstado, getPronosticoVigente } from "@/lib/queries";
import { diaMesCorto, fechaPeru, hhmmPeru, horaPeru, textoHace } from "@/lib/tiempo";
import { haversineKm } from "@/lib/geo";
import { opcionesPopup, popupNowcast } from "../popups";
import { NOWCAST_HEX } from "../palette";
import { FUENTE_SENAMHI } from "../senamhi";

// Nowcasting de lluvia de SENAMHI (vistas nowcast_estado y nowcast_vigente, tarea 'nowcast' del
// worker): manchas de ~2 km donde SENAMHI estima lluvia moderada, fuerte o extrema en la próxima
// hora, en 2 horas o ahora. EXPERIMENTAL ("referencial y aún en etapa de calibración"): azules y
// violeta con borde punteado para no confundirlo con los avisos, y sin rayos (el algoritmo no los
// mide). Si SENAMHI deja de publicar, las vistas dejan de entregar manchas a los 30 min (el umbral
// vive en la base: aquí se usan `vigente` y `vence_en`) y la capa lo dice.
export const URL_VISOR = "https://www.senamhi.gob.pe/mapas/mapa-nowcasting/nowcasting-pronostico-1h.php";

const NIVELES = {
  1: { nombre: "moderada", label: "Lluvia moderada" },
  2: { nombre: "fuerte", label: "Lluvia fuerte" },
  3: { nombre: "extrema", label: "Lluvia extrema (el nivel más alto de SENAMHI)" },
};
const OPACIDAD = { 1: 0.5, 2: 0.55, 3: 0.6 };
const CUANDO = {
  60: { largo: "en la próxima hora", chip: "en la próxima hora" },
  120: { largo: "en 2 horas", chip: "en 2 horas" },
  0: { largo: "ahora (estimación)", chip: "ahora" },
};

// Vencimiento de las manchas a la vista (uno solo: se limpia en cada dibujo).
let vence = null;

// "de las 20:40" (hoy) o "del mar 22 set a las 20:40"
const deLas = (t) =>
  fechaPeru(t) === fechaPeru() ? `de las ${hhmmPeru(t)}` : `del ${diaMesCorto(fechaPeru(t))} a las ${hhmmPeru(t)}`;
// El análisis (horizonte 0, "ahora") vale para un instante: SENAMHI da valido_desde = valido_hasta.
const esInstante = (x) => Date.parse(x.valido_desde) >= Date.parse(x.valido_hasta);
// "a las 13:10" (análisis) o "entre las 13:10 y las 14:10"
const lapso = (x) =>
  esInstante(x)
    ? `a las ${hhmmPeru(x.valido_desde)}`
    : `entre las ${hhmmPeru(x.valido_desde)} y las ${hhmmPeru(x.valido_hasta)}`;

// La nota de la capa y el texto corto del chip: {texto, corto, estado: fresco | vacio | viejo | error}.
function notaVieja(e, ahora = Date.now()) {
  return {
    estado: "viejo",
    texto: `No hay un nowcasting de SENAMHI reciente: el último es ${deLas(e.emision)} (${textoHace(ahora - Date.parse(e.emision))}). No mostramos manchas viejas.`,
    corto: `Sin nowcasting reciente de SENAMHI (último ${horaPeru(e.emision)})`,
  };
}
const NOTA_ERROR = {
  estado: "error",
  texto: "No se pudo consultar el nowcasting de SENAMHI.",
  corto: "No se pudo consultar el nowcasting",
};
export function notaNowcast(e, manchas, h, ahora = Date.now()) {
  if (!e) return NOTA_ERROR;
  if (!e.vigente || Date.parse(e.vence_en) <= ahora) return notaVieja(e, ahora);
  if (!manchas) return NOTA_ERROR; // falló la consulta de las manchas: no decir "sin lluvia"
  const emitido = hhmmPeru(e.emision);
  if (!manchas.length)
    return {
      estado: "vacio",
      texto: `SENAMHI no estima lluvia moderada o más fuerte en el Perú ${lapso(e)}. Puede haber lluvia ligera.`,
      corto: `Sin lluvia moderada o más fuerte · SENAMHI ${emitido}`,
    };
  const hace = textoHace(ahora - Date.parse(e.emision));
  return {
    estado: "fresco",
    texto: esInstante(e)
      ? `Experimental. Estimación de SENAMHI de las ${emitido} (${hace}). Se renueva cada 10 min.`
      : `Experimental. Estimación de SENAMHI de las ${emitido} (${hace}), válida hasta las ${hhmmPeru(e.valido_hasta)}. Se renueva cada 10 min.`,
    corto: `Lluvia ${CUANDO[h]?.chip ?? "en la próxima hora"} · SENAMHI ${emitido}`,
  };
}

// "Sobre Jaén" (a menos de 5 km), "A unos 15 km de Jaén (Cajamarca)" (hasta 40 km) o nada.
function cercaDe(latlng, localidades) {
  let mejor = null;
  for (const f of localidades) {
    if (f.lat == null || f.lon == null) continue;
    const km = haversineKm(latlng.lat, latlng.lng, f.lat, f.lon);
    if (!mejor || km < mejor.km) mejor = { km, f };
  }
  if (!mejor || mejor.km > 40) return null;
  if (mejor.km < 5) return `Sobre ${mejor.f.nombre}`;
  const km = Math.max(5, Math.round(mejor.km / 5) * 5);
  return `A unos ${km} km de ${mejor.f.nombre}${mejor.f.departamento ? ` (${mejor.f.departamento})` : ""}`;
}

export default {
  id: "nowcast",
  grupo: "Pronóstico",
  label: "Lluvia en las próximas 2 horas",
  Icon: Radar,
  insignia: "Experimental",
  defaultVisible: false,
  refreshMs: 2 * 60_000,
  opciones: {
    etiqueta: "Cuándo",
    valores: [
      { valor: "60", etiqueta: "En la próxima hora" },
      { valor: "120", etiqueta: "En 2 horas" },
      { valor: "0", etiqueta: "Ahora (estimación)" },
    ],
    defecto: "60",
  },
  legend: [1, 2, 3].map((n) => ({ forma: "mancha", color: NOWCAST_HEX[n], label: NIVELES[n].label })),
  fuente:
    "Nowcasting de SENAMHI: estimación automática con satélite, «referencial y aún en etapa de calibración». " +
    "No es un aviso. SIMPAC usa azules para no confundirlo con los avisos. Si SENAMHI no publica hace más de 30 min, " +
    "no se muestra.",
  // las localidades del pronóstico sirven para decir "cerca de" en el popup. Un error de la base
  // no rechaza la carga: la capa dice enseguida "No se pudo consultar" (MapView reintentaría en
  // silencio) y vuelve a probar en la próxima recarga (refreshMs)
  load: (opcion) =>
    Promise.all([
      getNowcastEstado().catch(() => null),
      getNowcast(Number(opcion ?? 60)).catch(() => null),
      getPronosticoVigente().catch(() => []),
    ]),
  render(group, [estados, manchas, localidades], { opcion, map, avisar }) {
    clearTimeout(vence);
    vence = null;
    const h = Number(opcion ?? 60);
    const e = estados?.find((x) => x.horizonte_min === h) ?? null;
    const lista = manchas ?? [];
    const nota = notaNowcast(e, manchas, h);
    if (nota.estado !== "fresco" && nota.estado !== "vacio") return nota;
    for (const nivel of [1, 2, 3]) {
      const c = NOWCAST_HEX[nivel];
      for (const m of lista.filter((x) => x.nivel === nivel && x.geojson)) {
        L.geoJSON(m.geojson, {
          pane: "nowcast",
          attribution: FUENTE_SENAMHI,
          style: { color: c, weight: 1.5, dashArray: "4 3", fillColor: c, fillOpacity: OPACIDAD[nivel] },
        })
          .on("click", (ev) => {
            const cerca = cercaDe(ev.latlng, localidades ?? []);
            const cuando = lapso(m);
            L.popup(opcionesPopup(map))
              .setLatLng(ev.latlng)
              .setContent(
                popupNowcast({
                  titulo: `Lluvia ${NIVELES[nivel].nombre} ${CUANDO[h]?.largo ?? ""}`.trim(),
                  cuando: cerca ? `${cerca}, ${cuando}.` : `${cuando[0].toUpperCase()}${cuando.slice(1)}.`,
                  emitido: `Emitido ${hhmmPeru(m.emision)} (${textoHace(Date.now() - Date.parse(m.emision))})`,
                  color: c,
                  url: URL_VISOR,
                })
              )
              .openOn(map);
          })
          .addTo(group);
      }
    }
    // al vencer (30 min después de la emisión) se borran las manchas aunque no haya recarga
    const espera = Date.parse(e.vence_en) - Date.now();
    vence = setTimeout(() => {
      group.clearLayers();
      avisar(notaVieja(e));
    }, Math.max(0, espera));
    return nota;
  },
};
