package pe.simpac.app

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import pe.simpac.app.data.AlertaActual
import pe.simpac.app.data.ComunicadoEnfen
import pe.simpac.app.data.PronosticoVigente
import pe.simpac.app.data.TitularZona
import pe.simpac.app.dominio.Nivel
import pe.simpac.app.ui.inicio.EstadoInicio
import pe.simpac.app.ui.inicio.Fuente
import pe.simpac.app.ui.inicio.InicioContenido
import pe.simpac.app.ui.theme.SimpacTheme

/** Prueba de Compose UI de la pantalla Inicio con datos falsos (sin red ni Supabase). */
@RunWith(AndroidJUnit4::class)
class InicioScreenTest {
    @get:Rule
    val regla = createComposeRule()

    private val estadoFalso = EstadoInicio(
        cargando = false,
        departamento = "Cajamarca",
        nivel = Nivel.ALERTA,
        titular = TitularZona(
            departamento = "Cajamarca", nivel = "alerta",
            titular_corto = "ALERTA en Cajamarca: aviso naranja de SENAMHI por lluvias.",
            detalle = "Aviso 421 vigente hasta el jueves.", generado_en = "2026-10-20T13:05:00+00:00", origen = "reglas",
        ),
        titularGeneradoMs = 1_792_501_500_000L,
        alertasZona = listOf(AlertaActual(tipo = "aviso", referencia = "SENAMHI aviso 421", zona = "Cajamarca", nivel = "alerta", ts = "2026-10-20T11:00:00+00:00")),
        alertasLeidas = true,
        enfen = ComunicadoEnfen(anio = 2026, numero = 18, fecha = "2026-10-16", estado = "Alerta de El Niño Costero"),
        pronostico = listOf(PronosticoVigente(codigo = "06-0011", nombre = "Cajamarca", fecha = "2026-10-20", tipo = "lluvia", posible = true, momento = "en la tarde", tmax = 21, tmin = 7)),
        localidad = "Cajamarca",
        fuentes = listOf(Fuente("Titular de SIMPAC (por reglas)", "20 oct, 08:05 (hace 1 h)")),
    )

    private fun montar(estado: EstadoInicio) {
        regla.setContent {
            SimpacTheme {
                InicioContenido(estado = estado, onReintentar = {}, onUsarGps = {}, onSinGps = {}, onElegirDepartamento = {}, irAlertas = {}, irAcudir = {})
            }
        }
    }

    @Test
    fun muestra_semaforo_titular_y_chips() {
        montar(estadoFalso)
        regla.onNodeWithTag("semaforo").assertIsDisplayed()
        regla.onNodeWithText("ALERTA").assertIsDisplayed()
        regla.onNodeWithText("Cajamarca").assertIsDisplayed()
        regla.onNodeWithTag("titular").assertIsDisplayed()
        regla.onNodeWithText("ALERTA en Cajamarca: aviso naranja de SENAMHI por lluvias.").assertIsDisplayed()
        regla.onNodeWithText("1 alerta oficial").assertIsDisplayed()
        regla.onNodeWithText("Alerta de El Niño Costero").assertIsDisplayed()
        regla.onNodeWithText("Llamar 105").assertIsDisplayed()
        regla.onNodeWithText("Llamar 116").assertIsDisplayed()
    }

    @Test
    fun sin_titular_no_dice_normal() {
        montar(estadoFalso.copy(titular = null, nivel = Nivel.SIN_DATO, alertasZona = emptyList()))
        regla.onNodeWithText("SIN DATOS").assertIsDisplayed()
        regla.onNodeWithText("Sin alertas oficiales vigentes").assertIsDisplayed()
    }

    @Test
    fun error_muestra_reintentar() {
        montar(EstadoInicio(cargando = false, error = "No se pudo leer SIMPAC (sin respuesta)."))
        regla.onNodeWithText("Reintentar").assertIsDisplayed()
    }

    @Test
    fun explicacion_del_gps_antes_de_pedir_el_permiso() {
        montar(EstadoInicio(cargando = false, explicarGps = true))
        regla.onNodeWithText("Usar mi ubicación").assertIsDisplayed()
        regla.onNodeWithText("Elegir mi departamento").assertIsDisplayed()
    }
}
