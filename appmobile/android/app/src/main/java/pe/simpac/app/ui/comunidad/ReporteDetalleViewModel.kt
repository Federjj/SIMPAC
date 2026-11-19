package pe.simpac.app.ui.comunidad

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.ComentarioReporte
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.ReporteOrdenado
import pe.simpac.app.ubicacion.Posicion
import pe.simpac.app.ubicacion.Ubicacion

data class EstadoDetalle(
    val cargando: Boolean = true,
    val error: String? = null,
    val reporte: ReporteOrdenado? = null,      // null tras cargar = vencio o no existe
    val comentarios: List<ComentarioReporte> = emptyList(),
    val miVoto: Int? = null,
    val texto: String = "",
    val enviando: Boolean = false,
    val votando: Boolean = false,
    val aviso: String? = null,
)

private val UUID = Regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", RegexOption.IGNORE_CASE)

/** Detalle de un reporte (pages/ReporteDetalle.jsx): tarjeta completa, votos y comentarios. */
class ReporteDetalleViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val repo = contenedor.repositorio
    private val sesion = contenedor.sesion

    private val _estado = MutableStateFlow(EstadoDetalle())
    val estado: StateFlow<EstadoDetalle> = _estado
    private var id: String = ""
    private var centro: Posicion? = null

    fun cargar(reportId: String) {
        id = reportId
        if (!UUID.matches(reportId)) { _estado.value = EstadoDetalle(cargando = false, reporte = null); return }
        viewModelScope.launch {
            _estado.value = _estado.value.copy(cargando = true, error = null)
            val conf = contenedor.ajustes.actual()
            val app = getApplication<Application>()
            val posicion = (if (conf.usarGps && Ubicacion.tienePermiso(app)) Ubicacion.actual(app) else null)?.takeIf { Ubicacion.enPeru(it) }
            val depto = Departamentos.porNombre(conf.departamento) ?: Departamentos.POR_DEFECTO
            val c = posicion ?: Posicion(depto.lat, depto.lon)
            centro = c
            try {
                coroutineScope {
                    val tReporte = async { repo.reporte(reportId).dato }
                    val tComentarios = async { runCatching { repo.comentarios(reportId).dato }.getOrDefault(emptyList()) }
                    val r = tReporte.await()
                    val voto = if (r != null && sesion.conSesion) runCatching { repo.misVotos(listOf(reportId))[reportId] }.getOrNull() else null
                    _estado.value = _estado.value.copy(
                        cargando = false,
                        reporte = r?.takeIf { Comunidad.vigente(it) }?.let { Comunidad.ordenar(listOf(it), c.lat, c.lon).first() },
                        comentarios = tComentarios.await(), miVoto = voto,
                    )
                }
            } catch (e: Exception) {
                _estado.value = _estado.value.copy(cargando = false, error = e.message ?: "sin respuesta")
            }
        }
    }

    fun votar(valor: Int?) {
        if (!sesion.conSesion) { _estado.value = _estado.value.copy(aviso = "Entra para votar. ${Comunidad.POR_QUE_CUENTA}"); return }
        if (_estado.value.votando) return
        viewModelScope.launch {
            _estado.value = _estado.value.copy(votando = true, aviso = null)
            try {
                repo.votar(id, valor)
                val nuevo = runCatching { repo.reporte(id).dato }.getOrNull()
                val c = centro
                _estado.value = _estado.value.copy(
                    votando = false, miVoto = valor,
                    reporte = if (nuevo != null && c != null) Comunidad.ordenar(listOf(nuevo), c.lat, c.lon).first() else _estado.value.reporte,
                )
            } catch (e: Exception) {
                _estado.value = _estado.value.copy(votando = false, aviso = e.message ?: "No se pudo votar.")
            }
        }
    }

    fun cambiarTexto(t: String) { _estado.value = _estado.value.copy(texto = t.take(Comunidad.MAX_COMENTARIO + 50)) }

    fun comentar() {
        val (texto, error) = Comunidad.validarTexto(_estado.value.texto)
        if (texto == null) { _estado.value = _estado.value.copy(aviso = error); return }
        if (!sesion.conSesion) { _estado.value = _estado.value.copy(aviso = "Entra para comentar."); return }
        viewModelScope.launch {
            _estado.value = _estado.value.copy(enviando = true, aviso = null)
            try {
                val c = repo.comentar(id, texto)
                _estado.value = _estado.value.copy(enviando = false, texto = "", comentarios = _estado.value.comentarios + c)
            } catch (e: Exception) {
                _estado.value = _estado.value.copy(enviando = false, aviso = e.message ?: "No se pudo comentar.")
            }
        }
    }

    fun limpiarAviso() { _estado.value = _estado.value.copy(aviso = null) }
}
