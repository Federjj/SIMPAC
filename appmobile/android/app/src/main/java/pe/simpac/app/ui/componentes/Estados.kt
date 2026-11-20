package pe.simpac.app.ui.componentes

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.MutableTransitionState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * Estado vacio sobrio y centrado: icono en un disco neutro, titulo, explicacion y una accion opcional
 * (por ejemplo "Actualizar" o "Reportar"). El icono es decorativo: el titulo ya dice lo que pasa.
 */
@Composable
fun EstadoVacio(
    icono: ImageVector,
    titulo: String,
    texto: String,
    modifier: Modifier = Modifier,
    accionTexto: String? = null,
    onAccion: (() -> Unit)? = null,
) {
    Column(
        modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier.size(56.dp).background(MaterialTheme.colorScheme.surfaceVariant, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icono, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(28.dp))
        }
        Spacer(Modifier.height(12.dp))
        Text(titulo, style = MaterialTheme.typography.titleMedium, textAlign = TextAlign.Center)
        Spacer(Modifier.height(6.dp))
        Text(texto, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        if (accionTexto != null && onAccion != null) {
            Spacer(Modifier.height(14.dp))
            OutlinedButton(onClick = onAccion) { Text(accionTexto) }
        }
    }
}

/** Error con boton "Reintentar": icono, titulo, el mensaje y el boton; aparece con un fundido corto. */
@Composable
fun ErrorReintentar(mensaje: String, onReintentar: () -> Unit, modifier: Modifier = Modifier) {
    val visible = remember { MutableTransitionState(false).apply { targetState = true } }
    AnimatedVisibility(
        visibleState = visible,
        enter = fadeIn(tween(220, easing = FastOutSlowInEasing)),
        exit = ExitTransition.None,
        modifier = modifier,
    ) {
        Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Box(
                Modifier.size(56.dp).background(MaterialTheme.colorScheme.errorContainer, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Outlined.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.onErrorContainer, modifier = Modifier.size(28.dp))
            }
            Spacer(Modifier.height(12.dp))
            Text("No se pudo cargar", style = MaterialTheme.typography.titleMedium, textAlign = TextAlign.Center)
            Spacer(Modifier.height(6.dp))
            Text(mensaje, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            Spacer(Modifier.height(14.dp))
            Button(onClick = onReintentar) {
                Icon(Icons.Filled.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text("Reintentar")
            }
        }
    }
}

private sealed interface FaseContenido {
    data object Cargando : FaseContenido
    data class Error(val mensaje: String) : FaseContenido
    data object Contenido : FaseContenido
}

/**
 * Cruza entre esqueleto, error y contenido con un fundido de 220 ms y el tamano animado (sin saltos).
 * El esqueleto va dentro de un `ProveedorEsqueleto` (un solo brillo) y se anuncia como "Cargando".
 * Usarlo con `modifier = Modifier.fillMaxSize()` y poner el scroll (LazyColumn o verticalScroll)
 * adentro de `contenido` y de `esqueleto`, no afuera.
 */
@Composable
fun ContenidoConEstado(
    cargando: Boolean,
    error: String?,
    onReintentar: () -> Unit,
    modifier: Modifier = Modifier,
    esqueleto: @Composable () -> Unit,
    contenido: @Composable () -> Unit,
) {
    val fase: FaseContenido = when {
        cargando -> FaseContenido.Cargando
        error != null -> FaseContenido.Error(error)
        else -> FaseContenido.Contenido
    }
    AnimatedContent(
        targetState = fase,
        modifier = modifier,
        contentKey = { it::class },
        transitionSpec = {
            val entra = fadeIn(tween(220, easing = FastOutSlowInEasing))
            val sale = fadeOut(tween(220, easing = FastOutSlowInEasing))
            (entra togetherWith sale).using(SizeTransform(clip = true) { _, _ -> tween(220, easing = FastOutSlowInEasing) })
        },
        contentAlignment = Alignment.TopStart,
        label = "contenidoConEstado",
    ) { f ->
        when (f) {
            FaseContenido.Cargando -> ProveedorEsqueleto {
                Box(Modifier.semantics(mergeDescendants = true) { contentDescription = "Cargando" }) { esqueleto() }
            }
            is FaseContenido.Error -> ErrorReintentar(f.mensaje, onReintentar)
            FaseContenido.Contenido -> contenido()
        }
    }
}
