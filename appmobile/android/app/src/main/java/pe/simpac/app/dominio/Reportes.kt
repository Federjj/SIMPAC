package pe.simpac.app.dominio

/**
 * Reportes de la comunidad en el mapa (tabla report): tipos, colores y etiquetas de
 * frontend/src/lib/reportTypes.js (deben coincidir con el CHECK de report.tipo y report.subtipo), y
 * la opacidad del pin por el saldo de votos (map/layers/incidentes.js). Modulo puro.
 */
object Reportes {
    data class Subtipo(val id: String, val etiqueta: String)
    data class Tipo(val id: String, val etiqueta: String, val color: Long, val subtipos: List<Subtipo> = emptyList())

    val TIPOS = listOf(
        Tipo("inundacion", "Inundación", 0xFF3B3BEB),
        Tipo("huayco", "Huayco / deslizamiento", 0xFFEB3B3B),
        Tipo("lluvia_intensa", "Lluvia intensa", 0xFF3BEBEB),
        Tipo("via_bloqueada", "Vía bloqueada", 0xFF111111),
        Tipo("atasco", "Atasco", 0xFFEBEB3B, listOf(Subtipo("leve", "Leve"), Subtipo("moderado", "Moderado"), Subtipo("detenido", "Detenido"))),
        Tipo("bache", "Bache", 0xFFF58E27),
        Tipo("accidente", "Accidente", 0xFFDB0404),
        Tipo("otro", "Otro", 0xFF6B7280),
    )
    val ESTADO = mapOf("sin_confirmar" to "Sin confirmar", "confirmado" to "Confirmado", "descartado" to "Descartado")

    fun tipo(id: String?): Tipo = TIPOS.firstOrNull { it.id == id } ?: TIPOS.last()

    /** "Atasco moderado" o "Inundación". */
    fun titulo(tipoId: String?, subtipoId: String?): String {
        val t = tipo(tipoId)
        val s = t.subtipos.firstOrNull { it.id == subtipoId }?.etiqueta
        return if (s != null) "${t.etiqueta} ${s.lowercase()}" else t.etiqueta
    }

    /**
     * Opacidad del pin: un reporte descartado por la comunidad se sigue viendo, pero atenuado (0.45);
     * con mas votos en contra que a favor, algo atenuado (0.65); si no, entero.
     */
    fun opacidad(estado: String?, likes: Int?, dislikes: Int?): Float = when {
        estado == "descartado" -> 0.45f
        (likes ?: 0) - (dislikes ?: 0) < 0 -> 0.65f
        else -> 1f
    }
}
