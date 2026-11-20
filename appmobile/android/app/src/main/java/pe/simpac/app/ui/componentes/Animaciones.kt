package pe.simpac.app.ui.componentes

import android.os.Build
import android.view.HapticFeedbackConstants
import android.view.View
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.EaseOutCubic
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.interaction.InteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Box
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.navigation.NavBackStackEntry
import kotlinx.coroutines.delay
import kotlin.math.roundToInt

/**
 * Specs de movimiento de la app. Cortas (150 a 300 ms) y con el easing de Material; nunca bloquean.
 * - Pestanas de la barra inferior: fundido de 200 ms.
 * - Detalle (comunidad/nuevo y comunidad/{id}): deslizamiento horizontal del 30 % + fundido, 250 ms,
 *   con sus inversos al volver (pop).
 * - `aparecer` / `desaparecer`: para `AnimatedVisibility` dentro de una pantalla (franjas, avisos).
 */
object Transiciones {
    const val PESTANA_MS = 200
    const val DETALLE_MS = 250
    const val APARECER_MS = 220
    const val ESCALON_MS = 35L
    const val MAX_ESCALONADOS = 6
    private const val FRACCION_DESLIZ = 0.3f

    private fun desliz(ancho: Int): Int = (ancho * FRACCION_DESLIZ).roundToInt()

    val entrarPestana: AnimatedContentTransitionScope<NavBackStackEntry>.() -> EnterTransition =
        { fadeIn(tween(PESTANA_MS, easing = FastOutSlowInEasing)) }
    val salirPestana: AnimatedContentTransitionScope<NavBackStackEntry>.() -> ExitTransition =
        { fadeOut(tween(PESTANA_MS, easing = FastOutSlowInEasing)) }

    /** El detalle entra desde la derecha (enterTransition). */
    val entrarDetalle: AnimatedContentTransitionScope<NavBackStackEntry>.() -> EnterTransition = {
        slideIntoContainer(AnimatedContentTransitionScope.SlideDirection.Start, tween(DETALLE_MS, easing = EaseOutCubic)) { desliz(it) } +
            fadeIn(tween(DETALLE_MS, easing = FastOutSlowInEasing))
    }

    /** Si desde el detalle se abre otra pantalla encima o se cambia de pestana, el detalle se funde (exitTransition). */
    val salirDetalle: AnimatedContentTransitionScope<NavBackStackEntry>.() -> ExitTransition = salirPestana

    /** Al volver (pop) hacia un detalle que quedo debajo, entra desde la izquierda (popEnterTransition). */
    val popEntrarDetalle: AnimatedContentTransitionScope<NavBackStackEntry>.() -> EnterTransition = {
        slideIntoContainer(AnimatedContentTransitionScope.SlideDirection.End, tween(DETALLE_MS, easing = EaseOutCubic)) { desliz(it) } +
            fadeIn(tween(DETALLE_MS, easing = FastOutSlowInEasing))
    }

    /** Al volver (pop) desde el detalle, sale hacia la derecha (popExitTransition). */
    val popSalirDetalle: AnimatedContentTransitionScope<NavBackStackEntry>.() -> ExitTransition = {
        slideOutOfContainer(AnimatedContentTransitionScope.SlideDirection.End, tween(DETALLE_MS, easing = EaseOutCubic)) { desliz(it) } +
            fadeOut(tween(DETALLE_MS, easing = FastOutSlowInEasing))
    }

    /** Para `AnimatedVisibility(visible, enter = Transiciones.aparecer, exit = Transiciones.desaparecer)`. */
    val aparecer: EnterTransition =
        fadeIn(tween(APARECER_MS, easing = FastOutSlowInEasing)) + expandVertically(tween(APARECER_MS, easing = FastOutSlowInEasing))
    val desaparecer: ExitTransition =
        fadeOut(tween(180, easing = FastOutSlowInEasing)) + shrinkVertically(tween(180, easing = FastOutSlowInEasing))
}

/**
 * Hace aparecer `contenido` con fundido y una subida de 12 dp, con un retraso de `indice` * 35 ms
 * (hasta 6 escalones; de ahi en adelante todos con el mismo retraso maximo). Solo la primera vez: se
 * recuerda con `rememberSaveable` que ya aparecio, asi que al volver a la pestana, al recomponer o al
 * volver a entrar en una lista no se repite. El fundido se aplica en `graphicsLayer` (sin recomponer).
 */
@Composable
fun AparecerEscalonado(indice: Int, modifier: Modifier = Modifier, contenido: @Composable () -> Unit) {
    var yaAparecio by rememberSaveable { mutableStateOf(false) }
    val avance = remember { Animatable(if (yaAparecio) 1f else 0f) }
    LaunchedEffect(Unit) {
        if (yaAparecio) return@LaunchedEffect
        delay(indice.coerceIn(0, Transiciones.MAX_ESCALONADOS - 1) * Transiciones.ESCALON_MS)
        avance.animateTo(1f, tween(Transiciones.APARECER_MS, easing = EaseOutCubic))
        yaAparecio = true
    }
    val desplazamiento = with(LocalDensity.current) { 12.dp.toPx() }
    Box(
        modifier.graphicsLayer {
            alpha = avance.value
            translationY = (1f - avance.value) * desplazamiento
        },
    ) { contenido() }
}

/**
 * Escala el elemento a 0,97 mientras esta presionado (150 ms). Pasar el mismo `interactionSource`
 * al `Card(onClick = ...)`, `Button` o `clickable` del elemento.
 */
fun Modifier.presionable(interactionSource: InteractionSource, escala: Float = 0.97f): Modifier = composed {
    val presionado by interactionSource.collectIsPressedAsState()
    val factor by animateFloatAsState(
        targetValue = if (presionado) escala else 1f,
        animationSpec = tween(150, easing = FastOutSlowInEasing),
        label = "presionable",
    )
    graphicsLayer {
        scaleX = factor
        scaleY = factor
    }
}

/** Numero que al cambiar sube (si crece) o baja (si decrece) con fundido, 200 ms. No anima la primera vez. */
@Composable
fun ContadorAnimado(
    valor: Int,
    modifier: Modifier = Modifier,
    style: TextStyle = MaterialTheme.typography.bodyMedium,
    color: Color = Color.Unspecified,
) {
    AnimatedContent(
        targetState = valor,
        modifier = modifier,
        transitionSpec = {
            val sube = targetState > initialState
            val entra = slideInVertically(tween(200, easing = FastOutSlowInEasing)) { if (sube) it else -it } +
                fadeIn(tween(200, easing = FastOutSlowInEasing))
            val sale = slideOutVertically(tween(200, easing = FastOutSlowInEasing)) { if (sube) -it else it } +
                fadeOut(tween(200, easing = FastOutSlowInEasing))
            (entra togetherWith sale).using(SizeTransform(clip = true))
        },
        label = "contador",
    ) { n ->
        Text(n.toString(), style = style, color = color)
    }
}

/**
 * Vibracion corta del sistema (respeta el ajuste "respuesta tactil" del telefono; sin permisos).
 * `val vista = LocalView.current` y luego `Haptica.toque(vista)` al pulsar algo, `Haptica.confirmar(vista)`
 * cuando una accion termino bien y `Haptica.rechazar(vista)` cuando fallo o no se puede.
 */
object Haptica {
    fun toque(view: View) {
        view.performHapticFeedback(HapticFeedbackConstants.CONTEXT_CLICK)
    }

    fun confirmar(view: View) {
        val constante = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) HapticFeedbackConstants.CONFIRM else HapticFeedbackConstants.VIRTUAL_KEY
        view.performHapticFeedback(constante)
    }

    fun rechazar(view: View) {
        val constante = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) HapticFeedbackConstants.REJECT else HapticFeedbackConstants.LONG_PRESS
        view.performHapticFeedback(constante)
    }
}
