package pe.simpac.app.ui.cuenta

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.EaseOutCubic
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.delay
import pe.simpac.app.BuildConfig
import pe.simpac.app.data.EstadoSesion
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.push.PushSimpac
import pe.simpac.app.ui.Intents
import pe.simpac.app.ui.componentes.AparecerEscalonado
import pe.simpac.app.ui.componentes.Cargando
import pe.simpac.app.ui.componentes.ContadorAnimado
import pe.simpac.app.ui.componentes.ContenidoConEstado
import pe.simpac.app.ui.componentes.EsqueletoTarjeta
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.LocalAvisador
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.Seccion
import pe.simpac.app.ui.componentes.Transiciones
import pe.simpac.app.ui.componentes.presionable
import pe.simpac.app.ui.comunidad.AvisoAccion
import pe.simpac.app.ui.comunidad.estadoSesion

/**
 * Pestana Cuenta: sin sesion, Entrar / Crear cuenta / Olvide mi contrasena (Supabase Auth por correo
 * y contrasena, nativo); con sesion, el perfil (nombre, correo, reputacion), Mis reportes y cerrar
 * sesion. Debajo, los ajustes (departamento, API, web, notificaciones) y "Acerca de".
 * Solo se piden correo, contrasena y un nombre para mostrar; nada mas se guarda.
 * Los modos se cruzan con fundido y un deslizamiento corto; el perfil carga con esqueleto; los
 * mensajes de los ajustes salen por el snackbar global; las fuentes de "Acerca de" van plegadas.
 */
@Composable
fun CuentaScreen(abrirReporte: (String) -> Unit = {}, vm: CuentaViewModel = viewModel(), ajustesVm: AjustesViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val sesion by estadoSesion()
    val vista = LocalView.current
    val sesionAnterior = remember { arrayOf<EstadoSesion?>(null) }
    LaunchedEffect(sesion) {
        if (sesion is EstadoSesion.ConSesion) {
            if (sesionAnterior[0] is EstadoSesion.SinSesion) Haptica.confirmar(vista)
            vm.cargarPerfil()
        }
        sesionAnterior[0] = sesion
    }
    // El error de la ultima accion se queda 6 s (aunque se cambie de modo) salvo que la persona escriba
    LaunchedEffect(estado.aviso) {
        if (estado.aviso != null) { Haptica.rechazar(vista); delay(6_000); vm.limpiarAviso() }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Cuenta", style = MaterialTheme.typography.headlineMedium)
        AparecerEscalonado(0) {
            when (val s = sesion) {
                is EstadoSesion.Cargando -> Cargando("Revisando tu sesión...")
                is EstadoSesion.SinSesion -> Acceso(estado, vm)
                is EstadoSesion.ConSesion -> Perfil(s, estado, vm, abrirReporte)
            }
        }
        AjustesYAcerca(ajustesVm)
        PieReferencial()
        Spacer(Modifier.height(8.dp))
    }
}

private enum class VistaAcceso { FORMULARIO, RECUPERAR, CONFIRMAR }

/** Entrar / Crear cuenta, Olvide mi contrasena y Revisa tu correo, cruzados con fundido y un deslizamiento de un octavo del ancho. */
@Composable
private fun Acceso(estado: EstadoCuenta, vm: CuentaViewModel) {
    val pantalla = when (estado.modo) {
        ModoCuenta.ENTRAR, ModoCuenta.REGISTRO -> VistaAcceso.FORMULARIO
        ModoCuenta.RECUPERAR -> VistaAcceso.RECUPERAR
        ModoCuenta.CONFIRMAR -> if (estado.confirmacion != null) VistaAcceso.CONFIRMAR else VistaAcceso.FORMULARIO
    }
    AnimatedContent(
        targetState = pantalla,
        transitionSpec = {
            val adelante = targetState.ordinal >= initialState.ordinal
            val entra = fadeIn(tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing)) +
                slideInHorizontally(tween(Transiciones.APARECER_MS, easing = EaseOutCubic)) { if (adelante) it / 8 else -it / 8 }
            val sale = fadeOut(tween(150, easing = FastOutSlowInEasing)) +
                slideOutHorizontally(tween(150, easing = FastOutSlowInEasing)) { if (adelante) -it / 8 else it / 8 }
            (entra togetherWith sale).using(SizeTransform(clip = false))
        },
        label = "acceso",
    ) { p ->
        when (p) {
            VistaAcceso.CONFIRMAR -> Confirmacion(estado, vm)
            VistaAcceso.RECUPERAR -> Recuperar(estado, vm)
            VistaAcceso.FORMULARIO -> Formulario(estado, vm)
        }
    }
}

@Composable
private fun Confirmacion(estado: EstadoCuenta, vm: CuentaViewModel) {
    val vista = LocalView.current
    Seccion(estado.confirmacion?.first ?: "Revisa tu correo") {
        Text(estado.confirmacion?.second ?: "", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = { Haptica.toque(vista); vm.cambiarModo(ModoCuenta.ENTRAR) }) { Text("Volver a entrar") }
    }
}

@Composable
private fun Recuperar(estado: EstadoCuenta, vm: CuentaViewModel) {
    val vista = LocalView.current
    Seccion("Tu cuenta de SIMPAC") {
        Text(Comunidad.POR_QUE_CUENTA, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(10.dp))
        Text("Olvidé mi contraseña", style = MaterialTheme.typography.titleMedium)
        LineaFuente("Te enviamos un enlace por correo para elegir una nueva.")
        Spacer(Modifier.height(6.dp))
        CampoCorreo(estado, vm)
        AvisoAccion(estado.aviso)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            BotonPrincipal(texto = "Enviar enlace", ocupado = "Enviando...", enviando = estado.enviando, onClick = { Haptica.toque(vista); vm.enviar() })
            TextButton(onClick = { Haptica.toque(vista); vm.cambiarModo(ModoCuenta.ENTRAR) }, enabled = !estado.enviando) { Text("Cancelar") }
        }
    }
}

@Composable
private fun Formulario(estado: EstadoCuenta, vm: CuentaViewModel) {
    val vista = LocalView.current
    val registro = estado.modo == ModoCuenta.REGISTRO
    Seccion("Tu cuenta de SIMPAC") {
        Text(Comunidad.POR_QUE_CUENTA, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ChipModo("Entrar", seleccionado = !registro) { vm.cambiarModo(ModoCuenta.ENTRAR) }
            ChipModo("Crear cuenta", seleccionado = registro) { vm.cambiarModo(ModoCuenta.REGISTRO) }
        }
        Spacer(Modifier.height(6.dp))
        AnimatedVisibility(visible = registro, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
            OutlinedTextField(
                value = estado.nombre, onValueChange = { vm.cambiarNombre(it) },
                label = { Text("Nombre para mostrar") }, placeholder = { Text("Ej.: Rosa de Baños del Inca") },
                singleLine = true, isError = estado.errores["nombre"] != null,
                supportingText = estado.errores["nombre"]?.let { { Text(it) } },
                enabled = !estado.enviando,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        CampoCorreo(estado, vm)
        OutlinedTextField(
            value = estado.password, onValueChange = { vm.cambiarPassword(it) },
            label = { Text("Contraseña") }, placeholder = { Text(if (registro) "Al menos 6 caracteres" else "") },
            singleLine = true, visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            isError = estado.errores["password"] != null,
            supportingText = estado.errores["password"]?.let { { Text(it) } },
            enabled = !estado.enviando,
            modifier = Modifier.fillMaxWidth(),
        )
        AvisoAccion(estado.aviso)
        BotonPrincipal(
            texto = if (registro) "Crear cuenta" else "Entrar",
            ocupado = "Un momento...",
            enviando = estado.enviando,
            onClick = { Haptica.toque(vista); vm.enviar() },
            modifier = Modifier.fillMaxWidth(),
        )
        AnimatedVisibility(visible = !registro, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
            TextButton(onClick = { Haptica.toque(vista); vm.cambiarModo(ModoCuenta.RECUPERAR) }, enabled = !estado.enviando) { Text("Olvidé mi contraseña") }
        }
        AnimatedVisibility(visible = registro, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
            LineaFuente("Después de crear la cuenta te llegará un correo para confirmarla. No guardamos más datos que tu correo y ese nombre.")
        }
    }
}

/** Chip Entrar / Crear cuenta: el elegido lleva una marca ademas del color. */
@Composable
private fun ChipModo(texto: String, seleccionado: Boolean, onClick: () -> Unit) {
    val vista = LocalView.current
    FilterChip(
        selected = seleccionado,
        onClick = { Haptica.toque(vista); onClick() },
        label = { Text(texto) },
        leadingIcon = if (seleccionado) {
            { Icon(Icons.Filled.Check, contentDescription = null, modifier = Modifier.size(18.dp)) }
        } else null,
    )
}

/** Boton principal del formulario: se encoge al presionar y, mientras envia, muestra una rueda en linea y "Un momento..." sin perder el color. */
@Composable
private fun BotonPrincipal(texto: String, ocupado: String, enviando: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val fuente = remember { MutableInteractionSource() }
    val colores = if (enviando) {
        ButtonDefaults.buttonColors(
            disabledContainerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.85f),
            disabledContentColor = MaterialTheme.colorScheme.onPrimary,
        )
    } else {
        ButtonDefaults.buttonColors()
    }
    Button(onClick = onClick, enabled = !enviando, colors = colores, interactionSource = fuente, modifier = modifier.presionable(fuente)) {
        AnimatedVisibility(visible = enviando) {
            Row {
                CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp, color = LocalContentColor.current)
                Spacer(Modifier.width(8.dp))
            }
        }
        Text(if (enviando) ocupado else texto)
    }
}

@Composable
private fun CampoCorreo(estado: EstadoCuenta, vm: CuentaViewModel) {
    OutlinedTextField(
        value = estado.email, onValueChange = { vm.cambiarEmail(it) },
        label = { Text("Correo") }, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
        isError = estado.errores["email"] != null,
        supportingText = estado.errores["email"]?.let { { Text(it) } },
        enabled = !estado.enviando,
        modifier = Modifier.fillMaxWidth(),
    )
}

/** Perfil y Mis reportes: esqueleto de dos tarjetas el primer cargado; despues, "Actualizar" recarga sin tapar nada. */
@Composable
private fun Perfil(s: EstadoSesion.ConSesion, estado: EstadoCuenta, vm: CuentaViewModel, abrirReporte: (String) -> Unit) {
    val vista = LocalView.current
    ContenidoConEstado(
        cargando = estado.cargandoPerfil && estado.perfil == null && estado.misReportes == null,
        error = null,
        onReintentar = { vm.cargarPerfil() },
        modifier = Modifier.fillMaxWidth(),
        esqueleto = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                EsqueletoTarjeta(lineas = 3)
                EsqueletoTarjeta(lineas = 4)
            }
        },
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Seccion(
                estado.perfil?.nombre ?: s.nombre ?: "Sin nombre",
                accion = {
                    TextButton(onClick = { Haptica.toque(vista); vm.cargarPerfil() }, enabled = !estado.cargandoPerfil) { Text("Actualizar") }
                },
            ) {
                Text(s.email ?: "", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Reputación: ", style = MaterialTheme.typography.bodyLarge)
                    ContadorAnimado(estado.perfil?.reputacion ?: 0, style = MaterialTheme.typography.bodyLarge)
                }
                LineaFuente("Suma de los votos que recibieron tus reportes (a favor menos en contra).")
                estado.errorPerfil?.let { LineaFuente("No se pudo leer tu perfil ($it).") }
                Spacer(Modifier.height(4.dp))
                LineaFuente(Comunidad.POR_QUE_CUENTA)
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = { Haptica.toque(vista); vm.salir() }, enabled = !estado.saliendo) {
                    AnimatedVisibility(visible = estado.saliendo) {
                        Row {
                            CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp, color = LocalContentColor.current)
                            Spacer(Modifier.width(8.dp))
                        }
                    }
                    Text(if (estado.saliendo) "Cerrando..." else "Cerrar sesión")
                }
            }
            Seccion("Mis reportes") {
                val lista = estado.misReportes
                when {
                    estado.errorReportes != null -> Text("No se pudieron leer tus reportes (${estado.errorReportes}).", style = MaterialTheme.typography.bodyMedium)
                    lista.isNullOrEmpty() -> Text("Todavía no has hecho reportes.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    else -> lista.forEachIndexed { i, r ->
                        if (i > 0) HorizontalDivider(Modifier.padding(vertical = 6.dp))
                        val vive = Comunidad.vigente(r)
                        Text(Comunidad.nombreReporte(r), style = MaterialTheme.typography.titleSmall)
                        LineaFuente("${Tiempo.haceTexto(Tiempo.parsearMs(r.creado_en))} · ${if (vive) "vigente" else "vencido"}")
                        if (!r.descripcion.isNullOrBlank()) Text(r.descripcion, style = MaterialTheme.typography.bodyMedium, maxLines = 2)
                        LineaFuente("${Comunidad.textoEstado(r.estado)} · ${r.likes} a favor · ${r.dislikes} en contra")
                        if (vive) {
                            TextButton(onClick = { Haptica.toque(vista); abrirReporte(r.id) }) {
                                Text("Ver")
                                Spacer(Modifier.width(4.dp))
                                Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null, modifier = Modifier.size(18.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}

/** Ajustes (departamento y notificaciones) y "Acerca de". Las direcciones de la API y la web vienen fijas del build. */
@Composable
private fun AjustesYAcerca(vm: AjustesViewModel) {
    val conf by vm.conf.collectAsStateWithLifecycle()
    val mensaje by vm.mensaje.collectAsStateWithLifecycle()
    val contexto = LocalContext.current
    val vista = LocalView.current
    val avisador = LocalAvisador.current
    val c = conf ?: return

    var menuAbierto by remember { mutableStateOf(false) }
    var fuentesAbiertas by rememberSaveable { mutableStateOf(false) }

    // Android 13+: el permiso de notificaciones se pide al prender el interruptor
    val pedirNotificaciones = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) vm.cambiarNotificaciones(true)
    }
    fun prender() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !PushSimpac.notificacionesPermitidas(contexto)) {
            pedirNotificaciones.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else vm.cambiarNotificaciones(true)
    }

    // Los mensajes de los ajustes (guardado, error de Firebase...) salen por el snackbar global
    LaunchedEffect(mensaje) {
        mensaje?.let { avisador.avisar(it, duracion = SnackbarDuration.Long); vm.limpiarMensaje() }
    }

    AparecerEscalonado(1) {
        Seccion("Notificaciones de tu zona") {
            if (!vm.pushDisponible) {
                Text("Notificaciones no configuradas en esta instalación.", style = MaterialTheme.typography.bodyLarge)
                LineaFuente("Falta el archivo google-services.json de Firebase al compilar la app (ver appmobile/README.md).")
            } else {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Avisarme si ${c.departamento} entra en alerta o emergencia", style = MaterialTheme.typography.bodyLarge)
                        LineaFuente("Solo niveles alerta y emergencia oficiales, y cuando vuelve la calma. Nunca por lluvia medida ni avisos amarillos.")
                    }
                    Spacer(Modifier.width(8.dp))
                    Switch(
                        checked = c.notificaciones,
                        onCheckedChange = { Haptica.toque(vista); if (it) prender() else vm.cambiarNotificaciones(false) },
                        thumbContent = if (c.notificaciones) {
                            { Icon(Icons.Filled.Check, contentDescription = null, modifier = Modifier.size(SwitchDefaults.IconSize)) }
                        } else null,
                    )
                }
                if (c.notificaciones && !PushSimpac.notificacionesPermitidas(contexto)) {
                    LineaFuente("Android tiene las notificaciones de SIMPAC apagadas: actívalas en Ajustes del teléfono.")
                }
            }
        }
    }

    AparecerEscalonado(2) {
        Seccion("Ajustes") {
            Text("Departamento", style = MaterialTheme.typography.labelLarge)
            Box {
                OutlinedButton(onClick = { Haptica.toque(vista); menuAbierto = true }) {
                    Text(c.departamento)
                    Spacer(Modifier.width(4.dp))
                    Icon(Icons.Filled.ArrowDropDown, contentDescription = null)
                }
                DropdownMenu(expanded = menuAbierto, onDismissRequest = { menuAbierto = false }) {
                    Departamentos.TODOS.forEach { d ->
                        DropdownMenuItem(
                            text = { Text(d.nombre) },
                            onClick = { menuAbierto = false; Haptica.toque(vista); vm.guardarDepartamento(d.nombre) },
                            trailingIcon = if (d.nombre == c.departamento) {
                                { Icon(Icons.Filled.Check, contentDescription = "Elegido", modifier = Modifier.size(18.dp)) }
                            } else null,
                        )
                    }
                }
            }
            LineaFuente(if (c.usarGps) "Con tu ubicación activa, la zona se detecta sola; al elegir aquí se usa este departamento." else "Zona para el inicio, las alertas y las notificaciones.")
            Spacer(Modifier.height(6.dp))
            TextButton(onClick = { Haptica.toque(vista); Intents.abrirNavegador(contexto, c.webUrl.trimEnd('/') + "/cuenta") }) { Text("Abrir mi cuenta en la web") }
        }
    }

    AparecerEscalonado(3) {
        Seccion("Acerca de SIMPAC") {
            Text("Versión ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}). Proyecto académico que reúne datos hidrometeorológicos oficiales del Perú para El Niño, con foco en Cajamarca. No es una app oficial de SENAMHI, ANA ni INDECI.", style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(6.dp))
            val giro by animateFloatAsState(if (fuentesAbiertas) 180f else 0f, tween(200, easing = FastOutSlowInEasing), label = "flechaFuentes")
            TextButton(onClick = { Haptica.toque(vista); fuentesAbiertas = !fuentesAbiertas }) {
                Text(if (fuentesAbiertas) "Ocultar fuentes y licencias" else "Ver fuentes y licencias")
                Spacer(Modifier.width(4.dp))
                Icon(Icons.Filled.KeyboardArrowDown, contentDescription = null, modifier = Modifier.rotate(giro))
            }
            AnimatedVisibility(visible = fuentesAbiertas, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
                Column {
                    Text("Fuentes", style = MaterialTheme.typography.labelLarge)
                    LineaFuente("SENAMHI: avisos meteorológicos, lluvia por estación, pronóstico por localidad y avisos hidrológicos (senamhi.gob.pe).")
                    LineaFuente("ANA: caudales y umbrales de ríos, trazo de los ríos (GeoSNIRH; RJ 056-2018-ANA y Carta Nacional del IGN).")
                    LineaFuente("ENFEN: comunicado oficial del estado de El Niño costero. IGP: ICEN. NOAA: RONI.")
                    LineaFuente("A dónde acudir: RENIPRESS de SUSALUD (ODC-By), padrón de comisarías del MININTER vía CENEPRED, bomberos del CGBVP, gob.pe.")
                    LineaFuente("Comunidad: reportes de las mismas personas que usan SIMPAC, validados con sus votos; no son información oficial.")
                    LineaFuente("Mapa base de la app y de la web: Stadia Maps, OpenMapTiles y OpenStreetMap (ODbL). Trazo del Mashcón: OpenStreetMap. Relieve de las zonas estimadas: Copernicus GLO-30.")
                    Spacer(Modifier.height(6.dp))
                    Text("Licencias de software", style = MaterialTheme.typography.labelLarge)
                    LineaFuente("Kotlin, Jetpack Compose, AndroidX, OkHttp, kotlinx.serialization, osmdroid, Coil (Apache 2.0); Firebase Cloud Messaging y Google Play Services (términos de Google).")
                }
            }
            TextButton(onClick = { Haptica.toque(vista); Intents.abrirNavegador(contexto, "https://github.com/Federjj/SIMPAC") }) { Text("Código del proyecto en GitHub") }
        }
    }
}
