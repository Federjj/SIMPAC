import L from "leaflet";
import { Satellite } from "lucide-react";
import { horaPeru, horasDesde } from "@/lib/tiempo";

// Lluvia estimada por satélite en todo el Perú: NASA GPM IMERG (Early, pasos de 30 min),
// servida como imágenes por NASA GIBS, gratis y sin llave. Llega con unas 5-6 h de
// retraso: dice dónde llovió hace unas horas, no dónde llueve ahora. Celdas de ~11 km.
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/IMERG_Precipitation_Rate_30min/default";
const MATRIZ = "GoogleMapsCompatible_Level6";

const PERU = "5/16/9"; // una celda (z/y/x) sobre el Perú
const existe = (tiempo) =>
  fetch(`${GIBS}/${tiempo}/${MATRIZ}/${PERU}.png`, { method: "HEAD" }).then((r) => r.ok, () => false);

// La hora del dato más reciente viene en la cabecera Layer-Time-Actual (GIBS la expone por
// CORS). Pero "default" a veces anuncia un paso que todavía no publicó (404 al pedirlo con su
// hora): se confirma y, si falta, se retrocede de a 30 min. Sin hora, se usa "default".
async function horaDisponible() {
  const r = await fetch(`${GIBS}/default/${MATRIZ}/${PERU}.png`, { method: "HEAD" });
  if (!r.ok) throw new Error(`GIBS respondió ${r.status}`);
  const anunciada = Date.parse(r.headers.get("Layer-Time-Actual") ?? "");
  for (let i = 0; Number.isFinite(anunciada) && i < 6; i++) {
    const hora = new Date(anunciada - i * 30 * 60_000).toISOString().replace(".000Z", "Z");
    if (await existe(hora)) return hora;
  }
  return null;
}

export default {
  id: "satelite",
  grupo: "Lluvia",
  label: "Lluvia por satélite (NASA)",
  Icon: Satellite,
  defaultVisible: false,
  refreshMs: 30 * 60_000,
  // colores de la paleta de GIBS (GPM_Precipitation_Rate): verde a rojo oscuro es lluvia y
  // celeste a morado, nieve
  legend: [
    { color: "#45C000", label: "Menos de 1 mm por hora", zona: true },
    { color: "#FF980F", label: "1 a 5 mm por hora", zona: true },
    { color: "#FF0101", label: "5 a 20 mm por hora", zona: true },
    { color: "#710000", label: "Más de 20 mm por hora", zona: true },
    { color: "#6DB8E1", label: "Nieve (celeste a morado)", zona: true },
  ],
  fuente:
    "Estimación satelital NASA GPM IMERG (Early): en la sierra puede quedarse corta. Imágenes: NASA Global Imagery Browse Services (GIBS), parte de ESDIS.",
  load: horaDisponible,
  render(group, hora, { map }) {
    const tiempo = hora ?? "default";
    L.tileLayer(`${GIBS}/${tiempo}/${MATRIZ}/{z}/{y}/{x}.png`, {
      maxNativeZoom: 6, // más cerca, GIBS no tiene imágenes: se agrandan las de zoom 6
      maxZoom: 20,
      opacity: 0.7,
      zIndex: 6,
      attribution: "Lluvia: NASA GPM IMERG, imágenes NASA GIBS (ESDIS)",
    }).addTo(group);
    const lejos = map.getZoom() > 9 ? " Aleja el mapa para verla mejor (cada celda mide ~11 km)." : "";
    return hora
      ? `Dato de las ${horaPeru(hora)} (hace ${horasDesde(hora)} h): el satélite llega con horas de retraso.${lejos}`
      : `Dato más reciente disponible.${lejos}`;
  },
};
