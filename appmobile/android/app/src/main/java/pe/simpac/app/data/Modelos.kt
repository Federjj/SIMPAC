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
    val url: String? = null,
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
