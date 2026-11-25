package pe.simpac.app.ui.cuenta

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import pe.simpac.app.SifecApp
import pe.simpac.app.data.AjustesApp
import pe.simpac.app.push.PushSifec

class AjustesViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SifecApp).contenedor
    private val ajustes = contenedor.ajustes

    val conf: StateFlow<AjustesApp?> = ajustes.flujo.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    /** Mensaje corto de la ultima accion (guardado, error de FCM...); la pantalla lo muestra en el snackbar global y lo consume. */
    private val _mensaje = MutableStateFlow<String?>(null)
    val mensaje: StateFlow<String?> = _mensaje

    val pushDisponible: Boolean get() = PushSifec.disponible(getApplication())

    fun guardarDepartamento(nombre: String) {
        viewModelScope.launch {
            ajustes.guardarDepartamento(nombre)
            ajustes.guardarUsarGps(false)
            val c = ajustes.actual()
            if (c.notificaciones && pushDisponible) {
                try {
                    activarPush(nombre)
                    _mensaje.value = "Zona guardada: $nombre. Los avisos ahora son de este departamento."
                } catch (e: Exception) {
                    _mensaje.value = "Zona guardada: $nombre, pero no se pudo cambiar la suscripción (${e.message ?: "sin respuesta de Firebase"})."
                }
            } else {
                _mensaje.value = "Zona guardada: $nombre."
            }
        }
    }

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
                    PushSifec.desactivar(c.temaZonaSuscrito)
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
        val tema = PushSifec.activar(departamento, c.temaZonaSuscrito)
        ajustes.guardarTemaZona(tema)
        PushSifec.token()?.let { contenedor.almacenSeguro.tokenFcm = it }
    }

    fun limpiarMensaje() { _mensaje.value = null }
}
