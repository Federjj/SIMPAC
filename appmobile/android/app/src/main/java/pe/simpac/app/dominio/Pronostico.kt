package pe.simpac.app.dominio

import pe.simpac.app.data.PronosticoVigente

/** Pronostico oficial de SENAMHI por localidad (vista pronostico_vigente): la localidad mas cercana y sus 3 dias. */
object Pronostico {
    /** Codigo de la localidad mas cercana a (lat, lon); null si no hay filas con coordenadas. */
    fun localidadCercana(filas: List<PronosticoVigente>, lat: Double, lon: Double): String? =
        filas.filter { it.lat != null && it.lon != null }
            .minByOrNull { Geo.distanciaKm(lat, lon, it.lat!!, it.lon!!) }?.codigo

    /** Las filas de esa localidad ordenadas por fecha (hoy, manana, pasado), una por dia. */
    fun franja(filas: List<PronosticoVigente>, codigo: String?): List<PronosticoVigente> {
        if (codigo == null) return emptyList()
        return filas.filter { it.codigo == codigo && it.fecha != null }
            .groupBy { it.fecha!! }.values.map { it.first() }
            .sortedBy { it.fecha }
            .take(3)
    }

    /**
     * Un dia en pocas palabras, sin inventar: "Lluvia en la tarde", "Puede haber tormenta", "Nublado"...
     * (misma lectura que frontend/src/lib/pronostico.js aspecto()).
     */
    fun resumenDia(f: PronosticoVigente): String {
        val momento = f.momento?.let { " $it" } ?: ""
        return when (f.tipo) {
            "tormenta" -> when {
                !f.posible -> "Tormenta$momento"
                f.lluvia_segura -> "Lluvia$momento, puede haber tormenta"
                else -> "Puede haber tormenta$momento"
            }
            "nieve" -> if (f.posible) "Puede nevar$momento" else "Nieve$momento"
            "lluvia" -> {
                val intensidad = f.intensidad?.let { " $it" } ?: ""
                if (f.posible) "Puede llover$momento" else "Lluvia$intensidad$momento"
            }
            else -> when (f.cielo) {
                "despejado" -> "Despejado"
                "nublado" -> "Nublado"
                "neblina" -> "Neblina"
                "parcial" -> "Algo nublado"
                else -> "Sin lluvia"
            }
        }
    }

    /** "18° / 6°" con lo que haya; "" sin temperaturas. */
    fun temperaturas(f: PronosticoVigente): String {
        val max = f.tmax?.let { "$it°" }
        val min = f.tmin?.let { "$it°" }
        return listOfNotNull(max, min).joinToString(" / ")
    }
}
