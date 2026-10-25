package pe.simpac.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pe.simpac.app.data.AlertaActual
import pe.simpac.app.data.AvisoHidro
import pe.simpac.app.data.LecturaRio
import pe.simpac.app.data.PronosticoVigente
import pe.simpac.app.data.PuntoAcudir
import pe.simpac.app.data.RioCauceSenal
import pe.simpac.app.dominio.Acudir
import pe.simpac.app.dominio.Alertas
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.Geo
import pe.simpac.app.dominio.Nivel
import pe.simpac.app.dominio.Pronostico
import pe.simpac.app.dominio.Rios
import pe.simpac.app.dominio.Tiempo
import java.time.LocalDate

class DominioTest {
    // ---- temas de FCM (contrato 1) ----
    @Test
    fun slug_del_tema_por_departamento() {
        assertEquals("zona_cajamarca", Departamentos.slugTema("Cajamarca"))
        assertEquals("zona_la_libertad", Departamentos.slugTema("La Libertad"))
        assertEquals("zona_madre_de_dios", Departamentos.slugTema("Madre de Dios"))
        assertEquals("zona_ancash", Departamentos.slugTema("Áncash"))
        assertEquals("zona_san_martin", Departamentos.slugTema("San Martín"))
        assertEquals("zona_callao", Departamentos.slugTema("Callao"))
        assertEquals("zona_lima", Departamentos.slugTema("Lima"))
        assertEquals("pais", Departamentos.TEMA_PAIS)
    }

    @Test
    fun departamento_por_nombre_tolera_tildes_y_mayusculas() {
        assertEquals("Áncash", Departamentos.porNombre("ANCASH")?.nombre)
        assertEquals("La Libertad", Departamentos.porNombre("la libertad")?.nombre)
        assertNull(Departamentos.porNombre("Narnia"))
        assertEquals(25, Departamentos.TODOS.size)
    }

    // ---- distancia ----
    @Test
    fun distancia_haversine_cajamarca_lima() {
        val km = Geo.distanciaKm(-7.1617, -78.5127, -12.0464, -77.0428)
        assertTrue("$km", km > 560 && km < 580)   // unos 568 km en linea recta
        assertEquals(0.0, Geo.distanciaKm(-7.0, -78.0, -7.0, -78.0), 1e-9)
    }

    @Test
    fun texto_de_distancia() {
        assertEquals("450 m", Geo.distanciaTexto(0.45))
        assertEquals("2.3 km", Geo.distanciaTexto(2.31))
        assertEquals("27 km", Geo.distanciaTexto(27.4))
    }

    @Test
    fun caja_alrededor_redondeada_a_decimas() {
        val c = Geo.cajaAlrededor(-7.1617, -78.5127, 30.0)
        assertTrue(c.sur <= -7.43 && c.sur >= -7.5)
        assertTrue(c.norte >= -6.9 && c.norte <= -6.8)
        assertTrue(c.oeste < -78.78 && c.este > -78.24)
        assertEquals(c.sur, Math.round(c.sur * 10) / 10.0, 1e-9)
    }

    // ---- "hace X" ----
    @Test
    fun hace_texto() {
        val ahora = 1_760_000_000_000L
        assertEquals("recién", Tiempo.haceTexto(ahora - 20_000, ahora))
        assertEquals("hace 5 min", Tiempo.haceTexto(ahora - 5 * 60_000, ahora))
        assertEquals("hace 2 h", Tiempo.haceTexto(ahora - 2 * 3_600_000, ahora))
        assertEquals("hace 1 día", Tiempo.haceTexto(ahora - 26 * 3_600_000, ahora))
        assertEquals("hace 3 días", Tiempo.haceTexto(ahora - 72 * 3_600_000, ahora))
        assertEquals("", Tiempo.haceTexto(null, ahora))
    }

    @Test
    fun parseo_de_timestamps_de_la_bd() {
        val ms = Tiempo.parsearMs("2026-10-20T13:05:11.123456+00:00")
        assertEquals("2026-10-20T13:05:11.123456+00:00 -> ms", 1_792_501_511_123L, ms)
        assertEquals(ms, Tiempo.parsearMs("2026-10-20T13:05:11.123456Z")?.let { it - it % 1000 + 123 })
        assertNull(Tiempo.parsearMs("ayer"))
        assertNull(Tiempo.parsearMs(null))
        assertEquals("20 oct, 08:05", Tiempo.horaCorta(ms))   // UTC-5
        assertTrue(Tiempo.desactualizado(ms, ms!! + 4 * 3_600_000))
        assertTrue(!Tiempo.desactualizado(ms, ms + 2 * 3_600_000))
    }

    @Test
    fun etiqueta_del_dia() {
        val hoy = LocalDate.of(2026, 10, 20)   // martes
        assertEquals("Hoy", Tiempo.etiquetaDia("2026-10-20", hoy))
        assertEquals("Mañana", Tiempo.etiquetaDia("2026-10-21", hoy))
        assertEquals("Jueves", Tiempo.etiquetaDia("2026-10-22", hoy))
    }

    // ---- orden de alertas ----
    private fun alerta(tipo: String, nivel: String, ts: String, zona: String = "Cajamarca") =
        AlertaActual(tipo = tipo, referencia = "$tipo-$nivel", zona = zona, nivel = nivel, ts = ts)

    @Test
    fun orden_emergencia_alerta_aviso_y_oficiales_primero() {
        val lista = listOf(
            alerta("lluvia", "aviso", "2026-10-20T12:00:00Z"),
            alerta("aviso", "aviso", "2026-10-20T10:00:00Z"),
            alerta("caudal", "emergencia", "2026-10-20T09:00:00Z"),
            alerta("aviso", "alerta", "2026-10-20T11:00:00Z"),
            alerta("nivel_bajo", "emergencia", "2026-10-20T13:00:00Z"),   // vaciante: como mucho aviso
            alerta("aviso", "aviso", "2026-10-20T11:30:00Z"),
        )
        val orden = Alertas.ordenar(lista).map { it.referencia }
        // el rio muy bajo vale "aviso" (oficial) y, al ser el mas reciente de ese nivel, va antes que los avisos amarillos
        assertEquals(listOf("caudal-emergencia", "aviso-alerta", "nivel_bajo-emergencia", "aviso-aviso", "aviso-aviso", "lluvia-aviso"), orden)
        // dentro del mismo nivel y oficialidad, la mas reciente primero
        assertEquals("2026-10-20T13:00:00Z", Alertas.ordenar(lista)[2].ts)
        assertEquals("2026-10-20T11:30:00Z", Alertas.ordenar(lista)[3].ts)
    }

    @Test
    fun lluvia_medida_nunca_es_oficial_ni_pasa_de_aviso() {
        val lluvia = alerta("lluvia", "alerta", "2026-10-20T12:00:00Z")
        assertTrue(!Alertas.esOficial(lluvia))
        assertEquals(Nivel.AVISO, Alertas.nivelDe(lluvia))
        assertEquals(0, Alertas.cuantasOficiales(listOf(lluvia)))
        assertEquals(1, Alertas.cuantasOficiales(listOf(lluvia, alerta("aviso", "alerta", "2026-10-20T12:00:00Z"))))
    }

    @Test
    fun filtro_por_zona_sin_tildes() {
        val lista = listOf(alerta("aviso", "aviso", "2026-10-20T10:00:00Z", zona = "Áncash"), alerta("aviso", "aviso", "2026-10-20T10:00:00Z", zona = "Lima"))
        assertEquals(1, Alertas.deZona(lista, "Ancash").size)
        assertEquals(0, Alertas.deZona(lista, "Cajamarca").size)
    }

    @Test
    fun nivel_desde_texto_nunca_normal_por_error() {
        assertEquals(Nivel.ALERTA, Nivel.desde("alerta"))
        assertEquals(Nivel.SIN_DATO, Nivel.desde(null))
        assertEquals(Nivel.SIN_DATO, Nivel.desde("cualquier cosa"))
    }

    // ---- a donde acudir ----
    private fun punto(clave: String, tipo: String, lat: Double, lon: Double, categoria: String? = null, h24: Boolean? = null) =
        PuntoAcudir(clave = clave, tipo = tipo, nombre = clave, categoria = categoria, atiende_24h = h24, lat = lat, lon = lon)

    @Test
    fun tarjeta_prefiere_hospital_24h_cercano_y_el_mas_cercano_del_resto() {
        val yo = -7.1617 to -78.5127
        val puntos = listOf(
            punto("posta", "salud", -7.1620, -78.5130, "Puesto de salud I-1"),            // a 40 m
            punto("hospital", "salud", -7.1660, -78.5100, "Hospital II-2", true),         // a unos 560 m, 24 h
            punto("comi_lejos", "comisaria", -7.30, -78.50),
            punto("comi_cerca", "comisaria", -7.1630, -78.5120),
            punto("bomberos", "bomberos", -7.1650, -78.5150),
            punto("civil", "otro", -7.1618, -78.5128),
        )
        val t = Acudir.paraTarjeta(puntos, yo.first, yo.second)
        assertEquals(listOf("hospital", "comi_cerca", "bomberos"), t.map { it.punto.clave })
        assertTrue(t[0].distanciaKm > 0.4 && t[0].distanciaKm < 0.7)
    }

    @Test
    fun tarjeta_sin_hospital_24h_toma_el_mas_cercano() {
        val puntos = listOf(
            punto("posta", "salud", -7.1620, -78.5130, "Puesto de salud I-1"),
            punto("hospital_lejos", "salud", -7.40, -78.51, "Hospital II-2", true),   // a mas de 15 km
        )
        val t = Acudir.paraTarjeta(puntos, -7.1617, -78.5127)
        assertEquals(listOf("posta"), t.map { it.punto.clave })
    }

    // ---- pronostico ----
    @Test
    fun franja_de_la_localidad_mas_cercana() {
        val filas = listOf(
            PronosticoVigente(codigo = "A", nombre = "Cajamarca", lat = -7.16, lon = -78.51, fecha = "2026-10-21", tipo = "lluvia", posible = true, momento = "en la tarde"),
            PronosticoVigente(codigo = "A", nombre = "Cajamarca", lat = -7.16, lon = -78.51, fecha = "2026-10-20", tipo = "sin_lluvia", cielo = "nublado", tmax = 21, tmin = 7),
            PronosticoVigente(codigo = "B", nombre = "Celendin", lat = -6.86, lon = -78.14, fecha = "2026-10-20", tipo = "tormenta"),
        )
        val codigo = Pronostico.localidadCercana(filas, -7.1617, -78.5127)
        assertEquals("A", codigo)
        val franja = Pronostico.franja(filas, codigo)
        assertEquals(listOf("2026-10-20", "2026-10-21"), franja.map { it.fecha })
        assertEquals("Nublado", Pronostico.resumenDia(franja[0]))
        assertEquals("21° / 7°", Pronostico.temperaturas(franja[0]))
        assertEquals("Puede llover en la tarde", Pronostico.resumenDia(franja[1]))
        assertEquals("Tormenta", Pronostico.resumenDia(filas[2]))
    }

    // ---- rios ----
    @Test
    fun rio_toma_la_peor_senal_y_el_bajo_es_como_mucho_aviso() {
        val normal = LecturaRio(estacion = "A", valor = 1.0, unidad = "m3/s", umbral_alerta = 10.0, umbral_emergencia = 20.0, estado = "normal")
        val bajo = LecturaRio(estacion = "B", valor = 0.2, unidad = "m", umbral_alerta = 1.0, umbral_emergencia = 0.5, estado = "emergencia")
        val crecido = LecturaRio(estacion = "C", valor = 25.0, unidad = "m3/s", umbral_alerta = 10.0, umbral_emergencia = 20.0, estado = "emergencia")
        assertEquals(Nivel.NORMAL, Rios.resumir(RioCauceSenal("x", listOf(normal)), "X").nivel)
        assertEquals(Nivel.AVISO, Rios.resumir(RioCauceSenal("x", listOf(bajo)), "X").nivel)
        assertEquals(Nivel.EMERGENCIA, Rios.resumir(RioCauceSenal("x", listOf(normal, crecido)), "X").nivel)
        assertEquals(Nivel.SIN_DATO, Rios.resumir(RioCauceSenal("x"), "X").nivel)
        // el aviso hidrologico naranja sube un rio tranquilo; uno en descenso no
        assertEquals(Nivel.ALERTA, Rios.resumir(RioCauceSenal("x", listOf(normal), listOf(AvisoHidro(nivel = 3, sentido = "crecida"))), "X").nivel)
        assertEquals(Nivel.NORMAL, Rios.resumir(RioCauceSenal("x", listOf(normal), listOf(AvisoHidro(nivel = 4, sentido = "descenso"))), "X").nivel)
    }
}
