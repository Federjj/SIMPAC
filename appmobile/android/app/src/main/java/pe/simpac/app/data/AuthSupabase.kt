package pe.simpac.app.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import pe.simpac.app.dominio.Comunidad

/** Error de Supabase Auth con el mensaje ya en lenguaje claro y el codigo HTTP (4xx = la sesion no sirve). */
class ErrorAuth(mensaje: String, val codigoHttp: Int) : ErrorConsulta(mensaje)

/**
 * La sesion que la app guarda (solo en AlmacenSeguro, cifrada): tokens, vencimiento (segundos desde
 * 1970) y lo minimo de la persona (id, correo y nombre para mostrar). Nada mas se pide ni se guarda.
 */
@Serializable
data class SesionGuardada(
    val accessToken: String,
    val refreshToken: String,
    val expiraEnSeg: Long,
    val usuarioId: String,
    val email: String? = null,
    val nombre: String? = null,
) {
    /** true si vence en menos de `margenSeg` segundos (se refresca antes). */
    fun porVencer(ahoraSeg: Long = System.currentTimeMillis() / 1000, margenSeg: Long = 60): Boolean = expiraEnSeg - ahoraSeg < margenSeg

    fun aJson(): String = JsonSifec.encodeToString(serializer(), this)

    companion object {
        fun desdeJson(texto: String?): SesionGuardada? = try {
            texto?.takeIf { it.isNotBlank() }?.let { JsonSifec.decodeFromString(serializer(), it) }
        } catch (_: Exception) { null }
    }
}

/** Lo que devuelve el registro: sesion si Auth no exige confirmar el correo; si no, "revisa tu correo". */
data class ResultadoRegistro(val sesion: SesionGuardada?, val confirmar: Boolean, val yaExistia: Boolean)

/**
 * Supabase Auth (GoTrue) por REST con la publishable key, como lib/sesion.js en la web:
 *   POST /auth/v1/signup?redirect_to=<WEB>/cuenta   {email, password, data: {nombre}}
 *   POST /auth/v1/token?grant_type=password          {email, password}
 *   POST /auth/v1/token?grant_type=refresh_token     {refresh_token}
 *   POST /auth/v1/recover?redirect_to=<WEB>/cuenta   {email}
 *   POST /auth/v1/logout                             (Bearer <access_token>)
 *   GET  /auth/v1/user                               (Bearer <access_token>)
 * Las peticiones se arman en `peticionX` (probadas en la JVM sin red) y se mandan por el transporte.
 * El enlace del correo (confirmacion o contrasena nueva) vuelve a la web, <WEB>/cuenta, igual que en
 * el navegador: Auth lo acepta solo si esa direccion esta en Redirect URLs del proyecto.
 */
class AuthSupabase(
    private val urlBase: String,
    private val clave: String,
    private val transporte: TransporteHttp = TransporteOkHttp,
) {
    val configurado: Boolean get() = urlBase.isNotBlank() && clave.isNotBlank()

    private fun url(ruta: String, params: Map<String, String> = emptyMap()): String {
        val b = (urlBase.trimEnd('/').toHttpUrlOrNull() ?: throw ErrorConsulta("La dirección de Supabase no es válida"))
            .newBuilder().addPathSegments("auth/v1/$ruta")
        params.forEach { (k, v) -> b.addQueryParameter(k, v) }
        return b.build().toString()
    }

    private fun cabeceras(token: String? = null): Map<String, String> =
        mapOf("apikey" to clave, "Authorization" to "Bearer ${token ?: clave}", "Content-Type" to "application/json")

    private fun post(ruta: String, params: Map<String, String>, cuerpo: JsonObject, token: String? = null): PeticionHttp =
        PeticionHttp("POST", url(ruta, params), cabeceras(token), cuerpo.toString().toByteArray(), "application/json")

    // ---- peticiones (puras) ----

    fun peticionEntrar(email: String, password: String): PeticionHttp =
        post("token", mapOf("grant_type" to "password"), buildJsonObject { put("email", email.trim()); put("password", password) })

    /** data.nombre lo copia el trigger crear_perfil al perfil; redirect_to es a donde vuelve el enlace del correo. */
    fun peticionRegistro(email: String, password: String, nombre: String, volverA: String): PeticionHttp =
        post("signup", mapOf("redirect_to" to volverA), buildJsonObject {
            put("email", email.trim()); put("password", password)
            putJsonObject("data") { put("nombre", nombre.trim()) }
        })

    fun peticionRefrescar(refreshToken: String): PeticionHttp =
        post("token", mapOf("grant_type" to "refresh_token"), buildJsonObject { put("refresh_token", refreshToken) })

    fun peticionRecuperar(email: String, volverA: String): PeticionHttp =
        post("recover", mapOf("redirect_to" to volverA), buildJsonObject { put("email", email.trim()) })

    fun peticionSalir(accessToken: String): PeticionHttp =
        PeticionHttp("POST", url("logout"), cabeceras(accessToken), "{}".toByteArray(), "application/json")

    fun peticionUsuario(accessToken: String): PeticionHttp =
        PeticionHttp("GET", url("user"), cabeceras(accessToken))

    // ---- acciones ----

    private suspend fun enviar(p: PeticionHttp): String {
        if (!configurado) throw ErrorConsulta("Falta la dirección o la llave pública de Supabase")
        val r = transporte.enviar(p)
        if (!r.ok) throw ErrorAuth(Comunidad.mensajeAuth(r.codigo, r.cuerpo), r.codigo)
        return r.cuerpo
    }

    suspend fun entrar(email: String, password: String): SesionGuardada =
        parsearSesion(enviar(peticionEntrar(email, password))) ?: throw ErrorAuth("No se pudo leer la respuesta de Auth.", 0)

    /**
     * Registro. Con confirmacion por correo activa, Auth devuelve el usuario sin sesion (confirmar = true).
     * Si el correo ya existia, devuelve un usuario sin identidades (no revela cuentas): yaExistia = true.
     */
    suspend fun registrar(email: String, password: String, nombre: String, volverA: String): ResultadoRegistro {
        val cuerpo = enviar(peticionRegistro(email, password, nombre, volverA))
        val sesion = parsearSesion(cuerpo)
        if (sesion != null) return ResultadoRegistro(sesion, confirmar = false, yaExistia = false)
        val o = objeto(cuerpo)
        val usuario = o?.get("user")?.let { it as? JsonObject } ?: o
        val identidades = usuario?.get("identities") as? JsonArray
        return ResultadoRegistro(null, confirmar = true, yaExistia = identidades != null && identidades.isEmpty())
    }

    suspend fun refrescar(refreshToken: String): SesionGuardada =
        parsearSesion(enviar(peticionRefrescar(refreshToken))) ?: throw ErrorAuth(Comunidad.SESION_VENCIDA, 401)

    suspend fun recuperar(email: String, volverA: String) { enviar(peticionRecuperar(email, volverA)) }

    /** Cierra la sesion en el servidor; si falla (sin red, token vencido) no importa: la app borra la suya igual. */
    suspend fun salir(accessToken: String) { try { enviar(peticionSalir(accessToken)) } catch (_: Exception) { } }

    companion object {
        private fun objeto(cuerpo: String): JsonObject? = try { JsonSifec.parseToJsonElement(cuerpo).jsonObject } catch (_: Exception) { null }
        private fun texto(o: JsonObject?, nombre: String): String? = try { o?.get(nombre)?.jsonPrimitive?.content?.takeIf { it != "null" } } catch (_: Exception) { null }

        /**
         * Sesion desde la respuesta de /token o /signup: access_token, refresh_token, expires_at (o
         * expires_in), user.id, user.email y user.user_metadata.nombre. null si no trae access_token.
         */
        fun parsearSesion(cuerpo: String, ahoraSeg: Long = System.currentTimeMillis() / 1000): SesionGuardada? {
            val o = objeto(cuerpo) ?: return null
            val access = texto(o, "access_token") ?: return null
            val refresh = texto(o, "refresh_token") ?: return null
            val expiraEn = texto(o, "expires_at")?.toLongOrNull()
                ?: texto(o, "expires_in")?.toLongOrNull()?.let { ahoraSeg + it }
                ?: (ahoraSeg + 3600)
            val u = o["user"] as? JsonObject ?: return null
            val id = texto(u, "id") ?: return null
            val meta = u["user_metadata"] as? JsonObject
            return SesionGuardada(access, refresh, expiraEn, id, texto(u, "email"), texto(meta, "nombre")?.takeIf { it.isNotBlank() })
        }

        /** Correos en los que tiene identidad el usuario de una respuesta de /user (para pruebas y depuracion). */
        fun identidades(cuerpo: String): Int = try { objeto(cuerpo)?.get("identities")?.jsonArray?.size ?: 0 } catch (_: Exception) { 0 }
    }
}
