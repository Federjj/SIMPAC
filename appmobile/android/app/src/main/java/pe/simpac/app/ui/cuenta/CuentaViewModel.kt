package pe.simpac.app.ui.cuenta

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.PerfilPropio
import pe.simpac.app.data.ReporteVigente
import pe.simpac.app.dominio.Comunidad

enum class ModoCuenta { ENTRAR, REGISTRO, RECUPERAR, CONFIRMAR }

data class EstadoCuenta(
    val modo: ModoCuenta = ModoCuenta.ENTRAR,
    val email: String = "",
    val password: String = "",
    val nombre: String = "",
    val errores: Map<String, String> = emptyMap(),
    val aviso: String? = null,
    val enviando: Boolean = false,
    val confirmacion: Pair<String, String>? = null,   // (titulo, texto) de la pantalla "Revisa tu correo"
    // con sesion
    val perfil: PerfilPropio? = null,
    val cargandoPerfil: Boolean = false,
    val errorPerfil: String? = null,
    val misReportes: List<ReporteVigente>? = null,
    val errorReportes: String? = null,
    val saliendo: Boolean = false,
)

/** Pestana Cuenta: entrar, crear cuenta, olvide mi contrasena y, con sesion, perfil, mis reportes y salir (pages/Cuenta.jsx). */
class CuentaViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val sesion = contenedor.sesion
    private val repo = contenedor.repositorio

    private val _estado = MutableStateFlow(EstadoCuenta())
    val estado: StateFlow<EstadoCuenta> = _estado

    fun cambiarModo(m: ModoCuenta) { _estado.value = _estado.value.copy(modo = m, errores = emptyMap(), aviso = null) }
    fun cambiarEmail(v: String) { _estado.value = _estado.value.copy(email = v, errores = _estado.value.errores - "email") }
    fun cambiarPassword(v: String) { _estado.value = _estado.value.copy(password = v, errores = _estado.value.errores - "password") }
    fun cambiarNombre(v: String) { _estado.value = _estado.value.copy(nombre = v.take(80), errores = _estado.value.errores - "nombre") }
    fun limpiarAviso() { _estado.value = _estado.value.copy(aviso = null) }

    /** A donde vuelve el enlace del correo: la pagina Cuenta de la web (misma regla que lib/sesion.js volverA). */
    private suspend fun volverA(): String = contenedor.ajustes.actual().webUrl.trimEnd('/') + "/cuenta"

    fun enviar() {
        val e = _estado.value
        if (e.enviando) return
        val correo = e.email.trim()
        when (e.modo) {
            ModoCuenta.RECUPERAR -> {
                val errores = Comunidad.validarCuenta(correo, "xxxxxx")
                _estado.value = e.copy(errores = errores, aviso = null)
                if (errores.isNotEmpty()) return
                viewModelScope.launch {
                    _estado.value = _estado.value.copy(enviando = true)
                    try {
                        sesion.recuperar(correo, volverA())
                        _estado.value = _estado.value.copy(
                            enviando = false, modo = ModoCuenta.CONFIRMAR,
                            confirmacion = "Revisa tu correo" to "Si $correo tiene una cuenta, le enviamos un enlace para elegir una contraseña nueva. El enlace abre la web de SIMPAC; después vuelve a la app y entra con la contraseña nueva. Revisa también la carpeta de spam.",
                        )
                    } catch (ex: Exception) {
                        _estado.value = _estado.value.copy(enviando = false, aviso = ex.message ?: "No se pudo completar.")
                    }
                }
            }
            ModoCuenta.ENTRAR, ModoCuenta.REGISTRO -> {
                val registro = e.modo == ModoCuenta.REGISTRO
                val errores = Comunidad.validarCuenta(correo, e.password, e.nombre, conNombre = registro)
                _estado.value = e.copy(errores = errores, aviso = null)
                if (errores.isNotEmpty()) return
                viewModelScope.launch {
                    _estado.value = _estado.value.copy(enviando = true)
                    try {
                        if (registro) {
                            val r = sesion.registrar(correo, e.password, e.nombre.trim(), volverA())
                            if (r.confirmar) {
                                _estado.value = _estado.value.copy(
                                    enviando = false, modo = ModoCuenta.CONFIRMAR, password = "",
                                    confirmacion = "Revisa tu correo" to if (r.yaExistia)
                                        "Si $correo ya tenía una cuenta, no se crea otra: entra con tu contraseña o pide una nueva. Si no la tenía, te enviamos un enlace para confirmarla."
                                    else
                                        "Te enviamos un enlace a $correo para confirmar tu cuenta. Hasta que lo abras no podrás entrar. El enlace abre la web de SIMPAC; después vuelve a la app y entra con tu correo y contraseña. Revisa también la carpeta de spam.",
                                )
                            } else {
                                _estado.value = _estado.value.copy(enviando = false, password = "")
                            }
                        } else {
                            sesion.entrar(correo, e.password)
                            _estado.value = _estado.value.copy(enviando = false, password = "")
                        }
                    } catch (ex: Exception) {
                        _estado.value = _estado.value.copy(enviando = false, aviso = ex.message ?: "No se pudo completar.")
                    }
                }
            }
            ModoCuenta.CONFIRMAR -> cambiarModo(ModoCuenta.ENTRAR)
        }
    }

    /** Perfil (nombre y reputacion) y mis reportes; se llama al tener sesion. */
    fun cargarPerfil() {
        viewModelScope.launch {
            _estado.value = _estado.value.copy(cargandoPerfil = true, errorPerfil = null, errorReportes = null)
            val perfil = runCatching { repo.perfilPropio() }
            val reportes = runCatching { repo.misReportes() }
            perfil.getOrNull()?.nombre?.let { sesion.actualizarNombre(it) }
            _estado.value = _estado.value.copy(
                cargandoPerfil = false,
                perfil = perfil.getOrNull() ?: _estado.value.perfil,
                errorPerfil = perfil.exceptionOrNull()?.message,
                misReportes = reportes.getOrNull() ?: _estado.value.misReportes,
                errorReportes = reportes.exceptionOrNull()?.message,
            )
        }
    }

    fun salir() {
        viewModelScope.launch {
            _estado.value = _estado.value.copy(saliendo = true)
            sesion.salir()
            _estado.value = EstadoCuenta()
        }
    }
}
