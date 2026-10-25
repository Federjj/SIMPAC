package pe.simpac.app.dominio

/**
 * Semaforo de SIMPAC, con los mismos colores que la web (frontend/src/lib/nivel.js).
 * Siempre se muestra color + etiqueta: nunca solo el color.
 * fondo = color del disco o la franja; tinta = texto sobre fondo claro.
 */
enum class Nivel(val clave: String, val etiqueta: String, val fondo: Long, val tinta: Long, val orden: Int) {
    EMERGENCIA("emergencia", "Emergencia", 0xFFDB0404, 0xFFB91C1C, 0),
    ALERTA("alerta", "Alerta", 0xFFF58E27, 0xFFC2410C, 1),
    AVISO("aviso", "Aviso", 0xFFEAB308, 0xFFA16207, 2),
    NORMAL("normal", "Normal", 0xFF15803D, 0xFF15803D, 3),
    SIN_DATO("sin_dato", "Sin datos", 0xFF9CA3AF, 0xFF4B5563, 4);

    /** El texto sobre el disco del semaforo: blanco salvo en amarillo (el blanco no se lee). */
    val textoSobreFondo: Long get() = if (this == AVISO) 0xFF422006 else 0xFFFFFFFF

    companion object {
        /** 'alerta' -> ALERTA; algo desconocido o nulo -> SIN_DATO (nunca "Normal" por algo no medido). */
        fun desde(texto: String?): Nivel = entries.firstOrNull { it.clave == texto?.trim()?.lowercase() } ?: SIN_DATO
    }
}
