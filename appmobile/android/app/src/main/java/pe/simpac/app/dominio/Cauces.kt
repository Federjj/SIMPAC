package pe.simpac.app.dominio

import pe.simpac.app.data.AvisoHidro
import pe.simpac.app.data.AvisoLluviaSenal
import pe.simpac.app.data.CaudalActual
import pe.simpac.app.data.LluviaCuenca
import pe.simpac.app.data.RioCauceMapa
import pe.simpac.app.data.RioVigiladoMapa
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale

/** Estado del cauce y del disco de una estacion de rio (lib/lenguaje.js textoRio). "atento" es criterio de SIMPAC. */
enum class EstadoCauce(val clave: String, val orden: Int, val etiqueta: String) {
    SD("sd", 0, "Sin nivel de alerta"),
    NORMAL("normal", 1, "Tranquilo"),
    ATENTO("atento", 2, "Atento"),
    ALERTA("alerta", 3, "En alerta"),
    EMERGENCIA("emergencia", 4, "En emergencia"),
}

/** Nivel de una zona que un rio podria afectar (lib/zonaRio.js estadoZona). */
enum class NivelZona(val clave: String, val orden: Int, val titulo: String) {
    SIN_SENALES("sin_senales", 0, "Sin señales ahora"),
    ATENTOS("atentos", 1, "Atentos"),
    ALERTA("alerta", 2, "El río pasó su nivel de alerta"),
    EMERGENCIA("emergencia", 3, "El río pasó su nivel de emergencia"),
}

/** Todo lo que el mapa dice de una estacion de rio: estado (color), etiqueta, frase, si vigila nivel bajo y los umbrales. */
data class TextoRio(
    val titulo: String,
    val estado: EstadoCauce,
    val etiqueta: String,
    val frase: String,
    val bajo: Boolean,
    val accion: String?,
    val ua: Double?,
    val ue: Double?,
    val esCaudal: Boolean,
)

/** Una senal de la zona de un rio con su nivel y su explicacion. */
data class SenalZona(val clave: String, val nivel: NivelZona, val titulo: String, val texto: String, val url: String? = null)

/** Resultado de estadoZona: nivel de la zona, senales ordenadas (la mas alta primero), menciones y el aviso hidrologico que manda. */
data class EstadoZona(
    val nivel: NivelZona,
    val t: TextoRio?,
    val senales: List<SenalZona>,
    val menciones: List<String>,
    val avisoHidro: AvisoHidro?,
)

/** Estado que muestran el cauce y el disco: el de ANA o, si es mas alto, el del aviso hidrologico. */
data class EstadoCauceRio(val estado: EstadoCauce, val porAviso: Boolean, val color: String?)

/** Estado de un rio del pais con trazo (lib/cauces.js estadoRio). */
data class EstadoRio(val peor: CaudalActual?, val t: TextoRio?, val zona: EstadoZona, val cauce: EstadoCauceRio)

/** Un rio del pais emparejado con sus lecturas de ANA. */
data class RioConLecturas(val fila: RioCauceMapa, val lecturas: List<CaudalActual>)

data class Emparejados(val rios: List<RioConLecturas>, val sinTrazo: List<CaudalActual>)

/**
 * Logica de los rios del mapa: el mismo criterio que la web (frontend/src/lib/lenguaje.js textoRio,
 * lib/zonaRio.js estadoZona/estadoCauce y lib/cauces.js estadoRio/emparejarCauces). Modulo puro.
 */
object Cauces {
    const val DETALLE_DESDE = 13      // trazo fino (~6 m) de los rios a la vista desde este zoom
    const val ROTULOS_DESDE = 11      // nombres de los rios a la vista desde este zoom
    const val MAX_ROTULOS = 8
    const val ZONAS_DESDE = 12        // zonas estimadas de los rios a la vista desde este zoom
    const val ESTACIONES_DESDE = 10   // estaciones de SENAMHI
    const val ACUDIR_DESDE = 11       // puntos de "A donde acudir"

    private val COLOR = mapOf(2 to "amarillo", 3 to "naranja", 4 to "rojo")
    private val DE_AVISO = mapOf(2 to NivelZona.ATENTOS, 3 to NivelZona.ALERTA, 4 to NivelZona.EMERGENCIA)
    private val CAUCE_DE_AVISO = mapOf(2 to EstadoCauce.ATENTO, 3 to EstadoCauce.ALERTA, 4 to EstadoCauce.EMERGENCIA)
    private val TENDENCIA = mapOf("Ascendente" to "subiendo", "Descendente" to "bajando", "Estable" to "estable")
    const val NOTA_ATENTO = "“Cerca” es un criterio de SIMPAC (80 % del caudal de alerta, o menos de 50 cm del nivel), no un aviso de ANA."
    const val ACCION_ALERTA = "Aléjate de la orilla y no cruces el río."
    const val ACCION_EMERGENCIA = "Aléjate de la orilla, no cruces el río y sigue las indicaciones de Defensa Civil."

    private val formato = DecimalFormat("#,##0.##", DecimalFormatSymbols(Locale.US))

    /** "938.54", "0.13", "8,130.38" (como toLocaleString("es-PE") en la web). */
    fun num(v: Double?): String = if (v == null) "" else formato.format(v)

    fun sinTildes(s: String?): String = Departamentos.sinTildes(s ?: "").lowercase().trim()

    fun colorAviso(nivel: Int?): String? = COLOR[nivel]

    private fun distancia(metros: Double): String =
        if (metros < 1) "${Math.round(metros * 100)} cm" else "${num(metros)} m"

    /** Puerto de lib/lenguaje.js textoRio: estado (color), etiqueta y frase de una estacion de ANA. */
    fun textoRio(c: CaudalActual): TextoRio {
        val esCaudal = c.unidad == "m³/s" || c.unidad == "m3/s"
        val que = if (c.rio == "Titicaca") "Lago" else "Río"
        val titulo = if (!c.rio.isNullOrBlank()) "$que ${c.rio} (${c.estacion})" else c.estacion
        val medida = c.valor?.let { "${num(it)} ${c.unidad ?: ""}".trim() }
        val tendencia = TENDENCIA[c.tendencia]
        val va = if (tendencia != null) " Está $tendencia." else ""
        val ua = c.umbral_alerta
        val ue = c.umbral_emergencia
        val unidad = c.unidad ?: ""
        fun base(estado: EstadoCauce, etiqueta: String, frase: String, bajo: Boolean = false, accion: String? = null) =
            TextoRio(titulo, estado, etiqueta, frase, bajo, accion, ua, ue, esCaudal)

        if (c.valor == null) return base(EstadoCauce.SD, "Sin medición", "ANA no tiene una medición reciente de esta estación.")
        if (ua == null) return base(EstadoCauce.SD, EstadoCauce.SD.etiqueta, "ANA no publica un nivel de alerta para esta estación. Medida: $medida.$va")

        // umbrales de nivel bajo (vaciante): el peligro es que el rio baje
        if (ue != null && ue < ua) {
            if (c.valor <= ue) return base(EstadoCauce.EMERGENCIA, "Río muy bajo", "Río muy bajo por la temporada seca: está por debajo de su nivel de emergencia por nivel bajo (${num(ue)} $unidad).$va", bajo = true, accion = "Puede dificultar la navegación y el transporte por río.")
            if (c.valor <= ua) return base(EstadoCauce.ALERTA, "Río muy bajo", "Río muy bajo por la temporada seca: está por debajo de su nivel de alerta por nivel bajo (${num(ua)} $unidad).$va", bajo = true, accion = "Puede dificultar la navegación y el transporte por río.")
            val sobra = c.valor - ua
            val atento = sobra <= 0.5 && c.tendencia == "Descendente"
            return base(
                if (atento) EstadoCauce.ATENTO else EstadoCauce.NORMAL,
                if (atento) EstadoCauce.ATENTO.etiqueta else EstadoCauce.NORMAL.etiqueta,
                "${if (atento) "Cerca de su nivel de alerta por nivel bajo" else "Tranquilo"}. Esta estación vigila que el río no baje demasiado: está ${distancia(sobra)} por encima de ese nivel (${num(ua)} $unidad).$va",
                bajo = true,
                accion = if (atento) "Revisa los avisos de SENAMHI por ríos bajos. $NOTA_ATENTO" else null,
            )
        }

        // umbrales de crecida
        if (ue != null && c.valor >= ue) return base(EstadoCauce.EMERGENCIA, EstadoCauce.EMERGENCIA.etiqueta, "Pasó su nivel de emergencia (${num(ue)} $unidad). Lleva $medida.$va", accion = ACCION_EMERGENCIA)
        if (c.valor >= ua) return base(EstadoCauce.ALERTA, EstadoCauce.ALERTA.etiqueta, "Pasó su nivel de alerta (${num(ua)} $unidad). Lleva $medida.$va", accion = ACCION_ALERTA)
        if (esCaudal) {
            val pct = c.valor / ua * 100
            val pctTxt = if (pct < 1) "menos del 1 %" else "el ${Math.round(pct)} %"
            val atento = pct >= 80
            return base(
                if (atento) EstadoCauce.ATENTO else EstadoCauce.NORMAL,
                if (atento) EstadoCauce.ATENTO.etiqueta else EstadoCauce.NORMAL.etiqueta,
                "${if (atento) "Cerca del nivel de alerta" else "Tranquilo"}. Lleva $medida, $pctTxt del caudal que activa la alerta (${num(ua)} m³/s).$va",
                accion = if (atento) NOTA_ATENTO else null,
            )
        }
        val faltan = ua - c.valor
        val atento = faltan <= 0.5 && c.rio != "Titicaca"
        return base(
            if (atento) EstadoCauce.ATENTO else EstadoCauce.NORMAL,
            if (atento) EstadoCauce.ATENTO.etiqueta else EstadoCauce.NORMAL.etiqueta,
            "${if (atento) "Cerca del nivel de alerta" else "Tranquilo"}. El agua está a $medida; le faltan ${distancia(faltan)} para el nivel de alerta (${num(ua)} $unidad).$va",
            accion = if (atento) NOTA_ATENTO else null,
        )
    }

    /** "hoy 20:00 (ANA)" / "4 nov 20:00 (ANA)": cuando se midio. */
    fun lecturaRio(c: CaudalActual, hoy: java.time.LocalDate = Tiempo.hoyPeru()): String? {
        val fecha = c.fecha ?: return null
        val dia = try {
            val f = java.time.LocalDate.parse(fecha.take(10))
            when (f.toEpochDay() - hoy.toEpochDay()) {
                0L -> "hoy"
                -1L -> "ayer"
                else -> Tiempo.fechaLarga(fecha).substringBeforeLast(' ')
            }
        } catch (_: Exception) { fecha }
        return "$dia ${c.hora ?: ""} (ANA)".replace("  ", " ")
    }

    // ---- zona y cauce (lib/zonaRio.js) ----

    private fun vencido(fin: String?, ahoraMs: Long): Boolean {
        val ms = Tiempo.parsearMs(fin) ?: return false
        return ms <= ahoraMs
    }

    /**
     * Nivel de la zona de un rio = la mas alta de sus senales: ANA (crecida), aviso hidrologico de
     * SENAMHI (crecida, vigente), aviso de lluvias naranja o rojo en curso sobre la cuenca (deja
     * "atentos") y lluvia medida sobre la referencia (tambien "atentos").
     */
    fun estadoZona(
        caudal: CaudalActual?,
        avisosHidro: List<AvisoHidro> = emptyList(),
        avisosLluvia: List<AvisoLluviaSenal> = emptyList(),
        lluviaCuenca: List<LluviaCuenca> = emptyList(),
        ahoraMs: Long = System.currentTimeMillis(),
    ): EstadoZona {
        val senales = mutableListOf<SenalZona>()
        val menciones = mutableListOf<String>()
        val t = caudal?.let { textoRio(it) }
        val unidad = caudal?.unidad ?: ""

        // 1. ANA (crecida; un rio muy bajo no se desborda)
        if (t != null && !t.bajo && caudal != null) {
            val medida = caudal.valor?.let { "${num(it)} $unidad" }
            when (t.estado) {
                EstadoCauce.EMERGENCIA -> senales += SenalZona("ana", NivelZona.EMERGENCIA, "El río pasó su nivel de emergencia (ANA)", "Lleva $medida; su nivel de emergencia es ${num(t.ue)} $unidad.")
                EstadoCauce.ALERTA -> senales += SenalZona("ana", NivelZona.ALERTA, "El río pasó su nivel de alerta (ANA)", "Lleva $medida; su nivel de alerta es ${num(t.ua)} $unidad.")
                EstadoCauce.ATENTO -> senales += SenalZona("ana", NivelZona.ATENTOS, "El río está cerca de su nivel de alerta", "${t.frase} “Cerca” es un criterio de SIMPAC, no un aviso de ANA.")
                else -> {}
            }
        }
        if (caudal == null) menciones += "ANA no tiene una medición reciente de la estación de este río."

        // 2. aviso hidrologico de SENAMHI (solo crecida, vigente)
        val hidro = avisosHidro
            .filter { it.sentido == "crecida" && DE_AVISO.containsKey(it.nivel) && !vencido(it.fin, ahoraMs) }
            .maxByOrNull { it.nivel ?: 0 }
        if (hidro != null) {
            val nivel = DE_AVISO.getValue(hidro.nivel!!)
            val valor = hidro.valor?.let { " La estación registró ${num(it)} ${if (hidro.unidad == "m3/s") "m³/s" else hidro.unidad ?: ""}." } ?: ""
            val hasta = Tiempo.parsearMs(hidro.fin)?.let { ", vigente hasta el ${Tiempo.horaCorta(it)}" } ?: ""
            senales += SenalZona("hidro", nivel, "Aviso hidrológico ${COLOR[hidro.nivel]} de SENAMHI para el río", "Aviso N.º ${hidro.numero ?: "?"}$hasta.$valor", hidro.url)
            val visto = Tiempo.parsearMs(hidro.visto_en)
            if (visto != null && ahoraMs - visto > 3 * 3_600_000L) {
                menciones += "La web de SENAMHI no responde desde el ${Tiempo.horaCorta(visto)}: este es su último aviso conocido para el río."
            }
        }
        val sinNivel = avisosHidro.firstOrNull { it.sentido == "crecida" && it.nivel == null && !vencido(it.fin, ahoraMs) }
        if (sinNivel != null && hidro == null) menciones += "SENAMHI publicó un aviso hidrológico para el río (N.º ${sinNivel.numero ?: "?"}) sin indicar su nivel."

        // 3. avisos de lluvia sobre la cuenca
        val fuerteHoy = avisosLluvia.filter { it.en_curso && (it.nivel ?: 0) >= 3 }.maxByOrNull { it.nivel ?: 0 }
        if (fuerteHoy != null) {
            val hasta = Tiempo.parsearMs(fuerteHoy.fin)?.let { "Vigente hasta el ${Tiempo.horaCorta(it)}." } ?: "Vigente hoy."
            senales += SenalZona("aviso_lluvia", NivelZona.ATENTOS, "Aviso ${COLOR[fuerteHoy.nivel]} de SENAMHI por lluvias sobre la cuenca", hasta, fuerteHoy.url)
        }
        val manana = avisosLluvia.filter { !it.en_curso && (it.nivel ?: 0) >= 3 }.maxByOrNull { it.nivel ?: 0 }
        if (manana != null) {
            val desde = Tiempo.parsearMs(manana.inicio)?.let { Tiempo.horaCorta(it) } ?: "mañana"
            menciones += "Desde el $desde rige un aviso ${COLOR[manana.nivel]} de SENAMHI por lluvias sobre la cuenca."
        }
        if (fuerteHoy == null && avisosLluvia.any { it.en_curso && it.nivel == 2 }) menciones += "Hay un aviso amarillo de SENAMHI por lluvias sobre la cuenca."

        // 4. lluvia medida en la cuenca sobre la referencia de SENAMHI
        val pasan = lluviaCuenca.filter { pasaReferencia(it) }
        if (pasan.isNotEmpty()) {
            val una = { e: LluviaCuenca ->
                if (pasa1h(e)) "${e.nombre}: ${num(e.pp_1h)} mm en la última hora (referencia de SENAMHI: ${num(e.umbral_1h)} mm)"
                else "${e.nombre}: ${num(e.pp_6h)} mm en 6 horas (referencia de SENAMHI: ${num(e.umbral_6h)} mm)"
            }
            val mas = if (pasan.size > 2) " y ${pasan.size - 2} más" else ""
            senales += SenalZona("lluvia_medida", NivelZona.ATENTOS, "Lluvia fuerte medida en la cuenca", "${pasan.take(2).joinToString("; ") { una(it) }}$mas. No es un aviso oficial.")
        }

        senales.sortByDescending { it.nivel.orden }
        val nivel = senales.maxByOrNull { it.nivel.orden }?.nivel ?: NivelZona.SIN_SENALES
        return EstadoZona(nivel, t, senales, menciones, hidro)
    }

    private fun pasa1h(e: LluviaCuenca): Boolean {
        val u = e.umbral_1h ?: return false
        val p = e.pp_1h ?: return false
        return u > 0 && p > u
    }

    private fun pasaReferencia(e: LluviaCuenca): Boolean {
        val evaluable = e.pp_1h != null && (e.umbral_1h ?: 0.0) > 0
        if (!evaluable) return false
        if (pasa1h(e)) return true
        val u6 = e.umbral_6h ?: return false
        val p6 = e.pp_6h ?: return false
        return u6 > 0 && p6 > u6
    }

    /** Estado del cauce y el disco: ANA o, si es mas alto, el aviso hidrologico. Un rio muy bajo cuenta como normal. */
    fun estadoCauce(t: TextoRio?, avisoHidro: AvisoHidro? = null): EstadoCauceRio {
        val ana = when {
            t == null -> EstadoCauce.SD
            t.bajo -> EstadoCauce.NORMAL
            else -> t.estado
        }
        val aviso = avisoHidro?.let { CAUCE_DE_AVISO[it.nivel] }
        if (aviso != null && aviso.orden > ana.orden) return EstadoCauceRio(aviso, true, COLOR[avisoHidro.nivel])
        return EstadoCauceRio(ana, false, null)
    }

    /** "san regis": la estacion que nombra el titulo de un aviso hidrologico ("... - ESTACIÓN SAN REGIS"); null si no la nombra. */
    fun estacionDeAviso(aviso: AvisoHidro?): String? {
        val m = Regex("ESTACI[OÓ]N\\s+(.+?)\\s*$", RegexOption.IGNORE_CASE).find(aviso?.titulo ?: "") ?: return null
        return sinTildes(m.groupValues[1]).replace(Regex("\\s+"), " ")
    }

    /** Si el aviso hidrologico es de esa estacion de ANA (mismo nombre, sin tildes). */
    fun avisoEsDeEstacion(aviso: AvisoHidro?, estacion: String?): Boolean {
        val de = estacionDeAviso(aviso) ?: return false
        return de == sinTildes(estacion).replace(Regex("\\s+"), " ")
    }

    // ---- rios del pais (lib/cauces.js) ----

    /** Fila de caudal_actual del rio vigilado (misma estacion y mismo rio, sin tildes). */
    fun caudalDelRio(rio: RioVigiladoMapa, caudales: List<CaudalActual>): CaudalActual? =
        caudales.firstOrNull { sinTildes(it.estacion) == sinTildes(rio.estacion_ana) && sinTildes(it.rio) == sinTildes(rio.rio_ana) }

    /** Filas de caudal_actual de un trazo: mismo rio y la estacion en su lista, sin tildes ni mayusculas. */
    fun lecturasDelCauce(fila: RioCauceMapa, caudales: List<CaudalActual>): List<CaudalActual> {
        val rio = sinTildes(fila.rio)
        val estaciones = fila.estaciones.map { sinTildes(it) }
        return caudales.filter { sinTildes(it.rio) == rio && sinTildes(it.estacion) in estaciones }
    }

    /** Empareja los trazos con las estaciones de ANA; salta los vigilados (el Mashcon se dibuja aparte). */
    fun emparejarCauces(cauces: List<RioCauceMapa>, caudales: List<CaudalActual>, vigilados: List<RioVigiladoMapa>): Emparejados {
        val conTrazo = mutableSetOf<CaudalActual>()
        val rios = mutableListOf<RioConLecturas>()
        for (fila in cauces) {
            if (fila.vigilado) continue
            val lecturas = lecturasDelCauce(fila, caudales)
            if (lecturas.any { c -> vigilados.any { v -> caudalDelRio(v, listOf(c)) != null } }) continue
            conTrazo += lecturas
            rios += RioConLecturas(fila, lecturas)
        }
        val sinTrazo = caudales.filter { c ->
            c.lat != null && c.lon != null && c !in conTrazo && vigilados.none { v -> caudalDelRio(v, listOf(c)) != null }
        }
        return Emparejados(rios, sinTrazo)
    }

    /** La estacion que manda en un rio con varias: la de peor estado de crecida (nivel bajo cuenta como normal); en empate, la primera. */
    fun peorLectura(lecturas: List<CaudalActual>): CaudalActual? {
        var peor: CaudalActual? = null
        var orden = -1
        for (c in lecturas) {
            val i = estadoCauce(textoRio(c)).estado.orden
            if (i > orden) { peor = c; orden = i }
        }
        return peor
    }

    /** Estado de un rio con trazo: zona (ANA + aviso hidrologico) y cauce (color del trazo). */
    fun estadoRio(lecturas: List<CaudalActual>, avisosHidro: List<AvisoHidro> = emptyList(), ahoraMs: Long = System.currentTimeMillis()): EstadoRio {
        val peor = peorLectura(lecturas)
        val zona = estadoZona(caudal = peor, avisosHidro = avisosHidro, ahoraMs = ahoraMs)
        val t = peor?.let { textoRio(it) }
        return EstadoRio(peor, t, zona, estadoCauce(t, zona.avisoHidro))
    }

    /** En alerta o emergencia de crecida (el trazo se ve de color aun con el mapa alejado). */
    fun esFuerte(estado: EstadoRio?): Boolean =
        estado != null && (estado.cauce.estado == EstadoCauce.ALERTA || estado.cauce.estado == EstadoCauce.EMERGENCIA)

    fun detallePorZoom(zoom: Double): String = if (zoom >= DETALLE_DESDE) "cauce" else "lejos"

    /** Que rios (rio_ana) piden sus zonas con la vista en `caja` y ese zoom: los que la tocan, desde ZONAS_DESDE. */
    fun riosParaZonas(cajasPorRio: Map<String, Caja>, caja: Caja?, zoom: Double): List<String> {
        if (zoom < ZONAS_DESDE || caja == null) return emptyList()
        return cajasPorRio.filter { GeoJson.cajasSeCruzan(it.value, caja) }.keys.toList()
    }

    /** La licencia corta para la hoja: hasta el primer punto y coma. */
    fun licenciaCorta(licencia: String?): String = (licencia ?: "").split(";")[0].trim()

    /** "A, B y C" / "A, B, C y 3 más". */
    fun lista(xs: List<String?>, maximo: Int = Int.MAX_VALUE): String {
        val u = xs.filterNotNull().filter { it.isNotBlank() }.distinct()
        val vistos = u.take(maximo)
        val resto = u.size - vistos.size
        if (resto > 0) return "${vistos.joinToString(", ")} y $resto más"
        return if (vistos.size > 1) "${vistos.dropLast(1).joinToString(", ")} y ${vistos.last()}" else vistos.firstOrNull() ?: ""
    }

    /** "Río Huallaga - tranquilo 938.54 m³/s (ANA, hoy 20:00)" para la hoja de una estacion. */
    fun resumenEstacion(nombreRio: String, c: CaudalActual, t: TextoRio, cauce: EstadoCauceRio?, hoy: java.time.LocalDate = Tiempo.hoyPeru()): String {
        val valor = c.valor?.let { "${num(it)} ${c.unidad ?: ""}".trim() }
        val cuando = lecturaRio(c, hoy)?.removeSuffix(" (ANA)")?.trim()
        val ana = if (valor != null) "ANA${if (cuando != null) ", $cuando" else ""}" else null
        if (cauce != null && cauce.porAviso) {
            return "$nombreRio - aviso hidrológico ${cauce.color} de SENAMHI" + (if (valor != null) " ($ana: ${t.etiqueta.lowercase()}, $valor)" else "")
        }
        if (valor == null) return "$nombreRio - sin medición"
        return "$nombreRio - ${t.etiqueta.lowercase()} $valor ($ana)"
    }
}
