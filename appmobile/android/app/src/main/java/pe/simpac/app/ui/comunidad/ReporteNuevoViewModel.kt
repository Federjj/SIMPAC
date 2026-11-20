package pe.simpac.app.ui.comunidad

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import pe.simpac.app.SimpacApp
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.ubicacion.Ubicacion

/** Como va la ubicacion del reporte. */
enum class EstadoGps { BUSCANDO, LISTA, SIN_PERMISO, SIN_SENAL, FUERA_DEL_PERU }

data class EstadoNuevo(
    val tipo: String? = null,
    val subtipo: String? = null,
    val descripcion: String = "",
    val fotoUri: Uri? = null,
    val lat: Double? = null,
    val lon: Double? = null,
    val gps: EstadoGps = EstadoGps.BUSCANDO,
    val errores: Map<String, String> = emptyMap(),
    val aviso: String? = null,
    val enviando: String? = null,     // null | "foto" | "reporte"
    val creadoId: String? = null,     // al terminar: id del reporte para abrir su detalle
    val rechazos: Int = 0,            // cuantas veces fallo un envio (validacion o red), para la vibracion de rechazo
)

/**
 * Formulario de un reporte nuevo: solo con sesion y con la posicion GPS real (sin pin manual, como
 * la web). La BD pone autor, confianza, estado y vencimiento, y aplica el limite de 5 por hora.
 */
class ReporteNuevoViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val repo = contenedor.repositorio
    private val sesion = contenedor.sesion

    private val _estado = MutableStateFlow(EstadoNuevo())
    val estado: StateFlow<EstadoNuevo> = _estado

    /** Una lectura nueva del GPS (la pantalla la pide al abrir y al conceder el permiso). */
    fun buscarUbicacion() {
        val app = getApplication<Application>()
        if (!Ubicacion.tienePermiso(app)) { _estado.value = _estado.value.copy(gps = EstadoGps.SIN_PERMISO, lat = null, lon = null); return }
        _estado.value = _estado.value.copy(gps = EstadoGps.BUSCANDO)
        viewModelScope.launch {
            val p = Ubicacion.actual(app)
            _estado.value = when {
                p == null -> _estado.value.copy(gps = EstadoGps.SIN_SENAL, lat = null, lon = null)
                !Comunidad.dentroDelPeru(p.lat, p.lon) -> _estado.value.copy(gps = EstadoGps.FUERA_DEL_PERU, lat = p.lat, lon = p.lon)
                else -> _estado.value.copy(gps = EstadoGps.LISTA, lat = p.lat, lon = p.lon, errores = _estado.value.errores - "pos")
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
}
