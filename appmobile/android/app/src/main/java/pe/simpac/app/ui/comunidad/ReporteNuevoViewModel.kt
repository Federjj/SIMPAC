package pe.simpac.app.ui.comunidad

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import pe.simpac.app.SimpacApp
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.ubicacion.MotivoSinPosicion
import pe.simpac.app.ubicacion.Ubicacion

/** Como va la ubicacion del reporte. */
enum class EstadoGps { BUSCANDO, LISTA, SIN_PERMISO, UBICACION_APAGADA, SIN_SENAL, FUERA_DEL_PERU }

data class EstadoNuevo(
    val tipo: String? = null,
    val subtipo: String? = null,
    val descripcion: String = "",
    val fotoUri: Uri? = null,
    val lat: Double? = null,
    val lon: Double? = null,
    val gps: EstadoGps = EstadoGps.BUSCANDO,
    val precisionM: Float? = null,     // radio de error de la posicion (m), si el telefono lo dice
    val afinando: Boolean = false,     // se siguen pidiendo posiciones para mejorar la precision
    val soloAproximada: Boolean = false,   // la app solo tiene permiso de ubicacion aproximada (Android 12+): no va a llegar nada mejor que ~2 km
    val notaGps: String? = null,       // aviso corto bajo la ubicacion ("No llego una posicion mas precisa...")
    val errores: Map<String, String> = emptyMap(),
    val aviso: String? = null,
    val enviando: String? = null,     // null | "foto" | "reporte"
    val creadoId: String? = null,     // al terminar: id del reporte para abrir su detalle
    val rechazos: Int = 0,            // cuantas veces fallo un envio (validacion o red), para la vibracion de rechazo
) {
    /** La posicion ya sirve pero podria mejorar (peor que 30 m o sin dato de precision): se ofrece "Mejorar precision". */
    val puedeMejorar: Boolean get() = gps == EstadoGps.LISTA && !afinando && !soloAproximada && (precisionM == null || precisionM > Ubicacion.PRECISION_REPORTE_M)
}

/**
 * Formulario de un reporte nuevo: solo con sesion y con la posicion GPS real (sin pin manual, como
 * la web). La BD pone autor, confianza, estado y vencimiento, y aplica el limite de 5 por hora.
 *
 * Ubicacion: en vez de una sola lectura, un afinado (`Ubicacion.afinar`) de alta precision de hasta 25 s
 * que se queda con la mejor posicion que llega (la primera se usa enseguida; para antes si baja de 30 m).
 * Solo en primer plano: la pantalla lo detiene al irse la app al fondo (onStop) y lo reanuda al volver;
 * al limpiarse el ViewModel se cancela con viewModelScope y se dejan de pedir posiciones al telefono.
 */
class ReporteNuevoViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val repo = contenedor.repositorio
    private val sesion = contenedor.sesion

    private val _estado = MutableStateFlow(EstadoNuevo())
    val estado: StateFlow<EstadoNuevo> = _estado

    private var trabajoGps: Job? = null
    private var generacion = 0          // cada busqueda nueva sube el numero: una vieja que termina tarde no toca el estado
    private var interrumpida = false

    /** Busca la posicion desde cero (la pantalla la pide al abrir, al conceder el permiso y en "Volver a buscar"). */
    fun buscarUbicacion() = afinarPosicion(mantener = false)

    /** Con una posicion ya lista, sigue pidiendo hasta 25 s por una mas precisa sin perder la que hay (boton "Mejorar precision"). */
    fun mejorarPrecision() = afinarPosicion(mantener = true)

    /** La app se fue al fondo: no se pide ubicacion en segundo plano. Se conserva la posicion que ya habia. */
    fun detenerBusqueda() {
        if (trabajoGps?.isActive == true) interrumpida = true
        trabajoGps?.cancel()
        trabajoGps = null
        if (_estado.value.afinando) _estado.value = _estado.value.copy(afinando = false)
    }

    /** La app volvio al frente: solo retoma lo que se habia interrumpido al irse al fondo. */
    fun reanudarBusqueda() {
        if (!interrumpida) return
        interrumpida = false
        afinarPosicion(mantener = _estado.value.gps == EstadoGps.LISTA)
    }

    private fun afinarPosicion(mantener: Boolean) {
        val app = getApplication<Application>()
        trabajoGps?.cancel()
        interrumpida = false
        val soloAproximada = Ubicacion.tienePermiso(app) && !Ubicacion.tienePermisoPreciso(app)
        when (Ubicacion.motivoSinPosicion(app)) {
            MotivoSinPosicion.SIN_PERMISO -> { _estado.value = _estado.value.copy(gps = EstadoGps.SIN_PERMISO, lat = null, lon = null, precisionM = null, afinando = false, notaGps = null, soloAproximada = false); return }
            MotivoSinPosicion.UBICACION_APAGADA -> { _estado.value = _estado.value.copy(gps = EstadoGps.UBICACION_APAGADA, lat = null, lon = null, precisionM = null, afinando = false, notaGps = null, soloAproximada = soloAproximada); return }
            MotivoSinPosicion.SIN_SENAL -> {}
        }
        _estado.value = if (mantener && _estado.value.gps == EstadoGps.LISTA) {
            _estado.value.copy(afinando = true, notaGps = null, soloAproximada = soloAproximada)
        } else {
            _estado.value.copy(gps = EstadoGps.BUSCANDO, lat = null, lon = null, precisionM = null, afinando = true, notaGps = null, soloAproximada = soloAproximada)
        }
        val precisionAntes = _estado.value.precisionM
        val mia = ++generacion
        trabajoGps = viewModelScope.launch {
            var llego = false
            try {
                Ubicacion.afinar(app).collect { p ->
                    if (mia != generacion) return@collect
                    val actual = _estado.value
                    if (mantener && actual.gps == EstadoGps.LISTA && precisionAntes != null && (p.precisionM ?: Float.MAX_VALUE) >= precisionAntes) return@collect
                    llego = true
                    _estado.value = if (!Comunidad.dentroDelPeru(p.lat, p.lon)) {
                        actual.copy(gps = EstadoGps.FUERA_DEL_PERU, lat = p.lat, lon = p.lon, precisionM = p.precisionM)
                    } else {
                        actual.copy(gps = EstadoGps.LISTA, lat = p.lat, lon = p.lon, precisionM = p.precisionM, errores = actual.errores - "pos")
                    }
                }
            } finally {
                // solo la busqueda vigente cierra el estado; una cancelada (fondo, busqueda nueva) solo apaga "afinando"
                if (mia == generacion) {
                    val cancelada = !isActive
                    val actual = _estado.value
                    _estado.value = when {
                        cancelada -> actual.copy(afinando = false)
                        actual.gps == EstadoGps.BUSCANDO -> actual.copy(gps = EstadoGps.SIN_SENAL, lat = null, lon = null, precisionM = null, afinando = false)
                        !llego && mantener && actual.gps == EstadoGps.LISTA ->
                            actual.copy(afinando = false, notaGps = "No llegó una posición más precisa. Prueba a cielo abierto o cerca de una ventana.")
                        else -> actual.copy(afinando = false)
                    }
                }
            }
        }
    }

    fun elegirTipo(id: String) { _estado.value = _estado.value.copy(tipo = id, subtipo = null, errores = _estado.value.errores - "tipo" - "subtipo") }
    fun elegirSubtipo(id: String) { _estado.value = _estado.value.copy(subtipo = id, errores = _estado.value.errores - "subtipo") }
    fun cambiarDescripcion(texto: String) { _estado.value = _estado.value.copy(descripcion = texto.take(Comunidad.MAX_DESCRIPCION + 50), errores = _estado.value.errores - "descripcion") }
    fun ponerFoto(uri: Uri?) { _estado.value = _estado.value.copy(fotoUri = uri, errores = _estado.value.errores - "foto") }
    fun limpiarAviso() { _estado.value = _estado.value.copy(aviso = null) }

    fun enviar() {
        val e = _estado.value
        if (e.enviando != null) return
        if (!sesion.conSesion) { _estado.value = e.copy(aviso = "Entra para reportar.", rechazos = e.rechazos + 1); return }
        val errores = Comunidad.validarReporte(e.tipo, e.subtipo, e.descripcion, e.lat, e.lon)
        if (errores.isNotEmpty()) { _estado.value = e.copy(errores = errores, aviso = null, rechazos = e.rechazos + 1); return }
        _estado.value = e.copy(errores = errores, aviso = null)
        viewModelScope.launch {
            try {
                var fotoUrl: String? = null
                if (e.fotoUri != null) {
                    _estado.value = _estado.value.copy(enviando = "foto")
                    val jpeg = try { Fotos.reducirJpeg(getApplication(), e.fotoUri) } catch (ex: Exception) {
                        _estado.value = _estado.value.copy(
                            enviando = null, rechazos = _estado.value.rechazos + 1,
                            aviso = "No se pudo procesar la foto. Prueba con otra o envía el reporte sin foto.",
                        )
                        return@launch
                    }
                    val uid = sesion.usuarioId ?: throw pe.simpac.app.data.ErrorConsulta(Comunidad.SESION_VENCIDA)
                    fotoUrl = repo.subirFoto(jpeg, uid)
                }
                _estado.value = _estado.value.copy(enviando = "reporte")
                val creado = repo.crearReporte(e.tipo!!, e.subtipo, e.descripcion.trim().ifBlank { null }, fotoUrl, e.lat!!, e.lon!!)
                _estado.value = _estado.value.copy(enviando = null, creadoId = creado.id)
            } catch (ex: Exception) {
                _estado.value = _estado.value.copy(
                    enviando = null, rechazos = _estado.value.rechazos + 1,
                    aviso = ex.message ?: "No se pudo enviar el reporte. Inténtalo de nuevo en un momento.",
                )
            }
        }
    }

    override fun onCleared() {
        trabajoGps?.cancel()
        super.onCleared()
    }
}
