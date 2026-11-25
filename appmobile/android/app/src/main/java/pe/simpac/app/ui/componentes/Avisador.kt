package pe.simpac.app.ui.componentes

import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.staticCompositionLocalOf
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Snackbar global de la app: un solo `SnackbarHostState` en el Scaffold de `AppSifec` (sale encima de
 * la barra inferior) y un ambito de corrutina que vive lo que la app, asi el aviso se muestra aunque la
 * pantalla que lo pidio ya se haya ido (por ejemplo "Reporte enviado" justo al abrir el detalle).
 *
 * En una pantalla:
 * ```
 * val avisador = LocalAvisador.current
 * Button(onClick = { avisador.avisar("Voto registrado") })
 * avisador.avisar("Sin conexión", accion = "Reintentar") { vm.cargar() }
 * ```
 */
class Avisador(val estado: SnackbarHostState, private val ambito: CoroutineScope) {
    /** Muestra `mensaje` (reemplaza el que estuviera visible). Con `accion`, el boton llama a `onAccion`. */
    fun avisar(
        mensaje: String,
        accion: String? = null,
        duracion: SnackbarDuration = SnackbarDuration.Short,
        onAccion: (() -> Unit)? = null,
    ) {
        ambito.launch {
            estado.currentSnackbarData?.dismiss()
            val resultado = estado.showSnackbar(
                message = mensaje,
                actionLabel = accion,
                withDismissAction = accion == null && duracion == SnackbarDuration.Indefinite,
                duration = duracion,
            )
            if (resultado == SnackbarResult.ActionPerformed) onAccion?.invoke()
        }
    }
}

/** Lo provee `AppSifec`; sin proveedor (vistas previas, pruebas) hay uno que no muestra nada. */
val LocalAvisador = staticCompositionLocalOf { Avisador(SnackbarHostState(), CoroutineScope(Dispatchers.Main.immediate)) }

/** Crea el avisador raiz (solo lo usa `AppSifec`; las pantallas leen `LocalAvisador.current`). */
@Composable
fun rememberAvisador(): Avisador {
    val ambito = rememberCoroutineScope()
    return remember { Avisador(SnackbarHostState(), ambito) }
}
