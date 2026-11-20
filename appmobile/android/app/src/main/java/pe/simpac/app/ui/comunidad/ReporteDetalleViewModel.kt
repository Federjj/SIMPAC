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
    val error: String? = null,                 // fallo sin reporte que mostrar: la pantalla muestra el error con "Reintentar"
    val errorRecarga: String? = null,          // fallo una recarga con el reporte ya en pantalla: se avisa abajo y se consume
    val cargado: Boolean = false,              // el reporte ya respondio alguna vez: volver a cargar no tapa nada con el esqueleto
    val reporte: ReporteOrdenado? = null,      // null tras cargar = vencio o no existe
    val comentarios: List<ComentarioReporte> = emptyList(),
    val miVoto: Int? = null,
    val texto: String = "",
    val enviando: Boolean = false,
    val votando: Boolean = false,
    val aviso: String? = null,
    val pideCuenta: Boolean = false,           // el aviso es "entra para..." (la pantalla ofrece ir a Cuenta)
    val comentado: Int = 0,                    // cuantos comentarios se publicaron en esta pantalla (para confirmar)
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

    /**
     * Pide el reporte, sus comentarios y el voto propio. El primer cargado va con esqueleto; las veces
     * siguientes (al volver a la pantalla o al cambiar la sesion) se recarga sin tapar lo que hay, y si
     * esa recarga falla el reporte se conserva y el fallo va en `errorRecarga`.
     */
    fun cargar(reportId: String) {
        id = reportId
        if (!UUID.matches(reportId)) { _estado.value = EstadoDetalle(cargando = false, cargado = true, reporte = null); return }
        viewModelScope.launch {
            val previo = _estado.value
            _estado.value = previo.copy(cargando = !previo.cargado, error = null)
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
                        cargando = false, cargado = true,
                        reporte = r?.takeIf { Comunidad.vigente(it) }?.let { Comunidad.ordenar(listOf(it), c.lat, c.lon).first() },
                        comentarios = tComentarios.await(), miVoto = voto,
                    )
                }
            } catch (e: Exception) {
                val motivo = e.message ?: "sin respuesta"
                _estado.value = if (_estado.value.cargado) _estado.value.copy(cargando = false, errorRecarga = motivo)
                else _estado.value.copy(cargando = false, error = motivo)
            }
        }
    }

    fun limpiarErrorRecarga() { _estado.value = _estado.value.copy(errorRecarga = null) }

    fun votar(valor: Int?) {
        if (!sesion.conSesion) { _estado.value = _estado.value.copy(aviso = "Entra para votar. ${Comunidad.POR_QUE_CUENTA}", pideCuenta = true); return }
        if (_estado.value.votando) return
        viewModelScope.launch {
            _estado.value = _estado.value.copy(votando = true, aviso = null, pideCuenta = false)
            try {
                repo.votar(id, valor)
                val nuevo = runCatching { repo.reporte(id).dato }.getOrNull()
                val c = centro
                _estado.value = _estado.value.copy(
                    votando = false, miVoto = valor,
                    reporte = if (nuevo != null && c != null) Comunidad.ordenar(listOf(nuevo), c.lat, c.lon).first() else _estado.value.reporte,
                )
            } catch (e: Exception) {
                _estado.value = _estado.value.copy(votando = false, aviso = e.message ?: "No se pudo votar.", pideCuenta = false)
            }
        }
    }

    fun cambiarTexto(t: String) { _estado.value = _estado.value.copy(texto = t.take(Comunidad.MAX_COMENTARIO + 50)) }

    fun comentar() {
        val (texto, error) = Comunidad.validarTexto(_estado.value.texto)
        if (texto == null) { _estado.value = _estado.value.copy(aviso = error, pideCuenta = false); return }
        if (!sesion.conSesion) { _estado.value = _estado.value.copy(aviso = "Entra para comentar.", pideCuenta = true); return }
        viewModelScope.launch {
            _estado.value = _estado.value.copy(enviando = true, aviso = null, pideCuenta = false)
            try {
                val c = repo.comentar(id, texto)
                _estado.value = _estado.value.copy(
                    enviando = false, texto = "",
                    comentarios = _estado.value.comentarios + c,
                    comentado = _estado.value.comentado + 1,
                )
            } catch (e: Exception) {
                _estado.value = _estado.value.copy(enviando = false, aviso = e.message ?: "No se pudo comentar.", pideCuenta = false)
            }
        }
    }

    fun limpiarAviso() { _estado.value = _estado.value.copy(aviso = null, pideCuenta = false) }
}
