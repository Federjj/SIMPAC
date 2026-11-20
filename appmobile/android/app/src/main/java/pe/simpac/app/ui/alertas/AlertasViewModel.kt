package pe.simpac.app.ui.alertas

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.AlertaActual
import pe.simpac.app.dominio.Alertas

data class EstadoAlertas(
    val cargando: Boolean = true,
    val error: String? = null,
    val departamento: String = "",
    val soloMiZona: Boolean = true,
    val todas: List<AlertaActual> = emptyList(),
    val obtenidoEn: Long? = null,
    val deCache: Boolean = false,
    val cargadas: Boolean = false,              // alerta_actual ya respondio alguna vez: recargar no vuelve al esqueleto
) {
    /** Las que se muestran con un filtro dado (el de la pantalla o el que se va durante el cruce), ya ordenadas. */
    fun visiblesCon(soloMiZona: Boolean): List<AlertaActual> =
        Alertas.ordenar(if (soloMiZona) Alertas.deZona(todas, departamento) else todas)

    /** Las que se muestran segun el filtro, ya ordenadas. */
    val visibles: List<AlertaActual>
        get() = visiblesCon(soloMiZona)
    val oficiales: List<AlertaActual> get() = visibles.filter { Alertas.esOficial(it) }
    val lluvia: List<AlertaActual> get() = visibles.filter { !Alertas.esOficial(it) }
}

class AlertasViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val _estado = MutableStateFlow(EstadoAlertas())
    val estado: StateFlow<EstadoAlertas> = _estado

    init { cargar() }

    fun cargar() {
        viewModelScope.launch {
            _estado.value = _estado.value.copy(cargando = true, error = null)
            val conf = contenedor.ajustes.actual()
            try {
                val r = contenedor.repositorio.alertas()
                _estado.value = _estado.value.copy(cargando = false, departamento = conf.departamento, todas = r.dato, obtenidoEn = r.obtenidoEn, deCache = r.deCache, cargadas = true)
            } catch (e: Exception) {
                // con una lista ya cargada se conserva: la pantalla avisa abajo que no se pudo actualizar
                _estado.value = _estado.value.copy(cargando = false, departamento = conf.departamento, error = e.message ?: "sin respuesta")
            }
        }
    }

    fun filtrar(soloMiZona: Boolean) { _estado.value = _estado.value.copy(soloMiZona = soloMiZona) }
}
