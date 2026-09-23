// Glifos del tiempo con "relleno suave" (viewBox 32): los usan las insignias de los avisos, los
// discos del pronóstico, la franja de 3 días y las leyendas. Los degradados y la sombra viven una
// sola vez en el documento (DEFS_SVG, que monta main.jsx), con ids prefijados "simpac-" para no
// chocar con otros SVG de la página. Son constantes: nunca llevan datos de una fuente.
// Trazos de viento basados en Lucide 0.454 (ISC).
// Módulo puro, sin imports: lo leen también las pruebas con node --test.

export const DEFS_ID = "simpac-defs-iconos";

// userSpaceOnUse en las nubes: una nube hecha de varios círculos lleva un solo degradado continuo.
export const DEFS_SVG = `<svg id="${DEFS_ID}" width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
<linearGradient id="simpac-gNube" x1="0" y1="4" x2="0" y2="25" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#B4C1D3"/></linearGradient>
<linearGradient id="simpac-gNubeOsc" x1="0" y1="4" x2="0" y2="25" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#A9B6C8"/><stop offset="1" stop-color="#5B6B82"/></linearGradient>
<linearGradient id="simpac-gGota" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6CCBFF"/><stop offset="1" stop-color="#1673D9"/></linearGradient>
<linearGradient id="simpac-gRayo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFE066"/><stop offset="1" stop-color="#F59E0B"/></linearGradient>
<radialGradient id="simpac-gSol" cx=".4" cy=".35" r=".7"><stop offset="0" stop-color="#FFE9A3"/><stop offset=".55" stop-color="#FFC53D"/><stop offset="1" stop-color="#F59E0B"/></radialGradient>
<linearGradient id="simpac-gCalor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FF8A5B"/><stop offset="1" stop-color="#E03E1A"/></linearGradient>
<linearGradient id="simpac-gFrio" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7CC4FF"/><stop offset="1" stop-color="#2563EB"/></linearGradient>
<filter id="simpac-fSombra" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy=".8" stdDeviation=".6" flood-color="#0f172a" flood-opacity=".38"/></filter>
</defs></svg>`;

// Monta los degradados una vez (antes de dibujar cualquier glifo).
export function montarDefsIconos(doc = document) {
  if (!doc.getElementById(DEFS_ID)) doc.body.insertAdjacentHTML("afterbegin", DEFS_SVG);
}

const s = (inner) => `<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">${inner}</svg>`;

const nube = (fill = "url(#simpac-gNube)", dy = 0) =>
  `<g transform="translate(0 ${dy})" fill="${fill}" filter="url(#simpac-fSombra)"><circle cx="10" cy="19" r="6"/><circle cx="17" cy="13.5" r="7.5"/><circle cx="23.5" cy="19.5" r="5.5"/><rect x="10" y="17" width="13.5" height="8"/></g>`;

const gotita = (x, y, k = 1) =>
  `<path fill="url(#simpac-gGota)" transform="translate(${x} ${y}) scale(${k})" d="M0-3.6C0-3.6-2.3-.8-2.3.9a2.3 2.3 0 0 0 4.6 0C2.3-.8 0-3.6 0-3.6z"/>`;

const GOTA_G = "M16 2.5S7 12.6 7 18.9a9 9 0 0 0 18 0C25 12.6 16 2.5 16 2.5z";
const brillo = `<ellipse cx="12.6" cy="19.2" rx="1.7" ry="3.2" fill="#fff" opacity=".55" transform="rotate(18 12.6 19.2)"/>`;

const rayo = (tr = "") =>
  `<path transform="${tr}" fill="url(#simpac-gRayo)" stroke="#fff" stroke-width="1.3" stroke-linejoin="round" d="M17.6 15.5 11.8 23.4h4.4l-2.4 7.1 7.6-9.7h-4.7l3-5.3z"/>`;

// copo grande: tres ejes con sus ramitas, con un halo blanco para que se lea sobre cualquier fondo
const copo = (cx, cy, r, color = "#5FB8F2", w = 2.2) => {
  let p = "";
  for (const a of [0, 60, 120]) {
    p += `<g transform="rotate(${a} ${cx} ${cy})"><path d="M${cx} ${cy - r}V${cy + r}M${cx - r * 0.32} ${cy - r * 0.78}l${r * 0.32} ${r * 0.3} ${r * 0.32}-${r * 0.3}M${cx - r * 0.32} ${cy + r * 0.78}l${r * 0.32}-${r * 0.3} ${r * 0.32} ${r * 0.3}"/></g>`;
  }
  return (
    `<g fill="none" stroke="#fff" stroke-width="${w + 1.6}" stroke-linecap="round" stroke-linejoin="round">${p}</g>` +
    `<g fill="none" stroke="${color}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round">${p}</g>`
  );
};

// copo chico: asterisco de 3 trazos (sin halo, para que no se vea como una mancha)
const copito = (cx, cy, r = 2.6) => {
  let d = "";
  for (const a of [90, 30, 150]) {
    const dx = Math.cos((a * Math.PI) / 180) * r;
    const dy = Math.sin((a * Math.PI) / 180) * r;
    d += `M${(cx - dx).toFixed(2)} ${(cy - dy).toFixed(2)}L${(cx + dx).toFixed(2)} ${(cy + dy).toFixed(2)}`;
  }
  return `<path d="${d}" stroke="#2F95E8" stroke-width="1.6" stroke-linecap="round"/>`;
};

const sol = (cx, cy, r) => {
  let rays = "";
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4;
    const x1 = cx + Math.cos(a) * (r + 2.2);
    const y1 = cy + Math.sin(a) * (r + 2.2);
    const x2 = cx + Math.cos(a) * (r + 4.3);
    const y2 = cy + Math.sin(a) * (r + 4.3);
    rays += `M${x1.toFixed(2)} ${y1.toFixed(2)}L${x2.toFixed(2)} ${y2.toFixed(2)}`;
  }
  return `<path d="${rays}" stroke="#F7B32B" stroke-width="2" stroke-linecap="round"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#simpac-gSol)"/>`;
};

const termometro = (degradado) =>
  s(
    `<rect x="12.5" y="3" width="7" height="19" rx="3.5" fill="#fff" stroke="#94A3B8" stroke-width="1.3"/>` +
      `<circle cx="16" cy="23.5" r="5.6" fill="url(#${degradado})" stroke="#fff" stroke-width="1.2"/>` +
      `<rect x="14.4" y="10" width="3.2" height="12" rx="1.6" fill="url(#${degradado})"/>`
  );

export const GLIFOS = {
  // avisos
  gota: s(`<path fill="url(#simpac-gGota)" filter="url(#simpac-fSombra)" d="${GOTA_G}"/>${brillo}`),
  // el rayo amarillo va DENTRO de la gota: se sigue leyendo a 24 px (afuera y chico se perdía)
  gota_rayo: s(
    `<path fill="url(#simpac-gGota)" filter="url(#simpac-fSombra)" d="${GOTA_G}"/>` +
      `<path fill="url(#simpac-gRayo)" stroke="#fff" stroke-width="1.1" stroke-linejoin="round" d="M17.9 11.2 12.4 19.6h3.9l-1.9 6.6 6.3-9.3h-4l2.6-5.7z"/>`
  ),
  copo: s(copo(16, 16, 12.5, "#4BA8EE", 2.6)),
  termometro: termometro("simpac-gCalor"),
  termometro_frio: termometro("simpac-gFrio"),
  viento: s(
    `<g transform="translate(4 4)" fill="none" stroke="#64748B" stroke-width="2.2" stroke-linecap="round">` +
      `<path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/></g>`
  ),
  // pronóstico por localidad
  sol: s(sol(16, 16, 7)),
  sol_nube: s(sol(12.5, 12.5, 6.4) + `<g transform="translate(9.5 8.5) scale(.7)">${nube()}</g>`),
  nube: s(nube("url(#simpac-gNube)", -1.5)),
  tendencia: s(nube("url(#simpac-gNube)", -3.5) + gotita(16, 27.2, 1.05)),
  lluvia: s(nube("url(#simpac-gNube)", -3.5) + gotita(10.5, 26.6) + gotita(16.5, 28.4) + gotita(22.5, 26.6)),
  tormenta: s(
    nube("url(#simpac-gNubeOsc)", -5) +
      rayo("translate(16.4 17.4) scale(1.12) translate(-16.4 -17.4) translate(-.4 -1.2)")
  ),
  nieve: s(nube("url(#simpac-gNube)", -3.5) + copito(10.5, 27.3) + copito(16.5, 28.6) + copito(22.5, 27.3)),
};

export const glifoSvg = (k) => GLIFOS[k] ?? GLIFOS.nube;
