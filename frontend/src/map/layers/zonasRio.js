import L from "leaflet";
import { ShieldAlert } from "lucide-react";
import {
  getCaucesRios, getCaucesZonas, getCaudales, getFranjaRio, getIncidentesRio, getRiosVigilados, getSenalesCauces, getSenalesRio, getZonasRio,
} from "@/lib/queries";
import { FRASES_RIO_PAIS, textoRio } from "@/lib/lenguaje";
import { TITULO_NIVEL, caudalDelRio, estadoZona, notaZonas } from "@/lib/zonaRio";
import {
  GEOMETRIAS, ZONAS_DESDE, aLatLngs, aligerar, avisosDe, cajaConMargen, emparejarCauces, esFuerte, estadoRio, licenciaCorta, notaAuras,
  notaZonasPais, riosParaZonas, zonasDeCauce,
} from "@/lib/cauces";
import { NOTA_SIMULACION, conSimulacion, simularCauce } from "@/lib/simulacion";
import { NIVEL_HEX, ZONA_HEX, ZONA_OSCURO } from "../palette";
import { enlaceSeguro, escapeHtml, popupHtml } from "../markers";
import { iconoLugar } from "../marcadores";
import { opcionesPopup, popupZonaRio } from "../popups";
import { rotuloLinea } from "../rotuloLinea";

// Zonas que un río vigilado podría afectar si se desborda (primero el Mashcón; vista rio_zona_mapa):
//   - la franja rayada: estimación de SIMPAC con el relieve (terreno bajo junto al río; Copernicus);
//   - las manchas lisas: el mapa de inundaciones del estudio INDECI-PNUD 2005, pasado a coordenadas.
// Ninguna es un mapa oficial vigente: marcan dónde mirar, no hasta dónde llegará el agua. Se pintan
// del nivel de la zona (lib/zonaRio.js: ANA, avisos hidrológicos y de lluvia de SENAMHI, lluvia
// medida en la cuenca), que siempre es el de hoy (no sigue el selector de día); sin señales, de azul
// (sigue siendo una zona que podría inundarse). Todas llevan borde blanco y trazo oscuro: ámbar,
// naranja y rojo son también los rellenos de las áreas de los avisos, y sin borde se perdían encima.
// Desde zoom 13 se ven los polígonos (con el aura suave debajo en zoom 13, donde aún miden pocos
// píxeles) y desde zoom 14 el rótulo «zona que podría inundarse» junto al río; con el mapa más
// alejado, si hay señales, un "aura" del color del nivel a lo largo del río (index.css:
// [data-zoom-banda]). Con aviso hidrológico, o el río en alerta o emergencia, se marcan los centros
// poblados que SENAMHI nombra en sus avisos del río.
//
// Ríos del país con trazo de ANA (vista rio_cauce_mapa, lib/cauces.js; el Mashcón no se repite):
//   - zonas estimadas (vista rio_cauce_zona_mapa, la genera el cargador de relieve: bajo_2m rayada y
//     bajo_3m lisa tenue, mismos estilos y colores que las del Mashcón por el estado del río,
//     lib/cauces.js estadoRio: azul sin señales, ámbar atentos, naranja alerta, rojo emergencia). Se
//     piden por los ríos cuya caja toca la vista desde zoom 12 (ZONAS_DESDE; nunca el país entero) y
//     se ven desde zoom 13 como las del Mashcón. Si la vista aún no existe o el río no tiene zonas,
//     no se dibuja nada y no falla.
//   - la franja de atención (rio_cauce_mapa.franja: banda de 60, 120 o 250 m a cada lado del trazo
//     según el largo del río) SOLO cuando el río está en alerta o emergencia: contorno punteado y
//     relleno muy suave del color del nivel, desde zoom 13 (antes mide 1-6 px; con el mapa alejado
//     queda el aura de siempre a lo largo del cauce). Es referencial: marca el entorno inmediato del
//     río a vigilar, NO es un mapa de inundación ni dice hasta dónde llegaría el agua.
//   - solo una estación SIN trazo que crece hasta su alerta o emergencia (dato ANA) sigue con el
//     círculo de 2,5 km alrededor. Un río muy bajo (vaciante) no enciende nada. Los centros poblados
//     que SENAMHI nombra solo se conocen para el Mashcón (rio_vigilado.lugares_aviso).
const RADIO_M = 2500;
const ACENTO = { atentos: 2, alerta: 3, emergencia: 4 };
const ESPERA_VISTA_MS = 150; // tras moveend, antes de pedir las zonas de los ríos a la vista
const MARGEN_VISTA = 0.2; // 20 % alrededor de la vista: un arrastre corto no vuelve a pedir
const minuscula = (t) => t.charAt(0).toLowerCase() + t.slice(1);
const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 1 });

// La señal que manda en un río del país y qué hacer: para el aura, la franja y las zonas.
function senalYAccion(est) {
  const { cauce, zona, t } = est;
  const aviso = cauce.porAviso ? zona.avisoHidro : null;
  const principal = zona.senales[0];
  const accion =
    zona.nivel === "emergencia"
      ? "Aléjate de la orilla, no cruces el río y sigue las indicaciones de Defensa Civil."
      : zona.nivel === "alerta"
        ? "Aléjate de la orilla y no cruces el río."
        : null;
  return { aviso, principal, accion, t };
}

// Popup del aura de un río del país: la señal que manda (ANA o el aviso de SENAMHI) y qué es el aura.
function popupAura(rio, est) {
  const { fila } = rio;
  const { cauce, peor } = est;
  const { aviso, principal, accion, t } = senalYAccion(est);
  return popupHtml({
    title: fila.nombre,
    meta: [aviso ? `Aviso hidrológico ${cauce.color} (SENAMHI)` : `${t?.etiqueta ?? "Sin estación de ANA"} (ANA)`, peor ? `Estación ${peor.estacion}` : null, fila.departamento],
    resumen: principal ? `${principal.titulo}. ${principal.texto}` : null,
    nota: [
      aviso && t ? `Última medición de ANA: ${t.frase}` : null,
      accion,
      "El aura marca el cauce que hay que vigilar, no hasta dónde llegaría el agua. Al acercarte (zoom 13) se ve la franja de atención junto al río y, si SIMPAC las estimó con el relieve, las zonas que podría afectar.",
      `Trazo del río: ${fila.fuente}.`,
    ],
    enlace: aviso && enlaceSeguro(aviso.url) ? { href: aviso.url, texto: "Ver el aviso de SENAMHI" } : null,
  });
}

// Popup de la franja de atención de un río del país (solo en alerta o emergencia).
function popupFranja(rio, est, anchoM) {
  const { fila } = rio;
  const { cauce, peor } = est;
  const { aviso, principal, accion, t } = senalYAccion(est);
  return popupHtml({
    title: `Franja de atención · ${minuscula(fila.nombre)}`,
    meta: [aviso ? `Aviso hidrológico ${cauce.color} (SENAMHI)` : `${t?.etiqueta ?? "Sin estación de ANA"} (ANA)`, peor ? `Estación ${peor.estacion}` : null, fila.departamento],
    resumen: principal ? `${principal.titulo}. ${principal.texto}` : null,
    nota: [
      accion,
      `${FRASES_RIO_PAIS.franjaPopup} Aquí mide ${anchoM} m a cada lado del trazo (según el largo del río).`,
      `Trazo del río: ${fila.fuente} (${licenciaCorta(fila.licencia)}).`,
      "Ante una emergencia sigue las indicaciones de Defensa Civil (INDECI).",
    ],
    enlace: aviso && enlaceSeguro(aviso.url) ? { href: aviso.url, texto: "Ver el aviso de SENAMHI" } : null,
  });
}

// Popup de una zona estimada de un río del país: qué es, el estado de hoy, método, fuente y licencia.
const QUE_ES = {
  bajo_2m: "Terreno que queda menos de 2 m por encima del río: si el río se desborda, es lo primero que podría inundarse.",
  bajo_3m: "Terreno entre 2 y 3 m por encima del río: podría inundarse con una crecida mayor; es la franja más incierta.",
};
function popupZonaPais(rio, est, z) {
  const { fila } = rio;
  const { cauce, zona, peor } = est;
  const { aviso, principal, accion, t } = senalYAccion(est);
  return popupHtml({
    title: `${z.subtipo === "bajo_2m" ? "Zona baja junto al río" : "Zona algo más alta"} · ${minuscula(fila.nombre)}`,
    meta: [
      TITULO_NIVEL[zona.nivel],
      aviso ? `aviso hidrológico ${cauce.color} (SENAMHI)` : t ? `${t.etiqueta} (ANA${peor ? `, ${peor.estacion}` : ""})` : null,
      z.area_km2 != null ? `${num(z.area_km2)} km²` : null,
      fila.departamento,
    ],
    resumen: QUE_ES[z.subtipo] ?? null,
    nota: [
      principal ? `${principal.titulo}. ${principal.texto}` : "Hoy el río no tiene señales de crecida: la zona sigue siendo una zona que podría inundarse.",
      accion,
      `${FRASES_RIO_PAIS.metodo}${z.metodo ? ` Método: ${z.metodo}.` : ""}`,
      z.fuente ? `Relieve: ${z.fuente}${z.licencia ? ` (${z.licencia})` : ""}.` : null,
      z.nota,
      z.atribucion,
      "Ante una emergencia sigue las indicaciones de Defensa Civil (INDECI).",
    ],
    enlace: aviso && enlaceSeguro(aviso.url) ? { href: aviso.url, texto: "Ver el aviso de SENAMHI" } : null,
  });
}

// Estilo de cada zona por su tipo y subtipo (null: no se dibuja). bajo_1m queda dentro de bajo_2m.
// `borde`: lleva debajo un borde blanco (ver arriba). bajo_3m (la franja exterior, más incierta)
// va lisa con el tono oscuro del nivel, que se distingue sobre el área de un aviso del mismo color.
function estilo(z, nivel) {
  const tenue = nivel === "sin_senales";
  if (z.tipo === "estimada" && z.subtipo === "bajo_3m")
    return { stroke: false, fillColor: ZONA_OSCURO[nivel], fillOpacity: tenue ? 0.12 : 0.2 };
  if (z.tipo === "estimada" && z.subtipo === "bajo_2m")
    return {
      borde: true, color: ZONA_OSCURO[nivel], weight: 2.5, opacity: 1,
      fillColor: `url(#simpac-rayado-${nivel})`, fillOpacity: 1,
    };
  if (z.tipo === "estudio" && z.subtipo === "menor")
    return {
      borde: true, color: ZONA_OSCURO[nivel], weight: 2.5, opacity: 1, dashArray: "3 3",
      fillColor: ZONA_HEX[nivel], fillOpacity: tenue ? 0.22 : 0.3,
    };
  if (z.tipo === "estudio" && z.subtipo === "mayor")
    return { borde: true, color: ZONA_OSCURO[nivel], weight: 2.5, opacity: 1, fillColor: ZONA_HEX[nivel], fillOpacity: tenue ? 0.4 : 0.5 };
  return null;
}

// Dibuja un polígono de zona (con su borde blanco debajo si corresponde) en `group`.
function dibujarZona(group, map, z, nivel, popup, clase = "") {
  const { borde, ...s } = estilo(z, nivel) ?? {};
  if (!s.fillColor) return;
  const op = opcionesPopup(map, { acento: ACENTO[nivel] });
  // borde blanco debajo: se lee también sobre el área de un aviso del mismo color
  if (borde)
    L.geoJSON(z.geojson, {
      pane: "zonaRio",
      interactive: false,
      style: { className: `zona-pol${clase}`, color: "#fff", weight: 5.5, opacity: 0.95, fill: false },
    }).addTo(group);
  L.geoJSON(z.geojson, { pane: "zonaRio", style: { className: `zona-pol${clase}`, ...s } })
    .bindPopup(popup, op)
    .addTo(group);
}

// Sigue la vista mientras la capa esté encendida: desde zoom 12 pide (una vez por río, caché de
// lib/queries.js) y dibuja las zonas estimadas de los ríos del país cuya caja toca la vista. Es un
// L.layerGroup vacío dentro de `group`: al quitarlo (se apaga la capa o se vuelve a dibujar) suelta
// el evento. `alCambiar(conZonas)` avisa qué ríos tienen zonas para la nota de la capa.
function seguirZonas(group, map, nacionales, estados, alCambiar) {
  const pedidos = new Set(); // rio_ana ya pedidos (con o sin zonas)
  const conZonas = []; // nombres de los ríos con zonas dibujadas
  let espera = 0;
  let vivo = false;

  const revisar = async () => {
    if (!vivo) return;
    const b = map.getBounds();
    const caja = cajaConMargen([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], MARGEN_VISTA);
    const ids = riosParaZonas(nacionales, caja, map.getZoom()).filter((id) => !pedidos.has(id));
    if (!ids.length) return;
    for (const id of ids) pedidos.add(id);
    let filas;
    try {
      filas = await getCaucesZonas(ids);
    } catch (e) {
      console.error("capa zona: zonas de los ríos del país", e);
      for (const id of ids) pedidos.delete(id); // se vuelve a intentar al mover el mapa
      return;
    }
    if (!vivo || filas == null) return; // se apagó la capa, o la vista aún no existe: nada que dibujar
    const zonas = zonasDeCauce(filas);
    let nuevas = false;
    for (const rio of nacionales) {
      const id = rio.fila.rio_ana;
      if (!ids.includes(id)) continue;
      const deRio = zonas.filter((z) => z.rio === id);
      if (!deRio.length) continue;
      const est = estados.get(id);
      const nivel = est?.zona.nivel ?? "sin_senales";
      for (const z of deRio) dibujarZona(group, map, z, nivel, () => popupZonaPais(rio, est, z), " nac");
      conZonas.push(rio.fila.nombre);
      nuevas = true;
    }
    if (nuevas) alCambiar([...conZonas]);
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
  });
  gancho.addTo(group);
}

export default {
  id: "zona",
  grupo: "Alertas y avisos",
  label: "Zonas que un río podría afectar",
  Icon: ShieldAlert,
  defaultVisible: true,
  refreshMs: 5 * 60_000, // señales de lluvia y avisos: cada 5 min
  // la forma dice de dónde sale la zona (muestras en gris) y el color, el nivel de hoy
  legend: [
    { forma: "rayado", color: "#475569", label: "Rayada: zona que podría inundarse si el río se desborda (estimación SIMPAC con el relieve; también en los ríos del país que la tienen, desde zoom 13)" },
    { zona: true, color: "#475569", label: "Lisa: zona inundable según el estudio INDECI-PNUD 2005 (Mashcón); tenue: terreno algo más alto, estimación con el relieve" },
    { zona: true, color: ZONA_HEX.emergencia, label: "Rojo: el río pasó su nivel de emergencia (ANA) o hay aviso hidrológico rojo (SENAMHI)" },
    { zona: true, color: ZONA_HEX.alerta, label: "Naranja: pasó su nivel de alerta (ANA) o hay aviso hidrológico naranja" },
    { zona: true, color: ZONA_HEX.atentos, label: "Ámbar, atentos: señales de crecida o de lluvia fuerte en su cuenca" },
    { zona: true, color: ZONA_HEX.sin_senales, label: "Azul: zona que podría inundarse si el río se desborda, hoy sin señales de crecida" },
    { forma: "punto", color: "#0F172A", label: "Lugar que SENAMHI nombra como posible afectado (con aviso del río)" },
    {
      forma: "linea",
      color: ZONA_HEX.alerta,
      label: "Aura a lo largo del cauce (mapa alejado): río del país que pasó su nivel de alerta o de emergencia (ANA) o con aviso hidrológico de SENAMHI; marca el río a vigilar",
    },
    { forma: "franja", color: ZONA_HEX.alerta, label: `${FRASES_RIO_PAIS.franjaLeyenda}; solo con el río en alerta o emergencia, desde zoom 13` },
    { forma: "circulo", color: NIVEL_HEX.alerta, label: "Círculo: zona a vigilar alrededor de una estación en alerta cuyo río no tiene trazo cargado" },
  ],
  fuente:
    "Zona baja: estimación de SIMPAC con el relieve (Copernicus GLO-30 © DLR e.V. 2010-2014 y © Airbus Defence and " +
    "Space GmbH 2014-2018, provisto bajo COPERNICUS por la Unión Europea y la ESA); no es un mapa oficial de " +
    "inundación. Zona inundable: INDECI-PNUD (2005), digitalizado por SIMPAC. Señales: ANA y SENAMHI. Trazo del " +
    "Mashcón: © colaboradores de OpenStreetMap (ODbL). Trazo y franja de los ríos del país: ANA - GeoSNIRH (la franja " +
    "es una banda de ancho fijo junto al trazo, referencial).",
  load: () =>
    Promise.all([
      getCaudales(),
      getRiosVigilados(),
      getZonasRio(),
      getSenalesRio(),
      getIncidentesRio(),
      // los ríos del país son opcionales: si fallan quedan los círculos de antes
      getCaucesRios().catch((e) => (console.error("capa zona: ríos del país", e), null)),
      getSenalesCauces().catch((e) => (console.error("capa zona: avisos de los ríos del país", e), null)),
    ]).then(([caudales, rios, zonas, senales, incidentes, cauces, senalesCauces]) => ({
      caudales, rios, zonas, senales, incidentes,
      cauces: cauces ? aligerar(cauces) : null, // las geometrías quedan en lib/cauces.js GEOMETRIAS
      senalesCauces: senalesCauces ?? [],
    })),
  render(group, { caudales, rios, zonas, senales, incidentes, cauces = null, senalesCauces = [] }, { map, avisar }) {
    const vigilados = rios ?? [];
    const estados = [];
    let simulada = false;

    for (const r0 of vigilados) {
      const sim = conSimulacion({
        rio: r0,
        caudal: caudalDelRio(r0, caudales),
        senal: senales?.find((s) => s.rio === r0.id) ?? null,
      });
      simulada ||= sim.activa;
      const { rio: r, caudal } = sim;
      const estado = estadoZona({ caudal, senal: sim.senal });
      const { nivel } = estado;
      estados.push({ rio: r, estado });
      const deRio = (zonas ?? []).filter((z) => z.rio === r.id && z.tipo !== "faja");
      const inc = (incidentes ?? []).filter((i) => i.rio === r.id);
      const op = opcionesPopup(map, { acento: ACENTO[nivel] });
      const popup = (zona) => () => popupZonaRio({ rio: r, zona, estado, caudal, incidentes: inc });

      // con el mapa alejado la franja mide pocos píxeles: si hay señales, el aura a lo largo del río
      // (antes que los polígonos: en zoom 13 va debajo de ellos)
      if (nivel !== "sin_senales" && r.cauce) {
        const principal = deRio.find((z) => z.subtipo === "bajo_2m") ?? deRio[0] ?? null;
        L.geoJSON(r.cauce, {
          pane: "zonaRio",
          style: { className: "zona-aura", color: ZONA_HEX[nivel], opacity: 0.55, weight: 20 },
        })
          .bindPopup(popup(principal), op)
          .addTo(group);
      }

      for (const z of deRio) dibujarZona(group, map, z, nivel, popup(z));

      // «zona que podría inundarse» escrito junto al río, del lado de abajo (el nombre del río va
      // arriba), desde zoom 14: dice qué es la franja sin abrir la leyenda
      if (deRio.length && r.guia_rotulo?.type === "LineString") {
        const guia = r.guia_rotulo.coordinates.map(([lon, lat]) => [lat, lon]);
        const c = caudal?.lat != null ? [[caudal.lat, caudal.lon]] : [];
        rotuloLinea(map, guia, "zona que podría inundarse", {
          pane: "rioCauce", dy: 23, clase: `zona-nombre n-${nivel}`, repetir: 1, evitar: c,
        }).addTo(group);
      }

      // centros poblados que SENAMHI nombra en sus avisos del río (el punto marca el caserío)
      if (estado.avisoHidro || nivel === "alerta" || nivel === "emergencia") {
        for (const l of r.lugares_aviso ?? []) {
          if (!l.mapa || l.lat == null || l.lon == null) continue;
          L.marker([l.lat, l.lon], { icon: iconoLugar(l.nombre), keyboard: true })
            .bindTooltip(escapeHtml(l.nombre), { className: "tip", direction: "top", offset: [0, -6] })
            .bindPopup(
              popupHtml({
                title: l.nombre,
                resumen: `SENAMHI lo nombra entre las «potenciales áreas de afectación» de sus avisos del ${minuscula(r.nombre)}.`,
                nota: "Punto del centro poblado (INEI/IGN/MINEDU): marca el caserío, no la zona afectada.",
              })
            )
            .addTo(group);
        }
      }
    }

    // ríos del país con trazo (sin el Mashcón): estado de hoy (con la simulación de desarrollo,
    // ?simular=rio:<rio_ana>:alerta); en alerta o emergencia, el aura a lo largo del cauce (trazo
    // de ~50 m: el aura es ancha, no hace falta el fino) y la franja de atención, que llega aparte
    const { rios: emparejados, sinTrazo } = emparejarCauces(cauces ?? [], caudales, vigilados);
    const nacionales = [];
    const estadosPais = new Map(); // rio_ana -> estadoRio
    const fuertes = [];
    const franjas = []; // nombres de los ríos con franja dibujada
    let conZonas = []; // nombres de los ríos con zonas estimadas dibujadas (seguirZonas)
    let notaBase = "";
    // la nota se completa después: la franja y las zonas llegan aparte
    const avisarNota = () => avisar?.(`${notaBase} ${notaZonasPais({ conZonas, franjas, sinVista: map.getZoom() < ZONAS_DESDE })}`.trim());
    for (const rio0 of emparejados) {
      const id = rio0.fila.rio_ana;
      const sim = simularCauce({ rioAna: id, lecturas: rio0.lecturas, avisos_hidro: avisosDe(senalesCauces, id) });
      simulada ||= sim.activa;
      const rio = sim.activa ? { ...rio0, lecturas: sim.lecturas } : rio0;
      const est = estadoRio({ lecturas: sim.lecturas, avisos_hidro: sim.avisos_hidro });
      const g = GEOMETRIAS.get(id);
      if (!g?.lejos.length || (!rio.lecturas.length && !est.zona.avisoHidro)) continue; // la capa `rio` tampoco lo resalta
      nacionales.push(rio);
      estadosPais.set(id, est);
      if (!esFuerte(est)) continue;
      const nivel = est.cauce.estado; // alerta | emergencia
      fuertes.push(rio.fila.nombre);
      const aura = L.polyline(aLatLngs(g.lejos), { pane: "zonaRio", className: "zona-aura nac", color: ZONA_HEX[nivel], opacity: 0.55, weight: 20 })
        .bindPopup(() => popupAura(rio, est), opcionesPopup(map, { acento: ACENTO[nivel] }))
        .addTo(group);
      // la franja de atención (rio_cauce_mapa.franja) se pide por río solo aquí: si falla o la vista
      // aún no la trae, queda el aura
      getFranjaRio(id)
        .then((f) => {
          if (!f?.franja || !map.hasLayer(group)) return;
          L.geoJSON(f.franja, {
            pane: "zonaRio",
            style: { className: "zona-franja nac", color: ZONA_OSCURO[nivel], weight: 1.5, opacity: 0.9, dashArray: "6 4", fillColor: ZONA_HEX[nivel], fillOpacity: 0.1 },
          })
            .bindPopup(() => popupFranja(rio, est, f.ancho_m), opcionesPopup(map, { acento: ACENTO[nivel] }))
            .addTo(group);
          aura.getElement()?.classList.add("con-franja"); // en zoom 13 la franja reemplaza al aura
          franjas.push(rio.fila.nombre);
          avisarNota();
        })
        .catch((e) => console.error("capa zona: franja del río", e));
    }

    // zonas estimadas de los ríos del país: por los ríos a la vista, desde zoom 12
    if (nacionales.length)
      seguirZonas(group, map, nacionales, estadosPais, (nombres) => {
        conZonas = nombres;
        avisarNota();
      });

    // estaciones sin trazo del río (ni mapa de zonas): el círculo alrededor de la estación crecida
    // en alerta o emergencia (no se toca: el clic va al disco del río o al aviso de abajo)
    for (const c of sinTrazo) {
      const t = textoRio(c); // se recalcula aquí: no se confía en filas viejas
      if (t.bajo || (t.estado !== "alerta" && t.estado !== "emergencia")) continue;
      const col = NIVEL_HEX[t.estado];
      L.circle([c.lat, c.lon], {
        radius: RADIO_M,
        color: col,
        weight: 1,
        fillColor: col,
        fillOpacity: 0.18,
        interactive: false,
      }).addTo(group);
    }

    const nota = [
      rios == null || zonas == null ? "Las zonas del río Mashcón aún no están cargadas." : notaZonas(estados),
      notaAuras(fuertes),
    ]
      .filter(Boolean)
      .join(" ");
    notaBase = simulada ? `${NOTA_SIMULACION} ${nota}` : nota;
    return `${notaBase} ${notaZonasPais({ conZonas, franjas, sinVista: map.getZoom() < ZONAS_DESDE })}`.trim();
  },
};
