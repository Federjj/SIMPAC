package pe.simpac.app.ui

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** Lo que Inicio le pide al Mapa: encuadrar tu punto y el cauce de un rio (rio_ana de rio_cauce_mapa). */
data class EncuadreMapa(val rioAna: String?, val lat: Double?, val lon: Double?)

/** Lo que una pestana le pide a otra: hoy, el encuadre del mapa que pide "Ver el rio en el mapa". */
class EstadoCompartido : ViewModel() {
    private val _encuadre = MutableStateFlow<EncuadreMapa?>(null)
    val encuadre: StateFlow<EncuadreMapa?> = _encuadre

    fun pedirEncuadre(e: EncuadreMapa) { _encuadre.value = e }
    fun encuadreAtendido() { _encuadre.value = null }
}
