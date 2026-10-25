import L from "leaflet";
import { Waves } from "lucide-react";
import { getCauceRio, getCaucesRios, getCaudales, getRiosVigilados, getSenalesCauces, getSenalesRio, getZonasRio } from "@/lib/queries";
import { lecturaRio, textoRio } from "@/lib/lenguaje";
import { avisoEsDeEstacion, caudalDelRio, diaHora, estacionDeAviso, estadoCauce, estadoZona } from "@/lib/zonaRio";
import {
  GEOMETRIAS, ROTULOS_DESDE, aLatLngs, aligerar, avisosDe, cajaConMargen, detallePorZoom, elegirRotulados, emparejarCauces,
  enVista, esFuerte, estadoRio, extenderTramo, guardarDetalle, latLngsTramo, licenciaCorta, lista, notaCauces, tramoCubre,
} from "@/lib/cauces";
import { NOTA_SIMULACION, conSimulacion, simularCauce } from "@/lib/simulacion";
import { CAUCE_HEX, RIO_HEX } from "../palette";
import { enlaceSeguro, escapeHtml, popupHtml } from "../markers";
import { iconoRio, textoRotulo } from "../marcadores";
import { rotuloLinea } from "../rotuloLinea";

// Estaciones de río de ANA (vista caudal_actual) como discos con rótulo «Mashcón · Tranquilo
// 0.13 m³/s» que acomoda map/acomodo.js (en alerta o emergencia el aro late y siempre se ven), y
// los ríos vigilados (vista rio_vigilado_mapa, primero el Mashcón) resaltados: halo blanco, cauce
// del color de su estación (azul si está tranquilo), afluentes finos, el nombre escrito sobre la
// línea (desde zoom 13) y el límite de la faja marginal de ANA (desde zoom 14). Los grosores por
// zoom los pone index.css ([data-zoom-banda], MapView). Sin las vistas de los ríos vigilados
// (migración pendiente) quedan solo las estaciones.
// Con un aviso hidrológico de SENAMHI para un río vigilado (vista rio_senal) más alto que lo que
// mide ANA, el cauce y el disco toman el color del aviso y lo dicen, con la cifra de ANA y su hora
// al lado (lib/zonaRio.js estadoCauce): así no se ve la zona roja y el río "tranquilo".
// Su disco tiene más prioridad en el acomodo que el de una estación cualquiera (más aún con
// señales en su zona) y, si choca, se corre a un lado en vez de quedar como punto.
//
// Ríos del país (vista rio_cauce_mapa, ~100 ríos con trazo de ANA - GeoSNIRH; lib/cauces.js): cada
// río con estación de ANA va resaltado igual que el Mashcón (halo blanco y cauce del color de la
// peor de sus estaciones o, si es más alto, del aviso hidrológico de SENAMHI de rio_cauce_senal),
// con su popup y el nombre sobre la línea. El Mashcón no se dibuja dos veces (rio_vigilado manda)
// y un río sin trazo no se inventa (queda su disco; la nota lo cuenta). Por rendimiento:
//   - de una vez llega el trazo de ~50 m de todos (cauce_lejos, ~750 KB, 35 000 vértices); el fino
//     (~6 m) se pide por río solo para los que están a la vista desde zoom 13 (getCauceRio) y se
//     vuelve al de ~50 m al alejarse;
//   - las geometrías no viajan con los datos de la capa (lib/cauces.js aligerar: MapView saca una
//     huella JSON de ellos y los 750 KB la pasarían de largo);
//   - con el mapa en vista país (zoom 6 o menos, [data-escala="pais"]) los ríos tranquilos van en
//     gris fino sin halo y solo los que están en alerta o emergencia conservan su color (CSS);
//   - el nombre se escribe solo para los ríos a la vista, desde zoom 10 y hasta 8 a la vez (primero
//     los que están en alerta o emergencia, después los de tramo visible más largo), sobre el tramo
//     visible (no sobre los 1700 km del Marañón), y no se rehace si tras un arrastre el tramo
//     rotulado sigue cubriendo lo visible.
// Un río con solo aviso de SENAMHI (sin estación de ANA: Biabo, Pampas...) se resalta únicamente
// mientras tenga un aviso hidrológico vigente.
// Un aviso hidrológico es de UNA estación (su título la nombra: "... - ESTACIÓN SAN REGIS"): el
// trazo del río lleva su color y lo explica, pero el disco y el rótulo de una estación de ANA solo
// dicen "Aviso" si el aviso es de esa misma estación (lib/zonaRio.js avisoEsDeEstacion). Antes el
// aviso de San Regis (Loreto) teñía también Balsas y Corral Quemado (Cajamarca, a cientos de km,
// tranquilos): 13 estaciones en naranja sin aviso propio.
const ATRIB_ANA = "Niveles de ríos: ANA";
const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });
const minuscula = (t) => t.charAt(0).toLowerCase() + t.slice(1);
const NOTA_CAUCE =
  "Las franjas junto al río marcan la zona que podría afectar si se desborda (capa «Zonas que un río podría afectar»).";
// las zonas estimadas (si SIMPAC las tiene para el río) y la franja de atención van en la otra capa
const SIN_ZONAS =
  "Si SIMPAC estimó zonas que este río podría afectar (con el relieve; no es un mapa oficial) se ven en la capa «Zonas que un río podría afectar» al acercarse; la franja punteada junto al cauce, solo en alerta o emergencia, es referencial.";
const ESPERA_VISTA_MS = 150; // tras moveend, antes de revisar detalle y nombres
const GUIA_PX = 6; // simplificación de la guía del nombre (píxeles con el zoom de ahora)
// "2021-01-11" -> "11/01/2021"
const fechaCorta = (f) => (/^\d{4}-\d{2}-\d{2}$/.test(f ?? "") ? f.split("-").reverse().join("/") : f);
const CORTA_AVISO = { amarillo: "Aviso amarillo", naranja: "Aviso naranja", rojo: "Aviso rojo" };
// enlace al histórico de la estación (/historico, pages/Historico.jsx); Mapa.jsx navega los
// <a data-ruta> de los popups sin recargar la página
const enlaceHistorico = (c) =>
  `<div class="pop"><p class="enl"><a data-ruta href="${escapeHtml(
    `/historico?tipo=rio&id=${encodeURIComponent(c.estacion)}${c.rio ? `&rio=${encodeURIComponent(c.rio)}` : ""}`
  )}">Ver histórico</a></p></div>`;

// Un río vigilado (o los del país) que falla no deja el mapa sin estaciones (MapView reintenta
// solo si falla todo).
const opcional = (p, que = "ríos vigilados") =>
  p.catch((e) => {
    console.error(`capa rio: ${que}`, e);
    return null;
  });

// "Hay un aviso hidrológico rojo de SENAMHI para este río (N.º 12, vigente hasta el 3 de octubre, 4:00 p. m.)."
function notaAviso(h, color) {
  const cuando = h.fin ? `, vigente hasta el ${diaHora(h.fin)}` : "";
  return (
    `Hay un aviso hidrológico ${color} de SENAMHI para este río (N.º ${h.numero}${cuando}). ` +
    "Tenlo en cuenta aunque la última medición de ANA diga otra cosa: el aviso puede llegar antes que la lectura nueva."
  );
}

// "San Regis": la estación de ANA a la que se refiere el aviso (si se llama igual) o, si no, el
// nombre que trae el título del aviso; null si el título no la nombra.
const MINUSCULAS = new Set(["de", "del", "la", "las", "el", "los", "y"]);
function estacionDelAviso(aviso, lecturas = []) {
  const c = lecturas.find((x) => avisoEsDeEstacion(aviso, x.estacion));
  if (c) return c.estacion;
  const de = estacionDeAviso(aviso);
  return de
    ? de.split(" ").map((w, i) => (i && MINUSCULAS.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1))).join(" ")
    : null;
}

// filas del popup: niveles de alerta y de emergencia de ANA y la medición con su hora
function filasAna(c, t) {
  const umbral = (etiqueta, v) => [
    `${t.bajo ? `${etiqueta} por nivel bajo` : etiqueta}`,
    v != null ? `${num(v)} ${c.unidad}` : null,
  ];
  return [umbral("Nivel de alerta", t.ua), umbral("Nivel de emergencia", t.ue), ["Medido", lecturaRio(c)]];
}

// Popup de una estación. `vig` (la de un río vigilado, o la de un río del país con aviso
// hidrológico más alto que su lectura): {rio, estado, cauce} para titularlo con el nombre del río
// y, si hay aviso hidrológico, decirlo primero.
function popupEstacion(c, t, { nota, vig } = {}) {
  const aviso = vig?.cauce.porAviso ? vig.estado.avisoHidro : null;
  return popupHtml({
    title: vig ? vig.rio.nombre : t.titulo,
    meta: [
      aviso ? `Aviso hidrológico ${vig.cauce.color} (SENAMHI)` : t.etiqueta,
      vig ? `Estación ${c.estacion} (ANA)` : null,
      c.departamento,
    ],
    resumen: aviso ? notaAviso(aviso, vig.cauce.color) : t.frase,
    filas: filasAna(c, t),
    nota: [aviso ? `Última medición de ANA: ${t.frase}` : null, t.accion, nota],
    enlace: aviso && enlaceSeguro(aviso.url) ? { href: aviso.url, texto: "Ver el aviso de SENAMHI" } : null,
  }) + enlaceHistorico(c);
}

// Halo, cauce, afluentes, nombre sobre la línea y faja marginal de un río vigilado.
// vig: {rio, estado (estadoZona), cauce (estadoCauce)}; c: su fila de ANA (o null).
function dibujarRio(group, map, vig, c, fajas) {
  const { rio: r, cauce } = vig;
  const t = c ? textoRio(c) : null;
  const color = CAUCE_HEX[cauce.estado] ?? CAUCE_HEX.sd;
  if (r.afluentes) {
    // más opacos que antes (.55): sobre el tinte de un aviso se veían grises, como los del mapa base
    L.geoJSON(r.afluentes, {
      pane: "rios",
      interactive: false,
      style: { className: "rio-afluente", color: "#5B8FC7", weight: 2, opacity: 0.9 },
    }).addTo(group);
  }
  if (r.cauce) {
    L.geoJSON(r.cauce, {
      pane: "rios",
      interactive: false,
      style: { className: "rio-halo", color: "#fff", weight: 13, opacity: 0.92 },
    }).addTo(group);
  }
  // la faja va encima del halo (casi toda cae dentro de su ancho) y debajo del cauce
  for (const z of fajas) {
    const rd = /RD [^)]+/.exec(z.fuente)?.[0];
    L.geoJSON(z.geojson, {
      pane: "rioFaja",
      style: { className: "rio-faja", color: "#0F4C81", weight: 1.5, opacity: 0.9, dashArray: "6 4" },
    })
      .bindTooltip(escapeHtml(`Límite de la faja marginal (ANA${rd ? `, ${rd}` : ""})`), { sticky: true, className: "tip" })
      .bindPopup(
        popupHtml({
          title: `Faja marginal del ${minuscula(r.nombre)}`,
          meta: ["ANA", fechaCorta(z.fecha_fuente)],
          resumen: z.texto,
          nota: z.atribucion,
          enlace: { href: z.fuente_url, texto: "Ver el servicio de ANA" },
        })
      )
      .addTo(group);
  }
  if (!r.cauce) return;
  L.geoJSON(r.cauce, { pane: "rioCauce", style: { className: "rio-cauce", color, weight: 6.5, opacity: 1 } })
    .bindTooltip(escapeHtml(tooltipRio(r.nombre, c, t, cauce)), { sticky: true, className: "tip" })
    .bindPopup(
      c
        ? popupEstacion(c, t, { nota: NOTA_CAUCE, vig })
        : popupHtml({ title: r.nombre, meta: [r.departamento], resumen: "ANA no tiene una medición reciente de la estación de este río.", nota: NOTA_CAUCE })
    )
    .addTo(group);
  if (r.guia_rotulo?.type === "LineString") {
    const guia = r.guia_rotulo.coordinates.map(([lon, lat]) => [lat, lon]);
    rotuloLinea(map, guia, r.nombre, { pane: "rioCauce", evitar: c?.lat != null ? [[c.lat, c.lon]] : [] }).addTo(group);
  }
}

// «Río Huallaga · tranquilo (938.54 m³/s, ANA)» / «... · aviso hidrológico naranja de SENAMHI (ANA,
// ayer 18:00: tranquilo, 938.54 m³/s)» / «... · sin medición»
function tooltipRio(nombre, c, t, cauce, estacionAviso = null) {
  const rot = c ? textoRotulo(c, t) : null;
  const cuando = (lecturaRio(c ?? {}) ?? "").replace(/\s*\(ANA\)$/, "");
  const ana = !c || c.valor == null ? null : `ANA${cuando ? `, ${cuando}` : ""}: ${rot.estado.toLowerCase()}, ${rot.valor}`;
  if (cauce.porAviso)
    return `${nombre} · aviso hidrológico ${cauce.color} de SENAMHI${estacionAviso ? ` en la estación ${estacionAviso}` : ""}${ana ? ` (${ana})` : ""}`;
  if (!c || c.valor == null) return `${nombre} · sin medición`;
  return `${nombre} · ${rot.estado.toLowerCase()} (${rot.valor}, ANA)`;
}

// ---------------------------------------------------------------------------
// Ríos del país con trazo de ANA (lib/cauces.js)
// ---------------------------------------------------------------------------

// Popup del trazo de un río del país: estado en palabras, la lectura y los niveles de ANA de la
// estación que manda, de dónde sale el trazo y que no hay mapa de zonas.
function popupCauce(rio, est) {
  const { fila, lecturas } = rio;
  const { cauce, zona } = est;
  const aviso = cauce.porAviso ? zona.avisoHidro : null;
  // con aviso, la estación que manda es la del aviso (si ANA la tiene); si no, la peor de ANA
  const deAviso = aviso ? lecturas.find((x) => avisoEsDeEstacion(aviso, x.estacion)) ?? null : null;
  const c = deAviso ?? est.peor;
  const t = deAviso ? textoRio(deAviso) : est.t;
  const estacionAviso = aviso ? estacionDelAviso(aviso, lecturas) : null;
  const sinAviso = aviso ? lecturas.filter((x) => x !== deAviso).map((x) => x.estacion) : [];
  const otras = aviso
    ? [
        `El aviso de SENAMHI es para la estación ${estacionAviso ?? "que nombra el aviso"}${deAviso?.departamento ? ` (${deAviso.departamento})` : ""}` +
          (sinAviso.length
            ? `; ${sinAviso.length === 1 ? "la otra estación de ANA en este río" : "las otras estaciones de ANA en este río"} (${lista(sinAviso, 4)}) no ${sinAviso.length === 1 ? "tiene" : "tienen"} aviso y ${sinAviso.length === 1 ? "se muestra" : "se muestran"} con su propia medición.`
            : "."),
        "SIMPAC resalta todo el trazo del río con el color del aviso; el aviso de SENAMHI no dice qué tramo abarca.",
      ]
    : lecturas.length > 1
      ? `Este río tiene ${lecturas.length} estaciones de ANA (${lista(lecturas.map((x) => x.estacion), 4)}); el trazo toma el estado de la peor.`
      : null;
  const trazo =
    `SIMPAC resalta el cauce con el trazo de ${fila.fuente} (${licenciaCorta(fila.licencia)}); ` +
    (c
      ? `el nivel es de la estación ${c.estacion} de ANA.`
      : "ANA no tiene una estación de caudal en este río: el color es el del aviso hidrológico de SENAMHI.");
  return (
    popupHtml({
      title: fila.nombre,
      meta: [
        aviso ? `Aviso hidrológico ${cauce.color} (SENAMHI${estacionAviso ? `, estación ${estacionAviso}` : ""})` : t ? t.etiqueta : "Sin estación de ANA",
        c ? `Estación ${c.estacion} (ANA)` : null,
        fila.departamento,
      ],
      resumen: aviso ? notaAviso(aviso, cauce.color) : t?.frase,
      filas: c ? filasAna(c, t) : [],
      nota: [
        aviso && t ? `Última medición de ANA en ${c.estacion}: ${t.frase}` : null,
        t?.accion,
        ...[otras].flat(),
        trazo,
        // fila.nota (avisos de la carga: "estación X a 614 m del trazo") es para quien carga, no
        // para el popup
        SIN_ZONAS,
      ],
      enlace: aviso && enlaceSeguro(aviso.url) ? { href: aviso.url, texto: "Ver el aviso de SENAMHI" } : { href: fila.fuente_url, texto: "Ver el servicio de ANA (GeoSNIRH)" },
    }) + (c ? enlaceHistorico(c) : "")
  );
}

// Halo y cauce de cada río del país (con el trazo de ~50 m; el fino lo pone seguirVista).
//   -> Map rio_ana -> { rio, est, halo, linea, detalle }
function dibujarNacionales(group, nacionales, estados) {
  const trazos = new Map();
  for (const rio of nacionales) {
    const id = rio.fila.rio_ana;
    const g = GEOMETRIAS.get(id);
    const est = estados.get(id);
    if (!g?.lejos.length || !est) continue;
    const fuerte = esFuerte(est);
    const clase = `rio-nac${fuerte ? " fuerte" : ""}`;
    const ll = aLatLngs(g.lejos);
    const halo = L.polyline(ll, {
      pane: "rios", interactive: false, className: `rio-halo ${clase}`, color: "#fff", weight: 13, opacity: 0.92,
    }).addTo(group);
    const linea = L.polyline(ll, {
      pane: "rioCauce", className: `rio-cauce ${clase}`, color: CAUCE_HEX[est.cauce.estado] ?? CAUCE_HEX.sd, weight: 6.5, opacity: 1,
    })
      .bindTooltip(
        escapeHtml(tooltipRio(rio.fila.nombre, est.peor, est.t, est.cauce, est.cauce.porAviso ? estacionDelAviso(est.zona.avisoHidro, rio.lecturas) : null)),
        { sticky: true, className: "tip" }
      )
      .bindPopup(() => popupCauce(rio, est)) // se arma recién al abrirlo
      .addTo(group);
    trazos.set(id, { rio, est, halo, linea, detalle: "lejos" });
  }
  return trazos;
}

// Sigue la vista mientras la capa esté encendida: desde zoom 13 pide el trazo fino de los ríos a
// la vista (y lo quita al alejarse); desde zoom 10 escribe el nombre de hasta 8 ríos a la vista.
// Es un L.layerGroup vacío dentro de `group`: al quitarlo (se apaga la capa o se vuelve a dibujar)
// suelta el evento y borra los nombres.
function seguirVista(group, map, trazos, estados) {
  const nacionales = [...trazos.values()].map((t) => t.rio);
  const rotulos = new Map(); // rio_ana -> { tramo, capa, zoom }
  let espera = 0;
  let vivo = false;

  const cajaVista = () => {
    const b = map.getBounds();
    return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
  };
  // La guía del nombre: el tramo simplificado a GUIA_PX píxeles con el zoom de ahora (Douglas-Peucker
  // de Leaflet, en píxeles). Con el trazo de ~50 m tal cual, los meandros reales del río giran más
  // de lo que rotuloLinea admite en cada 16 px y no quedaba lugar para ninguna letra; el Mashcón usa
  // para esto su guia_rotulo (~120 m, unos 6 px en zoom 13). Se rehace al cambiar el zoom.
  const guiaDe = (latlngs) =>
    L.LineUtil.simplify(latlngs.map((ll) => map.latLngToLayerPoint(ll)), GUIA_PX).map((p) => {
      const ll = map.layerPointToLatLng(p);
      return [ll.lat, ll.lng]; // rotuloLinea espera pares [lat, lon]
    });

  const aplicarDetalle = (t, detalle) => {
    const g = GEOMETRIAS.get(t.rio.fila.rio_ana);
    const partes = detalle === "cauce" ? g?.cauce : g?.lejos;
    if (!partes || t.detalle === detalle) return;
    const ll = aLatLngs(partes);
    t.halo.setLatLngs(ll);
    t.linea.setLatLngs(ll);
    t.detalle = detalle;
  };

  const pedirDetalle = (t) => {
    if (t.pidiendo) return;
    t.pidiendo = true;
    getCauceRio(t.rio.fila.rio_ana)
      .then((cauce) => {
        guardarDetalle(t.rio.fila.rio_ana, cauce);
        if (vivo) pedir(); // ya está: la próxima revisión lo aplica si sigue a la vista
      })
      .catch((e) => console.error("capa rio: trazo fino", e))
      .finally(() => {
        t.pidiendo = false;
      });
  };

  const revisar = () => {
    if (!vivo) return;
    const zoom = map.getZoom();
    const caja = cajaVista();
    const visibles = new Set(enVista(nacionales, caja));
    // detalle del trazo: fino solo a la vista y de cerca
    const detalle = detallePorZoom(zoom);
    for (const t of trazos.values()) {
      const quiere = detalle === "cauce" && visibles.has(t.rio) ? "cauce" : "lejos";
      if (quiere === "cauce" && !GEOMETRIAS.get(t.rio.fila.rio_ana)?.cauce) pedirDetalle(t);
      else aplicarDetalle(t, quiere);
    }
    // nombres sobre la línea
    const elegidos = zoom >= ROTULOS_DESDE ? elegirRotulados([...visibles], caja, estados) : [];
    const quedan = new Set();
    const margen = cajaConMargen(caja, 0.3);
    for (const { rio, tramo } of elegidos) {
      const id = rio.fila.rio_ana;
      quedan.add(id);
      const previo = rotulos.get(id);
      if (previo && previo.zoom === zoom && tramoCubre(previo.tramo, tramo)) continue; // sigue cubriendo lo visible
      if (previo) group.removeLayer(previo.capa);
      const g = GEOMETRIAS.get(id);
      const ext = extenderTramo(g.lejos, tramo, margen);
      const capa = rotuloLinea(map, guiaDe(latLngsTramo(g.lejos, ext)), rio.fila.nombre, {
        pane: "rioCauce",
        repetir: 1,
        clase: "rio-nombre nac",
        evitar: rio.lecturas.filter((c) => c.lat != null && c.lon != null).map((c) => [c.lat, c.lon]),
      }).addTo(group);
      rotulos.set(id, { tramo: ext, capa, zoom });
    }
    for (const [id, r] of rotulos) {
      if (quedan.has(id)) continue;
      group.removeLayer(r.capa); // del grupo, no solo del mapa: si no, volvería al encender la capa
      rotulos.delete(id);
    }
  };

  const pedir = () => {
    clearTimeout(espera);
    espera = setTimeout(revisar, ESPERA_VISTA_MS);
  };
  const gancho = L.layerGroup();
  gancho.on("add", () => {
    vivo = true;
    map.on("moveend", pedir);
    revisar();
  });
  gancho.on("remove", () => {
    vivo = false;
    map.off("moveend", pedir);
    clearTimeout(espera);
    for (const r of rotulos.values()) r.capa.remove(); // el grupo ya se está vaciando o quitando
    rotulos.clear();
  });
  gancho.addTo(group);
}

export default {
  id: "rio",
  grupo: "Ríos y estaciones",
  label: "Ríos",
  Icon: Waves,
  defaultVisible: true,
  refreshMs: 10 * 60_000, // la ingesta es horaria
  legend: [
    { forma: "rio", color: RIO_HEX.normal, label: "Tranquilo" },
    { forma: "rio", color: RIO_HEX.atento, label: "Cerca del nivel de alerta (criterio SIMPAC)" },
    { forma: "rio", color: RIO_HEX.alerta, label: "Pasó el nivel de alerta" },
    { forma: "rio", color: RIO_HEX.emergencia, label: "Pasó el nivel de emergencia" },
    { forma: "rio", color: RIO_HEX.sd, label: "Sin nivel de alerta publicado" },
    {
      forma: "linea",
      color: CAUCE_HEX.normal,
      label:
        "Río resaltado con su trazo: azul si está tranquilo; si no, el color de su estación (la peor, si tiene varias) o del aviso hidrológico de SENAMHI. El Mashcón tiene además mapa de zonas",
    },
    { forma: "linea", color: CAUCE_HEX.alerta, label: "Naranja o rojo: el río pasó su nivel de alerta o de emergencia (ANA), o hay aviso hidrológico de SENAMHI" },
    { forma: "linea", color: CAUCE_HEX.sd, label: "Gris fino: con el mapa en vista país (zoom 6 o menos), los ríos sin alerta; o sin nivel de alerta publicado" },
    { forma: "linea", color: "#0F4C81", punteado: true, label: "Límite de la faja marginal aprobada por ANA (desde zoom 14)" },
  ],
  fuente:
    "Ríos: niveles de ANA. Trazo de los ríos del país: ANA - GeoSNIRH (red hidrográfica R.J. 056-2018-ANA o Carta Nacional del IGN). " +
    "Trazo del Mashcón: © colaboradores de OpenStreetMap (ODbL). Faja marginal: ANA - DSNIRH.",
  load: () =>
    Promise.all([
      getCaudales(),
      opcional(getRiosVigilados()),
      opcional(getZonasRio()),
      opcional(getSenalesRio()),
      opcional(getCaucesRios(), "ríos del país"),
      opcional(getSenalesCauces(), "avisos de los ríos del país"),
    ]).then(([caudales, rios, zonas, senales, cauces, senalesCauces]) => ({
      caudales,
      rios: rios ?? [],
      fajas: zonas?.filter((z) => z.tipo === "faja") ?? [],
      senales: senales ?? [],
      // las geometrías quedan en lib/cauces.js GEOMETRIAS; null = la vista aún no existe
      cauces: cauces ? aligerar(cauces) : null,
      senalesCauces: senalesCauces ?? [],
    })),
  render(group, { caudales, rios, fajas, senales = [], cauces = null, senalesCauces = [] }, { map, acomodo }) {
    // simulación (solo en desarrollo, ?simular=...): la fila de ANA de un río vigilado cambia
    const reemplazo = new Map();
    const vigilados = new Map(); // fila de ANA -> {rio, estado, cauce}
    let simulada = false;
    for (const r of rios) {
      const c0 = caudalDelRio(r, caudales);
      const sim = conSimulacion({ rio: r, caudal: c0, senal: senales.find((s) => s.rio === r.id) ?? null });
      simulada ||= sim.activa;
      if (sim.activa && c0) reemplazo.set(c0, sim.caudal);
      const c = c0 ? reemplazo.get(c0) ?? c0 : null;
      const estado = estadoZona({ caudal: c, senal: sim.senal });
      const vig = { rio: r, estado, cauce: estadoCauce(c ? textoRio(c) : null, estado.avisoHidro) };
      if (c0) vigilados.set(c0, vig);
      dibujarRio(group, map, vig, c, fajas.filter((z) => z.rio === r.id));
    }

    // ríos del país con trazo (sin el Mashcón); uno con solo aviso de SENAMHI, mientras lo tenga
    const { rios: emparejados, sinTrazo } = emparejarCauces(cauces ?? [], caudales, rios);
    const estados = new Map(); // rio_ana -> estadoRio
    const nacionales = [];
    // fila de ANA -> {rio, estado, cauce}: la estación a la que se refiere el aviso hidrológico de
    // su río (solo esa: las demás estaciones del río no lo heredan)
    const conAviso = new Map();
    for (const rio0 of emparejados) {
      const id = rio0.fila.rio_ana;
      // simulación de un río del país (solo desarrollo, ?simular=rio:<rio_ana>:alerta|emergencia)
      const sim = simularCauce({ rioAna: id, lecturas: rio0.lecturas, avisos_hidro: avisosDe(senalesCauces, id) });
      simulada ||= sim.activa;
      const rio = sim.activa ? { ...rio0, lecturas: sim.lecturas } : rio0;
      const est = estadoRio({ lecturas: sim.lecturas, avisos_hidro: sim.avisos_hidro });
      if (!rio.lecturas.length && !est.zona.avisoHidro) continue;
      estados.set(id, est);
      nacionales.push(rio);
      if (est.cauce.porAviso)
        for (const c of rio.lecturas)
          if (avisoEsDeEstacion(est.zona.avisoHidro, c.estacion))
            conAviso.set(c, { rio: { nombre: rio.fila.nombre }, estado: est.zona, cauce: est.cauce });
      if (sim.activa) rio0.lecturas.forEach((c0, i) => sim.lecturas[i] !== c0 && reemplazo.set(c0, sim.lecturas[i]));
    }
    const trazos = dibujarNacionales(group, nacionales, estados);
    if (trazos.size) seguirVista(group, map, trazos, estados);

    for (const c0 of caudales) {
      const c = reemplazo.get(c0) ?? c0;
      if (c.lat == null || c.lon == null) continue;
      const t = textoRio(c);
      const vig = vigilados.get(c0) ?? null;
      // el disco de una estación de un río del país con aviso hidrológico más alto que su lectura
      // toma el color del aviso, como el del Mashcón (el cauce ya lo lleva)
      const ref = vig ?? conAviso.get(c0) ?? null;
      const porAviso = Boolean(ref?.cauce.porAviso);
      const estado = porAviso ? ref.cauce.estado : t.estado;
      const fuerte = porAviso
        ? estado === "alerta" || estado === "emergencia"
        : !t.bajo && (t.estado === "alerta" || t.estado === "emergencia");
      const rot0 = textoRotulo(c, t);
      // con aviso hidrológico: «Mashcón · Aviso rojo SENAMHI  ANA: 0.13 m³/s»
      const rot = porAviso
        ? { nombre: rot0.nombre, estado: `${CORTA_AVISO[ref.cauce.color]} SENAMHI`, valor: rot0.valor ? `ANA: ${rot0.valor}` : "" }
        : rot0;
      const corto = `${rot.nombre} · ${rot.estado}`;
      const m = L.marker([c.lat, c.lon], {
        icon: iconoRio({ estado, fuerte, rotulo: rot }),
        keyboard: true,
        zIndexOffset: fuerte ? 950 : 0,
        attribution: ATRIB_ANA, // la atribución del mapa dice "Datos: ... ANA" mientras haya estaciones
      })
        // el HTML del popup se arma recién al abrirlo (130 estaciones: armarlos todos costaba
        // más que dibujar los discos)
        .bindPopup(() => popupEstacion(c, t, { vig: ref }))
        .on("add", (e) =>
          e.target.getElement()?.setAttribute("aria-label", `${ref ? ref.rio.nombre : t.titulo}: ${porAviso ? rot.estado : t.etiqueta}`)
        )
        .addTo(group);
      // un río vigilado (tiene mapa de zonas) va antes que una estación cualquiera; con señales en
      // su zona, más aún (siempre debajo de los fuertes, 950)
      const conSenales = vig && vig.estado.nivel !== "sin_senales";
      acomodo?.registrar(m, {
        tipo: "rio",
        fuerte,
        vigilado: Boolean(vig),
        prioridad: fuerte ? 950 : (vig ? 800 : 700) + (estado === "atento" || conSenales ? 50 : 0),
        departamento: c.departamento,
        rotulo: rot.valor ? `${corto} ${rot.valor}` : corto,
        rotuloCorto: corto,
      });
    }
    const nota =
      cauces == null
        ? "Los trazos de los ríos del país aún no están cargados: se ven solo las estaciones."
        : notaCauces({
            resaltados: trazos.size,
            fuertes: nacionales.filter((r) => esFuerte(estados.get(r.fila.rio_ana))).map((r) => r.fila.nombre),
            sinTrazo,
          });
    return simulada ? `${NOTA_SIMULACION} ${nota}` : nota;
  },
};
