package pe.simpac.app.ui.componentes

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import pe.simpac.app.dominio.Nivel
import pe.simpac.app.ui.Intents

/** Disco grande del semaforo con la etiqueta adentro (color + texto, nunca solo color). */
@Composable
fun DiscoNivel(nivel: Nivel, modifier: Modifier = Modifier, tamano: Int = 132) {
    Box(
        modifier = modifier
            .size(tamano.dp)
            .background(Color(nivel.fondo), CircleShape)
            .semantics { contentDescription = "Nivel de la zona: ${nivel.etiqueta}" },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            nivel.etiqueta.uppercase(),
            color = Color(nivel.textoSobreFondo),
            fontWeight = FontWeight.Bold,
            fontSize = if (nivel == Nivel.EMERGENCIA) 18.sp else 20.sp,
            textAlign = TextAlign.Center,
        )
    }
}

/** Etiqueta pequena: punto de color + nombre del nivel. */
@Composable
fun EtiquetaNivel(nivel: Nivel, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .background(Color(nivel.fondo).copy(alpha = 0.14f), RoundedCornerShape(999.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(10.dp).background(Color(nivel.fondo), CircleShape))
        Spacer(Modifier.width(6.dp))
        Text(nivel.etiqueta, color = Color(nivel.tinta), fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall)
    }
}

/** Chip neutro de texto (para contadores y notas cortas). */
@Composable
fun Chip(texto: String, modifier: Modifier = Modifier, color: Color? = null) {
    Box(
        modifier = modifier
            .border(1.dp, color ?: MaterialTheme.colorScheme.outline, RoundedCornerShape(999.dp))
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Text(texto, style = MaterialTheme.typography.bodySmall, color = color ?: MaterialTheme.colorScheme.onSurface)
    }
}

/**
 * Rueda con texto para esperas cortas sin silueta conocida (por ejemplo "Revisando tu sesión...").
 * Para el primer cargado de una pantalla usar `ContenidoConEstado` con un esqueleto (Esqueletos.kt).
 */
@Composable
fun Cargando(texto: String = "Cargando...") {
    Column(
        Modifier.fillMaxWidth().padding(32.dp).semantics(mergeDescendants = true) {},
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator()
        Spacer(Modifier.height(12.dp))
        Text(texto, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Verdadero si la superficie del tema es oscura (para elegir tintas de franjas y esqueletos). */
@Composable
fun temaOscuro(): Boolean = MaterialTheme.colorScheme.surface.luminance() < 0.5f

/**
 * Franja de aviso sobre el dato: sin conexion (copia guardada, `fuerte`) o desactualizado (mas de 3 h).
 * Ambar o naranja claros sobre tinta oscura en el tema claro; en el oscuro, fondo apagado y tinta clara.
 */
@Composable
fun AvisoDato(texto: String, modifier: Modifier = Modifier, fuerte: Boolean = false) {
    val oscuro = temaOscuro()
    val fondo = when {
        fuerte && oscuro -> Color(0xFF431407)
        fuerte -> Color(0xFFFFEDD5)
        oscuro -> Color(0xFF422006)
        else -> Color(0xFFFEF9C3)
    }
    val tinta = when {
        fuerte && oscuro -> Color(0xFFFDBA74)
        fuerte -> Color(0xFF9A3412)
        oscuro -> Color(0xFFFDE68A)
        else -> Color(0xFF854D0E)
    }
    Box(modifier.fillMaxWidth().background(fondo, MaterialTheme.shapes.small).padding(12.dp)) {
        Text(texto, color = tinta, style = MaterialTheme.typography.bodyMedium)
    }
}

/**
 * Borde fino de las tarjetas de la app (Seccion y esqueletos): 1 dp de `outlineVariant`, el gris suave
 * del tema. `outline` es mas oscuro y queda para los controles (interruptores, campos, chips con borde).
 */
@Composable
fun bordeTarjeta(): BorderStroke = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)

/**
 * Tarjeta con titulo para una seccion de la pantalla: forma `medium` (14 dp), sin sombra y con borde
 * fino, igual en claro y oscuro. `accion` va a la derecha del titulo (por ejemplo un `TextButton`
 * "Ver todo" o "Actualizar"); si es nula el titulo ocupa todo el ancho.
 */
@Composable
fun Seccion(
    titulo: String,
    modifier: Modifier = Modifier,
    accion: (@Composable () -> Unit)? = null,
    contenido: @Composable () -> Unit,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = bordeTarjeta(),
    ) {
        Column(Modifier.padding(14.dp)) {
            if (accion == null) {
                Text(titulo, style = MaterialTheme.typography.titleMedium)
            } else {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(titulo, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                    accion()
                }
            }
            Spacer(Modifier.height(8.dp))
            contenido()
        }
    }
}

/**
 * Enlace de texto alineado con el contenido ("Ver las alertas de Cajamarca", "Cómo llegar", "Olvidé mi
 * contraseña"): un `TextButton` sin el relleno horizontal de 12 dp que trae Material, asi el texto
 * empieza donde empieza el parrafo o la tarjeta de arriba, con la misma respuesta al pulsar que el
 * resto de botones (`presionable`). Conserva la altura minima del boton (40 dp) para tocarlo bien; con
 * etiquetas de menos de 58 dp (el ancho minimo de Material) el texto queda centrado en ese ancho.
 * `iconoFinal` va a la derecha del texto (por ejemplo una flecha que gira al abrir). La vibracion la
 * pone quien llama (`Haptica.toque`), como en los demas botones de la app.
 */
@Composable
fun BotonEnlace(
    texto: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    iconoFinal: (@Composable () -> Unit)? = null,
    onClick: () -> Unit,
) {
    val fuente = remember { MutableInteractionSource() }
    TextButton(
        onClick = onClick,
        modifier = modifier.presionable(fuente),
        enabled = enabled,
        interactionSource = fuente,
        contentPadding = PaddingValues(horizontal = 0.dp, vertical = 8.dp),
    ) {
        Text(texto)
        if (iconoFinal != null) {
            Spacer(Modifier.width(4.dp))
            iconoFinal()
        }
    }
}

/** Botones "Llamar 105" y "Llamar 116" (abren el marcador; la persona confirma). */
@Composable
fun BotonesEmergencia(modifier: Modifier = Modifier) {
    val contexto = LocalContext.current
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Button(onClick = { Intents.marcar(contexto, "105") }, modifier = Modifier.weight(1f)) { Text("Llamar 105") }
        OutlinedButton(onClick = { Intents.marcar(contexto, "116") }, modifier = Modifier.weight(1f)) { Text("Llamar 116") }
    }
}

/** Pie fijo: la app es referencial. */
@Composable
fun PieReferencial(modifier: Modifier = Modifier) {
    Text(
        "Información referencial; no reemplaza los canales oficiales (105 Policía / 116 Bomberos).",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier.fillMaxWidth(),
    )
}

/** Linea "Fuente: X, hora". */
@Composable
fun LineaFuente(texto: String, modifier: Modifier = Modifier) {
    Text(texto, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = modifier)
}
