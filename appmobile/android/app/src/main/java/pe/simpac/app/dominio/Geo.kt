package pe.simpac.app.dominio

import kotlin.math.atan2
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

/** Caja de grados { oeste, sur, este, norte } para los filtros por lat/lon de la API REST de Supabase. */
data class Caja(val oeste: Double, val sur: Double, val este: Double, val norte: Double)

object Geo {
    private const val RADIO_TIERRA_KM = 6371.0088

    /** Distancia en linea recta (haversine) en kilometros. */
    fun distanciaKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val dLat = Math.toRadians(lat2 - lat1)
        val dLon = Math.toRadians(lon2 - lon1)
        val a = sin(dLat / 2) * sin(dLat / 2) +
            cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) * sin(dLon / 2) * sin(dLon / 2)
        return 2 * RADIO_TIERRA_KM * atan2(sqrt(a), sqrt(1 - a))
    }

    /** "450 m" hasta 1 km, "2.3 km" hasta 10 km, "27 km" despues. */
    fun distanciaTexto(km: Double): String = when {
        km < 1.0 -> "${(km * 1000).roundToInt()} m"
        km < 10.0 -> String.format(java.util.Locale.US, "%.1f km", km)
        else -> "${km.roundToInt()} km"
    }

    /**
     * Caja alrededor de un punto con radioKm a cada lado, redondeada hacia afuera a decimas de grado
     * (misma regla que frontend/src/lib/acudir.js cajaAlrededor: asi la clave de la cache se repite).
     */
    fun cajaAlrededor(lat: Double, lon: Double, radioKm: Double, paso: Double = 0.1): Caja {
        val dLat = radioKm / 111.32
        val dLon = radioKm / (111.32 * max(0.2, cos(Math.toRadians(lat))))
        fun abajo(v: Double) = redondear(floor(v / paso) * paso)
        fun arriba(v: Double) = redondear(ceil(v / paso) * paso)
        return Caja(abajo(lon - dLon), abajo(lat - dLat), arriba(lon + dLon), arriba(lat + dLat))
    }

    private fun redondear(v: Double): Double = (v * 10).roundToInt() / 10.0
}
