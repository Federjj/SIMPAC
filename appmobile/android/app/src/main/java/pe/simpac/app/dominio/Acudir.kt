package pe.simpac.app.dominio

import pe.simpac.app.data.PuntoAcudir

/** Un punto con su distancia en linea recta desde la posicion de la persona. */
data class PuntoCercano(val punto: PuntoAcudir, val distanciaKm: Double)

/**
 * "A donde acudir": los 3 puntos para la tarjeta (salud, comisaria, bomberos), con la misma regla que
 * frontend/src/lib/acudir.js: para salud, el hospital que atiende 24 h mas cercano si esta a menos de
 * 15 km; si no, el establecimiento mas cercano de todos. Nunca se inventa un horario ni un telefono.
 */
object Acudir {
    const val RADIO_KM = 30.0
    const val HOSPITAL_HASTA_KM = 15.0
    val TIPOS_TARJETA = listOf("salud", "comisaria", "bomberos")

    fun etiquetaTipo(tipo: String): String = when (tipo) {
        "salud" -> "Salud"
        "comisaria" -> "Comisaría"
        "bomberos" -> "Bomberos"
        "zona_segura" -> "Zona segura"
        "albergue" -> "Albergue"
        else -> "Defensa Civil"
    }

    fun conDistancia(puntos: List<PuntoAcudir>, lat: Double, lon: Double): List<PuntoCercano> =
        puntos.filter { it.lat != null && it.lon != null }
            .map { PuntoCercano(it, Geo.distanciaKm(lat, lon, it.lat!!, it.lon!!)) }
            .sortedBy { it.distanciaKm }

    fun esHospital(p: PuntoAcudir): Boolean = Regex("^(hospital|instituto)", RegexOption.IGNORE_CASE).containsMatchIn(p.categoria ?: "")

    /** El establecimiento de salud que conviene mostrar (ver arriba); null si no hay ninguno. */
    fun mejorSalud(salud: List<PuntoCercano>): PuntoCercano? {
        val hospital24 = salud.firstOrNull { it.punto.atiende_24h == true && esHospital(it.punto) && it.distanciaKm < HOSPITAL_HASTA_KM }
        return hospital24 ?: salud.firstOrNull()
    }

    /** Los puntos de la tarjeta, en el orden salud, comisaria, bomberos (los tipos sin ninguno se omiten). */
    fun paraTarjeta(puntos: List<PuntoAcudir>, lat: Double, lon: Double): List<PuntoCercano> {
        val ordenados = conDistancia(puntos, lat, lon)
        return TIPOS_TARJETA.mapNotNull { tipo ->
            val deTipo = ordenados.filter { it.punto.tipo == tipo }
            if (tipo == "salud") mejorSalud(deTipo) else deTipo.firstOrNull()
        }
    }
}
