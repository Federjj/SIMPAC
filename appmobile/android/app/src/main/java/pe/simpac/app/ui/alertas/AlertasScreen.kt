package pe.simpac.app.ui.alertas

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyItemScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Place
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.data.AlertaActual
import pe.simpac.app.dominio.Alertas
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.componentes.AparecerEscalonado
import pe.simpac.app.ui.componentes.AvisoDato
import pe.simpac.app.ui.componentes.ContenidoConEstado
import pe.simpac.app.ui.componentes.EsqueletoBloque
import pe.simpac.app.ui.componentes.EsqueletoLinea
import pe.simpac.app.ui.componentes.EstadoVacio
import pe.simpac.app.ui.componentes.EtiquetaNivel
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.LocalAvisador
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.RefrescarAlTirar
import pe.simpac.app.ui.componentes.Transiciones
import pe.simpac.app.ui.componentes.bordeTarjeta

@Composable
fun AlertasScreen(vm: AlertasViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val avisador = LocalAvisador.current
    // una recarga fallida con la lista ya en pantalla se avisa abajo; sin lista, la pantalla muestra el error
    LaunchedEffect(estado.error, estado.cargadas) {
        val e = estado.error
        if (e != null && estado.cargadas) avisador.avisar("No se pudieron actualizar las alertas ($e).", accion = "Reintentar") { vm.cargar() }
    }
    AlertasContenido(estado, onFiltrar = { vm.filtrar(it) }, onReintentar = { vm.cargar() })
}

/**
 * Alertas sin estado propio: esqueleto de lista en el primer cargado, "tirar para actualizar" con
 * datos, cruce con fundido entre "Mi zona" y "Todo el pais", filas con clave y movimiento, estado
 * vacio con la linea "Revisado ..." siempre visible y error con "Reintentar".
 */
@Composable
fun AlertasContenido(estado: EstadoAlertas, onFiltrar: (Boolean) -> Unit, onReintentar: () -> Unit) {
    val vista = LocalView.current
    // las primeras tarjetas entran escalonadas solo con el filtro inicial y la primera vez; al cambiar de
    // filtro la lista nueva ya cruza con fundido, asi que no se vuelve a escalonar
    val filtroInicial = rememberSaveable { estado.soloMiZona }
    var escalonar by rememberSaveable { mutableStateOf(true) }
    LaunchedEffect(estado.soloMiZona) { if (estado.soloMiZona != filtroInicial) escalonar = false }
    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Alertas", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.weight(1f))
            FilterChip(selected = estado.soloMiZona, onClick = { Haptica.toque(vista); onFiltrar(true) }, label = { Text("Mi zona") })
            FilterChip(selected = !estado.soloMiZona, onClick = { Haptica.toque(vista); onFiltrar(false) }, label = { Text("Todo el país") })
        }
        ContenidoConEstado(
            cargando = estado.cargando && !estado.cargadas,
            error = estado.error?.takeIf { !estado.cargadas }?.let { "No se pudieron leer las alertas ($it)." },
            onReintentar = onReintentar,
            modifier = Modifier.fillMaxSize(),
            esqueleto = { EsqueletoAlertas() },
        ) {
            RefrescarAlTirar(refrescando = estado.cargando && estado.cargadas, onRefrescar = onReintentar, modifier = Modifier.fillMaxSize()) {
                AnimatedContent(
                    targetState = estado.soloMiZona,
                    modifier = Modifier.fillMaxSize(),
                    transitionSpec = {
                        fadeIn(tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing)) togetherWith
                            fadeOut(tween(150, easing = FastOutSlowInEasing))
                    },
                    label = "filtroAlertas",
                ) { miZona ->
                    ListaAlertas(estado, miZona, escalonar = escalonar && miZona == filtroInicial, onReintentar = onReintentar)
                }
            }
        }
    }
}

/** Movimiento de cada fila de la lista: fundido al entrar o salir y desplazamiento al reordenarse. */
private fun LazyItemScope.filaAnimada(): Modifier = Modifier.animateItem(
    fadeInSpec = tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing),
    placementSpec = tween<IntOffset>(Transiciones.APARECER_MS, easing = FastOutSlowInEasing),
    fadeOutSpec = tween(150, easing = FastOutSlowInEasing),
)

private fun claveAlerta(a: AlertaActual): String = "${a.tipo}|${a.referencia}|${a.zona}|${a.ts}"

/** La lista para un filtro dado (se le pasa el filtro y no se lee del estado, para que la lista que se va no cambie durante el cruce). */
@Composable
private fun ListaAlertas(estado: EstadoAlertas, miZona: Boolean, escalonar: Boolean, onReintentar: () -> Unit) {
    val (oficiales, lluvia) = remember(estado.todas, estado.departamento, miZona) {
        estado.visiblesCon(miZona).partition { Alertas.esOficial(it) }
    }
    val ambito = if (miZona) estado.departamento else "todo el país"
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (estado.deCache) {
            item(key = "cache") { AvisoDato("Sin conexión: se muestra lo último guardado, de las ${Tiempo.horaCorta(estado.obtenidoEn)}.", filaAnimada(), fuerte = true) }
        }
        item(key = "resumen") {
            LineaFuente("${oficiales.size} alertas y avisos oficiales en $ambito. Revisado ${Tiempo.horaCorta(estado.obtenidoEn)}.", filaAnimada())
        }
        if (oficiales.isEmpty()) {
            item(key = "vacio") {
                EstadoVacio(
                    icono = Icons.Outlined.Notifications,
                    titulo = if (miZona) "Sin alertas oficiales en tu zona" else "Sin alertas oficiales en el país",
                    texto = if (miZona) "No hay alertas ni avisos oficiales vigentes en ${estado.departamento}. Si SENAMHI o ANA publican uno, aparecerá aquí."
                    else "No hay alertas ni avisos oficiales vigentes en el país.",
                    modifier = filaAnimada(),
                    accionTexto = "Actualizar",
                    onAccion = onReintentar,
                )
            }
        }
        itemsIndexed(oficiales, key = { _, a -> claveAlerta(a) }) { i, a ->
            if (escalonar && i < Transiciones.MAX_ESCALONADOS) {
                AparecerEscalonado(i, filaAnimada()) { TarjetaAlerta(a) }
            } else {
                TarjetaAlerta(a, filaAnimada())
            }
        }
        if (lluvia.isNotEmpty()) {
            item(key = "lluvia") {
                Column(filaAnimada()) {
                    Spacer(Modifier.height(6.dp))
                    Text("Lluvia medida (no es un aviso oficial)", style = MaterialTheme.typography.titleMedium)
                    LineaFuente("Una estación de SENAMHI midió más lluvia que su referencia. Es lo que midió esa estación, no un aviso de SENAMHI.")
                }
            }
            items(lluvia, key = { "lluvia|${it.referencia}|${it.ts}" }) { TarjetaAlerta(it, filaAnimada()) }
        }
        item(key = "pie") {
            Column(filaAnimada()) {
                Spacer(Modifier.height(4.dp))
                PieReferencial()
            }
        }
    }
}

/**
 * Tarjeta de una alerta: etiqueta del nivel y tipo arriba, titulo (referencia), zona con icono,
 * detalle y la linea de fuente con la hora. Borde del color del nivel si es oficial (siempre con la
 * etiqueta en texto); las no oficiales llevan el borde fino comun.
 */
@Composable
fun TarjetaAlerta(a: AlertaActual, modifier: Modifier = Modifier) {
    val nivel = Alertas.nivelDe(a)
    val oficial = Alertas.esOficial(a)
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = if (oficial) BorderStroke(2.dp, Color(nivel.fondo)) else bordeTarjeta(),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                EtiquetaNivel(nivel)
                Text(if (oficial) Alertas.tipoTexto(a) else "No oficial", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(a.referencia ?: "", style = MaterialTheme.typography.titleMedium)
            if (!a.zona.isNullOrBlank()) {
                Row(verticalAlignment = Alignment.Top) {
                    Icon(
                        Icons.Outlined.Place,
                        contentDescription = "Zona",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 2.dp).size(16.dp),
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(a.zona, style = MaterialTheme.typography.bodyMedium)
                }
            }
            if (!a.detalle.isNullOrBlank()) Text(a.detalle, style = MaterialTheme.typography.bodyMedium)
            LineaFuente("Fuente: ${Alertas.fuenteTexto(a)}. ${Tiempo.horaConHace(Tiempo.parsearMs(a.ts))}")
        }
    }
}

/* ---------- Esqueleto: la linea de resumen y cuatro tarjetas con la silueta de TarjetaAlerta ---------- */

@Composable
private fun EsqueletoAlertas() {
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        EsqueletoLinea(anchoFraccion = 0.8f, alto = 12.dp)
        repeat(4) { EsqueletoTarjetaAlerta() }
    }
}

@Composable
private fun EsqueletoTarjetaAlerta() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = bordeTarjeta(),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                EsqueletoBloque(22.dp, Modifier.width(84.dp), RoundedCornerShape(999.dp))
                EsqueletoLinea(alto = 10.dp, modifier = Modifier.width(72.dp))
            }
            EsqueletoLinea(anchoFraccion = 0.75f, alto = 16.dp)
            EsqueletoLinea(anchoFraccion = 0.5f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 1f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 0.9f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 0.6f, alto = 10.dp)
        }
    }
}
