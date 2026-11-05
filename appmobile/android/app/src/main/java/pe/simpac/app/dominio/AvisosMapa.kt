package pe.simpac.app.dominio

import pe.simpac.app.data.AvisoVigente
import java.time.Instant
import java.time.ZonedDateTime

/**
 * Avisos de SENAMHI en el mapa: cuales rigen hoy, que icono llevan y como se dicen en lenguaje claro
 * (frontend/src/lib/avisoTexto.js y map/layers/avisos.js). Modulo puro.
 */
object AvisosMapa {
    val COLOR_NIVEL = mapOf(2 to "amarillo", 3 to "naranja", 4 to "rojo")
    val ETIQUETA_NIVEL = mapOf(2 to "Amarillo (nivel 2 de 4)", 3 to "Naranja (nivel 3 de 4)", 4 to "Rojo (nivel 4 de 4, el más grave)")
    const val FIRMA = "Ícono, zona simplificada y resumen de SIMPAC, basados en el aviso de SENAMHI."
    val GLIFOS = setOf("gota", "gota_rayo", "copo", "termometro", "termometro_frio", "viento")

    /** El backend guarda 'temperatura': el titulo dice si es por calor o por frio. */
    fun tema(a: AvisoVigente): String {
        val t = a.tema ?: "otro"
        if (t != "temperatura") return t
        return if (Regex("INCREMENTO|CALOR|ALTA", RegexOption.IGNORE_CASE).containsMatchIn(a.titulo ?: "")) "calor" else "frio"
    }

    /** Glifo de la insignia: el del worker (gota, gota_rayo, copo) o el del tema (calor, frio, viento); null = sin insignia. */
    fun glifo(a: AvisoVigente): String? {
        a.icono?.takeIf { it in GLIFOS }?.let { return it }
        return when (tema(a)) {
            "calor" -> "termometro"
            "frio" -> "termometro_frio"
            "viento" -> "viento"
            "lluvia" -> "gota"
            else -> null
        }
    }

    /** Un aviso es uno por tipo, anio y numero (sus mapas son los dias). */
    fun clave(a: AvisoVigente): String = "${a.tipo}-${a.anio ?: ""}-${a.numero ?: ""}"

    /** Los que rigen en algun momento de hoy (hora del Peru) desde ahora, con geometria y nivel conocido. */
    fun deHoy(avisos: List<AvisoVigente>, ahoraMs: Long = System.currentTimeMillis()): List<AvisoVigente> {
        val inicioDia = ZonedDateTime.ofInstant(Instant.ofEpochMilli(ahoraMs), Tiempo.ZONA_PERU).toLocalDate().atStartOfDay(Tiempo.ZONA_PERU).toInstant().toEpochMilli()
        val desde = maxOf(inicioDia, ahoraMs)
        val hasta = inicioDia + 86_400_000L
        return avisos.filter { a ->
            a.geojson != null && COLOR_NIVEL.containsKey(a.nivel) &&
                (Tiempo.parsearMs(a.inicio) ?: Long.MIN_VALUE) < hasta && (Tiempo.parsearMs(a.fin) ?: Long.MAX_VALUE) > desde
        }
    }

    /** Uno por aviso (el de nivel mas alto), del mas alto al mas bajo; en el mismo nivel, primero la lluvia y el meteorologico. */
    fun unoPorAviso(filas: List<AvisoVigente>): List<AvisoVigente> {
        val porClave = LinkedHashMap<String, AvisoVigente>()
        for (a in filas) {
            val k = clave(a)
            val previo = porClave[k]
            if (previo == null || (previo.nivel ?: 0) < (a.nivel ?: 0)) porClave[k] = a
        }
        return porClave.values.sortedWith(
            compareByDescending<AvisoVigente> { it.nivel ?: 0 }
                .thenBy { if (tema(it) == "lluvia") 0 else 1 }
                .thenBy { if (it.tipo == "lluvia24h") 1 else 0 },
        )
    }

    /** "Aviso naranja de SENAMHI por lluvias" (titulo de la hoja). */
    fun titulo(a: AvisoVigente): String {
        val cab = "Aviso ${COLOR_NIVEL[a.nivel] ?: ""} de SENAMHI".replace("  ", " ")
        if (a.tipo == "lluvia24h") return "$cab por lluvia acumulada en 24 h"
        return when (tema(a)) {
            "calor" -> "$cab por calor"
            "frio" -> "$cab por frío"
            "viento" -> "$cab por viento"
            "lluvia" -> if (a.icono == "copo") "$cab por nevadas" else "$cab por lluvias"
            else -> cab
        }
    }

    /** Frase corta de que se trata (la del tooltip de la web). */
    fun resumen(a: AvisoVigente): String {
        if (a.tipo == "lluvia24h") return "Puede llover en algún momento en esta zona hasta el fin del aviso."
        return when (tema(a)) {
            "calor" -> "Temperaturas más altas de lo normal en la zona del aviso."
            "frio" -> "Temperaturas más bajas de lo normal en la zona del aviso."
            "viento" -> "Ráfagas de viento en la zona del aviso."
            "lluvia" -> when (a.icono) {
                "copo" -> "Puede nevar en algún momento en las partes altas de esta zona."
                "gota_rayo" -> "Puede llover, con rayos, en algún momento en esta zona."
                else -> "Puede llover en algún momento en esta zona. No quiere decir que llueva en toda la zona ni todo el día."
            }
            else -> "Aviso oficial de SENAMHI."
        }
    }

    /** "Nivel naranja (3 de 4): ..." en palabras, con que hacer. */
    fun accion(nivel: Int?): String? = when (nivel) {
        2 -> "Revisa techos, canaletas y acequias; si llueve fuerte, no cruces ríos ni quebradas."
        3 -> "Evita quebradas y laderas; si llueve fuerte, no cruces ríos ni huaycos."
        4 -> "Aléjate de ríos, quebradas y laderas, y sigue las indicaciones de Defensa Civil."
        else -> null
    }

    /** "Rige del 4 nov, 00:00 al 4 nov, 23:59 (hora del Perú)". */
    fun vigencia(a: AvisoVigente): String? {
        val i = Tiempo.parsearMs(a.inicio)
        val f = Tiempo.parsearMs(a.fin)
        return when {
            i != null && f != null -> "Rige del ${Tiempo.horaCorta(i)} al ${Tiempo.horaCorta(f)} (hora del Perú)"
            f != null -> "Rige hasta el ${Tiempo.horaCorta(f)} (hora del Perú)"
            else -> null
        }
    }
}
