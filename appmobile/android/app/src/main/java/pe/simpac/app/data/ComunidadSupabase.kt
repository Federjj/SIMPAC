package pe.simpac.app.data

import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import pe.simpac.app.dominio.Comunidad

/**
 * Escrituras de la comunidad en Supabase con la sesion de la persona (PostgREST y Storage): crear
 * reporte, votar, comentar, subir la foto, mis reportes y el perfil propio. Replica las reglas de
 * frontend/src/lib/queries.js y lib/sesion.js. Cada peticion se arma en un `peticionX` (se prueba
 * en la JVM sin red) y se manda por el TransporteHttp. Los errores salen ya traducidos
 * (Comunidad.mensajeErrorBD) como ErrorConsulta.
 */
class ComunidadSupabase(
    private val urlBase: String,
    private val clave: String,
    private val transporte: TransporteHttp = TransporteOkHttp,
    private val token: suspend () -> String?,
) {
    companion object {
        const val COLS_REPORTE = "id,tipo,subtipo,descripcion,foto_url,likes,dislikes,confianza,estado,creado_en,expira_en,lat,lon"
        const val COLS_COMENTARIO = "id,report_id,texto,creado_en"
        const val BUCKET = "reportes"
        private val NO_ALFANUMERICO = Regex("[^A-Za-z0-9_-]")

        /** Nombre del archivo en el bucket: <uid>/<ms>-<aleatorio>.jpg (lo exige report_foto_url_check). */
        fun rutaFoto(uid: String, ahoraMs: Long = System.currentTimeMillis(), aleatorio: String = aleatorio()): String =
            "$uid/$ahoraMs-${NO_ALFANUMERICO.replace(aleatorio, "").take(12)}.jpg"

        private fun aleatorio(): String = java.lang.Long.toString(kotlin.random.Random.nextLong(0, Long.MAX_VALUE), 36).take(6)
    }

    val configurado: Boolean get() = urlBase.isNotBlank() && clave.isNotBlank()
    private val base: String get() = urlBase.trimEnd('/')

    private fun cabeceras(token: String, extra: Map<String, String> = emptyMap()): Map<String, String> =
        mapOf("apikey" to clave, "Authorization" to "Bearer $token") + extra

    private fun urlRest(tabla: String, params: Map<String, String>): String {
        val b = (base.toHttpUrlOrNull() ?: throw ErrorConsulta("La dirección de Supabase no es válida")).newBuilder().addPathSegments("rest/v1/$tabla")
        params.forEach { (k, v) -> b.addQueryParameter(k, v) }
        return b.build().toString()
    }

    /** URL publica de una foto del bucket (lo que se guarda en report.foto_url). */
    fun urlFotoPublica(ruta: String): String = "$base/storage/v1/object/public/$BUCKET/$ruta"

    // ---- peticiones (puras: se prueban sin red) ----

    fun peticionCrearReporte(token: String, tipo: String, subtipo: String?, descripcion: String?, fotoUrl: String?, lat: Double, lon: Double): PeticionHttp {
        val fila = buildJsonObject {
            put("tipo", tipo)
            put("subtipo", subtipo?.takeIf { it.isNotBlank() }?.let { JsonPrimitive(it) } ?: JsonNull)
            put("descripcion", descripcion?.trim()?.takeIf { it.isNotBlank() }?.let { JsonPrimitive(it) } ?: JsonNull)
            put("foto_url", fotoUrl?.takeIf { it.isNotBlank() }?.let { JsonPrimitive(it) } ?: JsonNull)
            put("geom", Comunidad.ewkt(lat, lon))
        }
        return PeticionHttp(
            "POST", urlRest("report", mapOf("select" to COLS_REPORTE)),
            cabeceras(token, mapOf("Content-Type" to "application/json", "Prefer" to "return=representation")),
            fila.toString().toByteArray(), "application/json",
        )
    }

    fun peticionVotar(token: String, reportId: String, valor: Int): PeticionHttp = PeticionHttp(
        "POST", urlRest("voto", mapOf("on_conflict" to "report_id,autor")),
        cabeceras(token, mapOf("Content-Type" to "application/json", "Prefer" to "resolution=merge-duplicates,return=minimal")),
        buildJsonObject { put("report_id", reportId); put("valor", valor) }.toString().toByteArray(), "application/json",
    )

    fun peticionQuitarVoto(token: String, reportId: String): PeticionHttp = PeticionHttp(
        "DELETE", urlRest("voto", mapOf("report_id" to "eq.$reportId")),
        cabeceras(token, mapOf("Prefer" to "return=minimal")),
    )

    fun peticionComentar(token: String, reportId: String, texto: String): PeticionHttp = PeticionHttp(
        "POST", urlRest("comentario", mapOf("select" to COLS_COMENTARIO)),
        cabeceras(token, mapOf("Content-Type" to "application/json", "Prefer" to "return=representation")),
        buildJsonObject { put("report_id", reportId); put("texto", texto) }.toString().toByteArray(), "application/json",
    )

    fun peticionSubirFoto(token: String, ruta: String, jpeg: ByteArray): PeticionHttp = PeticionHttp(
        "POST", "$base/storage/v1/object/$BUCKET/$ruta",
        cabeceras(token, mapOf("Content-Type" to "image/jpeg", "x-upsert" to "false", "Cache-Control" to "3600")),
        jpeg, "image/jpeg",
    )

    fun peticionMisReportes(token: String): PeticionHttp = PeticionHttp(
        "POST", urlRest("rpc/mis_reportes", emptyMap()),
        cabeceras(token, mapOf("Content-Type" to "application/json")),
        "{}".toByteArray(), "application/json",
    )

    fun peticionPerfil(token: String): PeticionHttp =
        PeticionHttp("GET", urlRest("perfil", mapOf("select" to "id,nombre,reputacion", "limit" to "1")), cabeceras(token))

    fun peticionMisVotos(token: String, ids: List<String>): PeticionHttp = PeticionHttp(
        "GET", urlRest("voto", mapOf("select" to "report_id,valor", "report_id" to "in.(${ids.joinToString(",")})", "limit" to "500")),
        cabeceras(token),
    )

    // ---- acciones ----

    private suspend fun tokenOFalla(): String {
        if (!configurado) throw ErrorConsulta("Falta la dirección o la llave pública de Supabase")
        return token() ?: throw ErrorConsulta(Comunidad.SESION_VENCIDA)
    }

    private suspend fun enviar(p: PeticionHttp, que: String): String {
        val r = transporte.enviar(p)
        if (!r.ok) throw ErrorConsulta(Comunidad.mensajeErrorBD(r.codigo, r.cuerpo, que))
        return r.cuerpo
    }

    private inline fun <reified T> lista(cuerpo: String): List<T> =
        JsonSimpac.decodeFromString(ListSerializer(kotlinx.serialization.serializer<T>()), cuerpo)

    /** Crea el reporte y devuelve la fila como la guardo la BD (con id, expira_en y estado). */
    suspend fun crearReporte(tipo: String, subtipo: String?, descripcion: String?, fotoUrl: String?, lat: Double, lon: Double): ReporteVigente {
        val cuerpo = enviar(peticionCrearReporte(tokenOFalla(), tipo, subtipo, descripcion, fotoUrl, lat, lon), "enviar el reporte")
        return try { lista<ReporteVigente>(cuerpo).first() } catch (e: Exception) {
            throw ErrorConsulta("El reporte se envió pero no se pudo leer la respuesta.", e)
        }
    }

    /** Vota 1 o -1 (upsert por report_id+autor); null quita el voto. */
    suspend fun votar(reportId: String, valor: Int?) {
        val t = tokenOFalla()
        enviar(if (valor == null) peticionQuitarVoto(t, reportId) else peticionVotar(t, reportId, valor), "votar")
    }

    suspend fun comentar(reportId: String, texto: String): ComentarioReporte {
        val cuerpo = enviar(peticionComentar(tokenOFalla(), reportId, texto), "comentar")
        return try { lista<ComentarioReporte>(cuerpo).first() } catch (e: Exception) {
            throw ErrorConsulta("El comentario se envió pero no se pudo leer la respuesta.", e)
        }
    }

    /** Sube el JPEG ya reducido a <uid>/<ms>-<aleatorio>.jpg y devuelve la URL publica. */
    suspend fun subirFoto(jpeg: ByteArray, uid: String): String {
        if (jpeg.size > Comunidad.MAX_FOTO_BYTES) throw ErrorConsulta("La foto pesa demasiado (máximo 3 MB).")
        val ruta = rutaFoto(uid)
        enviar(peticionSubirFoto(tokenOFalla(), ruta, jpeg), "subir la foto")
        return urlFotoPublica(ruta)
    }

    /** Mis reportes, vigentes y vencidos (rpc mis_reportes: la unica forma de verlos, autor no es legible). */
    suspend fun misReportes(): List<ReporteVigente> =
        lista(enviar(peticionMisReportes(tokenOFalla()), "leer tus reportes"))

    /** Perfil propio (nombre y reputacion); null si el trigger aun no lo creo. */
    suspend fun perfil(): PerfilPropio? =
        lista<PerfilPropio>(enviar(peticionPerfil(tokenOFalla()), "leer tu perfil")).firstOrNull()

    /** Mis votos sobre esos reportes: { report_id: 1 | -1 }. */
    suspend fun misVotos(ids: List<String>): Map<String, Int> {
        if (ids.isEmpty()) return emptyMap()
        return lista<VotoPropio>(enviar(peticionMisVotos(tokenOFalla(), ids), "leer tus votos")).associate { it.report_id to it.valor }
    }
}
