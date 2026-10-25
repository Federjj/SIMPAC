package pe.simpac.app.dominio

import java.text.Normalizer

/**
 * Los 24 departamentos y el Callao con el nombre canonico (igual que backend/ingesta/departamentos.py
 * y titular_zona.departamento) y el centro de su capital (frontend/src/data/cities.js).
 */
data class Departamento(val nombre: String, val capital: String, val lat: Double, val lon: Double)

object Departamentos {
    val TODOS: List<Departamento> = listOf(
        Departamento("Cajamarca", "Cajamarca", -7.1617, -78.5127),
        Departamento("Amazonas", "Chachapoyas", -6.2299, -77.8688),
        Departamento("Áncash", "Huaraz", -9.5278, -77.5278),
        Departamento("Apurímac", "Abancay", -13.6339, -72.8814),
        Departamento("Arequipa", "Arequipa", -16.409, -71.5375),
        Departamento("Ayacucho", "Ayacucho", -13.1587, -74.2239),
        Departamento("Callao", "Callao", -12.0566, -77.1181),
        Departamento("Cusco", "Cusco", -13.532, -71.9675),
        Departamento("Huancavelica", "Huancavelica", -12.7861, -74.9736),
        Departamento("Huánuco", "Huánuco", -9.9306, -76.2422),
        Departamento("Ica", "Ica", -14.0678, -75.7286),
        Departamento("Junín", "Huancayo", -12.0686, -75.2103),
        Departamento("La Libertad", "Trujillo", -8.1091, -79.0215),
        Departamento("Lambayeque", "Chiclayo", -6.7714, -79.8409),
        Departamento("Lima", "Lima", -12.0464, -77.0428),
        Departamento("Loreto", "Iquitos", -3.7491, -73.2538),
        Departamento("Madre de Dios", "Puerto Maldonado", -12.5933, -69.1891),
        Departamento("Moquegua", "Moquegua", -17.1934, -70.9355),
        Departamento("Pasco", "Cerro de Pasco", -10.6828, -76.2565),
        Departamento("Piura", "Piura", -5.1945, -80.6328),
        Departamento("Puno", "Puno", -15.8402, -70.0219),
        Departamento("San Martín", "Moyobamba", -6.0341, -76.9711),
        Departamento("Tacna", "Tacna", -18.0066, -70.2463),
        Departamento("Tumbes", "Tumbes", -3.5669, -80.4515),
        Departamento("Ucayali", "Pucallpa", -8.3791, -74.5539),
    )

    /** Cajamarca: foco del proyecto y zona por defecto. */
    val POR_DEFECTO: Departamento = TODOS.first()

    fun porNombre(nombre: String?): Departamento? {
        if (nombre.isNullOrBlank()) return null
        val clave = sinTildes(nombre).lowercase().replace(Regex("[^a-z]"), "")
        return TODOS.firstOrNull { sinTildes(it.nombre).lowercase().replace(Regex("[^a-z]"), "") == clave }
    }

    /** El departamento cuya capital queda mas cerca (respaldo cuando no se puede consultar las estaciones). */
    fun masCercano(lat: Double, lon: Double): Departamento =
        TODOS.minByOrNull { Geo.distanciaKm(lat, lon, it.lat, it.lon) } ?: POR_DEFECTO

    /**
     * Tema de FCM del departamento (contrato con el backend): "zona_" + nombre en minusculas, sin tildes,
     * con los espacios como guion bajo. "La Libertad" -> "zona_la_libertad", "Áncash" -> "zona_ancash".
     */
    fun slugTema(nombre: String): String {
        val base = sinTildes(nombre).lowercase().trim().replace(Regex("\\s+"), "_").replace(Regex("[^a-z_]"), "")
        return "zona_$base"
    }

    /** Tema nacional (todas las zonas). */
    const val TEMA_PAIS = "pais"

    fun sinTildes(texto: String): String =
        Normalizer.normalize(texto, Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "")
}
