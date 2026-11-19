package pe.simpac.app.ui.mapa

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import pe.simpac.app.data.EstacionSenamhi
import pe.simpac.app.data.PuntoAcudir
import pe.simpac.app.data.ReporteVigente
import pe.simpac.app.dominio.Acudir
import pe.simpac.app.dominio.AvisosMapa
import pe.simpac.app.dominio.Cauces
import pe.simpac.app.dominio.EstadoCauce
import pe.simpac.app.dominio.Fen
import pe.simpac.app.dominio.Incidentes
import pe.simpac.app.dominio.Lluvia
import pe.simpac.app.dominio.NivelZona
import pe.simpac.app.dominio.Nowcast
import pe.simpac.app.dominio.Paleta
import pe.simpac.app.dominio.PronosticoMapa
import pe.simpac.app.dominio.Reportes
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ui.Intents
import pe.simpac.app.ui.componentes.LineaFuente
import pe.simpac.app.ui.componentes.PieReferencial

/** Hojas inferiores del mapa: texto en lenguaje claro, fuente con hora, sin HTML. */

@Composable
private fun Hoja(contenido: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        contenido()
        PieReferencial()
    }
}

@Composable
private fun Pastilla(texto: String, color: Long) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.background(Color(color).copy(alpha = 0.16f), RoundedCornerShape(999.dp)).padding(horizontal = 10.dp, vertical = 4.dp)) {
        Box(Modifier.size(10.dp).background(Color(color), CircleShape))
        Spacer(Modifier.width(6.dp))
        Text(texto, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun Titulo(texto: String) = Text(texto, style = MaterialTheme.typography.titleLarge)

@Composable
private fun Parrafo(texto: String) = Text(texto, style = MaterialTheme.typography.bodyMedium)

@Composable
fun HojaSeleccion(sel: Seleccion, estado: EstadoMapa) {
    when (sel) {
        is Seleccion.Avisos -> HojaAvisos(sel.avisos, estado.obtenidoAvisosEn)
        is Seleccion.Rio -> HojaRio(sel.rio, estado.obtenidoEn)
        is Seleccion.Mashcon -> HojaMashcon(sel.mashcon, estado.obtenidoEn)
        is Seleccion.EstacionRio -> HojaEstacionRio(sel.estacion, estado.obtenidoEn)
        is Seleccion.Zona -> HojaZona(sel.zona, estado.obtenidoEn)
        is Seleccion.Estacion -> HojaEstacion(sel.estacion, estado.obtenidoEstacionesEn)
        is Seleccion.Acudir -> HojaAcudir(sel.punto, estado.obtenidoAcudirEn)
        is Seleccion.Localidad -> HojaLocalidad(sel, estado.obtenidoPronosticoEn)
        is Seleccion.ManchaNowcast -> HojaNowcast(sel, estado)
        is Seleccion.LluviaEstacion -> HojaLluviaEstacion(sel.lluvia, estado.obtenidoLluviaEn)
        is Seleccion.PoligonoFen -> HojaFen(sel)
        is Seleccion.Incidentes -> HojaIncidentes(sel, estado.obtenidoIncidentesEn)
        is Seleccion.Reporte -> HojaReporte(sel.reporte, estado.obtenidoReportesEn)
        is Seleccion.Franja -> HojaFranja(sel.franja, estado.obtenidoEn)
    }
}

@Composable
private fun HojaAvisos(avisos: List<AvisoDibujo>, obtenidoEn: Long?) {
    val contexto = LocalContext.current
    Hoja {
        val lista = AvisosMapa.unoPorAviso(avisos.map { it.aviso })
        if (lista.size > 1) Text("${lista.size} avisos de SENAMHI en este punto", style = MaterialTheme.typography.labelLarge)
        lista.forEachIndexed { i, a ->
            if (i > 0) HorizontalDivider()
            Titulo(AvisosMapa.titulo(a))
            Pastilla(AvisosMapa.ETIQUETA_NIVEL[a.nivel] ?: "Nivel no indicado", Paleta.aviso(a.nivel))
            a.titulo?.let { Text(it, style = MaterialTheme.typography.titleMedium) }
            Parrafo(AvisosMapa.resumen(a))
            (a.texto_dia ?: a.descripcion)?.let { Parrafo(it) }
            AvisosMapa.accion(a.nivel)?.let { Text(it, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold) }
            AvisosMapa.vigencia(a)?.let { LineaFuente(it) }
            if (a.departamentos.isNotEmpty()) LineaFuente("Departamentos: ${a.departamentos.joinToString(", ")}")
            if (a.tipo == "lluvia24h") LineaFuente("Aviso de lluvia acumulada en 24 h: puede llover en algún momento, no todo el día.")
            a.url?.takeIf { it.startsWith("https://") }?.let { url ->
                Button(onClick = { Intents.abrirNavegador(contexto, url) }) { Text("Ver el aviso oficial") }
            }
        }
        LineaFuente("Fuente: SENAMHI, aviso ${lista.joinToString(" y ") { "N.º ${it.numero ?: "?"}-${it.anio ?: ""}" }}. ${AvisosMapa.FIRMA} Leído el ${Tiempo.horaCorta(obtenidoEn)}.")
    }
}

@Composable
private fun FilasAna(t: pe.simpac.app.dominio.TextoRio, unidad: String?) {
    val u = unidad ?: ""
    val sufijo = if (t.bajo) " por nivel bajo" else ""
    LineaFuente("Nivel de alerta$sufijo: ${t.ua?.let { "${Cauces.num(it)} $u" } ?: "no publicado"}")
    LineaFuente("Nivel de emergencia$sufijo: ${t.ue?.let { "${Cauces.num(it)} $u" } ?: "no publicado"}")
}

@Composable
private fun HojaEstacionRio(e: EstacionRioDibujo, obtenidoEn: Long?) {
    val contexto = LocalContext.current
    Hoja {
        Titulo(Cauces.resumenEstacion(e.nombreRio, e.caudal, e.t, if (e.porAviso) pe.simpac.app.dominio.EstadoCauceRio(e.estado, true, e.colorAviso) else null))
        Pastilla(if (e.porAviso) "Aviso hidrológico ${e.colorAviso} de SENAMHI" else e.t.etiqueta, Paleta.rio(e.estado))
        LineaFuente("Estación ${e.caudal.estacion} (ANA)${e.caudal.departamento?.let { ", $it" } ?: ""}")
        if (e.porAviso && e.aviso != null) {
            val h = e.aviso
            val hasta = Tiempo.parsearMs(h.fin)?.let { ", vigente hasta el ${Tiempo.horaCorta(it)}" } ?: ""
            Parrafo("Hay un aviso hidrológico ${e.colorAviso} de SENAMHI para este río (N.º ${h.numero ?: "?"}$hasta). Tenlo en cuenta aunque la última medición de ANA diga otra cosa: el aviso puede llegar antes que la lectura nueva.")
            Parrafo("Última medición de ANA: ${e.t.frase}")
        } else {
            Parrafo(e.t.frase)
        }
        e.t.accion?.let { Text(it, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold) }
        FilasAna(e.t, e.caudal.unidad)
        LineaFuente("Medido: ${Cauces.lecturaRio(e.caudal) ?: "sin fecha"}")
        if (e.porAviso) e.aviso?.url?.takeIf { it.startsWith("https://") }?.let { url ->
            Button(onClick = { Intents.abrirNavegador(contexto, url) }) { Text("Ver el aviso de SENAMHI") }
        }
        LineaFuente("Fuente: niveles y umbrales de ANA, leídos el ${Tiempo.horaCorta(obtenidoEn)}${e.fuenteTrazo?.let { "; trazo del río: $it" } ?: ""}.")
    }
}

@Composable
private fun HojaRio(r: RioDibujo, obtenidoEn: Long?) {
    val contexto = LocalContext.current
    val est = r.estado
    val aviso = if (est.cauce.porAviso) est.zona.avisoHidro else null
    Hoja {
        val c = est.peor
        val t = est.t
        Titulo(if (c != null && t != null) Cauces.resumenEstacion(r.nombre, c, t, est.cauce) else r.nombre)
        Pastilla(if (aviso != null) "Aviso hidrológico ${est.cauce.color} de SENAMHI" else t?.etiqueta ?: "Sin estación de ANA", Paleta.cauce(est.cauce.estado))
        r.departamento?.let { LineaFuente(it) }
        if (aviso != null) {
            val hasta = Tiempo.parsearMs(aviso.fin)?.let { ", vigente hasta el ${Tiempo.horaCorta(it)}" } ?: ""
            Parrafo("Hay un aviso hidrológico ${est.cauce.color} de SENAMHI para este río (N.º ${aviso.numero ?: "?"}$hasta). SIMPAC resalta todo el trazo con el color del aviso; el aviso no dice qué tramo abarca.")
            if (t != null && c != null) Parrafo("Última medición de ANA en ${c.estacion}: ${t.frase}")
        } else if (t != null) {
            Parrafo(t.frase)
        } else {
            Parrafo("ANA no tiene una estación de caudal en este río.")
        }
        t?.accion?.let { Text(it, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold) }
        if (t != null && c != null) {
            LineaFuente("Estación ${c.estacion} (ANA)${if (r.lecturas.size > 1) "; el trazo toma el estado de la peor de sus ${r.lecturas.size} estaciones (${Cauces.lista(r.lecturas.map { it.estacion }, 4)})" else ""}")
            FilasAna(t, c.unidad)
            LineaFuente("Medido: ${Cauces.lecturaRio(c) ?: "sin fecha"}")
        }
        Parrafo("Si SIMPAC estimó zonas que este río podría afectar (con el relieve; no es un mapa oficial) se ven en la capa \"Zonas que podrían inundarse\" al acercarse (zoom ${Cauces.ZONAS_DESDE}).")
        aviso?.url?.takeIf { it.startsWith("https://") }?.let { url ->
            Button(onClick = { Intents.abrirNavegador(contexto, url) }) { Text("Ver el aviso de SENAMHI") }
        }
        LineaFuente("Trazo del río: ${r.fuente ?: "ANA - GeoSNIRH"}${r.licencia?.let { " (${Cauces.licenciaCorta(it)})" } ?: ""}${r.km?.let { "; ${Cauces.num(it)} km" } ?: ""}.")
        LineaFuente("Niveles de ANA leídos el ${Tiempo.horaCorta(obtenidoEn)}.")
    }
}

@Composable
private fun HojaMashcon(m: MashconDibujo, obtenidoEn: Long?) {
    val contexto = LocalContext.current
    Hoja {
        val c = m.caudal
        val t = m.estado.t
        Titulo(if (c != null && t != null) Cauces.resumenEstacion(m.nombre, c, t, m.cauceEstado) else m.nombre)
        Pastilla(m.estado.nivel.titulo, Paleta.zona(m.estado.nivel))
        m.rio.departamento?.let { LineaFuente(it) }
        m.estado.senales.forEach { s ->
            Text(s.titulo, style = MaterialTheme.typography.titleMedium)
            Parrafo(s.texto)
        }
        if (m.estado.senales.isEmpty()) Parrafo(t?.frase ?: "Hoy el río no tiene señales de crecida.")
        m.estado.menciones.forEach { LineaFuente(it) }
        if (c != null && t != null) { FilasAna(t, c.unidad); LineaFuente("Medido: ${Cauces.lecturaRio(c) ?: "sin fecha"}") }
        Parrafo("Las franjas junto al río marcan la zona que podría afectar si se desborda (capa \"Zonas que podrían inundarse\").")
        m.estado.avisoHidro?.url?.takeIf { it.startsWith("https://") }?.let { url ->
            Button(onClick = { Intents.abrirNavegador(contexto, url) }) { Text("Ver el aviso de SENAMHI") }
        }
        LineaFuente("Fuente: ANA (nivel) y SENAMHI (avisos), leídos el ${Tiempo.horaCorta(obtenidoEn)}. Trazo del río: ${m.fuenteCauce}.")
    }
}

private val QUE_ES = mapOf(
    "bajo_2m" to "Terreno que queda menos de 2 m por encima del río: si el río se desborda, es lo primero que podría inundarse.",
    "bajo_3m" to "Terreno entre 2 y 3 m por encima del río: podría inundarse con una crecida mayor; es la franja más incierta.",
)

@Composable
private fun HojaZona(z: ZonaDibujo, obtenidoEn: Long?) {
    val contexto = LocalContext.current
    Hoja {
        val titulo = when {
            z.tipo == "estudio" -> "Zona inundable según el estudio INDECI-PNUD 2005 - ${z.nombreRio}"
            z.subtipo == "bajo_2m" -> "Zona baja junto al río - ${z.nombreRio}"
            else -> "Zona algo más alta - ${z.nombreRio}"
        }
        Titulo(titulo)
        Pastilla(z.estadoZona.nivel.titulo, Paleta.zona(z.nivel))
        if (z.tipo == "estimada") {
            Text("Zona que podría inundarse si el río se desborda - estimación de SIMPAC con el relieve (Copernicus), no es un mapa oficial.", style = MaterialTheme.typography.titleMedium)
            QUE_ES[z.subtipo]?.let { Parrafo(it) }
        } else {
            Text("Mapa de inundaciones del estudio INDECI-PNUD 2005, pasado a coordenadas por SIMPAC; no es un mapa oficial vigente.", style = MaterialTheme.typography.titleMedium)
            z.texto?.let { Parrafo(it) }
        }
        val principal = z.estadoZona.senales.firstOrNull()
        if (principal != null) Parrafo("${principal.titulo}. ${principal.texto}")
        else Parrafo("Hoy el río no tiene señales de crecida: la zona sigue siendo una zona que podría inundarse.")
        when (z.estadoZona.nivel) {
            NivelZona.EMERGENCIA -> Text(Cauces.ACCION_EMERGENCIA, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            NivelZona.ALERTA -> Text(Cauces.ACCION_ALERTA, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            else -> {}
        }
        z.areaKm2?.let { LineaFuente("Superficie: ${Cauces.num(it)} km²") }
        z.estacion?.let { LineaFuente("Estación de ANA que manda: $it") }
        z.metodo?.let { LineaFuente("Método: $it") }
        z.nota?.let { LineaFuente(it) }
        z.fuente?.let { LineaFuente("Relieve: $it${z.licencia?.let { l -> " ($l)" } ?: ""}.") }
        z.atribucion?.let { LineaFuente(it) }
        LineaFuente("Señales de ANA y SENAMHI leídas el ${Tiempo.horaCorta(obtenidoEn)}. Ante una emergencia sigue las indicaciones de Defensa Civil (INDECI).")
        z.estadoZona.avisoHidro?.url?.takeIf { it.startsWith("https://") }?.let { url ->
            Button(onClick = { Intents.abrirNavegador(contexto, url) }) { Text("Ver el aviso de SENAMHI") }
        }
    }
}

@Composable
private fun HojaEstacion(e: EstacionSenamhi, obtenidoEn: Long?) {
    Hoja {
        Titulo(e.nombre ?: e.cod)
        Pastilla(when (e.tipo) { "M" -> "Estación meteorológica"; "H" -> "Estación hidrológica"; else -> "Estación" }, Paleta.ESTACION[e.tipo] ?: Paleta.SIN_DATO)
        e.departamento?.let { Parrafo("Departamento: $it") }
        e.estado?.let { LineaFuente("Tipo según SENAMHI: ${it.lowercase()}") }
        LineaFuente("Código ${e.cod}. Fuente: SENAMHI, red de estaciones; leída el ${Tiempo.horaCorta(obtenidoEn)}.")
    }
}

@Composable
private fun HojaAcudir(p: PuntoAcudir, obtenidoEn: Long?) {
    val contexto = LocalContext.current
    Hoja {
        Titulo(p.nombre)
        Pastilla(Acudir.etiquetaTipo(p.tipo), Paleta.acudir(p.tipo))
        p.categoria?.takeIf { it != Acudir.etiquetaTipo(p.tipo) }?.let { Parrafo(it) }
        if (p.atiende_24h == true) Text("Atiende las 24 horas, según la fuente.", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
        val donde = listOfNotNull(p.direccion, p.distrito?.takeIf { it != p.direccion }).joinToString(", ")
        if (donde.isNotBlank()) Parrafo("Dónde: $donde")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (!p.telefono.isNullOrBlank()) Button(onClick = { Intents.marcar(contexto, p.telefono) }) { Text("Llamar ${p.telefono}") }
            if (p.lat != null && p.lon != null) OutlinedButton(onClick = { Intents.comoLlegar(contexto, p.lat, p.lon, p.nombre) }) { Text("Cómo llegar") }
        }
        if (p.telefono.isNullOrBlank()) LineaFuente("Sin teléfono en la fuente: si es urgente llama al 105 o al 116.")
        val fecha = p.actualizado?.let { " (${Tiempo.fechaLarga(it)})" } ?: ""
        LineaFuente(when (p.tipo) {
            "comisaria" -> "Fuente: MININTER, padrón de comisarías de noviembre de 2019 vía CENEPRED; puede haber cambios."
            "bomberos" -> "Fuente: CGBVP$fecha; ubicación de CENEPRED/COEN."
            "salud" -> "Fuente: SUSALUD, RENIPRESS$fecha."
            else -> "Fuente: ${p.fuente ?: "no indicada"}$fecha."
        })
        LineaFuente("Leído el ${Tiempo.horaCorta(obtenidoEn)}.")
    }
}


// ---------------------------------------------------------------------------
// Capas nuevas: pronostico por localidad, nowcasting, lluvia de la hora, El Nino, desbordes,
// reportes de la comunidad y franja de atencion (textos de las capas de la web).
// ---------------------------------------------------------------------------

@Composable
private fun GlifoTiempo(glifo: String, tamano: Int = 28) {
    val res = LocalContext.current.resources
    val bmp = remember(glifo) { IconosMapa.glifoLeyenda(res, glifo).bitmap.asImageBitmap() }
    Image(bmp, contentDescription = null, modifier = Modifier.size(tamano.dp))
}

@Composable
private fun HojaLocalidad(sel: Seleccion.Localidad, obtenidoEn: Long?) {
    val contexto = LocalContext.current
    val f = sel.fila
    val a = PronosticoMapa.aspecto(f)
    val hoy = Tiempo.hoyPeru()
    Hoja {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            GlifoTiempo(a.glifo, 40)
            Column {
                Titulo(f.nombre ?: f.codigo)
                LineaFuente("Pronóstico de SENAMHI${f.emision?.let { " · ${PronosticoMapa.emitidoTexto(it, hoy).lowercase()}" } ?: ""}${if (sel.tuya) " · tu localidad" else ""}")
            }
        }
        Text("${PronosticoMapa.diaConFecha(f.fecha ?: "", hoy)}: ${a.corto}${a.extra?.let { " ($it)" } ?: ""}", style = MaterialTheme.typography.titleMedium)
        val t = listOfNotNull(f.tmax?.let { "Máxima $it °C" }, f.tmin?.let { "Mínima $it °C" })
        if (t.isNotEmpty()) Parrafo(t.joinToString(" · "))
        f.texto?.takeIf { it.isNotBlank() }?.let { Text("«$it» — Texto de SENAMHI para esta localidad", style = MaterialTheme.typography.bodyMedium, fontStyle = FontStyle.Italic) }
        if (f.posible && f.por != "icono") LineaFuente("SENAMHI escribe «tendencia a»: es posible, no seguro.")
        if (f.por == "icono" && f.tipo == "tormenta") LineaFuente("SENAMHI usa su ícono de tormenta; su texto solo dice lluvia.")
        if (f.por == "icono" && f.tipo == "lluvia") LineaFuente("SENAMHI usa su ícono de lluvia; su texto no la menciona.")
        // los 3 dias (hoy, manana y pasado)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
            for ((fecha, fila) in PronosticoMapa.franja(sel.propias, f.codigo, hoy)) {
                val elegido = fecha == f.fecha
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.background(if (elegido) MaterialTheme.colorScheme.secondaryContainer else Color.Transparent, RoundedCornerShape(10.dp)).padding(8.dp),
                ) {
                    Text(Tiempo.etiquetaDia(fecha, hoy), style = MaterialTheme.typography.labelMedium)
                    if (fila != null) GlifoTiempo(PronosticoMapa.aspecto(fila).glifo) else Text("?", style = MaterialTheme.typography.titleLarge)
                    Text(PronosticoMapa.temps(fila), style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        LineaFuente("Vale para esta localidad; a pocos kilómetros puede ser distinto.")
        (f.url ?: PronosticoMapa.urlLocalidad(f.codigo)).takeIf { it.startsWith("https://") }?.let { url ->
            Button(onClick = { Intents.abrirNavegador(contexto, url) }) { Text("Ver el pronóstico en SENAMHI") }
        }
        LineaFuente("Ícono y resumen de SIMPAC, basados en el texto de SENAMHI. Leído el ${Tiempo.horaCorta(obtenidoEn)}.")
    }
}

@Composable
private fun HojaNowcast(sel: Seleccion.ManchaNowcast, estado: EstadoMapa) {
    val contexto = LocalContext.current
    val m = sel.mancha
    val h = Nowcast.horizonte(sel.horizonte)
    val cerca = Nowcast.cercaDe(sel.lat, sel.lon, estado.pronostico)
    val cuando = Nowcast.lapso(m.mancha.valido_desde, m.mancha.valido_hasta)
    Hoja {
        Titulo("Lluvia ${Nowcast.NOMBRE[m.nivel] ?: ""} ${h.largo}".trim())
        Pastilla("Experimental", Nowcast.COLOR[m.nivel] ?: Nowcast.COLOR.getValue(1))
        Parrafo(if (cerca != null) "$cerca, $cuando." else cuando.replaceFirstChar { it.uppercase() } + ".")
        Parrafo(Nowcast.ACLARA)
        val emision = Tiempo.parsearMs(m.mancha.emision)
        LineaFuente("Emitido ${Nowcast.hhmm(m.mancha.emision)}${emision?.let { " (${Nowcast.textoHace(System.currentTimeMillis() - it)})" } ?: ""}")
        Button(onClick = { Intents.abrirNavegador(contexto, Nowcast.URL_VISOR) }) { Text("Ver el nowcasting en SENAMHI") }
        LineaFuente("Basado en el nowcasting de SENAMHI; colores de SIMPAC. Leído el ${Tiempo.horaCorta(estado.nowcast?.obtenidoEn)}.")
    }
}

@Composable
private fun HojaLluviaEstacion(l: LluviaDibujo, obtenidoEn: Long?) {
    val e = l.e
    val pp = e.pp_1h ?: 0.0
    val hora = Tiempo.parsearMs(e.medido_en)?.let { Tiempo.horaCorta(it) } ?: "hora desconocida"
    Hoja {
        Titulo(Lluvia.nombre(e.nombre))
        Pastilla(if (pp > 0) "Lluvia ${l.intensidad}" else "Sin lluvia en la última hora", Lluvia.color(l.intensidad))
        listOfNotNull(e.distrito, e.provincia, e.departamento).takeIf { it.isNotEmpty() }?.let { LineaFuente(it.joinToString(", ")) }
        Parrafo(if (pp > 0) "En la hora que terminó a las $hora llovió ${Lluvia.num(pp)} mm (lluvia ${l.intensidad})." else "No llovió en la hora que terminó a las $hora.")
        e.pp_6h?.let { LineaFuente("Últimas 6 h: ${Lluvia.num(it)} mm") }
        e.umbral_1h?.let { LineaFuente("Referencia de SENAMHI: ${Lluvia.num(it)} mm en 1 h${e.umbral_6h?.let { u -> " · ${Lluvia.num(u)} mm en 6 h" } ?: ""}") }
        when {
            l.ref.pasa1 -> Text("Pasó la referencia de SENAMHI para esta estación en la última hora. ${Lluvia.NO_OFICIAL}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            l.ref.pasa6 -> Text("Pasó la referencia de SENAMHI para esta estación sumando las últimas 6 horas. ${Lluvia.NO_OFICIAL}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            else -> LineaFuente("Fuente: SENAMHI.")
        }
        LineaFuente("Estación automática de SENAMHI; escala de intensidad orientativa (AEMET). Leído el ${Tiempo.horaCorta(obtenidoEn)}.")
    }
}

@Composable
private fun HojaFen(sel: Seleccion.PoligonoFen) {
    val p = sel.poligono
    val f = sel.fen
    Hoja {
        Titulo(Fen.etiqueta(f.periodo, f.trimestre))
        Pastilla(p.clase?.etiqueta ?: "Sin clase", p.clase?.color ?: Fen.COLOR_SIN_CLASE)
        Parrafo(if (!f.meses.isNullOrBlank()) "De ${f.meses}, aquí llovió ${Fen.frase(p.rango)}." else "Aquí llovió ${Fen.frase(p.rango)}.")
        LineaFuente("Rango de SENAMHI: ${p.rango ?: "no indicado"} mm frente a lo normal del trimestre.")
        LineaFuente("Fuente: SENAMHI (IDESEP). Lluvia de un trimestre del evento frente a lo normal; cada evento y cada trimestre fue distinto.")
    }
}

@Composable
private fun HojaIncidentes(sel: Seleccion.Incidentes, obtenidoEn: Long?) {
    val contexto = LocalContext.current
    val lista = sel.grupo.incidentes
    val primero = lista.first()
    val unLugar = lista.all { it.lugar == primero.lugar }
    Hoja {
        Titulo(if (lista.size == 1) primero.titulo else "${lista.size} incidentes ${if (unLugar) "en este lugar" else "en este tramo del río"}")
        Pastilla(Incidentes.TIPO[primero.tipo] ?: "Incidente documentado", Incidentes.COLOR_ROMBO)
        LineaFuente(listOfNotNull(sel.nombreRio ?: "Río", if (unLugar) primero.lugar else null).joinToString(" · "))
        lista.forEachIndexed { i, inc ->
            if (i > 0) HorizontalDivider()
            Text("${inc.fecha_texto ?: ""} · ${inc.titulo}", style = MaterialTheme.typography.titleSmall)
            if (!unLugar) LineaFuente("Lugar: ${inc.lugar ?: ""}")
            inc.detalle?.let { Parrafo(it) }
            inc.precision_texto?.let { LineaFuente("Ubicación: $it") }
            val otras = (inc.otras_fuentes as? JsonArray)?.mapNotNull { o ->
                val obj = o as? JsonObject ?: return@mapNotNull null
                val fuente = (obj["fuente"] as? JsonPrimitive)?.content ?: return@mapNotNull null
                fuente to (obj["url"] as? JsonPrimitive)?.content
            } ?: emptyList()
            LineaFuente("Fuente: ${inc.fuente ?: "no indicada"}${if (otras.isNotEmpty()) " · También: ${otras.joinToString(" · ") { it.first }}" else ""}")
            inc.fuente_url?.takeIf { it.startsWith("https://") }?.let { url ->
                OutlinedButton(onClick = { Intents.abrirNavegador(contexto, url) }) { Text("Ver la fuente") }
            }
        }
        Parrafo("Aquí el río ya causó daños: es una zona de peligro cuando el río crece. Que haya pasado antes no significa que esté pasando hoy; mira el color de la zona y los avisos de hoy.")
        LineaFuente("Solo incidentes que nombran al río en su fuente (ANA, INDECI, SENAMHI, municipio, prensa, tesis). Leído el ${Tiempo.horaCorta(obtenidoEn)}.")
    }
}

@Composable
private fun HojaReporte(r: ReporteVigente, obtenidoEn: Long?) {
    val tipo = Reportes.tipo(r.tipo)
    Hoja {
        Titulo(Reportes.titulo(r.tipo, r.subtipo))
        Pastilla(Reportes.ESTADO[r.estado] ?: "Sin confirmar", tipo.color)
        LineaFuente("Reportado el ${Tiempo.horaCorta(Tiempo.parsearMs(r.creado_en))}${Tiempo.parsearMs(r.expira_en)?.let { " · vence el ${Tiempo.horaCorta(it)}" } ?: ""}")
        r.descripcion?.takeIf { it.isNotBlank() }?.let { Parrafo(it) }
        LineaFuente("A favor: ${r.likes} · En contra: ${r.dislikes}")
        if (r.estado == "descartado") LineaFuente("La comunidad lo descartó: se sigue viendo, pero atenuado.")
        LineaFuente("Reporte de una persona de la comunidad, no verificado por una autoridad. Inicia sesión en Comunidad para votar y comentar. Leído el ${Tiempo.horaCorta(obtenidoEn)}.")
    }
}

@Composable
private fun HojaFranja(f: FranjaDibujo, obtenidoEn: Long?) {
    val contexto = LocalContext.current
    val r = f.rio
    val est = r.estado
    val aviso = if (est.cauce.porAviso) est.zona.avisoHidro else null
    val principal = est.zona.senales.firstOrNull()
    Hoja {
        Titulo("Franja de atención · ${r.nombre.replaceFirstChar { it.lowercase() }}")
        Pastilla(if (aviso != null) "Aviso hidrológico ${est.cauce.color} (SENAMHI)" else "${est.t?.etiqueta ?: "Sin estación de ANA"} (ANA)", Paleta.cauce(est.cauce.estado))
        LineaFuente(listOfNotNull(est.peor?.let { "Estación ${it.estacion}" }, r.departamento).joinToString(" · "))
        if (principal != null) Parrafo("${principal.titulo}. ${principal.texto}")
        when (est.zona.nivel) {
            NivelZona.EMERGENCIA -> Text(Cauces.ACCION_EMERGENCIA, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            NivelZona.ALERTA -> Text(Cauces.ACCION_ALERTA, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            else -> {}
        }
        Parrafo("La franja punteada es una banda de ancho fijo a cada lado del trazo de ANA que marca el entorno inmediato del río que hay que vigilar; no es un mapa de inundación ni dice hasta dónde llegaría el agua.${f.anchoM?.let { " Aquí mide $it m a cada lado del trazo (según el largo del río)." } ?: ""}")
        LineaFuente("Trazo del río: ${r.fuente ?: "ANA - GeoSNIRH"}${r.licencia?.let { " (${Cauces.licenciaCorta(it)})" } ?: ""}.")
        LineaFuente("Ante una emergencia sigue las indicaciones de Defensa Civil (INDECI). Señales leídas el ${Tiempo.horaCorta(obtenidoEn)}.")
        aviso?.url?.takeIf { it.startsWith("https://") }?.let { url ->
            Button(onClick = { Intents.abrirNavegador(contexto, url) }) { Text("Ver el aviso de SENAMHI") }
        }
    }
}

// ---------------------------------------------------------------------------
// Hoja "Capas": grupos como en la web, un interruptor por capa con su leyenda, su nota y, si la tiene,
// su selector (cuando, periodo, evento y trimestre).
// ---------------------------------------------------------------------------

/** Lo que la hoja "Capas" le pide al ViewModel. */
class AccionesCapas(
    val alternar: (Capa) -> Unit,
    val elegirHorizonte: (Int) -> Unit,
    val elegirLluviaObservada: (String) -> Unit,
    val elegirFen: (String) -> Unit,
)

@Composable
fun HojaCapas(estado: EstadoMapa, acciones: AccionesCapas) {
    val capas = estado.capas
    Hoja {
        Titulo("Capas del mapa")
        LineaFuente("Arriba del mapa, Hoy / Mañana / Pasado mueve a la vez los avisos y el pronóstico.")
        for (grupo in GruposCapa.ORDEN) {
            val delGrupo = Capa.entries.filter { it.grupo == grupo }
            if (delGrupo.isEmpty()) continue
            Text(grupo, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 6.dp))
            for (capa in delGrupo) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            // el texto cede ancho y la insignia no se parte letra por letra
                            Text(capa.etiqueta, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f, fill = false))
                            capa.insignia?.let { Insignia(it) }
                        }
                        if (capa.desdeZoom > 0) LineaFuente("Se ve al acercar el mapa (zoom ${capa.desdeZoom.toInt()} o más).")
                    }
                    Switch(checked = capa in capas, onCheckedChange = { acciones.alternar(capa) })
                }
                if (capa in capas) Selector(capa, estado, acciones)
                estado.nota(capa)?.let { Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)) }
                Leyenda(capa, estado)
                HorizontalDivider()
            }
        }
        Text("Fuentes", style = MaterialTheme.typography.labelLarge)
        (estado.fuentes + estado.avisosParciales).forEach { LineaFuente(it) }
        LineaFuente(Lluvia.ATRIBUCION_SENAMHI)
        Spacer(Modifier.height(4.dp))
    }
}

@Composable
private fun Insignia(texto: String) {
    val oficial = texto == "Oficial"
    Text(
        texto, style = MaterialTheme.typography.labelSmall, maxLines = 1, softWrap = false,
        color = if (oficial) Color(0xFF166534) else Color(0xFF6D28D9),
        modifier = Modifier.background(if (oficial) Color(0xFFDCFCE7) else Color(0xFFEDE9FE), RoundedCornerShape(999.dp)).padding(horizontal = 6.dp, vertical = 1.dp),
    )
}

/** Un selector de opciones (chips) con su etiqueta. */
@Composable
private fun Opciones(etiqueta: String, valores: List<Pair<String, String>>, elegido: String, elegir: (String) -> Unit) {
    Text(etiqueta, style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(start = 4.dp))
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        for ((valor, texto) in valores) FilterChip(selected = valor == elegido, onClick = { elegir(valor) }, label = { Text(texto) })
    }
}

@Composable
private fun Selector(capa: Capa, estado: EstadoMapa, acciones: AccionesCapas) {
    when (capa) {
        Capa.NOWCAST -> Opciones("Cuándo", Nowcast.HORIZONTES.map { it.minutos.toString() to it.etiqueta }, estado.nowcastHorizonte.toString()) { acciones.elegirHorizonte(it.toInt()) }
        Capa.LLUVIA_OBSERVADA -> Opciones("Periodo", Lluvia.OBSERVADA.map { it.clave to it.etiqueta }, estado.lluviaObsOpcion, acciones.elegirLluviaObservada)
        Capa.FEN -> Opciones("Evento y trimestre", Fen.OPCIONES.map { it.valor to it.etiqueta }, estado.fenOpcion, acciones.elegirFen)
        else -> {}
    }
}

@Composable
private fun Muestra(color: Long, texto: String, linea: Boolean = false, zona: Boolean = false, rombo: Boolean = false, anillo: Boolean = false, punteado: Boolean = false) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 2.dp)) {
        when {
            linea -> Box(Modifier.width(18.dp).height(5.dp).background(Color(color), RoundedCornerShape(3.dp)))
            zona -> Box(Modifier.size(16.dp).background(Color(color).copy(alpha = 0.55f), RoundedCornerShape(3.dp)).border(1.dp, Color(color), RoundedCornerShape(3.dp)))
            rombo -> Box(Modifier.size(14.dp).rotate(45f).background(Color(color), RoundedCornerShape(2.dp)))
            anillo -> Box(Modifier.size(14.dp).border(3.dp, Color(color), CircleShape))
            punteado -> Box(Modifier.size(14.dp).border(2.dp, Color(color), CircleShape).background(Color.White, CircleShape))
            else -> Box(Modifier.size(14.dp).background(Color(color), CircleShape))
        }
        Spacer(Modifier.width(8.dp))
        Text(texto, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun MuestraGlifo(glifo: String, texto: String, punteado: Boolean = false) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 2.dp)) {
        Box(
            Modifier.size(26.dp).background(Color.White, CircleShape)
                .border(if (punteado) 2.dp else 1.dp, if (punteado) Color(0xFF475569) else Color(0xFFCBD5E1), CircleShape),
            contentAlignment = Alignment.Center,
        ) { GlifoTiempo(glifo, 18) }
        Spacer(Modifier.width(8.dp))
        Text(texto, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun Leyenda(capa: Capa, estado: EstadoMapa) {
    Column(Modifier.padding(start = 4.dp, bottom = 6.dp)) {
        when (capa) {
            Capa.AVISOS -> {
                Muestra(Paleta.aviso(2), "Amarillo (nivel 2 de 4)", zona = true)
                Muestra(Paleta.aviso(3), "Naranja (nivel 3 de 4)", zona = true)
                Muestra(Paleta.aviso(4), "Rojo (nivel 4 de 4, el más grave)", zona = true)
                LineaFuente("El ícono (gota, gota con rayo, copo, termómetro, viento) marca la zona del aviso, no el lugar exacto. Áreas basadas en los avisos oficiales de SENAMHI (simplificadas); si solo ves la gota, abre el aviso: puede mencionar rayos para una parte.")
            }
            Capa.PRONOSTICO -> {
                MuestraGlifo("lluvia", "Lluvia")
                MuestraGlifo("tendencia", "Puede llover (SENAMHI: «tendencia a»)", punteado = true)
                MuestraGlifo("tormenta", "Tormenta")
                MuestraGlifo("nieve", "Nieve o granizo")
                MuestraGlifo("sol_nube", "Sin lluvia")
                Muestra(0xFF0F172A, "Aro negro: tu localidad", anillo = true)
                LineaFuente("Pronóstico oficial de SENAMHI para cada localidad (hoy, mañana y pasado), no para toda la zona. Donde no hay ícono, SENAMHI no publica pronóstico: no quiere decir que no llueva. Ícono y resumen de SIMPAC.")
            }
            Capa.NOWCAST -> {
                for (n in 1..3) Muestra(Nowcast.COLOR.getValue(n), Nowcast.ETIQUETA.getValue(n), zona = true)
                LineaFuente(Nowcast.FUENTE)
            }
            Capa.LLUVIA_AHORA -> {
                Muestra(Lluvia.COLORES.getValue("sin lluvia"), "No llovió en la última hora")
                Muestra(Lluvia.COLORES.getValue("ligera"), "Lluvia ligera (hasta 2 mm)")
                Muestra(Lluvia.COLORES.getValue("moderada"), "Moderada (2 a 15 mm)")
                Muestra(Lluvia.COLORES.getValue("fuerte"), "Fuerte (15 a 30 mm)")
                Muestra(Lluvia.COLORES.getValue("muy fuerte"), "Muy fuerte (30 a 60 mm)")
                Muestra(Lluvia.COLORES.getValue("torrencial"), "Torrencial (más de 60 mm)")
                Muestra(Lluvia.BORDE_REFERENCIA, "Borde amarillo: pasó la referencia de SENAMHI de esa estación (1 h o 6 h); no es un aviso oficial", anillo = true)
                LineaFuente("Lluvia de la última hora en estaciones automáticas de SENAMHI. Escala de intensidad orientativa (AEMET). La referencia es la que SENAMHI usa para cada estación; no es un aviso oficial.")
            }
            Capa.LLUVIA_OBSERVADA -> {
                for ((color, texto) in Lluvia.leyendaObservada(Lluvia.observada(estado.lluviaObsOpcion))) Muestra(color, texto, zona = true)
                LineaFuente("Lluvia medida por SENAMHI e interpolada entre sus estaciones (imágenes del servidor de mapas de SENAMHI, IDESEP).")
            }
            Capa.SATELITE -> {
                for ((color, texto) in Lluvia.LEYENDA_SATELITE) Muestra(color, texto, zona = true)
                LineaFuente("Estimación satelital NASA GPM IMERG (Early): en la sierra puede quedarse corta. Imágenes: NASA Global Imagery Browse Services (GIBS), parte de ESDIS.")
            }
            Capa.RIOS -> {
                Muestra(Paleta.cauce(EstadoCauce.NORMAL), "Azul: río tranquilo (trazo de ANA)", linea = true)
                Muestra(Paleta.cauce(EstadoCauce.ATENTO), "Ámbar: cerca del nivel de alerta (criterio SIMPAC)", linea = true)
                Muestra(Paleta.cauce(EstadoCauce.ALERTA), "Naranja: pasó el nivel de alerta (ANA) o aviso hidrológico naranja", linea = true)
                Muestra(Paleta.cauce(EstadoCauce.EMERGENCIA), "Rojo: pasó el nivel de emergencia o aviso hidrológico rojo", linea = true)
                Muestra(Paleta.cauce(EstadoCauce.SD), "Gris: sin nivel de alerta publicado; en vista país, los ríos sin alerta", linea = true)
                Muestra(Paleta.rio(EstadoCauce.NORMAL), "Disco: estación de caudal de ANA, con el color de su estado")
                LineaFuente("Nombres de los ríos desde zoom ${Cauces.ROTULOS_DESDE}; trazo fino desde zoom ${Cauces.DETALLE_DESDE}.")
            }
            Capa.ZONAS -> {
                Muestra(Paleta.zonaOscuro(NivelZona.SIN_SENALES), "Rayada con borde oscuro: terreno bajo junto al río (menos de ~2 m); lisa tenue: algo más alto (~3 m)")
                Muestra(Paleta.zona(NivelZona.SIN_SENALES), "Azul: hoy sin señales de crecida")
                Muestra(Paleta.zona(NivelZona.ATENTOS), "Ámbar: señales de crecida o lluvia fuerte en su cuenca")
                Muestra(Paleta.zona(NivelZona.ALERTA), "Naranja: el río pasó su nivel de alerta o hay aviso hidrológico naranja")
                Muestra(Paleta.zona(NivelZona.EMERGENCIA), "Rojo: pasó su nivel de emergencia o aviso hidrológico rojo")
                Muestra(Paleta.zona(NivelZona.ALERTA), "Contorno punteado con relleno suave: franja de atención junto al río (referencial, no es un mapa de inundación); solo con el río en alerta o emergencia, desde zoom ${Cauces.DETALLE_DESDE}", punteado = true)
                LineaFuente("Estimación de SIMPAC con el relieve (Copernicus GLO-30); el Mashcón tiene además el estudio INDECI-PNUD 2005. Trazo y franja de los ríos del país: ANA - GeoSNIRH. No son mapas oficiales: marcan dónde mirar, no hasta dónde llegará el agua.")
            }
            Capa.DESBORDES -> {
                Muestra(Incidentes.COLOR_ROMBO, "Desborde, erosión o puente caído documentado (con su año)", rombo = true)
                LineaFuente("Solo incidentes que nombran al río Mashcón en su fuente: ANA, INDECI, SENAMHI, Municipalidad Provincial de Cajamarca, Red Integrada de Salud Cajamarca, DesInventar, RPP, SOLTV y tesis UNC. Cada rombo cita la suya.")
            }
            Capa.ESTACIONES -> {
                Muestra(Paleta.ESTACION.getValue("M"), "Estación meteorológica de SENAMHI")
                Muestra(Paleta.ESTACION.getValue("H"), "Estación hidrológica de SENAMHI")
            }
            Capa.FEN -> {
                for (c in Fen.CLASES) Muestra(c.color, c.etiqueta, zona = true)
                LineaFuente("Lluvia de un trimestre del evento frente a lo normal; SENAMHI publica cada evento en trimestres (dic a feb, ene a mar, feb a abr) y aquí se elige cuál ver. SENAMHI (IDESEP).")
            }
            Capa.REPORTES -> {
                for (t in Reportes.TIPOS) Muestra(t.color, t.etiqueta)
                LineaFuente("Reportes de personas de la comunidad (vigentes); un reporte descartado por la comunidad se sigue viendo, pero atenuado.")
            }
            Capa.ACUDIR -> {
                Muestra(Paleta.acudir("salud"), "Hospital, centro o puesto de salud (SUSALUD)")
                Muestra(Paleta.acudir("comisaria"), "Comisaría PNP (padrón MININTER 2019)")
                Muestra(Paleta.acudir("bomberos"), "Compañía de bomberos (CGBVP)")
                Muestra(Paleta.acudir("otro"), "Oficina de Defensa Civil")
            }
        }
    }
}
