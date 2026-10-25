package pe.simpac.app.push

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.tasks.await
import pe.simpac.app.dominio.Departamentos

/**
 * Suscripcion a los temas de FCM segun el contrato con el backend:
 *   "pais"          -> alertas y emergencias de todo el pais
 *   "zona_<slug>"   -> las del departamento (Departamentos.slugTema)
 * El backend solo envia niveles alerta y emergencia (nunca aviso ni lluvia medida) y un mensaje
 * "SIMPAC: vuelve la calma en <Departamento>" cuando baja de alerta a normal/aviso.
 */
object PushSimpac {
    /** true si Firebase quedo configurado en esta instalacion (hubo google-services.json al compilar). */
    fun disponible(contexto: Context): Boolean = try {
        FirebaseApp.getApps(contexto).isNotEmpty()
    } catch (_: Exception) {
        false
    }

    /** true si Android dejara mostrar la notificacion (permiso POST_NOTIFICATIONS en Android 13+ y canal no apagado). */
    fun notificacionesPermitidas(contexto: Context): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(contexto, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return false
        return NotificationManagerCompat.from(contexto).areNotificationsEnabled()
    }

    suspend fun suscribir(tema: String) {
        FirebaseMessaging.getInstance().subscribeToTopic(tema).await()
    }

    suspend fun desuscribir(tema: String) {
        FirebaseMessaging.getInstance().unsubscribeFromTopic(tema).await()
    }

    /** Suscribe a "pais" y a la zona; si antes habia otra zona, la deja. Devuelve el tema de zona suscrito. */
    suspend fun activar(departamento: String, temaAnterior: String?): String {
        val tema = Departamentos.slugTema(departamento)
        if (temaAnterior != null && temaAnterior != tema) desuscribir(temaAnterior)
        suscribir(Departamentos.TEMA_PAIS)
        suscribir(tema)
        return tema
    }

    suspend fun desactivar(temaAnterior: String?) {
        if (temaAnterior != null) desuscribir(temaAnterior)
        desuscribir(Departamentos.TEMA_PAIS)
    }

    /** Token de registro del dispositivo (solo para diagnostico; se guarda cifrado). */
    suspend fun token(): String? = try {
        FirebaseMessaging.getInstance().token.await()
    } catch (_: Exception) {
        null
    }
}
