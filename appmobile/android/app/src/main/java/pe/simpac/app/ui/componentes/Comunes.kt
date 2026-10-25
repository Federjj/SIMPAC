package pe.simpac.app.ui.componentes

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
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

@Composable
fun Cargando(texto: String = "Cargando...") {
    Column(Modifier.fillMaxWidth().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        CircularProgressIndicator()
        Spacer(Modifier.height(12.dp))
        Text(texto, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
fun ErrorReintentar(mensaje: String, onReintentar: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text("No se pudo cargar", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(6.dp))
        Text(mensaje, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center)
        Spacer(Modifier.height(12.dp))
        Button(onClick = onReintentar) { Text("Reintentar") }
    }
}

/** Franja de aviso sobre el dato: sin conexion (copia guardada) o desactualizado (mas de 3 h). */
@Composable
fun AvisoDato(texto: String, modifier: Modifier = Modifier, fuerte: Boolean = false) {
    val fondo = if (fuerte) Color(0xFFFFEDD5) else Color(0xFFFEF9C3)
    val tinta = if (fuerte) Color(0xFF9A3412) else Color(0xFF854D0E)
    Box(modifier.fillMaxWidth().background(fondo, RoundedCornerShape(10.dp)).padding(12.dp)) {
        Text(texto, color = tinta, style = MaterialTheme.typography.bodyMedium)
    }
}

/** Tarjeta con titulo para una seccion de la pantalla. */
@Composable
fun Seccion(titulo: String, modifier: Modifier = Modifier, contenido: @Composable () -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(Modifier.padding(14.dp)) {
            Text(titulo, style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            contenido()
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
