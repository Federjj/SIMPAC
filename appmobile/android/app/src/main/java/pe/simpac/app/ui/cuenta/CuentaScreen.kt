package pe.simpac.app.ui.cuenta

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.BuildConfig
import pe.simpac.app.data.EstadoSesion
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.push.PushSimpac
import pe.simpac.app.ui.Intents
import pe.simpac.app.ui.componentes.Cargando
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.Seccion
import pe.simpac.app.ui.comunidad.AvisoAccion
import pe.simpac.app.ui.comunidad.estadoSesion

/**
 * Pestana Cuenta: sin sesion, Entrar / Crear cuenta / Olvide mi contrasena (Supabase Auth por correo
 * y contrasena, nativo); con sesion, el perfil (nombre, correo, reputacion), Mis reportes y cerrar
 * sesion. Debajo, los ajustes (departamento, API, web, notificaciones) y "Acerca de".
 * Solo se piden correo, contrasena y un nombre para mostrar; nada mas se guarda.
 */
@Composable
fun CuentaScreen(abrirReporte: (String) -> Unit = {}, vm: CuentaViewModel = viewModel(), ajustesVm: AjustesViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val sesion by estadoSesion()
    LaunchedEffect(sesion) { if (sesion is EstadoSesion.ConSesion) vm.cargarPerfil() }
    LaunchedEffect(estado.aviso) { if (estado.aviso != null) { kotlinx.coroutines.delay(8_000); vm.limpiarAviso() } }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Cuenta", style = MaterialTheme.typography.headlineMedium)
        when (val s = sesion) {
            is EstadoSesion.Cargando -> Cargando("Revisando tu sesión...")
            is EstadoSesion.SinSesion -> Acceso(estado, vm)
            is EstadoSesion.ConSesion -> Perfil(s, estado, vm, abrirReporte)
        }
        AjustesYAcerca(ajustesVm)
        PieReferencial()
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun Acceso(estado: EstadoCuenta, vm: CuentaViewModel) {
    val registro = estado.modo == ModoCuenta.REGISTRO
    if (estado.modo == ModoCuenta.CONFIRMAR && estado.confirmacion != null) {
        Seccion(estado.confirmacion.first) {
            Text(estado.confirmacion.second, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { vm.cambiarModo(ModoCuenta.ENTRAR) }) { Text("Volver a entrar") }
        }
        return
    }
    Seccion("Tu cuenta de SIMPAC") {
        Text(Comunidad.POR_QUE_CUENTA, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(10.dp))
        if (estado.modo == ModoCuenta.RECUPERAR) {
            Text("Olvidé mi contraseña", style = MaterialTheme.typography.titleMedium)
            LineaFuente("Te enviamos un enlace por correo para elegir una nueva.")
            Spacer(Modifier.height(6.dp))
            CampoCorreo(estado, vm)
            AvisoAccion(estado.aviso)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.enviar() }, enabled = !estado.enviando) { Text(if (estado.enviando) "Enviando..." else "Enviar enlace") }
                TextButton(onClick = { vm.cambiarModo(ModoCuenta.ENTRAR) }) { Text("Cancelar") }
            }
            return@Seccion
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = !registro, onClick = { vm.cambiarModo(ModoCuenta.ENTRAR) }, label = { Text("Entrar") })
            FilterChip(selected = registro, onClick = { vm.cambiarModo(ModoCuenta.REGISTRO) }, label = { Text("Crear cuenta") })
        }
        Spacer(Modifier.height(6.dp))
        if (registro) {
            OutlinedTextField(
                value = estado.nombre, onValueChange = { vm.cambiarNombre(it) },
                label = { Text("Nombre para mostrar") }, placeholder = { Text("Ej.: Rosa de Baños del Inca") },
                singleLine = true, isError = estado.errores["nombre"] != null,
                supportingText = estado.errores["nombre"]?.let { { Text(it) } },
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
            modifier = Modifier.fillMaxWidth(),
        )
        AvisoAccion(estado.aviso)
        Button(onClick = { vm.enviar() }, enabled = !estado.enviando, modifier = Modifier.fillMaxWidth()) {
            Text(if (estado.enviando) "Un momento..." else if (registro) "Crear cuenta" else "Entrar")
        }
        if (!registro) TextButton(onClick = { vm.cambiarModo(ModoCuenta.RECUPERAR) }) { Text("Olvidé mi contraseña") }
        if (registro) LineaFuente("Después de crear la cuenta te llegará un correo para confirmarla. No guardamos más datos que tu correo y ese nombre.")
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
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun Perfil(s: EstadoSesion.ConSesion, estado: EstadoCuenta, vm: CuentaViewModel, abrirReporte: (String) -> Unit) {
    Seccion(estado.perfil?.nombre ?: s.nombre ?: "Sin nombre") {
        Text(s.email ?: "", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(6.dp))
        Text("Reputación: ${estado.perfil?.reputacion ?: 0}", style = MaterialTheme.typography.bodyLarge)
        LineaFuente("Suma de los votos que recibieron tus reportes (a favor menos en contra).")
        estado.errorPerfil?.let { LineaFuente("No se pudo leer tu perfil ($it).") }
        Spacer(Modifier.height(4.dp))
        LineaFuente(Comunidad.POR_QUE_CUENTA)
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { vm.salir() }, enabled = !estado.saliendo) { Text(if (estado.saliendo) "Cerrando..." else "Cerrar sesión") }
            TextButton(onClick = { vm.cargarPerfil() }, enabled = !estado.cargandoPerfil) { Text("Actualizar") }
        }
    }
    Seccion("Mis reportes") {
        when {
            estado.cargandoPerfil && estado.misReportes == null -> Text("Cargando...", style = MaterialTheme.typography.bodyMedium)
            estado.errorReportes != null -> Text("No se pudieron leer tus reportes (${estado.errorReportes}).", style = MaterialTheme.typography.bodyMedium)
            estado.misReportes?.isEmpty() == true -> Text("Todavía no has hecho reportes.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> estado.misReportes?.forEachIndexed { i, r ->
                if (i > 0) HorizontalDivider(Modifier.padding(vertical = 6.dp))
                val vive = Comunidad.vigente(r)
                Text(Comunidad.nombreReporte(r), style = MaterialTheme.typography.titleSmall)
                LineaFuente("${Tiempo.haceTexto(Tiempo.parsearMs(r.creado_en))} · ${if (vive) "vigente" else "vencido"}")
                if (!r.descripcion.isNullOrBlank()) Text(r.descripcion, style = MaterialTheme.typography.bodyMedium, maxLines = 2)
                LineaFuente("${Comunidad.textoEstado(r.estado)} · ${r.likes} a favor · ${r.dislikes} en contra")
                if (vive) TextButton(onClick = { abrirReporte(r.id) }) { Text("Ver") }
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
    val c = conf ?: return

    var menuAbierto by remember { mutableStateOf(false) }

    // Android 13+: el permiso de notificaciones se pide al prender el interruptor
    val pedirNotificaciones = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) vm.cambiarNotificaciones(true)
    }
    fun prender() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !PushSimpac.notificacionesPermitidas(contexto)) {
            pedirNotificaciones.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else vm.cambiarNotificaciones(true)
    }

    LaunchedEffect(mensaje) { if (mensaje != null) { kotlinx.coroutines.delay(6_000); vm.limpiarMensaje() } }

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
                Switch(checked = c.notificaciones, onCheckedChange = { if (it) prender() else vm.cambiarNotificaciones(false) })
            }
            if (c.notificaciones && !PushSimpac.notificacionesPermitidas(contexto)) {
                LineaFuente("Android tiene las notificaciones de SIMPAC apagadas: actívalas en Ajustes del teléfono.")
            }
        }
    }

    Seccion("Ajustes") {
        Text("Departamento", style = MaterialTheme.typography.labelLarge)
        OutlinedButton(onClick = { menuAbierto = true }) { Text(c.departamento) }
        DropdownMenu(expanded = menuAbierto, onDismissRequest = { menuAbierto = false }) {
            Departamentos.TODOS.forEach { d ->
                DropdownMenuItem(text = { Text(d.nombre) }, onClick = { menuAbierto = false; vm.guardarDepartamento(d.nombre) })
            }
        }
        LineaFuente(if (c.usarGps) "Con tu ubicación activa, la zona se detecta sola; al elegir aquí se usa este departamento." else "Zona para el inicio, las alertas y las notificaciones.")
        mensaje?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary) }
        Spacer(Modifier.height(6.dp))
        TextButton(onClick = { Intents.abrirNavegador(contexto, c.webUrl.trimEnd('/') + "/cuenta") }) { Text("Abrir mi cuenta en la web") }
    }

    Seccion("Acerca de SIMPAC") {
        Text("Versión ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}). Proyecto académico que reúne datos hidrometeorológicos oficiales del Perú para El Niño, con foco en Cajamarca. No es una app oficial de SENAMHI, ANA ni INDECI.", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(6.dp))
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
        TextButton(onClick = { Intents.abrirNavegador(contexto, "https://github.com/Federjj/SIMPAC") }) { Text("Código del proyecto en GitHub") }
    }
}
