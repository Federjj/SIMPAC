import { useEffect, useRef } from "react";
import L from "leaflet";
import { createBaseMap } from "@/map/baseMap";
import { SVG } from "@/map/markers";

// Anfitrión del mapa: crea el mapa base y un L.layerGroup por capa. Cada capa se
// carga la primera vez que se enciende, cada refreshMs mientras siga encendida, al
// volver a encenderla si sus datos ya pasaron de refreshMs y cuando cambia su opción
// (p. ej. el evento FEN elegido); si una carga falla se reintenta a los 5 s, 15 s y
// 60 s. Lo que dibuja cada capa vive en src/map/layers/. Si render() devuelve un texto,
// es su nota (p. ej. "dato de las 10:30") y se avisa con onNota.
const REINTENTOS_MS = [5_000, 15_000, 60_000];

export default function MapView({ layers, visible, opciones = {}, focus, userPos, onNota }) {
  const elRef = useRef(null);
  const ctxRef = useRef(null);
  const userMkRef = useRef(null);
  const onNotaRef = useRef(onNota);
  onNotaRef.current = onNota;

  // init (una vez)
  useEffect(() => {
    const base = createBaseMap(elRef.current, { center: [-7.16, -78.51], zoom: 13 });
    // las áreas sombreadas van debajo de los círculos y marcadores
    base.map.createPane("areas").style.zIndex = 350;
    const ctx = {
      map: base.map,
      groups: Object.fromEntries(layers.map((l) => [l.id, L.layerGroup()])),
      cargadas: new Set(),
      ultimaCarga: {},
      opcionCargada: {},
      turno: {},
      timers: {},
      opciones: {},
      vivo: true,
      nota: (id, texto) => onNotaRef.current?.(id, texto),
    };
    ctxRef.current = ctx;
    return () => {
      ctx.vivo = false;
      Object.values(ctx.timers).forEach(clearInterval);
      base.dispose();
      ctxRef.current = null;
    };
  }, []); // las capas son constantes (map/layers/index.js)

  // enciende / apaga capas; la primera vez que se encienden (o si cambió su opción), las carga
  useEffect(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    ctx.opciones = opciones;
    for (const layer of layers) {
      const group = ctx.groups[layer.id];
      const on = Boolean(visible[layer.id]);
      const vieja = layer.refreshMs && Date.now() - (ctx.ultimaCarga[layer.id] ?? 0) > layer.refreshMs;
      const otraOpcion = ctx.opcionCargada[layer.id] !== opciones[layer.id];
      if (on && (!ctx.cargadas.has(layer.id) || vieja || otraOpcion)) {
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
  }, [visible, opciones]);

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
  const opcion = ctx.opciones[layer.id];
  const turno = (ctx.turno[layer.id] ?? 0) + 1; // solo la carga más reciente dibuja
  ctx.turno[layer.id] = turno;
  ctx.ultimaCarga[layer.id] = Date.now(); // al pedir: un toggle con la carga en vuelo no la repite
  if (layer.id in ctx.opcionCargada && ctx.opcionCargada[layer.id] !== opcion) {
    // otra opción (p. ej. otro evento FEN): no dejar a la vista lo de la anterior mientras carga
    group.clearLayers();
    ctx.nota(layer.id, "Cargando…");
  }
  ctx.opcionCargada[layer.id] = opcion;
  layer
    .load(opcion)
    .then((datos) => {
      if (!ctx.vivo || ctx.turno[layer.id] !== turno) return; // desmontado, o llegó una carga más nueva
      group.clearLayers();
      const avisar = (texto) => ctx.vivo && ctx.turno[layer.id] === turno && ctx.nota(layer.id, texto);
      const nota = layer.render(group, datos, { opcion, map: ctx.map, avisar });
      ctx.nota(layer.id, typeof nota === "string" ? nota : null);
    })
    .catch((err) => {
      console.error(`capa ${layer.id}`, err);
      if (ctx.turno[layer.id] !== turno) return;
      const espera = REINTENTOS_MS[intento];
      if (espera == null) {
        ctx.cargadas.delete(layer.id); // agotados los reintentos: se vuelve a probar al encenderla
        ctx.nota(layer.id, "No se pudo cargar: se reintentará al volver a encenderla.");
        return;
      }
      setTimeout(() => {
        if (!ctx.vivo || ctx.turno[layer.id] !== turno) return; // ya hubo una carga más nueva
        if (ctx.map.hasLayer(group)) cargar(ctx, layer, intento + 1);
        else ctx.cargadas.delete(layer.id); // apagada: se vuelve a cargar al encenderla
      }, espera);
    });
}
