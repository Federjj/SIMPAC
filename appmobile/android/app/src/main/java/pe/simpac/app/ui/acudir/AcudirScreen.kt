package pe.simpac.app.ui.acudir

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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.dominio.Acudir
import pe.simpac.app.dominio.Geo
import pe.simpac.app.dominio.PuntoCercano
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.Intents
import pe.simpac.app.ui.componentes.AvisoDato
import pe.simpac.app.ui.componentes.Cargando
import pe.simpac.app.ui.componentes.ErrorReintentar
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.PieReferencial
import pe.simpac.app.ui.componentes.Seccion

/** Numeros de emergencia nacionales (copia de frontend/src/data/emergencias.js, verificados el 14-10-2026 en gob.pe). */
private val NUMEROS = listOf(
    Triple("105", "Policía Nacional", null),
    Triple("116", "Bomberos", null),
    Triple("115", "Defensa Civil (INDECI)", null),
    Triple("106", "SAMU, ambulancia", "gob.pe no lista a Cajamarca entre las regiones con SAMU"),
)

@Composable
fun AcudirScreen(vm: AcudirViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val contexto = LocalContext.current
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("A dónde acudir", style = MaterialTheme.typography.headlineMedium)
        Seccion("Llama a") {
            NUMEROS.forEach { (numero, servicio, nota) ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("$numero  $servicio", style = MaterialTheme.typography.bodyLarge)
                        if (nota != null) LineaFuente(nota)
                    }
                    OutlinedButton(onClick = { Intents.marcar(contexto, numero) }) { Text("Llamar") }
                }
            }
            LineaFuente("Fuente: gob.pe, verificado el 14 oct 2026.")
        }
        when {
            estado.cargando -> Cargando("Buscando lo más cercano...")
            estado.error != null -> ErrorReintentar("No se pudieron leer los puntos (${estado.error}).", onReintentar = { vm.cargar() })
            else -> {
                if (estado.deCache) AvisoDato("Sin conexión: se muestra lo último guardado, de las ${Tiempo.horaCorta(estado.obtenidoEn)}.", fuerte = true)
                Text("Lo más cercano desde ${estado.desde} (en línea recta, hasta ${Acudir.RADIO_KM.toInt()} km):", style = MaterialTheme.typography.bodyMedium)
                if (estado.puntos.isEmpty()) {
                    Text("No hay establecimientos de salud, comisarías ni bomberos registrados a menos de ${Acudir.RADIO_KM.toInt()} km. Llama a los números de arriba.", style = MaterialTheme.typography.bodyLarge)
                }
                estado.puntos.forEach { TarjetaPunto(it) }
                TextButton(onClick = { vm.cargar() }) { Text("Actualizar") }
                LineaFuente("Zona segura: terreno alto y lejos del río o la quebrada (INDECI). La zona segura oficial de tu barrio la define tu municipalidad.")
            }
        }
        PieReferencial()
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun TarjetaPunto(pc: PuntoCercano) {
    val contexto = LocalContext.current
    val p = pc.punto
    Seccion("${Acudir.etiquetaTipo(p.tipo)}: a ${Geo.distanciaTexto(pc.distanciaKm)}") {
        Text(p.nombre, style = MaterialTheme.typography.titleMedium)
        val linea2 = listOfNotNull(p.categoria, when (p.atiende_24h) { true -> "atiende 24 h"; false -> "no atiende 24 h"; null -> null }).joinToString(", ")
        if (linea2.isNotBlank()) Text(linea2, style = MaterialTheme.typography.bodyMedium)
        val direccion = listOfNotNull(p.direccion, p.distrito).joinToString(", ")
        if (direccion.isNotBlank()) Text(direccion, style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (!p.telefono.isNullOrBlank()) {
                Button(onClick = { Intents.marcar(contexto, p.telefono) }) { Text("Llamar ${p.telefono}") }
            } else {
                Text("Sin teléfono en la fuente", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (p.lat != null && p.lon != null) {
                OutlinedButton(onClick = { Intents.comoLlegar(contexto, p.lat, p.lon, p.nombre) }) { Text("Cómo llegar") }
            }
        }
        Spacer(Modifier.height(4.dp))
        LineaFuente("Fuente: ${p.fuente ?: "oficial"}, dato del ${Tiempo.fechaLarga(p.actualizado)}.")
    }
}
