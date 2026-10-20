import { supabase } from "./supabaseClient";
import { cache, cached, faltaColumna, filas, siExiste, todas } from "./consultaCache";

// Todas las lecturas usan la publishable key (lectura pública por RLS).
// Las que piden varias partes de la app a la vez (el panel y dos capas del mapa
// leen los caudales) pasan por cached(): una sola request cada TTL. cached, filas, todas y
// siExiste viven en lib/consultaCache.js (módulo puro, con pruebas sin red).

export function getEstaciones() {
  return cached("estaciones", () =>
    todas(() =>
      supabase.from("estacion").select("cod,nombre,tipo,estado,departamento,lat,lon").order("cod")
    ),
    10 * 60_000
  );
}

// Última lectura de cada estación, de ayer u hoy (vista caudal_actual; lectura_caudal
// es el historial).
export function getCaudales() {
  return cached("caudales", () =>
    filas(
      supabase
        .from("caudal_actual")
        .select("estacion,rio,departamento,fecha,hora,valor,unidad,umbral_alerta,umbral_emergencia,tendencia,estado,lat,lon")
    )
  );
}

// ICEN (IGP o ENFEN, el mes más nuevo), su estimado ICEN_TMP y el RONI de NOAA.
export function getIndices() {
  return cached("indices", () =>
    filas(supabase.from("indice").select("fuente,periodo,valor,categoria,origen"))
  );
}

// Último comunicado oficial del ENFEN (estado del Sistema de Alerta).
export async function getComunicadoENFEN() {
  const [c] = await cached("enfen", () =>
    filas(
      supabase
        .from("comunicado_enfen")
        .select("anio,numero,extraordinario,fecha,estado,proximo,resumen,url")
        .order("fecha", { ascending: false })
        .limit(1)
    ),
    10 * 60_000
  );
  return c ?? null;
}

// ICEN mes a mes (IGP y tabla del Informe Técnico ENFEN), los últimos `meses`, del más viejo
// al más nuevo: para el gráfico de El Niño.
export function getIcenSerie(meses = 24) {
  return cached(`icen_serie:${meses}`, async () =>
    (
      await filas(
        supabase.from("icen_serie").select("mes,valor,categoria,origen").order("mes", { ascending: false }).limit(meses)
      )
    ).reverse(),
    10 * 60_000
  );
}

// Avisos de SENAMHI que no han terminado (vista aviso_vigente), con el polígono en GeoJSON;
// ya vienen ordenados por nivel (el rojo al final, para dibujarlo encima). texto_dia, icono,
// lectura y anclas (íconos y lectura del texto oficial) son de la migración de íconos: si aún no
// está, se piden las columnas de antes (una sola vez por sesión) y el mapa va sin insignias.
const AVISO_V1 = "id,tipo,anio,numero,mapa,nivel,titulo,tema,descripcion,inicio,fin,en_curso,departamentos,url,geojson";
let avisosSinIconos = false;
export function getAvisosVigentes() {
  return cached(
    "avisos",
    async () => {
      const pedir = (cols) => filas(supabase.from("aviso_vigente").select(cols));
      if (avisosSinIconos) return pedir(AVISO_V1);
      try {
        return await pedir(`${AVISO_V1},texto_dia,icono,lectura,anclas`);
      } catch (e) {
        if (!faltaColumna(e)) throw e;
        avisosSinIconos = true;
        return pedir(AVISO_V1);
      }
    },
    5 * 60_000
  );
}

// Pronóstico oficial de SENAMHI por localidad, de hoy a pasado mañana (vista pronostico_vigente:
// solo localidades con punto y emisiones de los últimos 5 días). Lo leen el mapa, la franja de
// 3 días y el "cerca de" del nowcasting. null si la vista aún no existe.
export function getPronosticoVigente() {
  return cached(
    "pronostico",
    () =>
      siExiste(() =>
        todas(() =>
          supabase
            .from("pronostico_vigente")
            .select(
              "codigo,nombre,departamento,lat,lon,fecha,emision,tmax,tmin,texto,tipo,posible,por,lluvia_segura,granizo,intensidad,momento,cielo,url"
            )
            .order("codigo")
            .order("fecha")
        )
      ),
    10 * 60_000
  );
}

// Estado del nowcasting de SENAMHI por horizonte (0 = ahora, 60 y 120 min): emisión, validez y si
// sigue vigente (el umbral de 30 min vive en la vista). null si la vista aún no existe.
export function getNowcastEstado() {
  return cached(
    "nowcast_estado",
    () =>
      siExiste(() =>
        filas(
          supabase
            .from("nowcast_estado")
            .select("horizonte_min,fichero,emision,valido_desde,valido_hasta,manchas,ts_captura,vence_en,vigente")
        )
      ),
    60_000
  );
}

// Manchas del nowcasting de un horizonte, una por nivel (1 a 3), solo de una emisión vigente.
export function getNowcast(h) {
  return cached(
    `nowcast:${h}`,
    async () =>
      (await siExiste(() =>
        filas(
          supabase
            .from("nowcast_vigente")
            .select("horizonte_min,nivel,emision,valido_desde,valido_hasta,geojson")
            .eq("horizonte_min", h)
        )
      )) ?? [],
    60_000
  );
}

// Ríos vigilados (primero el Mashcón; vista rio_vigilado_mapa): el trazo del río, sus afluentes y la
// guía del nombre sobre la línea en GeoJSON, los lugares que SENAMHI nombra en sus avisos y las
// fuentes. Se cargan una vez (backend/mapas/cargar_rios.py): caché de 60 min. null si la vista aún
// no existe (migración pendiente).
export function getRiosVigilados() {
  return cached(
    "rios_vigilados",
    async () => {
      const r = await siExiste(() =>
        filas(
          supabase
            .from("rio_vigilado_mapa")
            .select(
              "id,nombre,departamento,estacion_ana,rio_ana,estacion_senamhi,centro_lat,centro_lon,zoom,cauce,afluentes,guia_rotulo,lugares_aviso,fuentes"
            )
        )
      );
      sinRios = r == null;
      return r;
    },
    60 * 60_000
  );
}

// Las otras vistas de los ríos vigilados llegan con la misma migración que rio_vigilado_mapa. Se
// piden a la vez que ella (no después: esperar su respuesta atrasaba las zonas unos 250 ms en cada
// apertura). Si la vista principal no existe, queda la bandera `sinRios` y las demás no insisten
// hasta que vuelva a pedirse (un pedido fallido por hora, no cuatro).
let sinRios = false;
const conRios = (fn) => (sinRios ? Promise.resolve(null) : siExiste(fn));

// Zonas que un río vigilado podría afectar (estimación por relieve, estudio INDECI-PNUD 2005) y la
// faja marginal de ANA, del fondo hacia arriba (`orden`). null si la vista aún no existe.
export function getZonasRio() {
  return cached(
    "zonas_rio",
    () =>
      conRios(() =>
        filas(
          supabase
            .from("rio_zona_mapa")
            .select(
              "clave,rio,tipo,subtipo,orden,nombre,texto,fuente,fuente_url,licencia,atribucion,metodo,fecha_fuente,area_km2,geojson"
            )
            .order("orden")
        )
      ),
    60 * 60_000
  );
}

// Desbordes y daños pasados documentados de los ríos vigilados (y sus crecidas medidas en rojo),
// del más nuevo al más viejo. null si la tabla aún no existe.
export function getIncidentesRio() {
  return cached(
    "incidentes_rio",
    () =>
      conRios(() =>
        filas(
          supabase
            .from("rio_incidente")
            .select(
              "id,rio,fecha,fecha_texto,tipo,titulo,lugar,detalle,precision,precision_texto,caudal_m3s,fuente_tipo,fuente,fuente_url,otras_fuentes,lat,lon"
            )
            .order("fecha", { ascending: false, nullsFirst: false })
        )
      ),
    60 * 60_000
  );
}

// Señales de hoy por río vigilado (vista rio_senal, una fila por río): avisos de lluvia que tocan su
// cuenca, lluvia medida en la cuenca y avisos hidrológicos vigentes de SENAMHI. El nivel de la zona
// lo decide lib/zonaRio.js. null si la vista aún no existe.
export function getSenalesRio() {
  return cached(
    "senales_rio",
    () => conRios(() => filas(supabase.from("rio_senal").select("rio,avisos_lluvia,lluvia_cuenca,avisos_hidro"))),
    5 * 60_000
  );
}

// Lluvia de la última hora en ~200 estaciones automáticas de SENAMHI en todo el país
// (vista lluvia_senamhi_actual: solo lecturas de las últimas 3 h), con la referencia de
// SENAMHI de cada estación en 1 h y en 6 h. La comparten el mapa y el panel de estado.
export function getLluviaAhora() {
  return cached(
    "lluvia_ahora",
    () =>
      filas(
        supabase
          .from("lluvia_senamhi_actual")
          .select("clave,nombre,departamento,provincia,distrito,pp_1h,umbral_1h,pp_6h,umbral_6h,medido_en,lat,lon")
      ),
    5 * 60_000
  );
}

// Cuándo corrió de verdad la ingesta (para avisar "sin actualizar" si se detiene).
export function getLatido() {
  return cached("latido", () => filas(supabase.from("latido").select("servicio,ts,resumen")));
}

// Lluvia horaria de las últimas 24 h de las estaciones de un departamento.
export function getLluvia24h(depto) {
  const desde = new Date(Date.now() - 24 * 3_600_000).toISOString();
  return cached(`lluvia:${depto}`, () =>
    filas(
      supabase
        .from("lectura_lluvia")
        .select("cod,medido_en,precip_mm,estacion!inner(nombre,departamento)")
        .eq("estacion.departamento", depto)
        .gte("medido_en", desde)
        .order("medido_en")
    )
  );
}

// Alertas vigentes, con su departamento en `zona` (ríos: ingesta; avisos: tarea avisos;
// lluvia: tarea lluvia_nacional). La vista alerta_actual ya deja fuera la lluvia medida
// hace más de 3 h; en la de lluvia, `valor` y `umbral` son los de la ventana `ventana_h`.
export function getAlertasVigentes() {
  return cached("alertas", () =>
    filas(
      supabase
        .from("alerta_actual")
        .select("tipo,referencia,zona,nivel,detalle,valor,umbral,ventana_h,ts")
        .order("ts", { ascending: false })
    )
  );
}

// Reportes ciudadanos vigentes (los más recientes primero). El filtro de vencidos lo
// hace la BD (RLS), no el reloj del celular. Columnas explícitas: `autor` no es legible.
export function getReportesVigentes() {
  return cached("reportes", () =>
    filas(
      supabase
        .from("report")
        .select("id,tipo,subtipo,descripcion,likes,dislikes,estado,creado_en,expira_en,lat,lon")
        .order("creado_en", { ascending: false })
        .limit(500)
    )
  );
}

// Capa de anomalías de precipitación (FeatureCollection GeoJSON en la tabla mapa).
export async function getMapaAnomalias() {
  const [m] = await filas(
    supabase
      .from("mapa")
      .select("titulo,variable,periodo,fuente,geojson")
      .eq("variable", "precipitacion")
      .order("periodo", { ascending: false }) // el mes más reciente
      .limit(1)
  );
  return m ?? null;
}

// Mapa de un evento El Niño pasado (variable 'FEN'; periodo = "1997-1998", "2017", ...).
// Son mapas fijos: se guardan en memoria toda la sesión.
export async function getMapaFEN(periodo) {
  const [m] = await cached(
    `fen:${periodo}`,
    () =>
      filas(
        supabase
          .from("mapa")
          .select("titulo,periodo,fuente,geojson")
          .eq("variable", "FEN")
          .eq("periodo", periodo)
          .limit(1)
      ),
    Infinity
  );
  return m ?? null;
}

// ---------------------------------------------------------------------------
// Páginas Alertas, Comunidad, Chat, Cuenta e Histórico (lecturas y, al final, las escrituras que
// necesitan sesión). Columnas siempre explícitas: `autor` de report y comentario y `geom` de
// message no son legibles.
// ---------------------------------------------------------------------------

// Alertas pasadas (tabla alerta, lectura pública): entre dos fechas de Perú (incluidas) y, si se
// pide, de una zona. Sin lat/lon: la página no los necesita. Hasta 500, las más nuevas primero.
export function getAlertasPasadas({ desde, hasta, zona = null } = {}) {
  let q = supabase
    .from("alerta")
    .select("id,tipo,referencia,zona,nivel,detalle,valor,umbral,ventana_h,vigente,ts")
    .gte("ts", `${desde}T00:00:00-05:00`)
    .lte("ts", `${hasta}T23:59:59-05:00`)
    .order("ts", { ascending: false })
    .limit(500);
  if (zona) q = q.eq("zona", zona);
  return filas(q);
}

// Reportes vigentes para la página Comunidad: como getReportesVigentes más la foto y la
// confianza (la calcula la BD con los votos). `fresco` salta la caché (tras votar o crear).
const COLS_REPORTE = "id,tipo,subtipo,descripcion,foto_url,likes,dislikes,confianza,estado,creado_en,expira_en,lat,lon";
export function getReportesComunidad({ fresco = false } = {}) {
  if (fresco) cache.delete("reportes_comunidad");
  return cached(
    "reportes_comunidad",
    () => filas(supabase.from("report").select(COLS_REPORTE).order("creado_en", { ascending: false }).limit(500)),
    60_000
  );
}

// Un reporte por id; null si no existe o ya venció (la RLS no lo entrega).
export async function getReporte(id) {
  const { data, error } = await supabase.from("report").select(COLS_REPORTE).eq("id", id).maybeSingle();
  if (error) throw error;
  return data ?? null;
}

// Comentarios de un reporte (lectura pública; sin autor), del más viejo al más nuevo.
export function getComentarios(reportId) {
  return filas(
    supabase.from("comentario").select("id,report_id,texto,creado_en").eq("report_id", reportId).order("creado_en").limit(200)
  );
}

// Mis votos sobre una lista de reportes (la RLS solo entrega los propios): { [report_id]: 1 | -1 }.
export async function getMisVotos(ids = []) {
  if (!ids.length) return {};
  const v = await filas(supabase.from("voto").select("report_id,valor").in("report_id", ids));
  return Object.fromEntries(v.map((x) => [x.report_id, x.valor]));
}

// Mensajes vigentes del chat de una zona (solo con sesión), del más viejo al más nuevo.
export function getMensajes(zona) {
  return filas(
    supabase
      .from("message")
      .select("id,autor,zona,contenido,expira_en,creado_en")
      .eq("zona", zona)
      .gt("expira_en", new Date().toISOString())
      .order("creado_en")
      .limit(300)
  );
}

// Histórico de una estación de río (lectura_caudal; una fila por fecha y hora) desde una fecha de
// Perú "AAAA-MM-DD". Por páginas: 30 días pueden pasar de 1000 filas si ANA publica cada hora.
export function getHistoricoCaudal({ estacion, rio = null, desde }) {
  return todas(() => {
    let q = supabase
      .from("lectura_caudal")
      .select("fecha,hora,valor,unidad,umbral_alerta,umbral_emergencia,tendencia,estado")
      .eq("estacion", estacion)
      .gte("fecha", desde)
      .order("fecha")
      .order("hora");
    if (rio) q = q.eq("rio", rio);
    return q;
  });
}

// Primera lectura guardada de una estación de río ("hay datos desde..."); null si no hay ninguna.
export async function getPrimeraLecturaCaudal({ estacion, rio = null }) {
  let q = supabase.from("lectura_caudal").select("fecha,hora").eq("estacion", estacion).order("fecha").order("hora").limit(1);
  if (rio) q = q.eq("rio", rio);
  const [f] = await filas(q);
  return f ?? null;
}

// Histórico de lluvia horaria (y temperatura) de una estación de SENAMHI desde un instante ISO.
export function getHistoricoLluvia({ cod, desdeIso }) {
  return todas(() =>
    supabase.from("lectura_lluvia").select("ts,medido_en,precip_mm,temp_c").eq("cod", cod).gte("medido_en", desdeIso).order("medido_en")
  );
}

export async function getPrimeraLecturaLluvia(cod) {
  const [f] = await filas(supabase.from("lectura_lluvia").select("medido_en").eq("cod", cod).order("medido_en").limit(1));
  return f ?? null;
}

// --- Escrituras de la comunidad (necesitan sesión; la BD valida y pone autor, fechas y límites).
// Devuelven { data, error } crudos: la página los traduce con lib/comunidad.js mensajeErrorBD.

// Crea un reporte y devuelve su id. geom es el EWKT del GPS (lib/comunidad.js ewkt).
export async function crearReporte({ tipo, subtipo = null, descripcion = null, foto_url = null, geom }) {
  const fila = { tipo, subtipo: subtipo || null, descripcion: descripcion || null, foto_url: foto_url || null, geom };
  const { data, error } = await supabase.from("report").insert(fila).select("id").single();
  cache.delete("reportes");
  cache.delete("reportes_comunidad");
  return { id: data?.id ?? null, error };
}

// Sube la foto al bucket público "reportes" dentro de la carpeta del usuario y devuelve su URL.
export async function subirFotoReporte(archivo, usuarioId) {
  const ruta = `${usuarioId}/${Date.now()}-${Math.random().toString(36).slice(2, 8)}.jpg`;
  const { error } = await supabase.storage.from("reportes").upload(ruta, archivo, { contentType: archivo.type || "image/jpeg", upsert: false });
  if (error) return { url: null, error };
  const { data } = supabase.storage.from("reportes").getPublicUrl(ruta);
  return { url: data?.publicUrl ?? null, error: null };
}

// Vota (1 a favor, -1 en contra) o cambia el voto; valor null lo quita.
export async function votar(reportId, valor) {
  const r =
    valor == null
      ? await supabase.from("voto").delete().eq("report_id", reportId)
      : await supabase.from("voto").upsert({ report_id: reportId, valor }, { onConflict: "report_id,autor" });
  cache.delete("reportes");
  cache.delete("reportes_comunidad");
  return { error: r.error };
}

export async function comentar(reportId, texto) {
  const { data, error } = await supabase.from("comentario").insert({ report_id: reportId, texto }).select("id,report_id,texto,creado_en").single();
  return { comentario: data ?? null, error };
}

export async function enviarMensaje(zona, contenido) {
  const { data, error } = await supabase.from("message").insert({ zona, contenido }).select("id,autor,zona,contenido,expira_en,creado_en").single();
  return { mensaje: data ?? null, error };
}

// Canal en tiempo real de los mensajes nuevos de una zona (la publicación supabase_realtime
// incluye message). Devuelve la función para cerrarlo. La página sondea además cada 10 s.
export function escucharMensajes(zona, alLlegar) {
  const canal = supabase
    .channel(`chat:${zona}`)
    .on("postgres_changes", { event: "INSERT", schema: "public", table: "message", filter: `zona=eq.${zona}` }, (p) => alLlegar(p.new))
    .subscribe();
  return () => supabase.removeChannel(canal);
}

// ---------------------------------------------------------------------------
// A dónde acudir (tabla punto_acudir: salud, comisarías, bomberos, Defensa Civil)
// ---------------------------------------------------------------------------

export const COLUMNAS_ACUDIR =
  "clave,tipo,nombre,categoria,atiende_24h,direccion,distrito,provincia,departamento,telefono,lat,lon,fuente,fuente_url,atribucion,actualizado,detalle";

// Puntos dentro de una caja de grados { oeste, sur, este, norte }, nunca la tabla entera (hay más
// de 11 000 establecimientos de salud en el país). La caja llega ya redondeada a 0,1 grados
// (lib/acudir.js cajaRedondeada), así la clave de la caché se repite al mover un poco el mapa; se
// guarda 60 min. Por páginas de 1000: alrededor de Lima una caja de 30 km pasa de 1500 filas.
export function getPuntosAcudirCaja({ oeste, sur, este, norte }) {
  const clave = `acudir:${oeste},${sur},${este},${norte}`;
  return cached(
    clave,
    () =>
      todas(() =>
        supabase
          .from("punto_acudir")
          .select(COLUMNAS_ACUDIR)
          .gte("lat", sur)
          .lte("lat", norte)
          .gte("lon", oeste)
          .lte("lon", este)
          .order("clave")
      ),
    60 * 60_000
  );
}

// ---------------------------------------------------------------------------
// Ríos del país con trazo (vista rio_cauce_mapa; backend/mapas/cargar_cauces.py desde ANA -
// GeoSNIRH). Los lee la capa `rio` (y `zona`, para el aura y el círculo): lib/cauces.js decide el
// color y el detalle; el Mashcón (rio_vigilado) no está aquí.
// ---------------------------------------------------------------------------

// Los ~100 ríos con su trazo simplificado a ~50 m (cauce_lejos, ~750 KB en total) para todo el
// país de una vez; el trazo fino (cauce) se pide por río con getCauceRio al acercarse. Carga única
// en la BD: caché de 60 min. null si la vista aún no existe.
export function getCaucesRios() {
  return cached(
    "cauces_rios",
    () =>
      siExiste(() =>
        filas(
          supabase
            .from("rio_cauce_mapa")
            .select(
              "rio_ana,rio,nombre,departamento,estaciones,estaciones_senamhi,capa,km,dist_estacion_m,nota,fuente,fuente_url,licencia,atribucion,fecha_fuente,vigilado,cauce_lejos"
            )
            .order("rio_ana")
        )
      ),
    60 * 60_000
  );
}

// Trazo fino (~6 m) de un río (GeoJSON MultiLineString o null): lo pide la capa `rio` solo para los
// ríos a la vista desde zoom 13. No cambia en la sesión.
export async function getCauceRio(rioAna) {
  const [f] = await cached(
    `cauce:${rioAna}`,
    () => filas(supabase.from("rio_cauce_mapa").select("rio_ana,cauce").eq("rio_ana", rioAna).limit(1)),
    Infinity
  );
  return f?.cauce ?? null;
}

// Avisos hidrológicos vigentes de SENAMHI por río con trazo (vista rio_cauce_senal; solo esa
// columna: las lecturas de ANA ya vienen en getCaudales). null si la vista aún no existe.
export function getSenalesCauces() {
  return cached(
    "senales_cauces",
    () => siExiste(() => filas(supabase.from("rio_cauce_senal").select("rio_ana,avisos_hidro"))),
    5 * 60_000
  );
}

// --- inicio-impacto: "Tu zona ahora" (components/TuZona.jsx, hooks/useZonaAhora.js) ---

// Titular interpretado del departamento (tabla titular_zona: lo escribe la tarea 'titular' del
// worker cada 30 min, con reglas fijas o un modelo de lenguaje validado). Es OPCIONAL: null si la
// tabla aún no existe, no hay fila o la consulta falla; la tarjeta usa entonces el titular
// determinista de lib/zonaAhora.js (titularCorto). Caché de 5 min.
export function getTitular(depto) {
  if (!depto) return Promise.resolve(null);
  return cached(
    `titular:${depto}`,
    () =>
      siExiste(async () => {
        const [f] = await filas(
          supabase
            .from("titular_zona")
            .select("departamento,titular,detalle,nivel,generado_en,revisado_en,origen")
            .eq("departamento", depto)
            .limit(1)
        );
        return f ?? null;
      }).catch((e) => {
        console.warn("titular_zona", e);
        return null;
      }),
    5 * 60_000
  );
}
