package pe.simpac.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import java.io.File
import pe.simpac.app.data.Ajustes
import pe.simpac.app.data.AlmacenSeguro
import pe.simpac.app.data.CacheDisco
import pe.simpac.app.data.ClienteApi
import pe.simpac.app.data.ClienteSupabase
import pe.simpac.app.data.Repositorio

/** Lo que comparten las pantallas: ajustes, repositorio y almacen seguro (inyeccion a mano, sin framework). */
class Contenedor(app: Application) {
    val ajustes = Ajustes(app)
    val almacenSeguro = AlmacenSeguro(app)
    val repositorio = Repositorio(
        supabase = ClienteSupabase(BuildConfig.SUPABASE_URL, BuildConfig.SUPABASE_KEY),
        api = ClienteApi(),
        cache = CacheDisco(File(app.filesDir, "simpac_cache")),
    )
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
