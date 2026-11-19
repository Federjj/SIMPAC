package pe.simpac.app.dominio

import pe.simpac.app.data.LluviaSenamhiActual

/**
 * Lluvia de la ultima hora en las estaciones automaticas de SENAMHI (vista lluvia_senamhi_actual):
 * intensidad (escala orientativa de AEMET), color y tamano del circulo, y si paso la referencia de
 * SENAMHI (frontend/src/lib/lenguaje.js intensidad() y referenciaLluvia(); map/layers/lluviaAhora.js).
 */
object Lluvia {
    val COLORES: Map<String, Long> = mapOf(
        "sin lluvia" to 0xFF9CA3AF, "ligera" to 0xFF95CEF4, "moderada" to 0xFF3BA5EB,
        "fuerte" to 0xFF3B3BEB, "muy fuerte" to 0xFF7B2FBE, "torrencial" to 0xFFDB0404,
    )
    /** Radio en px de la web (se usa como dp). */
    val RADIO: Map<String, Float> = mapOf("sin lluvia" to 3f, "ligera" to 6f, "moderada" to 8f, "fuerte" to 10f, "muy fuerte" to 12f, "torrencial" to 13f)
    const val BORDE_REFERENCIA: Long = 0xFFEAB308
    const val NO_OFICIAL = "Es lo que midió la estación, no un aviso oficial. Fuente: SENAMHI."

    fun intensidad(mmHora: Double?): String? = when {
        mmHora == null -> null
        mmHora <= 0 -> "sin lluvia"
        mmHora <= 2 -> "ligera"
        mmHora <= 15 -> "moderada"
        mmHora <= 30 -> "fuerte"
        mmHora <= 60 -> "muy fuerte"
        else -> "torrencial"
    }

    data class Referencia(val evaluable: Boolean, val pasa1: Boolean, val pasa6: Boolean) { val pasa: Boolean get() = pasa1 || pasa6 }

    /** Misma regla que backend/alerts.py: mayor estricto, referencia > 0, las 6 h solo si la estacion es evaluable. */
    fun referencia(e: LluviaSenamhiActual): Referencia {
        val evaluable = e.pp_1h != null && e.umbral_1h != null && e.umbral_1h > 0
        val pasa1 = evaluable && e.pp_1h!! > e.umbral_1h!!
        val pasa6 = evaluable && e.pp_6h != null && e.umbral_6h != null && e.umbral_6h > 0 && e.pp_6h > e.umbral_6h
        return Referencia(evaluable, pasa1, pasa6)
    }

    fun color(intensidad: String?): Long = COLORES[intensidad] ?: COLORES.getValue("sin lluvia")
    fun radio(intensidad: String?, pasa: Boolean): Float {
        val r = RADIO[intensidad] ?: 3f
        return if (pasa) maxOf(r, 7f) else r
    }

    /** "12.3" con una decimal como la web (es-PE usa coma, pero el texto de la app usa punto para no confundir con la lista). */
    fun num(v: Double?): String = if (v == null) "" else Cauces.num(v)

    /** Nota de la capa: "Llovió en 6 de 219 estaciones en su última hora medida. En 1 pasó la referencia de SENAMHI." */
    fun nota(estaciones: List<LluviaSenamhiActual>): String {
        val total = estaciones.size
        if (total == 0) return "Sin lecturas de las últimas 3 horas."
        val conLluvia = estaciones.count { (it.pp_1h ?: 0.0) > 0 }
        val sobre = estaciones.count { referencia(it).pasa }
        val ref = if (sobre > 0) " En $sobre pasó la referencia de SENAMHI." else ""
        return if (conLluvia > 0) "Llovió en $conLluvia de $total estaciones en su última hora medida.$ref"
        else "No llovió en ninguna de las $total estaciones en su última hora medida.$ref"
    }

    /** "SAUSAYA" -> "Sausaya" (los nombres vienen en mayusculas). */
    fun nombre(n: String?): String = (n ?: "").lowercase().split(" ").joinToString(" ") { p -> p.replaceFirstChar { it.uppercase() } }.trim()

    // ---- lluvia observada de SENAMHI (WMS de IDESEP; map/layers/lluviaObservada.js y map/senamhi.js) ----

    const val GEOSERVER = "https://idesep.senamhi.gob.pe/geoserver"
    const val ATRIBUCION_SENAMHI = "Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) entera responsabilidad."

    data class CapaObservada(val clave: String, val etiqueta: String, val capa: String, val cortes: List<Int>, val titulo: String)
    val OBSERVADA = listOf(
        CapaObservada("ayer", "Ayer", "monitoreo_meteorologico:prec_1", listOf(1, 5, 15, 30), "en el último día procesado"),
        CapaObservada("semana", "Últimos 7 días", "monitoreo_meteorologico:prec_1_ac07d", listOf(5, 25, 75, 150), "en los últimos 7 días procesados"),
    )
    val COLORES_OBSERVADA: List<Long> = listOf(0xFF95CEF4, 0xFF3BA5EB, 0xFF3B3BEB, 0xFF7B2FBE)
    fun observada(clave: String?): CapaObservada = OBSERVADA.firstOrNull { it.clave == clave } ?: OBSERVADA.first()

    /** Leyenda de la capa observada: "1 a 5 mm", "5 a 15 mm", "15 a 30 mm", "más de 30 mm". */
    fun leyendaObservada(c: CapaObservada): List<Pair<Long, String>> {
        val (c1, c2, c3, c4) = c.cortes
        return listOf(COLORES_OBSERVADA[0] to "$c1 a $c2 mm", COLORES_OBSERVADA[1] to "$c2 a $c3 mm", COLORES_OBSERVADA[2] to "$c3 a $c4 mm", COLORES_OBSERVADA[3] to "más de $c4 mm")
    }

    /** Estilo propio (SLD) como la web: transparente bajo el primer corte y una escala de azules. */
    fun sldLluvia(capa: String, cortes: List<Int>): String {
        val (c1, c2, c3, c4) = cortes
        fun e(color: String, q: Any, op: Double) = "<ColorMapEntry color=\"$color\" quantity=\"$q\" opacity=\"$op\"/>"
        return "<StyledLayerDescriptor version=\"1.0.0\" xmlns=\"http://www.opengis.net/sld\" xmlns:ogc=\"http://www.opengis.net/ogc\">" +
            "<NamedLayer><Name>$capa</Name><UserStyle><FeatureTypeStyle><Rule><RasterSymbolizer><ColorMap type=\"intervals\">" +
            e("#000000", c1, 0.0) + e("#95CEF4", c2, 0.6) + e("#3BA5EB", c3, 0.65) + e("#3B3BEB", c4, 0.7) + e("#7B2FBE", 100000, 0.75) +
            "</ColorMap></RasterSymbolizer></Rule></FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>"
    }

    private val MESES = listOf("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic")
    /** "2026-11-18" -> "18 nov". */
    fun dia(iso: String?): String? {
        val p = (iso ?: return null).split("-")
        val m = p.getOrNull(1)?.toIntOrNull() ?: return null
        val d = p.getOrNull(2)?.toIntOrNull() ?: return null
        return "$d ${MESES.getOrNull(m - 1) ?: m}"
    }

    /** "Cuánta lluvia cayó el 18 nov (cada día va de 7:00 a 7:00), según SENAMHI." con las fechas del latido lluvia_nacional. */
    fun notaObservada(c: CapaObservada, prec1: String?, desde: String?, hasta: String?): String {
        val dias = if (c.clave == "semana") {
            val a = dia(desde); val b = dia(hasta)
            if (a != null && b != null) "del $a al $b" else c.titulo
        } else dia(prec1)?.let { "el $it" } ?: c.titulo
        return "Cuánta lluvia cayó $dias (cada día va de 7:00 a 7:00), según SENAMHI."
    }

    const val SIN_SERVIDOR = "El servidor de mapas de SENAMHI no responde ahora; la capa puede verse incompleta."

    // ---- lluvia por satelite (NASA GIBS IMERG; map/layers/lluviaSatelite.js) ----
    const val GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/IMERG_Precipitation_Rate_30min/default"
    const val GIBS_MATRIZ = "GoogleMapsCompatible_Level6"
    const val GIBS_ZOOM_MAX = 6
    const val ATRIBUCION_GIBS = "Lluvia: NASA GPM IMERG, imágenes NASA GIBS (ESDIS)"
    val LEYENDA_SATELITE: List<Pair<Long, String>> = listOf(
        0xFF45C000L to "Menos de 1 mm por hora", 0xFFFF980FL to "1 a 5 mm por hora", 0xFFFF0101L to "5 a 20 mm por hora",
        0xFF710000L to "Más de 20 mm por hora", 0xFF6DB8E1L to "Nieve (celeste a morado)",
    )

    /** Nota de la capa satelital: "Dato de las 12:30 (hace 5 h): el satélite llega con horas de retraso." */
    fun notaSatelite(horaIso: String?, zoom: Double, ahoraMs: Long = System.currentTimeMillis()): String {
        val lejos = if (zoom > 9) " Aleja el mapa para verla mejor (cada celda mide ~11 km)." else ""
        val ms = Tiempo.parsearMs(horaIso)
        return if (ms != null) "Dato de las ${Tiempo.horaCorta(ms)} (hace ${(ahoraMs - ms) / 3_600_000} h): el satélite llega con horas de retraso.$lejos"
        else "Dato más reciente disponible.$lejos"
    }
}
