import { useEffect, useRef } from "react";
import L from "leaflet";
import { getEstaciones, getCaudales } from "../lib/queries";

const C = {
  met: "#3BA5EB", hid: "#3B3BEB",
  normal: "#3BEB40", alerta: "#F58E27", emergencia: "#DB0404",
  primary: "#111111",
  inc: { inundacion: "#3B3BEB", lluvia: "#3BA5EB", huayco: "#F58E27", via: "#EB3B3B" },
};

const SVG = {
  station: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><circle cx="12" cy="10" r="3"/><path d="M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z"/></svg>',
  wave: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M3 12c3 3 5-2 9 0s5 2 9 0"/></svg>',
  inundacion: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M12 22a7 7 0 0 0 7-7c0-5-7-13-7-13S5 10 5 15a7 7 0 0 0 7 7z"/></svg>',
  lluvia: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M8 19v2m4-3v3m4-4v2M18 15a4 4 0 0 0-1-7.9A6 6 0 1 0 6 13"/></svg>',
  huayco: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M3 20h18L14 6l-4 7-3-3z"/></svg>',
  via: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M4 19 20 5M4 5l16 14"/></svg>',
  nav: '<svg viewBox="0 0 24 24" fill="#fff" stroke="#fff" stroke-width="1" stroke-linejoin="round"><path d="M3 11l19-9-9 19-2-8-8-2z"/></svg>',
};

function icon(color, svg, diamond) {
  return L.divIcon({
    className: "",
    html: `<div class="mk${diamond ? " diamond" : ""}" style="width:34px;height:34px;background:${color}">${svg}</div>`,
    iconSize: [34, 34], iconAnchor: [17, 17],
  });
}

// Color por anomalía de precipitación (%): seco (naranja/rojo) ↔ húmedo (celeste/azul).
function anomColor(a) {
  if (a <= -50) return "#DB0404";
  if (a <= -20) return "#F58E27";
  if (a < 20) return "#EBEB3B";
  if (a < 50) return "#3BA5EB";
  return "#3B3BEB";
}

export default function MapView({ visible, onReady, focus, userPos, anomGeo }) {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const groupsRef = useRef(null);
  const userMkRef = useRef(null);
  const visibleRef = useRef(visible);
  useEffect(() => { visibleRef.current = visible; }, [visible]);

  // init (una vez)
  useEffect(() => {
    const map = L.map(elRef.current, { zoomControl: false }).setView([-7.16, -78.51], 13);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    // Stadia Alidade Smooth: claro y limpio (tipo Positron) pero con detalle de
    // calles. Gratis en localhost; al desplegar a un dominio real requiere una
    // API key gratuita de Stadia (?api_key=...).
    L.tileLayer(
      "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 20,
        attribution:
          '© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }
    ).addTo(map);

    const g = {
      est: L.layerGroup(), rio: L.layerGroup(), inc: L.layerGroup(),
      zona: L.layerGroup(), anom: L.layerGroup(),
    };
    mapRef.current = map;
    groupsRef.current = g;
    if (onReady) onReady(map);

    // estaciones (reales)
    getEstaciones().then((rows) => {
      rows.forEach((e) => {
        if (e.lat == null) return;
        const col = e.tipo === "H" ? C.hid : C.met;
        L.marker([e.lat, e.lon], { icon: icon(col, SVG.station) })
          .bindPopup(`<div class="pop"><h4>${e.nombre}</h4><div class="meta">${e.tipo === "H" ? "Estación hidrológica" : "Estación meteorológica"} · ${e.estado}</div></div>`)
          .addTo(g.est);
      });
    }).catch((err) => console.error("estaciones", err));

    // ríos / caudal (reales) + zona si en alerta
    getCaudales().then((rows) => {
      rows.forEach((c) => {
        if (c.lat == null) return;
        const col = C[c.estado] || C.hid;
        L.marker([c.lat, c.lon], { icon: icon(col, SVG.wave) })
          .bindPopup(`<div class="pop"><h4>${c.estacion}</h4><div class="meta">Río ${c.rio} · ${c.estado}</div><p>Caudal: <b>${c.valor} ${c.unidad}</b></p></div>`)
          .addTo(g.rio);
        // Zona real: círculo solo alrededor de ríos en alerta/emergencia (dato ANA).
        if (c.estado === "alerta" || c.estado === "emergencia")
          L.circle([c.lat, c.lon], { radius: 2500, color: col, weight: 1, fillColor: col, fillOpacity: 0.18 }).addTo(g.zona);
      });
    }).catch((err) => console.error("caudales", err));

    // Los incidentes ciudadanos (g.inc) se llenaran con reportes reales de
    // Supabase (tabla `report`) cuando exista el flujo de creacion + login.

    const t = setTimeout(() => map.invalidateSize(), 300);
    // Recalcula el tamano cuando el contenedor pasa de oculto a visible
    // (evita el mapa "gris" al montarse en un panel/tab sin tamano).
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(elRef.current);

    return () => {
      clearTimeout(t);
      ro.disconnect();
      if (onReady) onReady(null);
      map.remove();
      mapRef.current = null;
      groupsRef.current = null;
    };
  }, []);

  // sincroniza visibilidad de capas
  useEffect(() => {
    const map = mapRef.current, g = groupsRef.current;
    if (!map || !g) return;
    Object.entries(visible).forEach(([k, on]) => {
      if (!g[k]) return;
      if (on && !map.hasLayer(g[k])) g[k].addTo(map);
      if (!on && map.hasLayer(g[k])) map.removeLayer(g[k]);
    });
  }, [visible]);

  // capa de anomalías de precipitación (datos reales de la tabla `mapa`)
  useEffect(() => {
    const map = mapRef.current, g = groupsRef.current;
    if (!map || !g) return;
    g.anom.clearLayers();
    const feats = anomGeo?.features || [];
    feats.forEach((f) => {
      const coords = f.geometry?.coordinates;
      if (!coords) return;
      const [lon, lat] = coords;
      const a = f.properties?.ANOMALIA ?? 0;
      const p = f.properties || {};
      L.circleMarker([lat, lon], {
        radius: 7, color: "#fff", weight: 1.5, fillColor: anomColor(a), fillOpacity: 0.85,
      })
        .bindPopup(`<div class="pop"><h4>${p.ESTACION || "Estación"}</h4><div class="meta">${p.DISTRITO || ""} · ${p.PROVINCIA || ""}</div><p>Anomalía de lluvia: <b>${a}%</b><br/>Precip ${p.PREC} mm (normal ${p.NORMAL} mm)</p></div>`)
        .addTo(g.anom);
    });
    if (visibleRef.current?.anom && !map.hasLayer(g.anom)) g.anom.addTo(map);
  }, [anomGeo]);

  // recentra el mapa cuando cambia la ciudad / ubicación
  useEffect(() => {
    const map = mapRef.current;
    if (map && focus) map.setView([focus.lat, focus.lon], focus.zoom ?? map.getZoom());
  }, [focus]);

  // marcador de "tu ubicación"
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (userMkRef.current) { map.removeLayer(userMkRef.current); userMkRef.current = null; }
    if (userPos) {
      userMkRef.current = L.marker(userPos, {
        icon: L.divIcon({ className: "", html: `<div class="mkself">${SVG.nav}</div>`, iconSize: [32, 32], iconAnchor: [16, 16] }),
        zIndexOffset: 1000,
      }).addTo(map).bindPopup("Tu ubicación");
    }
  }, [userPos]);

  return <div ref={elRef} className="absolute inset-0" />;
}
