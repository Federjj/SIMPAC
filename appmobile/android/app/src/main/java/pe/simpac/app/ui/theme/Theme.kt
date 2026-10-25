package pe.simpac.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** Colores de SIMPAC: azul de la marca y neutros claros como la web. Sin colores dinamicos del sistema
 *  para que el semaforo (dominio/Nivel.kt) sea siempre el mismo. */
val AzulSimpac = Color(0xFF1D4ED8)
val AzulOscuro = Color(0xFF0F172A)
val FondoClaro = Color(0xFFF8FAFC)
val TextoOscuro = Color(0xFF0F172A)
val GrisTexto = Color(0xFF475569)
val GrisBorde = Color(0xFFE2E8F0)

private val EsquemaClaro = lightColorScheme(
    primary = AzulSimpac,
    onPrimary = Color.White,
    secondary = Color(0xFF0F766E),
    background = FondoClaro,
    surface = Color.White,
    onBackground = TextoOscuro,
    onSurface = TextoOscuro,
    onSurfaceVariant = GrisTexto,
    outline = GrisBorde,
    surfaceVariant = Color(0xFFF1F5F9),
)

private val EsquemaOscuro = darkColorScheme(
    primary = Color(0xFF93C5FD),
    onPrimary = AzulOscuro,
    secondary = Color(0xFF5EEAD4),
    background = Color(0xFF0B1220),
    surface = Color(0xFF111827),
    onBackground = Color(0xFFE5E7EB),
    onSurface = Color(0xFFE5E7EB),
    onSurfaceVariant = Color(0xFFCBD5E1),
    outline = Color(0xFF334155),
    surfaceVariant = Color(0xFF1F2937),
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

@Composable
fun SimpacTheme(oscuro: Boolean = isSystemInDarkTheme(), contenido: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (oscuro) EsquemaOscuro else EsquemaClaro,
        typography = TipografiaSimpac,
        content = contenido,
    )
}
