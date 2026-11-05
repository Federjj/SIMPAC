package pe.simpac.app.ui.mapa

import androidx.compose.foundation.background
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import pe.simpac.app.data.EstacionSenamhi
import pe.simpac.app.data.PuntoAcudir
import pe.simpac.app.dominio.Acudir
import pe.simpac.app.dominio.AvisosMapa
import pe.simpac.app.dominio.Cauces
import pe.simpac.app.dominio.EstadoCauce
import pe.simpac.app.dominio.NivelZona
import pe.simpac.app.dominio.Paleta
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

/** Hoja "Capas": un interruptor por capa con su leyenda corta. */
@Composable
fun HojaCapas(capas: Set<Capa>, alternar: (Capa) -> Unit, fuentes: List<String>) {
    Hoja {
        Titulo("Capas del mapa")
        Capa.entries.forEach { capa ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(capa.etiqueta, style = MaterialTheme.typography.bodyLarge)
                    if (capa.desdeZoom > 0) LineaFuente("Se ve al acercar el mapa (zoom ${capa.desdeZoom.toInt()} o más).")
                }
                Switch(checked = capa in capas, onCheckedChange = { alternar(capa) })
            }
            Leyenda(capa)
            HorizontalDivider()
        }
        Text("Fuentes", style = MaterialTheme.typography.labelLarge)
        fuentes.forEach { LineaFuente(it) }
        Spacer(Modifier.height(4.dp))
    }
}

@Composable
private fun Muestra(color: Long, texto: String, linea: Boolean = false) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 2.dp)) {
        if (linea) Box(Modifier.width(18.dp).height(5.dp).background(Color(color), RoundedCornerShape(3.dp)))
        else Box(Modifier.size(14.dp).background(Color(color), CircleShape))
        Spacer(Modifier.width(8.dp))
        Text(texto, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun Leyenda(capa: Capa) {
    Column(Modifier.padding(start = 4.dp, bottom = 6.dp)) {
        when (capa) {
            Capa.AVISOS -> {
                Muestra(Paleta.aviso(2), "Amarillo (nivel 2 de 4)")
                Muestra(Paleta.aviso(3), "Naranja (nivel 3 de 4)")
                Muestra(Paleta.aviso(4), "Rojo (nivel 4 de 4, el más grave)")
                LineaFuente("El ícono (gota, gota con rayo, copo, termómetro, viento) marca la zona del aviso, no el lugar exacto. Áreas simplificadas de los avisos oficiales de SENAMHI.")
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
                LineaFuente("Estimación de SIMPAC con el relieve (Copernicus GLO-30); el Mashcón tiene además el estudio INDECI-PNUD 2005. No son mapas oficiales: marcan dónde mirar, no hasta dónde llegará el agua.")
            }
            Capa.ESTACIONES -> {
                Muestra(Paleta.ESTACION.getValue("M"), "Estación meteorológica de SENAMHI")
                Muestra(Paleta.ESTACION.getValue("H"), "Estación hidrológica de SENAMHI")
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
