package pe.simpac.app.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement

/**
 * Modelos de lo que lee la app. Los nombres de los campos son los de la BD (API REST de Supabase) y
 * del snapshot de la API, para no traducir nada. Todo campo que la BD pueda dejar nulo es nullable.
 */

/** Parser compartido: tolera campos nuevos y nulos en vez de romper la app con un cambio de la BD. */
val JsonSimpac: Json = Json {
    ignoreUnknownKeys = true
    isLenient = true
    coerceInputValues = true
    explicitNulls = false
}

/** titular_zona: el titular en lenguaje claro de un departamento (lo escribe la tarea 'titular'). */
@Serializable
data class TitularZona(
    val departamento: String,
    val nivel: String,
    val titular_corto: String? = null,
    val titular: String? = null,
    val detalle: String? = null,
    val generado_en: String? = null,
    val revisado_en: String? = null,   // ultima corrida que confirmo que sigue vigente (frescura)
    val origen: String? = null,
)

/** alerta_actual: una alerta vigente (o la lluvia medida, que no es oficial). */
@Serializable
data class AlertaActual(
    val tipo: String? = null,
    val referencia: String? = null,
    val zona: String? = null,
    val nivel: String? = null,
    val detalle: String? = null,
    val valor: Double? = null,
    val umbral: Double? = null,
    val ventana_h: Int? = null,
    val ts: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
    val oficial: Boolean? = null,   // solo en el snapshot de la API
)

/** pronostico_vigente: un dia del pronostico oficial de SENAMHI para una localidad. */
@Serializable
data class PronosticoVigente(
    val codigo: String,
    val nombre: String? = null,
    val departamento: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
    val fecha: String? = null,
    val emision: String? = null,
    val tmax: Int? = null,
    val tmin: Int? = null,
    val texto: String? = null,
    val tipo: String? = null,
    val posible: Boolean = false,
    val lluvia_segura: Boolean = false,
    val intensidad: String? = null,
    val momento: String? = null,
    val cielo: String? = null,
    val url: String? = null,
)

/** punto_acudir: un establecimiento de salud, comisaria, compania de bomberos u oficina de Defensa Civil. */
@Serializable
data class PuntoAcudir(
    val clave: String,
    val tipo: String,
    val nombre: String,
    val categoria: String? = null,
    val atiende_24h: Boolean? = null,
    val direccion: String? = null,
    val distrito: String? = null,
    val provincia: String? = null,
    val departamento: String? = null,
    val telefono: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
    val fuente: String? = null,
    val fuente_url: String? = null,
    val atribucion: String? = null,
    val actualizado: String? = null,
)

/** Una fila de rio_cauce_mapa sin geometria: para saber que rios tiene un departamento. */
@Serializable
data class RioCauceResumen(
    val rio_ana: String,
    val nombre: String? = null,
    val departamento: String? = null,
)

/** Una lectura de caudal_actual dentro de rio_cauce_senal.lecturas. */
@Serializable
data class LecturaRio(
    val estacion: String? = null,
    val departamento: String? = null,
    val valor: Double? = null,
    val unidad: String? = null,
    val umbral_alerta: Double? = null,
    val umbral_emergencia: Double? = null,
    val estado: String? = null,
    val tendencia: String? = null,
    val fecha: String? = null,
    val hora: String? = null,
    val ts_captura: String? = null,
)

/** Un aviso hidrologico vigente dentro de rio_cauce_senal.avisos_hidro. */
@Serializable
data class AvisoHidro(
    val numero: Int? = null,
    val titulo: String? = null,
    val nivel: Int? = null,
    val sentido: String? = null,
    val inicio: String? = null,
    val fin: String? = null,
    val valor: Double? = null,
    val unidad: String? = null,
    val url: String? = null,
    val visto_en: String? = null,
)

/** rio_cauce_senal: las senales de hoy de un rio con trazo. */
@Serializable
data class RioCauceSenal(
    val rio_ana: String,
    val lecturas: List<LecturaRio> = emptyList(),
    val avisos_hidro: List<AvisoHidro> = emptyList(),
)

/** Una estacion de SENAMHI (tabla estacion): para saber en que departamento esta la persona. */
@Serializable
data class EstacionBreve(
    val departamento: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
)

/** GET /api/snapshot de la API de SIMPAC (backend/snapshot.py). */
@Serializable
data class ComunicadoEnfen(
    val anio: Int? = null,
    val numero: Int? = null,
    val extraordinario: Boolean = false,
    val fecha: String? = null,
    val estado: String? = null,
    val proximo: String? = null,
    val url: String? = null,
)

@Serializable
data class ResumenSnapshot(
    val caudales: Int = 0,
    val en_alerta: List<String> = emptyList(),
    val nivel_bajo: List<String> = emptyList(),
    val alertas: Int = 0,
    val alertas_oficiales: Int = 0,
    val lluvia_sobre_referencia: Int = 0,
)

@Serializable
data class CaudalSnapshot(
    val estacion: String? = null,
    val rio: String? = null,
    val departamento: String? = null,
    val fecha: String? = null,
    val hora: String? = null,
    val valor: Double? = null,
    val unidad: String? = null,
    val umbral_alerta: Double? = null,
    val umbral_emergencia: Double? = null,
    val tendencia: String? = null,
    val estado: String? = null,
)

@Serializable
data class Snapshot(
    val generado: String? = null,
    val enfen: ComunicadoEnfen? = null,
    val resumen: ResumenSnapshot? = null,
    val alertas: List<AlertaActual> = emptyList(),
    val caudales: List<CaudalSnapshot> = emptyList(),
    val indices: List<JsonElement> = emptyList(),
)

// ---------------------------------------------------------------------------
// Vistas del mapa nativo (pestana Mapa). La geometria llega como GeoJSON y queda en JsonElement:
// la convierte dominio/GeoJson.kt fuera del hilo principal.
// ---------------------------------------------------------------------------

/** Una insignia de un aviso (aviso_vigente.anclas): centro de cada parte grande del poligono. */
@Serializable
data class AnclaAviso(
    val lat: Double? = null,
    val lon: Double? = null,
    val parte: Int? = null,
    val km2: Double? = null,
    val mayor: Boolean = false,
    val radio_km: Double? = null,
)

/** aviso_vigente: un dia (mapa) de un aviso de SENAMHI que no ha terminado, con su area en GeoJSON. */
@Serializable
data class AvisoVigente(
    val id: Long,
    val tipo: String? = null,            // "meteorologico" o "lluvia24h"
    val anio: Int? = null,
    val numero: Int? = null,
    val mapa: Int? = null,
    val nivel: Int? = null,              // 2 amarillo, 3 naranja, 4 rojo
    val titulo: String? = null,
    val tema: String? = null,            // lluvia, temperatura, viento, otro
    val descripcion: String? = null,
    val inicio: String? = null,
    val fin: String? = null,
    val en_curso: Boolean = false,
    val departamentos: List<String> = emptyList(),
    val url: String? = null,
    val icono: String? = null,           // gota, gota_rayo, copo (lo calcula el worker)
    val texto_dia: String? = null,
    val anclas: List<AnclaAviso> = emptyList(),
    val geojson: JsonElement? = null,
)

/** caudal_actual: la ultima lectura de una estacion de rio de ANA con sus umbrales. */
@Serializable
data class CaudalActual(
    val estacion: String = "",
    val rio: String? = null,
    val departamento: String? = null,
    val fecha: String? = null,
    val hora: String? = null,
    val valor: Double? = null,
    val unidad: String? = null,
    val umbral_alerta: Double? = null,
    val umbral_emergencia: Double? = null,
    val tendencia: String? = null,
    val estado: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
)

/** rio_vigilado_mapa: un rio vigilado (hoy solo el Mashcon) con su cauce y afluentes en GeoJSON. */
@Serializable
data class RioVigiladoMapa(
    val id: String,
    val nombre: String? = null,
    val departamento: String? = null,
    val estacion_ana: String? = null,
    val rio_ana: String? = null,
    val centro_lat: Double? = null,
    val centro_lon: Double? = null,
    val zoom: Int? = null,
    val cauce: JsonElement? = null,
    val afluentes: JsonElement? = null,
    val fuentes: JsonElement? = null,
)

/** rio_zona_mapa: una zona que el rio vigilado podria afectar (estimada con el relieve o del estudio INDECI-PNUD). */
@Serializable
data class RioZonaMapa(
    val clave: String,
    val rio: String? = null,
    val tipo: String? = null,            // estimada, estudio, faja
    val subtipo: String? = null,         // bajo_2m, bajo_3m, menor, mayor
    val orden: Int? = null,
    val nombre: String? = null,
    val texto: String? = null,
    val fuente: String? = null,
    val fuente_url: String? = null,
    val licencia: String? = null,
    val atribucion: String? = null,
    val metodo: String? = null,
    val fecha_fuente: String? = null,
    val area_km2: Double? = null,
    val geojson: JsonElement? = null,
)

/** Un aviso de SENAMHI por lluvias que toca la cuenca de un rio vigilado (rio_senal.avisos_lluvia). */
@Serializable
data class AvisoLluviaSenal(
    val tipo: String? = null,
    val numero: Int? = null,
    val nivel: Int? = null,
    val en_curso: Boolean = false,
    val inicio: String? = null,
    val fin: String? = null,
    val url: String? = null,
)

/** Lluvia medida por una estacion de SENAMHI de la cuenca frente a su referencia (rio_senal.lluvia_cuenca). */
@Serializable
data class LluviaCuenca(
    val nombre: String? = null,
    val pp_1h: Double? = null,
    val pp_6h: Double? = null,
    val umbral_1h: Double? = null,
    val umbral_6h: Double? = null,
)

/** rio_senal: las senales de hoy de un rio vigilado. */
@Serializable
data class RioSenal(
    val rio: String,
    val avisos_lluvia: List<AvisoLluviaSenal> = emptyList(),
    val lluvia_cuenca: List<LluviaCuenca> = emptyList(),
    val avisos_hidro: List<AvisoHidro> = emptyList(),
)

/** rio_cauce_mapa: un rio del pais con el trazo de ANA simplificado a ~50 m (cauce_lejos). */
@Serializable
data class RioCauceMapa(
    val rio_ana: String,
    val rio: String? = null,
    val nombre: String? = null,
    val departamento: String? = null,
    val estaciones: List<String> = emptyList(),
    val km: Double? = null,
    val fuente: String? = null,
    val fuente_url: String? = null,
    val licencia: String? = null,
    val vigilado: Boolean = false,
    val cauce_lejos: JsonElement? = null,
)

/** rio_cauce_mapa (solo rio_ana y cauce): el trazo fino (~6 m) de un rio, pedido al acercarse. */
@Serializable
data class RioCauceDetalle(
    val rio_ana: String,
    val cauce: JsonElement? = null,
)

/** rio_cauce_zona_mapa: una zona estimada con el relieve de un rio del pais (bajo_2m o bajo_3m). */
@Serializable
data class RioCauceZonaMapa(
    val clave: String,
    val rio_ana: String,
    val subtipo: String? = null,
    val area_km2: Double? = null,
    val metodo: String? = null,
    val fuente: String? = null,
    val licencia: String? = null,
    val nota: String? = null,
    val atribucion: String? = null,
    val geojson: JsonElement? = null,
)

/** estacion: una estacion de SENAMHI (M meteorologica, H hidrologica) con su posicion. */
@Serializable
data class EstacionSenamhi(
    val cod: String,
    val nombre: String? = null,
    val tipo: String? = null,
    val estado: String? = null,
    val departamento: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
)
