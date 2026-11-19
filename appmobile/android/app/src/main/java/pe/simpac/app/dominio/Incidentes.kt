package pe.simpac.app.dominio

import pe.simpac.app.data.RioIncidente
import kotlin.math.cos

/**
 * Desbordes y danos pasados de los rios vigilados (tabla rio_incidente): que se dibuja (los que
 * tienen lugar y no son crecidas medidas en la estacion), como se agrupan los que en pantalla
 * quedarian encimados y la nota de la capa (frontend/src/lib/zonaRio.js agruparIncidentes() y
 * map/layers/desbordes.js). Modulo puro.
 */
object Incidentes {
    const val RADIO_PX = 26.0          // un rombo mide 24 px
    const val DESDE_ZOOM = 12.0        // con el mapa mas alejado no se ven (web: banda z10)
    const val COLOR_ROMBO: Long = 0xFF334155
    val TIPO = mapOf("desborde" to "Desborde", "erosion" to "Erosión", "puente" to "Puente caído", "infraestructura" to "Daño en infraestructura", "crecida" to "Crecida")

    data class Grupo(val lat: Double, val lon: Double, val incidentes: List<RioIncidente>)

    private val RX_ANIO = Regex("(\\d{4})")
    private val RX_ULTIMO_ANIO = Regex("(\\d{4})(?!.*\\d{4})")

    fun anio(i: RioIncidente): Int? = RX_ANIO.find(i.fecha ?: i.fecha_texto ?: "")?.groupValues?.get(1)?.toIntOrNull()

    /** "’14" (ano corto) de un incidente. */
    fun anioCorto(i: RioIncidente): String = anio(i)?.let { "’" + it.toString().takeLast(2) } ?: ""

    /** Los que se dibujan: no son crecidas y tienen lugar. */
    fun dibujables(lista: List<RioIncidente>): List<RioIncidente> = lista.filter { it.tipo != "crecida" && it.lat != null && it.lon != null }

    fun metrosPorPixel(lat: Double, zoom: Double): Double = 156543.03 * cos(Math.toRadians(lat)) / Math.pow(2.0, zoom)

    private fun orden(i: RioIncidente): String = i.fecha ?: "${RX_ULTIMO_ANIO.find(i.fecha_texto ?: "")?.groupValues?.get(1) ?: "0000"}-12-31"

    /**
     * Del mas nuevo al mas viejo, juntos los que quedan a menos de radioM metros del mas nuevo de un
     * grupo (el grupo va en el punto de ese). Con el mapa alejado se juntan mas.
     */
    fun agrupar(incidentes: List<RioIncidente>, radioM: Double): List<Grupo> {
        val grupos = ArrayList<Grupo>()
        for (i in incidentes.sortedByDescending { orden(it) }) {
            val lat = i.lat ?: continue; val lon = i.lon ?: continue
            val k = grupos.indexOfFirst { Geo.distanciaKm(it.lat, it.lon, lat, lon) * 1000 < radioM }
            if (k >= 0) grupos[k] = grupos[k].copy(incidentes = grupos[k].incidentes + i)
            else grupos += Grupo(lat, lon, listOf(i))
        }
        return grupos
    }

    /** Radio de agrupacion en metros para ese zoom (26 px al zoom dado, en la latitud media). */
    fun radioM(lat: Double, zoom: Double): Double = RADIO_PX * metrosPorPixel(lat, zoom)

    private fun minuscula(t: String) = t.replaceFirstChar { it.lowercase() }

    /** "10 incidentes documentados del río Mashcón con lugar (2012–2025). ... Otro (1974) solo tiene el distrito." */
    fun nota(incidentes: List<RioIncidente>, nombres: Map<String, String>): String {
        val danos = incidentes.filter { it.tipo != "crecida" }
        val conLugar = danos.filter { it.lat != null }
        val sinLugar = danos.filter { it.lat == null }
        if (conLugar.isEmpty()) return "No hay desbordes documentados con lugar para los ríos vigilados."
        val ids = danos.map { it.rio }.toSet()
        val deQuien = if (ids.size == 1) "del ${minuscula(nombres[ids.first()] ?: "río")}" else "de los ríos vigilados"
        val anios = conLugar.mapNotNull { anio(it) }
        val rango = if (anios.isNotEmpty()) " (${anios.min()}–${anios.max()})" else ""
        val otros = sinLugar.mapNotNull { anio(it) }.joinToString(", ")
        val resto = when {
            sinLugar.isEmpty() -> ""
            sinLugar.size == 1 -> " Otro${if (otros.isNotEmpty()) " ($otros)" else ""} solo tiene el distrito."
            else -> " Otros ${sinLugar.size}${if (otros.isNotEmpty()) " ($otros)" else ""} solo tienen el distrito."
        }
        return "${conLugar.size} ${if (conLugar.size == 1) "incidente documentado" else "incidentes documentados"} $deQuien con lugar$rango. " +
            "La ubicación es aproximada: toca un rombo para ver la fuente.$resto"
    }
}
