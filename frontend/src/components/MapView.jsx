import { useEffect, useRef } from "react";
import L from "leaflet";
import { createBaseMap } from "@/map/baseMap";
import { SVG } from "@/map/markers";
import { crearAcomodo, escalaDeZoom } from "@/map/acomodo";

// Anfitrión del mapa: crea el mapa base y un L.layerGroup por capa. Cada capa se
// carga la primera vez que se enciende, cada refreshMs mientras siga encendida, al
// volver a encenderla si sus datos ya pasaron de refreshMs y cuando cambia su opción
// (p. ej. el evento FEN elegido); si una carga falla se reintenta a los 5 s, 15 s y
// 60 s. Lo que dibuja cada capa vive en src/map/layers/. Si render() devuelve un texto
// (o un objeto {texto, ...}), es su nota (p. ej. "dato de las 10:30") y se avisa con onNota.
// Las insignias de los avisos y los discos del pronóstico los acomoda map/acomodo.js: cada capa
// recibe `acomodo` (su registro) en render, y localidadUsuario marca tu localidad.
const REINTENTOS_MS = [5_000, 15_000, 60_000];

// Panes de las áreas: el relleno de los avisos va en uno por nivel, con la transparencia en el
// pane (dos amarillos superpuestos no se oscurecen); los bordes encima; el nowcasting más arriba.
const PANES = [
  ["areas", 350], // eventos El Niño pasados
  ["aviso2", 350, 0.3],
  ["aviso3", 351, 0.4],
  ["aviso4", 352, 0.4],
  ["avisoBorde", 353],
  ["nowcast", 380],
];

export default function MapView({ layers, visible, opciones = {}, focus, userPos, onNota, localidadUsuario }) {
  const elRef = useRef(null);
  const ctxRef = useRef(null);
  const userMkRef = useRef(null);
  const onNotaRef = useRef(onNota);
  onNotaRef.current = onNota;

  // init (una vez)
  useEffect(() => {
    const base = createBaseMap(elRef.current, { center: [-7.16, -78.51], zoom: 13 });
    const map = base.map;
    for (const [nombre, z, opacidad] of PANES) {
      const pane = map.createPane(nombre);
      pane.style.zIndex = z;
      if (opacidad != null) pane.style.opacity = opacidad;
    }
    // tamaño de insignias y discos por zoom (index.css: [data-escala])
    const escala = () => (map.getContainer().dataset.escala = escalaDeZoom(map.getZoom()));
    escala();
    map.on("zoomend", escala);
    // un <details> que se abre o se cierra dentro de un popup cambia su alto; y con un popup
    // abierto, en pantallas angostas los chips de arriba se apartan (index.css: html[data-popup])
    map.on("popupopen", ({ popup }) => {
      document.documentElement.dataset.popup = "";
      popup
        .getElement()
        ?.querySelectorAll("details")
        .forEach((d) => d.addEventListener("toggle", () => popup.update()));
    });
    map.on("popupclose", () => delete document.documentElement.dataset.popup);
    const ctx = {
      map,
      groups: Object.fromEntries(layers.map((l) => [l.id, L.layerGroup()])),
      acomodo: crearAcomodo(map),
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
      ctx.acomodo.destruir();
      delete document.documentElement.dataset.popup;
      base.dispose();
      ctxRef.current = null;
    };
  }, []); // las capas son constantes (map/layers/index.js)

  // tu localidad: su disco lleva aro negro y su nombre siempre se ve
  useEffect(() => {
    ctxRef.current?.acomodo.usuario(localidadUsuario ?? null);
  }, [localidadUsuario]);

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
  const acomodo = ctx.acomodo.capa(layer.id);
  if (layer.id in ctx.opcionCargada && ctx.opcionCargada[layer.id] !== opcion) {
    // otra opción (p. ej. otro evento FEN): no dejar a la vista lo de la anterior mientras carga
    acomodo.limpiar();
    group.clearLayers();
    ctx.nota(layer.id, "Cargando…");
  }
  ctx.opcionCargada[layer.id] = opcion;
  layer
    .load(opcion)
    .then((datos) => {
      if (!ctx.vivo || ctx.turno[layer.id] !== turno) return; // desmontado, o llegó una carga más nueva
      acomodo.limpiar();
      group.clearLayers();
      const avisar = (texto) => ctx.vivo && ctx.turno[layer.id] === turno && ctx.nota(layer.id, texto);
      const nota = layer.render(group, datos, { opcion, map: ctx.map, avisar, acomodo });
      ctx.nota(layer.id, typeof nota === "string" || (nota && typeof nota === "object") ? nota : null);
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
