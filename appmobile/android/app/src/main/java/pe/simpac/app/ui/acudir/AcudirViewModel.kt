package pe.simpac.app.ui.acudir

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import pe.simpac.app.SimpacApp
import pe.simpac.app.dominio.Acudir
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.Geo
import pe.simpac.app.dominio.PuntoCercano
import pe.simpac.app.ubicacion.Posicion
import pe.simpac.app.ubicacion.Ubicacion

data class EstadoAcudir(
    val cargando: Boolean = true,
    val error: String? = null,
    val desde: String = "",                   // "tu ubicacion" o "el centro de Cajamarca"
    val porGps: Boolean = false,
    val puntos: List<PuntoCercano> = emptyList(),
    val cuantosEnCaja: Int = 0,
    val obtenidoEn: Long? = null,
    val deCache: Boolean = false,
)

class AcudirViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val _estado = MutableStateFlow(EstadoAcudir())
    val estado: StateFlow<EstadoAcudir> = _estado

    init { cargar() }

    fun cargar() {
        viewModelScope.launch {
            _estado.value = _estado.value.copy(cargando = true, error = null)
            val conf = contenedor.ajustes.actual()
            val app = getApplication<Application>()
            val posicion = (if (conf.usarGps && Ubicacion.tienePermiso(app)) Ubicacion.actual(app) else null)?.takeIf { Ubicacion.enPeru(it) }
            val depto = Departamentos.porNombre(conf.departamento) ?: Departamentos.POR_DEFECTO
            val centro = posicion ?: Posicion(depto.lat, depto.lon)
            val desde = if (posicion != null) "tu ubicación" else "el centro de ${depto.capital}"
            try {
                val r = contenedor.repositorio.puntosAcudir(Geo.cajaAlrededor(centro.lat, centro.lon, Acudir.RADIO_KM))
                _estado.value = EstadoAcudir(
                    cargando = false, desde = desde, porGps = posicion != null,
                    puntos = Acudir.paraTarjeta(r.dato, centro.lat, centro.lon),
                    cuantosEnCaja = r.dato.size, obtenidoEn = r.obtenidoEn, deCache = r.deCache,
                )
            } catch (e: Exception) {
                _estado.value = EstadoAcudir(cargando = false, desde = desde, porGps = posicion != null, error = e.message ?: "sin respuesta")
            }
        }
    }
}
