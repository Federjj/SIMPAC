import { useEffect, useRef } from "react";
import L from "leaflet";
import { createBaseMap } from "@/map/baseMap";
import { SVG } from "@/map/markers";

// Anfitrión del mapa: crea el mapa base y un L.layerGroup por capa. Cada capa se
// carga la primera vez que se enciende, cada refreshMs mientras siga encendida y al
// volver a encenderla si sus datos ya pasaron de refreshMs; si una carga falla se
// reintenta a los 5 s, 15 s y 60 s. Lo que dibuja cada capa vive en src/map/layers/.
const REINTENTOS_MS = [5_000, 15_000, 60_000];
export default function MapView({ layers, visible, focus, userPos }) {
  const elRef = useRef(null);
  const ctxRef = useRef(null);
  const userMkRef = useRef(null);

  // init (una vez)
  useEffect(() => {
    const base = createBaseMap(elRef.current, { center: [-7.16, -78.51], zoom: 13 });
    const ctx = {
      map: base.map,
      groups: Object.fromEntries(layers.map((l) => [l.id, L.layerGroup()])),
      cargadas: new Set(),
      ultimaCarga: {},
      timers: {},
      vivo: true,
    };
    ctxRef.current = ctx;
    return () => {
      ctx.vivo = false;
      Object.values(ctx.timers).forEach(clearInterval);
      base.dispose();
      ctxRef.current = null;
    };
  }, []); // las capas son constantes (map/layers/index.js)

  // enciende / apaga capas; la primera vez que se encienden, las carga
  useEffect(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    for (const layer of layers) {
      const group = ctx.groups[layer.id];
      const on = Boolean(visible[layer.id]);
      const vieja = layer.refreshMs && Date.now() - (ctx.ultimaCarga[layer.id] ?? 0) > layer.refreshMs;
      if (on && (!ctx.cargadas.has(layer.id) || vieja)) {
        ctx.cargadas.add(layer.id);
        cargar(ctx, layer);
        if (layer.refreshMs && !ctx.timers[layer.id]) {
          ctx.timers[layer.id] = setInterval(
            () => ctx.map.hasLayer(group) && cargar(ctx, layer),
            layer.refreshMs
          );
        }
      }
      if (on && !ctx.map.hasLayer(group)) group.addTo(ctx.map);
      if (!on && ctx.map.hasLayer(group)) ctx.map.removeLayer(group);
    }
  }, [visible]);

  // recentra el mapa cuando cambia la ciudad / ubicación
  useEffect(() => {
    const map = ctxRef.current?.map;
    if (map && focus) map.setView([focus.lat, focus.lon], focus.zoom ?? map.getZoom());
  }, [focus]);

  // marcador de "tu ubicación"
  useEffect(() => {
    const map = ctxRef.current?.map;
    if (!map) return;
    if (userMkRef.current) {
      map.removeLayer(userMkRef.current);
      userMkRef.current = null;
    }
    if (userPos) {
      userMkRef.current = L.marker(userPos, {
        icon: L.divIcon({
          className: "",
          html: `<div class="mkself">${SVG.nav}</div>`,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        }),
        zIndexOffset: 1000,
      })
        .addTo(map)
        .bindPopup("Tu ubicación");
    }
  }, [userPos]);

  return <div ref={elRef} className="absolute inset-0" />;
}

function cargar(ctx, layer, intento = 0) {
  const group = ctx.groups[layer.id];
  ctx.ultimaCarga[layer.id] = Date.now(); // al pedir: un toggle con la carga en vuelo no la repite
  layer
    .load()
    .then((datos) => {
      if (!ctx.vivo) return; // el mapa se desmontó mientras llegaban los datos
      group.clearLayers();
      layer.render(group, datos);
    })
    .catch((err) => {
      console.error(`capa ${layer.id}`, err);
      const espera = REINTENTOS_MS[intento];
      if (espera == null) {
        ctx.cargadas.delete(layer.id); // agotados los reintentos: se vuelve a probar al encenderla
        return;
      }
      setTimeout(() => {
        if (ctx.vivo && ctx.map.hasLayer(group)) cargar(ctx, layer, intento + 1);
        else ctx.cargadas.delete(layer.id);
      }, espera);
    });
}
