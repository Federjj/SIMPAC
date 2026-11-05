package pe.simpac.app

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pe.simpac.app.dominio.Caja
import pe.simpac.app.dominio.Coord
import pe.simpac.app.dominio.GeoJson
import pe.simpac.app.dominio.Geometria

/** Parser GeoJSON minimo (dominio/GeoJson.kt): lo que llega de aviso_vigente, rio_cauce_mapa, rio_zona_mapa... */
class GeoJsonTest {
    private fun json(texto: String): JsonElement = Json.parseToJsonElement(texto)

    @Test
    fun point_y_linestring() {
        val p = GeoJson.parsear(json("""{"type":"Point","coordinates":[-78.5127,-7.1617]}""")) as Geometria.Punto
        assertEquals(-7.1617, p.punto.lat, 1e-9)   // GeoJSON es [lon, lat]
        assertEquals(-78.5127, p.punto.lon, 1e-9)
        val l = GeoJson.parsear(json("""{"type":"LineString","coordinates":[[1,2],[3,0,99]]}""")) as Geometria.Lineas
        assertEquals(1, l.partes.size)
        assertEquals(listOf(Coord(2.0, 1.0), Coord(0.0, 3.0)), l.partes[0])
        assertEquals(Caja(1.0, 0.0, 3.0, 2.0), GeoJson.caja(l))
    }

    @Test
    fun multilinestring_como_rio_cauce_mapa() {
        val g = GeoJson.parsear(json("""{"type":"MultiLineString","coordinates":[[[-76.2,-9.9],[-76.0,-9.5],[-75.8,-9.0]],[[-75.5,-6.0],[-75.3,-5.5]]]}""")) as Geometria.Lineas
        assertEquals(2, g.partes.size)
        assertEquals(5, GeoJson.vertices(g))
        assertEquals(Caja(-76.2, -9.9, -75.3, -5.5), GeoJson.caja(g))
    }

    @Test
    fun polygon_con_hueco_y_multipolygon() {
        val pol = GeoJson.parsear(json("""{"type":"Polygon","coordinates":[[[0,0],[10,0],[10,10],[0,10],[0,0]],[[4,4],[6,4],[6,6],[4,6],[4,4]]]}""")) as Geometria.Poligonos
        assertEquals(1, pol.poligonos.size)
        assertEquals(2, pol.poligonos[0].size)
        assertTrue(GeoJson.contiene(pol, 2.0, 2.0))
        assertFalse(GeoJson.contiene(pol, 5.0, 5.0))    // dentro del hueco
        assertFalse(GeoJson.contiene(pol, 20.0, 2.0))
        val c = GeoJson.centroideMayor(pol)!!
        assertEquals(5.0, c.lat, 1e-9)
        assertEquals(5.0, c.lon, 1e-9)
        val multi = GeoJson.parsear(json("""{"type":"MultiPolygon","coordinates":[[[[0,0],[1,0],[1,1],[0,1],[0,0]]],[[[10,10],[14,10],[14,14],[10,14],[10,10]]]]}""")) as Geometria.Poligonos
        assertEquals(2, multi.poligonos.size)
        val mayor = GeoJson.centroideMayor(multi)!!   // el segundo es 16 veces mas grande
        assertEquals(12.0, mayor.lat, 1e-9)
        assertEquals(12.0, mayor.lon, 1e-9)
        assertEquals(Caja(0.0, 0.0, 14.0, 14.0), GeoJson.caja(multi))
    }

    @Test
    fun feature_y_featurecollection() {
        val f = GeoJson.parsear(json("""{"type":"Feature","properties":{"a":1},"geometry":{"type":"Point","coordinates":[1,2]}}"""))
        assertTrue(f is Geometria.Punto)
        val fc = GeoJson.parsear(json("""{"type":"FeatureCollection","features":[
            {"type":"Feature","geometry":{"type":"LineString","coordinates":[[0,0],[1,1]]}},
            {"type":"Feature","geometry":{"type":"LineString","coordinates":[[2,2],[3,3]]}}]}""")) as Geometria.Lineas
        assertEquals(2, fc.partes.size)
    }

    @Test
    fun lo_que_no_se_entiende_da_null_y_nunca_lanza() {
        assertNull(GeoJson.parsear(null))
        assertNull(GeoJson.parsear(json("null")))
        assertNull(GeoJson.parsear(json("""{"type":"Polygon","coordinates":[]}""")))
        assertNull(GeoJson.parsear(json("""{"type":"LineString","coordinates":[[1,2]]}""")))   // un solo vertice no es linea
        assertNull(GeoJson.parsear(json("""{"type":"Punto","coordinates":[1,2]}""")))
        assertNull(GeoJson.parsear(json("""{"type":"Point","coordinates":["a","b"]}""")))
        assertNull(GeoJson.parsear(json("""{"type":"Point","coordinates":[200,5]}""")))        // fuera de rango
    }

    @Test
    fun simplificacion_douglas_peucker_conserva_extremos_y_baja_vertices() {
        // una linea casi recta con un zigzag chico: con tolerancia grande quedan los extremos
        val parte = (0..100).map { i -> Coord(-7.0 + i * 0.001 + (if (i % 2 == 0) 0.00005 else -0.00005), -78.5 + i * 0.001) }
        val s = GeoJson.simplificar(parte, 0.001)
        assertEquals(parte.first(), s.first())
        assertEquals(parte.last(), s.last())
        assertTrue("quedaron ${s.size}", s.size < 10)
        // sin tolerancia no cambia nada
        assertEquals(parte, GeoJson.simplificar(parte, 0.0))
        // un codo real se conserva
        val codo = listOf(Coord(0.0, 0.0), Coord(0.0, 1.0), Coord(1.0, 1.0))
        assertEquals(codo, GeoJson.simplificar(codo, 0.1))
        assertTrue(GeoJson.toleranciaPorZoom(6.0) > GeoJson.toleranciaPorZoom(10.0))
        assertEquals(0.0, GeoJson.toleranciaPorZoom(12.0), 0.0)
    }

    @Test
    fun cajas_de_la_vista() {
        assertTrue(GeoJson.cajasSeCruzan(Caja(0.0, 0.0, 1.0, 1.0), Caja(1.0, 1.0, 2.0, 2.0)))   // se tocan en la esquina
        assertFalse(GeoJson.cajasSeCruzan(Caja(0.0, 0.0, 1.0, 1.0), Caja(1.1, 0.0, 2.0, 1.0)))
        assertFalse(GeoJson.cajasSeCruzan(null, Caja(0.0, 0.0, 1.0, 1.0)))
        assertEquals(Caja(-1.0, -2.0, 11.0, 22.0), GeoJson.cajaConMargen(Caja(0.0, 0.0, 10.0, 20.0), 0.1))
        // la caja de la vista redondeada hacia afuera a decimas: clave de cache repetible
        val r = GeoJson.cajaRedondeada(Caja(-78.56, -7.23, -78.41, -7.08))
        assertEquals(Caja(-78.6, -7.3, -78.4, -7.0), r)
        assertTrue(GeoJson.dentro(Coord(-7.1, -78.5), r))
        assertNotNull(GeoJson.cajaDe(sequenceOf(Coord(1.0, 2.0))))
        assertNull(GeoJson.cajaDe(emptySequence()))
    }
}
