package pe.simpac.app.ubicacion

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.os.CancellationSignal
import android.os.Looper
import androidx.core.content.ContextCompat
import androidx.core.location.LocationListenerCompat
import androidx.core.location.LocationManagerCompat
import androidx.core.location.LocationRequestCompat
import com.google.android.gms.common.ConnectionResult
import com.google.android.gms.common.GoogleApiAvailability
import com.google.android.gms.location.CurrentLocationRequest
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.lastOrNull
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

/**
 * Posicion de la persona (lat, lon). `precisionM` es el radio de error en metros que informa el
 * telefono (null si no lo dice) y `tomadaEnMs` cuando se tomo (epoch ms). Las dos son opcionales para
 * que `Posicion(lat, lon)` siga valiendo donde solo hay un centro (la capital del departamento).
 */
data class Posicion(val lat: Double, val lon: Double, val precisionM: Float? = null, val tomadaEnMs: Long? = null) {
    /** Cuanto hace que se tomo (ms), o null si no se sabe. */
    fun antiguedadMs(ahora: Long = System.currentTimeMillis()): Long? = tomadaEnMs?.let { (ahora - it).coerceAtLeast(0L) }

    /** "unos 12 m" / "unos 2 km": el texto de la precision para la pantalla; null si no se sabe. */
    fun textoPrecision(): String? = precisionM?.let { Ubicacion.textoMetros(it) }
}

/** Por que no hay posicion, para que cada pantalla diga lo justo (y ofrezca la accion que toca). */
enum class MotivoSinPosicion {
    /** La app no tiene el permiso de ubicacion: se pide ahi mismo. */
    SIN_PERMISO,
    /** El permiso esta, pero la ubicacion del telefono (el interruptor del sistema) esta apagada. */
    UBICACION_APAGADA,
    /** Permiso y ubicacion prendidos, pero ningun proveedor respondio a tiempo (techo, sotano, sin red). */
    SIN_SENAL,
}

/** Resultado de una lectura: la posicion o el motivo de que no la haya. */
sealed interface Lectura {
    data class Hecha(val posicion: Posicion) : Lectura
    data class Fallida(val motivo: MotivoSinPosicion) : Lectura
}

/**
 * Ubicacion solo en primer plano: se lee cuando una pantalla la necesita (al abrir, al tocar "centrar",
 * al preparar un reporte) y nunca en segundo plano. Toda espera es cancelable: quien la pide la cancela
 * al salir de la pantalla o al irse la app al fondo (onStop / ViewModel limpiado), y la cancelacion
 * corta el pedido al telefono (CancellationToken / CancellationSignal / removeUpdates).
 *
 * Como lee: primero Google Play Services (fused); si el telefono no los trae, el LocationManager del
 * sistema (GPS y red). Una ultima posicion conocida fresca (menos de 2 min) y precisa (100 m o menos) se
 * usa sin encender el GPS; si no la hay, una lectura activa de alta precision hasta `maxEsperaMs`.
 */
object Ubicacion {
    val PERMISOS = arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION)

    /** Espera de las pantallas que cargan datos (Inicio, Mapa al abrir, Comunidad, Acudir): no demoran mas que esto por la posicion. */
    const val ESPERA_PANTALLA_MS = 10_000L
    /** Espera del boton "Centrar en tu ubicacion": la persona lo pidio y ve el progreso. */
    const val ESPERA_BOTON_MS = 20_000L
    /** Afinado de un reporte: se queda con la mejor precision que llegue en este tiempo (o para antes si baja de PRECISION_REPORTE_M). */
    const val ESPERA_REPORTE_MS = 25_000L
    /** Precision con la que un reporte se da por bien ubicado. */
    const val PRECISION_REPORTE_M = 30f
    /** Peor precision que vale para decidir el departamento sin esperar una mejor. */
    const val PRECISION_ZONA_M = 2_000f
    /** Cuanto espera Inicio por una posicion mejor cuando la primera es peor que PRECISION_ZONA_M. */
    const val ESPERA_MEJORA_ZONA_MS = 6_000L

    private const val FRESCA_MS = 2 * 60_000L
    private const val FRESCA_PRECISION_M = 100f
    private const val ULTIMA_VALIDA_MS = 10 * 60_000L
    private const val ULTIMA_ESPERA_MS = 3_000L
    private const val INTERVALO_MS = 1_000L
    private const val INTERVALO_MIN_MS = 500L

    fun tienePermiso(contexto: Context): Boolean = PERMISOS.any {
        ContextCompat.checkSelfPermission(contexto, it) == PackageManager.PERMISSION_GRANTED
    }

    /** Permiso de ubicacion precisa (FINE). Con solo la aproximada (Android 12+), el telefono redondea a unos 2 km y no llega nada mejor. */
    fun tienePermisoPreciso(contexto: Context): Boolean =
        ContextCompat.checkSelfPermission(contexto, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    /** El interruptor de ubicacion del telefono (ajustes del sistema), independiente del permiso de la app. */
    fun ubicacionActiva(contexto: Context): Boolean {
        val gestor = contexto.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return false
        return runCatching { LocationManagerCompat.isLocationEnabled(gestor) }.getOrDefault(false)
    }

    /** Por que no habria posicion ahora mismo, sin leer nada (sin permiso, ubicacion apagada o, si todo esta, sin senal). */
    fun motivoSinPosicion(contexto: Context): MotivoSinPosicion = when {
        !tienePermiso(contexto) -> MotivoSinPosicion.SIN_PERMISO
        !ubicacionActiva(contexto) -> MotivoSinPosicion.UBICACION_APAGADA
        else -> MotivoSinPosicion.SIN_SENAL
    }

    /**
     * El Peru con margen (la misma caja que limita el mapa). Una posicion fuera (una persona de viaje,
     * o el GPS de fabrica de un emulador) no sirve para centrar el mapa ni para elegir el departamento.
     */
    fun enPeru(p: Posicion): Boolean = p.lat in -20.5..2.5 && p.lon in -84.5..-66.0

    /** "unos 12 m", "unos 350 m", "unos 2 km". */
    fun textoMetros(metros: Float): String = when {
        metros < 1_000f -> "unos ${metros.toInt().coerceAtLeast(1)} m"
        else -> {
            val km = metros / 1_000f
            if (km < 10f) "unos ${String.format(java.util.Locale.US, "%.1f", km).removeSuffix(".0")} km" else "unos ${km.toInt()} km"
        }
    }

    /**
     * Una posicion, o el motivo de que no la haya. Sin permiso o con la ubicacion del telefono apagada
     * responde enseguida; si no, usa la ultima conocida si es fresca y precisa, y si no una lectura
     * activa de alta precision hasta `maxEsperaMs`. Si la lectura no responde pero hay una ultima
     * posicion de hace menos de 10 min, vale esa (con su `tomadaEnMs`, para que quien la use lo sepa).
     */
    suspend fun leer(contexto: Context, maxEsperaMs: Long = ESPERA_PANTALLA_MS): Lectura {
        if (!tienePermiso(contexto)) return Lectura.Fallida(MotivoSinPosicion.SIN_PERMISO)
        if (!ubicacionActiva(contexto)) return Lectura.Fallida(MotivoSinPosicion.UBICACION_APAGADA)
        val ahora = System.currentTimeMillis()
        val ultima = ultimaConocida(contexto)
        if (ultima != null && esFresca(ultima, ahora)) return Lectura.Hecha(ultima.aPosicion())
        val nueva = withTimeoutOrNull(maxEsperaMs) { lecturaActiva(contexto) }
        if (nueva != null) return Lectura.Hecha(nueva.aPosicion())
        if (ultima != null && ahora - ultima.time <= ULTIMA_VALIDA_MS) return Lectura.Hecha(ultima.aPosicion())
        return Lectura.Fallida(MotivoSinPosicion.SIN_SENAL)
    }

    /** Como `leer`, pero solo la posicion (null si no hay). Es lo que usan las pantallas que cargan datos. */
    suspend fun actual(contexto: Context, maxEsperaMs: Long = ESPERA_PANTALLA_MS): Posicion? =
        (leer(contexto, maxEsperaMs) as? Lectura.Hecha)?.posicion

    /**
     * La posicion para decidir el departamento (Inicio). Si la primera que llega es peor que 2 km (solo
     * red celular) y la app tiene permiso de ubicacion precisa, espera hasta 6 s mas por una mejor antes
     * de elegir la zona con ella; con solo el permiso aproximado no espera, porque no va a llegar nada mejor.
     */
    suspend fun paraZona(contexto: Context): Posicion? {
        val p = actual(contexto) ?: return null
        val precision = p.precisionM ?: return p
        if (precision <= PRECISION_ZONA_M || !tienePermisoPreciso(contexto)) return p
        val mejor = afinar(contexto, ESPERA_MEJORA_ZONA_MS, PRECISION_ZONA_M)
            .filter { (it.precisionM ?: Float.MAX_VALUE) < precision }
            .lastOrNull()
        return mejor ?: p
    }

    /**
     * Afina la posicion para un reporte: emite cada posicion mejor que la anterior (la primera puede ser
     * la ultima conocida fresca) y termina al bajar de `objetivoM` o al cumplirse `maxEsperaMs`. No emite
     * nada sin permiso, con la ubicacion apagada o si ningun proveedor responde. Al cancelar la
     * recoleccion se dejan de pedir actualizaciones al telefono.
     */
    fun afinar(contexto: Context, maxEsperaMs: Long = ESPERA_REPORTE_MS, objetivoM: Float = PRECISION_REPORTE_M): Flow<Posicion> = flow {
        if (!tienePermiso(contexto) || !ubicacionActiva(contexto)) return@flow
        var mejor = Float.MAX_VALUE
        val ahora = System.currentTimeMillis()
        ultimaConocida(contexto)?.takeIf { ahora - it.time <= FRESCA_MS }?.let { u ->
            mejor = u.precision()
            emit(u.aPosicion())
        }
        if (mejor <= objetivoM) return@flow
        withTimeoutOrNull(maxEsperaMs) {
            try {
                actualizaciones(contexto)
                    .onEach { loc ->
                        val precision = loc.precision()
                        if (precision < mejor) {
                            mejor = precision
                            emit(loc.aPosicion())
                        }
                    }
                    .first { mejor <= objetivoM }
            } catch (_: NoSuchElementException) {
                // el proveedor dejo de emitir sin llegar al objetivo: se queda lo mejor que hubo
            }
        }
    }

    // ---- por dentro ----

    private fun esFresca(loc: Location, ahora: Long): Boolean =
        ahora - loc.time <= FRESCA_MS && loc.hasAccuracy() && loc.accuracy <= FRESCA_PRECISION_M

    private fun Location.precision(): Float = if (hasAccuracy()) accuracy else Float.MAX_VALUE

    private fun Location.aPosicion(): Posicion = Posicion(latitude, longitude, if (hasAccuracy()) accuracy else null, time)

    private fun gestor(contexto: Context): LocationManager? = contexto.getSystemService(Context.LOCATION_SERVICE) as? LocationManager

    /** Google Play Services disponibles (fused). Sin ellos, todo va por el LocationManager del sistema. */
    private fun conPlay(contexto: Context): Boolean = runCatching {
        GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(contexto) == ConnectionResult.SUCCESS
    }.getOrDefault(false)

    /** La ultima posicion que el telefono recuerda (de esta o de otra app), o null si nadie pidio una nunca. */
    @Suppress("MissingPermission")
    private suspend fun ultimaConocida(contexto: Context): Location? {
        if (conPlay(contexto)) {
            val dePlay = runCatching {
                withTimeoutOrNull(ULTIMA_ESPERA_MS) { LocationServices.getFusedLocationProviderClient(contexto).lastLocation.await() }
            }.getOrNull()
            if (dePlay != null) return dePlay
        }
        val gestor = gestor(contexto) ?: return null
        return listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER, LocationManager.PASSIVE_PROVIDER)
            .mapNotNull { p -> runCatching { gestor.getLastKnownLocation(p) }.getOrNull() }
            .maxByOrNull { it.time }
    }

    /** Una lectura nueva de alta precision; quien llama pone el plazo con withTimeoutOrNull. */
    private suspend fun lecturaActiva(contexto: Context): Location? {
        if (conPlay(contexto)) {
            val dePlay = runCatching { lecturaActivaPlay(contexto) }.getOrNull()
            if (dePlay != null) return dePlay
        }
        val gestor = gestor(contexto) ?: return null
        return runCatching { lecturaActivaSistema(contexto, gestor) }.getOrNull()
    }

    // await(CancellationTokenSource) esta marcado experimental en kotlinx-coroutines-play-services 1.10
    @OptIn(ExperimentalCoroutinesApi::class)
    @Suppress("MissingPermission")
    private suspend fun lecturaActivaPlay(contexto: Context): Location? {
        val fused = LocationServices.getFusedLocationProviderClient(contexto)
        val fuente = CancellationTokenSource()
        val pedido = CurrentLocationRequest.Builder()
            .setPriority(Priority.PRIORITY_HIGH_ACCURACY)
            .setMaxUpdateAgeMillis(FRESCA_MS)
            .build()
        // await(fuente): si la corrutina se cancela (plazo o pantalla cerrada) se cancela el pedido al telefono
        return fused.getCurrentLocation(pedido, fuente.token).await(fuente)
    }

    /** Sin Play Services: GPS y red a la vez, gana el primero que responde (la red suele tardar 1 o 2 s). */
    @Suppress("MissingPermission")
    private suspend fun lecturaActivaSistema(contexto: Context, gestor: LocationManager): Location? = coroutineScope {
        val proveedores = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            .filter { runCatching { gestor.isProviderEnabled(it) }.getOrDefault(false) }
        if (proveedores.isEmpty()) return@coroutineScope null
        val canal = Channel<Location?>(proveedores.size)
        val trabajos = proveedores.map { p -> launch { canal.send(runCatching { unaLecturaSistema(contexto, gestor, p) }.getOrNull()) } }
        var resultado: Location? = null
        for (i in proveedores.indices) {
            val l = canal.receive()
            if (l != null) { resultado = l; break }
        }
        trabajos.forEach { it.cancel() }
        resultado
    }

    @Suppress("MissingPermission")
    private suspend fun unaLecturaSistema(contexto: Context, gestor: LocationManager, proveedor: String): Location? =
        suspendCancellableCoroutine { cont ->
            val senal = CancellationSignal()
            cont.invokeOnCancellation { runCatching { senal.cancel() } }
            LocationManagerCompat.getCurrentLocation(gestor, proveedor, senal, ContextCompat.getMainExecutor(contexto)) { loc ->
                if (cont.isActive) cont.resume(loc)
            }
        }

    /** Actualizaciones de alta precision mientras alguien las recoja; al dejar de recoger se cancelan en el telefono. */
    private fun actualizaciones(contexto: Context): Flow<Location> =
        (if (conPlay(contexto)) actualizacionesPlay(contexto) else actualizacionesSistema(contexto))
            .catch { /* un proveedor que falla no tumba la pantalla: simplemente no llega nada mas */ }

    @Suppress("MissingPermission")
    private fun actualizacionesPlay(contexto: Context): Flow<Location> = callbackFlow {
        val fused = LocationServices.getFusedLocationProviderClient(contexto)
        val pedido = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, INTERVALO_MS)
            .setMinUpdateIntervalMillis(INTERVALO_MIN_MS)
            .setWaitForAccurateLocation(false)
            .build()
        val callback = object : LocationCallback() {
            override fun onLocationResult(resultado: LocationResult) {
                resultado.locations.forEach { trySend(it) }
            }
        }
        fused.requestLocationUpdates(pedido, callback, Looper.getMainLooper()).addOnFailureListener { close(it) }
        awaitClose { fused.removeLocationUpdates(callback) }
    }

    @Suppress("MissingPermission")
    private fun actualizacionesSistema(contexto: Context): Flow<Location> = callbackFlow {
        val gestor = gestor(contexto) ?: run { close(); return@callbackFlow }
        val pedido = LocationRequestCompat.Builder(INTERVALO_MS)
            .setQuality(LocationRequestCompat.QUALITY_HIGH_ACCURACY)
            .setMinUpdateIntervalMillis(INTERVALO_MIN_MS)
            .build()
        val oyente = LocationListenerCompat { loc -> trySend(loc) }
        val proveedores = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            .filter { runCatching { gestor.isProviderEnabled(it) }.getOrDefault(false) }
        if (proveedores.isEmpty()) { close(); return@callbackFlow }
        for (p in proveedores) {
            runCatching { LocationManagerCompat.requestLocationUpdates(gestor, p, pedido, ContextCompat.getMainExecutor(contexto), oyente) }
        }
        awaitClose { runCatching { LocationManagerCompat.removeUpdates(gestor, oyente) } }
    }
}
