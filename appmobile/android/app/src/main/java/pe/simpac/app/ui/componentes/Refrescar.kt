package pe.simpac.app.ui.componentes

import androidx.compose.foundation.layout.BoxScope
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/**
 * Tirar hacia abajo para actualizar (PullToRefreshBox de Material 3). `contenido` debe poder hacer
 * scroll (LazyColumn o `verticalScroll`) para que el gesto llegue. `refrescando` es "estoy
 * recargando con datos ya en pantalla" (no el primer cargado, que va con esqueleto): por ejemplo
 * `estado.cargando && estado.tieneDatos`. Al soltar se llama `onRefrescar` una vez.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RefrescarAlTirar(
    refrescando: Boolean,
    onRefrescar: () -> Unit,
    modifier: Modifier = Modifier,
    contenido: @Composable BoxScope.() -> Unit,
) {
    PullToRefreshBox(
        isRefreshing = refrescando,
        onRefresh = onRefrescar,
        modifier = modifier,
        content = contenido,
    )
}
