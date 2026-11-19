package pe.simpac.app

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pe.simpac.app.data.AvisoVigente
import pe.simpac.app.data.LluviaSenamhiActual
import pe.simpac.app.data.NowcastEstado
import pe.simpac.app.data.PronosticoLocalidad
import pe.simpac.app.data.RioIncidente
import pe.simpac.app.dominio.DiaMapa
import pe.simpac.app.dominio.Fen
import pe.simpac.app.dominio.Incidentes
import pe.simpac.app.dominio.Lluvia
import pe.simpac.app.dominio.Nowcast
import pe.simpac.app.dominio.Paleta
import pe.simpac.app.dominio.PronosticoMapa
import pe.simpac.app.dominio.Reportes
import pe.simpac.app.ui.mapa.Capa
import java.time.LocalDate

/** Logica pura de las capas nuevas del mapa (pronostico, nowcasting, lluvia, El Nino, desbordes, reportes). */
class MapaCapasTest {
    // 2026-11-19 15:00 en Lima (UTC-5) = 20:00 UTC
    private val AHORA = java.time.ZonedDateTime.of(2026, 11, 19, 20, 0, 0, 0, java.time.ZoneOffset.UTC).toInstant().toEpochMilli()

    // ---- selector de dia -> fecha ----
    @Test
    fun dia_elegido_da_la_fecha_en_hora_del_peru() {
        assertEquals("2026-11-19", DiaMapa.HOY.fechaIso(AHORA))
        assertEquals("2026-11-20", DiaMapa.MANANA.fechaIso(AHORA))
        assertEquals("2026-11-21", DiaMapa.PASADO.fechaIso(AHORA))
        // a las 23:30 de Lima (04:30 UTC del dia siguiente) sigue siendo el 19 en el Peru
        val noche = java.time.ZonedDateTime.of(2026, 11, 20, 4, 30, 0, 0, java.time.ZoneOffset.UTC).toInstant().toEpochMilli()
        assertEquals("2026-11-19", DiaMapa.HOY.fechaIso(noche))
        assertEquals(DiaMapa.MANANA, DiaMapa.desdeClave("manana"))
        assertEquals(DiaMapa.HOY, DiaMapa.desdeClave("cualquiera"))
    }

    @Test
    fun ventana_del_dia_hoy_empieza_ahora_y_los_otros_dias_enteros() {
        val (desdeHoy, hastaHoy) = PronosticoMapa.ventana(DiaMapa.HOY, AHORA)
        assertEquals(AHORA, desdeHoy)
        // fin de hoy en Lima: 2026-11-20 00:00 -05:00 = 05:00 UTC
        assertEquals(java.time.ZonedDateTime.of(2026, 11, 20, 5, 0, 0, 0, java.time.ZoneOffset.UTC).toInstant().toEpochMilli(), hastaHoy)
        val (desdeManana, hastaManana) = PronosticoMapa.ventana(DiaMapa.MANANA, AHORA)
        assertEquals(hastaHoy, desdeManana)
        assertEquals(hastaHoy + 86_400_000L, hastaManana)
    }

    @Test
    fun avisos_del_dia_filtra_por_la_fecha_elegida() {
        val geo = Json.parseToJsonElement("""{"type":"Polygon","coordinates":[[[-78.6,-7.2],[-78.4,-7.2],[-78.4,-7.0],[-78.6,-7.2]]]}""")
        val hoy = AvisoVigente(1, nivel = 3, inicio = "2026-11-19T05:00:00+00:00", fin = "2026-11-20T04:59:00+00:00", geojson = geo)
        val pasado = AvisoVigente(2, nivel = 2, inicio = "2026-11-21T05:00:00+00:00", fin = "2026-11-22T04:59:00+00:00", geojson = geo)
        val yaTermino = AvisoVigente(3, nivel = 4, inicio = "2026-11-19T05:00:00+00:00", fin = "2026-11-19T15:00:00+00:00", geojson = geo)
        val todos = listOf(hoy, pasado, yaTermino)
        assertEquals(listOf(1L), PronosticoMapa.avisosDelDia(todos, DiaMapa.HOY, AHORA).map { it.id })
        assertEquals(emptyList<Long>(), PronosticoMapa.avisosDelDia(todos, DiaMapa.MANANA, AHORA).map { it.id })
        assertEquals(listOf(2L), PronosticoMapa.avisosDelDia(todos, DiaMapa.PASADO, AHORA).map { it.id })
        assertEquals("No hay avisos de SENAMHI para mañana.", PronosticoMapa.notaAvisos(emptyList(), DiaMapa.MANANA))
        assertTrue(PronosticoMapa.notaAvisos(listOf(hoy), DiaMapa.HOY).startsWith("Avisos para hoy: 1 de otro tipo (el más alto, naranja)."))
    }

    // ---- glifo por tipo de pronostico (lib/pronostico.js aspecto) ----
    private fun fila(tipo: String? = null, posible: Boolean = false, segura: Boolean = false, cielo: String? = null, texto: String? = null, momento: String? = null, intensidad: String? = null, granizo: Boolean = false) =
        PronosticoLocalidad("06-0123", "Bambamarca", "Cajamarca", -6.67, -78.52, "2026-11-19", "2026-11-18", 24, 13, texto, tipo, posible, "texto", segura, granizo, intensidad, momento, cielo, null)

    @Test
    fun glifo_y_frase_por_tipo_de_pronostico() {
        val lluvia = PronosticoMapa.aspecto(fila("lluvia", intensidad = "moderada", momento = "en la tarde"))
        assertEquals("lluvia", lluvia.glifo); assertFalse(lluvia.posible); assertEquals("Lluvia moderada en la tarde", lluvia.corto); assertEquals(600, lluvia.prioridad)
        val tendencia = PronosticoMapa.aspecto(fila("lluvia", posible = true))
        assertEquals("tendencia", tendencia.glifo); assertTrue(tendencia.posible); assertEquals("posible", tendencia.tono); assertEquals("Puede llover", tendencia.corto)
        assertEquals("#93C5FD", Paleta.hex(tendencia.color))
        val tormenta = PronosticoMapa.aspecto(fila("tormenta"))
        assertEquals("tormenta", tormenta.glifo); assertEquals("Tormenta", tormenta.corto); assertEquals(700, tormenta.prioridad)
        val tormentaPosible = PronosticoMapa.aspecto(fila("tormenta", posible = true, segura = true))
        assertEquals("tormenta", tormentaPosible.glifo); assertTrue(tormentaPosible.posible); assertEquals("Lluvia", tormentaPosible.corto); assertEquals("puede haber tormenta", tormentaPosible.extra)
        val nieve = PronosticoMapa.aspecto(fila("nieve", texto = "Cielo nublado con nevadas en la tarde", granizo = true))
        assertEquals("nieve", nieve.glifo); assertEquals("Nieve", nieve.corto); assertEquals("con granizo", nieve.extra)
        assertEquals("Granizo", PronosticoMapa.aspecto(fila("nieve", texto = "Cielo nublado con granizo")).corto)
        assertEquals("sol", PronosticoMapa.aspecto(fila("sin_lluvia", cielo = "despejado")).glifo)
        assertEquals("nube", PronosticoMapa.aspecto(fila("sin_lluvia", cielo = "nublado")).glifo)
        val parcial = PronosticoMapa.aspecto(fila("sin_lluvia", cielo = "parcial"))
        assertEquals("sol_nube", parcial.glifo); assertEquals("Algo nublado", parcial.corto); assertEquals("seco", parcial.clase)
        assertEquals("Sin lluvia", PronosticoMapa.aspecto(fila("sin_lluvia")).corto)
        assertEquals("24°/13°", PronosticoMapa.temps(fila()))
        assertEquals("–", PronosticoMapa.temps(null))
    }

    @Test
    fun nota_del_pronostico_cuenta_por_tono() {
        val hoy = LocalDate.of(2026, 11, 19)
        val filas = listOf(fila("lluvia"), fila("lluvia", posible = true), fila("sin_lluvia"), fila("sin_lluvia"))
        assertEquals("Hoy, jue 19: lluvia en 1 localidad, puede llover en 1, sin lluvia en 2.", PronosticoMapa.nota(filas, "2026-11-19", hoy))
        assertEquals("SENAMHI no tiene pronóstico por localidad para ese día.", PronosticoMapa.nota(filas, "2026-11-21", hoy))
        assertEquals("Hoy, jueves 19", PronosticoMapa.diaConFecha("2026-11-19", hoy))
        assertEquals("Mañana, viernes 20", PronosticoMapa.diaConFecha("2026-11-20", hoy))
        assertEquals("Sábado 21", PronosticoMapa.diaConFecha("2026-11-21", hoy))
        assertEquals("Emitido anoche", PronosticoMapa.emitidoTexto("2026-11-18", hoy))
        assertTrue(PronosticoMapa.atrasado("2026-11-14", hoy))
        assertFalse(PronosticoMapa.atrasado("2026-11-16", hoy))
    }

    // ---- mapeo de RANGO a color (El Nino) ----
    @Test
    fun rango_fen_a_clase_y_color() {
        assertEquals("#3B3BEB", Paleta.hex(Fen.color("300 - 550")))        // medio 425: mucha mas lluvia
        assertEquals("#7B2FBE", Paleta.hex(Fen.color("> 2,500")))          // 2500: muchisima mas
        assertEquals("#95CEF4", Paleta.hex(Fen.color("60 - 120")))         // 90: mas lluvia
        assertEquals("#D4ECFA", Paleta.hex(Fen.color("30 - 60")))          // 45: algo mas
        assertEquals("#E5E5E5", Paleta.hex(Fen.color("-30 - 0")))          // -15: cerca de lo normal
        assertEquals("#E5E5E5", Paleta.hex(Fen.color("0 - 30")))
        assertEquals("#F0DDB0", Paleta.hex(Fen.color("-60 - -30")))        // -45: algo menos
        assertEquals("#D8B365", Paleta.hex(Fen.color("-210 - -120")))      // -165: menos
        assertEquals("#8C510A", Paleta.hex(Fen.color("-800 - -550")))      // -675: mucha menos
        assertEquals("#9CA3AF", Paleta.hex(Fen.color("sin datos")))
        assertNull(Fen.clase(null))
        assertEquals(0x40, Fen.alfa(Fen.clase("0 - 30")))
        assertEquals(0x99, Fen.alfa(Fen.clase("300 - 550")))
    }

    @Test
    fun frase_y_opciones_fen() {
        assertEquals("entre 300 y 550 mm más de lo normal", Fen.frase("300 - 550"))
        assertEquals("más de 2500 mm más de lo normal", Fen.frase("> 2,500"))
        assertEquals("más de 800 mm menos de lo normal", Fen.frase("< -800"))
        assertEquals("entre 120 y 210 mm menos de lo normal", Fen.frase("-210 - -120"))
        assertEquals("hasta 30 mm menos de lo normal (casi normal)", Fen.frase("-30 - 0"))
        assertEquals("hasta 30 mm más de lo normal (casi normal)", Fen.frase("0 - 30"))
        assertEquals(13, Fen.OPCIONES.size)
        assertEquals("El Niño 1997-1998, dic a feb", Fen.etiqueta("1997-1998", "DEF"))
        assertEquals("1997-1998|DEF", Fen.normalizar("1997-1998"))      // valor viejo (solo el evento)
        assertEquals("2023|EFM", Fen.normalizar("2023"))
        assertEquals(Fen.DEFECTO, Fen.normalizar("narnia"))
        assertEquals("2017" to "FMA", Fen.partir("2017|FMA"))
        val pols = Fen.poligonos(Json.parseToJsonElement("""{"type":"FeatureCollection","features":[
            {"type":"Feature","properties":{"RANGO":"60 - 120"},"geometry":{"type":"Polygon","coordinates":[[[-79,-7],[-78,-7],[-78,-6],[-79,-6],[-79,-7]]]}},
            {"type":"Feature","properties":{"RANGO":"< -800"},"geometry":{"type":"MultiPolygon","coordinates":[[[[-77,-7],[-76,-7],[-76,-6],[-77,-7]]],[[[-75,-7],[-74,-7],[-74,-6],[-75,-7]]]]}}]}"""))
        assertEquals(2, pols.size)
        assertEquals("#95CEF4", Paleta.hex(pols[0].clase!!.color))
        assertEquals(2, pols[1].anillos.size)
        assertEquals(-79.0, pols[0].caja.oeste, 1e-9)
    }

    // ---- agrupacion de rombos (desbordes) ----
    private fun inc(id: String, fecha: String?, lat: Double?, lon: Double?, tipo: String = "desborde", texto: String = fecha ?: "") =
        RioIncidente(id, "mashcon", fecha, texto, tipo, "Desborde $id", "Lugar", null, "punto", "Punto exacto", null, "oficial", "ANA", "https://x", null, lat, lon)

    @Test
    fun agrupa_los_rombos_que_se_enciman_y_pone_el_mas_nuevo_primero() {
        val a = inc("a", "2025-03-20", -7.18001, -78.50)
        val b = inc("b", "2022-04-01", -7.18010, -78.50)      // ~10 m de a
        val c = inc("c", "2014-03-26", -7.14777, -78.52)      // lejos
        val d = inc("d", null, -7.14780, -78.52, texto = "noviembre de 2012")   // sin fecha: por el ano del texto
        val grupos = Incidentes.agrupar(listOf(c, b, a, d), 50.0)
        assertEquals(2, grupos.size)
        assertEquals(listOf("a", "b"), grupos[0].incidentes.map { it.id })   // el mas nuevo manda y da el punto
        assertEquals(-7.18001, grupos[0].lat, 1e-9)
        assertEquals(listOf("c", "d"), grupos[1].incidentes.map { it.id })
        // con un radio chico (2 m: a y b distan ~10 m, c y d ~3 m) no se junta ninguno
        assertEquals(4, Incidentes.agrupar(listOf(a, b, c, d), 2.0).size)
        assertEquals("’25", Incidentes.anioCorto(a))
        assertEquals("’12", Incidentes.anioCorto(d))
        // los que no tienen lugar y las crecidas no se dibujan
        assertEquals(listOf("a"), Incidentes.dibujables(listOf(a, inc("x", "2026-03-13", null, null, tipo = "crecida"), inc("y", "2021-12-06", null, null))).map { it.id })
        // 26 px a zoom 13 en Cajamarca son unos 490 m
        val radio = Incidentes.radioM(-7.16, 13.0)
        assertTrue("$radio", radio > 450 && radio < 520)
        assertEquals(
            "2 incidentes documentados del río Mashcón con lugar (2022–2025). La ubicación es aproximada: toca un rombo para ver la fuente. Otro (2021) solo tiene el distrito.",
            Incidentes.nota(listOf(a, b, inc("y", "2021-12-06", null, null), inc("x", "2026-03-13", null, null, tipo = "crecida")), mapOf("mashcon" to "Río Mashcón")),
        )
    }

    // ---- lluvia de la ultima hora ----
    @Test
    fun intensidad_y_referencia_de_lluvia() {
        assertEquals("sin lluvia", Lluvia.intensidad(0.0)); assertEquals("ligera", Lluvia.intensidad(2.0)); assertEquals("moderada", Lluvia.intensidad(10.0))
        assertEquals("fuerte", Lluvia.intensidad(30.0)); assertEquals("muy fuerte", Lluvia.intensidad(45.0)); assertEquals("torrencial", Lluvia.intensidad(61.0)); assertNull(Lluvia.intensidad(null))
        val e = LluviaSenamhiActual("X@1,2", "SAUSAYA", pp_1h = 6.0, umbral_1h = 5.0, pp_6h = 8.0, umbral_6h = 15.0, lat = -14.5, lon = -71.3)
        val r = Lluvia.referencia(e)
        assertTrue(r.pasa1); assertFalse(r.pasa6); assertTrue(r.pasa)
        assertFalse(Lluvia.referencia(e.copy(umbral_1h = 0.0)).evaluable)
        assertTrue(Lluvia.referencia(e.copy(pp_1h = 1.0, pp_6h = 16.0)).pasa6)
        assertEquals(7f, Lluvia.radio("sin lluvia", true), 0f)
        assertEquals(3f, Lluvia.radio("sin lluvia", false), 0f)
        assertEquals("Sausaya", Lluvia.nombre("SAUSAYA"))
        assertEquals("Llovió en 1 de 2 estaciones en su última hora medida. En 1 pasó la referencia de SENAMHI.", Lluvia.nota(listOf(e, e.copy(clave = "y", pp_1h = 0.0))))
        assertEquals("Cuánta lluvia cayó el 18 nov (cada día va de 7:00 a 7:00), según SENAMHI.", Lluvia.notaObservada(Lluvia.observada("ayer"), "2026-11-18", null, null))
        assertEquals("Cuánta lluvia cayó del 12 nov al 18 nov (cada día va de 7:00 a 7:00), según SENAMHI.", Lluvia.notaObservada(Lluvia.observada("semana"), null, "2026-11-12", "2026-11-18"))
        assertEquals(listOf("1 a 5 mm", "5 a 15 mm", "15 a 30 mm", "más de 30 mm"), Lluvia.leyendaObservada(Lluvia.observada("ayer")).map { it.second })
        assertTrue(Lluvia.sldLluvia("monitoreo_meteorologico:prec_1", listOf(1, 5, 15, 30)).contains("quantity=\"5\" opacity=\"0.6\""))
    }

    // ---- nowcasting: nada si SENAMHI no publica hace mas de 30 min ----
    @Test
    fun nota_del_nowcasting() {
        val fresco = NowcastEstado(60, emision = "2026-11-19T19:40:00+00:00", valido_desde = "2026-11-19T19:40:00+00:00", valido_hasta = "2026-11-19T20:40:00+00:00", manchas = 3, vence_en = "2026-11-19T20:10:00+00:00", vigente = true)
        val n = Nowcast.nota(fresco, 3, 60, AHORA)
        assertEquals(Nowcast.EstadoNota.FRESCO, n.estado)
        assertEquals("Lluvia en la próxima hora · SENAMHI 14:40", n.corto)
        assertTrue(n.texto.startsWith("Experimental. Estimación de SENAMHI de las 14:40 (hace 20 min), válida hasta las 15:40."))
        assertEquals(Nowcast.EstadoNota.VACIO, Nowcast.nota(fresco, 0, 60, AHORA).estado)
        val viejo = fresco.copy(emision = "2026-11-19T18:00:00+00:00", vence_en = "2026-11-19T18:30:00+00:00", vigente = false)
        val nv = Nowcast.nota(viejo, 3, 60, AHORA)
        assertEquals(Nowcast.EstadoNota.VIEJO, nv.estado)
        assertEquals("Sin nowcasting reciente de SENAMHI (último 13:00)", nv.corto)
        // vigente segun la BD pero ya vencido para el reloj de la app: tampoco se muestra
        assertEquals(Nowcast.EstadoNota.VIEJO, Nowcast.nota(fresco.copy(vence_en = "2026-11-19T19:59:00+00:00"), 3, 60, AHORA).estado)
        assertEquals(Nowcast.EstadoNota.ERROR, Nowcast.nota(null, 3, 60, AHORA).estado)
        assertEquals(Nowcast.EstadoNota.ERROR, Nowcast.nota(fresco, null, 60, AHORA).estado)
        assertEquals("a las 14:40", Nowcast.lapso("2026-11-19T19:40:00+00:00", "2026-11-19T19:40:00+00:00"))
        assertEquals("Sobre Bambamarca", Nowcast.cercaDe(-6.68, -78.52, listOf(fila())))
        assertEquals("A unos 25 km de Bambamarca (Cajamarca)", Nowcast.cercaDe(-6.90, -78.52, listOf(fila())))
        assertNull(Nowcast.cercaDe(-9.0, -78.52, listOf(fila())))
    }

    // ---- reportes: tipos de reportTypes.js y opacidad por saldo de votos ----
    @Test
    fun reportes_tipo_color_y_opacidad() {
        assertEquals("#3B3BEB", Paleta.hex(Reportes.tipo("inundacion").color))
        assertEquals("#6B7280", Paleta.hex(Reportes.tipo("desconocido").color))
        assertEquals("Atasco moderado", Reportes.titulo("atasco", "moderado"))
        assertEquals("Huayco / deslizamiento", Reportes.titulo("huayco", null))
        assertEquals(0.45f, Reportes.opacidad("descartado", 9, 0), 0f)
        assertEquals(0.65f, Reportes.opacidad("sin_confirmar", 1, 3), 0f)
        assertEquals(1f, Reportes.opacidad("confirmado", 3, 1), 0f)
    }

    // ---- capas guardadas: las nuevas de fabrica se prenden una vez (marca v2) y las opciones viajan con ellas ----
    @Test
    fun capas_guardadas_y_opciones() {
        val viejas = Capa.desdeClaves(setOf("avisos", "rios"))
        assertTrue(Capa.PRONOSTICO in viejas); assertTrue(Capa.REPORTES in viejas); assertTrue(Capa.DESBORDES in viejas); assertFalse(Capa.NOWCAST in viejas); assertFalse(Capa.ZONAS in viejas)
        val nuevas = Capa.desdeClaves(setOf("avisos", "v2", "op:fen=2017|FMA"))
        assertEquals(setOf(Capa.AVISOS), nuevas)
        assertEquals(mapOf("fen" to "2017|FMA"), Capa.opcionesDesdeClaves(setOf("avisos", "v2", "op:fen=2017|FMA")))
        val claves = Capa.aClaves(setOf(Capa.AVISOS, Capa.FEN), mapOf("fen" to "2017|FMA", "nowcast" to "120"))
        assertEquals(setOf("avisos", "fen", "op:fen=2017|FMA", "op:nowcast=120", "v2"), claves)
        assertTrue(claves.none { it.contains(",") })
        // grupos en el orden de la web
        assertEquals(listOf("Alertas y avisos", "Pronóstico", "Lluvia", "Ríos y estaciones", "El Niño", "Comunidad", "A dónde acudir"), pe.simpac.app.ui.mapa.GruposCapa.ORDEN)
    }
}
