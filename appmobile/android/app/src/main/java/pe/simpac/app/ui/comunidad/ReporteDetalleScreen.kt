package pe.simpac.app.ui.comunidad

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.MailOutline
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.data.ComentarioReporte
import pe.simpac.app.data.EstadoSesion
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.ReporteOrdenado
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.componentes.AparecerEscalonado
import pe.simpac.app.ui.componentes.ContenidoConEstado
import pe.simpac.app.ui.componentes.EsqueletoBloque
import pe.simpac.app.ui.componentes.EsqueletoLinea
import pe.simpac.app.ui.componentes.EstadoVacio
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.LocalAvisador
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.Transiciones

/**
 * Detalle de un reporte: tarjeta completa, votar con sesion, comentarios y caja de comentario con sesion.
 * Encabezado fijo; debajo, esqueleto (tarjeta con foto y tres comentarios) solo el primer cargado, error
 * con reintentar si no hay reporte, o la lista: tarjeta, comentarios (aparecen escalonados y se reacomodan
 * animados) y la caja. Al volver a la pantalla o al cambiar la sesion se recarga sin tapar lo que hay; si
 * esa recarga falla, se conserva el reporte y se avisa abajo con "Reintentar".
 */
@Composable
fun ReporteDetalleScreen(id: String, volver: () -> Unit, irCuenta: () -> Unit, verEnMapa: (Double, Double) -> Unit, vm: ReporteDetalleViewModel = viewModel(key = "reporte:$id")) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val sesion by estadoSesion()
    val avisador = LocalAvisador.current
    val vista = LocalView.current
    LaunchedEffect(id, sesion is EstadoSesion.ConSesion) { if (sesion !is EstadoSesion.Cargando) vm.cargar(id) }
    // Una recarga fallida con el reporte ya en pantalla se avisa abajo (sin reporte, la pantalla muestra el error)
    LaunchedEffect(estado.errorRecarga) {
        val e = estado.errorRecarga ?: return@LaunchedEffect
        vm.limpiarErrorRecarga()
        avisador.avisar("No se pudo actualizar el reporte ($e).", accion = "Reintentar") { vm.cargar(id) }
    }
    LaunchedEffect(estado.aviso) {
        val aviso = estado.aviso ?: return@LaunchedEffect
        Haptica.rechazar(vista)
        if (estado.pideCuenta) avisador.avisar(aviso, accion = "Entrar", duracion = SnackbarDuration.Long) { irCuenta() }
        else avisador.avisar(aviso, duracion = SnackbarDuration.Long)
        vm.limpiarAviso()
    }
    // Solo los comentarios publicados desde ahora (al volver a esta pantalla no se repite el aviso)
    var comentadosVistos by rememberSaveable { mutableIntStateOf(estado.comentado) }
    LaunchedEffect(estado.comentado) {
        if (estado.comentado > comentadosVistos) {
            comentadosVistos = estado.comentado
            Haptica.confirmar(vista)
            avisador.avisar("Comentario publicado")
        }
    }
    var votoEnCurso by remember { mutableStateOf(false) }
    LaunchedEffect(estado.votando) {
        if (estado.votando) votoEnCurso = true
        else if (votoEnCurso) {
            votoEnCurso = false
            if (estado.aviso == null) Haptica.confirmar(vista)
        }
    }

    Column(Modifier.fillMaxSize()) {
        Row(Modifier.padding(start = 4.dp, end = 16.dp, top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { Haptica.toque(vista); volver() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver a Comunidad") }
            Text("Reporte", style = MaterialTheme.typography.headlineMedium)
        }
        ContenidoConEstado(
            cargando = estado.cargando && !estado.cargado,
            error = estado.error?.takeIf { !estado.cargado }?.let { "No se pudo cargar el reporte ($it)." },
            onReintentar = { vm.cargar(id) },
            modifier = Modifier.fillMaxWidth().weight(1f),
            esqueleto = { EsqueletoDetalle() },
        ) {
            val r = estado.reporte
            if (r == null) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    EstadoVacio(
                        icono = Icons.Outlined.Info,
                        titulo = "Este reporte ya venció o no existe",
                        texto = "Los reportes duran ${Comunidad.HORAS_VIGENCIA} horas. Vuelve a la lista para ver los vigentes.",
                        accionTexto = "Volver a Comunidad",
                        onAccion = { Haptica.toque(vista); volver() },
                    )
                    LineaFuente(Comunidad.AVISO_REPORTE)
                    PieReferencial()
                }
            } else {
                LazyColumn(
                    Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item(key = "tarjeta") {
                        AparecerEscalonado(0) {
                            TarjetaReporte(
                                ro = r, miVoto = estado.miVoto, detalle = true, votando = estado.votando,
                                onVotar = { v -> vm.votar(v) },
                                onVerMapa = r.reporte.lat?.let { lat -> r.reporte.lon?.let { lon -> { verEnMapa(lat, lon) } } },
                            )
                        }
                    }
                    item(key = "titulo-comentarios") {
                        AparecerEscalonado(1) { Text("Comentarios (${estado.comentarios.size})", style = MaterialTheme.typography.titleMedium) }
                    }
                    if (estado.comentarios.isEmpty()) {
                        item(key = "sin-comentarios") {
                            Box(Modifier.animateItem()) {
                                AparecerEscalonado(2) {
                                    EstadoVacio(
                                        icono = Icons.Outlined.MailOutline,
                                        titulo = "Todavía no hay comentarios",
                                        texto = "Si estuviste ahí, cuenta lo que viste. Con respeto y sin datos personales.",
                                    )
                                }
                            }
                        }
                    }
                    itemsIndexed(estado.comentarios, key = { _, c -> c.id }) { i, c ->
                        Box(Modifier.animateItem()) {
                            if (i + 2 < Transiciones.MAX_ESCALONADOS) AparecerEscalonado(i + 2) { TarjetaComentario(c) } else TarjetaComentario(c)
                        }
                    }
                    item(key = "caja") {
                        Box(Modifier.animateItem()) { CajaComentario(estado, r, sesion, vm, irCuenta) }
                    }
                    item(key = "pie") {
                        Column(Modifier.animateItem(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            LineaFuente(Comunidad.AVISO_REPORTE)
                            PieReferencial()
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TarjetaComentario(c: ComentarioReporte) {
    Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.shapes.medium).padding(12.dp)) {
        Text(c.texto, style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(4.dp))
        LineaFuente("Vecino · ${Tiempo.haceTexto(Tiempo.parsearMs(c.creado_en))}")
    }
}

/** Caja para comentar: con sesion y reporte vigente; si no, "Entra para comentar" o el aviso de vencido. */
@Composable
private fun CajaComentario(estado: EstadoDetalle, r: ReporteOrdenado, sesion: EstadoSesion, vm: ReporteDetalleViewModel, irCuenta: () -> Unit) {
    val vista = LocalView.current
    when {
        sesion is EstadoSesion.SinSesion -> EntraPara("comentar", irCuenta, compacto = true)
        !Comunidad.vigente(r.reporte) -> Text("Este reporte ya venció: no admite comentarios nuevos.", style = MaterialTheme.typography.bodyMedium)
        sesion is EstadoSesion.ConSesion -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = estado.texto, onValueChange = { vm.cambiarTexto(it) },
                label = { Text("Tu comentario (hasta ${Comunidad.MAX_COMENTARIO} letras)") },
                placeholder = { Text("Lo que viste, con respeto. Sin datos personales.") },
                minLines = 2, modifier = Modifier.fillMaxWidth(),
                enabled = !estado.enviando,
                supportingText = { ContadorLetras(estado.texto.trim().length, Comunidad.MAX_COMENTARIO) },
            )
            Button(onClick = { Haptica.toque(vista); vm.comentar() }, enabled = !estado.enviando) {
                AnimatedVisibility(visible = estado.enviando) {
                    Row {
                        CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp, color = LocalContentColor.current)
                        Spacer(Modifier.width(8.dp))
                    }
                }
                Text(if (estado.enviando) "Enviando..." else "Comentar")
            }
        }
    }
}

/** Silueta del detalle: la tarjeta grande con foto, el titulo de comentarios y tres comentarios. */
@Composable
private fun EsqueletoDetalle() {
    Column(
        Modifier.fillMaxSize().clipToBounds().padding(start = 16.dp, end = 16.dp, top = 4.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        EsqueletoTarjetaReporte(detalle = true)
        EsqueletoLinea(anchoFraccion = 0.4f, alto = 16.dp)
        repeat(3) { EsqueletoBloque(60.dp, forma = MaterialTheme.shapes.medium) }
    }
}
