package pe.simpac.app.ui.comunidad

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.EstadoSesion
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.ReporteOrdenado
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.componentes.LineaFuente

/** Estado de la sesion (data/Sesion.kt) para cualquier pantalla. */
@Composable
fun estadoSesion(): State<EstadoSesion> =
    (LocalContext.current.applicationContext as SimpacApp).contenedor.sesion.estado.collectAsState()

/** Glifo del tipo de reporte sobre un disco del color del tipo (misma idea que components/IconoReporte.jsx). */
@Composable
fun GlifoReporte(tipo: String?, modifier: Modifier = Modifier, tamano: Int = 36) {
    val t = Comunidad.tipo(tipo)
    Box(modifier.size(tamano.dp).background(Color(t.color), CircleShape).semantics { contentDescription = t.etiqueta }, contentAlignment = Alignment.Center) {
        Canvas(Modifier.size((tamano * 0.56f).dp)) {
            val w = size.width
            val h = size.height
            val blanco = Color.White
            val trazo = Stroke(width = w * 0.11f, cap = StrokeCap.Round)
            when (t.id) {
                "inundacion" -> for (y in listOf(0.35f, 0.65f)) {
                    val p = Path().apply {
                        moveTo(0f, h * y)
                        quadraticTo(w * 0.25f, h * (y - 0.2f), w * 0.5f, h * y)
                        quadraticTo(w * 0.75f, h * (y + 0.2f), w, h * y)
                    }
                    drawPath(p, blanco, style = trazo)
                }
                "huayco" -> drawPath(Path().apply { moveTo(w * 0.05f, h * 0.9f); lineTo(w * 0.42f, h * 0.15f); lineTo(w * 0.62f, h * 0.55f); lineTo(w * 0.75f, h * 0.4f); lineTo(w * 0.95f, h * 0.9f); close() }, blanco, style = trazo)
                "lluvia_intensa" -> {
                    drawPath(Path().apply { moveTo(w * 0.2f, h * 0.55f); quadraticTo(w * 0.1f, h * 0.2f, w * 0.4f, h * 0.25f); quadraticTo(w * 0.6f, h * 0.0f, w * 0.75f, h * 0.3f); quadraticTo(w, h * 0.3f, w * 0.85f, h * 0.55f); close() }, blanco, style = trazo)
                    for (x in listOf(0.3f, 0.52f, 0.74f)) drawLine(blanco, Offset(w * x, h * 0.7f), Offset(w * (x - 0.08f), h * 0.95f), trazo.width, StrokeCap.Round)
                }
                "via_bloqueada" -> {
                    drawCircle(blanco, radius = w * 0.4f, style = trazo)
                    drawLine(blanco, Offset(w * 0.22f, h * 0.22f), Offset(w * 0.78f, h * 0.78f), trazo.width, StrokeCap.Round)
                }
                "atasco" -> {
                    drawRoundRect(blanco, Offset(w * 0.08f, h * 0.35f), androidx.compose.ui.geometry.Size(w * 0.84f, h * 0.35f), androidx.compose.ui.geometry.CornerRadius(w * 0.1f), style = trazo)
                    drawPath(Path().apply { moveTo(w * 0.22f, h * 0.35f); lineTo(w * 0.32f, h * 0.12f); lineTo(w * 0.68f, h * 0.12f); lineTo(w * 0.78f, h * 0.35f) }, blanco, style = trazo)
                    drawCircle(blanco, radius = w * 0.09f, center = Offset(w * 0.28f, h * 0.8f))
                    drawCircle(blanco, radius = w * 0.09f, center = Offset(w * 0.72f, h * 0.8f))
                }
                "bache" -> {
                    drawCircle(blanco, radius = w * 0.42f, style = trazo)
                    drawCircle(blanco, radius = w * 0.14f)
                }
                "accidente" -> {
                    drawPath(Path().apply { moveTo(w * 0.5f, h * 0.08f); lineTo(w * 0.95f, h * 0.9f); lineTo(w * 0.05f, h * 0.9f); close() }, blanco, style = trazo)
                    drawLine(blanco, Offset(w * 0.5f, h * 0.38f), Offset(w * 0.5f, h * 0.62f), trazo.width, StrokeCap.Round)
                    drawCircle(blanco, radius = trazo.width * 0.6f, center = Offset(w * 0.5f, h * 0.77f))
                }
                else -> {
                    drawCircle(blanco, radius = trazo.width * 0.6f, center = Offset(w * 0.5f, h * 0.2f))
                    drawLine(blanco, Offset(w * 0.5f, h * 0.42f), Offset(w * 0.5f, h * 0.88f), trazo.width, StrokeCap.Round)
                }
            }
        }
    }
}

/** Foto del reporte desde la URL publica del bucket (Coil). */
@Composable
fun FotoReporte(url: String, nombre: String, alto: Int, modifier: Modifier = Modifier) {
    AsyncImage(
        model = url,
        contentDescription = "Foto del reporte: $nombre",
        contentScale = ContentScale.Crop,
        modifier = modifier.fillMaxWidth().height(alto.dp).clip(RoundedCornerShape(10.dp)),
    )
}

/**
 * Tarjeta de un reporte ciudadano (components/TarjetaReporte.jsx): tipo con glifo, hace cuanto,
 * distancia, estado segun la comunidad, vencimiento, descripcion, foto, votos y acciones.
 */
@Composable
fun TarjetaReporte(
    ro: ReporteOrdenado,
    miVoto: Int?,
    onVotar: (Int?) -> Unit,
    modifier: Modifier = Modifier,
    detalle: Boolean = false,
    onAbrir: (() -> Unit)? = null,
    onVerMapa: (() -> Unit)? = null,
) {
    val r = ro.reporte
    val nombre = Comunidad.nombreReporte(r)
    val descartado = r.estado == "descartado"
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.Top) {
                GlifoReporte(r.tipo, tamano = if (detalle) 48 else 36)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(nombre, style = if (detalle) MaterialTheme.typography.titleLarge else MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    val hace = Tiempo.haceTexto(Tiempo.parsearMs(r.creado_en))
                    val dist = Comunidad.textoDistancia(ro.distanciaKm)
                    LineaFuente(listOfNotNull(hace.takeIf { it.isNotBlank() }, dist).joinToString(" · "))
                    LineaFuente("${Comunidad.textoEstado(r.estado)} · ${Comunidad.venceEn(r.expira_en)}")
                }
            }
            if (!r.descripcion.isNullOrBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    r.descripcion, style = MaterialTheme.typography.bodyMedium,
                    maxLines = if (detalle) Int.MAX_VALUE else 3, overflow = TextOverflow.Ellipsis,
                    color = if (descartado) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                )
            }
            if (!r.foto_url.isNullOrBlank()) {
                Spacer(Modifier.height(10.dp))
                FotoReporte(r.foto_url, nombre, alto = if (detalle) 300 else 180)
            }
            Spacer(Modifier.height(10.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Voto(cuenta = r.likes, etiqueta = "a favor", activo = miVoto == 1, abajo = false) { onVotar(if (miVoto == 1) null else 1) }
                Voto(cuenta = r.dislikes, etiqueta = "en contra", activo = miVoto == -1, abajo = true) { onVotar(if (miVoto == -1) null else -1) }
                Spacer(Modifier.weight(1f))
                if (onVerMapa != null && r.lat != null && r.lon != null) {
                    TextButton(onClick = onVerMapa) { Text("Ver en el mapa") }
                }
            }
            if (onAbrir != null) {
                TextButton(onClick = onAbrir, modifier = Modifier.fillMaxWidth()) { Text("Detalle y comentarios") }
            }
        }
    }
}

@Composable
private fun Voto(cuenta: Int, etiqueta: String, activo: Boolean, abajo: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected = activo,
        onClick = onClick,
        label = { Text("$cuenta $etiqueta") },
        leadingIcon = { Icon(Icons.Filled.ThumbUp, contentDescription = null, modifier = Modifier.size(16.dp).then(if (abajo) Modifier.rotate(180f) else Modifier)) },
    )
}

/** "Entra para X." con el boton a la pestana Cuenta (components/EstadoCarga.jsx EntraPara). */
@Composable
fun EntraPara(que: String, irCuenta: () -> Unit, modifier: Modifier = Modifier, compacto: Boolean = false) {
    Column(
        modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(12.dp)).padding(14.dp),
    ) {
        Text("Entra para $que.", style = MaterialTheme.typography.titleMedium)
        if (!compacto) {
            Spacer(Modifier.height(4.dp))
            Text(Comunidad.POR_QUE_CUENTA, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(8.dp))
        Button(onClick = irCuenta) { Text("Iniciar sesión o crear cuenta") }
    }
}

/** Franja con el aviso de la ultima accion (error o confirmacion). */
@Composable
fun AvisoAccion(texto: String?, ok: Boolean = false, modifier: Modifier = Modifier) {
    if (texto.isNullOrBlank()) return
    val fondo = if (ok) Color(0xFFDCFCE7) else Color(0xFFFEE2E2)
    val tinta = if (ok) Color(0xFF166534) else Color(0xFF991B1B)
    Box(modifier.fillMaxWidth().background(fondo, RoundedCornerShape(10.dp)).padding(12.dp)) {
        Text(texto, color = tinta, style = MaterialTheme.typography.bodyMedium)
    }
}
