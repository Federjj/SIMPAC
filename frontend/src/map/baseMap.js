import L from "leaflet";

// Mapa base: tiles Stadia Alidade Smooth (claro y limpio, con detalle de calles).
// Gratis en localhost; al desplegar a un dominio real requiere una API key
// gratuita de Stadia (?api_key=...).
const TILES = "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png";
const ATRIBUCION =
  '© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

// Al abrirse, un popup mueve el mapa para no quedar bajo los chips de arriba a la izquierda
// (marca, ciudad, El Niño) ni bajo los botones de la derecha.
L.Popup.mergeOptions({ autoPanPaddingTopLeft: L.point(16, 150), autoPanPaddingBottomRight: L.point(64, 16) });

export function createBaseMap(el, { center, zoom }) {
  const map = L.map(el, { zoomControl: false }).setView(center, zoom);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer(TILES, { maxZoom: 20, attribution: ATRIBUCION }).addTo(map);

  // Recalcula el tamaño cuando el contenedor cambia o pasa de oculto a visible
  // (evita el mapa "gris" al montarse en un panel sin tamaño).
  const t = setTimeout(() => map.invalidateSize(), 300);
  const ro = new ResizeObserver(() => map.invalidateSize());
  ro.observe(el);

  return {
    map,
    dispose() {
      clearTimeout(t);
      ro.disconnect();
      map.remove();
    },
  };
}
