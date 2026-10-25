package pe.simpac.app.dominio

import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale

/** Fechas y horas en lenguaje claro, siempre en la hora del Peru. */
object Tiempo {
    val ZONA_PERU: ZoneId = ZoneId.of("America/Lima")
    const val DESACTUALIZADO_MS: Long = 3 * 60 * 60 * 1000L   // mas de 3 h sin dato nuevo

    private val MESES = listOf("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic")
    private val DIAS = listOf("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

    /** Milisegundos de un timestamp ISO de la BD ("2026-10-20T14:05:11.123+00:00", con o sin zona); null si no se entiende. */
    fun parsearMs(texto: String?): Long? {
        if (texto.isNullOrBlank()) return null
        val t = texto.trim()
        return try {
            OffsetDateTime.parse(t).toInstant().toEpochMilli()
        } catch (_: DateTimeParseException) {
            try {
                Instant.parse(t).toEpochMilli()
            } catch (_: DateTimeParseException) {
                try {
                    // sin zona: se asume hora del Peru (asi guarda el worker fecha + hora)
                    LocalDateTime.parse(t).atZone(ZONA_PERU).toInstant().toEpochMilli()
                } catch (_: DateTimeParseException) {
                    null
                }
            }
        }
    }

    /** "hace 5 min", "hace 2 h", "hace 3 días"; "recién" si tiene menos de un minuto; "" si no hay fecha. */
    fun haceTexto(ms: Long?, ahoraMs: Long = System.currentTimeMillis()): String {
        if (ms == null) return ""
        val dif = ahoraMs - ms
        if (dif < 0) return "recién"
        val min = dif / 60_000
        if (min < 1) return "recién"
        if (min < 60) return "hace $min min"
        val horas = min / 60
        if (horas < 24) return "hace $horas h"
        val dias = horas / 24
        return if (dias == 1L) "hace 1 día" else "hace $dias días"
    }

    /** "20 oct, 14:05" en hora del Peru. */
    fun horaCorta(ms: Long?): String {
        if (ms == null) return ""
        val f = Instant.ofEpochMilli(ms).atZone(ZONA_PERU)
        return "${f.dayOfMonth} ${MESES[f.monthValue - 1]}, " + String.format(Locale.US, "%02d:%02d", f.hour, f.minute)
    }

    /** "20 oct, 14:05 (hace 2 h)". */
    fun horaConHace(ms: Long?, ahoraMs: Long = System.currentTimeMillis()): String {
        if (ms == null) return "sin hora"
        return "${horaCorta(ms)} (${haceTexto(ms, ahoraMs)})"
    }

    /** true si el dato tiene mas de 3 h (o no tiene hora). */
    fun desactualizado(ms: Long?, ahoraMs: Long = System.currentTimeMillis()): Boolean =
        ms == null || ahoraMs - ms > DESACTUALIZADO_MS

    /** Fecha de hoy en el Peru ("2026-10-20"). */
    fun hoyPeru(ahoraMs: Long = System.currentTimeMillis()): LocalDate =
        Instant.ofEpochMilli(ahoraMs).atZone(ZONA_PERU).toLocalDate()

    /** "Hoy", "Mañana" o el dia de la semana ("Jueves") para una fecha "AAAA-MM-DD". */
    fun etiquetaDia(fecha: String, hoy: LocalDate = hoyPeru()): String {
        val f = try { LocalDate.parse(fecha, DateTimeFormatter.ISO_LOCAL_DATE) } catch (_: DateTimeParseException) { return fecha }
        return when (f.toEpochDay() - hoy.toEpochDay()) {
            0L -> "Hoy"
            1L -> "Mañana"
            else -> DIAS[f.dayOfWeek.value - 1].replaceFirstChar { it.uppercase() }
        }
    }

    /** "20 oct 2026" para una fecha "AAAA-MM-DD"; el texto tal cual si no se entiende. */
    fun fechaLarga(fecha: String?): String {
        if (fecha.isNullOrBlank()) return ""
        val f = try { LocalDate.parse(fecha.take(10)) } catch (_: DateTimeParseException) { return fecha }
        return "${f.dayOfMonth} ${MESES[f.monthValue - 1]} ${f.year}"
    }
}
