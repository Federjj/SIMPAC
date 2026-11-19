package pe.simpac.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException

/**
 * Una peticion HTTP ya armada (metodo, direccion, cabeceras y cuerpo). Las escrituras de la app
 * (Auth, reportes, votos, comentarios, fotos) se construyen como PeticionHttp y se mandan por un
 * TransporteHttp: en la app es OkHttp; en las pruebas JVM, un transporte simulado que solo guarda
 * lo que recibio y responde lo que la prueba diga. Asi se prueban cuerpos y cabeceras sin red.
 */
data class PeticionHttp(
    val metodo: String,
    val url: String,
    val cabeceras: Map<String, String> = emptyMap(),
    val cuerpo: ByteArray? = null,
    val tipoContenido: String? = null,
) {
    val cuerpoTexto: String? get() = cuerpo?.toString(Charsets.UTF_8)
}

data class RespuestaHttp(val codigo: Int, val cuerpo: String) {
    val ok: Boolean get() = codigo in 200..299
}

fun interface TransporteHttp {
    /** Manda la peticion y devuelve el codigo y el cuerpo; lanza ErrorConsulta solo si no hubo respuesta (sin red). */
    suspend fun enviar(p: PeticionHttp): RespuestaHttp
}

/** Transporte real: el mismo OkHttpClient de las lecturas (Http.cliente), TLS verificado, tiempos cortos. */
object TransporteOkHttp : TransporteHttp {
    const val SIN_RED = "No hay conexión. Revisa tu internet e inténtalo de nuevo."

    override suspend fun enviar(p: PeticionHttp): RespuestaHttp = withContext(Dispatchers.IO) {
        val tipo = (p.tipoContenido ?: "application/json").toMediaType()
        val cuerpo = when {
            p.cuerpo != null -> p.cuerpo.toRequestBody(tipo)
            p.metodo == "GET" || p.metodo == "DELETE" -> null
            else -> ByteArray(0).toRequestBody(tipo)   // OkHttp exige cuerpo en POST/PUT/PATCH
        }
        val peticion = Request.Builder().url(p.url).method(p.metodo, cuerpo).apply {
            header("Accept", "application/json")
            header("User-Agent", "SIMPAC-Android")
            p.cabeceras.forEach { (k, v) -> header(k, v) }
        }.build()
        try {
            Http.cliente.newCall(peticion).execute().use { r -> RespuestaHttp(r.code, r.body?.string() ?: "") }
        } catch (e: IOException) {
            throw ErrorConsulta(SIN_RED, e)
        }
    }
}
