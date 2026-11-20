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
    val error: String? = null,                // fallo sin lista que mostrar: la pantalla muestra el error con "Reintentar"
    val errorRecarga: String? = null,         // fallo una recarga con la lista ya en pantalla: se avisa abajo y se consume
    val reportes: List<ReporteOrdenado> = emptyList(),
    val misVotos: Map<String, Int> = emptyMap(),
    val desde: String = "",                   // "tu ubicacion" o "Cajamarca (la ciudad elegida)"
    val porGps: Boolean = false,
    val obtenidoEn: Long? = null,
    val deCache: Boolean = false,
    val cargados: Boolean = false,            // report ya respondio alguna vez: recargar no vuelve al esqueleto
    val aviso: String? = null,                // resultado de la ultima accion (votar)
    val pideCuenta: Boolean = false,          // el aviso es "entra para..." (la pantalla ofrece ir a Cuenta)
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

    /**
     * Pide los reportes. El primer cargado va con esqueleto; las recargas que pide la persona (tirar,
     * "Actualizar la lista", "Reintentar") con el indicador de refresco, y las automaticas al volver a
     * la pestana o al cambiar la sesion (`silenciosa`) sin indicador. Si una recarga falla con la lista
     * ya en pantalla, la lista se conserva y el fallo va en `errorRecarga` (la pantalla lo avisa abajo).
     */
    fun cargar(silenciosa: Boolean = false) {
        viewModelScope.launch {
            val previo = _estado.value
            _estado.value = previo.copy(cargando = if (silenciosa && previo.cargados) previo.cargando else true, error = null)
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
                    cargando = false, error = null, cargados = true,
                    reportes = Comunidad.ordenar(vigentes, c.lat, c.lon), misVotos = votos,
                    desde = if (posicion != null) "tu ubicación" else "${depto.capital} (la ciudad elegida)",
                    porGps = posicion != null, obtenidoEn = r.obtenidoEn, deCache = r.deCache,
                )
            } catch (e: Exception) {
                val motivo = e.message ?: "sin respuesta"
                _estado.value = if (_estado.value.cargados) _estado.value.copy(cargando = false, errorRecarga = motivo)
                else _estado.value.copy(cargando = false, error = motivo)
            }
        }
    }

    fun limpiarErrorRecarga() { _estado.value = _estado.value.copy(errorRecarga = null) }

    /** Vota 1 o -1; null quita el voto. Sin sesion, avisa. Tras votar vuelve a pedir el reporte (la BD recalcula). */
    fun votar(reportId: String, valor: Int?) {
        if (!sesion.conSesion) { _estado.value = _estado.value.copy(aviso = "Entra para votar. ${Comunidad.POR_QUE_CUENTA}", pideCuenta = true); return }
        viewModelScope.launch {
            _estado.value = _estado.value.copy(votando = reportId, aviso = null, pideCuenta = false)
            try {
                repo.votar(reportId, valor)
                val nuevo = runCatching { repo.reporte(reportId).dato }.getOrNull()
                reemplazar(reportId, nuevo, valor)
            } catch (e: Exception) {
                _estado.value = _estado.value.copy(votando = null, aviso = e.message ?: "No se pudo votar.", pideCuenta = false)
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

    fun limpiarAviso() { _estado.value = _estado.value.copy(aviso = null, pideCuenta = false) }
}
