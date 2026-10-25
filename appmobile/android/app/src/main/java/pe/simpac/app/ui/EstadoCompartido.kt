package pe.simpac.app.ui

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** Lo que una pestana le pide a otra: hoy, la ruta de la web que debe abrir el WebView del Mapa. */
class EstadoCompartido : ViewModel() {
    private val _rutaWeb = MutableStateFlow<String?>(null)
    val rutaWeb: StateFlow<String?> = _rutaWeb

    fun pedirRutaWeb(ruta: String) { _rutaWeb.value = ruta }
    fun rutaWebAtendida() { _rutaWeb.value = null }
}
