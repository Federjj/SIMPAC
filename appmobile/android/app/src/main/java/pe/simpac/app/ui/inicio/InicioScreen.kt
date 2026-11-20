package pe.simpac.app.ui.inicio

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.ContentTransform
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.EaseOutCubic
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.outlined.Call
import androidx.compose.material.icons.outlined.Create
import androidx.compose.material.icons.outlined.KeyboardArrowDown
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.dominio.Alertas
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.Nivel
import pe.simpac.app.dominio.Pronostico
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.EncuadreMapa
import pe.simpac.app.ui.Intents
import pe.simpac.app.ui.acudir.AcudirResumen
import pe.simpac.app.ui.acudir.AcudirViewModel
import pe.simpac.app.ui.componentes.AparecerEscalonado
import pe.simpac.app.ui.componentes.AvisoDato
import pe.simpac.app.ui.componentes.BotonEnlace
import pe.simpac.app.ui.componentes.ContenidoConEstado
import pe.simpac.app.ui.componentes.EsqueletoBloque
import pe.simpac.app.ui.componentes.EsqueletoCirculo
import pe.simpac.app.ui.componentes.EsqueletoLinea
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.LocalAvisador
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.RefrescarAlTirar
import pe.simpac.app.ui.componentes.Seccion
import pe.simpac.app.ui.componentes.Transiciones
import pe.simpac.app.ui.componentes.bordeTarjeta
import pe.simpac.app.ui.componentes.presionable
import pe.simpac.app.ui.componentes.temaOscuro

/**
 * Pantalla Inicio con su ViewModel (la parte sin estado es InicioContenido, que prueba el androidTest).
 * "Tirar para actualizar" y "Reintentar" recargan tambien la seccion "A donde acudir" (mismo dueno de
 * ViewModel: la entrada de navegacion de la pestana), y una recarga fallida con datos en pantalla se
 * avisa abajo con el snackbar global en vez de tapar la pantalla.
 */
@Composable
fun InicioScreen(irAlertas: () -> Unit, irReportar: () -> Unit, irMapa: (EncuadreMapa) -> Unit = {}, vm: InicioViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val vmAcudir: AcudirViewModel = viewModel()
    val avisador = LocalAvisador.current
    val pedirPermiso = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { r ->
        vm.gpsDecidido(r[Manifest.permission.ACCESS_FINE_LOCATION] == true || r[Manifest.permission.ACCESS_COARSE_LOCATION] == true)
    }
    fun recargar() { vm.cargar(); vmAcudir.cargar() }
    LaunchedEffect(estado.error, estado.tieneDatos) {
        val e = estado.error
        if (e != null && estado.tieneDatos) avisador.avisar(e, accion = "Reintentar") { recargar() }
    }
    InicioContenido(
        estado = estado,
        onReintentar = { recargar() },
        onUsarGps = { pedirPermiso.launch(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION)) },
        onSinGps = { vm.gpsDecidido(false) },
        onElegirDepartamento = { vm.elegirDepartamento(it) },
        irAlertas = irAlertas,
        irReportar = irReportar,
        seccionAcudir = { AcudirResumen(vmAcudir) },
        verRioEnMapa = {
            val rio = estado.rioDestacado ?: estado.rios.firstOrNull()
            irMapa(EncuadreMapa(rio?.rioAna, estado.centroLat, estado.centroLon))
        },
    )
}

/**
 * Inicio sin estado propio. Mientras se leen los ajustes no se dibuja nada (asi la primera apertura no
 * muestra el esqueleto de los datos para despues cruzar a "Tu ubicacion"); despues, o la explicacion
 * del GPS o el esqueleto con la silueta de la pantalla hasta que llega el primer dato. Con datos,
 * recargar es "tirar para actualizar" (onReintentar) sin volver al esqueleto. Las secciones aparecen
 * escalonadas solo la primera vez; el semaforo, el titular y los chips cruzan con un fundido cuando
 * cambia la zona o el nivel.
 */
@Composable
fun InicioContenido(
    estado: EstadoInicio,
    onReintentar: () -> Unit,
    onUsarGps: () -> Unit,
    onSinGps: () -> Unit,
    onElegirDepartamento: (String) -> Unit,
    irAlertas: () -> Unit,
    irReportar: () -> Unit = {},
    seccionAcudir: @Composable () -> Unit = {},   // "A donde acudir" con su propio ViewModel (ui/acudir)
    verRioEnMapa: () -> Unit = {},
) {
    val vista = when {
        estado.leyendoAjustes -> VistaInicio.LEYENDO
        estado.explicarGps -> VistaInicio.EXPLICAR_GPS
        else -> VistaInicio.CONTENIDO
    }
    AnimatedContent(
        targetState = vista,
        modifier = Modifier.fillMaxSize(),
        transitionSpec = { fundido() },
        label = "inicio",
    ) { v ->
        when (v) {
            // todavia no se sabe si toca explicar el GPS: solo el fondo, lo que dure leer los ajustes; lo que siga entra con fundido
            VistaInicio.LEYENDO -> Box(Modifier.fillMaxSize())
            VistaInicio.EXPLICAR_GPS -> ExplicacionGps(onUsarGps, onSinGps)
            VistaInicio.CONTENIDO -> ContenidoInicio(estado, onReintentar, onElegirDepartamento, irAlertas, irReportar, seccionAcudir, verRioEnMapa)
        }
    }
}

/** Que se ve en Inicio: nada (leyendo los ajustes), la explicacion del GPS o el contenido (esqueleto, error o datos). */
private enum class VistaInicio { LEYENDO, EXPLICAR_GPS, CONTENIDO }

/** Esqueleto, error o la pantalla con datos (con "tirar para actualizar"), segun el estado. */
@Composable
private fun ContenidoInicio(
    estado: EstadoInicio,
    onReintentar: () -> Unit,
    onElegirDepartamento: (String) -> Unit,
    irAlertas: () -> Unit,
    irReportar: () -> Unit,
    seccionAcudir: @Composable () -> Unit,
    verRioEnMapa: () -> Unit,
) {
    val tieneDatos = estado.tieneDatos
    ContenidoConEstado(
        cargando = estado.cargando && !tieneDatos,
        error = estado.error?.takeIf { !tieneDatos },
        onReintentar = onReintentar,
        modifier = Modifier.fillMaxSize(),
        esqueleto = { EsqueletoInicio() },
    ) {
        RefrescarAlTirar(refrescando = estado.cargando && tieneDatos, onRefrescar = onReintentar, modifier = Modifier.fillMaxSize()) {
            Column(
                Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp).testTag("inicio"),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                AnimatedVisibility(visible = estado.deCache, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
                    AvisoDato("Sin conexión: se muestra lo último guardado, de las ${Tiempo.horaCorta(estado.obtenidoEn)}.", fuerte = true)
                }
                AnimatedVisibility(visible = estado.desactualizado, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
                    AvisoDato("Dato desactualizado: SIMPAC no actualiza esta zona desde hace ${Tiempo.haceTexto(estado.titularRevisadoMs).removePrefix("hace ")}. Verifica con los canales oficiales.")
                }
                AparecerEscalonado(0) { Semaforo(estado, onElegirDepartamento) }
                AparecerEscalonado(1) { TarjetaTitular(estado) }
                AparecerEscalonado(2) { ChipsZona(estado, irAlertas, verRioEnMapa) }
                AparecerEscalonado(3) { ContextoNino(estado) }
                AparecerEscalonado(4) { PronosticoTresDias(estado) }
                AparecerEscalonado(5) { BotonesLlamar() }
                seccionAcudir()
                TarjetaComunidad(irReportar)
                Fuentes(estado)
                PieReferencial()
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

/** Cruce con fundido (220 ms entra, 150 ms sale) y tamano animado, para textos y chips que cambian. */
private fun <T> AnimatedContentTransitionScope<T>.fundido(): ContentTransform =
    (fadeIn(tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing)) togetherWith fadeOut(tween(150, easing = FastOutSlowInEasing)))
        .using(SizeTransform(clip = false) { _, _ -> tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing) })

/** Pantalla previa al permiso de ubicacion: icono, por que se pide y las dos salidas. */
@Composable
private fun ExplicacionGps(onUsarGps: () -> Unit, onSinGps: () -> Unit) {
    val vista = LocalView.current
    val fuenteUsar = remember { MutableInteractionSource() }
    val fuenteElegir = remember { MutableInteractionSource() }
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            Modifier.size(72.dp).background(MaterialTheme.colorScheme.primaryContainer, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Outlined.LocationOn, contentDescription = null, tint = MaterialTheme.colorScheme.onPrimaryContainer, modifier = Modifier.size(36.dp))
        }
        Spacer(Modifier.height(16.dp))
        Text("Tu ubicación", style = MaterialTheme.typography.headlineMedium, textAlign = TextAlign.Center)
        Spacer(Modifier.height(12.dp))
        Text(
            "SIMPAC usa tu ubicación solo mientras la app está abierta, para saber en qué departamento estás, " +
                "darte el pronóstico de la localidad más cercana y calcular a cuánto quedan la posta, la comisaría y los bomberos. " +
                "No la guarda ni la comparte. Si prefieres, elige tu departamento a mano.",
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(24.dp))
        Button(
            onClick = { Haptica.toque(vista); onUsarGps() },
            interactionSource = fuenteUsar,
            modifier = Modifier.fillMaxWidth().presionable(fuenteUsar),
        ) { Text("Usar mi ubicación") }
        Spacer(Modifier.height(8.dp))
        OutlinedButton(
            onClick = { Haptica.toque(vista); onSinGps() },
            interactionSource = fuenteElegir,
            modifier = Modifier.fillMaxWidth().presionable(fuenteElegir),
        ) { Text("Elegir mi departamento") }
    }
}

/**
 * Cabecera: el disco del nivel (96 dp, con la etiqueta adentro: ya dice el nivel, asi que no se repite
 * en una pastilla debajo), el departamento y el enlace "cambiar" con su menu. Espaciados de 8 dp para
 * que la primera tarjeta quede a la vista sin desplazar.
 */
@Composable
private fun Semaforo(estado: EstadoInicio, onElegirDepartamento: (String) -> Unit) {
    var abierto by remember { mutableStateOf(false) }
    val vista = LocalView.current
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        DiscoNivelAnimado(estado.nivel, Modifier.testTag("semaforo"))
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            AnimatedContent(targetState = estado.departamento, transitionSpec = { fundido() }, label = "departamento") { nombre ->
                Text(nombre, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.testTag("departamento"))
            }
            Spacer(Modifier.width(8.dp))
            Box {
                BotonEnlace(if (estado.porGps) "por GPS, cambiar" else "cambiar") { Haptica.toque(vista); abierto = true }
                DropdownMenu(expanded = abierto, onDismissRequest = { abierto = false }) {
                    Departamentos.TODOS.forEach { d ->
                        DropdownMenuItem(text = { Text(d.nombre) }, onClick = { abierto = false; onElegirDepartamento(d.nombre) })
                    }
                }
            }
        }
    }
}

/**
 * Disco del semaforo (misma silueta y textos que DiscoNivel del kit, en 96 dp): entra con escala de 0,9
 * a 1 la primera vez (el fundido lo pone la seccion escalonada) y su color cruza en 300 ms cuando cambia
 * el nivel. Siempre color + etiqueta; "EMERGENCIA" y "SIN DATOS" van un poco mas chicos para caber.
 */
@Composable
private fun DiscoNivelAnimado(nivel: Nivel, modifier: Modifier = Modifier, tamano: Int = 96) {
    val fondo = animateColorAsState(Color(nivel.fondo), tween(300, easing = FastOutSlowInEasing), label = "fondoNivel")
    val tinta by animateColorAsState(Color(nivel.textoSobreFondo), tween(300, easing = FastOutSlowInEasing), label = "tintaNivel")
    var yaAparecio by rememberSaveable { mutableStateOf(false) }
    val escala = remember { Animatable(if (yaAparecio) 1f else 0.9f) }
    LaunchedEffect(Unit) {
        if (yaAparecio) return@LaunchedEffect
        escala.animateTo(1f, tween(Transiciones.APARECER_MS, easing = EaseOutCubic))
        yaAparecio = true
    }
    Box(
        modifier = modifier
            .size(tamano.dp)
            .graphicsLayer { scaleX = escala.value; scaleY = escala.value }
            .drawBehind { drawCircle(fondo.value) }
            .semantics { contentDescription = "Nivel de la zona: ${nivel.etiqueta}" },
        contentAlignment = Alignment.Center,
    ) {
        AnimatedContent(targetState = nivel, transitionSpec = { fundido() }, label = "textoNivel") { n ->
            Text(
                n.etiqueta.uppercase(),
                color = tinta,
                fontWeight = FontWeight.Bold,
                fontSize = when (n) {
                    Nivel.EMERGENCIA -> 13.sp
                    Nivel.SIN_DATO -> 15.sp
                    else -> 16.sp
                },
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun TarjetaTitular(estado: EstadoInicio) {
    Seccion("Tu zona ahora") {
        AnimatedContent(targetState = estado.titular, modifier = Modifier.fillMaxWidth(), transitionSpec = { fundido() }, label = "titular") { t ->
            if (t == null) {
                Text("SIMPAC todavía no tiene un titular para ${estado.departamento}. No significa que todo esté en calma: revisa las alertas y los canales oficiales.", style = MaterialTheme.typography.bodyLarge)
            } else {
                Column(Modifier.fillMaxWidth()) {
                    Text(t.titular_corto ?: t.titular ?: "", style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("titular"))
                    if (!t.detalle.isNullOrBlank()) {
                        Spacer(Modifier.height(6.dp))
                        DetalleDesplegable(t.detalle)
                    }
                    Spacer(Modifier.height(6.dp))
                    LineaFuente("Generado el ${Tiempo.horaCorta(estado.titularGeneradoMs)} (${Tiempo.haceTexto(estado.titularGeneradoMs)}), " +
                        if (t.origen == "llm") "redactado por un modelo de lenguaje con cifras oficiales y validado" else "por reglas de SIMPAC con datos oficiales")
                }
            }
        }
    }
}

/** Lineas del detalle del titular que se ven plegadas; "Leer mas" despliega el resto. */
private const val LINEAS_DETALLE = 5

/**
 * Detalle del titular plegado a 5 lineas con puntos suspensivos y "Leer mas" / "Leer menos" (solo si
 * hay mas texto que eso), con el alto animado. No cambia el texto, solo cuanto se despliega; para el
 * lector de pantalla el parrafo entero sigue ahi. Si el titular cambia, vuelve a verse plegado.
 */
@Composable
private fun DetalleDesplegable(detalle: String) {
    val vista = LocalView.current
    var expandido by rememberSaveable { mutableStateOf(false) }
    var desborda by remember { mutableStateOf(false) }
    val giro by animateFloatAsState(if (expandido) 180f else 0f, tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing), label = "giroLeerMas")
    Column(Modifier.fillMaxWidth().animateContentSize(tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing))) {
        Text(
            detalle,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = if (expandido) Int.MAX_VALUE else LINEAS_DETALLE,
            overflow = TextOverflow.Ellipsis,
            // se mide plegado: si cabe entero no hace falta el enlace
            onTextLayout = { if (!expandido) desborda = it.hasVisualOverflow },
        )
        if (desborda || expandido) {
            BotonEnlace(
                if (expandido) "Leer menos" else "Leer más",
                iconoFinal = {
                    Icon(
                        Icons.Outlined.KeyboardArrowDown,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp).graphicsLayer { rotationZ = giro },
                    )
                },
            ) { Haptica.toque(vista); expandido = !expandido }
        }
    }
}

@Composable
private fun ChipsZona(estado: EstadoInicio, irAlertas: () -> Unit, verRioEnMapa: () -> Unit) {
    val vista = LocalView.current
    // la tinta del nivel (oscura, para fondo claro) no se lee sobre el tema oscuro: ahi va el color del disco
    val oscuro = temaOscuro()
    fun tintaDe(n: Nivel): Color = Color(if (oscuro) n.fondo else n.tinta)
    // texto y tinta de cada chip, calculados una vez por cambio de datos (el cruce anima el cambio)
    val chipAlertas: Pair<String, Color?>? = remember(estado.alertasLeidas, estado.alertasZona, oscuro) {
        if (!estado.alertasLeidas) null else {
            val oficiales = Alertas.cuantasOficiales(estado.alertasZona)
            val peor = estado.alertasZona.filter { Alertas.esOficial(it) }.minOfOrNull { Alertas.nivelDe(it).orden }?.let { o -> Nivel.entries.first { it.orden == o } }
            val texto = when (oficiales) {
                0 -> "Sin alertas oficiales vigentes"
                1 -> "1 alerta oficial"
                else -> "$oficiales alertas oficiales"
            }
            texto to peor?.let { tintaDe(it) }
        }
    }
    val chipRio: Pair<String, Color?>? = remember(estado.rioDestacado, estado.rios, oscuro) {
        val r = estado.rioDestacado
        when {
            r != null -> {
                // rio_cauce.nombre ya suele traer "Río ..."; no se duplica la palabra
                val nombre = if (r.nombre.trim().lowercase().startsWith("río") || r.nombre.trim().lowercase().startsWith("rio")) r.nombre.trim() else "Río ${r.nombre}"
                "$nombre: ${r.texto}" to tintaDe(r.nivel)
            }
            estado.rios.isNotEmpty() -> "${estado.rios.size} ríos con estación, sin señales hoy" to null
            else -> null
        }
    }
    val hayAlertas = estado.alertasLeidas && estado.alertasZona.isNotEmpty()
    val hayRios = estado.rios.isNotEmpty()
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        // cada chip con su alto natural: si no caben juntos, el segundo baja a la linea siguiente
        FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (chipAlertas != null) {
                AnimatedContent(targetState = chipAlertas, transitionSpec = { fundido() }, label = "chipAlertas") { (texto, tinta) ->
                    ChipZona(texto, Modifier.testTag("chip_alertas"), color = tinta)
                }
            }
            if (chipRio != null) {
                AnimatedContent(targetState = chipRio, transitionSpec = { fundido() }, label = "chipRio") { (texto, tinta) ->
                    // hasta dos lineas: el caudal va al final y no se pierde en un telefono angosto
                    ChipZona(texto, color = tinta, maxLines = 2)
                }
            }
        }
        if (hayAlertas || hayRios) {
            FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                if (hayAlertas) EnlacePestana("Ver las alertas de ${estado.departamento}") { Haptica.toque(vista); irAlertas() }
                if (hayRios) EnlacePestana("Ver el río en el mapa") { Haptica.toque(vista); verRioEnMapa() }
            }
        }
    }
}

/**
 * Pastilla de texto con borde (la silueta de `Chip` del kit) acotada a `maxLines` con puntos
 * suspensivos, para que un texto largo no deforme la fila. El lector de pantalla recibe el texto entero.
 */
@Composable
private fun ChipZona(texto: String, modifier: Modifier = Modifier, color: Color? = null, maxLines: Int = 1) {
    Box(
        modifier = modifier
            .border(1.dp, color ?: MaterialTheme.colorScheme.outline, Pastilla)
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Text(
            texto,
            style = MaterialTheme.typography.bodySmall,
            color = color ?: MaterialTheme.colorScheme.onSurface,
            maxLines = maxLines,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/** Enlace a otra pestana: texto sin relleno (empieza donde empieza el chip de arriba) y flecha de 16 dp al final. */
@Composable
private fun EnlacePestana(texto: String, onClick: () -> Unit) {
    BotonEnlace(
        texto,
        iconoFinal = { Icon(Icons.AutoMirrored.Outlined.ArrowForward, contentDescription = null, modifier = Modifier.size(16.dp)) },
        onClick = onClick,
    )
}

@Composable
private fun ContextoNino(estado: EstadoInicio) {
    Seccion("El Niño ahora") {
        val e = estado.enfen
        if (e != null) {
            Text(e.estado ?: "Sin estado", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text("Comunicado oficial ${e.numero}-${e.anio}${if (e.extraordinario) " (extraordinario)" else ""} del ENFEN, ${Tiempo.fechaLarga(e.fecha)}." +
                (e.proximo?.let { " Próximo: ${Tiempo.fechaLarga(it)}." } ?: ""), style = MaterialTheme.typography.bodyMedium)
        } else {
            Text(estado.errorApi ?: "Sin contexto El Niño por ahora.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun PronosticoTresDias(estado: EstadoInicio) {
    Seccion(if (estado.localidad != null) "Pronóstico de SENAMHI en ${estado.localidad}" else "Pronóstico de SENAMHI") {
        if (estado.pronostico.isEmpty()) {
            Text("No hay pronóstico de SENAMHI para una localidad cercana.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                estado.pronostico.forEach { f ->
                    Column(Modifier.weight(1f)) {
                        Text(Tiempo.etiquetaDia(f.fecha ?: ""), style = MaterialTheme.typography.labelLarge)
                        Text(Pronostico.resumenDia(f), style = MaterialTheme.typography.bodyMedium)
                        Text(Pronostico.temperaturas(f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

/** "Llamar 105" y "Llamar 116" (abren el marcador; la persona confirma), con icono y respuesta al pulsar. */
@Composable
private fun BotonesLlamar() {
    val contexto = LocalContext.current
    val vista = LocalView.current
    val fuente105 = remember { MutableInteractionSource() }
    val fuente116 = remember { MutableInteractionSource() }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Button(
            onClick = { Haptica.toque(vista); Intents.marcar(contexto, "105") },
            interactionSource = fuente105,
            modifier = Modifier.weight(1f).presionable(fuente105),
        ) {
            Icon(Icons.Outlined.Call, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text("Llamar 105")
        }
        OutlinedButton(
            onClick = { Haptica.toque(vista); Intents.marcar(contexto, "116") },
            interactionSource = fuente116,
            modifier = Modifier.weight(1f).presionable(fuente116),
        ) {
            Icon(Icons.Outlined.Call, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text("Llamar 116")
        }
    }
}

@Composable
private fun TarjetaComunidad(irReportar: () -> Unit) {
    val vista = LocalView.current
    val fuente = remember { MutableInteractionSource() }
    Seccion("Comunidad") {
        Text("¿Ves una inundación, un huayco, una vía bloqueada o un atasco? Repórtalo desde donde estás: dura 12 horas y la comunidad lo vota.", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(8.dp))
        Button(onClick = { Haptica.toque(vista); irReportar() }, interactionSource = fuente, modifier = Modifier.presionable(fuente)) {
            Icon(Icons.Outlined.Create, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text("Reportar")
        }
    }
}

@Composable
private fun Fuentes(estado: EstadoInicio) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text("Fuentes y hora", style = MaterialTheme.typography.labelLarge)
        estado.fuentes.forEach { LineaFuente("${it.nombre}: ${it.hora}") }
        estado.avisos.forEach { LineaFuente(it) }
    }
}

/* ---------- Esqueleto de Inicio: la misma silueta que la pantalla con datos ---------- */

/** Tarjeta con el mismo borde, forma y relleno que Seccion, para dibujar su silueta mientras carga. */
@Composable
private fun TarjetaEsqueleto(contenido: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = bordeTarjeta(),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp), content = contenido)
    }
}

private val Pastilla = RoundedCornerShape(999.dp)

/** Silueta de Inicio: semaforo, titular, chips, El Nino, pronostico de 3 dias, botones, a donde acudir y comunidad. */
@Composable
private fun EsqueletoInicio() {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            EsqueletoCirculo(96.dp)
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                EsqueletoLinea(alto = 22.dp, modifier = Modifier.width(150.dp))
                EsqueletoLinea(alto = 12.dp, modifier = Modifier.width(56.dp))
            }
        }
        TarjetaEsqueleto {
            EsqueletoLinea(anchoFraccion = 0.4f, alto = 16.dp)
            Spacer(Modifier.height(2.dp))
            EsqueletoLinea(anchoFraccion = 1f, alto = 18.dp)
            EsqueletoLinea(anchoFraccion = 0.75f, alto = 18.dp)
            Spacer(Modifier.height(2.dp))
            EsqueletoLinea(anchoFraccion = 1f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 0.95f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 1f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 0.9f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 0.7f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 0.2f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 0.6f, alto = 10.dp)
        }
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            EsqueletoBloque(30.dp, Modifier.width(140.dp), Pastilla)
            EsqueletoBloque(30.dp, Modifier.fillMaxWidth(0.85f), Pastilla)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            EsqueletoLinea(alto = 14.dp, modifier = Modifier.width(170.dp))
            EsqueletoLinea(alto = 14.dp, modifier = Modifier.width(130.dp))
        }
        TarjetaEsqueleto {
            EsqueletoLinea(anchoFraccion = 0.35f, alto = 16.dp)
            EsqueletoLinea(anchoFraccion = 0.6f, alto = 14.dp)
            EsqueletoLinea(anchoFraccion = 1f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 0.8f, alto = 12.dp)
        }
        TarjetaEsqueleto {
            EsqueletoLinea(anchoFraccion = 0.7f, alto = 16.dp)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                repeat(3) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        EsqueletoLinea(anchoFraccion = 0.6f, alto = 12.dp)
                        EsqueletoLinea(anchoFraccion = 1f, alto = 12.dp)
                        EsqueletoLinea(anchoFraccion = 0.8f, alto = 10.dp)
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            EsqueletoBloque(40.dp, Modifier.weight(1f), Pastilla)
            EsqueletoBloque(40.dp, Modifier.weight(1f), Pastilla)
        }
        TarjetaEsqueleto {
            EsqueletoLinea(anchoFraccion = 0.4f, alto = 16.dp)
            EsqueletoLinea(anchoFraccion = 0.9f, alto = 12.dp)
            repeat(3) {
                Spacer(Modifier.height(2.dp))
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    EsqueletoLinea(anchoFraccion = 0.75f, alto = 14.dp, modifier = Modifier.weight(1f))
                    EsqueletoLinea(alto = 12.dp, modifier = Modifier.width(48.dp))
                }
                EsqueletoLinea(anchoFraccion = 0.85f, alto = 12.dp)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    EsqueletoBloque(36.dp, Modifier.width(120.dp), Pastilla)
                    EsqueletoBloque(36.dp, Modifier.width(100.dp), Pastilla)
                }
            }
        }
        TarjetaEsqueleto {
            EsqueletoLinea(anchoFraccion = 0.3f, alto = 16.dp)
            EsqueletoLinea(anchoFraccion = 1f, alto = 12.dp)
            EsqueletoLinea(anchoFraccion = 0.7f, alto = 12.dp)
            EsqueletoBloque(40.dp, Modifier.width(120.dp), Pastilla)
        }
    }
}
