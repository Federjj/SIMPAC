package pe.simpac.app.ui.comunidad

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.ReporteVigente
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.ReporteOrdenado
import pe.simpac.app.ubicacion.Posicion
import pe.simpac.app.ubicacion.Ubicacion

data class EstadoComunidad(
    val cargando: Boolean = true,
    val error: String? = null,
    val reportes: List<ReporteOrdenado> = emptyList(),
    val misVotos: Map<String, Int> = emptyMap(),
    val desde: String = "",                   // "tu ubicacion" o "Cajamarca (la ciudad elegida)"
    val porGps: Boolean = false,
    val obtenidoEn: Long? = null,
    val deCache: Boolean = false,
    val aviso: String? = null,                // resultado de la ultima accion (votar)
    val votando: String? = null,              // id del reporte cuyo voto se esta enviando
)

/** Pestana Comunidad: reportes vigentes ordenados por confianza y cercania, y los votos propios. */
class ComunidadViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val repo = contenedor.repositorio
    private val sesion = contenedor.sesion

    private val _estado = MutableStateFlow(EstadoComunidad())
    val estado: StateFlow<EstadoComunidad> = _estado

    private var centro: Posicion? = null

    init { cargar() }

    fun cargar() {
        viewModelScope.launch {
            _estado.value = _estado.value.copy(cargando = _estado.value.reportes.isEmpty(), error = null)
            val conf = contenedor.ajustes.actual()
            val app = getApplication<Application>()
            val posicion = (if (conf.usarGps && Ubicacion.tienePermiso(app)) Ubicacion.actual(app) else null)?.takeIf { Ubicacion.enPeru(it) }
            val depto = Departamentos.porNombre(conf.departamento) ?: Departamentos.POR_DEFECTO
            val c = posicion ?: Posicion(depto.lat, depto.lon)
            centro = c
            try {
                val r = repo.reportesVigentes(Comunidad.CAJA_PERU)
                val ahora = System.currentTimeMillis()
                val vigentes = r.dato.filter { Comunidad.vigente(it, ahora) }
                val votos = if (sesion.conSesion) runCatching { repo.misVotos(vigentes.map { it.id }) }.getOrDefault(emptyMap()) else emptyMap()
                _estado.value = _estado.value.copy(
                    cargando = false, error = null,
                    reportes = Comunidad.ordenar(vigentes, c.lat, c.lon), misVotos = votos,
                    desde = if (posicion != null) "tu ubicación" else "${depto.capital} (la ciudad elegida)",
                    porGps = posicion != null, obtenidoEn = r.obtenidoEn, deCache = r.deCache,
                )
            } catch (e: Exception) {
                _estado.value = _estado.value.copy(cargando = false, error = e.message ?: "sin respuesta")
            }
        }
    }

    /** Vota 1 o -1; null quita el voto. Sin sesion, avisa. Tras votar vuelve a pedir el reporte (la BD recalcula). */
    fun votar(reportId: String, valor: Int?) {
        if (!sesion.conSesion) { _estado.value = _estado.value.copy(aviso = "Entra para votar. ${Comunidad.POR_QUE_CUENTA}"); return }
        viewModelScope.launch {
            _estado.value = _estado.value.copy(votando = reportId, aviso = null)
            try {
                repo.votar(reportId, valor)
                val nuevo = runCatching { repo.reporte(reportId).dato }.getOrNull()
                reemplazar(reportId, nuevo, valor)
            } catch (e: Exception) {
                _estado.value = _estado.value.copy(votando = null, aviso = e.message ?: "No se pudo votar.")
            }
        }
    }

    private fun reemplazar(reportId: String, nuevo: ReporteVigente?, voto: Int?) {
        val c = centro
        val e = _estado.value
        val lista = if (nuevo == null) e.reportes else e.reportes.map { if (it.reporte.id == reportId) it.copy(reporte = nuevo, puntaje = Comunidad.puntaje(nuevo, it.distanciaKm)) else it }
        val votos = e.misVotos.toMutableMap().apply { if (voto == null) remove(reportId) else put(reportId, voto) }
        _estado.value = e.copy(reportes = if (c != null) Comunidad.ordenar(lista.map { it.reporte }, c.lat, c.lon) else lista, misVotos = votos, votando = null)
    }

    fun limpiarAviso() { _estado.value = _estado.value.copy(aviso = null) }
}
