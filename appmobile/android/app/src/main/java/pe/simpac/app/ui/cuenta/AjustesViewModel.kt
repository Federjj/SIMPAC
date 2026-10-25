package pe.simpac.app.ui.cuenta

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.AjustesApp
import pe.simpac.app.push.PushSimpac

class AjustesViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val ajustes = contenedor.ajustes

    val conf: StateFlow<AjustesApp?> = ajustes.flujo.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    /** Mensaje corto de la ultima accion (guardado, error de FCM...). */
    private val _mensaje = MutableStateFlow<String?>(null)
    val mensaje: StateFlow<String?> = _mensaje

    val pushDisponible: Boolean get() = PushSimpac.disponible(getApplication())

    fun guardarDepartamento(nombre: String) {
        viewModelScope.launch {
            ajustes.guardarDepartamento(nombre)
            ajustes.guardarUsarGps(false)
            val c = ajustes.actual()
            if (c.notificaciones && pushDisponible) activarPush(nombre)
        }
    }

    fun guardarDirecciones(api: String, web: String) {
        viewModelScope.launch {
            ajustes.guardarApiUrl(api)
            ajustes.guardarWebUrl(web)
            contenedor.repositorio.limpiarCache()
            _mensaje.value = "Direcciones guardadas."
        }
    }

    fun restablecerDirecciones() = guardarDirecciones(pe.simpac.app.data.Ajustes.API_POR_DEFECTO, pe.simpac.app.data.Ajustes.WEB_POR_DEFECTO)

    fun cambiarNotificaciones(activar: Boolean) {
        viewModelScope.launch {
            if (!pushDisponible) { _mensaje.value = "Notificaciones no configuradas en esta instalación."; return@launch }
            val c = ajustes.actual()
            try {
                if (activar) {
                    activarPush(c.departamento)
                    ajustes.guardarNotificaciones(true)
                    _mensaje.value = "Recibirás avisos de alerta o emergencia de ${c.departamento} y del país."
                } else {
                    PushSimpac.desactivar(c.temaZonaSuscrito)
                    ajustes.guardarTemaZona(null)
                    ajustes.guardarNotificaciones(false)
                    _mensaje.value = "Notificaciones apagadas."
                }
            } catch (e: Exception) {
                _mensaje.value = "No se pudo cambiar la suscripción (${e.message ?: "sin respuesta de Firebase"})."
            }
        }
    }

    private suspend fun activarPush(departamento: String) {
        val c = ajustes.actual()
        val tema = PushSimpac.activar(departamento, c.temaZonaSuscrito)
        ajustes.guardarTemaZona(tema)
        PushSimpac.token()?.let { contenedor.almacenSeguro.tokenFcm = it }
    }

    fun limpiarMensaje() { _mensaje.value = null }
}
