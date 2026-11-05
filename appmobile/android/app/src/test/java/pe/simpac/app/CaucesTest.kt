package pe.simpac.app

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pe.simpac.app.data.AvisoHidro
import pe.simpac.app.data.AvisoVigente
import pe.simpac.app.data.CaudalActual
import pe.simpac.app.data.RioCauceMapa
import pe.simpac.app.data.RioVigiladoMapa
import pe.simpac.app.dominio.AvisosMapa
import pe.simpac.app.dominio.Caja
import pe.simpac.app.dominio.Cauces
import pe.simpac.app.dominio.EstadoCauce
import pe.simpac.app.dominio.NivelZona
import pe.simpac.app.dominio.Paleta
import pe.simpac.app.dominio.Tiempo

/**
 * Los mismos casos que frontend/src/lib/cauces.test.js y zonaRio.test.js (filas reales del 14-10-2026,
 * recortadas): la app debe pintar cada rio del mismo color que la web.
 */
class CaucesTest {
    private val HUALLAGA = RioCauceMapa(rio_ana = "huallaga", rio = "Huallaga", nombre = "Río Huallaga", departamento = "Huánuco, Loreto, San Martín", estaciones = listOf("Lagunas", "Picota", "Puente Pérez", "Tingo María"))
    private val JEQUETEPEQUE = RioCauceMapa(rio_ana = "jequetepeque", rio = "Jequetepeque", nombre = "Río Jequetepeque", estaciones = listOf("Yonán"))
    private val MASHCON_CAUCE = RioCauceMapa(rio_ana = "mashcon", rio = "Mashcon", nombre = "Río Mashcón", estaciones = listOf("Mashcón"), vigilado = true)
    private val LAGUNAS = CaudalActual(estacion = "Lagunas", rio = "Huallaga", valor = 111.84, unidad = "m.s.n.m", umbral_alerta = 111.95, umbral_emergencia = 111.21, tendencia = "Ascendente", lat = -5.23, lon = -75.67)
    private val PICOTA = CaudalActual(estacion = "Picota", rio = "Huallaga", valor = 938.54, unidad = "m³/s", umbral_alerta = 8130.38, umbral_emergencia = 9883.48, tendencia = "Ascendente", lat = -6.92, lon = -76.33)
    private val TINGO = CaudalActual(estacion = "Tingo Maria", rio = "Huallaga", valor = 159.9, unidad = "m³/s", umbral_alerta = 1010.0, umbral_emergencia = 1178.0, lat = -9.3, lon = -76.0)
    private val YONAN = CaudalActual(estacion = "Yonán", rio = "Jequetepeque", valor = 12.0, unidad = "m³/s", umbral_alerta = 400.0, umbral_emergencia = 600.0, lat = -7.25, lon = -79.0)
    private val MASHCON = CaudalActual(estacion = "Mashcón", rio = "Mashcon", valor = 0.13, unidad = "m³/s", umbral_alerta = 14.0, umbral_emergencia = 18.0, lat = -7.1, lon = -78.5)
    private val SUMBAY = CaudalActual(estacion = "Sumbay", rio = "Sumbay", valor = 3.0, unidad = "m³/s", umbral_alerta = 40.0, umbral_emergencia = 60.0, lat = -16.0, lon = -71.4)
    private val VIGILADO = RioVigiladoMapa(id = "mashcon", nombre = "Río Mashcón", estacion_ana = "Mashcón", rio_ana = "Mashcon")
    private val AHORA = Tiempo.parsearMs("2026-10-14T12:00:00Z")!!
    private val AVISO_NARANJA = AvisoHidro(numero = 1645, titulo = "SITUACIÓN ACTUAL DEL NIVEL DEL RÍO HUALLAGA - ESTACIÓN LAGUNAS", nivel = 3, sentido = "crecida", inicio = "2026-10-12T05:00:00+00:00", fin = null, url = "https://www.senamhi.gob.pe/?p=avisos-detalle-hidrologicos&ca=70609&ce=230603", visto_en = "2026-10-14T10:58:09+00:00")

    @Test
    fun textoRio_tranquilo_atento_alerta_emergencia_y_bajo() {
        val t = Cauces.textoRio(PICOTA)
        assertEquals(EstadoCauce.NORMAL, t.estado)
        assertEquals("Tranquilo", t.etiqueta)
        assertEquals("Río Huallaga (Picota)", t.titulo)
        assertTrue(t.frase, t.frase.startsWith("Tranquilo. Lleva 938.54 m³/s, el 12 % del caudal que activa la alerta (8,130.38 m³/s). Está subiendo."))
        assertEquals(EstadoCauce.ATENTO, Cauces.textoRio(PICOTA.copy(valor = 7000.0)).estado)
        assertEquals(EstadoCauce.ALERTA, Cauces.textoRio(PICOTA.copy(valor = 8500.0)).estado)
        assertEquals(EstadoCauce.EMERGENCIA, Cauces.textoRio(PICOTA.copy(valor = 9900.0)).estado)
        // Lagunas vigila nivel bajo (emergencia < alerta): "alerta" por nivel bajo, no es crecida
        val bajo = Cauces.textoRio(LAGUNAS)
        assertTrue(bajo.bajo)
        assertEquals(EstadoCauce.ALERTA, bajo.estado)
        assertEquals("Río muy bajo", bajo.etiqueta)
        // sin medicion o sin umbral: sin dato
        assertEquals(EstadoCauce.SD, Cauces.textoRio(PICOTA.copy(valor = null)).estado)
        assertEquals(EstadoCauce.SD, Cauces.textoRio(PICOTA.copy(umbral_alerta = null)).estado)
        // niveles en metros: a menos de 50 cm, atento; en el Titicaca no
        assertEquals(EstadoCauce.ATENTO, Cauces.textoRio(CaudalActual(estacion = "X", rio = "Napo", valor = 4.7, unidad = "m", umbral_alerta = 5.0, umbral_emergencia = 6.0)).estado)
        assertEquals(EstadoCauce.NORMAL, Cauces.textoRio(CaudalActual(estacion = "X", rio = "Titicaca", valor = 4.7, unidad = "m", umbral_alerta = 5.0, umbral_emergencia = 6.0)).estado)
    }

    @Test
    fun lecturasDelCauce_mismo_rio_y_estacion_sin_tildes() {
        assertEquals(listOf(LAGUNAS, PICOTA, TINGO), Cauces.lecturasDelCauce(HUALLAGA, listOf(LAGUNAS, PICOTA, TINGO, YONAN)))
        assertEquals(listOf(YONAN), Cauces.lecturasDelCauce(JEQUETEPEQUE, listOf(YONAN.copy(estacion = "Otra"), YONAN)))
    }

    @Test
    fun emparejarCauces_salta_el_vigilado_y_deja_aparte_las_estaciones_sin_trazo() {
        val e = Cauces.emparejarCauces(listOf(HUALLAGA, JEQUETEPEQUE, MASHCON_CAUCE), listOf(LAGUNAS, PICOTA, YONAN, MASHCON, SUMBAY), listOf(VIGILADO))
        assertEquals(listOf("huallaga", "jequetepeque"), e.rios.map { it.fila.rio_ana })
        assertEquals(listOf(SUMBAY), e.sinTrazo)   // el Mashcon es vigilado: ni "sin trazo" ni trazo nacional
        val otra = Cauces.emparejarCauces(listOf(MASHCON_CAUCE.copy(vigilado = false)), listOf(MASHCON), listOf(VIGILADO))
        assertEquals(0, otra.rios.size)
    }

    @Test
    fun peorLectura_manda_la_peor_de_crecida_y_el_nivel_bajo_cuenta_como_normal() {
        assertEquals(LAGUNAS, Cauces.peorLectura(listOf(LAGUNAS, PICOTA)))   // empate normal/normal: la primera
        val crecida = PICOTA.copy(valor = 8500.0)
        assertEquals(crecida, Cauces.peorLectura(listOf(LAGUNAS, crecida, TINGO)))
        assertNull(Cauces.peorLectura(emptyList()))
    }

    @Test
    fun estadoRio_ana_manda_sin_aviso_el_aviso_naranja_si_es_mas_alto_y_uno_vencido_no() {
        val tranquilo = Cauces.estadoRio(listOf(PICOTA, TINGO), ahoraMs = AHORA)
        assertEquals(EstadoCauce.NORMAL, tranquilo.cauce.estado)
        assertEquals(NivelZona.SIN_SENALES, tranquilo.zona.nivel)
        assertFalse(Cauces.esFuerte(tranquilo))
        val aviso = Cauces.estadoRio(listOf(LAGUNAS, PICOTA, TINGO), listOf(AVISO_NARANJA), AHORA)
        assertEquals(EstadoCauce.ALERTA, aviso.cauce.estado)
        assertTrue(aviso.cauce.porAviso)
        assertEquals("naranja", aviso.cauce.color)
        assertEquals(NivelZona.ALERTA, aviso.zona.nivel)
        assertEquals(1645, aviso.zona.avisoHidro?.numero)
        assertTrue(Cauces.esFuerte(aviso))
        val vencido = Cauces.estadoRio(listOf(PICOTA), listOf(AVISO_NARANJA.copy(fin = "2026-10-13T00:00:00Z")), AHORA)
        assertEquals(EstadoCauce.NORMAL, vencido.cauce.estado)
        // ANA en emergencia por encima de un aviso naranja: manda ANA
        val peorAna = Cauces.estadoRio(listOf(PICOTA.copy(valor = 9900.0)), listOf(AVISO_NARANJA), AHORA)
        assertEquals(EstadoCauce.EMERGENCIA, peorAna.cauce.estado)
        assertFalse(peorAna.cauce.porAviso)
        // sin estacion (rio solo con aviso SENAMHI): sd sin aviso, el aviso si lo hay
        assertEquals(EstadoCauce.SD, Cauces.estadoRio(emptyList(), ahoraMs = AHORA).cauce.estado)
        assertEquals(EstadoCauce.ALERTA, Cauces.estadoRio(emptyList(), listOf(AVISO_NARANJA), AHORA).cauce.estado)
        // un aviso en descenso (vaciante) no sube
        assertEquals(EstadoCauce.NORMAL, Cauces.estadoRio(listOf(PICOTA), listOf(AVISO_NARANJA.copy(sentido = "descenso")), AHORA).cauce.estado)
    }

    @Test
    fun el_aviso_hidrologico_es_de_una_estacion() {
        assertEquals("lagunas", Cauces.estacionDeAviso(AVISO_NARANJA))
        assertTrue(Cauces.avisoEsDeEstacion(AVISO_NARANJA, "Lagunas"))
        assertFalse(Cauces.avisoEsDeEstacion(AVISO_NARANJA, "Picota"))
        assertNull(Cauces.estacionDeAviso(AvisoHidro(titulo = "AVISO SIN ESTACION")))
    }

    @Test
    fun detalle_y_zonas_por_zoom() {
        assertEquals("lejos", Cauces.detallePorZoom(6.0))
        assertEquals("lejos", Cauces.detallePorZoom(12.0))
        assertEquals("cauce", Cauces.detallePorZoom(13.0))
        val cajas = mapOf("huallaga" to Caja(-76.2, -9.9, -75.3, -5.5), "jequetepeque" to Caja(-79.2, -7.3, -78.8, -7.2))
        assertEquals(12, Cauces.ZONAS_DESDE)
        assertEquals(listOf("jequetepeque"), Cauces.riosParaZonas(cajas, Caja(-79.1, -7.3, -78.9, -7.2), 12.0))
        assertEquals(emptyList<String>(), Cauces.riosParaZonas(cajas, Caja(-79.1, -7.3, -78.9, -7.2), 11.0))
        assertEquals(listOf("huallaga"), Cauces.riosParaZonas(cajas, Caja(-76.1, -9.6, -75.9, -9.4), 14.0))
        assertEquals(emptyList<String>(), Cauces.riosParaZonas(cajas, Caja(-70.0, -15.0, -69.0, -14.0), 14.0))
        assertEquals(emptyList<String>(), Cauces.riosParaZonas(cajas, null, 14.0))
    }

    @Test
    fun resumen_de_la_hoja_de_una_estacion() {
        val c = PICOTA.copy(fecha = "2026-10-14", hora = "20:00")
        val t = Cauces.textoRio(c)
        val hoy = java.time.LocalDate.of(2026, 10, 14)
        assertEquals("hoy 20:00 (ANA)", Cauces.lecturaRio(c, hoy))
        assertEquals("ayer 20:00 (ANA)", Cauces.lecturaRio(c, hoy.plusDays(1)))
        assertEquals("Río Huallaga - tranquilo 938.54 m³/s (ANA, hoy 20:00)", Cauces.resumenEstacion("Río Huallaga", c, t, Cauces.estadoCauce(t), hoy))
        assertEquals("Río Huallaga - tranquilo 938.54 m³/s (ANA, 14 oct 20:00)", Cauces.resumenEstacion("Río Huallaga", c, t, Cauces.estadoCauce(t), hoy.plusDays(5)))
        assertEquals("Río Huallaga - sin medición", Cauces.resumenEstacion("Río Huallaga", c.copy(valor = null), Cauces.textoRio(c.copy(valor = null)), null, hoy))
        assertEquals("A, B y C", Cauces.lista(listOf("A", "A", "B", "C")))
        assertEquals("A, B y 2 más", Cauces.lista(listOf("A", "B", "C", "D"), 2))
        assertEquals("Información pública del Estado peruano publicada por la ANA (GeoSNIRH) sin texto de licencia", Cauces.licenciaCorta("Información pública del Estado peruano publicada por la ANA (GeoSNIRH) sin texto de licencia; se cita la fuente"))
    }

    // ---- colores por nivel: los de la web (map/palette.js) ----
    @Test
    fun colores_por_nivel_iguales_a_la_web() {
        assertEquals("#1C7ED6", Paleta.hex(Paleta.cauce(EstadoCauce.NORMAL)))
        assertEquals("#EAB308", Paleta.hex(Paleta.cauce(EstadoCauce.ATENTO)))
        assertEquals("#F58E27", Paleta.hex(Paleta.cauce(EstadoCauce.ALERTA)))
        assertEquals("#DB0404", Paleta.hex(Paleta.cauce(EstadoCauce.EMERGENCIA)))
        assertEquals("#94A3B8", Paleta.hex(Paleta.cauce(EstadoCauce.SD)))
        assertEquals("#3BEB40", Paleta.hex(Paleta.rio(EstadoCauce.NORMAL)))
        assertEquals("#9CA3AF", Paleta.hex(Paleta.rio(EstadoCauce.SD)))
        assertEquals("#1D4ED8", Paleta.hex(Paleta.zona(NivelZona.SIN_SENALES)))
        assertEquals("#EAB308", Paleta.hex(Paleta.zona(NivelZona.ATENTOS)))
        assertEquals("#991B1B", Paleta.hex(Paleta.zonaOscuro(NivelZona.EMERGENCIA)))
        assertEquals("#EBEB3B", Paleta.hex(Paleta.aviso(2)))            // area (layers/avisos.js NIVELES)
        assertEquals("#EAB308", Paleta.hex(Paleta.AVISO_ARO.getValue(2))) // aro de la insignia (palette.js AVISO_ARO)
        assertEquals("#F58E27", Paleta.hex(Paleta.aviso(3)))
        assertEquals("#DB0404", Paleta.hex(Paleta.aviso(4)))
        assertEquals("#9CA3AF", Paleta.hex(Paleta.aviso(null)))
        assertEquals("#0F766E", Paleta.hex(Paleta.acudir("salud")))
        assertEquals("#475569", Paleta.hex(Paleta.acudir("lo que sea")))
    }

    // ---- avisos de SENAMHI del dia ----
    private fun aviso(id: Long, nivel: Int, inicio: String, fin: String, tema: String = "lluvia", tipo: String = "meteorologico", numero: Int = 1, icono: String? = null, titulo: String? = null) =
        AvisoVigente(id = id, tipo = tipo, anio = 2026, numero = numero, nivel = nivel, tema = tema, inicio = inicio, fin = fin, icono = icono, titulo = titulo,
            geojson = Json.parseToJsonElement("""{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}"""))

    @Test
    fun avisos_de_hoy_glifo_y_titulo() {
        val ahora = Tiempo.parsearMs("2026-11-04T15:00:00-05:00")!!
        val hoy = aviso(1, 3, "2026-11-04T05:00:00+00:00", "2026-11-05T04:59:59+00:00")
        val vencido = aviso(2, 4, "2026-11-03T05:00:00+00:00", "2026-11-04T12:00:00+00:00")       // termino a las 7 am de hoy
        val masTarde = aviso(3, 2, "2026-11-04T22:00:00+00:00", "2026-11-05T04:59:59+00:00")      // empieza a las 5 pm de hoy
        val manana = aviso(4, 2, "2026-11-05T05:00:00+00:00", "2026-11-06T04:59:59+00:00", numero = 2)
        val sinGeo = hoy.copy(id = 5, geojson = null)
        assertEquals(listOf(1L, 3L), AvisosMapa.deHoy(listOf(hoy, vencido, masTarde, manana, sinGeo), ahora).map { it.id })
        // uno por aviso (tipo-anio-numero): el de nivel mas alto; del mas alto al mas bajo
        val dias = listOf(aviso(10, 2, "2026-11-04T05:00:00+00:00", "2026-11-05T04:59:59+00:00", numero = 7), aviso(11, 3, "2026-11-05T05:00:00+00:00", "2026-11-06T04:59:59+00:00", numero = 7), hoy)
        assertEquals(listOf(11L, 1L), AvisosMapa.unoPorAviso(dias).map { it.id })
        // glifo: el del worker o el del tema
        assertEquals("gota", AvisosMapa.glifo(hoy))
        assertEquals("gota_rayo", AvisosMapa.glifo(hoy.copy(icono = "gota_rayo")))
        assertEquals("termometro", AvisosMapa.glifo(hoy.copy(tema = "temperatura", titulo = "INCREMENTO DE TEMPERATURA DIURNA")))
        assertEquals("termometro_frio", AvisosMapa.glifo(hoy.copy(tema = "temperatura", titulo = "DESCENSO DE TEMPERATURA NOCTURNA")))
        assertEquals("viento", AvisosMapa.glifo(hoy.copy(tema = "viento")))
        assertNull(AvisosMapa.glifo(hoy.copy(tema = "otro")))
        assertEquals("Aviso naranja de SENAMHI por lluvias", AvisosMapa.titulo(hoy))
        assertEquals("Aviso amarillo de SENAMHI por calor", AvisosMapa.titulo(masTarde.copy(tema = "temperatura", titulo = "INCREMENTO DE TEMPERATURA")))
        assertEquals("Naranja (nivel 3 de 4)", AvisosMapa.ETIQUETA_NIVEL[3])
    }
}
