package pe.simpac.app.ui.comunidad

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.EstadoSesion
import pe.simpac.app.dominio.Comunidad
import pe.simpac.app.dominio.ReporteOrdenado
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.componentes.ContadorAnimado
import pe.simpac.app.ui.componentes.EsqueletoBloque
import pe.simpac.app.ui.componentes.EsqueletoCirculo
import pe.simpac.app.ui.componentes.EsqueletoLinea
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.Transiciones
import pe.simpac.app.ui.componentes.bordeTarjeta
import pe.simpac.app.ui.componentes.esqueleto
import pe.simpac.app.ui.componentes.presionable
import pe.simpac.app.ui.componentes.temaOscuro

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

/**
 * Foto del reporte desde la URL publica del bucket (Coil): esqueleto con brillo mientras baja, fundido
 * de 220 ms al llegar y, si falla, un bloque neutro con icono y texto (nunca un hueco en blanco).
 */
@Composable
fun FotoReporte(url: String, nombre: String, alto: Int, modifier: Modifier = Modifier) {
    val contexto = LocalContext.current
    val peticion = remember(url) { ImageRequest.Builder(contexto).data(url).crossfade(Transiciones.APARECER_MS).build() }
    val forma = RoundedCornerShape(10.dp)
    SubcomposeAsyncImage(
        model = peticion,
        contentDescription = "Foto del reporte: $nombre",
        contentScale = ContentScale.Crop,
        modifier = modifier.fillMaxWidth().height(alto.dp).clip(forma),
        loading = { Box(Modifier.fillMaxSize().esqueleto(forma)) },
        error = {
            Column(
                Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surfaceVariant).padding(12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Icon(Icons.Outlined.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(6.dp))
                Text(
                    "No se pudo cargar la foto",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
            }
        },
    )
}

/**
 * Tarjeta de un reporte ciudadano (components/TarjetaReporte.jsx): tipo con glifo, hace cuanto,
 * distancia, estado segun la comunidad, vencimiento, descripcion, foto, votos y acciones.
 * Con `onAbrir`, toda la tarjeta se puede tocar (se encoge al presionar) ademas del boton de detalle.
 * `votando` deshabilita los votos mientras se envia uno (sin doble toque) y muestra una rueda pequena.
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
    votando: Boolean = false,
) {
    val colores = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    val sinSombra = CardDefaults.cardElevation(defaultElevation = 0.dp)
    if (onAbrir != null) {
        val vista = LocalView.current
        val fuente = remember { MutableInteractionSource() }
        Card(
            onClick = { Haptica.toque(vista); onAbrir() },
            interactionSource = fuente,
            modifier = modifier.fillMaxWidth().presionable(fuente),
            shape = MaterialTheme.shapes.medium,
            colors = colores,
            elevation = sinSombra,
            border = bordeTarjeta(),
        ) {
            CuerpoReporte(ro, miVoto, onVotar, detalle, onAbrir, onVerMapa, votando)
        }
    } else {
        Card(
            modifier = modifier.fillMaxWidth(),
            shape = MaterialTheme.shapes.medium,
            colors = colores,
            elevation = sinSombra,
            border = bordeTarjeta(),
        ) {
            CuerpoReporte(ro, miVoto, onVotar, detalle, null, onVerMapa, votando)
        }
    }
}

@Composable
private fun CuerpoReporte(
    ro: ReporteOrdenado,
    miVoto: Int?,
    onVotar: (Int?) -> Unit,
    detalle: Boolean,
    onAbrir: (() -> Unit)?,
    onVerMapa: (() -> Unit)?,
    votando: Boolean,
) {
    val r = ro.reporte
    val nombre = Comunidad.nombreReporte(r)
    val descartado = r.estado == "descartado"
    val vista = LocalView.current
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
            Voto(cuenta = r.likes, etiqueta = "a favor", activo = miVoto == 1, abajo = false, habilitado = !votando) { onVotar(if (miVoto == 1) null else 1) }
            Voto(cuenta = r.dislikes, etiqueta = "en contra", activo = miVoto == -1, abajo = true, habilitado = !votando) { onVotar(if (miVoto == -1) null else -1) }
            AnimatedVisibility(
                visible = votando,
                enter = fadeIn(tween(150, easing = FastOutSlowInEasing)),
                exit = fadeOut(tween(150, easing = FastOutSlowInEasing)),
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(16.dp).semantics { contentDescription = "Enviando tu voto" },
                    strokeWidth = 2.dp,
                )
            }
            Spacer(Modifier.weight(1f))
            if (onVerMapa != null && r.lat != null && r.lon != null) {
                TextButton(onClick = { Haptica.toque(vista); onVerMapa() }) { Text("Ver en el mapa") }
            }
        }
        if (onAbrir != null) {
            TextButton(onClick = { Haptica.toque(vista); onAbrir() }, modifier = Modifier.fillMaxWidth()) { Text("Detalle y comentarios") }
        }
    }
}

/**
 * Chip de voto: se encoge al presionar, da un rebote corto (1,15 y vuelta, 270 ms) al tocarlo, vibra
 * y el numero sube o baja animado. El texto "a favor" / "en contra" acompana al icono girado.
 */
@Composable
private fun Voto(cuenta: Int, etiqueta: String, activo: Boolean, abajo: Boolean, habilitado: Boolean, onClick: () -> Unit) {
    val vista = LocalView.current
    val fuente = remember { MutableInteractionSource() }
    val escala = remember { Animatable(1f) }
    var pulsos by remember { mutableIntStateOf(0) }
    LaunchedEffect(pulsos) {
        if (pulsos == 0) return@LaunchedEffect
        escala.animateTo(1.15f, tween(120, easing = FastOutSlowInEasing))
        escala.animateTo(1f, tween(150, easing = FastOutSlowInEasing))
    }
    FilterChip(
        selected = activo,
        enabled = habilitado,
        onClick = { Haptica.toque(vista); pulsos++; onClick() },
        interactionSource = fuente,
        modifier = Modifier.presionable(fuente).graphicsLayer {
            scaleX = escala.value
            scaleY = escala.value
        },
        label = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                ContadorAnimado(cuenta, style = LocalTextStyle.current)
                Spacer(Modifier.width(4.dp))
                Text(etiqueta)
            }
        },
        leadingIcon = { Icon(Icons.Filled.ThumbUp, contentDescription = null, modifier = Modifier.size(16.dp).then(if (abajo) Modifier.rotate(180f) else Modifier)) },
    )
}

/** "Entra para X." con el boton a la pestana Cuenta (components/EstadoCarga.jsx EntraPara). Toda la tarjeta se puede tocar. */
@Composable
fun EntraPara(que: String, irCuenta: () -> Unit, modifier: Modifier = Modifier, compacto: Boolean = false) {
    val vista = LocalView.current
    val fuente = remember { MutableInteractionSource() }
    Card(
        onClick = { Haptica.toque(vista); irCuenta() },
        interactionSource = fuente,
        modifier = modifier.fillMaxWidth().presionable(fuente),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(Modifier.padding(14.dp)) {
            Text("Entra para $que.", style = MaterialTheme.typography.titleMedium)
            if (!compacto) {
                Spacer(Modifier.height(4.dp))
                Text(Comunidad.POR_QUE_CUENTA, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(8.dp))
            Button(onClick = { Haptica.toque(vista); irCuenta() }) { Text("Iniciar sesión o crear cuenta") }
        }
    }
}

/**
 * Franja con el aviso de la ultima accion (error o confirmacion): icono con descripcion + texto, con
 * tintas del tema (correctas en oscuro). Aparece y se va con fundido y altura animada; para eso
 * recuerda el ultimo texto mientras se cierra.
 */
@Composable
fun AvisoAccion(texto: String?, ok: Boolean = false, modifier: Modifier = Modifier) {
    val memoria = remember { arrayOfNulls<String>(1) }
    if (!texto.isNullOrBlank()) memoria[0] = texto
    AnimatedVisibility(visible = !texto.isNullOrBlank(), enter = Transiciones.aparecer, exit = Transiciones.desaparecer, modifier = modifier) {
        val oscuro = temaOscuro()
        val fondo = if (ok) (if (oscuro) Color(0xFF14532D) else Color(0xFFDCFCE7)) else MaterialTheme.colorScheme.errorContainer
        val tinta = if (ok) (if (oscuro) Color(0xFFBBF7D0) else Color(0xFF166534)) else MaterialTheme.colorScheme.onErrorContainer
        Row(
            Modifier.fillMaxWidth().background(fondo, MaterialTheme.shapes.small).padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                if (ok) Icons.Outlined.CheckCircle else Icons.Outlined.Warning,
                contentDescription = if (ok) "Listo" else "Atención",
                tint = tinta,
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(memoria[0] ?: "", color = tinta, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/**
 * "n/max" de un campo de texto: a partir del 90 % del limite cambia de color y dice cuantas letras
 * quedan; pasado el limite va en el color de error y dice cuantas sobran (el texto acompana al color).
 */
@Composable
fun ContadorLetras(n: Int, max: Int, modifier: Modifier = Modifier) {
    val umbral = (max * 0.9).toInt()
    val oscuro = temaOscuro()
    val objetivo = when {
        n > max -> MaterialTheme.colorScheme.error
        n >= umbral -> if (oscuro) Color(0xFFFCD34D) else Color(0xFF92400E)
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    val color by animateColorAsState(objetivo, tween(200, easing = FastOutSlowInEasing), label = "contadorLetras")
    val texto = when {
        n > max -> "$n/$max · sobran ${n - max}"
        n >= umbral -> "$n/$max · quedan ${max - n}"
        else -> "$n/$max"
    }
    Text(texto, color = color, fontWeight = if (n >= umbral) FontWeight.SemiBold else null, modifier = modifier)
}

/** Silueta de una tarjeta de reporte (glifo, titulo, dos lineas, descripcion, foto y dos chips) para el esqueleto. */
@Composable
internal fun EsqueletoTarjetaReporte(detalle: Boolean = false, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = bordeTarjeta(),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.Top) {
                EsqueletoCirculo(if (detalle) 48.dp else 36.dp)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    EsqueletoLinea(anchoFraccion = 0.55f, alto = if (detalle) 20.dp else 16.dp)
                    EsqueletoLinea(anchoFraccion = 0.4f, alto = 12.dp)
                    EsqueletoLinea(anchoFraccion = 0.5f, alto = 12.dp)
                }
            }
            Spacer(Modifier.height(8.dp))
            EsqueletoLinea(anchoFraccion = 1f, alto = 12.dp)
            Spacer(Modifier.height(6.dp))
            EsqueletoLinea(anchoFraccion = 0.7f, alto = 12.dp)
            Spacer(Modifier.height(10.dp))
            EsqueletoBloque(if (detalle) 200.dp else 180.dp, forma = RoundedCornerShape(10.dp))
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                EsqueletoBloque(32.dp, Modifier.width(96.dp), RoundedCornerShape(8.dp))
                EsqueletoBloque(32.dp, Modifier.width(110.dp), RoundedCornerShape(8.dp))
            }
        }
    }
}
