package pe.simpac.app.dominio

import pe.simpac.app.data.AvisoVigente
import pe.simpac.app.data.PronosticoLocalidad
import java.time.Instant
import java.time.LocalDate
import java.time.ZonedDateTime

/** El dia elegido arriba del mapa: mueve a la vez los avisos de SENAMHI y el pronostico por localidad. */
enum class DiaMapa(val clave: String, val etiqueta: String, val dias: Long, val para: String) {
    HOY("ahora", "Hoy", 0, "hoy"),
    MANANA("manana", "Mañana", 1, "mañana"),
    PASADO("pasado", "Pasado", 2, "pasado mañana");

    /** "AAAA-MM-DD" del dia elegido en hora del Peru. */
    fun fecha(ahoraMs: Long = System.currentTimeMillis()): LocalDate = Tiempo.hoyPeru(ahoraMs).plusDays(dias)
    fun fechaIso(ahoraMs: Long = System.currentTimeMillis()): String = fecha(ahoraMs).toString()

    companion object {
        fun desdeClave(clave: String?): DiaMapa = entries.firstOrNull { it.clave == clave } ?: HOY
    }
}

/**
 * Pronostico oficial de SENAMHI por localidad en el mapa (vista pronostico_vigente): como se dibuja y
 * se dice cada dia (frontend/src/lib/pronostico.js aspecto() y notaPronostico()), y que avisos rigen
 * el dia elegido (map/layers/avisos.js ventana()). Nunca usa amarillo, naranja ni rojo (son de los
 * avisos). Modulo puro.
 */
object PronosticoMapa {
    /** Color del punto por tono (palette.js PRONOSTICO_HEX). */
    val COLOR_TONO: Map<String, Long> = mapOf(
        "lluvia" to 0xFF1C7ED6, "posible" to 0xFF93C5FD, "tormenta" to 0xFF4338CA, "nieve" to 0xFF0891B2, "seco" to 0xFFCBD5E1,
    )
    val PRIORIDAD = mapOf("tormenta" to 700, "nieve" to 650, "lluvia" to 600, "posible" to 500, "seco" to 300)
    private val RX_NIEVE = Regex("\\b(?:NEVADAS?|NIEVE|AGUANIEVE)\\b")

    /** Como se dibuja y se dice un dia. */
    data class Aspecto(val glifo: String, val clase: String, val tono: String, val posible: Boolean, val corto: String, val extra: String?) {
        val prioridad: Int get() = PRIORIDAD[tono] ?: 0
        val color: Long get() = COLOR_TONO[tono] ?: COLOR_TONO.getValue("seco")
    }

    private fun plano(t: String?): String = Departamentos.sinTildes(t ?: "").uppercase()

    fun aspecto(f: PronosticoLocalidad): Aspecto {
        val m = f.momento?.let { " $it" } ?: ""
        fun a(glifo: String, clase: String, posible: Boolean, corto: String, extra: String? = null, tono: String = clase) =
            Aspecto(glifo, clase, tono, posible, corto, extra)
        return when (f.tipo) {
            "tormenta" -> when {
                !f.posible -> a("tormenta", "tormenta", false, "Tormenta$m")
                f.lluvia_segura -> a("tormenta", "tormenta", true, "Lluvia$m", "puede haber tormenta")
                else -> a("tormenta", "tormenta", true, "Puede haber tormenta$m")
            }
            "nieve" -> {
                val p = f.posible
                if (RX_NIEVE.containsMatchIn(plano(f.texto))) a("nieve", "nieve", p, if (p) "Puede nevar$m" else "Nieve$m", if (f.granizo) "con granizo" else null)
                else a("nieve", "nieve", p, if (p) "Puede granizar$m" else "Granizo$m")
            }
            "lluvia" -> if (f.posible) a("tendencia", "lluvia", true, "Puede llover$m", null, "posible")
            else a("lluvia", "lluvia", false, "Lluvia${f.intensidad?.let { " $it" } ?: ""}$m")
            else -> when (f.cielo) {
                "despejado" -> a("sol", "seco", false, "Despejado")
                "nublado" -> a("nube", "seco", false, "Nublado")
                "neblina" -> a("nube", "seco", false, "Neblina")
                "parcial" -> a("sol_nube", "seco", false, "Algo nublado")
                else -> a("sol_nube", "seco", false, "Sin lluvia")
            }
        }
    }

    /** "21°/10°" (o "–" si SENAMHI no da temperaturas). */
    fun temps(f: PronosticoLocalidad?): String {
        if (f?.tmax == null && f?.tmin == null) return "–"
        fun t(v: Int?) = if (v == null) "–" else "$v°"
        return "${t(f.tmax)}/${t(f.tmin)}"
    }

    fun urlLocalidad(codigo: String): String {
        val partes = codigo.split("-")
        return "https://www.senamhi.gob.pe/?p=pronostico-detalle&dp=${partes.getOrNull(0) ?: ""}&localidad=${partes.getOrNull(1) ?: ""}"
    }

    /** "Hoy, miércoles 19", "Mañana, jueves 20" o "Viernes 21". */
    fun diaConFecha(fecha: String, hoy: LocalDate = Tiempo.hoyPeru()): String {
        val f = runCatching { LocalDate.parse(fecha) }.getOrNull() ?: return fecha
        val dia = "${DIAS[f.dayOfWeek.value - 1]} ${f.dayOfMonth}"
        return when (f.toEpochDay() - hoy.toEpochDay()) {
            0L -> "Hoy, $dia"
            1L -> "Mañana, $dia"
            else -> dia.replaceFirstChar { it.uppercase() }
        }
    }
    private val DIAS = listOf("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    private val DIAS_CORTOS = listOf("lun", "mar", "mié", "jue", "vie", "sáb", "dom")

    /** "mié 19" para el titulo corto. */
    fun diaCorto(fecha: String): String {
        val f = runCatching { LocalDate.parse(fecha) }.getOrNull() ?: return fecha
        return "${DIAS_CORTOS[f.dayOfWeek.value - 1]} ${f.dayOfMonth}"
    }

    /** Mas de 3 dias sin un pronostico nuevo (SENAMHI no lo actualiza los fines de semana ni feriados). */
    fun atrasado(emision: String?, hoy: LocalDate = Tiempo.hoyPeru()): Boolean {
        val e = runCatching { LocalDate.parse(emision ?: return false) }.getOrNull() ?: return false
        return hoy.toEpochDay() - e.toEpochDay() > 3
    }

    fun emisionMax(filas: List<PronosticoLocalidad>): String? = filas.mapNotNull { it.emision }.maxOrNull()

    /** Nota de la capa: "Hoy, mié 19: lluvia en 57 localidades, puede llover en 42, ... sin lluvia en 174." */
    fun nota(filas: List<PronosticoLocalidad>, fecha: String, hoy: LocalDate = Tiempo.hoyPeru()): String {
        val deDia = filas.filter { it.fecha == fecha }
        if (deDia.isEmpty()) return "SENAMHI no tiene pronóstico por localidad para ese día."
        val n = HashMap<String, Int>()
        for (f in deDia) { val t = aspecto(f).tono; n[t] = (n[t] ?: 0) + 1 }
        val partes = listOf("lluvia" to "lluvia en", "posible" to "puede llover en", "tormenta" to "tormenta en", "nieve" to "nieve o granizo en", "seco" to "sin lluvia en")
            .filter { (n[it.first] ?: 0) > 0 }
            .mapIndexed { i, (k, t) -> "$t ${n[k]}${if (i == 0) (if (n[k] == 1) " localidad" else " localidades") else ""}" }
        var texto = "${diaConFechaCorta(fecha, hoy)}: ${partes.joinToString(", ")}."
        val emision = emisionMax(deDia)
        if (atrasado(emision, hoy)) texto += " Emitido el ${Tiempo.fechaLarga(emision)}: SENAMHI no lo actualiza los fines de semana ni feriados."
        return texto
    }

    private fun diaConFechaCorta(fecha: String, hoy: LocalDate): String {
        val f = runCatching { LocalDate.parse(fecha) }.getOrNull() ?: return fecha
        return when (f.toEpochDay() - hoy.toEpochDay()) {
            0L -> "Hoy, ${diaCorto(fecha)}"
            1L -> "Mañana, ${diaCorto(fecha)}"
            else -> diaCorto(fecha).replaceFirstChar { it.uppercase() }
        }
    }

    /** Codigo de la localidad con pronostico mas cercana a (lat, lon); null si no hay. */
    fun localidadCercana(filas: List<PronosticoLocalidad>, lat: Double, lon: Double): String? =
        filas.filter { it.lat != null && it.lon != null }.minByOrNull { Geo.distanciaKm(lat, lon, it.lat!!, it.lon!!) }?.codigo

    /** Los 3 dias de una localidad: (fecha, fila o null). */
    fun franja(filas: List<PronosticoLocalidad>, codigo: String, hoy: LocalDate = Tiempo.hoyPeru()): List<Pair<String, PronosticoLocalidad?>> =
        (0L..2L).map { n -> val f = hoy.plusDays(n).toString(); f to filas.firstOrNull { it.codigo == codigo && it.fecha == f } }

    /** "Emitido hoy", "Emitido anoche" o "Emitido el 18 nov 2026". */
    fun emitidoTexto(emision: String?, hoy: LocalDate = Tiempo.hoyPeru()): String {
        if (emision.isNullOrBlank()) return ""
        val e = runCatching { LocalDate.parse(emision) }.getOrNull() ?: return "Emitido el $emision"
        return when (hoy.toEpochDay() - e.toEpochDay()) {
            0L -> "Emitido hoy"
            1L -> "Emitido anoche"
            else -> "Emitido el ${Tiempo.fechaLarga(emision)}"
        }
    }

    // ---- avisos por dia (map/layers/avisos.js ventana) ----

    /** Ventana del dia elegido en hora del Peru: desde ahora si es hoy, todo el dia si es manana o pasado. */
    fun ventana(dia: DiaMapa, ahoraMs: Long = System.currentTimeMillis()): Pair<Long, Long> {
        val inicio = ZonedDateTime.ofInstant(Instant.ofEpochMilli(ahoraMs), Tiempo.ZONA_PERU).toLocalDate().plusDays(dia.dias)
            .atStartOfDay(Tiempo.ZONA_PERU).toInstant().toEpochMilli()
        return maxOf(inicio, ahoraMs) to inicio + 86_400_000L
    }

    /** Los avisos que rigen en algun momento del dia elegido (con geometria y nivel conocido). */
    fun avisosDelDia(avisos: List<AvisoVigente>, dia: DiaMapa, ahoraMs: Long = System.currentTimeMillis()): List<AvisoVigente> {
        val (desde, hasta) = ventana(dia, ahoraMs)
        return avisos.filter { a ->
            a.geojson != null && AvisosMapa.COLOR_NIVEL.containsKey(a.nivel) &&
                (Tiempo.parsearMs(a.inicio) ?: Long.MIN_VALUE) < hasta && (Tiempo.parsearMs(a.fin) ?: Long.MAX_VALUE) > desde
        }
    }

    private val TEMAS = listOf("lluvia" to "de lluvia", "calor" to "de calor", "frio" to "de frío", "viento" to "de viento", "otro" to "de otro tipo")

    /** Nota de la capa de avisos: "Avisos para hoy: 3 de lluvia (el más alto, naranja). Toca un área..." */
    fun notaAvisos(lista: List<AvisoVigente>, dia: DiaMapa): String {
        if (lista.isEmpty()) return "No hay avisos de SENAMHI para ${dia.para}."
        val partes = TEMAS.mapNotNull { (clave, texto) ->
            val deTema = lista.filter { AvisosMapa.tema(it) == clave }
            if (deTema.isEmpty()) return@mapNotNull null
            val n = deTema.map { AvisosMapa.clave(it) }.toSet().size
            val peor = AvisosMapa.COLOR_NIVEL[deTema.maxOf { it.nivel ?: 0 }] ?: ""
            "$n $texto (el más alto, $peor)"
        }
        val temas = if (partes.size > 1) partes.dropLast(1).joinToString(", ") + " y " + partes.last() else partes.firstOrNull() ?: ""
        return "Avisos para ${dia.para}: $temas. Toca un área o un ícono para ver de qué trata."
    }
}
