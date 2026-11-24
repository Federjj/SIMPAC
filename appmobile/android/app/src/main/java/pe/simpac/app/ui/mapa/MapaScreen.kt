package pe.simpac.app.ui.mapa

import android.content.ActivityNotFoundException
import android.content.Intent
import android.provider.Settings
import android.view.ViewGroup
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.materialIcon
import androidx.compose.material.icons.materialPath
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import pe.simpac.app.dominio.DiaMapa
import pe.simpac.app.dominio.Lluvia
import pe.simpac.app.ubicacion.Lectura
import pe.simpac.app.ubicacion.MotivoSinPosicion
import pe.simpac.app.ubicacion.Posicion
import pe.simpac.app.ubicacion.Ubicacion
import pe.simpac.app.ui.EstadoCompartido
import pe.simpac.app.ui.componentes.AparecerEscalonado
import pe.simpac.app.ui.componentes.ErrorReintentar
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LocalAvisador
import pe.simpac.app.ui.componentes.bordeTarjeta
import pe.simpac.app.ui.componentes.presionable
import pe.simpac.app.ui.componentes.temaOscuro

/**
 * Pestana Mapa: mapa nativo (osmdroid) con las capas de SIMPAC. Arriba, el selector de dia (Hoy /
 * Manana / Pasado, que mueve avisos y pronostico) y el chip con el nivel de tu zona; abajo la barra de
 * capas; al tocar algo, una hoja inferior de Material 3 en lenguaje claro. Solo existe la barra
 * inferior de la app: nada de barras duplicadas.
 *
 * Movimiento: una barra fina de progreso bajo el selector mientras el mapa o alguna capa pide datos
 * (solo si la espera pasa de 300 ms, para que un cambio rapido no parpadee); mientras llega el nivel de
 * tu zona, un chip "Leyendo tu zona..." con rueda; los chips flotantes entran y salen con fundido y un
 * deslizamiento corto; la camara vuela (500 ms) al centrar o encuadrar; el selector y la barra de capas
 * aparecen escalonados solo la primera vez. Los botones de zoom son de Material 3 (arriba a la
 * izquierda, misma superficie que el boton de ubicacion); los de osmdroid van apagados en GestorMapa.
 * Nada de esto recompone ni recrea el MapView (que vive en un `remember`).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MapaScreen(compartido: EstadoCompartido, vm: MapaViewModel = viewModel()) {
    val contexto = LocalContext.current
    val vista = LocalView.current
    val avisador = LocalAvisador.current
    val estado by vm.estado.collectAsStateWithLifecycle()
    val encuadre by compartido.encuadre.collectAsStateWithLifecycle()
    val ambito = rememberCoroutineScope()
    val ciclo = LocalLifecycleOwner.current
    var seleccion by remember { mutableStateOf<Seleccion?>(null) }
    var hojaCapas by remember { mutableStateOf(false) }
    // centro ya aplicado: se vuelve a centrar solo si el ViewModel manda otro (cambio de ciudad o de ubicacion)
    var centradoEn by remember { mutableStateOf<Posicion?>(null) }
    // boton "Centrar en tu ubicacion": la espera en curso (para cortarla al irse la app al fondo) y si se esta buscando
    val trabajoUbicacion = remember { mutableStateOf<Job?>(null) }
    var buscandoUbicacion by remember { mutableStateOf(false) }

    val gestor = remember {
        OsmdroidSimpac.preparar(contexto)
        val mapa = MapView(contexto).apply {
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        }
        GestorMapa(
            mapa,
            alTocar = { sel ->
                // un pin de reporte abre el detalle de Comunidad si la app lo ofrece; si no, la hoja del mapa
                val abrir = compartido.abrirReporte
                if (sel is Seleccion.Reporte && abrir != null) abrir(sel.reporte.id) else seleccion = sel
            },
            alCambiarVista = { caja, zoom -> vm.vistaCambio(caja, zoom) },
        )
    }

    // onResume/onPause siguen al ciclo de vida de la pestana. El LifecycleOwner puede cambiar sin que
    // la pantalla salga de la composicion (la entrada de navegacion se reemplaza al volver a tocar la
    // pestana); por eso este efecto solo registra el observador y NO desarma el mapa.
    DisposableEffect(ciclo) {
        val observador = LifecycleEventObserver { _, evento ->
            when (evento) {
                Lifecycle.Event.ON_RESUME -> gestor.mapa.onResume()
                Lifecycle.Event.ON_PAUSE -> gestor.mapa.onPause()
                // ubicacion solo en primer plano: al irse la app al fondo se corta la espera del boton "centrar"
                Lifecycle.Event.ON_STOP -> trabajoUbicacion.value?.cancel()
                else -> {}
            }
        }
        ciclo.lifecycle.addObserver(observador)
        onDispose { ciclo.lifecycle.removeObserver(observador) }
    }
    // onDetach libera tiles y capas y deja el MapView inservible: solo al salir de verdad de la pestana
    DisposableEffect(Unit) {
        onDispose { gestor.soltar() }
    }

    // centro inicial: tu ubicacion o la ciudad elegida, zoom 13 (una vez por centro distinto). La primera
    // vez el mapa aparece ya centrado (sin vuelo desde el borde); si despues cambia la ciudad o la
    // ubicacion, la camara vuela hasta el centro nuevo.
    LaunchedEffect(estado.centro) {
        val c = estado.centro ?: return@LaunchedEffect
        if (c != centradoEn) {
            if (centradoEn == null) {
                gestor.mapa.controller.setZoom(estado.zoomInicial)
                gestor.mapa.controller.setCenter(GeoPoint(c.lat, c.lon))
            } else {
                gestor.volar(c, estado.zoomInicial)
            }
            centradoEn = c
            gestor.mapa.post { gestor.revisarVista() }
        }
    }
    LaunchedEffect(estado.capas) { gestor.capasVisibles(estado.capas) }
    LaunchedEffect(estado.avisos) { gestor.mostrarAvisos(estado.avisos) }
    LaunchedEffect(estado.rios, estado.mashcon) { gestor.mostrarRios(estado.rios, estado.mashcon) }
    LaunchedEffect(estado.cauceFino) { gestor.mostrarFinos(estado.cauceFino) }
    LaunchedEffect(estado.estacionesRio) { gestor.mostrarEstacionesRio(estado.estacionesRio) }
    LaunchedEffect(estado.zonas) { gestor.mostrarZonas(estado.zonas) }
    LaunchedEffect(estado.franjas) { gestor.mostrarFranjas(estado.franjas) }
    LaunchedEffect(estado.estaciones) { gestor.mostrarEstaciones(estado.estaciones) }
    LaunchedEffect(estado.acudir) { gestor.mostrarAcudir(estado.acudir) }
    LaunchedEffect(estado.ubicacion) { gestor.mostrarUbicacion(estado.ubicacion) }
    // capas nuevas: el pronostico sigue al dia elegido; el nowcasting solo se ve con "Hoy"
    LaunchedEffect(estado.pronostico, estado.dia, estado.localidadTuya) {
        gestor.mostrarPronostico(estado.pronostico, estado.dia.fechaIso(), estado.localidadTuya)
    }
    LaunchedEffect(estado.dia) { gestor.nowcastSoloHoy(estado.dia == DiaMapa.HOY) }
    LaunchedEffect(estado.nowcast) { gestor.mostrarNowcast(estado.nowcast) }
    LaunchedEffect(estado.lluviaAhora) { gestor.mostrarLluviaAhora(estado.lluviaAhora) }
    LaunchedEffect(estado.capas, estado.lluviaObsOpcion, estado.lluviaObsDia) {
        val c = if (Capa.LLUVIA_OBSERVADA in estado.capas) Lluvia.observada(estado.lluviaObsOpcion) else null
        // el dia procesado es la clave de la cache de imagenes: un dia nuevo, imagenes nuevas
        gestor.mostrarLluviaObservada(c, estado.lluviaObsDia)
    }
    LaunchedEffect(estado.capas, estado.sateliteHora, estado.errores[Capa.SATELITE]) {
        val con = Capa.SATELITE in estado.capas && estado.errores[Capa.SATELITE] == null
        gestor.mostrarSatelite(if (con) estado.sateliteHora ?: "default" else null)
    }
    LaunchedEffect(estado.fen, estado.capas.contains(Capa.FEN)) { gestor.mostrarFen(if (Capa.FEN in estado.capas) estado.fen else null) }
    LaunchedEffect(estado.incidentes, estado.riosVigiladosNombres) { gestor.mostrarIncidentes(estado.incidentes, estado.riosVigiladosNombres) }
    LaunchedEffect(estado.reportes) { gestor.mostrarReportes(estado.reportes) }

    // "Ver el rio en el mapa" desde Inicio: encuadra tu punto y el cauce cuando los rios ya cargaron
    // (zoomToBoundingBox y centrar son vuelos animados, nunca un salto seco)
    LaunchedEffect(encuadre, estado.cargando) {
        val e = encuadre ?: return@LaunchedEffect
        if (estado.cargando) return@LaunchedEffect
        val caja = vm.cajaParaEncuadre(e.rioAna, e.lat, e.lon)
        if (caja != null) gestor.encuadrar(caja)
        else if (e.lat != null && e.lon != null) gestor.centrar(Posicion(e.lat, e.lon), 13.0)
        centradoEn = estado.centro   // el encuadre manda sobre el centro inicial
        compartido.encuadreAtendido()
    }

    // la barra fina solo si la carga pasa de 300 ms: un pedido corto (cambio de dia o de capa con los
    // datos ya en cache) no la hace parpadear; al terminar se va enseguida
    var barraVisible by remember { mutableStateOf(false) }
    LaunchedEffect(estado.cargandoAlgo) {
        if (estado.cargandoAlgo) {
            delay(300)
            barraVisible = true
        } else {
            barraVisible = false
        }
    }

    Column(Modifier.fillMaxSize()) {
        // selector de dia: mueve a la vez los avisos de SENAMHI (por su fecha) y el pronostico por localidad
        AparecerEscalonado(0) {
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface).padding(horizontal = 12.dp, vertical = 4.dp)) {
                DiaMapa.entries.forEachIndexed { i, dia ->
                    SegmentedButton(
                        selected = estado.dia == dia,
                        onClick = { if (estado.dia != dia) { Haptica.toque(vista); vm.elegirDia(dia) } },
                        shape = SegmentedButtonDefaults.itemShape(index = i, count = DiaMapa.entries.size),
                        label = { Text(dia.etiqueta, maxLines = 1) },
                    )
                }
            }
        }
        // clipToBounds: osmdroid pinta en todo el canvas y, sin recorte, se encimaba al selector de dia
        Box(Modifier.weight(1f).fillMaxWidth().clipToBounds()) {
            AndroidView(modifier = Modifier.fillMaxSize().clipToBounds(), factory = { gestor.mapa })

            // barra fina bajo el selector: mientras el mapa o alguna capa pide datos (va encima del mapa,
            // no en la columna, para no cambiar el tamano del MapView al aparecer). Nombre completo
            // porque dentro del Box la version de ColumnScope de afuera gana y el DslMarker la prohibe.
            androidx.compose.animation.AnimatedVisibility(
                visible = barraVisible,
                enter = fadeIn(tween(200, easing = FastOutSlowInEasing)),
                exit = fadeOut(tween(300, easing = FastOutSlowInEasing)),
                modifier = Modifier.align(Alignment.TopCenter),
            ) {
                LinearProgressIndicator(Modifier.fillMaxWidth().height(3.dp).semantics { contentDescription = "Cargando capas del mapa" })
            }

            // chips flotantes: a la derecha de los botones de zoom (start 64 dp) para no cruzarlos;
            // los anchos (avisos) se parten en dos lineas dentro de ese espacio
            Column(
                Modifier.align(Alignment.TopCenter).fillMaxWidth().padding(start = 64.dp, end = 16.dp, top = 12.dp),
                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                // chip con el nivel de tu zona (texto + color); mientras llega, un chip con rueda que dice
                // que se esta leyendo (una silueta gris sobre el mapa claro parecia un texto que faltaba)
                AnimatedVisibility(visible = estado.chip == null && estado.cargando, enter = entrarChip, exit = salirChip) {
                    ChipCarga("Leyendo tu zona...")
                }
                val chip = recordarUltimo(estado.chip)
                AnimatedVisibility(visible = estado.chip != null, enter = entrarChip, exit = salirChip) {
                    if (chip != null) {
                        Text(
                            chip.texto,
                            Modifier.background(Color(chip.nivel.fondo), RoundedCornerShape(999.dp)).padding(horizontal = 14.dp, vertical = 7.dp)
                                .semantics { contentDescription = "Nivel de tu zona: ${chip.texto}" },
                            color = Color(chip.nivel.textoSobreFondo), fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
                AnimatedVisibility(visible = estado.deCache, enter = entrarChip, exit = salirChip) {
                    ChipAviso("Sin conexión: se muestra lo último guardado")
                }
                // chip del nowcasting: que se ve (o por que no se ve nada)
                val textoNowcast = recordarUltimo(estado.chipNowcast)
                AnimatedVisibility(visible = estado.chipNowcast != null, enter = entrarChip, exit = salirChip) {
                    ChipInfo(textoNowcast ?: "")
                }
                AnimatedVisibility(visible = Capa.LLUVIA_OBSERVADA in estado.capas && estado.lluviaObsSinServidor, enter = entrarChip, exit = salirChip) {
                    ChipAviso(Lluvia.SIN_SERVIDOR)
                }
                // capas pesadas: un chip discreto mientras llegan, que se va solo
                val textoCarga = when {
                    estado.fenCargando -> "Cargando El Niño..."
                    Capa.LLUVIA_OBSERVADA in estado.cargandoCapas -> "Cargando la lluvia de SENAMHI..."
                    else -> null
                }
                val ultimoTextoCarga = recordarUltimo(textoCarga)
                AnimatedVisibility(visible = textoCarga != null, enter = entrarChip, exit = salirChip) {
                    ChipCarga(ultimoTextoCarga ?: "")
                }
            }

            // zoom + y - de Material 3, uno sobre otro arriba a la izquierda (los de osmdroid van apagados):
            // zoomIn/zoomOut animan el acercamiento (250 ms) sin tocar la composicion
            Column(Modifier.align(Alignment.TopStart).padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                BotonZoom(Icons.Filled.Add, "Acercar el mapa") { Haptica.toque(vista); gestor.mapa.controller.zoomIn() }
                BotonZoom(IconoQuitar, "Alejar el mapa") { Haptica.toque(vista); gestor.mapa.controller.zoomOut() }
            }

            estado.error?.let { mensaje ->
                Box(
                    Modifier.align(Alignment.Center).padding(24.dp)
                        .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.96f), MaterialTheme.shapes.large)
                        .border(bordeTarjeta(), MaterialTheme.shapes.large),
                ) {
                    ErrorReintentar(mensaje, onReintentar = { vm.cargar() })
                }
            }

            // Boton "Centrar en tu ubicacion": lectura activa de hasta 20 s con progreso en el propio boton (no se
            // puede tocar dos veces) y un mensaje exacto por causa. Sin permiso se pide aqui mismo y al concederlo
            // se centra; con la ubicacion del telefono apagada, aviso con "Activar" (ajustes del sistema); sin
            // senal, aviso con "Reintentar". El permiso no depende de "Usar mi ubicacion" de Inicio (eso solo
            // decide el departamento). Solo en primer plano: ON_STOP cancela la espera.
            val alConcederPermiso = remember { arrayOfNulls<() -> Unit>(1) }
            val pedirPermiso = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { r ->
                if (r.values.any { it }) {
                    alConcederPermiso[0]?.invoke()
                } else {
                    Haptica.rechazar(vista)
                    avisador.avisar("Sin permiso de ubicación no se puede centrar el mapa en ti", duracion = SnackbarDuration.Long)
                }
            }
            fun abrirAjustesUbicacion() {
                try {
                    contexto.startActivity(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS))
                } catch (_: ActivityNotFoundException) {
                    avisador.avisar("No se pudieron abrir los ajustes de ubicación del teléfono")
                }
            }
            fun centrarEnMi() {
                if (buscandoUbicacion) return
                trabajoUbicacion.value = ambito.launch {
                    buscandoUbicacion = true
                    try {
                        when (val lectura = vm.ubicacionAhora()) {
                            is Lectura.Hecha -> {
                                val p = lectura.posicion
                                if (!Ubicacion.enPeru(p)) {
                                    // el mapa solo cubre el Perú: fuera de esa caja el mapa se iria al borde (mar) sin nada que ver
                                    Haptica.rechazar(vista)
                                    avisador.avisar("Tu ubicación está fuera del Perú: el mapa de SIMPAC solo cubre el país", duracion = SnackbarDuration.Long)
                                } else {
                                    // con una posicion precisa (100 m o menos) se acerca a zoom 15 para ver la cuadra; si no, 13
                                    val precisa = (p.precisionM ?: Float.MAX_VALUE) <= 100f
                                    gestor.centrar(p, maxOf(gestor.mapa.zoomLevelDouble, if (precisa) 15.0 else 13.0))
                                    val precision = p.textoPrecision()
                                    if (precision != null && (p.precisionM ?: 0f) > 500f) avisador.avisar("Posición aproximada: precisión de $precision")
                                }
                            }
                            is Lectura.Fallida -> when (lectura.motivo) {
                                MotivoSinPosicion.SIN_PERMISO -> pedirPermiso.launch(Ubicacion.PERMISOS)
                                MotivoSinPosicion.UBICACION_APAGADA -> {
                                    Haptica.rechazar(vista)
                                    avisador.avisar(
                                        "La ubicación del teléfono está apagada. Actívala para centrar el mapa en ti",
                                        accion = "Activar", duracion = SnackbarDuration.Long, onAccion = { abrirAjustesUbicacion() },
                                    )
                                }
                                MotivoSinPosicion.SIN_SENAL -> {
                                    Haptica.rechazar(vista)
                                    avisador.avisar(
                                        "No se pudo obtener tu posición; prueba a cielo abierto",
                                        accion = "Reintentar", duracion = SnackbarDuration.Long, onAccion = { centrarEnMi() },
                                    )
                                }
                            }
                        }
                    } finally {
                        buscandoUbicacion = false
                    }
                }
            }
            alConcederPermiso[0] = { centrarEnMi() }

            val fuenteUbicacion = remember { MutableInteractionSource() }
            SmallFloatingActionButton(
                onClick = { if (!buscandoUbicacion) { Haptica.toque(vista); centrarEnMi() } },
                interactionSource = fuenteUbicacion,
                modifier = Modifier.align(Alignment.BottomEnd).padding(end = 12.dp, bottom = 30.dp).presionable(fuenteUbicacion, escala = 0.92f),
            ) {
                if (buscandoUbicacion) {
                    CircularProgressIndicator(
                        Modifier.size(20.dp).semantics { contentDescription = "Buscando tu ubicación" },
                        strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                } else {
                    Icon(Icons.Filled.LocationOn, contentDescription = "Centrar en tu ubicación")
                }
            }

            // atribucion visible abajo: una sola linea, chica y legible, como la atribucion corta del celular en la web
            val extra = remember(estado.capas) {
                listOfNotNull(
                    if (Capa.SATELITE in estado.capas) "NASA GIBS" else null,
                    if (Capa.LLUVIA_OBSERVADA in estado.capas || Capa.LLUVIA_AHORA in estado.capas || Capa.NOWCAST in estado.capas) "SENAMHI (IDESEP)" else null,
                )
            }
            Text(
                OsmdroidSimpac.atribucion + extra.joinToString("") { ", $it" },
                Modifier.align(Alignment.BottomStart).fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.85f))
                    .padding(horizontal = 8.dp, vertical = 2.dp),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
        }

        // barra de capas (abajo del mapa, encima de la barra de la app)
        AparecerEscalonado(1) {
            Row(
                Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface).horizontalScroll(rememberScrollState()).padding(horizontal = 8.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically,
            ) {
                val fuenteCapas = remember { MutableInteractionSource() }
                TextButton(onClick = { Haptica.toque(vista); hojaCapas = true }, interactionSource = fuenteCapas, modifier = Modifier.presionable(fuenteCapas)) {
                    Icon(Icons.AutoMirrored.Filled.List, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Capas", style = MaterialTheme.typography.labelLarge)
                }
                Capa.entries.forEach { capa ->
                    val prendida = capa in estado.capas
                    FilterChip(
                        selected = prendida,
                        onClick = { Haptica.toque(vista); vm.alternarCapa(capa) },
                        label = { Text(capa.corta) },
                        // la marca dice "prendida" ademas del color
                        leadingIcon = if (prendida) ({ Icon(Icons.Filled.Check, contentDescription = null, modifier = Modifier.size(FilterChipDefaults.IconSize)) }) else null,
                    )
                }
            }
        }
    }

    val formaHoja = remember { RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp) }
    seleccion?.let { sel ->
        ModalBottomSheet(onDismissRequest = { seleccion = null }, shape = formaHoja) { HojaSeleccion(sel, estado) }
    }
    if (hojaCapas) {
        ModalBottomSheet(onDismissRequest = { hojaCapas = false }, shape = formaHoja) {
            HojaCapas(
                estado,
                AccionesCapas(
                    alternar = { vm.alternarCapa(it) },
                    elegirHorizonte = { vm.elegirHorizonteNowcast(it) },
                    elegirLluviaObservada = { vm.elegirLluviaObservada(it) },
                    elegirFen = { vm.elegirFen(it) },
                    restablecer = { vm.restablecerCapas() },
                ),
            )
        }
    }
}

/** Entrada y salida de los chips flotantes sobre el mapa: fundido + deslizamiento vertical corto. */
private val entrarChip: EnterTransition =
    fadeIn(tween(200, easing = FastOutSlowInEasing)) +
        slideInVertically(tween(200, easing = FastOutSlowInEasing)) { -it / 2 } +
        expandVertically(tween(200, easing = FastOutSlowInEasing))
private val salirChip: ExitTransition =
    fadeOut(tween(160, easing = FastOutSlowInEasing)) +
        slideOutVertically(tween(160, easing = FastOutSlowInEasing)) { -it / 2 } +
        shrinkVertically(tween(160, easing = FastOutSlowInEasing))

/**
 * Devuelve `valor` y, cuando es nulo, el ultimo no nulo que hubo: asi un chip que se esta yendo
 * conserva su texto durante la animacion de salida en vez de encogerse vacio.
 */
@Composable
private fun <T : Any> recordarUltimo(valor: T?): T? {
    val ultimo = remember { mutableStateOf(valor) }
    if (valor != null) SideEffect { ultimo.value = valor }
    return valor ?: ultimo.value
}

/**
 * Boton de zoom del mapa: 40 dp, tonal, con la misma superficie, tinta y forma que el boton de
 * ubicacion (primaryContainer, forma `medium`), y la escala corta al pulsar.
 */
@Composable
private fun BotonZoom(icono: ImageVector, descripcion: String, onClick: () -> Unit) {
    val fuente = remember { MutableInteractionSource() }
    FilledTonalIconButton(
        onClick = onClick,
        modifier = Modifier.size(40.dp).presionable(fuente, escala = 0.92f),
        shape = MaterialTheme.shapes.medium,
        colors = IconButtonDefaults.filledTonalIconButtonColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
            contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
        ),
        interactionSource = fuente,
    ) { Icon(icono, contentDescription = descripcion) }
}

/** El "menos" de Material (igual que Icons.Filled.Remove, que vive en el paquete extendido de iconos, que la app no trae). */
private val IconoQuitar: ImageVector = materialIcon(name = "Filled.Remove") {
    materialPath {
        moveTo(19f, 13f)
        horizontalLineTo(5f)
        verticalLineToRelative(-2f)
        horizontalLineToRelative(14f)
        verticalLineToRelative(2f)
        close()
    }
}

/** Chip flotante de aviso (sin conexion, servidor que no responde): ambar/naranja segun el tema, como AvisoDato. */
@Composable
private fun ChipAviso(texto: String, modifier: Modifier = Modifier) {
    val oscuro = temaOscuro()
    Text(
        texto,
        modifier
            .background(if (oscuro) Color(0xF2431407) else Color(0xF2FFEDD5), MaterialTheme.shapes.small)
            .padding(horizontal = 10.dp, vertical = 5.dp),
        color = if (oscuro) Color(0xFFFDBA74) else Color(0xFF9A3412),
        style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis,
    )
}

/** Chip flotante informativo (nowcasting): tintas primarias del tema, legible en claro y oscuro. */
@Composable
private fun ChipInfo(texto: String, modifier: Modifier = Modifier) {
    Text(
        texto,
        modifier
            .background(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.94f), MaterialTheme.shapes.small)
            .padding(horizontal = 10.dp, vertical = 5.dp),
        color = MaterialTheme.colorScheme.onPrimaryContainer,
        style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis,
    )
}

/** Chip flotante "cargando" de una capa pesada: rueda chica y texto sobre la superficie del tema. */
@Composable
private fun ChipCarga(texto: String, modifier: Modifier = Modifier) {
    Row(
        modifier
            .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.94f), RoundedCornerShape(999.dp))
            .border(bordeTarjeta(), RoundedCornerShape(999.dp))
            .padding(horizontal = 12.dp, vertical = 6.dp)
            .semantics(mergeDescendants = true) {},
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CircularProgressIndicator(Modifier.size(14.dp), strokeWidth = 2.dp)
        Spacer(Modifier.width(8.dp))
        Text(texto, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}
