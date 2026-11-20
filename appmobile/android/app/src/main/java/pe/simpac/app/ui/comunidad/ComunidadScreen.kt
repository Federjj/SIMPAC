package pe.simpac.app.ui.comunidad

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.outlined.ThumbUp
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.data.EstadoSesion
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.componentes.AparecerEscalonado
import pe.simpac.app.ui.componentes.AvisoDato
import pe.simpac.app.ui.componentes.ContenidoConEstado
import pe.simpac.app.ui.componentes.EsqueletoBloque
import pe.simpac.app.ui.componentes.EsqueletoLinea
import pe.simpac.app.ui.componentes.EstadoVacio
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.LocalAvisador
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.RefrescarAlTirar
import pe.simpac.app.ui.componentes.Transiciones

/**
 * Pestana Comunidad: reportes de vecinos vigentes (12 h), ordenados por confianza y cercania
 * (pages/Comunidad.jsx). Consultar no pide cuenta; reportar, votar y comentar si.
 * Encabezado fijo; debajo, esqueleto de tres tarjetas solo el primer cargado, error con reintentar
 * si no hay lista, o la lista (tirar para actualizar, aparicion escalonada la primera vez). Al volver
 * a la pestana o al cambiar la sesion se recarga en silencio sin tapar lo que hay; si esa recarga
 * falla, la lista se conserva y se avisa abajo con "Reintentar". "Reportar incidente" es un boton
 * flotante extendido que se encoge al bajar por la lista y sube cuando hay un aviso en pantalla.
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
    val avisador = LocalAvisador.current
    val vista = LocalView.current
    val lista = rememberLazyListState()

    LaunchedEffect(sesion) { if (sesion !is EstadoSesion.Cargando && !estado.cargando) vm.cargar(silenciosa = true) }
    // Una recarga fallida con la lista ya en pantalla se avisa abajo (sin lista, la pantalla muestra el error)
    LaunchedEffect(estado.errorRecarga) {
        val e = estado.errorRecarga ?: return@LaunchedEffect
        vm.limpiarErrorRecarga()
        avisador.avisar("No se pudieron actualizar los reportes ($e).", accion = "Reintentar") { vm.cargar() }
    }
    // El aviso de la ultima accion sale por el snackbar global; si pide cuenta, ofrece ir a Cuenta
    LaunchedEffect(estado.aviso) {
        val aviso = estado.aviso ?: return@LaunchedEffect
        Haptica.rechazar(vista)
        if (estado.pideCuenta) avisador.avisar(aviso, accion = "Entrar", duracion = SnackbarDuration.Long) { irCuenta() }
        else avisador.avisar(aviso, duracion = SnackbarDuration.Long)
        vm.limpiarAviso()
    }
    // Vibracion de confirmacion cuando un voto termina bien
    var votoEnCurso by remember { mutableStateOf(false) }
    LaunchedEffect(estado.votando) {
        if (estado.votando != null) votoEnCurso = true
        else if (votoEnCurso) {
            votoEnCurso = false
            if (estado.aviso == null) Haptica.confirmar(vista)
        }
    }

    val fabExtendido = !lista.lastScrolledForward
    val hayAviso = avisador.estado.currentSnackbarData != null
    val subidaFab by animateDpAsState(if (hayAviso) 64.dp else 0.dp, tween(200, easing = FastOutSlowInEasing), label = "subidaFab")

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize()) {
            Encabezado(
                onActualizar = { Haptica.toque(vista); vm.cargar() },
                actualizando = estado.cargando,
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp),
            )
            ContenidoConEstado(
                cargando = estado.cargando && !estado.cargados,
                error = estado.error?.takeIf { !estado.cargados }?.let { "No se pudieron cargar los reportes ($it)." },
                onReintentar = { vm.cargar() },
                modifier = Modifier.fillMaxWidth().weight(1f),
                esqueleto = { EsqueletoComunidad(conEntrar = sesion is EstadoSesion.SinSesion) },
            ) {
                RefrescarAlTirar(
                    refrescando = estado.cargando && estado.cargados,
                    onRefrescar = { vm.cargar() },
                    modifier = Modifier.fillMaxSize(),
                ) {
                    LazyColumn(
                        state = lista,
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 10.dp, bottom = 96.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        if (sesion is EstadoSesion.SinSesion) {
                            item(key = "entrar") {
                                Box(Modifier.animateItem()) { EntraPara("reportar, votar y comentar", irCuenta, compacto = true) }
                            }
                        }
                        item(key = "fuente") {
                            Column(Modifier.animateItem()) {
                                AnimatedVisibility(visible = estado.deCache, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
                                    AvisoDato(
                                        "Sin conexión: se muestra lo último guardado, de las ${Tiempo.horaCorta(estado.obtenidoEn)}.",
                                        fuerte = true,
                                        modifier = Modifier.padding(bottom = 10.dp),
                                    )
                                }
                                LineaFuente("Distancias desde ${estado.desde}. Primero los reportes con más apoyo de la comunidad y más cercanos. Leídos a las ${Tiempo.horaCorta(estado.obtenidoEn)}.")
                            }
                        }
                        if (estado.reportes.isEmpty()) {
                            item(key = "vacio") {
                                // Sin boton propio: el flotante "Reportar incidente" ya esta a la vista
                                EstadoVacio(
                                    icono = Icons.Outlined.ThumbUp,
                                    titulo = "No hay reportes vigentes ahora",
                                    texto = "Cada reporte dura ${Comunidad.HORAS_VIGENCIA} horas. Si ves algo en tu zona, repórtalo desde donde estás.",
                                    modifier = Modifier.animateItem(),
                                )
                            }
                        }
                        itemsIndexed(estado.reportes, key = { _, ro -> ro.reporte.id }) { i, ro ->
                            val tarjeta: @Composable () -> Unit = {
                                TarjetaReporte(
                                    ro = ro,
                                    miVoto = estado.misVotos[ro.reporte.id],
                                    votando = estado.votando == ro.reporte.id,
                                    onVotar = { v -> if (estado.votando == null) vm.votar(ro.reporte.id, v) },
                                    onAbrir = { abrirReporte(ro.reporte.id) },
                                    onVerMapa = ro.reporte.lat?.let { lat -> ro.reporte.lon?.let { lon -> { verEnMapa(lat, lon) } } },
                                )
                            }
                            Box(Modifier.animateItem()) {
                                if (i < Transiciones.MAX_ESCALONADOS) AparecerEscalonado(i) { tarjeta() } else tarjeta()
                            }
                        }
                        item(key = "pie") {
                            // El aviso de "reporte comunitario" solo acompana a reportes; sin lista basta el pie
                            Column(Modifier.animateItem(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                if (estado.reportes.isNotEmpty()) LineaFuente(Comunidad.AVISO_REPORTE)
                                PieReferencial()
                            }
                        }
                    }
                }
            }
        }
        ExtendedFloatingActionButton(
            text = { Text("Reportar incidente") },
            icon = { Icon(Icons.Filled.Add, contentDescription = if (fabExtendido) null else "Reportar incidente") },
            onClick = { Haptica.toque(vista); irNuevo() },
            expanded = fabExtendido,
            modifier = Modifier.align(Alignment.BottomEnd).padding(end = 16.dp, bottom = 16.dp + subidaFab),
        )
    }
}

/** Titulo, bajada y el boton "Actualizar la lista", que se apaga mientras una carga esta en curso. */
@Composable
private fun Encabezado(onActualizar: () -> Unit, actualizando: Boolean, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("Comunidad", style = MaterialTheme.typography.headlineMedium)
            LineaFuente("Reportes de vecinos, validados por la misma comunidad con sus votos. Duran ${Comunidad.HORAS_VIGENCIA} horas.")
        }
        IconButton(onClick = onActualizar, enabled = !actualizando) { Icon(Icons.Filled.Refresh, contentDescription = "Actualizar la lista") }
    }
}

/** Misma silueta que la lista: tarjeta "Entra para..." si no hay sesion, la linea de fuente y tres tarjetas de reporte. */
@Composable
private fun EsqueletoComunidad(conEntrar: Boolean) {
    Column(
        Modifier.fillMaxSize().clipToBounds().padding(start = 16.dp, end = 16.dp, top = 10.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (conEntrar) EsqueletoBloque(104.dp, forma = MaterialTheme.shapes.medium)
        EsqueletoLinea(anchoFraccion = 0.92f, alto = 12.dp)
        repeat(3) { EsqueletoTarjetaReporte() }
    }
}
