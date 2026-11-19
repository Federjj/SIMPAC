package pe.simpac.app.data

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Estado de la sesion que observan las pantallas. */
sealed interface EstadoSesion {
    /** Todavia no se leyo el almacen cifrado (ninguna pantalla dice "entra para..." antes de tiempo). */
    data object Cargando : EstadoSesion
    data object SinSesion : EstadoSesion
    data class ConSesion(val usuarioId: String, val email: String?, val nombre: String?) : EstadoSesion
}

/**
 * La sesion de Supabase Auth de la app: vive solo en AlmacenSeguro (cifrado con el Keystore), se
 * refresca antes de vencer y expone un estado observable. Es el equivalente de hooks/useSesion.js.
 * Las acciones lanzan ErrorConsulta con el mensaje en lenguaje claro (Comunidad.mensajeAuth).
 */
class Sesion(
    private val almacen: AlmacenSeguro,
    private val auth: AuthSupabase,
    private val alcance: CoroutineScope,
) {
    private val _estado = MutableStateFlow<EstadoSesion>(EstadoSesion.Cargando)
    val estado: StateFlow<EstadoSesion> = _estado

    @Volatile private var actual: SesionGuardada? = null
    private val candado = Mutex()

    val conSesion: Boolean get() = actual != null
    val usuarioId: String? get() = actual?.usuarioId

    /** Lee la sesion guardada (fuera del hilo principal) y, si ya vencio, la refresca. */
    fun iniciar() {
        alcance.launch {
            val guardada = withContext(Dispatchers.IO) { SesionGuardada.desdeJson(almacen.sesionJson) }
            publicar(guardada)
            if (guardada != null && guardada.porVencer()) token()
        }
    }

    private suspend fun publicar(s: SesionGuardada?) {
        actual = s
        withContext(Dispatchers.IO) { almacen.sesionJson = s?.aJson() }
        _estado.value = if (s == null) EstadoSesion.SinSesion else EstadoSesion.ConSesion(s.usuarioId, s.email, s.nombre)
    }

    /**
     * Access token vigente para las escrituras: si esta por vencer (menos de 60 s) lo refresca primero.
     * null sin sesion. Si Auth rechaza el refresh token (4xx) la sesion se borra; sin red se devuelve
     * el token que hay (PostgREST dira si ya no sirve).
     */
    suspend fun token(): String? = candado.withLock {
        val s = actual ?: return null
        if (!s.porVencer()) return s.accessToken
        try {
            val nueva = auth.refrescar(s.refreshToken)
            publicar(nueva.copy(nombre = nueva.nombre ?: s.nombre))
            nueva.accessToken
        } catch (e: ErrorAuth) {
            if (e.codigoHttp in 400..499) { publicar(null); null } else s.accessToken
        } catch (_: Exception) {
            s.accessToken
        }
    }

    suspend fun entrar(email: String, password: String) {
        val s = auth.entrar(email, password)
        candado.withLock { publicar(s) }
    }

    /** Registro; si Auth no exige confirmar, deja la sesion abierta. */
    suspend fun registrar(email: String, password: String, nombre: String, volverA: String): ResultadoRegistro {
        val r = auth.registrar(email, password, nombre, volverA)
        if (r.sesion != null) candado.withLock { publicar(r.sesion) }
        return r
    }

    suspend fun recuperar(email: String, volverA: String) = auth.recuperar(email, volverA)

    suspend fun salir() {
        val s = actual
        candado.withLock { publicar(null) }
        if (s != null) auth.salir(s.accessToken)
    }

    /** El nombre del perfil (la BD manda sobre user_metadata) para mostrarlo en Cuenta. */
    suspend fun actualizarNombre(nombre: String?) {
        val s = actual ?: return
        if (nombre.isNullOrBlank() || nombre == s.nombre) return
        candado.withLock { publicar(s.copy(nombre = nombre)) }
    }
}
