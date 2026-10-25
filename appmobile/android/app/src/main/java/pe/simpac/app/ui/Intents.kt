package pe.simpac.app.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast

/** Acciones que salen de la app: marcar un numero, abrir una direccion en el navegador o en un mapa. */
object Intents {
    /** Abre el marcador con el numero puesto (ACTION_DIAL: la persona confirma la llamada; no hace falta permiso). */
    fun marcar(contexto: Context, numero: String) {
        val limpio = numero.filter { it.isDigit() || it == '+' }
        if (limpio.isBlank()) { avisar(contexto, "Este lugar no tiene teléfono en la fuente"); return }
        lanzar(contexto, Intent(Intent.ACTION_DIAL, Uri.parse("tel:$limpio")), "No hay una app de teléfono")
    }

    fun abrirNavegador(contexto: Context, url: String) {
        lanzar(contexto, Intent(Intent.ACTION_VIEW, Uri.parse(url)), "No hay un navegador para abrir $url")
    }

    /** "Como llegar": geo:lat,lon?q=lat,lon(nombre) abre la app de mapas que tenga el telefono. */
    fun comoLlegar(contexto: Context, lat: Double, lon: Double, nombre: String) {
        val etiqueta = Uri.encode(nombre)
        val uri = Uri.parse("geo:$lat,$lon?q=$lat,$lon($etiqueta)")
        lanzar(contexto, Intent(Intent.ACTION_VIEW, uri), "No hay una app de mapas para abrir la ruta")
    }

    private fun lanzar(contexto: Context, intent: Intent, siFalla: String) {
        try {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            contexto.startActivity(intent)
        } catch (_: ActivityNotFoundException) {
            avisar(contexto, siFalla)
        }
    }

    private fun avisar(contexto: Context, texto: String) {
        Toast.makeText(contexto, texto, Toast.LENGTH_LONG).show()
    }
}
