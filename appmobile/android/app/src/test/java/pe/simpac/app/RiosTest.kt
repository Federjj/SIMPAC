package pe.simpac.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pe.simpac.app.data.AvisoLluviaSenal
import pe.simpac.app.data.CaudalActual
import pe.simpac.app.data.LecturaRio
import pe.simpac.app.data.LluviaCuenca
import pe.simpac.app.data.RioCauceSenal
import pe.simpac.app.data.RioSenal
import pe.simpac.app.data.RioVigiladoMapa
import pe.simpac.app.dominio.Cauces
import pe.simpac.app.dominio.Nivel
import pe.simpac.app.dominio.NivelZona
import pe.simpac.app.dominio.Rios
import pe.simpac.app.dominio.Tiempo

/**
 * La linea de la cuenca junto a la medicion (el rio esta tranquilo en su estacion y ademas puede subir):
 * la misma lectura que hace la web con lib/zonaRio.js estadoZona para el titular y la tarjeta del rio.
 */
class RiosTest {
    private val AHORA = Tiempo.parsearMs("2026-11-23T15:00:00-05:00")!!
    private val MASHCON = LecturaRio(estacion = "Mashcón", valor = 0.13, unidad = "m3/s", umbral_alerta = 14.0, umbral_emergencia = 18.0, estado = "normal", tendencia = "Estable")
    private val NARANJA_HOY = AvisoLluviaSenal(tipo = "meteorologico", numero = 412, nivel = 3, en_curso = true, inicio = "2026-11-23T05:00:00+00:00", fin = null, url = "https://www.senamhi.gob.pe/?p=aviso-meteorologico-detalle&a=2026&b=412")
    // el Maranon en Borja vigila nivel bajo (umbral de emergencia por debajo del de alerta): "muy bajo" cuenta como "aviso"
    private val BORJA = LecturaRio(estacion = "Borja", valor = 163.8, unidad = "m.s.n.m", umbral_alerta = 163.89, umbral_emergencia = 163.28, estado = "alerta", tendencia = "Descendente")
    private val VIGILADO = RioVigiladoMapa(id = "mashcon", nombre = "Río Mashcón", departamento = "Cajamarca", estacion_ana = "Mashcón", rio_ana = "Mashcon")
    private val CAUDAL_MASHCON = CaudalActual(estacion = "Mashcón", rio = "Mashcon", departamento = "Cajamarca", valor = 0.34, unidad = "m³/s", umbral_alerta = 14.0, umbral_emergencia = 18.0, estado = "normal", tendencia = "Descendente")
    private val CAUDAL_BORJA = CaudalActual(estacion = "Borja", rio = "Marañón", departamento = "Loreto", valor = 163.8, unidad = "m.s.n.m", umbral_alerta = 163.89, umbral_emergencia = 163.28, estado = "alerta", tendencia = "Descendente")

    @Test
    fun aviso_naranja_en_curso_da_la_linea_de_la_cuenca_con_su_url() {
        val zona = Cauces.estadoZona(null, emptyList(), listOf(NARANJA_HOY), emptyList(), AHORA)
        val c = Rios.cuenca(zona)
        assertNotNull(c)
        assertEquals("aviso_lluvia", c!!.clave)
        assertEquals("Cuenca: aviso naranja de SENAMHI por lluvias vigente hoy; el caudal puede subir.", c.linea)
        assertEquals(NARANJA_HOY.url, c.url)
        assertEquals(NivelZona.ATENTOS, c.nivel)
        assertNull(c.detalle)
    }

    @Test
    fun aviso_rojo_con_fin_dice_hasta_cuando() {
        val rojo = NARANJA_HOY.copy(nivel = 4, fin = "2026-11-24T04:59:59+00:00")
        val c = Rios.cuenca(Cauces.estadoZona(null, emptyList(), listOf(rojo), emptyList(), AHORA))!!
        assertTrue(c.linea, c.linea.startsWith("Cuenca: aviso rojo de SENAMHI por lluvias vigente hasta el "))
        assertTrue(c.linea, c.linea.endsWith("; el caudal puede subir."))
    }

    @Test
    fun amarillo_o_de_manana_no_dan_linea() {
        assertNull(Rios.cuenca(Cauces.estadoZona(null, emptyList(), listOf(NARANJA_HOY.copy(nivel = 2)), emptyList(), AHORA)))
        assertNull(Rios.cuenca(Cauces.estadoZona(null, emptyList(), listOf(NARANJA_HOY.copy(en_curso = false)), emptyList(), AHORA)))
        assertNull(Rios.cuenca(Cauces.estadoZona(null, emptyList(), emptyList(), emptyList(), AHORA)))
    }

    @Test
    fun lluvia_medida_sobre_la_referencia_da_linea_con_detalle_y_sin_url() {
        val lluvia = LluviaCuenca(nombre = "Weberbauer", pp_1h = 12.0, umbral_1h = 10.0, pp_6h = 20.0, umbral_6h = 30.0)
        val c = Rios.cuenca(Cauces.estadoZona(null, emptyList(), emptyList(), listOf(lluvia), AHORA))!!
        assertEquals("lluvia_medida", c.clave)
        assertTrue(c.linea, c.linea.startsWith("Cuenca: lluvia fuerte medida por SENAMHI"))
        assertTrue(c.linea, c.linea.endsWith("; el caudal puede subir."))
        assertTrue(c.detalle ?: "", (c.detalle ?: "").contains("Weberbauer"))
        assertNull(c.url)
        // con aviso y lluvia medida a la vez manda el aviso
        assertEquals("aviso_lluvia", Rios.cuenca(Cauces.estadoZona(null, emptyList(), listOf(NARANJA_HOY), listOf(lluvia), AHORA))!!.clave)
    }

    @Test
    fun resumir_mantiene_la_medicion_de_ana_y_agrega_la_cuenca() {
        val sinCuenca = Rios.resumir(RioCauceSenal("mashcon", listOf(MASHCON)), "Río Mashcón", AHORA)
        assertEquals(Nivel.NORMAL, sinCuenca.nivel)
        assertEquals("tranquilo en Mashcón (0.13 m³/s)", sinCuenca.texto)
        assertEquals("Estación Mashcón (ANA): tranquila (0.13 m³/s)", sinCuenca.medicion)
        assertNull(sinCuenca.cuenca)
        assertEquals(Nivel.NORMAL, sinCuenca.nivelDestacar)

        val conCuenca = Rios.resumir(RioCauceSenal("mashcon", listOf(MASHCON), avisos_lluvia = listOf(NARANJA_HOY)), "Río Mashcón", AHORA)
        assertEquals(Nivel.NORMAL, conCuenca.nivel)                 // la medicion no cambia: el rio esta bajo ahora
        assertEquals(sinCuenca.medicion, conCuenca.medicion)
        assertEquals("Cuenca: aviso naranja de SENAMHI por lluvias vigente hoy; el caudal puede subir.", conCuenca.cuenca?.linea)
        assertEquals(Nivel.AVISO, conCuenca.nivelDestacar)          // pero se destaca como "aviso" (atentos)

        // sin lectura, solo la senal de la cuenca: no hay medicion, pero el rio igual se destaca
        val soloCuenca = Rios.resumir(RioCauceSenal("x", avisos_lluvia = listOf(NARANJA_HOY)), "Río X", AHORA)
        assertEquals(Nivel.SIN_DATO, soloCuenca.nivel)
        assertNull(soloCuenca.medicion)
        assertNotNull(soloCuenca.cuenca)
        assertEquals(Nivel.AVISO, soloCuenca.nivelDestacar)
    }

    @Test
    fun destacado_prefiere_el_rio_con_senal_de_cuenca_entre_los_tranquilos() {
        val tranquilo = Rios.resumir(RioCauceSenal("a", listOf(MASHCON.copy(estacion = "A"))), "Río A", AHORA)
        val conCuenca = Rios.resumir(RioCauceSenal("b", listOf(MASHCON.copy(estacion = "B")), avisos_lluvia = listOf(NARANJA_HOY)), "Río B", AHORA)
        val crecido = Rios.resumir(RioCauceSenal("c", listOf(MASHCON.copy(estacion = "C", valor = 15.0, estado = "alerta"))), "Río C", AHORA)
        assertEquals("b", Rios.destacado(listOf(tranquilo, conCuenca))?.rioAna)
        assertEquals("c", Rios.destacado(listOf(tranquilo, conCuenca, crecido))?.rioAna)   // una alerta de ANA manda
        assertEquals("Estación C (ANA): en alerta (15.00 m³/s)", crecido.medicion)
        assertNull(Rios.destacado(listOf(Rios.resumir(RioCauceSenal("d"), "Río D", AHORA))))
        // empate en "aviso" entre un rio muy bajo (vaciante) y uno tranquilo con aviso sobre su cuenca: manda la cuenca,
        // que es el rio que nombra el titular; el orden de la lista no decide
        val muyBajo = Rios.resumir(RioCauceSenal("e", listOf(BORJA)), "Río E", AHORA)
        assertEquals(Nivel.AVISO, muyBajo.nivelDestacar)
        assertEquals("muy bajo en Borja (163.80 m.s.n.m)", muyBajo.texto)
        assertEquals("b", Rios.destacado(listOf(muyBajo, conCuenca))?.rioAna)
        assertEquals("b", Rios.destacado(listOf(conCuenca, muyBajo))?.rioAna)
        assertEquals("e", Rios.destacado(listOf(muyBajo, tranquilo))?.rioAna)
    }

    @Test
    fun de_vigilado_arma_la_senal_con_la_lectura_de_ana_y_la_cuenca_de_rio_senal() {
        val senal = RioSenal("mashcon", avisos_lluvia = listOf(NARANJA_HOY))
        val s = Rios.deVigilado(VIGILADO, senal, listOf(CAUDAL_BORJA, CAUDAL_MASHCON))
        assertEquals("mashcon", s.rio_ana)
        assertEquals(listOf("Mashcón"), s.lecturas.map { it.estacion })
        assertEquals(listOf(NARANJA_HOY), s.avisos_lluvia)
        val r = Rios.resumir(s, VIGILADO.nombre!!, AHORA)
        assertEquals(Nivel.NORMAL, r.nivel)
        assertEquals("Estación Mashcón (ANA): tranquila (0.34 m³/s)", r.medicion)
        assertEquals("Cuenca: aviso naranja de SENAMHI por lluvias vigente hoy; el caudal puede subir.", r.cuenca?.linea)
        assertEquals(Nivel.AVISO, r.nivelDestacar)
        // sin fila en rio_senal ni lectura de ANA no se inventa nada
        val vacio = Rios.deVigilado(VIGILADO, null, listOf(CAUDAL_BORJA))
        assertTrue(vacio.lecturas.isEmpty())
        assertTrue(vacio.avisos_lluvia.isEmpty() && vacio.lluvia_cuenca.isEmpty() && vacio.avisos_hidro.isEmpty())
        assertNull(Rios.resumir(vacio, "Río Mashcón", AHORA).cuenca)
    }

    @Test
    fun resumir_zona_pone_el_vigilado_del_departamento_primero_y_no_lo_repite() {
        val senales = listOf(RioSenal("mashcon", avisos_lluvia = listOf(NARANJA_HOY)))
        val caudales = listOf(CAUDAL_BORJA, CAUDAL_MASHCON)
        val cauces = listOf(RioCauceSenal("maranon", listOf(BORJA)), RioCauceSenal("mashcon", listOf(MASHCON)))
        val nombres = mapOf("maranon" to "Río Marañón", "mashcon" to "Río Mashcón")
        val rios = Rios.resumirZona("Cajamarca", listOf(VIGILADO), senales, caudales, cauces, nombres, AHORA)
        assertEquals(listOf("mashcon", "maranon"), rios.map { it.rioAna })
        assertEquals("Río Mashcón", rios[0].nombre)
        assertEquals("Estación Mashcón (ANA): tranquila (0.34 m³/s)", rios[0].medicion)   // la lectura de caudal_actual, no la del trazo repetido
        assertNotNull(rios[0].cuenca)
        assertEquals("muy bajo en Borja (163.80 m.s.n.m)", rios[1].texto)
        assertEquals(Nivel.AVISO, rios[1].nivelDestacar)
        // el chip dice el mismo rio que el titular: en empate de "aviso" manda la senal de cuenca
        assertEquals("mashcon", Rios.destacado(rios)?.rioAna)
        // en otro departamento el vigilado no entra; el nombre del departamento va sin tildes ni mayusculas
        assertEquals(listOf("maranon", "mashcon"), Rios.resumirZona("Loreto", listOf(VIGILADO), senales, caudales, cauces, nombres, AHORA).map { it.rioAna })
        assertEquals("mashcon", Rios.resumirZona("cajamarca", listOf(VIGILADO), senales, caudales, cauces, nombres, AHORA).first().rioAna)
        // sin rio_senal ni caudal_actual (fallaron) el vigilado igual aparece, sin cuenca ni medicion
        val aSecas = Rios.resumirZona("Cajamarca", listOf(VIGILADO), emptyList(), emptyList(), cauces, nombres, AHORA)
        assertEquals("mashcon", aSecas.first().rioAna)
        assertNull(aSecas.first().cuenca)
        assertEquals("maranon", Rios.destacado(aSecas)?.rioAna)
    }

    @Test
    fun etiqueta_de_la_estacion_en_femenino() {
        assertEquals("tranquila", Rios.etiquetaEstacion("Tranquilo"))
        assertEquals("atenta", Rios.etiquetaEstacion("Atento"))
        assertEquals("en alerta", Rios.etiquetaEstacion("En alerta"))
        assertEquals("río muy bajo", Rios.etiquetaEstacion("Río muy bajo"))
        assertEquals("Estación Picota (ANA): en alerta (8,500 m³/s)", Rios.medicion("Picota", "En alerta", "8,500 m³/s"))
        assertEquals("Estación Picota (ANA): sin medición", Rios.medicion("Picota", "Sin medición", null))
        // las hojas del mapa la piden sin valor: el titulo ya lo dice
        assertEquals("Estación Picota (ANA): en alerta", Rios.medicion("Picota", "En alerta"))
    }
}
