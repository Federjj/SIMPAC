package pe.simpac.app.ui.comunidad

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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.data.EstadoSesion
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.componentes.AvisoDato
import pe.simpac.app.ui.componentes.Cargando
import pe.simpac.app.ui.componentes.ErrorReintentar
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.PieReferencial

/**
 * Pestana Comunidad: reportes de vecinos vigentes (12 h), ordenados por confianza y cercania
 * (pages/Comunidad.jsx). Consultar no pide cuenta; reportar, votar y comentar si.
 */
@Composable
fun ComunidadScreen(
    irNuevo: () -> Unit,
    abrirReporte: (String) -> Unit,
    irCuenta: () -> Unit,
    verEnMapa: (Double, Double) -> Unit,
    vm: ComunidadViewModel = viewModel(),
) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val sesion by estadoSesion()
    LaunchedEffect(sesion) { if (sesion !is EstadoSesion.Cargando && !estado.cargando) vm.cargar() }
    LaunchedEffect(estado.aviso) { if (estado.aviso != null) { kotlinx.coroutines.delay(6_000); vm.limpiarAviso() } }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Comunidad", style = MaterialTheme.typography.headlineMedium)
                    LineaFuente("Reportes de vecinos, validados por la misma comunidad con sus votos. Duran ${Comunidad.HORAS_VIGENCIA} horas.")
                }
                IconButton(onClick = { vm.cargar() }) { Icon(Icons.Filled.Refresh, contentDescription = "Actualizar la lista") }
            }
        }
        item { Button(onClick = irNuevo, modifier = Modifier.fillMaxWidth()) { Text("Reportar incidente") } }
        if (sesion is EstadoSesion.SinSesion) {
            item { EntraPara("reportar, votar y comentar", irCuenta, compacto = true) }
        }
        item { AvisoAccion(estado.aviso) }
        when {
            estado.cargando -> item { Cargando("Cargando los reportes...") }
            estado.error != null -> item { ErrorReintentar("No se pudieron cargar los reportes (${estado.error}).", onReintentar = { vm.cargar() }) }
            else -> {
                item {
                    if (estado.deCache) AvisoDato("Sin conexión: se muestra lo último guardado, de las ${Tiempo.horaCorta(estado.obtenidoEn)}.", fuerte = true)
                    LineaFuente("Distancias desde ${estado.desde}. Primero los reportes con más apoyo de la comunidad y más cercanos. Leídos a las ${Tiempo.horaCorta(estado.obtenidoEn)}.")
                }
                if (estado.reportes.isEmpty()) {
                    item {
                        Column(Modifier.fillMaxWidth().padding(vertical = 24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("No hay reportes vigentes ahora.", style = MaterialTheme.typography.titleMedium)
                            Spacer(Modifier.height(6.dp))
                            Text("Cada reporte dura ${Comunidad.HORAS_VIGENCIA} horas. Si ves algo en tu zona, repórtalo desde donde estás.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                items(estado.reportes, key = { it.reporte.id }) { ro ->
                    TarjetaReporte(
                        ro = ro,
                        miVoto = estado.misVotos[ro.reporte.id],
                        onVotar = { v -> if (estado.votando == null) vm.votar(ro.reporte.id, v) },
                        onAbrir = { abrirReporte(ro.reporte.id) },
                        onVerMapa = ro.reporte.lat?.let { lat -> ro.reporte.lon?.let { lon -> { verEnMapa(lat, lon) } } },
                    )
                }
            }
        }
        item {
            LineaFuente(Comunidad.AVISO_REPORTE)
            PieReferencial()
            Spacer(Modifier.height(8.dp))
        }
    }
}
