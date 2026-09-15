import { useEffect, useRef } from "react";
import L from "leaflet";
import { getEstaciones, getCaudales } from "../lib/queries";
import { DEMO_INCIDENTS, DEMO_USERS } from "../data/incidents";

const C = {
  met: "#2E5BFF", hid: "#12B8A6",
  normal: "#12B886", alerta: "#FF6A00", emergencia: "#F02D5A",
  primary: "#2E5BFF",
  inc: { inundacion: "#1C7ED6", lluvia: "#22B8CF", huayco: "#E8590C", via: "#F03E3E" },
  zInund: "#F02D5A", zAlerta: "#FF6A00", zLluvia: "#22B8CF",
};

const SVG = {
  station: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><circle cx="12" cy="10" r="3"/><path d="M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z"/></svg>',
  wave: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M3 12c3 3 5-2 9 0s5 2 9 0"/></svg>',
  inundacion: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M12 22a7 7 0 0 0 7-7c0-5-7-13-7-13S5 10 5 15a7 7 0 0 0 7 7z"/></svg>',
  lluvia: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M8 19v2m4-3v3m4-4v2M18 15a4 4 0 0 0-1-7.9A6 6 0 1 0 6 13"/></svg>',
  huayco: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M3 20h18L14 6l-4 7-3-3z"/></svg>',
  via: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M4 19 20 5M4 5l16 14"/></svg>',
  person: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M5 21v-1a7 7 0 0 1 14 0v1"/></svg>',
  nav: '<svg viewBox="0 0 24 24" fill="#fff" stroke="#fff" stroke-width="1" stroke-linejoin="round"><path d="M3 11l19-9-9 19-2-8-8-2z"/></svg>',
};

// pin tipo Waze (gota) para usuarios; distinto de los círculos de estaciones.
function pinIcon(color, svg) {
  return L.divIcon({
    className: "",
    html: `<div class="mkpin" style="background:${color}">${svg}</div>`,
    iconSize: [30, 30], iconAnchor: [15, 28],
  });
}

function icon(color, svg, diamond) {
  return L.divIcon({
    className: "",
    html: `<div class="mk${diamond ? " diamond" : ""}" style="width:34px;height:34px;background:${color}">${svg}</div>`,
    iconSize: [34, 34], iconAnchor: [17, 17],
  });
}

export default function MapView({ visible, onReady, focus, userPos }) {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const groupsRef = useRef(null);
  const userMkRef = useRef(null);

  // init (una vez)
  useEffect(() => {
    const map = L.map(elRef.current, { zoomControl: false }).setView([-7.16, -78.51], 13);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18, attribution: "© OpenStreetMap",
    }).addTo(map);

    const g = {
      est: L.layerGroup(), rio: L.layerGroup(), inc: L.layerGroup(),
      usr: L.layerGroup(), zona: L.layerGroup(),
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
        if (c.estado === "alerta" || c.estado === "emergencia")
          L.circle([c.lat, c.lon], { radius: 2500, color: col, weight: 1, fillColor: col, fillOpacity: 0.18 }).addTo(g.zona);
      });
    }).catch((err) => console.error("caudales", err));

    // zonas demo (estado "alerta" en la ciudad)
    L.circle([-7.157, -78.512], { radius: 1400, color: C.zInund, weight: 1, fillColor: C.zInund, fillOpacity: 0.16 }).addTo(g.zona);
    L.circle([-7.17, -78.52], { radius: 2200, color: C.zAlerta, weight: 1, fillColor: C.zAlerta, fillOpacity: 0.12 }).addTo(g.zona);
    L.circle([-7.15, -78.5], { radius: 1800, color: C.zLluvia, weight: 1, fillColor: C.zLluvia, fillOpacity: 0.14 }).addTo(g.zona);

    // incidentes demo
    DEMO_INCIDENTS.forEach((i) => {
      L.marker([i.lat, i.lon], { icon: icon(C.inc[i.tipo], SVG[i.tipo], true) })
        .bindPopup(
          `<div class="pop"><h4>${i.titulo}</h4><div class="meta">${i.autor} · ${i.hace} · ${i.km}</div><p>${i.desc}</p>
           <div class="acts">
             <button class="vote up">▲ ${i.up}</button>
             <button class="vote down">▼ ${i.down}</button>
             <button class="vote-fill">Ver reporte →</button>
           </div></div>`
        )
        .addTo(g.inc);
    });

    // usuarios cercanos demo (pin de persona tipo Waze)
    DEMO_USERS.forEach((ll) => L.marker(ll, { icon: pinIcon("#7048E8", SVG.person) })
      .bindPopup('<div class="pop"><h4>Usuario cercano</h4><div class="meta">En tu zona</div></div>')
      .addTo(g.usr));

    const t = setTimeout(() => map.invalidateSize(), 300);

    return () => {
      clearTimeout(t);
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

  return <div ref={elRef} className="mapcanvas" />;
}
