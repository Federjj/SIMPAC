package pe.simpac.app

import kotlinx.serialization.builtins.ListSerializer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pe.simpac.app.data.AlertaActual
import pe.simpac.app.data.JsonSimpac
import pe.simpac.app.data.PronosticoVigente
import pe.simpac.app.data.PuntoAcudir
import pe.simpac.app.data.RioCauceSenal
import pe.simpac.app.data.Snapshot
import pe.simpac.app.data.TitularZona

/** Parseo de las respuestas reales de la API REST de Supabase y del snapshot de la API. */
class ModelosTest {
    @Test
    fun titular_zona_con_campos_nulos_y_desconocidos() {
        val json = """[{"departamento":"Cajamarca","nivel":"alerta","titular_corto":"ALERTA en Cajamarca: aviso naranja de SENAMHI por lluvias.",
            "titular":"largo","detalle":null,"generado_en":"2026-10-20T13:05:11.123456+00:00","revisado_en":"2026-10-20T14:35:00+00:00","origen":"reglas","insumos":{"x":1}}]"""
        val filas = JsonSimpac.decodeFromString(ListSerializer(TitularZona.serializer()), json)
        assertEquals(1, filas.size)
        assertEquals("Cajamarca", filas[0].departamento)
        assertEquals("alerta", filas[0].nivel)
        assertNull(filas[0].detalle)
        assertEquals("reglas", filas[0].origen)
    }

    @Test
    fun alerta_actual_lluvia_y_aviso() {
        val json = """[{"tipo":"lluvia","referencia":"472A2C3E","zona":"Arequipa","nivel":"aviso","detalle":"Cotahuasi midio 6.2 mm en 6 h","valor":6.2,"umbral":5.0,"ventana_h":6,"ts":"2026-10-20T12:00:00+00:00","lat":-15.2,"lon":-72.9},
            {"tipo":"aviso","referencia":"SENAMHI aviso 421","zona":"Cajamarca","nivel":"alerta","detalle":"Lluvias de moderada a fuerte intensidad","valor":null,"umbral":null,"ventana_h":null,"ts":"2026-10-20T11:00:00+00:00","lat":null,"lon":null}]"""
        val filas = JsonSimpac.decodeFromString(ListSerializer(AlertaActual.serializer()), json)
        assertEquals(2, filas.size)
        assertEquals(6, filas[0].ventana_h)
        assertNull(filas[1].valor)
        assertNull(filas[1].oficial)
    }

    @Test
    fun pronostico_vigente_booleanos_y_enteros() {
        val json = """[{"codigo":"06-0011","nombre":"Cajamarca","departamento":"Cajamarca","lat":-7.16,"lon":-78.51,"fecha":"2026-10-20","emision":"2026-10-20",
            "tmax":21,"tmin":7,"texto":"Cielo nublado...","tipo":"lluvia","posible":true,"por":"texto","lluvia_segura":false,"granizo":false,"intensidad":"ligera","momento":"en la tarde","cielo":null,"url":"https://www.senamhi.gob.pe/?p=pronostico-detalle&dp=06&localidad=0011"}]"""
        val f = JsonSimpac.decodeFromString(ListSerializer(PronosticoVigente.serializer()), json)[0]
        assertEquals(21, f.tmax)
        assertTrue(f.posible)
        assertFalse(f.lluvia_segura)
        assertEquals("en la tarde", f.momento)
    }

    @Test
    fun punto_acudir_sin_telefono() {
        val json = """[{"clave":"comisarias:5000","tipo":"comisaria","nombre":"Comisaria Central Cajamarca","categoria":"Comisaria tipo A","atiende_24h":null,
            "direccion":"Jr. Amalia Puga 600","distrito":"Cajamarca","provincia":"Cajamarca","departamento":"Cajamarca","telefono":null,"lat":-7.158,"lon":-78.514,
            "fuente":"MININTER via CENEPRED","fuente_url":"https://x","atribucion":"MININTER","actualizado":"2019-11-01","detalle":{"nota":"padron 2019"}}]"""
        val p = JsonSimpac.decodeFromString(ListSerializer(PuntoAcudir.serializer()), json)[0]
        assertNull(p.telefono)
        assertNull(p.atiende_24h)
        assertEquals("2019-11-01", p.actualizado)
    }

    @Test
    fun rio_cauce_senal_con_lecturas_y_avisos() {
        val json = """[{"rio_ana":"Chancay","lecturas":[{"estacion":"Racarumi","departamento":"Lambayeque","valor":12.5,"unidad":"m3/s","umbral_alerta":150,"umbral_emergencia":250,"estado":"normal","tendencia":"estable","fecha":"2026-10-20","hora":"06:00","ts_captura":"2026-10-20T11:00:00+00:00"}],
            "avisos_hidro":[{"ca":"x","ce":"220213","numero":57,"titulo":"Aviso","nivel":3,"sentido":"crecida","inicio":"2026-10-20T00:00:00","fin":null,"fin_dia":"2026-10-22","valor":null,"unidad":null,"umbral_rojo":null,"url":"https://senamhi","visto_en":"2026-10-20T11:00:00+00:00"}]},
            {"rio_ana":"Sisa","lecturas":[],"avisos_hidro":[]}]"""
        val filas = JsonSimpac.decodeFromString(ListSerializer(RioCauceSenal.serializer()), json)
        assertEquals(2, filas.size)
        assertEquals(1, filas[0].lecturas.size)
        assertEquals(3, filas[0].avisos_hidro[0].nivel)
        assertTrue(filas[1].lecturas.isEmpty())
    }

    @Test
    fun snapshot_de_la_api() {
        val json = """{"generado":"2026-10-20T15:00:00+00:00","indices":[{"fuente":"ICEN","periodo":"2026-08","valor":3.73,"categoria":"extraordinaria","origen":"ENFEN"}],
            "enfen":{"anio":2026,"numero":18,"extraordinario":false,"fecha":"2026-10-16","estado":"Alerta de El Nino Costero","proximo":"2026-10-30","url":"https://x.pdf"},
            "caudales":[{"estacion":"Mashcon","rio":"Mashcon","departamento":"Cajamarca","fecha":"2026-10-20","hora":"06:00","valor":0.13,"unidad":"m3/s","umbral_alerta":15.4,"umbral_emergencia":19,"tendencia":"estable","estado":"normal","lat":-7.1,"lon":-78.5}],
            "alertas":[{"tipo":"lluvia","referencia":"X","zona":"Arequipa","nivel":"aviso","detalle":"d","valor":6.2,"umbral":5,"ventana_h":6,"ts":"2026-10-20T12:00:00+00:00","lat":null,"lon":null,"oficial":false}],
            "resumen":{"caudales":138,"en_alerta":["A"],"nivel_bajo":["B","C"],"alertas":1,"alertas_oficiales":0,"lluvia_sobre_referencia":1}}"""
        val s = JsonSimpac.decodeFromString(Snapshot.serializer(), json)
        assertEquals("Alerta de El Nino Costero", s.enfen?.estado)
        assertEquals(138, s.resumen?.caudales)
        assertEquals(listOf("B", "C"), s.resumen?.nivel_bajo)
        assertEquals(false, s.alertas[0].oficial)
        assertEquals(1, s.indices.size)
    }
}
