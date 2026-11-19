package pe.simpac.app.dominio

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/**
 * Mapas de eventos El Nino pasados (tabla mapa, variable 'FEN'): cuanto mas (o menos) llovio que lo
 * normal en mm acumulados (SENAMHI/IDESEP). Misma lectura que frontend/src/lib/fen.js y
 * map/layers/fenHistorico.js: eventos y trimestres fijos, rangos agrupados en clases por su punto
 * medio y la frase "entre 300 y 550 mm mas de lo normal". Modulo puro (pruebas JVM).
 */
object Fen {
    data class Trimestre(val codigo: String, val corto: String)
    data class Evento(val periodo: String, val nombre: String, val trimestres: List<String>)
    data class Opcion(val valor: String, val etiqueta: String, val periodo: String, val trimestre: String)
    /** Una clase de la leyenda: hasta que diferencia (mm) llega, su color y su texto. */
    data class Clase(val hasta: Double, val color: Long, val etiqueta: String)
    /** Un poligono del mapa listo para dibujar: su rango, su clase, sus anillos (y simplificados) y su caja. */
    data class PoligonoFen(val rango: String?, val clase: Clase?, val anillos: List<List<Coord>>, val lejos: List<List<Coord>>, val caja: Caja)

    val TRIMESTRES = listOf(Trimestre("DEF", "dic a feb"), Trimestre("EFM", "ene a mar"), Trimestre("FMA", "feb a abr"))

    /** En el orden del selector; los trimestres que trae la BD el 25-10-2026 (13 filas). */
    val EVENTOS = listOf(
        Evento("1982-1983", "El Niño 1982-1983", listOf("DEF", "EFM", "FMA")),
        Evento("1997-1998", "El Niño 1997-1998", listOf("DEF", "EFM", "FMA")),
        Evento("2017", "El Niño costero 2017", listOf("DEF", "EFM", "FMA")),
        Evento("2023", "El Niño costero 2023", listOf("EFM", "FMA")),
        Evento("2023-2024", "El Niño 2023-2024", listOf("DEF", "EFM")),
    )
    const val SEPARADOR = "|"
    const val DEFECTO = "1997-1998|DEF"

    /** Rangos de SENAMHI agrupados en clases por su punto medio (layers/fenHistorico.js CLASES). */
    val CLASES = listOf(
        Clase(-300.0, 0xFF8C510A, "Mucha menos lluvia (más de 300 mm menos)"),
        Clase(-60.0, 0xFFD8B365, "Menos lluvia (60 a 300 mm menos)"),
        Clase(-30.0, 0xFFF0DDB0, "Algo menos de lluvia (30 a 60 mm menos)"),
        Clase(30.0, 0xFFE5E5E5, "Cerca de lo normal (hasta 30 mm de diferencia)"),
        Clase(60.0, 0xFFD4ECFA, "Algo más de lluvia (30 a 60 mm más)"),
        Clase(300.0, 0xFF95CEF4, "Más lluvia (60 a 300 mm más)"),
        Clase(1000.0, 0xFF3B3BEB, "Mucha más lluvia (300 a 1000 mm más)"),
        Clase(Double.POSITIVE_INFINITY, 0xFF7B2FBE, "Muchísima más lluvia (más de 1000 mm más)"),
    )
    const val COLOR_SIN_CLASE: Long = 0xFF9CA3AF

    fun valor(periodo: String, trimestre: String) = "$periodo$SEPARADOR$trimestre"

    /** "1997-1998|DEF" -> (periodo, trimestre); sin trimestre -> (periodo, null). */
    fun partir(valor: String?): Pair<String?, String?> {
        val partes = (valor ?: "").split(SEPARADOR)
        return (partes.getOrNull(0)?.takeIf { it.isNotBlank() }) to (partes.getOrNull(1)?.takeIf { it.isNotBlank() })
    }

    fun evento(periodo: String?): Evento? = EVENTOS.firstOrNull { it.periodo == periodo }
    fun mesesCortos(trimestre: String?): String = TRIMESTRES.firstOrNull { it.codigo == trimestre }?.corto ?: (trimestre ?: "")

    /** "El Niño 1997-1998, dic a feb". */
    fun etiqueta(periodo: String?, trimestre: String?): String {
        val nombre = evento(periodo)?.nombre ?: "El Niño ${periodo ?: ""}".trim()
        return if (trimestre != null) "$nombre, ${mesesCortos(trimestre)}" else nombre
    }

    /** Las opciones del selector: una por evento y trimestre, en el orden de EVENTOS. */
    val OPCIONES: List<Opcion> = EVENTOS.flatMap { e -> e.trimestres.map { t -> Opcion(valor(e.periodo, t), etiqueta(e.periodo, t), e.periodo, t) } }

    fun esValor(valor: String?): Boolean = OPCIONES.any { it.valor == valor }

    /** Un valor viejo (solo el evento) pasa al primer trimestre del evento; uno desconocido vuelve al de fabrica. */
    fun normalizar(valor: String?): String {
        if (valor == null) return DEFECTO
        if (esValor(valor)) return valor
        val e = evento(valor) ?: return DEFECTO
        return valor(e.periodo, e.trimestres.first())
    }

    private val RX_NUM = Regex("-?\\d+(\\.\\d+)?")
    fun numeros(rango: String?): List<Double> = RX_NUM.findAll((rango ?: "").replace(",", "")).map { it.value.toDouble() }.toList()

    /** Punto medio del rango ("300 - 550" -> 425; "> 2,500" -> 2500); null si no trae numeros. */
    fun medio(rango: String?): Double? {
        val n = numeros(rango)
        if (n.isEmpty()) return null
        return if (n.size == 1) n[0] else (n[0] + n[1]) / 2
    }

    /** Clase (color y texto) de un rango; null si no se entiende. */
    fun clase(rango: String?): Clase? {
        val m = medio(rango) ?: return null
        return CLASES.firstOrNull { m < it.hasta } ?: CLASES.last()
    }

    fun color(rango: String?): Long = clase(rango)?.color ?: COLOR_SIN_CLASE

    /** Relleno: la clase "cerca de lo normal" va casi transparente (25 %), el resto al 60 %. */
    fun alfa(clase: Clase?): Int = if (clase?.hasta == 30.0) 0x40 else 0x99

    /** "300 - 550" -> "entre 300 y 550 mm más de lo normal" (como la web). */
    fun frase(rango: String?): String {
        val r = (rango ?: "").trim()
        val n = numeros(r)
        if (r.startsWith("<") && n.isNotEmpty()) return "más de ${num(Math.abs(n[0]))} mm menos de lo normal"
        if (r.startsWith(">") && n.isNotEmpty()) return "más de ${num(Math.abs(n[0]))} mm más de lo normal"
        if (n.size < 2) return r
        val (a, b) = n
        if (b <= 0) return if (a == -30.0 && b == 0.0) "hasta 30 mm menos de lo normal (casi normal)" else "entre ${num(Math.abs(b))} y ${num(Math.abs(a))} mm menos de lo normal"
        if (a == 0.0) return "hasta ${num(b)} mm más de lo normal (casi normal)"
        return "entre ${num(a)} y ${num(b)} mm más de lo normal"
    }

    private fun num(v: Double): String = if (v == Math.floor(v)) v.toLong().toString() else v.toString()

    /**
     * Los poligonos de una FeatureCollection con su RANGO (cada feature por separado: GeoJson.parsear
     * junta las geometrias y perderia las propiedades). Cada uno lleva el anillo exterior completo y
     * una version simplificada para el mapa alejado; los huecos se omiten (son manchas de lluvia, no
     * importan a esa escala). Fuera del hilo principal.
     */
    fun poligonos(geojson: JsonElement?, toleranciaLejos: Double = 0.004): List<PoligonoFen> {
        val obj = geojson as? JsonObject ?: return emptyList()
        val features = obj["features"] as? JsonArray ?: return emptyList()
        val salida = ArrayList<PoligonoFen>(features.size)
        for (f in features) {
            val fo = f as? JsonObject ?: continue
            val props = fo["properties"] as? JsonObject
            val rango = (props?.get("RANGO") as? JsonPrimitive)?.content
            val geo = GeoJson.parsear(fo["geometry"]) as? Geometria.Poligonos ?: continue
            val anillos = geo.poligonos.map { it.first() }.filter { it.size >= 3 }
            if (anillos.isEmpty()) continue
            val caja = GeoJson.cajaDe(anillos.asSequence().flatten()) ?: continue
            val lejos = anillos.map { GeoJson.simplificar(it, toleranciaLejos) }.filter { it.size >= 3 }
            salida += PoligonoFen(rango, clase(rango), anillos, lejos, caja)
        }
        return salida
    }

    /** Nota de la capa: "El Niño 1997-1998, dic a feb: dónde llovió más (azul) o menos (marrón) que lo normal de diciembre de 1997 a febrero de 1998. ..." */
    fun nota(periodo: String?, trimestre: String?, meses: String?): String {
        val evento = etiqueta(periodo, trimestre)
        return if (!meses.isNullOrBlank()) "$evento: dónde llovió más (azul) o menos (marrón) que lo normal de $meses. Cada evento y cada trimestre fue distinto."
        else "$evento: dónde llovió más (azul) o menos (marrón) que lo normal en esos meses. Cada evento fue distinto."
    }
}
