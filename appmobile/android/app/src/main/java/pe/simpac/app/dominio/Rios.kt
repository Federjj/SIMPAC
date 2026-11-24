package pe.simpac.app.dominio

import pe.simpac.app.data.CaudalActual
import pe.simpac.app.data.LecturaRio
import pe.simpac.app.data.RioCauceSenal
import pe.simpac.app.data.RioSenal
import pe.simpac.app.data.RioVigiladoMapa

/**
 * Un rio del departamento con el estado que dicen sus senales de hoy. `nivel` y `texto` son la medicion
 * de ANA o el aviso hidrologico que manda; `medicion` es siempre la de ANA con su estacion ("Estación
 * Mashcón (ANA): tranquila (0.13 m³/s)") y `cuenca`, si la hay, la senal de lluvia sobre la cuenca. Las dos
 * cosas son ciertas a la vez: el rio esta como lo mide su estacion y ademas puede subir.
 */
data class RioResumen(
    val rioAna: String,
    val nombre: String,
    val nivel: Nivel,
    val texto: String,
    val fuente: String,
    val medicion: String? = null,
    val cuenca: SenalCuenca? = null,
) {
    /** Con que nivel se elige el rio a destacar: una senal de cuenca sobre un rio tranquilo cuenta como "aviso" (atentos, como la zona en la web). */
    val nivelDestacar: Nivel get() = if (cuenca != null && nivel.orden > Nivel.AVISO.orden) Nivel.AVISO else nivel
}

/**
 * La senal de la cuenca de un rio (aviso de lluvias de SENAMHI en curso o lluvia medida sobre la referencia)
 * y la linea que la explica junto a la medicion: "Cuenca: aviso naranja de SENAMHI por lluvias vigente hoy;
 * el caudal puede subir." `detalle` trae las estaciones de la lluvia medida; `url`, el aviso oficial.
 */
data class SenalCuenca(val clave: String, val linea: String, val detalle: String?, val url: String?, val nivel: NivelZona)

/**
 * Estado de un rio con trazo a partir de rio_cauce_senal: la peor estacion de ANA en crecida o el aviso
 * hidrologico vigente de SENAMHI si es mas alto (la misma regla que frontend/src/lib/cauces.js).
 * Un rio en nivel bajo (vaciante) es como mucho "aviso". Sin lecturas ni avisos no hay "normal":
 * se dice "sin senales hoy" con nivel SIN_DATO para no afirmar calma sin medir.
 * La senal de la cuenca (aviso de lluvias o lluvia medida) no cambia ese nivel: se dice aparte.
 */
object Rios {
    const val PUEDE_SUBIR = "el caudal puede subir"
    private const val SUFIJO_CUENCA = " sobre la cuenca"

    private fun esBajo(l: LecturaRio): Boolean {
        val ua = l.umbral_alerta
        val ue = l.umbral_emergencia
        return ua != null && ue != null && ue < ua
    }

    private fun nivelAvisoHidro(nivel: Int?): Nivel = when (nivel) {
        4 -> Nivel.EMERGENCIA
        3 -> Nivel.ALERTA
        2 -> Nivel.AVISO
        else -> Nivel.SIN_DATO
    }

    private fun unidad(u: String?): String = if (u == "m3/s") "m³/s" else u ?: ""

    /** "tranquila", "atenta", "en alerta", "río muy bajo": la etiqueta del estado dicha de la estacion. */
    fun etiquetaEstacion(etiqueta: String): String = when (val e = etiqueta.trim().lowercase()) {
        "tranquilo", "normal" -> "tranquila"
        "atento" -> "atenta"
        else -> e
    }

    /**
     * "Estación Mashcón (ANA): tranquila (0.13 m³/s)": la medicion con su estacion, para el chip de Inicio. Sin `valor`
     * queda "Estación Mashcón (ANA): tranquila": las hojas del mapa, cuyo titulo ya dice el valor.
     */
    fun medicion(estacion: String?, etiqueta: String, valor: String? = null): String =
        "Estación ${estacion?.takeIf { it.isNotBlank() } ?: "de ANA"} (ANA): ${etiquetaEstacion(etiqueta)}" +
            (valor?.takeIf { it.isNotBlank() }?.let { " ($it)" } ?: "")

    /**
     * La senal de la cuenca entre las de la zona (Cauces.estadoZona, la misma regla que lib/zonaRio.js): el
     * aviso de lluvias de SENAMHI en curso (naranja o rojo) o, si no hay, la lluvia medida sobre la referencia.
     * Null si la cuenca no tiene senal. No repite la regla: solo redacta la linea a partir de la senal.
     */
    fun cuenca(senales: List<SenalZona>): SenalCuenca? {
        val s = senales.firstOrNull { it.clave == "aviso_lluvia" } ?: senales.firstOrNull { it.clave == "lluvia_medida" } ?: return null
        return if (s.clave == "aviso_lluvia") {
            // titulo "Aviso naranja de SENAMHI por lluvias sobre la cuenca"; texto "Vigente hoy." o "Vigente hasta el 23 nov 23:59."
            val que = s.titulo.removeSuffix(SUFIJO_CUENCA).replaceFirstChar { it.lowercase() }
            val vigencia = s.texto.trim().removeSuffix(".").replaceFirstChar { it.lowercase() }
            SenalCuenca(s.clave, "Cuenca: $que $vigencia; $PUEDE_SUBIR.", null, s.url, s.nivel)
        } else {
            SenalCuenca(s.clave, "Cuenca: lluvia fuerte medida por SENAMHI, por encima de su referencia (no es un aviso oficial); $PUEDE_SUBIR.", s.texto, s.url, s.nivel)
        }
    }

    fun cuenca(zona: EstadoZona): SenalCuenca? = cuenca(zona.senales)

    /** La senal de la cuenca a partir de las senales crudas de un rio (Inicio): pasa por Cauces.estadoZona, sin la medicion. */
    fun cuenca(senal: RioCauceSenal, ahoraMs: Long = System.currentTimeMillis()): SenalCuenca? =
        if (senal.avisos_lluvia.isEmpty() && senal.lluvia_cuenca.isEmpty()) null
        else cuenca(Cauces.estadoZona(null, emptyList(), senal.avisos_lluvia, senal.lluvia_cuenca, ahoraMs))

    fun resumir(senal: RioCauceSenal, nombre: String, ahoraMs: Long = System.currentTimeMillis()): RioResumen {
        var peor = Nivel.SIN_DATO
        var texto = "sin señales hoy"
        var fuente = ""
        var medicion: String? = null
        for (l in senal.lecturas) {
            val estado = l.estado?.lowercase()
            val nivel = when {
                estado == "emergencia" || estado == "alerta" -> if (esBajo(l)) Nivel.AVISO else Nivel.desde(estado)
                estado == "normal" -> Nivel.NORMAL
                else -> Nivel.SIN_DATO
            }
            if (nivel.orden < peor.orden || (peor == Nivel.SIN_DATO && nivel != Nivel.SIN_DATO)) {
                peor = nivel
                val valor = l.valor?.let { v -> (String.format(java.util.Locale.US, "%.2f", v) + " " + unidad(l.unidad)).trim() }
                val entreParentesis = valor?.let { " ($it)" } ?: ""
                val bajo = esBajo(l) && (estado == "alerta" || estado == "emergencia")
                texto = when {
                    bajo -> "muy bajo en ${l.estacion}$entreParentesis"
                    nivel == Nivel.NORMAL -> "tranquilo en ${l.estacion}$entreParentesis"
                    nivel == Nivel.SIN_DATO -> "sin estado en ${l.estacion}"
                    else -> "${nivel.etiqueta.lowercase()} en ${l.estacion}$entreParentesis"
                }
                val etiqueta = when {
                    bajo -> "río muy bajo"
                    nivel == Nivel.NORMAL -> "tranquila"
                    nivel == Nivel.SIN_DATO -> "sin estado"
                    else -> "en ${nivel.etiqueta.lowercase()}"
                }
                medicion = medicion(l.estacion, etiqueta, valor)
                fuente = "ANA"
            }
        }
        for (h in senal.avisos_hidro) {
            if (h.sentido == "descenso") continue   // vaciante: no es crecida
            val nivel = nivelAvisoHidro(h.nivel)
            if (nivel != Nivel.SIN_DATO && nivel.orden < peor.orden) {
                peor = nivel
                texto = "aviso hidrológico ${nivel.etiqueta.lowercase()} de SENAMHI" + (h.numero?.let { " N° $it" } ?: "")
                fuente = "SENAMHI"
            }
        }
        return RioResumen(senal.rio_ana, nombre, peor, texto, fuente, medicion, cuenca(senal, ahoraMs))
    }

    /**
     * El rio que conviene destacar en el chip: el de peor nivel con senales (una senal de cuenca cuenta); null si
     * ninguno tiene. En empate manda el que tiene senal de cuenca: un rio tranquilo con aviso de lluvias en curso
     * (el que nombra el titular) antes que uno "muy bajo" (vaciante), que tambien cuenta como "aviso".
     */
    fun destacado(rios: List<RioResumen>): RioResumen? =
        rios.filter { it.nivelDestacar != Nivel.SIN_DATO }
            .minWithOrNull(compareBy({ it.nivelDestacar.orden }, { if (it.cuenca != null) 0 else 1 }))

    /** Los rios vigilados (rio_vigilado) de un departamento, sin tildes ni mayusculas. */
    fun vigiladosDe(vigilados: List<RioVigiladoMapa>, departamento: String): List<RioVigiladoMapa> =
        vigilados.filter { Cauces.sinTildes(it.departamento) == Cauces.sinTildes(departamento) }

    /**
     * Un rio vigilado (el Mashcon) como RioCauceSenal, para resumirlo igual que un rio con trazo: la lectura de su
     * estacion de ANA sale de caudal_actual (Cauces.caudalDelRio) y las senales de hoy (avisos hidrologicos, avisos
     * de lluvias y lluvia medida sobre la cuenca) de su fila de rio_senal (rio_senal.rio = rio_vigilado.id). Hace
     * falta porque el vigilado no tiene fila en rio_cauce (su trazo es el de OSM revisado a mano y el cargador lo
     * salta): sin esto la senal de la cuenca nunca llega a Inicio.
     */
    fun deVigilado(rio: RioVigiladoMapa, senal: RioSenal?, caudales: List<CaudalActual>): RioCauceSenal {
        val c = Cauces.caudalDelRio(rio, caudales)
        val lectura = c?.let {
            LecturaRio(estacion = it.estacion, departamento = it.departamento, valor = it.valor, unidad = it.unidad,
                umbral_alerta = it.umbral_alerta, umbral_emergencia = it.umbral_emergencia, estado = it.estado,
                tendencia = it.tendencia, fecha = it.fecha, hora = it.hora)
        }
        return RioCauceSenal(rio.id, listOfNotNull(lectura), senal?.avisos_hidro ?: emptyList(), senal?.avisos_lluvia ?: emptyList(), senal?.lluvia_cuenca ?: emptyList())
    }

    /**
     * Los rios de la zona para Inicio: primero los vigilados del departamento (con las senales de su cuenca) y
     * despues los rios con trazo (rio_cauce_senal) con su nombre de rio_cauce_mapa, sin repetir un rio que ya
     * entro como vigilado (misma clave, misma clave de ANA o misma estacion).
     */
    fun resumirZona(
        departamento: String,
        vigilados: List<RioVigiladoMapa>,
        senalesVigilados: List<RioSenal>,
        caudales: List<CaudalActual>,
        cauces: List<RioCauceSenal>,
        nombres: Map<String, String>,
        ahoraMs: Long = System.currentTimeMillis(),
    ): List<RioResumen> {
        val deZona = vigiladosDe(vigilados, departamento)
        val propios = deZona.map { v -> resumir(deVigilado(v, senalesVigilados.firstOrNull { it.rio == v.id }, caudales), v.nombre ?: v.id, ahoraMs) }
        val repetido = { c: RioCauceSenal ->
            deZona.any { v ->
                v.id == c.rio_ana || Cauces.sinTildes(v.rio_ana) == Cauces.sinTildes(c.rio_ana) ||
                    (v.estacion_ana != null && c.lecturas.any { Cauces.sinTildes(it.estacion) == Cauces.sinTildes(v.estacion_ana) })
            }
        }
        return propios + cauces.filterNot(repetido).map { resumir(it, nombres[it.rio_ana] ?: it.rio_ana, ahoraMs) }
    }
}
