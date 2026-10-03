import { escapeHtml as esc, enlaceSeguro } from "./markers";
import { glifoSvg } from "./iconos";
import { AVISO_ARO, AVISO_HALO, ZONA_HEX } from "./palette";
import { textoAviso } from "@/lib/avisoTexto";
import { CERCA_M, TITULO_NIVEL, fraseCorta, pasoAntes } from "@/lib/zonaRio";
import { lecturaRio } from "@/lib/lenguaje";
import { aspecto, diaConFecha, franja, temps } from "@/lib/pronostico";
import { DIAS_CORTOS, diaMesCorto, fechaPeru } from "@/lib/tiempo";

// HTML de los popups nuevos (avisos con insignia, pronóstico por localidad, nowcasting y zonas y
// desbordes de los ríos vigilados). Los textos salen de lib/avisoTexto.js, lib/pronostico.js y
// lib/zonaRio.js; aquí solo se arman, siempre escapados.
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

// ---------------------------------------------------------------------------
// Ríos vigilados: zona que el río podría afectar y desbordes pasados (layers/zonasRio.js y
// layers/desbordes.js). Los textos del nivel salen de lib/zonaRio.js.
// ---------------------------------------------------------------------------

const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });
const minuscula = (t) => t.charAt(0).toLowerCase() + t.slice(1);
const INSIGNIA_ZONA = {
  estimada: '<span class="insig">Estimado</span>',
  estudio: '<span class="insig oficial">Estudio 2005</span>',
};
const ACLARA_ZONA = {
  estimada: "Es una estimación hecha con el relieve: marca dónde mirar, no hasta dónde llegará el agua.",
  estudio: "Es un mapa de 2005: la ciudad y el río cambiaron desde entonces; marca dónde mirar, no hasta dónde llegará el agua.",
};
const verAviso = (url) =>
  enlaceSeguro(url) ? ` <a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Ver el aviso</a>` : "";

// Por qué la zona tiene su nivel (sin señales: cómo estaba el río en la última medición de ANA,
// que es horaria y puede tener horas de atraso: se dice de cuándo es).
function porQue(estado, caudal) {
  if (estado.senales.length) {
    const items = estado.senales.map((s) => `<li><b>${esc(s.titulo)}.</b> ${esc(s.texto)}${verAviso(s.url)}</li>`).join("");
    return `<div class="sub">Por qué</div><ul>${items}</ul>`;
  }
  const t = estado.t;
  if (!caudal || caudal.valor == null)
    return `<p>No hay medición reciente del río (ANA) ni avisos de lluvia fuerte en su cuenca.</p>`;
  const cuando = (lecturaRio(caudal) ?? "").replace(/\s*\(ANA\)$/, "");
  const medida = `${num(caudal.valor)} ${caudal.unidad}${cuando ? `, ${cuando}` : ""}`;
  return t && !t.bajo && t.estado === "normal"
    ? `<p>El río estaba tranquilo en la última medición de ANA (${esc(medida)}) y no hay avisos de lluvia fuerte en su cuenca.</p>`
    : `<p>En la última medición de ANA el río llevaba ${esc(medida)}, sin señales de crecida, y no hay avisos de lluvia fuerte en su cuenca.</p>`;
}

// "a 850 m" o "a 4,8 km"
const aDistancia = (m) =>
  m < 1000 ? `a ${Math.round(m / 50) * 50 || 50} m` : `a ${(m / 1000).toLocaleString("es-PE", { maximumFractionDigits: 1 })} km`;

// "Pasó antes en el río": con la zona tocada, primero los desbordes y daños más cercanos a ella
// ("Cerca de aquí", a menos de 1 km; si no, "En otros tramos del río", con la distancia), para que
// no se lean como ocurridos ahí los de otro tramo; y las crecidas medidas en rojo.
function pasoAntesHtml(incidentes, rio, zona) {
  const { danos, crecidas } = pasoAntes(incidentes, 4, zona?.geojson ?? null);
  if (!danos.length && !crecidas.length) return "";
  // los que no se listan y sí están en el mapa (los que solo tienen el distrito no van en la capa)
  const enMapa = (i) => i.tipo !== "crecida" && i.lat != null;
  const mas = incidentes.filter(enMapa).length - danos.filter(enMapa).length;
  const fuente = (i) =>
    enlaceSeguro(i.fuente_url)
      ? `<a href="${esc(i.fuente_url)}" target="_blank" rel="noopener noreferrer">${esc(i.fuente)}</a>`
      : esc(i.fuente);
  const linea = (i) =>
    `<li><b>${esc(i.fecha_texto)}</b> · ${esc(i.lugar)}${i.distM > 0 ? ` (${esc(aDistancia(i.distM))})` : ""} · ` +
    `${esc(i.titulo)} — ${fuente(i)}</li>`;
  const lista = (items) => (items.length ? `<ul>${items.map(linea).join("")}</ul>` : "");
  const conZona = danos.some((i) => i.distM != null);
  const cerca = conZona ? danos.filter((i) => i.distM != null && i.distM < CERCA_M) : [];
  const resto = conZona ? danos.filter((i) => !cerca.includes(i)) : danos;
  const enRojo = [...crecidas]
    .sort((a, b) => String(a.fecha ?? "").localeCompare(String(b.fecha ?? "")))
    .map((i) => `${i.fecha_texto}${i.caudal_m3s != null ? ` (${num(i.caudal_m3s)} m³/s)` : ""}`);
  return (
    `<div class="sub">Pasó antes en el ${esc(minuscula(rio.nombre))}</div>` +
    (cerca.length ? `<p class="tramo">Cerca de aquí</p>${lista(cerca)}` : "") +
    (conZona && resto.length ? `<p class="tramo">En otros tramos del río</p>` : "") +
    lista(resto) +
    (mas ? `<p class="aclara">Y ${mas} más en la capa «Desbordes y daños pasados».</p>` : "") +
    (enRojo.length ? `<p class="aclara">Crecidas medidas en rojo: ${esc(enRojo.join(", "))} (SENAMHI).</p>` : "")
  );
}

// Popup de una zona que el río podría afectar (o del aura, sin zona si aún no hay polígonos).
// rio: fila de rio_vigilado_mapa; zona: de rio_zona_mapa; estado: estadoZona(); caudal: fila de ANA.
// (La franja de color va con opcionesPopup(map, {acento}) según el nivel.)
export function popupZonaRio({ rio, zona, estado, caudal, incidentes = [] }) {
  const { nivel, avisoHidro } = estado;
  const fuerte = nivel === "alerta" || nivel === "emergencia";
  const accion = fuerte ? fraseCorta(rio, estado).accion : null;
  const titulo = zona ? `${zona.nombre} · ${minuscula(rio.nombre)}` : `Zona que podría afectar el ${minuscula(rio.nombre)}`;
  // sin señales y sin medición, porQue() ya dice que ANA no tiene medición
  const menciones = estado.menciones.filter((m) => estado.senales.length || m.clave !== "sin_ana");
  const lugares = (rio.lugares_aviso ?? []).map((l) => l.nombre);
  return (
    `<div class="pop pop-zona"><h4>${esc(titulo)}</h4>` +
    `<div class="meta">${esc(rio.departamento)} ·${zona ? ` ${INSIGNIA_ZONA[zona.tipo] ?? ""}` : ""}</div>` +
    `<div class="nivel-zona" style="--c:${ZONA_HEX[nivel]}"><i></i><span>${esc(TITULO_NIVEL[nivel])}` +
    (accion ? `. <b>${esc(accion)}</b>` : "") +
    `</span></div>` +
    (zona?.texto ? `<p>${esc(zona.texto)}</p>` : "") +
    porQue(estado, caudal) +
    menciones.map((m) => `<p class="aclara">${esc(m.texto)}${verAviso(m.url)}</p>`).join("") +
    (avisoHidro?.areas ? `<div class="sub">Según SENAMHI</div><p class="cita">«${esc(avisoHidro.areas)}»</p>` : "") +
    (fuerte && !avisoHidro && lugares.length
      ? `<div class="sub">Lugares que SENAMHI suele nombrar</div><p>${esc(lugares.join(", "))}.</p>`
      : "") +
    pasoAntesHtml(incidentes, rio, zona) +
    (nivel === "emergencia" && avisoHidro?.significado_rojo
      ? `<p>Para SENAMHI, el nivel rojo en este río significa: «${esc(avisoHidro.significado_rojo)}»</p>`
      : "") +
    `<p class="aclara">${zona ? `${esc(ACLARA_ZONA[zona.tipo] ?? ACLARA_ZONA.estimada)} ` : ""}` +
    `Ante una emergencia sigue las indicaciones de Defensa Civil (INDECI).</p>` +
    (zona?.atribucion ? firma(zona.atribucion) : "") +
    (zona ? enlace(zona.fuente_url, "Ver la fuente") : "") +
    `</div>`
  );
}

// Popup de un rombo de desbordes pasados: uno o varios incidentes juntos (del más nuevo). Con el
// mapa alejado un rombo junta lugares distintos: cada incidente dice el suyo.
export function popupIncidentes(lista, rio) {
  const [primero] = lista;
  const unLugar = lista.every((i) => i.lugar === primero.lugar);
  const titulo =
    lista.length === 1 ? primero.titulo : `${lista.length} incidentes ${unLugar ? "en este lugar" : "en este tramo del río"}`;
  const meta = [rio?.nombre ?? "Río", unLugar ? primero.lugar : null].filter(Boolean).join(" · ");
  const enlaceDe = (href, texto) =>
    enlaceSeguro(href) ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(texto)}</a>` : esc(texto);
  const items = lista
    .map((i) => {
      const otras = (Array.isArray(i.otras_fuentes) ? i.otras_fuentes : [])
        .filter((o) => o?.fuente)
        .map((o) => enlaceDe(o.url, o.fuente));
      return (
        `<div class="inc"><p class="tit"><b>${esc(i.fecha_texto)}</b> · ${esc(i.titulo)}</p>` +
        (unLugar ? "" : `<p class="aclara">Lugar: ${esc(i.lugar)}</p>`) +
        (i.detalle ? `<p class="aclara">${esc(i.detalle)}</p>` : "") +
        `<p class="aclara">Ubicación: ${esc(i.precision_texto)}</p>` +
        `<p class="enl">Fuente: ${enlaceDe(i.fuente_url, i.fuente)}${otras.length ? ` · También: ${otras.join(" · ")}` : ""}</p></div>`
      );
    })
    .join("");
  return (
    `<div class="pop pop-inc"><h4>${esc(titulo)}</h4><div class="meta">${esc(meta)}</div>${items}` +
    `<p class="aclara">Aquí el río ya causó daños: es una zona de peligro cuando el río crece. Que haya pasado antes no ` +
    `significa que esté pasando hoy; mira el color de la zona y los avisos de hoy.</p></div>`
  );
}
