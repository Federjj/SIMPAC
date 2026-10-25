package pe.simpac.app.ui.alertas

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.data.AlertaActual
import pe.simpac.app.dominio.Alertas
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.componentes.AvisoDato
import pe.simpac.app.ui.componentes.Cargando
import pe.simpac.app.ui.componentes.ErrorReintentar
import pe.simpac.app.ui.componentes.EtiquetaNivel
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.PieReferencial

@Composable
fun AlertasScreen(vm: AlertasViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    AlertasContenido(estado, onFiltrar = { vm.filtrar(it) }, onReintentar = { vm.cargar() })
}

@Composable
fun AlertasContenido(estado: EstadoAlertas, onFiltrar: (Boolean) -> Unit, onReintentar: () -> Unit) {
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Alertas", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.weight(1f))
            FilterChip(selected = estado.soloMiZona, onClick = { onFiltrar(true) }, label = { Text("Mi zona") })
            FilterChip(selected = !estado.soloMiZona, onClick = { onFiltrar(false) }, label = { Text("Todo el país") })
        }
        when {
            estado.cargando -> Cargando("Leyendo las alertas vigentes...")
            estado.error != null -> ErrorReintentar("No se pudieron leer las alertas (${estado.error}).", onReintentar)
            else -> LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (estado.deCache) item { AvisoDato("Sin conexión: se muestra lo último guardado, de las ${Tiempo.horaCorta(estado.obtenidoEn)}.", fuerte = true) }
                item {
                    val ambito = if (estado.soloMiZona) estado.departamento else "todo el país"
                    LineaFuente("${estado.oficiales.size} alertas y avisos oficiales en $ambito. Revisado ${Tiempo.horaCorta(estado.obtenidoEn)}.")
                }
                if (estado.oficiales.isEmpty()) {
                    item {
                        Text(
                            if (estado.soloMiZona) "No hay alertas ni avisos oficiales vigentes en ${estado.departamento}. Si SENAMHI o ANA publican uno, aparecerá aquí."
                            else "No hay alertas ni avisos oficiales vigentes en el país.",
                            style = MaterialTheme.typography.bodyLarge,
                        )
                        TextButton(onClick = onReintentar) { Text("Actualizar") }
                    }
                }
                items(estado.oficiales, key = { "${it.tipo}|${it.referencia}|${it.zona}|${it.ts}" }) { TarjetaAlerta(it) }
                if (estado.lluvia.isNotEmpty()) {
                    item {
                        Spacer(Modifier.height(6.dp))
                        Text("Lluvia medida (no es un aviso oficial)", style = MaterialTheme.typography.titleMedium)
                        LineaFuente("Una estación de SENAMHI midió más lluvia que su referencia. Es lo que midió esa estación, no un aviso de SENAMHI.")
                    }
                    items(estado.lluvia, key = { "lluvia|${it.referencia}|${it.ts}" }) { TarjetaAlerta(it) }
                }
                item { Spacer(Modifier.height(4.dp)); PieReferencial() }
            }
        }
    }
}

@Composable
fun TarjetaAlerta(a: AlertaActual) {
    val nivel = Alertas.nivelDe(a)
    val oficial = Alertas.esOficial(a)
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(if (oficial) 2.dp else 1.dp, if (oficial) Color(nivel.fondo) else MaterialTheme.colorScheme.outline),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                EtiquetaNivel(nivel)
                Text(if (oficial) Alertas.tipoTexto(a) else "No oficial", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(a.referencia ?: "", style = MaterialTheme.typography.titleMedium)
            if (!a.zona.isNullOrBlank()) Text(a.zona, style = MaterialTheme.typography.bodyMedium)
            if (!a.detalle.isNullOrBlank()) Text(a.detalle, style = MaterialTheme.typography.bodyMedium)
            LineaFuente("Fuente: ${Alertas.fuenteTexto(a)}. ${Tiempo.horaConHace(Tiempo.parsearMs(a.ts))}")
        }
    }
}
