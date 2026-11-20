package pe.simpac.app.ui.componentes

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.State
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Esqueletos con brillo (shimmer) para el estado "cargando": en vez de un texto "Cargando..." se
 * dibuja la silueta de lo que va a aparecer (lineas, bloques, circulos, tarjetas) con una banda de
 * luz que cruza la pantalla.
 *
 * Una sola transicion infinita por pantalla: `ProveedorEsqueleto` (o `ContenidoConEstado`, que ya lo
 * incluye) crea el avance del brillo una vez y todos los `Modifier.esqueleto` de adentro lo comparten.
 * La banda se calcula con la posicion de cada elemento en la ventana, asi que se ve como una sola luz
 * que recorre toda la pantalla, no una por tarjeta. Si no hay proveedor, cada elemento crea el suyo
 * (funciona, pero gasta mas).
 */
class EstadoEsqueleto internal constructor(internal val avance: State<Float>)

/** Avance del brillo (0 a 1, 1,3 s por vuelta). Crearlo una vez por pantalla. */
@Composable
fun rememberEsqueleto(): EstadoEsqueleto {
    val transicion = rememberInfiniteTransition(label = "esqueleto")
    val avance = transicion.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1300, easing = LinearEasing), RepeatMode.Restart),
        label = "brillo",
    )
    return remember { EstadoEsqueleto(avance) }
}

/** Brillo compartido por los esqueletos de la pantalla (nulo si nadie lo proveyo). */
val LocalEsqueleto = compositionLocalOf<EstadoEsqueleto?> { null }

/** Provee un solo brillo para todos los esqueletos de `contenido`. Si ya hay uno arriba, lo reutiliza. */
@Composable
fun ProveedorEsqueleto(contenido: @Composable () -> Unit) {
    if (LocalEsqueleto.current != null) {
        contenido()
    } else {
        val estado = rememberEsqueleto()
        CompositionLocalProvider(LocalEsqueleto provides estado) { contenido() }
    }
}

/**
 * Pinta el elemento como esqueleto: fondo `surfaceContainerHigh` (un gris que se distingue tanto sobre
 * las tarjetas blancas como sobre el fondo de la pantalla; `surfaceVariant` se confundia con ambos) con
 * una banda mas clara que se desplaza: en claro va un 55 % hacia el blanco y en oscuro un 12 % hacia
 * `onSurface`. La banda se lee solo al dibujar, asi que el brillo no recompone nada.
 */
fun Modifier.esqueleto(forma: Shape = RoundedCornerShape(8.dp)): Modifier = composed {
    val estado = LocalEsqueleto.current ?: rememberEsqueleto()
    val esquema = MaterialTheme.colorScheme
    val base = esquema.surfaceContainerHigh
    val brillo = if (base.luminance() < 0.5f) lerp(base, esquema.onSurface, 0.12f) else lerp(base, Color.White, 0.55f)
    val colores = remember(base, brillo) { listOf(base, brillo, base) }
    val anchoVentana = LocalWindowInfo.current.containerSize.width.toFloat().coerceAtLeast(1f)
    val banda = with(LocalDensity.current) { 220.dp.toPx() }
    val posicionX = remember { mutableFloatStateOf(0f) }
    this
        .onGloballyPositioned { c ->
            val x = c.positionInRoot().x
            if (x != posicionX.floatValue) posicionX.floatValue = x
        }
        .clip(forma)
        .drawBehind {
            val inicio = -banda + estado.avance.value * (anchoVentana + 2f * banda) - posicionX.floatValue
            drawRect(
                Brush.linearGradient(
                    colors = colores,
                    start = Offset(inicio, 0f),
                    end = Offset(inicio + banda, banda * 0.3f),
                ),
            )
        }
}

/** Una linea de texto en esqueleto (ancho como fraccion del disponible). */
@Composable
fun EsqueletoLinea(anchoFraccion: Float = 1f, alto: Dp = 14.dp, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth(anchoFraccion).height(alto).esqueleto(RoundedCornerShape(alto / 2)))
}

/** Un bloque (foto, mapa, boton, chip ancho) en esqueleto. */
@Composable
fun EsqueletoBloque(alto: Dp, modifier: Modifier = Modifier, forma: Shape = RoundedCornerShape(12.dp)) {
    Box(modifier.fillMaxWidth().height(alto).esqueleto(forma))
}

/** Un circulo (avatar, disco del semaforo, glifo) en esqueleto. */
@Composable
fun EsqueletoCirculo(tamano: Dp, modifier: Modifier = Modifier) {
    Box(modifier.size(tamano).esqueleto(CircleShape))
}

/** Tarjeta con el mismo borde y forma que `Seccion`: titulo opcional y `lineas` de texto. */
@Composable
fun EsqueletoTarjeta(lineas: Int = 3, modifier: Modifier = Modifier, conTitulo: Boolean = true) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = bordeTarjeta(),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (conTitulo) EsqueletoLinea(anchoFraccion = 0.45f, alto = 16.dp)
            repeat(lineas) { i -> EsqueletoLinea(anchoFraccion = anchoDeLinea(i, lineas), alto = 12.dp) }
        }
    }
}

/** `n` tarjetas en columna (separadas 10 dp, como las listas de la app). Se anuncia como "Cargando". */
@Composable
fun EsqueletoLista(n: Int = 3, modifier: Modifier = Modifier, lineas: Int = 3) {
    Column(
        modifier.fillMaxWidth().semantics(mergeDescendants = true) { contentDescription = "Cargando" },
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        repeat(n) { EsqueletoTarjeta(lineas = lineas) }
    }
}

/** Anchos variados para que la silueta parezca texto: la ultima corta, las impares un poco mas cortas. */
private fun anchoDeLinea(i: Int, n: Int): Float = when {
    i == n - 1 -> 0.6f
    i % 2 == 1 -> 0.85f
    else -> 1f
}
