package pe.simpac.app.ui.mapa

import android.view.ViewGroup
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.launch
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import pe.simpac.app.dominio.DiaMapa
import pe.simpac.app.dominio.Lluvia
import pe.simpac.app.ubicacion.Posicion
import pe.simpac.app.ubicacion.Ubicacion
import pe.simpac.app.ui.EstadoCompartido
import pe.simpac.app.ui.componentes.ErrorReintentar

/**
 * Pestana Mapa: mapa nativo (osmdroid) con las capas de SIMPAC. Arriba, el selector de dia (Hoy /
 * Manana / Pasado, que mueve avisos y pronostico) y el chip con el nivel de tu zona; abajo la barra de
 * capas; al tocar algo, una hoja inferior de Material 3 en lenguaje claro. Solo existe la barra
 * inferior de la app: nada de barras duplicadas.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MapaScreen(compartido: EstadoCompartido, vm: MapaViewModel = viewModel()) {
    val contexto = LocalContext.current
    val estado by vm.estado.collectAsStateWithLifecycle()
    val encuadre by compartido.encuadre.collectAsStateWithLifecycle()
    val ambito = rememberCoroutineScope()
    val ciclo = LocalLifecycleOwner.current
    var seleccion by remember { mutableStateOf<Seleccion?>(null) }
    var hojaCapas by remember { mutableStateOf(false) }
    // centro ya aplicado: se vuelve a centrar solo si el ViewModel manda otro (cambio de ciudad o de ubicacion)
    var centradoEn by remember { mutableStateOf<Posicion?>(null) }

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

    // centro inicial: tu ubicacion o la ciudad elegida, zoom 13 (una vez por centro distinto)
    LaunchedEffect(estado.centro) {
        val c = estado.centro ?: return@LaunchedEffect
        if (c != centradoEn) {
            gestor.mapa.controller.setZoom(estado.zoomInicial)
            gestor.mapa.controller.setCenter(GeoPoint(c.lat, c.lon))
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
    LaunchedEffect(encuadre, estado.cargando) {
        val e = encuadre ?: return@LaunchedEffect
        if (estado.cargando) return@LaunchedEffect
        val caja = vm.cajaParaEncuadre(e.rioAna, e.lat, e.lon)
        if (caja != null) gestor.encuadrar(caja)
        else if (e.lat != null && e.lon != null) gestor.centrar(Posicion(e.lat, e.lon), 13.0)
        centradoEn = estado.centro   // el encuadre manda sobre el centro inicial
        compartido.encuadreAtendido()
    }

    Column(Modifier.fillMaxSize()) {
        // selector de dia: mueve a la vez los avisos de SENAMHI (por su fecha) y el pronostico por localidad
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface).padding(horizontal = 12.dp, vertical = 4.dp)) {
            DiaMapa.entries.forEachIndexed { i, dia ->
                SegmentedButton(
                    selected = estado.dia == dia,
                    onClick = { vm.elegirDia(dia) },
                    shape = SegmentedButtonDefaults.itemShape(index = i, count = DiaMapa.entries.size),
                    label = { Text(dia.etiqueta, maxLines = 1) },
                )
            }
        }
        // clipToBounds: osmdroid pinta en todo el canvas y, sin recorte, se encimaba al selector de dia
        Box(Modifier.weight(1f).fillMaxWidth().clipToBounds()) {
            AndroidView(modifier = Modifier.fillMaxSize().clipToBounds(), factory = { gestor.mapa })

            Column(Modifier.align(Alignment.TopCenter).padding(top = 10.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                // chip con el nivel de tu zona (texto + color)
                estado.chip?.let { chip ->
                    Row(
                        Modifier.background(Color(chip.nivel.fondo), RoundedCornerShape(999.dp)).padding(horizontal = 14.dp, vertical = 7.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(chip.texto, color = Color(chip.nivel.textoSobreFondo), fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                if (estado.deCache) {
                    Text("Sin conexión: se muestra lo último guardado", Modifier.background(Color(0xFFFFEDD5), RoundedCornerShape(8.dp)).padding(horizontal = 8.dp, vertical = 4.dp), color = Color(0xFF9A3412), style = MaterialTheme.typography.bodySmall)
                }
                // chip del nowcasting: que se ve (o por que no se ve nada)
                estado.chipNowcast?.let { texto ->
                    Text(texto, Modifier.padding(horizontal = 40.dp).background(Color(0xEEEFF6FF), RoundedCornerShape(8.dp)).padding(horizontal = 8.dp, vertical = 4.dp),
                        color = Color(0xFF1E3A8A), style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                if (Capa.LLUVIA_OBSERVADA in estado.capas && estado.lluviaObsSinServidor) {
                    Text(Lluvia.SIN_SERVIDOR, Modifier.padding(horizontal = 40.dp).background(Color(0xFFFFEDD5), RoundedCornerShape(8.dp)).padding(horizontal = 8.dp, vertical = 4.dp),
                        color = Color(0xFF9A3412), style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
            }
            if (estado.cargando) {
                Row(Modifier.align(Alignment.Center).background(Color(0xDDFFFFFF), RoundedCornerShape(12.dp)).padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.padding(end = 10.dp))
                    Text("Leyendo avisos y ríos...", color = Color(0xFF0F172A))
                }
            }
            estado.error?.let { mensaje ->
                Box(Modifier.align(Alignment.Center).background(Color(0xEEFFFFFF), RoundedCornerShape(12.dp))) {
                    ErrorReintentar(mensaje, onReintentar = { vm.cargar() })
                }
            }

            SmallFloatingActionButton(
                onClick = {
                    ambito.launch {
                        val p = vm.ubicacionAhora() ?: estado.ubicacion
                        when {
                            p == null -> Toast.makeText(contexto, "Activa tu ubicación en Inicio (\"Usar mi ubicación\") para centrar el mapa en ti", Toast.LENGTH_LONG).show()
                            // el mapa solo cubre el Perú: fuera de esa caja el mapa se iria al borde (mar) sin nada que ver
                            !Ubicacion.enPeru(p) -> Toast.makeText(contexto, "Tu ubicación está fuera del Perú: el mapa de SIMPAC solo cubre el país", Toast.LENGTH_LONG).show()
                            else -> gestor.centrar(p, maxOf(gestor.mapa.zoomLevelDouble, 13.0))
                        }
                    }
                },
                modifier = Modifier.align(Alignment.BottomEnd).padding(end = 12.dp, bottom = 30.dp),
            ) { Icon(Icons.Filled.LocationOn, contentDescription = "Centrar en tu ubicación") }

            // atribucion visible abajo: una sola linea, chica, como la atribucion corta del celular en la web
            val extra = listOfNotNull(
                if (Capa.SATELITE in estado.capas) "NASA GIBS" else null,
                if (Capa.LLUVIA_OBSERVADA in estado.capas || Capa.LLUVIA_AHORA in estado.capas || Capa.NOWCAST in estado.capas) "SENAMHI (IDESEP)" else null,
            )
            Text(
                OsmdroidSimpac.atribucion + extra.joinToString("") { ", $it" },
                Modifier.align(Alignment.BottomStart).fillMaxWidth().background(Color(0xCCFFFFFF)).padding(horizontal = 6.dp, vertical = 1.dp),
                style = MaterialTheme.typography.labelSmall, color = Color(0xFF334155), maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
        }

        // barra de capas (abajo del mapa, encima de la barra de la app)
        Row(
            Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface).horizontalScroll(rememberScrollState()).padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = { hojaCapas = true }) {
                Icon(Icons.Filled.List, contentDescription = null)
                Text(" Capas", style = MaterialTheme.typography.labelLarge)
            }
            Capa.entries.forEach { capa ->
                FilterChip(selected = capa in estado.capas, onClick = { vm.alternarCapa(capa) }, label = { Text(capa.corta) })
            }
        }
    }

    seleccion?.let { sel ->
        ModalBottomSheet(onDismissRequest = { seleccion = null }) { HojaSeleccion(sel, estado) }
    }
    if (hojaCapas) {
        ModalBottomSheet(onDismissRequest = { hojaCapas = false }) {
            HojaCapas(
                estado,
                AccionesCapas(
                    alternar = { vm.alternarCapa(it) },
                    elegirHorizonte = { vm.elegirHorizonteNowcast(it) },
                    elegirLluviaObservada = { vm.elegirLluviaObservada(it) },
                    elegirFen = { vm.elegirFen(it) },
                ),
            )
        }
    }
}
