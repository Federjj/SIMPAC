import L from "leaflet";

// Íconos (SVG blanco sobre el color del marcador). Son constantes internas, nunca
// datos: todo lo que venga de una fuente o de un usuario pasa por escapeHtml().
const svg = (d, extra = "") =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"${extra}>${d}</svg>`;

export const SVG = {
  station: svg('<circle cx="12" cy="10" r="3"/><path d="M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z"/>'),
  wave: svg('<path d="M3 12c3 3 5-2 9 0s5 2 9 0"/>'),
  nav: '<svg viewBox="0 0 24 24" fill="#fff" stroke="#fff" stroke-width="1" stroke-linejoin="round"><path d="M3 11l19-9-9 19-2-8-8-2z"/></svg>',
  // reportes ciudadanos (ids de lib/reportTypes.js)
  inundacion: svg('<path d="M12 22a7 7 0 0 0 7-7c0-5-7-13-7-13S5 10 5 15a7 7 0 0 0 7 7z"/>'),
  huayco: svg('<path d="M3 20h18L14 6l-4 7-3-3z"/>'),
  lluvia_intensa: svg('<path d="M8 19v2m4-3v3m4-4v2M18 15a4 4 0 0 0-1-7.9A6 6 0 1 0 6 13"/>'),
  via_bloqueada: svg('<path d="M4 19 20 5M4 5l16 14"/>'),
  atasco: svg('<path d="M5 17h14v-4l-2-5H7l-2 5z"/><circle cx="8" cy="17" r="1.5"/><circle cx="16" cy="17" r="1.5"/>'),
  bache: svg('<ellipse cx="12" cy="14" rx="8" ry="4"/><path d="M8 13l2 1 3-2 3 2"/>'),
  accidente: svg('<path d="M12 3 2 20h20z"/><path d="M12 10v4m0 3h.01"/>'),
  otro: svg('<path d="M12 5v9m0 4h.01"/>'),
};

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(valor) {
  return String(valor ?? "").replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

// Marcador redondo con ícono (estaciones, ríos) o gota tipo Waze (reportes).
export function markerIcon(color, icono, { forma = "circulo" } = {}) {
  if (forma === "gota") {
    return L.divIcon({
      className: "",
      html: `<div class="mkpin" style="background:${color}">${icono}</div>`,
      iconSize: [30, 30],
      iconAnchor: [15, 36], // la punta de la gota (el cuadro rotado 45 grados)
      popupAnchor: [0, -32],
    });
  }
  return L.divIcon({
    className: "",
    html: `<div class="mk" style="width:34px;height:34px;background:${color}">${icono}</div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

// Solo enlaces https (los que vienen de una fuente, p. ej. la página de un aviso).
export function enlaceSeguro(href) {
  try {
    return new URL(href).protocol === "https:" ? href : null;
  } catch {
    return null;
  }
}

// Popup con título, contexto, una frase en lenguaje claro, filas etiqueta/valor, una
// nota (qué hacer) y un enlace opcional a la fuente. Todo se escapa.
export function popupHtml({ title, meta = [], resumen, filas = [], nota, enlace }) {
  const m = meta.filter(Boolean).map(escapeHtml).join(" · ");
  const f = filas
    .filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`)
    .join("");
  return (
    `<div class="pop"><h4>${escapeHtml(title)}</h4>` +
    (m ? `<div class="meta">${m}</div>` : "") +
    (resumen ? `<p class="resumen">${escapeHtml(resumen)}</p>` : "") +
    (f ? `<dl class="filas">${f}</dl>` : "") +
    (nota ? `<p class="nota">${escapeHtml(nota)}</p>` : "") +
    (enlace && enlaceSeguro(enlace.href)
      ? `<p class="nota"><a href="${escapeHtml(enlace.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(enlace.texto)}</a></p>`
      : "") +
    `</div>`
  );
}
