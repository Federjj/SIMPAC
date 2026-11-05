package pe.simpac.app.dominio

/**
 * Colores del mapa nativo: los mismos que frontend/src/map/palette.js (y lib/acudir.js para los
 * puntos de "A donde acudir"). Son ARGB como Long, listos para Color(...) de Compose o toInt() de
 * android.graphics. Un color solo nunca dice el nivel: el texto de la hoja lo acompana siempre.
 */
object Paleta {
    /** Area de un aviso de SENAMHI por nivel (layers/avisos.js NIVELES: relleno traslucido y borde). */
    val AVISO_AREA: Map<Int, Long> = mapOf(2 to 0xFFEBEB3B, 3 to 0xFFF58E27, 4 to 0xFFDB0404)
    /** Aro de la insignia de un aviso (palette.js AVISO_ARO): el amarillo va mas oscuro para leerse sobre el area. */
    val AVISO_ARO: Map<Int, Long> = mapOf(2 to 0xFFEAB308, 3 to 0xFFF58E27, 4 to 0xFFDB0404)

    /** Disco de una estacion de rio por estado (palette.js RIO_HEX). */
    val RIO: Map<EstadoCauce, Long> = mapOf(
        EstadoCauce.NORMAL to 0xFF3BEB40, EstadoCauce.ATENTO to 0xFFEBEB3B,
        EstadoCauce.ALERTA to 0xFFF58E27, EstadoCauce.EMERGENCIA to 0xFFDB0404, EstadoCauce.SD to 0xFF9CA3AF,
    )
    /** Cauce de un rio resaltado (palette.js CAUCE_HEX): azul agua si esta tranquilo. */
    val CAUCE: Map<EstadoCauce, Long> = mapOf(
        EstadoCauce.NORMAL to 0xFF1C7ED6, EstadoCauce.ATENTO to 0xFFEAB308,
        EstadoCauce.ALERTA to 0xFFF58E27, EstadoCauce.EMERGENCIA to 0xFFDB0404, EstadoCauce.SD to 0xFF94A3B8,
    )
    /** Relleno de una zona que un rio podria afectar, por nivel de la zona (palette.js ZONA_HEX). */
    val ZONA: Map<NivelZona, Long> = mapOf(
        NivelZona.EMERGENCIA to 0xFFDB0404, NivelZona.ALERTA to 0xFFF58E27,
        NivelZona.ATENTOS to 0xFFEAB308, NivelZona.SIN_SENALES to 0xFF1D4ED8,
    )
    /** Trazo oscuro de la zona (palette.js ZONA_OSCURO). */
    val ZONA_OSCURO: Map<NivelZona, Long> = mapOf(
        NivelZona.EMERGENCIA to 0xFF991B1B, NivelZona.ALERTA to 0xFFC2410C,
        NivelZona.ATENTOS to 0xFFA16207, NivelZona.SIN_SENALES to 0xFF1E3A8A,
    )
    /** Estaciones de SENAMHI: M meteorologica, H hidrologica (palette.js ESTACION_HEX). */
    val ESTACION: Map<String, Long> = mapOf("M" to 0xFF3BA5EB, "H" to 0xFF3B3BEB)
    const val SIN_DATO: Long = 0xFF9CA3AF
    const val AFLUENTE: Long = 0xFF5B8FC7
    const val HALO: Long = 0xFFFFFFFF
    /** Punto de tu ubicacion (azul de la marca). */
    const val UBICACION: Long = 0xFF1D4ED8

    /** "A donde acudir" por tipo (lib/acudir.js TIPO_ACUDIR): distintos de los del semaforo. */
    val ACUDIR: Map<String, Long> = mapOf(
        "salud" to 0xFF0F766E, "comisaria" to 0xFF1D4ED8, "bomberos" to 0xFF991B1B,
        "zona_segura" to 0xFF4D7C0F, "albergue" to 0xFF6D28D9, "otro" to 0xFF475569,
    )

    fun acudir(tipo: String?): Long = ACUDIR[tipo] ?: ACUDIR.getValue("otro")
    fun cauce(estado: EstadoCauce): Long = CAUCE.getValue(estado)
    fun rio(estado: EstadoCauce): Long = RIO.getValue(estado)
    fun zona(nivel: NivelZona): Long = ZONA.getValue(nivel)
    fun zonaOscuro(nivel: NivelZona): Long = ZONA_OSCURO.getValue(nivel)
    fun aviso(nivel: Int?): Long = AVISO_AREA[nivel] ?: SIN_DATO

    /** "#EAB308" (para pruebas y para comparar con la web). */
    fun hex(argb: Long): String = "#" + String.format(java.util.Locale.US, "%06X", argb and 0xFFFFFF)
}
