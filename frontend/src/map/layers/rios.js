import L from "leaflet";
import { Waves } from "lucide-react";
import { getCaudales, getRiosVigilados, getSenalesRio, getZonasRio } from "@/lib/queries";
import { lecturaRio, textoRio } from "@/lib/lenguaje";
import { caudalDelRio, diaHora, estadoCauce, estadoZona } from "@/lib/zonaRio";
import { NOTA_SIMULACION, conSimulacion } from "@/lib/simulacion";
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
const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });
const minuscula = (t) => t.charAt(0).toLowerCase() + t.slice(1);
const NOTA_CAUCE =
  "Las franjas junto al río marcan la zona que podría afectar si se desborda (capa «Zonas que un río podría afectar»).";
// "2021-01-11" -> "11/01/2021"
const fechaCorta = (f) => (/^\d{4}-\d{2}-\d{2}$/.test(f ?? "") ? f.split("-").reverse().join("/") : f);
const CORTA_AVISO = { amarillo: "Aviso amarillo", naranja: "Aviso naranja", rojo: "Aviso rojo" };

// Un río vigilado que falla no deja el mapa sin estaciones (MapView reintenta solo si falla todo).
const opcional = (p) =>
  p.catch((e) => {
    console.error("capa rio: ríos vigilados", e);
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

// Popup de una estación. `vig` (solo la de un río vigilado): {rio, estado, cauce} para titularlo
// con el nombre del río y, si hay aviso hidrológico, decirlo primero.
function popupEstacion(c, t, { nota, vig } = {}) {
  const umbral = (etiqueta, v) => [
    `${t.bajo ? `${etiqueta} por nivel bajo` : etiqueta}`,
    v != null ? `${num(v)} ${c.unidad}` : null,
  ];
  const aviso = vig?.cauce.porAviso ? vig.estado.avisoHidro : null;
  return popupHtml({
    title: vig ? vig.rio.nombre : t.titulo,
    meta: [
      aviso ? `Aviso hidrológico ${vig.cauce.color} (SENAMHI)` : t.etiqueta,
      vig ? `Estación ${c.estacion} (ANA)` : null,
      c.departamento,
    ],
    resumen: aviso ? notaAviso(aviso, vig.cauce.color) : t.frase,
    filas: [umbral("Nivel de alerta", t.ua), umbral("Nivel de emergencia", t.ue), ["Medido", lecturaRio(c)]],
    nota: [aviso ? `Última medición de ANA: ${t.frase}` : null, t.accion, nota],
    enlace: aviso && enlaceSeguro(aviso.url) ? { href: aviso.url, texto: "Ver el aviso de SENAMHI" } : null,
  });
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
  const rot = c ? textoRotulo(c, t) : null;
  // "ANA, ayer 18:00: tranquilo, 0.13 m³/s"
  const cuando = (lecturaRio(c ?? {}) ?? "").replace(/\s*\(ANA\)$/, "");
  const ana = !c || c.valor == null ? null : `ANA${cuando ? `, ${cuando}` : ""}: ${rot.estado.toLowerCase()}, ${rot.valor}`;
  const tooltip = cauce.porAviso
    ? `${r.nombre} · aviso hidrológico ${cauce.color} de SENAMHI${ana ? ` (${ana})` : ""}`
    : !c || c.valor == null
      ? `${r.nombre} · sin medición`
      : `${r.nombre} · ${rot.estado.toLowerCase()} (${rot.valor}, ANA)`;
  L.geoJSON(r.cauce, { pane: "rioCauce", style: { className: "rio-cauce", color, weight: 6.5, opacity: 1 } })
    .bindTooltip(escapeHtml(tooltip), { sticky: true, className: "tip" })
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
        "Río resaltado (tiene mapa de zonas): azul si está tranquilo; si no, el color de su estación o del aviso hidrológico de SENAMHI",
    },
    { forma: "linea", color: "#0F4C81", punteado: true, label: "Límite de la faja marginal aprobada por ANA (desde zoom 14)" },
  ],
  fuente: "Ríos: niveles de ANA. Trazo del río: © colaboradores de OpenStreetMap (ODbL). Faja marginal: ANA - DSNIRH.",
  load: () =>
    Promise.all([getCaudales(), opcional(getRiosVigilados()), opcional(getZonasRio()), opcional(getSenalesRio())]).then(
      ([caudales, rios, zonas, senales]) => ({
        caudales,
        rios: rios ?? [],
        fajas: zonas?.filter((z) => z.tipo === "faja") ?? [],
        senales: senales ?? [],
      })
    ),
  render(group, { caudales, rios, fajas, senales = [] }, { map, acomodo }) {
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

    for (const c0 of caudales) {
      const c = reemplazo.get(c0) ?? c0;
      if (c.lat == null || c.lon == null) continue;
      const t = textoRio(c);
      const vig = vigilados.get(c0) ?? null;
      const porAviso = Boolean(vig?.cauce.porAviso);
      const estado = porAviso ? vig.cauce.estado : t.estado;
      const fuerte = porAviso
        ? estado === "alerta" || estado === "emergencia"
        : !t.bajo && (t.estado === "alerta" || t.estado === "emergencia");
      const rot0 = textoRotulo(c, t);
      // con aviso hidrológico: «Mashcón · Aviso rojo SENAMHI  ANA: 0.13 m³/s»
      const rot = porAviso
        ? { nombre: rot0.nombre, estado: `${CORTA_AVISO[vig.cauce.color]} SENAMHI`, valor: rot0.valor ? `ANA: ${rot0.valor}` : "" }
        : rot0;
      const corto = `${rot.nombre} · ${rot.estado}`;
      const m = L.marker([c.lat, c.lon], {
        icon: iconoRio({ estado, fuerte, rotulo: rot }),
        keyboard: true,
        zIndexOffset: fuerte ? 950 : 0,
      })
        .bindPopup(popupEstacion(c, t, { vig }))
        .on("add", (e) =>
          e.target.getElement()?.setAttribute("aria-label", `${vig ? vig.rio.nombre : t.titulo}: ${porAviso ? rot.estado : t.etiqueta}`)
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
    return simulada ? NOTA_SIMULACION : null;
  },
};
