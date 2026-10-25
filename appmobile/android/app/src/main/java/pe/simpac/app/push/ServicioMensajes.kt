package pe.simpac.app.push

import android.app.PendingIntent
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import pe.simpac.app.MainActivity
import pe.simpac.app.R
import pe.simpac.app.SimpacApp
import pe.simpac.app.dominio.Nivel

/**
 * Recibe los mensajes de FCM cuando la app esta abierta (en segundo plano FCM los muestra solo, con el
 * canal e icono por defecto del manifest) y guarda el token nuevo cifrado.
 * Mensaje del backend: notification.title = "SIMPAC: ALERTA en Cajamarca", notification.body =
 * titular_corto; data = { nivel, zona, generado_en, ruta: "/alertas" }.
 */
class ServicioMensajes : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        (application as? SimpacApp)?.contenedor?.almacenSeguro?.tokenFcm = token
    }

    override fun onMessageReceived(mensaje: RemoteMessage) {
        val datos = mensaje.data
        val titulo = mensaje.notification?.title ?: datos["titulo"] ?: "SIMPAC"
        val cuerpo = mensaje.notification?.body ?: datos["cuerpo"] ?: datos["titular_corto"] ?: ""
        val ruta = datos["ruta"] ?: "/alertas"
        val nivel = Nivel.desde(datos["nivel"])
        mostrar(titulo, cuerpo, ruta, nivel)
    }

    private fun mostrar(titulo: String, cuerpo: String, ruta: String, nivel: Nivel) {
        if (!PushSimpac.notificacionesPermitidas(this)) return   // sin permiso no se puede mostrar
        val intent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            putExtra(MainActivity.EXTRA_RUTA, ruta)
        }
        val pendiente = PendingIntent.getActivity(
            this, ruta.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val color = if (nivel == Nivel.SIN_DATO) 0xFF1D4ED8.toInt() else nivel.fondo.toInt()
        val notificacion = NotificationCompat.Builder(this, SimpacApp.CANAL_ALERTAS)
            .setSmallIcon(R.drawable.ic_notificacion)
            .setColor(color)
            .setContentTitle(titulo)
            .setContentText(cuerpo)
            .setStyle(NotificationCompat.BigTextStyle().bigText(cuerpo))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(pendiente)
            .build()
        try {
            NotificationManagerCompat.from(this).notify((System.currentTimeMillis() % Int.MAX_VALUE).toInt(), notificacion)
        } catch (_: SecurityException) {
            // el permiso se revoco entre la comprobacion y el aviso
        }
    }
}
