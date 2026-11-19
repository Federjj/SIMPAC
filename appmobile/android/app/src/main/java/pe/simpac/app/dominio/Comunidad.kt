package pe.simpac.app.dominio

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import pe.simpac.app.data.JsonSimpac
import pe.simpac.app.data.ReporteVigente
import java.util.Locale
import kotlin.math.min
import kotlin.math.roundToInt

/** Un tipo de reporte ciudadano (los mismos ids y colores que frontend/src/lib/reportTypes.js y el CHECK de la BD). */
data class TipoReporte(val id: String, val etiqueta: String, val color: Long, val subtipos: List<Pair<String, String>> = emptyList())

/** Un reporte con su distancia a la persona y su puntaje de orden. */
data class ReporteOrdenado(val reporte: ReporteVigente, val distanciaKm: Double?, val puntaje: Double)

/**
 * Logica pura de la comunidad, copiada de frontend/src/lib/comunidad.js (orden por confianza y
 * cercania, textos de distancia y vencimiento, validaciones, errores de la BD y de Auth en lenguaje
 * claro). Sin Android ni red: se prueba en la JVM (ComunidadTest).
 */
object Comunidad {
    const val MAX_DESCRIPCION = 500
    const val MAX_COMENTARIO = 500
    const val MAX_FOTO_BYTES = 3 * 1024 * 1024
    const val LADO_FOTO = 1280
    const val HORAS_VIGENCIA = 12
    const val MAX_REPORTES_HORA = 5

    const val AVISO_REPORTE = "Es un reporte comunitario, no oficial. Para emergencias llama al 105 o 116."
    const val POR_QUE_CUENTA = "Para consultar no hace falta cuenta. Solo se pide para reportar, votar y comentar."
    const val SESION_VENCIDA = "Tu sesión venció. Vuelve a entrar para continuar."
    const val SIN_RED = "No hay conexión. Revisa tu internet e inténtalo de nuevo."

    val TIPOS: List<TipoReporte> = listOf(
        TipoReporte("inundacion", "Inundación", 0xFF3B3BEB),
        TipoReporte("huayco", "Huayco / deslizamiento", 0xFFEB3B3B),
        TipoReporte("lluvia_intensa", "Lluvia intensa", 0xFF3BEBEB),
        TipoReporte("via_bloqueada", "Vía bloqueada", 0xFF111111),
        TipoReporte("atasco", "Atasco", 0xFFEBEB3B, listOf("leve" to "Leve", "moderado" to "Moderado", "detenido" to "Detenido")),
        TipoReporte("bache", "Bache", 0xFFF58E27),
        TipoReporte("accidente", "Accidente", 0xFFDB0404),
        TipoReporte("otro", "Otro", 0xFF6B7280),
    )
    val TIPO_OTRO: TipoReporte = TIPOS.last()

    fun tipo(id: String?): TipoReporte = TIPOS.firstOrNull { it.id == id } ?: TIPO_OTRO

    /** "Atasco detenido", "Inundación". */
    fun nombreReporte(tipo: String?, subtipo: String?): String {
        val t = tipo(tipo)
        val sub = t.subtipos.firstOrNull { it.first == subtipo }?.second
        return if (sub != null) "${t.etiqueta} ${sub.lowercase(Locale.ROOT)}" else t.etiqueta
    }
    fun nombreReporte(r: ReporteVigente): String = nombreReporte(r.tipo, r.subtipo)

    fun textoEstado(estado: String?): String = when (estado) {
        "confirmado" -> "Confirmado por la comunidad"
        "descartado" -> "Descartado por la comunidad"
        else -> "Sin confirmar"
    }

    // ---- orden por confianza y cercania ----

    fun distanciaKm(r: ReporteVigente, lat: Double?, lon: Double?): Double? {
        if (lat == null || lon == null || r.lat == null || r.lon == null) return null
        return Geo.distanciaKm(lat, lon, r.lat, r.lon)
    }

    /** "a 350 m", "a 1,2 km", "a 15 km" (como la web). */
    fun textoDistancia(km: Double?): String? {
        if (km == null || !km.isFinite()) return null
        if (km < 1) return "a ${maxOf(10, (km * 100).roundToInt() * 10)} m"
        if (km < 10) return "a " + String.format(Locale.US, "%.1f", km).replace('.', ',') + " km"
        return "a ${km.roundToInt()} km"
    }

    /** Confianza (0 a 1, 0.5 si falta) menos un castigo por lejania: 50 km restan 1; mas de 100 km no restan mas. */
    fun puntaje(r: ReporteVigente, km: Double?): Double {
        val confianza = r.confianza?.takeIf { it.isFinite() } ?: 0.5
        val lejania = if (km == null) 0.0 else min(km, 100.0) / 50.0
        return confianza - lejania
    }

    /** Mejor puntaje primero; empate, el mas nuevo primero. */
    fun ordenar(reportes: List<ReporteVigente>, lat: Double?, lon: Double?): List<ReporteOrdenado> =
        reportes.map { r -> val km = distanciaKm(r, lat, lon); ReporteOrdenado(r, km, puntaje(r, km)) }
            .sortedWith(compareByDescending<ReporteOrdenado> { it.puntaje }.thenByDescending { Tiempo.parsearMs(it.reporte.creado_en) ?: 0L })

    // ---- tiempos ----

    /** "vence en 45 min", "vence en 1 h 20 min", "vence en 2 días" o "vencido". */
    fun venceEn(expiraEn: String?, ahoraMs: Long = System.currentTimeMillis()): String {
        val t = Tiempo.parsearMs(expiraEn) ?: return ""
        val min = Math.floorDiv(t - ahoraMs, 60_000L)
        if (min <= 0) return "vencido"
        if (min < 60) return "vence en $min min"
        val h = min / 60
        if (h >= 48) return "vence en ${h / 24} días"
        return if (min % 60 != 0L) "vence en $h h ${min % 60} min" else "vence en $h h"
    }

    fun vigente(r: ReporteVigente, ahoraMs: Long = System.currentTimeMillis()): Boolean =
        (Tiempo.parsearMs(r.expira_en) ?: 0L) > ahoraMs

    // ---- validaciones ----

    /** El mismo recuadro que el CHECK de report.geom (lon -81.5..-68.5, lat -18.5..0.1). */
    fun dentroDelPeru(lat: Double, lon: Double): Boolean = lon in -81.5..-68.5 && lat in -18.5..0.1

    /** Punto para la BD como EWKT (ojo: primero lon, despues lat). */
    fun ewkt(lat: Double, lon: Double): String = "SRID=4326;POINT(${fmt(lon)} ${fmt(lat)})"
    private fun fmt(v: Double): String = String.format(Locale.US, "%.6f", v).trimEnd('0').trimEnd('.')

    /** Caja del Peru para pedir todos los reportes vigentes (la misma del CHECK). */
    val CAJA_PERU = Caja(-81.5, -18.5, -68.5, 0.1)

    /** Errores por campo (tipo, subtipo, descripcion, pos) listos para mostrar; vacio si esta bien. */
    fun validarReporte(tipo: String?, subtipo: String?, descripcion: String?, lat: Double?, lon: Double?): Map<String, String> {
        val errores = linkedMapOf<String, String>()
        val t = TIPOS.firstOrNull { it.id == tipo }
        if (t == null) errores["tipo"] = "Elige qué estás viendo."
        if (t != null && t.subtipos.isNotEmpty() && t.subtipos.none { it.first == subtipo }) errores["subtipo"] = "Indica qué tan fuerte es el atasco."
        if (t != null && t.subtipos.isEmpty() && !subtipo.isNullOrBlank()) errores["subtipo"] = "Ese detalle no corresponde a este tipo de reporte."
        val d = (descripcion ?: "").trim()
        if (d.length > MAX_DESCRIPCION) errores["descripcion"] = "La descripción puede tener hasta $MAX_DESCRIPCION letras (llevas ${d.length})."
        if (lat == null || lon == null || !lat.isFinite() || !lon.isFinite()) {
            errores["pos"] = "No tenemos tu ubicación. Sin ella no se puede reportar."
        } else if (!dentroDelPeru(lat, lon)) {
            errores["pos"] = "Tu ubicación cae fuera del Perú: solo se reporta desde dentro del país."
        }
        return errores
    }

    /** Un comentario: 1 a `max` letras, sin solo espacios. Devuelve (texto limpio, null) o (null, error). */
    fun validarTexto(texto: String?, max: Int = MAX_COMENTARIO): Pair<String?, String?> {
        val t = (texto ?: "").trim()
        if (t.isEmpty()) return null to "Escribe algo antes de enviar."
        if (t.length > max) return null to "Puede tener hasta $max letras (llevas ${t.length})."
        return t to null
    }

    private val CORREO = Regex("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$")

    /** Errores por campo (email, password, nombre) de los formularios de Cuenta. */
    fun validarCuenta(email: String?, password: String?, nombre: String? = null, conNombre: Boolean = false): Map<String, String> {
        val errores = linkedMapOf<String, String>()
        if (!CORREO.matches((email ?: "").trim())) errores["email"] = "Escribe un correo válido."
        if ((password ?: "").length < 6) errores["password"] = "La contraseña tiene que tener al menos 6 caracteres."
        if (conNombre) {
            val n = (nombre ?: "").trim()
            if (n.length < 2) errores["nombre"] = "Escribe el nombre con el que quieres aparecer."
            if (n.length > 80) errores["nombre"] = "El nombre puede tener hasta 80 letras."
        }
        return errores
    }

    // ---- errores en lenguaje claro ----

    private fun objeto(cuerpo: String?): JsonObject? = try {
        cuerpo?.takeIf { it.isNotBlank() }?.let { JsonSimpac.parseToJsonElement(it).jsonObject }
    } catch (_: Exception) { null }

    private fun campo(o: JsonObject?, nombre: String): String = try {
        o?.get(nombre)?.let { if (it is JsonObject) it.toString() else it.jsonPrimitive.content } ?: ""
    } catch (_: Exception) { "" }

    /**
     * Un error de PostgREST, de Storage o de la red (codigo HTTP y cuerpo) -> frase para la persona.
     * `que` es la accion ("enviar el reporte", "votar") para la frase generica. Misma tabla que
     * mensajeErrorBD de lib/comunidad.js.
     */
    fun mensajeErrorBD(codigoHttp: Int, cuerpo: String?, que: String = "guardar"): String {
        val o = objeto(cuerpo)
        val m = listOf(campo(o, "message"), campo(o, "details"), campo(o, "hint"), campo(o, "error"), campo(o, "msg"))
            .joinToString(" ").lowercase(Locale.ROOT)
        val code = campo(o, "code").ifBlank { campo(o, "statusCode") }
        Regex("l[ií]mite de (\\d+) por hora").find(m)?.let { return "Llegaste al límite de ${it.groupValues[1]} por hora. Espera un rato antes de volver a $que." }
        if (m.contains("propio reporte")) return "No puedes votar tu propio reporte."
        if (m.contains("report_geom_check") || (m.contains("geom") && m.contains("check"))) return "Tu ubicación cae fuera del Perú: solo se reporta desde dentro del país."
        if (m.contains("jwt") || m.contains("expired") || code == "401" || code == "PGRST301" || codigoHttp == 401) return SESION_VENCIDA
        if (code == "42501" || m.contains("row-level security") || m.contains("permission denied") || codigoHttp == 403) {
            return "No tienes permiso para esto. Si acabas de entrar, prueba de nuevo; si no, vuelve a iniciar sesión."
        }
        if (code == "23505") return "Eso ya estaba guardado."
        if (m.contains("payload too large") || m.contains("exceeded the maximum allowed size") || code == "413" || codigoHttp == 413) return "La foto pesa demasiado (máximo 3 MB)."
        if (m.contains("mime type") || m.contains("not supported")) return "La foto tiene que ser JPG, PNG o WebP."
        if (m.contains("failed to fetch") || m.contains("networkerror") || m.contains("network request failed")) return SIN_RED
        if (m.contains("vigente") || m.contains("expira")) return "Este reporte ya venció: no admite votos ni comentarios."
        return "No se pudo $que. Inténtalo de nuevo en un momento."
    }

    /** Un error de Supabase Auth (GoTrue: {code, error_code, msg} o {error, error_description}) -> frase para la persona. */
    fun mensajeAuth(codigoHttp: Int, cuerpo: String?): String {
        val o = objeto(cuerpo)
        val m = listOf(campo(o, "msg"), campo(o, "message"), campo(o, "error_description"), campo(o, "error"))
            .joinToString(" ").lowercase(Locale.ROOT)
        val code = campo(o, "error_code").ifBlank { campo(o, "error") }
        if (code == "invalid_credentials" || m.contains("invalid login credentials") || code == "invalid_grant") return "Correo o contraseña incorrectos."
        if (code == "email_not_confirmed" || m.contains("email not confirmed")) return "Tu correo aún no está confirmado. Busca el mensaje que te enviamos (revisa también la carpeta de spam)."
        if (code == "user_already_exists" || m.contains("already registered") || m.contains("already been registered")) return "Ya hay una cuenta con ese correo. Entra con tu contraseña o pide una nueva."
        if (code == "weak_password" || m.contains("password should be") || m.contains("at least 6")) return "La contraseña tiene que tener al menos 6 caracteres."
        if (code == "over_email_send_rate_limit" || code == "over_request_rate_limit" || m.contains("rate limit") || codigoHttp == 429) return "Enviamos demasiados correos en poco tiempo. Espera unos minutos y vuelve a intentar."
        if (code == "validation_failed" || m.contains("invalid email") || m.contains("unable to validate email")) return "Ese correo no parece válido. Revísalo."
        if (code == "same_password") return "La contraseña nueva tiene que ser distinta de la actual."
        if (code == "refresh_token_not_found" || code == "refresh_token_already_used" || m.contains("refresh token")) return SESION_VENCIDA
        if (code == "otp_expired" || m.contains("expired")) return "El enlace venció. Pide uno nuevo."
        if (m.contains("failed to fetch") || m.contains("network")) return SIN_RED
        return "No se pudo completar. Inténtalo de nuevo en un momento."
    }
}
