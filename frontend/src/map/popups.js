import { escapeHtml as esc, enlaceSeguro } from "./markers";
import { glifoSvg } from "./iconos";
import { AVISO_ARO, AVISO_HALO } from "./palette";
import { textoAviso } from "@/lib/avisoTexto";
import { aspecto, diaConFecha, franja, temps } from "@/lib/pronostico";
import { DIAS_CORTOS, diaMesCorto, fechaPeru } from "@/lib/tiempo";

// HTML de los popups nuevos (avisos con insignia, pronóstico por localidad y nowcasting). Los
// textos salen de lib/avisoTexto.js y lib/pronostico.js; aquí solo se arman, siempre escapados.
// Los glifos (map/iconos.js) son constantes y van sin escapar.

// Ancho fijo; alto con tope que cabe entre los márgenes (en el celular, sobre el panel de estado,
// que ocupa cerca del 45% de abajo). `acento` (nivel 2 a 4) pinta la franja de 4 px del color del
// aviso en el borde de arriba del popup (sigue a la vista aunque el contenido se desplace). En
// pantallas angostas los chips de arriba se apartan mientras hay un popup abierto (MapView + CSS).
export function opcionesPopup(map, { acento } = {}) {
  const abajo = innerWidth < 640 ? Math.round(innerHeight * 0.45) : 24;
  return {
    maxWidth: 320,
    minWidth: 280,
    className: acento ? `pop-ancho acento-${acento}` : "pop-ancho",
    maxHeight: Math.max(200, Math.min(480, Math.round(map.getSize().y * 0.6), innerHeight - 70 - abajo - 50)),
    autoPanPaddingTopLeft: [16, 70],
    autoPanPaddingBottomRight: [16, abajo],
  };
}

const enlace = (href, texto) =>
  enlaceSeguro(href)
    ? `<p class="enl"><a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(texto)}</a></p>`
    : "";

const firma = (t) => `<p class="firma">${esc(t)}</p>`;

function caja([linea, aclara]) {
  return `<div class="caja">${esc(linea)}${aclara ? `<span class="aclara">${esc(aclara)}</span>` : ""}</div>`;
}

function filas(lista) {
  if (!lista?.length) return "";
  const f = lista
    .map(
      ({ etiqueta, texto, cita }) =>
        `<dt>${esc(etiqueta)}</dt><dd>${esc(texto)}${cita ? `<span class="cita">${esc(cita)}</span>` : ""}</dd>`
    )
    .join("");
  return `<dl class="filas filas-suave">${f}</dl>`;
}

// Tabla de montos por subregión; en mm, cada fila con su barra sobre la misma escala.
function montos(m) {
  const barra = (b) => {
    if (!b) return "<span></span>";
    if (b.tipo === "cerca") return `<div class="barra"><span class="punto" style="left:${b.desde}%"></span></div>`;
    const cls = b.tipo === "mas_de" ? ' class="mas"' : "";
    return `<div class="barra"><span${cls} style="left:${b.desde}%;width:${Math.max(2, b.hasta - b.desde)}%"></span></div>`;
  };
  const filasMm = m.filas
    .map((f) => `<span class="l">${esc(f.lugar)}</span><span class="v">${esc(f.texto)}</span>${barra(f.barra)}`)
    .join("");
  const escala = m.escala
    ? `<span></span><span></span><div class="esc"><span>0</span><span>${m.escala / 2}</span><span>${m.escala}</span></div>`
    : "";
  return `<div class="sub">${esc(m.titulo)}</div><div class="mm">${filasMm}${escala}</div><p class="mm-nota">${esc(m.nota)}</p>`;
}

function detalles({ general, dia } = {}) {
  if (!general && !dia) return "";
  return (
    `<details><summary>Texto oficial de SENAMHI</summary>` +
    (general ? `<blockquote>${esc(general)}</blockquote>` : "") +
    (dia ? `<blockquote>${esc(dia)}</blockquote>` : "") +
    `<p class="pie-det">Texto de SENAMHI, sin cambios.</p></details>`
  );
}

function cabecera(t, subtitulo) {
  return (
    `<div class="cab"><span class="pop-ins" style="--aro:${AVISO_ARO[t.nivel]};--halo:${AVISO_HALO[t.nivel]}">` +
    `${t.glifo ? glifoSvg(t.glifo) : ""}</span><div class="cab-txt"><h4>${esc(t.cabecera)}</h4>` +
    (subtitulo ? `<div class="meta">${esc(subtitulo)}</div>` : "") +
    `</div></div>`
  );
}

function seccionAviso(t) {
  if (t.forma === "otro") {
    return (
      cabecera(t, t.meta) +
      `<p class="resumen">${esc(t.resumen)}</p>` +
      `<p class="nota">${esc(t.nota)}</p>` +
      enlace(t.url, "Ver el aviso oficial")
    );
  }
  if (t.forma === "24h") {
    return cabecera(t, t.subtitulo) + caja(t.caja) + filas(t.filas) + detalles(t.oficial) + enlace(t.url, "Ver el aviso oficial en SENAMHI") + firma(t.firma);
  }
  return (
    cabecera(t, t.subtitulo) +
    (t.titulo ? `<p class="tit">${esc(t.titulo)}</p>` : "") +
    (t.donde ? `<p class="donde">${esc(t.donde)}</p>` : "") +
    caja(t.caja) +
    (t.montos ? montos(t.montos) : "") +
    (t.literal ? `<div class="sub">${esc(t.literal.titulo)}</div><p class="cita">${esc(t.literal.texto)}</p>` : "") +
    filas(t.filas) +
    detalles(t.oficial) +
    enlace(t.url, "Ver el aviso oficial en SENAMHI") +
    firma(t.firma)
  );
}

// Uno o varios avisos (los que rigen en el punto tocado o los juntados en una insignia), del
// más alto al más bajo. `mapasDe(fila)` = cuántos días tiene ese aviso.
// (La franja de color va con opcionesPopup(map, {acento: nivel del primero}).)
export function popupAvisos(lista, { hoy = fechaPeru(), mapasDe = () => 1 } = {}) {
  const partes = lista.map((a, i) => {
    const t = textoAviso(a, { hoy, mapas: mapasDe(a) });
    const sep = i === 0 ? "" : `<div class="sep">${i === 1 ? "También rige aquí" : ""}</div>`;
    return sep + seccionAviso(t);
  });
  return `<div class="pop pop-aviso">${partes.join("")}</div>`;
}

const mayuscula = (t) => t.charAt(0).toUpperCase() + t.slice(1);

// Popup de una localidad: el día elegido con su texto literal y los 3 días en chico.
export function popupLocalidad(fila, propias, { hoy = fechaPeru() } = {}) {
  const a = aspecto(fila);
  const t = [
    fila.tmax != null ? `Máxima ${fila.tmax} °C` : null,
    fila.tmin != null ? `Mínima ${fila.tmin} °C` : null,
  ].filter(Boolean);
  const notas = [];
  if (fila.posible && fila.por !== "icono") notas.push("SENAMHI escribe «tendencia a»: es posible, no seguro.");
  if (fila.por === "icono" && fila.tipo === "tormenta") notas.push("SENAMHI usa su ícono de tormenta; su texto solo dice lluvia.");
  if (fila.por === "icono" && fila.tipo === "lluvia") notas.push("SENAMHI usa su ícono de lluvia; su texto no la menciona.");
  const dias = franja(propias, fila.codigo, hoy)
    .map((d) => {
      const etiqueta = d.fecha === hoy ? "Hoy" : mayuscula(DIAS_CORTOS[new Date(`${d.fecha}T12:00:00-05:00`).getUTCDay()]);
      const sel = d.fecha === fila.fecha ? " sel" : "";
      if (!d.fila) return `<div class="d falta${sel}"><div class="l">${esc(etiqueta)}</div><span class="glifo sin">?</span><div class="t">–</div></div>`;
      return (
        `<div class="d${sel}"><div class="l">${esc(etiqueta)}</div>` +
        `<span class="glifo">${glifoSvg(aspecto(d.fila).glifo)}</span><div class="t">${esc(temps(d.fila))}</div></div>`
      );
    })
    .join("");
  return (
    `<div class="pop pop-loc"><h4>${esc(fila.nombre)}</h4>` +
    `<div class="meta">Pronóstico de SENAMHI${fila.emision ? ` · emitido el ${esc(diaMesCorto(fila.emision))}` : ""}</div>` +
    `<p class="resumen"><span class="cuando">${esc(diaConFecha(fila.fecha, hoy))}:</span> ${esc(a.corto)}` +
    (a.extra ? `<span class="extra">${esc(a.extra)}</span>` : "") +
    `</p>` +
    (t.length ? `<p class="temps">${esc(t.join(" · "))}</p>` : "") +
    (fila.texto
      ? `<blockquote class="literal">«${esc(fila.texto)}»<span class="de">— Texto de SENAMHI para esta localidad</span></blockquote>`
      : "") +
    notas.map((n) => `<p class="aclara">${esc(n)}</p>`).join("") +
    `<div class="mini3">${dias}</div>` +
    `<p class="aclara">Vale para esta localidad; a pocos kilómetros puede ser distinto.</p>` +
    enlace(fila.url, "Ver el pronóstico en SENAMHI") +
    firma("Ícono y resumen de SIMPAC, basados en el texto de SENAMHI.") +
    `</div>`
  );
}

// Popup de una mancha del nowcasting (experimental; ningún nivel lleva rayo).
export function popupNowcast({ titulo, cuando, emitido, color, url }) {
  return (
    `<div class="pop pop-nc">` +
    `<div class="cab"><span class="pop-ins nc" style="--aro:${color};--halo:${color}33">${glifoSvg("lluvia")}</span>` +
    `<div class="cab-txt"><h4>${esc(titulo)}</h4><span class="insig">Experimental</span></div></div>` +
    `<p class="resumen">${esc(cuando)}</p>` +
    `<p class="aclara">Es una estimación automática de SENAMHI con imágenes de satélite, todavía en calibración. Puede fallar y no es un aviso oficial.</p>` +
    `<p class="meta">${esc(emitido)}</p>` +
    enlace(url, "Ver el nowcasting en SENAMHI") +
    firma("Basado en el nowcasting de SENAMHI; colores de SIMPAC.") +
    `</div>`
  );
}
