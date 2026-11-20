package pe.simpac.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Colores de SIMPAC: azul de la marca y neutros claros como la web. Sin colores dinamicos del sistema
 *  para que el semaforo (dominio/Nivel.kt) sea siempre el mismo. */
val AzulSimpac = Color(0xFF1D4ED8)
val AzulOscuro = Color(0xFF0F172A)
val FondoClaro = Color(0xFFF8FAFC)
val TextoOscuro = Color(0xFF0F172A)
val GrisTexto = Color(0xFF475569)
val GrisBorde = Color(0xFFE2E8F0)

/* Los contenedores (surfaceContainer*, secondaryContainer, inverseSurface...) se fijan a la misma
 * escala de grises azulados (slate) que el resto: sin ellos Material 3 usaria sus neutros con tinte
 * lila en la barra inferior, los chips seleccionados, el snackbar y el indicador de "tirar para
 * actualizar".
 * `secondary` es el mismo azul que `primary`: Material 3 pinta con el la etiqueta de la pestana
 * activa de la barra inferior (el icono y el indicador van con secondaryContainer), y con otro color
 * la etiqueta salia de un tono distinto al del resto de la barra.
 * `outline` es un gris medio: lo usan los controles que no tienen otra senal (el boton y el borde del
 * interruptor apagado, el borde de los campos de texto, de los botones y chips con borde).
 * `outlineVariant` es el gris fino de las tarjetas (`bordeTarjeta`) y de los separadores. */
private val EsquemaClaro = lightColorScheme(
    primary = AzulSimpac,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDBEAFE),
    onPrimaryContainer = Color(0xFF1E3A8A),
    secondary = AzulSimpac,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFDBEAFE),
    onSecondaryContainer = Color(0xFF1E3A8A),
    background = FondoClaro,
    onBackground = TextoOscuro,
    surface = Color.White,
    onSurface = TextoOscuro,
    surfaceVariant = Color(0xFFF1F5F9),
    onSurfaceVariant = GrisTexto,
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = FondoClaro,
    surfaceContainer = Color(0xFFF1F5F9),
    surfaceContainerHigh = Color(0xFFE8EDF3),
    surfaceContainerHighest = GrisBorde,
    outline = Color(0xFF94A3B8),
    outlineVariant = GrisBorde,
    inverseSurface = AzulOscuro,
    inverseOnSurface = FondoClaro,
    inversePrimary = Color(0xFF93C5FD),
    error = Color(0xFFB91C1C),
    onError = Color.White,
    errorContainer = Color(0xFFFEE2E2),
    onErrorContainer = Color(0xFF991B1B),
)

private val EsquemaOscuro = darkColorScheme(
    primary = Color(0xFF93C5FD),
    onPrimary = AzulOscuro,
    primaryContainer = Color(0xFF1E40AF),
    onPrimaryContainer = Color(0xFFDBEAFE),
    secondary = Color(0xFF93C5FD),
    onSecondary = AzulOscuro,
    secondaryContainer = Color(0xFF1E3A8A),
    onSecondaryContainer = Color(0xFFDBEAFE),
    background = Color(0xFF0B1220),
    onBackground = Color(0xFFE5E7EB),
    surface = Color(0xFF111827),
    onSurface = Color(0xFFE5E7EB),
    surfaceVariant = Color(0xFF1F2937),
    onSurfaceVariant = Color(0xFFCBD5E1),
    surfaceContainerLowest = Color(0xFF0B1220),
    surfaceContainerLow = Color(0xFF111827),
    surfaceContainer = Color(0xFF1F2937),
    surfaceContainerHigh = Color(0xFF273445),
    surfaceContainerHighest = Color(0xFF334155),
    outline = Color(0xFF64748B),
    outlineVariant = Color(0xFF334155),
    inverseSurface = Color(0xFFE5E7EB),
    inverseOnSurface = AzulOscuro,
    inversePrimary = AzulSimpac,
    error = Color(0xFFFCA5A5),
    onError = Color(0xFF450A0A),
    errorContainer = Color(0xFF7F1D1D),
    onErrorContainer = Color(0xFFFECACA),
)

val TipografiaSimpac = Typography(
    headlineLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 30.sp, lineHeight = 36.sp),
    headlineMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 24.sp, lineHeight = 30.sp),
    titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 20.sp, lineHeight = 26.sp),
    titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp),
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 14.sp, lineHeight = 20.sp),
    bodySmall = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 12.sp, lineHeight = 16.sp),
    labelLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Medium, fontSize = 14.sp),
)

/** Esquinas: small 8 dp (franjas, chips de texto), medium 14 dp (tarjetas), large 20 dp (hojas, fotos). */
val FormasSimpac = Shapes(
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(14.dp),
    large = RoundedCornerShape(20.dp),
)

@Composable
fun SimpacTheme(oscuro: Boolean = isSystemInDarkTheme(), contenido: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (oscuro) EsquemaOscuro else EsquemaClaro,
        typography = TipografiaSimpac,
        shapes = FormasSimpac,
        content = contenido,
    )
}
