package pe.simpac.app.dominio

import pe.simpac.app.data.NowcastEstado
import pe.simpac.app.data.PronosticoLocalidad
import java.time.Instant
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Nowcasting de lluvia de SENAMHI (vistas nowcast_estado y nowcast_vigente): manchas de ~2 km donde
 * SENAMHI estima lluvia moderada, fuerte o extrema ahora, en 1 h o en 2 h. EXPERIMENTAL: azules y
 * violeta con borde punteado para no confundirlo con los avisos. Si SENAMHI no publica hace mas de
 * 30 min no se muestra nada y la capa lo dice (frontend/src/map/layers/nowcast.js). Modulo puro.
 */
object Nowcast {
    const val URL_VISOR = "https://www.senamhi.gob.pe/mapas/mapa-nowcasting/nowcasting-pronostico-1h.php"
    val COLOR: Map<Int, Long> = mapOf(1 to 0xFF3BA5EB, 2 to 0xFF3B3BEB, 3 to 0xFF7B2FBE)
    val NOMBRE = mapOf(1 to "moderada", 2 to "fuerte", 3 to "extrema")
    val ETIQUETA = mapOf(1 to "Lluvia moderada", 2 to "Lluvia fuerte", 3 to "Lluvia extrema (el nivel más alto de SENAMHI)")
    /** Relleno por nivel (0.5, 0.55, 0.6 de la web) en alfa de 0 a 255. */
    val ALFA = mapOf(1 to 0x80, 2 to 0x8C, 3 to 0x99)

    data class Horizonte(val minutos: Int, val etiqueta: String, val largo: String, val chip: String)
    val HORIZONTES = listOf(
        Horizonte(60, "En la próxima hora", "en la próxima hora", "en la próxima hora"),
        Horizonte(120, "En 2 horas", "en 2 horas", "en 2 horas"),
        Horizonte(0, "Ahora (estimación)", "ahora (estimación)", "ahora"),
    )
    const val DEFECTO = 60
    fun horizonte(min: Int?): Horizonte = HORIZONTES.firstOrNull { it.minutos == min } ?: HORIZONTES.first()

    const val FUENTE = "Nowcasting de SENAMHI: estimación automática con satélite, «referencial y aún en etapa de calibración». " +
        "No es un aviso. SIMPAC usa azules para no confundirlo con los avisos. Si SENAMHI no publica hace más de 30 min, no se muestra."
    const val ACLARA = "Es una estimación automática de SENAMHI con imágenes de satélite, todavía en calibración. Puede fallar y no es un aviso oficial."

    enum class EstadoNota { FRESCO, VACIO, VIEJO, ERROR }
    data class Nota(val estado: EstadoNota, val texto: String, val corto: String)

    private val HHMM = DateTimeFormatter.ofPattern("HH:mm", Locale.US)
    fun hhmm(iso: String?): String = Tiempo.parsearMs(iso)?.let { Instant.ofEpochMilli(it).atZone(Tiempo.ZONA_PERU).format(HHMM) } ?: "?"

    /** "hace 8 min", "hace 2 h 45 min" (como lib/tiempo.js textoHace). */
    fun textoHace(ms: Long): String {
        val min = maxOf(0L, ms / 60_000)
        if (min < 1) return "hace menos de 1 min"
        if (min < 60) return "hace $min min"
        val h = min / 60
        if (h >= 48) return "hace ${h / 24} días"
        return if (min % 60 != 0L) "hace $h h ${min % 60} min" else "hace $h h"
    }

    /** El analisis (horizonte 0) vale para un instante: SENAMHI da valido_desde = valido_hasta. */
    fun esInstante(desde: String?, hasta: String?): Boolean = (Tiempo.parsearMs(desde) ?: 0) >= (Tiempo.parsearMs(hasta) ?: 0)

    /** "a las 13:10" (analisis) o "entre las 13:10 y las 14:10". */
    fun lapso(desde: String?, hasta: String?): String =
        if (esInstante(desde, hasta)) "a las ${hhmm(desde)}" else "entre las ${hhmm(desde)} y las ${hhmm(hasta)}"

    /** "de las 20:40" (hoy) o "del 18 nov, 20:40". */
    private fun deLas(iso: String?, ahoraMs: Long): String {
        val ms = Tiempo.parsearMs(iso) ?: return "de hora desconocida"
        return if (Tiempo.hoyPeru(ms) == Tiempo.hoyPeru(ahoraMs)) "de las ${hhmm(iso)}" else "del ${Tiempo.horaCorta(ms)}"
    }

    private fun notaVieja(e: NowcastEstado, ahoraMs: Long): Nota {
        val emision = Tiempo.parsearMs(e.emision) ?: ahoraMs
        return Nota(
            EstadoNota.VIEJO,
            "No hay un nowcasting de SENAMHI reciente: el último es ${deLas(e.emision, ahoraMs)} (${textoHace(ahoraMs - emision)}). No mostramos manchas viejas.",
            "Sin nowcasting reciente de SENAMHI (último ${hhmm(e.emision)})",
        )
    }
    val NOTA_ERROR = Nota(EstadoNota.ERROR, "No se pudo consultar el nowcasting de SENAMHI.", "No se pudo consultar el nowcasting")

    /** La nota de la capa y el texto corto del chip. manchas null = fallo la consulta (no decir "sin lluvia"). */
    fun nota(e: NowcastEstado?, manchas: Int?, horizonteMin: Int, ahoraMs: Long = System.currentTimeMillis()): Nota {
        if (e == null) return NOTA_ERROR
        val vence = Tiempo.parsearMs(e.vence_en) ?: 0L
        if (!e.vigente || vence <= ahoraMs) return notaVieja(e, ahoraMs)
        if (manchas == null) return NOTA_ERROR
        val emitido = hhmm(e.emision)
        if (manchas == 0) return Nota(
            EstadoNota.VACIO,
            "SENAMHI no estima lluvia moderada o más fuerte en el Perú ${lapso(e.valido_desde, e.valido_hasta)}. Puede haber lluvia ligera.",
            "Sin lluvia moderada o más fuerte · SENAMHI $emitido",
        )
        val hace = textoHace(ahoraMs - (Tiempo.parsearMs(e.emision) ?: ahoraMs))
        val texto = if (esInstante(e.valido_desde, e.valido_hasta)) "Experimental. Estimación de SENAMHI de las $emitido ($hace). Se renueva cada 10 min."
        else "Experimental. Estimación de SENAMHI de las $emitido ($hace), válida hasta las ${hhmm(e.valido_hasta)}. Se renueva cada 10 min."
        return Nota(EstadoNota.FRESCO, texto, "Lluvia ${horizonte(horizonteMin).chip} · SENAMHI $emitido")
    }

    /** "Sobre Jaén" (a menos de 5 km), "A unos 15 km de Jaén (Cajamarca)" (hasta 40 km) o null. */
    fun cercaDe(lat: Double, lon: Double, localidades: List<PronosticoLocalidad>): String? {
        var mejor: PronosticoLocalidad? = null; var mejorKm = Double.MAX_VALUE
        for (f in localidades) {
            val km = Geo.distanciaKm(lat, lon, f.lat ?: continue, f.lon ?: continue)
            if (km < mejorKm) { mejorKm = km; mejor = f }
        }
        val m = mejor ?: return null
        if (mejorKm > 40) return null
        if (mejorKm < 5) return "Sobre ${m.nombre}"
        val km = maxOf(5L, Math.round(mejorKm / 5) * 5)
        return "A unos $km km de ${m.nombre}${m.departamento?.let { " ($it)" } ?: ""}"
    }
}
