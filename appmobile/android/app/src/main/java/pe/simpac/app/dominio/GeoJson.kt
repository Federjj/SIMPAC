package pe.simpac.app.dominio

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

/** Un vertice (lat, lon) en grados. GeoJSON escribe [lon, lat]; aqui siempre se lee como (lat, lon). */
data class Coord(val lat: Double, val lon: Double)

/**
 * Lo que la app dibuja a partir de un GeoJSON: un punto, lineas (LineString o MultiLineString) o
 * poligonos (Polygon o MultiPolygon). Un poligono es una lista de anillos: el primero es el borde
 * exterior y los demas, huecos. Modulo puro (sin Android ni osmdroid): lo prueban las pruebas JVM.
 */
sealed class Geometria {
    data class Punto(val punto: Coord) : Geometria()
    data class Lineas(val partes: List<List<Coord>>) : Geometria()
    data class Poligonos(val poligonos: List<List<List<Coord>>>) : Geometria()
}

object GeoJson {
    /**
     * Parser minimo de GeoJSON: Point, LineString, MultiLineString, Polygon, MultiPolygon, y tambien
     * un Feature (su geometry) o una FeatureCollection (se juntan las geometrias del mismo tipo que
     * la primera). Devuelve null si no se entiende o esta vacio; nunca lanza.
     */
    fun parsear(elemento: JsonElement?): Geometria? {
        val obj = elemento as? JsonObject ?: return null
        return try {
            when (tipo(obj)) {
                "Feature" -> parsear(obj["geometry"])
                "FeatureCollection" -> {
                    val geos = (obj["features"] as? JsonArray)?.mapNotNull { parsear(it) } ?: emptyList()
                    juntar(geos)
                }
                "Point" -> coord(obj["coordinates"])?.let { Geometria.Punto(it) }
                "LineString" -> linea(obj["coordinates"])?.takeIf { it.size >= 2 }?.let { Geometria.Lineas(listOf(it)) }
                "MultiLineString" -> {
                    val partes = (obj["coordinates"] as? JsonArray)?.mapNotNull { linea(it)?.takeIf { l -> l.size >= 2 } } ?: emptyList()
                    if (partes.isEmpty()) null else Geometria.Lineas(partes)
                }
                "Polygon" -> poligono(obj["coordinates"])?.let { Geometria.Poligonos(listOf(it)) }
                "MultiPolygon" -> {
                    val pols = (obj["coordinates"] as? JsonArray)?.mapNotNull { poligono(it) } ?: emptyList()
                    if (pols.isEmpty()) null else Geometria.Poligonos(pols)
                }
                else -> null
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun tipo(obj: JsonObject): String? = (obj["type"] as? JsonPrimitive)?.content

    private fun juntar(geos: List<Geometria>): Geometria? {
        val primera = geos.firstOrNull() ?: return null
        return when (primera) {
            is Geometria.Punto -> primera
            is Geometria.Lineas -> Geometria.Lineas(geos.filterIsInstance<Geometria.Lineas>().flatMap { it.partes })
            is Geometria.Poligonos -> Geometria.Poligonos(geos.filterIsInstance<Geometria.Poligonos>().flatMap { it.poligonos })
        }
    }

    /** [lon, lat] (con o sin altura) -> Coord; null si no son dos numeros. */
    private fun coord(e: JsonElement?): Coord? {
        val a = e as? JsonArray ?: return null
        if (a.size < 2) return null
        val lon = a[0].jsonPrimitive.doubleOrNull ?: return null
        val lat = a[1].jsonPrimitive.doubleOrNull ?: return null
        if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null
        return Coord(lat, lon)
    }

    private fun linea(e: JsonElement?): List<Coord>? {
        val a = e as? JsonArray ?: return null
        val pts = a.mapNotNull { coord(it) }
        return if (pts.isEmpty()) null else pts
    }

    /** Anillos de un Polygon: cada uno con al menos 3 vertices distintos; sin exterior valido no hay poligono. */
    private fun poligono(e: JsonElement?): List<List<Coord>>? {
        val a = e as? JsonArray ?: return null
        val anillos = a.mapNotNull { linea(it)?.takeIf { l -> l.size >= 3 } }
        return if (anillos.isEmpty()) null else anillos
    }

    /** Caja (oeste, sur, este, norte) de la geometria; null si esta vacia. */
    fun caja(g: Geometria): Caja? = when (g) {
        is Geometria.Punto -> Caja(g.punto.lon, g.punto.lat, g.punto.lon, g.punto.lat)
        is Geometria.Lineas -> cajaDe(g.partes.asSequence().flatten())
        is Geometria.Poligonos -> cajaDe(g.poligonos.asSequence().flatMap { it.firstOrNull()?.asSequence() ?: emptySequence() })
    }

    fun cajaDe(puntos: Sequence<Coord>): Caja? {
        var o = Double.POSITIVE_INFINITY; var s = Double.POSITIVE_INFINITY
        var e = Double.NEGATIVE_INFINITY; var n = Double.NEGATIVE_INFINITY
        var hay = false
        for (p in puntos) {
            hay = true
            if (p.lon < o) o = p.lon
            if (p.lon > e) e = p.lon
            if (p.lat < s) s = p.lat
            if (p.lat > n) n = p.lat
        }
        return if (hay) Caja(o, s, e, n) else null
    }

    /** Si dos cajas se tocan (bordes incluidos); false si alguna es nula. */
    fun cajasSeCruzan(a: Caja?, b: Caja?): Boolean =
        a != null && b != null && a.oeste <= b.este && a.este >= b.oeste && a.sur <= b.norte && a.norte >= b.sur

    /** La caja con un margen proporcional a cada lado (0.3 = 30 % del ancho y del alto). */
    fun cajaConMargen(c: Caja, k: Double): Caja {
        val dx = (c.este - c.oeste) * k
        val dy = (c.norte - c.sur) * k
        return Caja(c.oeste - dx, c.sur - dy, c.este + dx, c.norte + dy)
    }

    fun dentro(p: Coord, c: Caja): Boolean = p.lon >= c.oeste && p.lon <= c.este && p.lat >= c.sur && p.lat <= c.norte

    /** Area con signo (grados cuadrados, aproximacion plana) de un anillo: alcanza para comparar y centrar. */
    fun areaFirmada(anillo: List<Coord>): Double {
        var a = 0.0
        for (i in anillo.indices) {
            val p = anillo[i]
            val q = anillo[(i + 1) % anillo.size]
            a += p.lon * q.lat - q.lon * p.lat
        }
        return a / 2
    }

    /** Centroide de un anillo (promedio ponderado por area; si el area es 0, el promedio de los vertices). */
    fun centroide(anillo: List<Coord>): Coord? {
        if (anillo.isEmpty()) return null
        val a = areaFirmada(anillo)
        if (abs(a) < 1e-12) {
            return Coord(anillo.sumOf { it.lat } / anillo.size, anillo.sumOf { it.lon } / anillo.size)
        }
        var cx = 0.0; var cy = 0.0
        for (i in anillo.indices) {
            val p = anillo[i]
            val q = anillo[(i + 1) % anillo.size]
            val f = p.lon * q.lat - q.lon * p.lat
            cx += (p.lon + q.lon) * f
            cy += (p.lat + q.lat) * f
        }
        return Coord(cy / (6 * a), cx / (6 * a))
    }

    /** Centroide del poligono mas grande (por el area de su anillo exterior). */
    fun centroideMayor(g: Geometria.Poligonos): Coord? =
        g.poligonos.maxByOrNull { abs(areaFirmada(it.first())) }?.let { centroide(it.first()) }

    /** Si el punto cae dentro de algun poligono (dentro del exterior y fuera de sus huecos). */
    fun contiene(g: Geometria.Poligonos, lat: Double, lon: Double): Boolean = g.poligonos.any { pol ->
        enAnillo(pol.first(), lat, lon) && pol.drop(1).none { enAnillo(it, lat, lon) }
    }

    private fun enAnillo(anillo: List<Coord>, lat: Double, lon: Double): Boolean {
        var dentro = false
        var j = anillo.size - 1
        for (i in anillo.indices) {
            val a = anillo[i]; val b = anillo[j]
            if ((a.lat > lat) != (b.lat > lat)) {
                val x = (b.lon - a.lon) * (lat - a.lat) / (b.lat - a.lat) + a.lon
                if (lon < x) dentro = !dentro
            }
            j = i
        }
        return dentro
    }

    /**
     * Simplificacion de Douglas-Peucker de una linea con una tolerancia en grados (0.001 = ~110 m).
     * Con ella el trazo de ~50 m de los 100 rios (35 000 vertices) baja a unos cientos para el mapa
     * alejado, y se vuelve al trazo completo al acercarse. Siempre conserva los extremos.
     */
    fun simplificar(parte: List<Coord>, tolerancia: Double): List<Coord> {
        if (parte.size <= 2 || tolerancia <= 0) return parte
        val conservar = BooleanArray(parte.size)
        conservar[0] = true; conservar[parte.size - 1] = true
        val pila = ArrayDeque<Pair<Int, Int>>()
        pila.addLast(0 to parte.size - 1)
        while (pila.isNotEmpty()) {
            val (i0, i1) = pila.removeLast()
            if (i1 - i0 < 2) continue
            var mejor = -1; var dMax = 0.0
            for (i in i0 + 1 until i1) {
                val d = distanciaASegmento(parte[i], parte[i0], parte[i1])
                if (d > dMax) { dMax = d; mejor = i }
            }
            if (mejor >= 0 && dMax > tolerancia) {
                conservar[mejor] = true
                pila.addLast(i0 to mejor)
                pila.addLast(mejor to i1)
            }
        }
        return parte.filterIndexed { i, _ -> conservar[i] }
    }

    private fun distanciaASegmento(p: Coord, a: Coord, b: Coord): Double {
        val dx = b.lon - a.lon; val dy = b.lat - a.lat
        if (dx == 0.0 && dy == 0.0) return hypot(p.lon - a.lon, p.lat - a.lat)
        val t = max(0.0, min(1.0, ((p.lon - a.lon) * dx + (p.lat - a.lat) * dy) / (dx * dx + dy * dy)))
        return hypot(p.lon - (a.lon + t * dx), p.lat - (a.lat + t * dy))
    }

    /** Tolerancia de simplificacion por zoom: generosa con el pais entero, nula desde el zoom 12. */
    fun toleranciaPorZoom(zoom: Double): Double = when {
        zoom < 8 -> 0.01
        zoom < 10 -> 0.003
        zoom < 12 -> 0.0008
        else -> 0.0
    }

    /** Cuantos vertices tiene la geometria (para medir la simplificacion). */
    fun vertices(g: Geometria): Int = when (g) {
        is Geometria.Punto -> 1
        is Geometria.Lineas -> g.partes.sumOf { it.size }
        is Geometria.Poligonos -> g.poligonos.sumOf { pol -> pol.sumOf { it.size } }
    }

    /** Caja (oeste, sur, este, norte) redondeada hacia afuera a decimas de grado (clave de cache repetible). */
    fun cajaRedondeada(c: Caja, paso: Double = 0.1): Caja {
        fun abajo(v: Double) = Math.floor(v / paso) * paso
        fun arriba(v: Double) = Math.ceil(v / paso) * paso
        fun r(v: Double) = Math.round(v * 10) / 10.0
        return Caja(r(abajo(c.oeste)), r(abajo(c.sur)), r(arriba(c.este)), r(arriba(c.norte)))
    }
}
