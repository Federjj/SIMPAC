package pe.simpac.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import pe.simpac.app.ui.AppSimpac
import pe.simpac.app.ui.Pestana
import pe.simpac.app.ui.theme.SimpacTheme

class MainActivity : ComponentActivity() {
    companion object {
        /** Extra con la ruta de la web ("/alertas", "/cuenta"...) que manda la notificacion o la pantalla Cuenta. */
        const val EXTRA_RUTA = "ruta"
    }

    /** Pestana que pide la notificacion al tocarla (cambia con cada intent nuevo). */
    private var pestanaPedida by mutableStateOf<Pestana?>(null)
    private var vecesPedida by mutableStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        leerRuta(intent)
        setContent {
            SimpacTheme {
                AppSimpac(pestanaInicial = pestanaPedida, vecesPedida = vecesPedida)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        leerRuta(intent)
    }

    private fun leerRuta(intent: Intent?) {
        val ruta = intent?.getStringExtra(EXTRA_RUTA) ?: return
        pestanaPedida = Pestana.desdeRuta(ruta)
        vecesPedida += 1
    }
}
