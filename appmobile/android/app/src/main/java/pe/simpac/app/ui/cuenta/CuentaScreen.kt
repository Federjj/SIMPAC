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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.BuildConfig
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.push.PushSimpac
import pe.simpac.app.ui.Intents
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.Seccion

@Composable
fun CuentaScreen(abrirEnWeb: (String) -> Unit, vm: AjustesViewModel = viewModel()) {
    val conf by vm.conf.collectAsStateWithLifecycle()
    val mensaje by vm.mensaje.collectAsStateWithLifecycle()
    val contexto = LocalContext.current
    val c = conf ?: return

    var api by remember(c.apiUrl) { mutableStateOf(c.apiUrl) }
    var web by remember(c.webUrl) { mutableStateOf(c.webUrl) }
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

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Cuenta", style = MaterialTheme.typography.headlineMedium)
        Seccion("Tu cuenta de SIMPAC") {
            Text(
                "Las cuentas se manejan en la web de SIMPAC (crear cuenta, entrar, reportar, votar y chatear). " +
                    "Esta app no comparte la sesión de la web: si entras allá, tendrás que entrar también dentro del mapa de la app.",
                style = MaterialTheme.typography.bodyMedium,
            )
            Spacer(Modifier.height(8.dp))
            Button(onClick = { abrirEnWeb("/cuenta") }) { Text("Abrir mi cuenta en la web") }
        }

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
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(value = api, onValueChange = { api = it }, label = { Text("Dirección de la API") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(value = web, onValueChange = { web = it }, label = { Text("Dirección de la web") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            LineaFuente("Por defecto apuntan a la PC desde el emulador (10.0.2.2). En un teléfono, usa la IP de la PC o el dominio real.")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.guardarDirecciones(api, web) }) { Text("Guardar") }
                TextButton(onClick = { vm.restablecerDirecciones() }) { Text("Restablecer") }
            }
            mensaje?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary) }
        }

        Seccion("Acerca de SIMPAC") {
            Text("Versión ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}). Proyecto académico que reúne datos hidrometeorológicos oficiales del Perú para El Niño, con foco en Cajamarca. No es una app oficial de SENAMHI, ANA ni INDECI.", style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(6.dp))
            Text("Fuentes", style = MaterialTheme.typography.labelLarge)
            LineaFuente("SENAMHI: avisos meteorológicos, lluvia por estación, pronóstico por localidad y avisos hidrológicos (senamhi.gob.pe).")
            LineaFuente("ANA: caudales y umbrales de ríos, trazo de los ríos (GeoSNIRH; RJ 056-2018-ANA y Carta Nacional del IGN).")
            LineaFuente("ENFEN: comunicado oficial del estado de El Niño costero. IGP: ICEN. NOAA: RONI.")
            LineaFuente("A dónde acudir: RENIPRESS de SUSALUD (ODC-By), padrón de comisarías del MININTER vía CENEPRED, bomberos del CGBVP, gob.pe.")
            LineaFuente("Mapa base de la web: Stadia Maps y OpenStreetMap (ODbL).")
            Spacer(Modifier.height(6.dp))
            Text("Licencias de software", style = MaterialTheme.typography.labelLarge)
            LineaFuente("Kotlin, Jetpack Compose, AndroidX, OkHttp, kotlinx.serialization (Apache 2.0); Firebase Cloud Messaging y Google Play Services (términos de Google).")
            TextButton(onClick = { Intents.abrirNavegador(contexto, "https://github.com/Federjj/SIMPAC") }) { Text("Código del proyecto en GitHub") }
        }
        PieReferencial()
        Spacer(Modifier.height(8.dp))
    }
}
