package pe.simpac.app.ui.comunidad

import android.Manifest
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import pe.simpac.app.data.EstadoSesion
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.ui.componentes.Cargando
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.PieReferencial
import java.util.Locale

/** Formulario "Reportar incidente" (pages/ReporteNuevo.jsx). Exige sesion y ubicacion GPS real. */
@Composable
fun ReporteNuevoScreen(volver: () -> Unit, abrirReporte: (String) -> Unit, irCuenta: () -> Unit, vm: ReporteNuevoViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val sesion by estadoSesion()
    val contexto = LocalContext.current

    LaunchedEffect(estado.creadoId) { estado.creadoId?.let { abrirReporte(it) } }
    LaunchedEffect(sesion) { if (sesion is EstadoSesion.ConSesion) vm.buscarUbicacion() }

    val pedirUbicacion = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { vm.buscarUbicacion() }
    var uriCamara by remember { mutableStateOf<Uri?>(null) }
    val tomarFoto = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok -> if (ok) vm.ponerFoto(uriCamara) }
    val pedirCamara = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) { val u = Fotos.uriParaCamara(contexto); uriCamara = u; tomarFoto.launch(u) }
    }
    val elegirFoto = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri -> if (uri != null) vm.ponerFoto(uri) }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = volver) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver a Comunidad") }
            Text("Reportar incidente", style = MaterialTheme.typography.headlineMedium)
        }
        when (sesion) {
            is EstadoSesion.Cargando -> Cargando("Revisando tu sesión...")
            is EstadoSesion.SinSesion -> {
                EntraPara("reportar", irCuenta)
                Text(
                    "Los reportes se hacen desde donde estás (ubicación GPS), con el tipo de incidente, una descripción corta y una foto si quieres. Duran ${Comunidad.HORAS_VIGENCIA} horas y la comunidad los vota.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            is EstadoSesion.ConSesion -> {
                Text("Tu ubicación", style = MaterialTheme.typography.titleMedium)
                when (estado.gps) {
                    EstadoGps.LISTA -> Text(
                        "Ubicación lista (${String.format(Locale.US, "%.4f, %.4f", estado.lat, estado.lon)}). El reporte se marcará ahí.",
                        style = MaterialTheme.typography.bodyMedium, color = Color(0xFF166534),
                    )
                    EstadoGps.BUSCANDO -> Text("Buscando tu ubicación...", style = MaterialTheme.typography.bodyMedium)
                    EstadoGps.SIN_PERMISO -> {
                        Text(
                            "No diste permiso de ubicación. Sin ella no se puede reportar: es la decisión del equipo para evitar reportes falsos (solo se reporta desde donde uno está).",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        OutlinedButton(onClick = { pedirUbicacion.launch(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION)) }) { Text("Dar permiso de ubicación") }
                    }
                    EstadoGps.SIN_SENAL -> {
                        Text("No se pudo obtener tu ubicación. Revisa que el GPS esté prendido y vuelve a intentar.", style = MaterialTheme.typography.bodyMedium)
                        OutlinedButton(onClick = { vm.buscarUbicacion() }) { Text("Volver a buscar mi ubicación") }
                    }
                    EstadoGps.FUERA_DEL_PERU -> {
                        Text("Tu ubicación cae fuera del Perú: solo se reporta desde dentro del país.", style = MaterialTheme.typography.bodyMedium)
                        OutlinedButton(onClick = { vm.buscarUbicacion() }) { Text("Volver a buscar mi ubicación") }
                    }
                }
                estado.errores["pos"]?.let { AvisoAccion(it) }

                Text("¿Qué estás viendo?", style = MaterialTheme.typography.titleMedium)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Comunidad.TIPOS.forEach { t ->
                        FilterChip(
                            selected = estado.tipo == t.id,
                            onClick = { vm.elegirTipo(t.id) },
                            label = { Text(t.etiqueta) },
                            leadingIcon = { GlifoReporte(t.id, tamano = 24) },
                        )
                    }
                }
                estado.errores["tipo"]?.let { AvisoAccion(it) }
                val tipo = Comunidad.TIPOS.firstOrNull { it.id == estado.tipo }
                if (tipo != null && tipo.subtipos.isNotEmpty()) {
                    Text("¿Qué tan fuerte es el atasco?", style = MaterialTheme.typography.labelLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        tipo.subtipos.forEach { (id, etiqueta) ->
                            FilterChip(selected = estado.subtipo == id, onClick = { vm.elegirSubtipo(id) }, label = { Text(etiqueta) })
                        }
                    }
                    estado.errores["subtipo"]?.let { AvisoAccion(it) }
                }

                OutlinedTextField(
                    value = estado.descripcion,
                    onValueChange = { vm.cambiarDescripcion(it) },
                    label = { Text("Cuéntalo en pocas palabras (opcional)") },
                    placeholder = { Text("Ej.: la pista está anegada frente al mercado, pasan solo camionetas.") },
                    minLines = 3,
                    isError = estado.errores["descripcion"] != null,
                    supportingText = {
                        val n = estado.descripcion.trim().length
                        Text(estado.errores["descripcion"] ?: "$n/${Comunidad.MAX_DESCRIPCION}")
                    },
                    modifier = Modifier.fillMaxWidth(),
                )

                Text("Foto (opcional, cámara o galería)", style = MaterialTheme.typography.titleMedium)
                if (estado.fotoUri != null) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        AsyncImage(
                            model = estado.fotoUri, contentDescription = "Vista previa de tu foto", contentScale = ContentScale.Crop,
                            modifier = Modifier.size(96.dp).clip(RoundedCornerShape(10.dp)),
                        )
                        Spacer(Modifier.width(12.dp))
                        OutlinedButton(onClick = { vm.ponerFoto(null) }) { Text("Quitar") }
                    }
                } else {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = { pedirCamara.launch(Manifest.permission.CAMERA) }) { Text("Tomar foto") }
                        OutlinedButton(onClick = { elegirFoto.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }) { Text("Elegir de la galería") }
                    }
                }
                LineaFuente("La foto se reduce a ${Comunidad.LADO_FOTO} px y se sube sin datos de ubicación.")

                LineaFuente(Comunidad.AVISO_REPORTE)
                AvisoAccion(estado.aviso)
                Button(
                    onClick = { vm.enviar() },
                    enabled = estado.enviando == null && estado.gps != EstadoGps.BUSCANDO,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(when (estado.enviando) { "foto" -> "Subiendo la foto..."; "reporte" -> "Enviando..."; else -> "Enviar reporte" })
                }
                LineaFuente("Máximo ${Comunidad.MAX_REPORTES_HORA} reportes por hora. Se publica tu reporte, no tu nombre ni tu correo; la ubicación es la del reporte, no la tuya en el tiempo.")
                TextButton(onClick = volver) { Text("Cancelar") }
            }
        }
        PieReferencial()
        Spacer(Modifier.height(8.dp))
    }
}
