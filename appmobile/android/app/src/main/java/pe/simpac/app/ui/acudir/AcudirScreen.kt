package pe.simpac.app.ui.acudir

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
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
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.Seccion

/** Numeros de emergencia nacionales (copia de frontend/src/data/emergencias.js, verificados el 14-10-2026 en gob.pe). */
private val NUMEROS = listOf(
    Triple("105", "Policía Nacional", null),
    Triple("116", "Bomberos", null),
    Triple("115", "Defensa Civil (INDECI)", null),
    Triple("106", "SAMU, ambulancia", "gob.pe no lista a Cajamarca entre las regiones con SAMU"),
)

/**
 * Seccion "A donde acudir" de Inicio (antes era una pestana): los 3 puntos mas cercanos (salud 24 h si
 * esta a menos de 15 km o el mas cercano, comisaria, bomberos) en 30 km alrededor de la posicion (GPS o
 * centro del departamento), con distancia en linea recta, telefono, "Como llegar", fuente y fecha; y
 * los numeros nacionales. El mapa tiene la capa con todos los puntos.
 */
@Composable
fun AcudirResumen(vm: AcudirViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val contexto = LocalContext.current
    Seccion("A dónde acudir") {
        when {
            estado.cargando -> Text("Buscando lo más cercano...", style = MaterialTheme.typography.bodyMedium)
            estado.error != null -> {
                Text("No se pudieron leer los puntos (${estado.error}).", style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = { vm.cargar() }) { Text("Reintentar") }
            }
            else -> {
                if (estado.deCache) AvisoDato("Sin conexión: se muestra lo último guardado, de las ${Tiempo.horaCorta(estado.obtenidoEn)}.", fuerte = true)
                Text("Lo más cercano desde ${estado.desde} (en línea recta, hasta ${Acudir.RADIO_KM.toInt()} km):", style = MaterialTheme.typography.bodyMedium)
                if (estado.puntos.isEmpty()) {
                    Text("No hay establecimientos de salud, comisarías ni bomberos registrados a menos de ${Acudir.RADIO_KM.toInt()} km. Llama a los números de emergencia.", style = MaterialTheme.typography.bodyLarge)
                }
                estado.puntos.forEach { Spacer(Modifier.height(6.dp)); PuntoCompacto(it) }
            }
        }
        HorizontalDivider(Modifier.padding(vertical = 8.dp))
        Text("Llama a", style = MaterialTheme.typography.labelLarge)
        NUMEROS.forEach { (numero, servicio, nota) ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("$numero  $servicio", style = MaterialTheme.typography.bodyMedium)
                    if (nota != null) LineaFuente(nota)
                }
                TextButton(onClick = { Intents.marcar(contexto, numero) }) { Text("Llamar") }
            }
        }
        LineaFuente("Fuente: gob.pe, verificado el 14 oct 2026. Zona segura: terreno alto y lejos del río o la quebrada (INDECI); la oficial de tu barrio la define tu municipalidad. Todos los puntos están en la capa \"A dónde acudir\" del mapa.")
    }
}

@Composable
private fun PuntoCompacto(pc: PuntoCercano) {
    val contexto = LocalContext.current
    val p = pc.punto
    Column(Modifier.fillMaxWidth()) {
        Text("${Acudir.etiquetaTipo(p.tipo)}: ${p.nombre}", style = MaterialTheme.typography.titleSmall)
        val detalle = listOfNotNull(
            "a ${Geo.distanciaTexto(pc.distanciaKm)}",
            p.categoria,
            when (p.atiende_24h) { true -> "atiende 24 h"; false -> "no atiende 24 h"; null -> null },
            listOfNotNull(p.direccion, p.distrito).joinToString(", ").takeIf { it.isNotBlank() },
        ).joinToString(" · ")
        Text(detalle, style = MaterialTheme.typography.bodyMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (!p.telefono.isNullOrBlank()) {
                OutlinedButton(onClick = { Intents.marcar(contexto, p.telefono) }) { Text("Llamar ${p.telefono}") }
            } else {
                Text("Sin teléfono en la fuente", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 10.dp))
            }
            if (p.lat != null && p.lon != null) {
                TextButton(onClick = { Intents.comoLlegar(contexto, p.lat, p.lon, p.nombre) }) { Text("Cómo llegar") }
            }
        }
        LineaFuente("Fuente: ${p.fuente ?: "oficial"}, dato del ${Tiempo.fechaLarga(p.actualizado)}.")
    }
}
