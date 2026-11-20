package pe.simpac.app.ui.acudir

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.ContentTransform
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Call
import androidx.compose.material.icons.outlined.Place
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.simpac.app.dominio.Acudir
import pe.simpac.app.dominio.Geo
import pe.simpac.app.dominio.PuntoCercano
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.Intents
import pe.simpac.app.ui.componentes.AvisoDato
import pe.simpac.app.ui.componentes.BotonEnlace
import pe.simpac.app.ui.componentes.EsqueletoBloque
import pe.simpac.app.ui.componentes.EsqueletoLinea
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.ProveedorEsqueleto
import pe.simpac.app.ui.componentes.Seccion
import pe.simpac.app.ui.componentes.Transiciones
import pe.simpac.app.ui.componentes.presionable

/** Numeros de emergencia nacionales (copia de frontend/src/data/emergencias.js, verificados el 14-10-2026 en gob.pe). */
private val NUMEROS = listOf(
    Triple("105", "Policía Nacional", null),
    Triple("116", "Bomberos", null),
    Triple("115", "Defensa Civil (INDECI)", null),
    Triple("106", "SAMU, ambulancia", "gob.pe no lista a Cajamarca entre las regiones con SAMU"),
)

/** Fases de la parte que carga de la seccion (los numeros nacionales se ven siempre). */
private enum class FaseAcudir { CARGANDO, ERROR, CONTENIDO }

/**
 * Filas de "Llama a": el boton "Llamar" ocupa 48 dp de alto (el area tactil minima de Material, que el
 * `TextButton` impone aunque dibuje 40 dp), asi que la fila mide eso como minimo y el texto baja
 * 14 dp para que su primera linea (20 dp) quede centrada con el boton; la nota sigue debajo.
 */
private val ALTO_FILA_LLAMAR = 48.dp
private val DESCENSO_TEXTO_LLAMAR = 14.dp

/**
 * Seccion "A donde acudir" de Inicio (antes era una pestana): los 3 puntos mas cercanos (salud 24 h si
 * esta a menos de 15 km o el mas cercano, comisaria, bomberos) en 30 km alrededor de la posicion (GPS o
 * centro del departamento), con distancia en linea recta, telefono, "Como llegar", fuente y fecha; y
 * los numeros nacionales. El mapa tiene la capa con todos los puntos. Mientras carga se ve la silueta
 * de las 3 filas; con puntos ya en pantalla, una recarga fallida solo deja una nota con "Reintentar".
 */
@Composable
fun AcudirResumen(vm: AcudirViewModel = viewModel()) {
    val estado by vm.estado.collectAsStateWithLifecycle()
    val contexto = LocalContext.current
    val vista = LocalView.current
    val fase = when {
        estado.cargando && !estado.cargado -> FaseAcudir.CARGANDO
        estado.error != null && !estado.cargado -> FaseAcudir.ERROR
        else -> FaseAcudir.CONTENIDO
    }
    Seccion("A dónde acudir") {
        AnimatedContent(targetState = fase, modifier = Modifier.fillMaxWidth(), transitionSpec = { fundido() }, label = "acudir") { f ->
            when (f) {
                FaseAcudir.CARGANDO -> ProveedorEsqueleto { EsqueletoAcudir() }
                FaseAcudir.ERROR -> NotaError("No se pudieron leer los puntos (${estado.error}).", onReintentar = { vm.cargar() })
                FaseAcudir.CONTENIDO -> Column(Modifier.fillMaxWidth()) {
                    AnimatedVisibility(visible = estado.deCache, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
                        AvisoDato("Sin conexión: se muestra lo último guardado, de las ${Tiempo.horaCorta(estado.obtenidoEn)}.", Modifier.padding(bottom = 8.dp), fuerte = true)
                    }
                    AnimatedVisibility(visible = estado.error != null && estado.cargado, enter = Transiciones.aparecer, exit = Transiciones.desaparecer) {
                        NotaError("No se pudo actualizar la lista (${estado.error}). Se muestra lo último leído.", onReintentar = { vm.cargar() })
                    }
                    Text("Lo más cercano desde ${estado.desde} (en línea recta, hasta ${Acudir.RADIO_KM.toInt()} km):", style = MaterialTheme.typography.bodyMedium)
                    if (estado.puntos.isEmpty()) {
                        VacioCompacto(
                            titulo = "Sin puntos registrados cerca",
                            texto = "No hay establecimientos de salud, comisarías ni bomberos registrados a menos de ${Acudir.RADIO_KM.toInt()} km. Llama a los números de emergencia.",
                        )
                    }
                    estado.puntos.forEachIndexed { i, pc ->
                        if (i > 0) HorizontalDivider(Modifier.padding(vertical = 8.dp), color = MaterialTheme.colorScheme.outlineVariant)
                        else Spacer(Modifier.height(8.dp))
                        PuntoCompacto(pc)
                    }
                }
            }
        }
        HorizontalDivider(Modifier.padding(vertical = 8.dp))
        Text("Llama a", style = MaterialTheme.typography.labelLarge)
        NUMEROS.forEachIndexed { i, (numero, servicio, nota) ->
            if (i > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth().heightIn(min = ALTO_FILA_LLAMAR), verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f).padding(top = DESCENSO_TEXTO_LLAMAR, bottom = 10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(numero, style = MaterialTheme.typography.labelLarge)
                        Spacer(Modifier.width(8.dp))
                        Text(servicio, style = MaterialTheme.typography.bodyMedium)
                    }
                    if (nota != null) LineaFuente(nota)
                }
                Spacer(Modifier.width(12.dp))
                BotonEnlace(
                    "Llamar",
                    iconoFinal = { Icon(Icons.Outlined.Call, contentDescription = null, modifier = Modifier.size(16.dp)) },
                ) { Haptica.toque(vista); Intents.marcar(contexto, numero) }
            }
        }
        LineaFuente("Fuente: gob.pe, verificado el 14 oct 2026. Zona segura: terreno alto y lejos del río o la quebrada (INDECI); la oficial de tu barrio la define tu municipalidad. Todos los puntos están en la capa \"A dónde acudir\" del mapa.")
    }
}

/** Cruce con fundido y tamano animado entre esqueleto, error y contenido. */
private fun <T> AnimatedContentTransitionScope<T>.fundido(): ContentTransform =
    (fadeIn(tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing)) togetherWith fadeOut(tween(150, easing = FastOutSlowInEasing)))
        .using(SizeTransform(clip = false) { _, _ -> tween(Transiciones.APARECER_MS, easing = FastOutSlowInEasing) })

/** Error compacto dentro de la tarjeta (icono con nombre, texto y "Reintentar"); el error grande del kit es para pantallas enteras. */
@Composable
private fun NotaError(texto: String, onReintentar: () -> Unit) {
    val fuente = remember { MutableInteractionSource() }
    Row(Modifier.fillMaxWidth().padding(bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Outlined.Warning, contentDescription = "Error", tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(8.dp))
        Text(texto, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
        TextButton(onClick = onReintentar, interactionSource = fuente, modifier = Modifier.presionable(fuente)) { Text("Reintentar") }
    }
}

/** Estado vacio sobrio para dentro de la tarjeta: icono en disco neutro, titulo y explicacion. */
@Composable
private fun VacioCompacto(titulo: String, texto: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier.size(40.dp).background(MaterialTheme.colorScheme.surfaceVariant, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Outlined.Place, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(22.dp))
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(titulo, style = MaterialTheme.typography.titleSmall)
            Text(texto, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** Un punto: tipo y nombre con la distancia alineada a la derecha, detalle, botones y fuente. */
@Composable
private fun PuntoCompacto(pc: PuntoCercano) {
    val contexto = LocalContext.current
    val vista = LocalView.current
    val p = pc.punto
    val fuenteLlamar = remember { MutableInteractionSource() }
    val fuenteLlegar = remember { MutableInteractionSource() }
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f)) {
                Text("${Acudir.etiquetaTipo(p.tipo)}: ${p.nombre}", style = MaterialTheme.typography.titleSmall)
                val detalle = listOfNotNull(
                    p.categoria,
                    when (p.atiende_24h) { true -> "atiende 24 h"; false -> "no atiende 24 h"; null -> null },
                    listOfNotNull(p.direccion, p.distrito).joinToString(", ").takeIf { it.isNotBlank() },
                ).joinToString(" · ")
                if (detalle.isNotBlank()) Text(detalle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.width(12.dp))
            Text(
                "a ${Geo.distanciaTexto(pc.distanciaKm)}",
                style = MaterialTheme.typography.titleSmall,
                textAlign = TextAlign.End,
                modifier = Modifier.widthIn(min = 56.dp),
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            if (!p.telefono.isNullOrBlank()) {
                OutlinedButton(
                    onClick = { Haptica.toque(vista); Intents.marcar(contexto, p.telefono) },
                    interactionSource = fuenteLlamar,
                    modifier = Modifier.presionable(fuenteLlamar),
                ) {
                    Icon(Icons.Outlined.Call, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Llamar ${p.telefono}")
                }
            } else {
                Text("Sin teléfono en la fuente", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (p.lat != null && p.lon != null) {
                TextButton(
                    onClick = { Haptica.toque(vista); Intents.comoLlegar(contexto, p.lat, p.lon, p.nombre) },
                    interactionSource = fuenteLlegar,
                    modifier = Modifier.presionable(fuenteLlegar),
                ) { Text("Cómo llegar") }
            }
        }
        LineaFuente("Fuente: ${p.fuente ?: "oficial"}, dato del ${Tiempo.fechaLarga(p.actualizado)}.")
    }
}

/* ---------- Esqueleto: la frase de "desde" y tres filas con la silueta de PuntoCompacto ---------- */

private val Pastilla = RoundedCornerShape(999.dp)

@Composable
private fun EsqueletoAcudir() {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        EsqueletoLinea(anchoFraccion = 0.85f, alto = 12.dp)
        repeat(3) { i ->
            if (i > 0) HorizontalDivider(Modifier.padding(vertical = 4.dp), color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                EsqueletoLinea(anchoFraccion = 0.75f, alto = 14.dp, modifier = Modifier.weight(1f))
                EsqueletoLinea(alto = 12.dp, modifier = Modifier.width(48.dp))
            }
            EsqueletoLinea(anchoFraccion = 0.9f, alto = 12.dp)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                EsqueletoBloque(36.dp, Modifier.width(132.dp), Pastilla)
                EsqueletoBloque(36.dp, Modifier.width(100.dp), Pastilla)
            }
            EsqueletoLinea(anchoFraccion = 0.6f, alto = 10.dp)
        }
    }
}
