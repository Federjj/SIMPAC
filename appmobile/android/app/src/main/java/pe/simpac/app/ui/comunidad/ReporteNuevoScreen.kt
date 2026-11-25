package pe.simpac.app.ui.comunidad

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import coil.request.ImageRequest
import pe.simpac.app.data.EstadoSesion
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.TipoReporte
import pe.simpac.app.ubicacion.Ubicacion
import pe.simpac.app.ui.componentes.AparecerEscalonado
import pe.simpac.app.ui.componentes.Cargando
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.LocalAvisador
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.Transiciones
import pe.simpac.app.ui.componentes.bordeTarjeta
import pe.simpac.app.ui.componentes.temaOscuro
import java.util.Locale

/**
 * Formulario "Reportar incidente" (pages/ReporteNuevo.jsx). Exige sesion y ubicacion GPS real.
 * Los bloques aparecen escalonados la primera vez; el subtipo y la vista previa de la foto entran y
 * salen animados; al enviar, un velo con barra de progreso tapa el formulario con el paso en curso
 * ("Subiendo la foto" / "Enviando el reporte") y al terminar avisa "Reporte enviado" y abre el detalle.
 */
@Composable
fun ReporteNuevoScreen(volver: () -> Unit, abrirReporte: (String) -> Unit, irCuenta: () -> Unit, vm: ReporteNuevoViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val sesion by estadoSesion()
    val contexto = LocalContext.current
    val vista = LocalView.current
    val avisador = LocalAvisador.current

    LaunchedEffect(estado.creadoId) {
        estado.creadoId?.let { Haptica.confirmar(vista); avisador.avisar("Reporte enviado"); abrirReporte(it) }
    }
    // Vibra solo por los rechazos nuevos (al volver a esta pantalla no se repite)
    var rechazosVistos by rememberSaveable { mutableIntStateOf(estado.rechazos) }
    LaunchedEffect(estado.rechazos) {
        if (estado.rechazos > rechazosVistos) { rechazosVistos = estado.rechazos; Haptica.rechazar(vista) }
    }
    LaunchedEffect(sesion) { if (sesion is EstadoSesion.ConSesion) vm.buscarUbicacion() }
    // ubicacion solo en primer plano: al irse la app al fondo se deja de pedir la posicion; al volver se retoma lo interrumpido
    val ciclo = LocalLifecycleOwner.current
    DisposableEffect(ciclo) {
        val observador = LifecycleEventObserver { _, evento ->
            when (evento) {
                Lifecycle.Event.ON_STOP -> vm.detenerBusqueda()
                Lifecycle.Event.ON_START -> vm.reanudarBusqueda()
                else -> {}
            }
        }
        ciclo.lifecycle.addObserver(observador)
        onDispose { ciclo.lifecycle.removeObserver(observador) }
    }

    val pedirUbicacion = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { vm.buscarUbicacion() }
    var uriCamara by remember { mutableStateOf<Uri?>(null) }
    val tomarFoto = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok -> if (ok) vm.ponerFoto(uriCamara) }
    val pedirCamara = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) { val u = Fotos.uriParaCamara(contexto); uriCamara = u; tomarFoto.launch(u) }
    }
    val elegirFoto = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri -> if (uri != null) vm.ponerFoto(uri) }

    val enviando = estado.enviando != null
    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { Haptica.toque(vista); volver() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver a Comunidad") }
                Text("Reportar incidente", style = MaterialTheme.typography.headlineMedium)
            }
            when (sesion) {
                is EstadoSesion.Cargando -> Cargando("Revisando tu sesión...")
                is EstadoSesion.SinSesion -> AparecerEscalonado(0) {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        EntraPara("reportar", irCuenta)
                        Text(
                            "Los reportes se hacen desde donde estás (ubicación GPS), con el tipo de incidente, una descripción corta y una foto si quieres. Duran ${Comunidad.HORAS_VIGENCIA} horas y la comunidad los vota.",
                            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                is EstadoSesion.ConSesion -> {
                    AparecerEscalonado(0) {
                        BloqueUbicacion(estado, vm, enviando) {
                            pedirUbicacion.launch(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION))
                        }
                    }
                    AparecerEscalonado(1) { BloqueTipo(estado, vm, enviando) }
                    AparecerEscalonado(2) {
                        OutlinedTextField(
                            value = estado.descripcion,
                            onValueChange = { vm.cambiarDescripcion(it) },
                            label = { Text("Cuéntalo en pocas palabras (opcional)") },
                            placeholder = { Text("Ej.: la pista está anegada frente al mercado, pasan solo camionetas.") },
                            minLines = 3,
                            enabled = !enviando,
                            isError = estado.errores["descripcion"] != null,
                            supportingText = {
                                val error = estado.errores["descripcion"]
                                if (error != null) Text(error) else ContadorLetras(estado.descripcion.trim().length, Comunidad.MAX_DESCRIPCION)
                            },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    AparecerEscalonado(3) {
                        BloqueFoto(
                            estado, vm, enviando,
                            onTomar = { pedirCamara.launch(Manifest.permission.CAMERA) },
                            onElegir = { elegirFoto.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                        )
                    }
                    AparecerEscalonado(4) { BloqueEnviar(estado, vm, enviando, volver) }
                }
            }
            PieReferencial()
            Spacer(Modifier.height(8.dp))
        }
        VeloEnvio(estado.enviando)
    }
}

/**
 * Estado del GPS: cada caso se cruza con fundido; "lista" lleva icono, tinta verde legible en ambos temas
 * y la precision ("Precision: unos 12 m"). Mientras se afina se ve una rueda con texto; si la posicion
 * puede mejorar (peor que 30 m) hay un boton "Mejorar precision". Cada causa de no tener posicion trae
 * su accion: dar el permiso, activar la ubicacion del telefono (ajustes del sistema) o volver a buscar.
 */
@Composable
private fun BloqueUbicacion(estado: EstadoNuevo, vm: ReporteNuevoViewModel, enviando: Boolean, pedirPermiso: () -> Unit) {
    val vista = LocalView.current
    val contexto = LocalContext.current
    val avisador = LocalAvisador.current
    val verde = if (temaOscuro()) Color(0xFF86EFAC) else Color(0xFF166534)
    fun abrirAjustes(intencion: Intent) {
        try {
            contexto.startActivity(intencion)
        } catch (_: ActivityNotFoundException) {
            avisador.avisar("No se pudieron abrir los ajustes del teléfono")
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu ubicación", style = MaterialTheme.typography.titleMedium)
        AnimatedContent(
            targetState = estado.gps,
            transitionSpec = {
                (fadeIn(tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing)) togetherWith fadeOut(tween(150, easing = FastOutSlowInEasing)))
                    .using(SizeTransform(clip = false))
            },
            label = "gps",
        ) { gps ->
            when (gps) {
                EstadoGps.LISTA -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.Top) {
                        Icon(Icons.Outlined.CheckCircle, contentDescription = null, tint = verde, modifier = Modifier.padding(top = 2.dp).size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        val precision = estado.precisionM?.let { Ubicacion.textoMetros(it) } ?: "sin dato"
                        Text(
                            "Ubicación lista (${String.format(Locale.US, "%.4f, %.4f", estado.lat, estado.lon)}). Precisión: $precision. El reporte se marcará ahí.",
                            style = MaterialTheme.typography.bodyMedium, color = verde,
                        )
                    }
                    if (estado.afinando) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                            Text(
                                "Afinando la posición (hasta ${Ubicacion.ESPERA_REPORTE_MS / 1000} s). Puedes enviar cuando quieras.",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    } else if (estado.puedeMejorar) {
                        OutlinedButton(onClick = { Haptica.toque(vista); vm.mejorarPrecision() }, enabled = !enviando) { Text("Mejorar precisión") }
                    }
                    if (estado.soloAproximada) {
                        Text(
                            "La app solo tiene permiso de ubicación aproximada (unos 2 km). Para marcar el reporte donde estás, cambia el permiso de SIFEC a \"Precisa\" en los ajustes del teléfono.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        OutlinedButton(
                            onClick = {
                                Haptica.toque(vista)
                                abrirAjustes(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", contexto.packageName, null)))
                            },
                            enabled = !enviando,
                        ) { Text("Abrir ajustes de la app") }
                    }
                }
                EstadoGps.BUSCANDO -> Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text("Buscando tu ubicación...", style = MaterialTheme.typography.bodyMedium)
                }
                EstadoGps.SIN_PERMISO -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "No diste permiso de ubicación. Sin ella no se puede reportar: es la decisión del equipo para evitar reportes falsos (solo se reporta desde donde uno está).",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    OutlinedButton(onClick = { Haptica.toque(vista); pedirPermiso() }, enabled = !enviando) { Text("Dar permiso de ubicación") }
                }
                EstadoGps.UBICACION_APAGADA -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "La ubicación del teléfono está apagada. Préndela en los ajustes del sistema y vuelve a buscar.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        OutlinedButton(
                            onClick = { Haptica.toque(vista); abrirAjustes(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)) },
                            enabled = !enviando,
                        ) { Text("Activar la ubicación") }
                        OutlinedButton(onClick = { Haptica.toque(vista); vm.buscarUbicacion() }, enabled = !enviando) { Text("Volver a buscar") }
                    }
                }
                EstadoGps.SIN_SENAL -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "No se pudo obtener tu posición. Prueba a cielo abierto o cerca de una ventana y vuelve a intentar.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    OutlinedButton(onClick = { Haptica.toque(vista); vm.buscarUbicacion() }, enabled = !enviando) { Text("Volver a buscar mi ubicación") }
                }
                EstadoGps.FUERA_DEL_PERU -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Tu ubicación cae fuera del Perú: solo se reporta desde dentro del país.", style = MaterialTheme.typography.bodyMedium)
                    OutlinedButton(onClick = { Haptica.toque(vista); vm.buscarUbicacion() }, enabled = !enviando) { Text("Volver a buscar mi ubicación") }
                }
            }
        }
        estado.notaGps?.let { LineaFuente(it) }
        AvisoAccion(estado.errores["pos"])
    }
}

/** Tipos de incidente: el chip elegido cambia su glifo por una marca sobre el mismo disco de color; el subtipo del atasco entra y sale animado. */
@Composable
private fun BloqueTipo(estado: EstadoNuevo, vm: ReporteNuevoViewModel, enviando: Boolean) {
    val vista = LocalView.current
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("¿Qué estás viendo?", style = MaterialTheme.typography.titleMedium)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Comunidad.TIPOS.forEach { t ->
                val elegido = estado.tipo == t.id
                FilterChip(
                    selected = elegido,
                    enabled = !enviando,
                    onClick = { Haptica.toque(vista); vm.elegirTipo(t.id) },
                    label = { Text(t.etiqueta) },
                    leadingIcon = { MarcaTipo(t, elegido) },
                )
            }
        }
        AvisoAccion(estado.errores["tipo"])
        val tipo = Comunidad.TIPOS.firstOrNull { it.id == estado.tipo }
        val conSubtipos = tipo != null && tipo.subtipos.isNotEmpty()
        val memoria = remember { arrayOfNulls<TipoReporte>(1) }
        if (conSubtipos) memoria[0] = tipo
        AnimatedVisibility(visible = conSubtipos, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
            val t = memoria[0]
            if (t != null) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("¿Qué tan fuerte es el atasco?", style = MaterialTheme.typography.labelLarge)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        t.subtipos.forEach { (id, etiqueta) ->
                            val elegido = estado.subtipo == id
                            FilterChip(
                                selected = elegido,
                                enabled = !enviando,
                                onClick = { Haptica.toque(vista); vm.elegirSubtipo(id) },
                                label = { Text(etiqueta) },
                                leadingIcon = if (elegido) {
                                    { Icon(Icons.Filled.Check, contentDescription = "Elegido", modifier = Modifier.size(18.dp)) }
                                } else null,
                            )
                        }
                    }
                    AvisoAccion(estado.errores["subtipo"])
                }
            }
        }
    }
}

@Composable
private fun MarcaTipo(t: TipoReporte, elegido: Boolean) {
    AnimatedContent(
        targetState = elegido,
        transitionSpec = { fadeIn(tween(150, easing = FastOutSlowInEasing)) togetherWith fadeOut(tween(150, easing = FastOutSlowInEasing)) },
        label = "marcaTipo",
    ) { marcado ->
        if (marcado) {
            Box(Modifier.size(24.dp).background(Color(t.color), CircleShape), contentAlignment = Alignment.Center) {
                Icon(Icons.Filled.Check, contentDescription = "Elegido", tint = Color.White, modifier = Modifier.size(16.dp))
            }
        } else {
            GlifoReporte(t.id, tamano = 24)
        }
    }
}

/** Foto opcional: la vista previa entra con fundido y tiene su boton para quitarla. */
@Composable
private fun BloqueFoto(estado: EstadoNuevo, vm: ReporteNuevoViewModel, enviando: Boolean, onTomar: () -> Unit, onElegir: () -> Unit) {
    val vista = LocalView.current
    val contexto = LocalContext.current
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Foto (opcional, cámara o galería)", style = MaterialTheme.typography.titleMedium)
        AnimatedContent(
            targetState = estado.fotoUri,
            transitionSpec = {
                (fadeIn(tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing)) togetherWith fadeOut(tween(150, easing = FastOutSlowInEasing)))
                    .using(SizeTransform(clip = false))
            },
            label = "foto",
        ) { uri ->
            if (uri != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    val peticion = remember(uri) { ImageRequest.Builder(contexto).data(uri).crossfade(Transiciones.APARECER_MS).build() }
                    AsyncImage(
                        model = peticion, contentDescription = "Vista previa de tu foto", contentScale = ContentScale.Crop,
                        modifier = Modifier.size(96.dp).clip(RoundedCornerShape(10.dp)),
                    )
                    Spacer(Modifier.width(12.dp))
                    OutlinedButton(onClick = { Haptica.toque(vista); vm.ponerFoto(null) }, enabled = !enviando) {
                        Icon(Icons.Filled.Close, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Quitar")
                    }
                }
            } else {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    OutlinedButton(onClick = { Haptica.toque(vista); onTomar() }, enabled = !enviando) { Text("Tomar foto") }
                    OutlinedButton(onClick = { Haptica.toque(vista); onElegir() }, enabled = !enviando) { Text("Elegir de la galería") }
                }
            }
        }
        LineaFuente("La foto se reduce a ${Comunidad.LADO_FOTO} px y se sube sin datos de ubicación.")
    }
}

/** Aviso de la ultima accion (entra y sale animado) justo encima del boton de enviar. */
@Composable
private fun BloqueEnviar(estado: EstadoNuevo, vm: ReporteNuevoViewModel, enviando: Boolean, volver: () -> Unit) {
    val vista = LocalView.current
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        LineaFuente(Comunidad.AVISO_REPORTE)
        AvisoAccion(estado.aviso)
        Button(
            onClick = { Haptica.toque(vista); vm.enviar() },
            enabled = !enviando && estado.gps != EstadoGps.BUSCANDO,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Enviar reporte")
        }
        LineaFuente("Máximo ${Comunidad.MAX_REPORTES_HORA} reportes por hora. Se publica tu reporte, no tu nombre ni tu correo; la ubicación es la del reporte, no la tuya en el tiempo.")
        TextButton(onClick = { Haptica.toque(vista); volver() }, enabled = !enviando) { Text("Cancelar") }
    }
}

/**
 * Velo sobre el formulario mientras se envia: fondo translucido que absorbe los toques, tarjeta con el
 * paso en curso y barra indeterminada. Recuerda el ultimo paso para que el texto no cambie al cerrarse.
 */
@Composable
private fun BoxScope.VeloEnvio(paso: String?) {
    val memoria = remember { arrayOfNulls<String>(1) }
    if (paso != null) memoria[0] = paso
    AnimatedVisibility(
        visible = paso != null,
        enter = fadeIn(tween(200, easing = FastOutSlowInEasing)),
        exit = fadeOut(tween(200, easing = FastOutSlowInEasing)),
        modifier = Modifier.matchParentSize(),
    ) {
        val texto = if (memoria[0] == "foto") "Subiendo la foto" else "Enviando el reporte"
        Box(
            Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.72f))
                .pointerInput(Unit) {
                    awaitPointerEventScope { while (true) { awaitPointerEvent().changes.forEach { it.consume() } } }
                },
            contentAlignment = Alignment.Center,
        ) {
            Card(
                shape = MaterialTheme.shapes.medium,
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                border = bordeTarjeta(),
            ) {
                Column(Modifier.padding(20.dp).width(260.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(texto, style = MaterialTheme.typography.titleMedium)
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                    LineaFuente("Suele tardar unos segundos.")
                }
            }
        }
    }
}
