package pe.simpac.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Error de una consulta con el mensaje en lenguaje claro para la pantalla. */
class ErrorConsulta(mensaje: String, causa: Throwable? = null) : IOException(mensaje, causa)

/** Cliente HTTP unico de la app (OkHttp): solo GET, tiempos cortos, TLS siempre verificado. */
object Http {
    val cliente: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .callTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    /** GET que devuelve el cuerpo como texto; lanza ErrorConsulta con un mensaje legible. */
    suspend fun get(url: HttpUrl, cabeceras: Map<String, String> = emptyMap()): String = withContext(Dispatchers.IO) {
        val peticion = Request.Builder().url(url).get().apply {
            cabeceras.forEach { (k, v) -> header(k, v) }
            header("Accept", "application/json")
            header("User-Agent", "SIMPAC-Android")
        }.build()
        try {
            cliente.newCall(peticion).execute().use { respuesta ->
                val cuerpo = respuesta.body?.string() ?: ""
                if (!respuesta.isSuccessful) {
                    throw ErrorConsulta("El servidor respondió ${respuesta.code} (${url.host})")
                }
                cuerpo
            }
        } catch (e: ErrorConsulta) {
            throw e
        } catch (e: IOException) {
            throw ErrorConsulta("No se pudo conectar con ${url.host}", e)
        }
    }
}

/**
 * API REST de Supabase (PostgREST) con la publishable key: solo lectura de las tablas y vistas
 * publicas (la RLS decide que se ve). Los filtros son los de PostgREST: "eq.Cajamarca", "gte.-7.5".
 */
class ClienteSupabase(private val urlBase: String, private val clave: String) {
    val configurado: Boolean get() = urlBase.isNotBlank() && clave.isNotBlank()

    fun url(tabla: String, params: Map<String, String>): HttpUrl {
        val base = urlBase.trimEnd('/').toHttpUrlOrNull()
            ?: throw ErrorConsulta("La dirección de Supabase no es válida")
        val b = base.newBuilder().addPathSegments("rest/v1/$tabla")
        params.forEach { (k, v) -> b.addQueryParameter(k, v) }
        return b.build()
    }

    suspend fun get(tabla: String, params: Map<String, String>): String {
        if (!configurado) throw ErrorConsulta("Falta la dirección o la llave pública de Supabase")
        return Http.get(url(tabla, params), mapOf("apikey" to clave, "Authorization" to "Bearer $clave"))
    }
}

/** API de solo lectura de SIMPAC (FastAPI): GET /health y GET /api/snapshot. */
class ClienteApi {
    fun urlSnapshot(apiBase: String): HttpUrl =
        (apiBase.trimEnd('/') + "/api/snapshot").toHttpUrlOrNull()
            ?: throw ErrorConsulta("La dirección de la API no es válida: $apiBase")

    suspend fun snapshot(apiBase: String): String = Http.get(urlSnapshot(apiBase))
}
