package pe.simpac.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import pe.simpac.app.data.Ajustes
import pe.simpac.app.data.AlmacenSeguro
import pe.simpac.app.data.AuthSupabase
import pe.simpac.app.data.CacheDisco
import pe.simpac.app.data.ClienteApi
import pe.simpac.app.data.ClienteSupabase
import pe.simpac.app.data.ComunidadSupabase
import pe.simpac.app.data.Repositorio
import pe.simpac.app.data.Sesion

/** Lo que comparten las pantallas: ajustes, repositorio, almacen seguro y sesion (inyeccion a mano, sin framework). */
class Contenedor(app: Application) {
    val ajustes = Ajustes(app)
    val almacenSeguro = AlmacenSeguro(app)
    private val alcance = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    /** Sesion de Supabase Auth (correo y contrasena), guardada solo en el almacen cifrado. */
    val sesion = Sesion(almacenSeguro, AuthSupabase(BuildConfig.SUPABASE_URL, BuildConfig.SUPABASE_KEY), alcance)
    val repositorio = Repositorio(
        supabase = ClienteSupabase(BuildConfig.SUPABASE_URL, BuildConfig.SUPABASE_KEY),
        api = ClienteApi(),
        cache = CacheDisco(File(app.filesDir, "simpac_cache")),
    ).apply {
        comunidad = ComunidadSupabase(BuildConfig.SUPABASE_URL, BuildConfig.SUPABASE_KEY, token = { sesion.token() })
    }

    init { sesion.iniciar() }
}

class SimpacApp : Application() {
    companion object {
        const val CANAL_ALERTAS = "alertas"
    }

    lateinit var contenedor: Contenedor
        private set

    override fun onCreate() {
        super.onCreate()
        contenedor = Contenedor(this)
        crearCanalNotificaciones()
    }

    /** Canal "alertas" de importancia alta: suena y aparece arriba aunque la app este cerrada. */
    private fun crearCanalNotificaciones() {
        val gestor = getSystemService(NotificationManager::class.java) ?: return
        val canal = NotificationChannel(
            CANAL_ALERTAS,
            getString(R.string.canal_alertas_nombre),
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = getString(R.string.canal_alertas_descripcion)
            enableVibration(true)
        }
        gestor.createNotificationChannel(canal)
    }
}
