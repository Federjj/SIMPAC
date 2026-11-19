package pe.simpac.app.ui.comunidad

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import pe.simpac.app.ui.componentes.Cargando
import pe.simpac.app.ui.componentes.ErrorReintentar
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.Seccion

/** Detalle de un reporte: tarjeta completa, votar con sesion, comentarios y caja de comentario con sesion. */
@Composable
fun ReporteDetalleScreen(id: String, volver: () -> Unit, irCuenta: () -> Unit, verEnMapa: (Double, Double) -> Unit, vm: ReporteDetalleViewModel = viewModel(key = "reporte:$id")) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val sesion by estadoSesion()
    LaunchedEffect(id, sesion is EstadoSesion.ConSesion) { if (sesion !is EstadoSesion.Cargando) vm.cargar(id) }
    LaunchedEffect(estado.aviso) { if (estado.aviso != null) { kotlinx.coroutines.delay(6_000); vm.limpiarAviso() } }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = volver) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver a Comunidad") }
            Text("Reporte", style = MaterialTheme.typography.headlineMedium)
        }
        val r = estado.reporte
        when {
            estado.cargando -> Cargando("Cargando el reporte...")
            estado.error != null -> ErrorReintentar("No se pudo cargar el reporte (${estado.error}).", onReintentar = { vm.cargar(id) })
            r == null -> {
                Text("Este reporte ya venció o no existe.", style = MaterialTheme.typography.titleMedium)
                Text("Los reportes duran ${Comunidad.HORAS_VIGENCIA} horas. Vuelve a la lista para ver los vigentes.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            else -> {
                AvisoAccion(estado.aviso)
                TarjetaReporte(
                    ro = r, miVoto = estado.miVoto, detalle = true,
                    onVotar = { v -> vm.votar(v) },
                    onVerMapa = r.reporte.lat?.let { lat -> r.reporte.lon?.let { lon -> { verEnMapa(lat, lon) } } },
                )
                Seccion("Comentarios (${estado.comentarios.size})") {
                    if (estado.comentarios.isEmpty()) Text("Nadie ha comentado todavía.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    estado.comentarios.forEach { c ->
                        Column(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                            Text(c.texto, style = MaterialTheme.typography.bodyMedium)
                            LineaFuente("Vecino · ${Tiempo.haceTexto(Tiempo.parsearMs(c.creado_en))}")
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    when {
                        sesion is EstadoSesion.SinSesion -> EntraPara("comentar", irCuenta, compacto = true)
                        !Comunidad.vigente(r.reporte) -> Text("Este reporte ya venció: no admite comentarios nuevos.", style = MaterialTheme.typography.bodyMedium)
                        sesion is EstadoSesion.ConSesion -> {
                            OutlinedTextField(
                                value = estado.texto, onValueChange = { vm.cambiarTexto(it) },
                                label = { Text("Tu comentario (hasta ${Comunidad.MAX_COMENTARIO} letras)") },
                                placeholder = { Text("Lo que viste, con respeto. Sin datos personales.") },
                                minLines = 2, modifier = Modifier.fillMaxWidth(),
                                supportingText = { Text("${estado.texto.trim().length}/${Comunidad.MAX_COMENTARIO}") },
                            )
                            Button(onClick = { vm.comentar() }, enabled = !estado.enviando) { Text(if (estado.enviando) "Enviando..." else "Comentar") }
                        }
                    }
                }
            }
        }
        LineaFuente(Comunidad.AVISO_REPORTE)
        PieReferencial()
        Spacer(Modifier.height(8.dp))
    }
}
