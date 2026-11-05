package pe.simpac.app.ubicacion

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withTimeoutOrNull

/** Posicion de la persona (lat, lon). */
data class Posicion(val lat: Double, val lon: Double)

/** Ubicacion solo en primer plano: una lectura cuando la pantalla la necesita, nunca en segundo plano. */
object Ubicacion {
    val PERMISOS = arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION)

    fun tienePermiso(contexto: Context): Boolean = PERMISOS.any {
        ContextCompat.checkSelfPermission(contexto, it) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * El Peru con margen (la misma caja que limita el mapa). Una posicion fuera (una persona de viaje,
     * o el GPS de fabrica de un emulador) no sirve para centrar el mapa ni para elegir el departamento.
     */
    fun enPeru(p: Posicion): Boolean = p.lat in -20.5..2.5 && p.lon in -84.5..-66.0

    /**
     * Ultima posicion conocida o una lectura nueva (hasta 8 s). null sin permiso, sin GPS o si no responde.
     * Primero Google Play Services (fused); si no esta, el LocationManager del sistema.
     */
    suspend fun actual(contexto: Context): Posicion? {
        if (!tienePermiso(contexto)) return null
        try {
            val fused = LocationServices.getFusedLocationProviderClient(contexto)
            @Suppress("MissingPermission")
            val ultima = withTimeoutOrNull(3_000) { fused.lastLocation.await() }
            if (ultima != null) return Posicion(ultima.latitude, ultima.longitude)
            @Suppress("MissingPermission")
            val nueva = withTimeoutOrNull(8_000) { fused.getCurrentLocation(Priority.PRIORITY_BALANCED_POWER_ACCURACY, null).await() }
            if (nueva != null) return Posicion(nueva.latitude, nueva.longitude)
        } catch (_: Exception) {
            // sin Google Play Services (o fallo): se intenta con el sistema
        }
        return try {
            val gestor = contexto.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return null
            @Suppress("MissingPermission")
            val loc = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER, LocationManager.PASSIVE_PROVIDER)
                .mapNotNull { p -> try { gestor.getLastKnownLocation(p) } catch (_: Exception) { null } }
                .maxByOrNull { it.time }
            loc?.let { Posicion(it.latitude, it.longitude) }
        } catch (_: Exception) {
            null
        }
    }
}
