import L from "leaflet";
import { lineaCorta } from "./atribucion";
import { escapeHtml } from "./markers";
import { ajustePopup } from "./popups";

// Mapa base: tiles Stadia Alidade Smooth (claro y limpio, con detalle de calles).
// Gratis en localhost sin llave. En un dominio real Stadia pide identificarse: o se autoriza el
// dominio en su panel (recomendado para el navegador: no hay llave en el código; manda el Origin
// y el Referer) o se pasa una API key gratuita con ?api_key=... Si VITE_STADIA_API_KEY está
// definida (frontend/.env.example), va detrás de {r}.png; Leaflet reemplaza {z}{x}{y}{r} igual.
const KEY_STADIA = import.meta.env.VITE_STADIA_API_KEY;
const TILES =
  "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png" +
  (KEY_STADIA ? `?api_key=${encodeURIComponent(KEY_STADIA)}` : "");
const ATRIBUCION =
  '© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const PANTALLA_CORTA = "(max-width: 1023px)"; // más angosto que lg: la hoja va abajo

// Al abrirse, un popup mueve el mapa para no quedar bajo los chips de arriba a la izquierda
// (marca, ciudad, El Niño) ni bajo los botones de la derecha.
L.Popup.mergeOptions({ autoPanPaddingTopLeft: L.point(16, 150), autoPanPaddingBottomRight: L.point(64, 16) });

// En el celular cada popup, al abrirse, toma el alto máximo y el relleno del autoPan que dejan
// libres la hoja de abajo y la atribución en ese momento (map/popups.js ajustePopup): las opciones
// que se fijaron en bindPopup se calcularon cuando la hoja medía otra cosa (o con un 45 % fijo), y
// el popup quedaba debajo de la hoja o con el título fuera de la pantalla. Desde lg, las de siempre.
const abrirPopup = L.Popup.prototype.onAdd;
L.Popup.include({
  onAdd(map) {
    if (window.matchMedia(PANTALLA_CORTA).matches) Object.assign(this.options, ajustePopup(map));
    return abrirPopup.call(this, map);
  },
});

// Atribución: en escritorio el texto completo de siempre; en el celular una línea corta
// ("© Stadia Maps · OpenMapTiles · OSM · Datos: SENAMHI, ANA · más") que al tocar "más" despliega
// el texto completo con sus enlaces ("menos" lo pliega). La de Leaflet crecía a 2 o 3 líneas de
// ancho completo (34 a 50 px) en plena mitad de la pantalla al subir sobre la hoja: tapaba
// marcadores y rótulos e interceptaba los toques (un toque al mapa abría openstreetmap.org).
const Atribucion = L.Control.Attribution.extend({
  onAdd(map) {
    const c = L.Control.Attribution.prototype.onAdd.call(this, map);
    this._corta = window.matchMedia(PANTALLA_CORTA);
    this._alCambiar = () => this._update();
    this._corta.addEventListener("change", this._alCambiar);
    L.DomEvent.on(c, "click", (e) => {
      if (!e.target.closest?.(".atrib-mas")) return;
      L.DomEvent.stop(e);
      this._abierta = !this._abierta;
      this._update();
    });
    return c;
  },
  onRemove(map) {
    this._corta?.removeEventListener("change", this._alCambiar);
    L.Control.Attribution.prototype.onRemove.call(this, map);
  },
  _update() {
    if (!this._map) return;
    const textos = Object.keys(this._attributions).filter((k) => this._attributions[k]);
    const completo = [this.options.prefix, textos.join(", ")].filter(Boolean).join(' <span aria-hidden="true">|</span> ');
    const corta = Boolean(this._corta?.matches);
    const plegada = corta && !this._abierta;
    this._container.classList.toggle("atrib-corta", plegada);
    if (!corta) {
      this._container.innerHTML = completo;
      return;
    }
    this._container.innerHTML = plegada
      ? `<span>${escapeHtml(lineaCorta(textos))}</span> <button type="button" class="atrib-mas" aria-expanded="false">más</button>`
      : `${completo} <button type="button" class="atrib-mas" aria-expanded="true">menos</button>`;
  },
});

export function createBaseMap(el, { center, zoom }) {
  const map = L.map(el, { zoomControl: false, attributionControl: false }).setView(center, zoom);
  // la atribución antes que el zoom: en la esquina de abajo Leaflet apila hacia arriba, así queda
  // la atribución en el borde y el zoom encima de ella
  new Atribucion({ position: "bottomright" }).addTo(map);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  // Desde el Perú cada tile tarda 0,7 a 1 s en llegar: se piden menos durante la animación del
  // zoom (updateWhenZooming: false; al terminar se piden los de la vista nueva) y se guardan 3
  // anillos de tiles alrededor de la vista (keepBuffer) para que un arrastre corto no vuelva a
  // pedir. En celular Leaflet ya espera a que termine el arrastre (updateWhenIdle).
  L.tileLayer(TILES, { maxZoom: 20, attribution: ATRIBUCION, updateWhenZooming: false, keepBuffer: 3 }).addTo(map);

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
