package pe.simpac.app.ui.inicio

import android.Manifest
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.dominio.Alertas
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.Nivel
import pe.simpac.app.dominio.Pronostico
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.EncuadreMapa
import pe.simpac.app.ui.componentes.AvisoDato
import pe.simpac.app.ui.componentes.BotonesEmergencia
import pe.simpac.app.ui.componentes.Cargando
import pe.simpac.app.ui.componentes.Chip
import pe.simpac.app.ui.componentes.DiscoNivel
import pe.simpac.app.ui.componentes.ErrorReintentar
import pe.simpac.app.ui.componentes.EtiquetaNivel
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.Seccion

/** Pantalla Inicio con su ViewModel (la parte sin estado es InicioContenido, que prueba el androidTest). */
@Composable
fun InicioScreen(irAlertas: () -> Unit, irAcudir: () -> Unit, irMapa: (EncuadreMapa) -> Unit = {}, vm: InicioViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val pedirPermiso = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { r ->
        vm.gpsDecidido(r[Manifest.permission.ACCESS_FINE_LOCATION] == true || r[Manifest.permission.ACCESS_COARSE_LOCATION] == true)
    }
    InicioContenido(
        estado = estado,
        onReintentar = { vm.cargar() },
        onUsarGps = { pedirPermiso.launch(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION)) },
        onSinGps = { vm.gpsDecidido(false) },
        onElegirDepartamento = { vm.elegirDepartamento(it) },
        irAlertas = irAlertas,
        irAcudir = irAcudir,
        verRioEnMapa = {
            val rio = estado.rioDestacado ?: estado.rios.firstOrNull()
            irMapa(EncuadreMapa(rio?.rioAna, estado.centroLat, estado.centroLon))
        },
    )
}

@Composable
fun InicioContenido(
    estado: EstadoInicio,
    onReintentar: () -> Unit,
    onUsarGps: () -> Unit,
    onSinGps: () -> Unit,
    onElegirDepartamento: (String) -> Unit,
    irAlertas: () -> Unit,
    irAcudir: () -> Unit,
    verRioEnMapa: () -> Unit = {},
) {
    when {
        estado.explicarGps -> ExplicacionGps(onUsarGps, onSinGps)
        estado.cargando -> Cargando("Leyendo los datos de tu zona...")
        estado.error != null -> ErrorReintentar(estado.error, onReintentar)
        else -> Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp).testTag("inicio"),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (estado.deCache) {
                AvisoDato("Sin conexión: se muestra lo último guardado, de las ${Tiempo.horaCorta(estado.obtenidoEn)}.", fuerte = true)
            }
            if (estado.desactualizado) {
                AvisoDato("Dato desactualizado: SIMPAC no actualiza esta zona desde hace ${Tiempo.haceTexto(estado.titularRevisadoMs).removePrefix("hace ")}. Verifica con los canales oficiales.")
            }
            Semaforo(estado, onElegirDepartamento)
            TarjetaTitular(estado)
            ChipsZona(estado, irAlertas, verRioEnMapa)
            ContextoNino(estado)
            PronosticoTresDias(estado)
            BotonesEmergencia()
            TextButton(onClick = irAcudir) { Text("A dónde acudir cerca de ti") }
            Fuentes(estado)
            PieReferencial()
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun ExplicacionGps(onUsarGps: () -> Unit, onSinGps: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Tu ubicación", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(12.dp))
        Text(
            "SIMPAC usa tu ubicación solo mientras la app está abierta, para saber en qué departamento estás, " +
                "darte el pronóstico de la localidad más cercana y calcular a cuánto quedan la posta, la comisaría y los bomberos. " +
                "No la guarda ni la comparte. Si prefieres, elige tu departamento a mano.",
            style = MaterialTheme.typography.bodyLarge,
        )
        Spacer(Modifier.height(20.dp))
        Button(onClick = onUsarGps, modifier = Modifier.fillMaxWidth()) { Text("Usar mi ubicación") }
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = onSinGps, modifier = Modifier.fillMaxWidth()) { Text("Elegir mi departamento") }
    }
}

@Composable
private fun Semaforo(estado: EstadoInicio, onElegirDepartamento: (String) -> Unit) {
    var abierto by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        DiscoNivel(estado.nivel, Modifier.testTag("semaforo"))
        Spacer(Modifier.height(10.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(estado.departamento, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.testTag("departamento"))
            Spacer(Modifier.width(6.dp))
            TextButton(onClick = { abierto = true }) { Text(if (estado.porGps) "por GPS, cambiar" else "cambiar") }
            DropdownMenu(expanded = abierto, onDismissRequest = { abierto = false }) {
                Departamentos.TODOS.forEach { d ->
                    DropdownMenuItem(text = { Text(d.nombre) }, onClick = { abierto = false; onElegirDepartamento(d.nombre) })
                }
            }
        }
        EtiquetaNivel(estado.nivel)
    }
}

@Composable
private fun TarjetaTitular(estado: EstadoInicio) {
    val t = estado.titular
    Seccion("Tu zona ahora") {
        if (t == null) {
            Text("SIMPAC todavía no tiene un titular para ${estado.departamento}. No significa que todo esté en calma: revisa las alertas y los canales oficiales.", style = MaterialTheme.typography.bodyLarge)
        } else {
            Text(t.titular_corto ?: t.titular ?: "", style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("titular"))
            if (!t.detalle.isNullOrBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(t.detalle, style = MaterialTheme.typography.bodyMedium)
            }
            Spacer(Modifier.height(6.dp))
            LineaFuente("Generado el ${Tiempo.horaCorta(estado.titularGeneradoMs)} (${Tiempo.haceTexto(estado.titularGeneradoMs)}), " +
                if (t.origen == "llm") "redactado por un modelo de lenguaje con cifras oficiales y validado" else "por reglas de SIMPAC con datos oficiales")
        }
    }
}

@Composable
private fun ChipsZona(estado: EstadoInicio, irAlertas: () -> Unit, verRioEnMapa: () -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        if (estado.alertasLeidas) {
            val oficiales = Alertas.cuantasOficiales(estado.alertasZona)
            val peor = estado.alertasZona.filter { Alertas.esOficial(it) }.minOfOrNull { Alertas.nivelDe(it).orden }?.let { o -> Nivel.entries.first { it.orden == o } }
            val texto = when (oficiales) {
                0 -> "Sin alertas oficiales vigentes"
                1 -> "1 alerta oficial"
                else -> "$oficiales alertas oficiales"
            }
            Chip(texto, Modifier.testTag("chip_alertas"), color = peor?.let { androidx.compose.ui.graphics.Color(it.tinta) })
        }
        estado.rioDestacado?.let { r ->
            // rio_cauce.nombre ya suele traer "Río ..."; no se duplica la palabra
            val nombre = if (r.nombre.trim().lowercase().startsWith("río") || r.nombre.trim().lowercase().startsWith("rio")) r.nombre.trim() else "Río ${r.nombre}"
            Chip("$nombre: ${r.texto}", color = androidx.compose.ui.graphics.Color(r.nivel.tinta))
        } ?: if (estado.rios.isNotEmpty()) Chip("${estado.rios.size} ríos con estación, sin señales hoy") else Unit
    }
    if (estado.alertasLeidas && estado.alertasZona.isNotEmpty()) {
        TextButton(onClick = irAlertas) { Text("Ver las alertas de ${estado.departamento}") }
    }
    if (estado.rios.isNotEmpty()) {
        TextButton(onClick = verRioEnMapa) { Text("Ver el río en el mapa") }
    }
}

@Composable
private fun ContextoNino(estado: EstadoInicio) {
    Seccion("El Niño ahora") {
        val e = estado.enfen
        if (e != null) {
            Text(e.estado ?: "Sin estado", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text("Comunicado oficial ${e.numero}-${e.anio}${if (e.extraordinario) " (extraordinario)" else ""} del ENFEN, ${Tiempo.fechaLarga(e.fecha)}." +
                (e.proximo?.let { " Próximo: ${Tiempo.fechaLarga(it)}." } ?: ""), style = MaterialTheme.typography.bodyMedium)
        } else {
            Text(estado.errorApi ?: "Sin contexto El Niño por ahora.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun PronosticoTresDias(estado: EstadoInicio) {
    Seccion(if (estado.localidad != null) "Pronóstico de SENAMHI en ${estado.localidad}" else "Pronóstico de SENAMHI") {
        if (estado.pronostico.isEmpty()) {
            Text("No hay pronóstico de SENAMHI para una localidad cercana.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                estado.pronostico.forEach { f ->
                    Column(Modifier.weight(1f)) {
                        Text(Tiempo.etiquetaDia(f.fecha ?: ""), style = MaterialTheme.typography.labelLarge)
                        Text(Pronostico.resumenDia(f), style = MaterialTheme.typography.bodyMedium)
                        Text(Pronostico.temperaturas(f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun Fuentes(estado: EstadoInicio) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text("Fuentes y hora", style = MaterialTheme.typography.labelLarge)
        estado.fuentes.forEach { LineaFuente("${it.nombre}: ${it.hora}") }
        estado.avisos.forEach { LineaFuente(it) }
    }
}
