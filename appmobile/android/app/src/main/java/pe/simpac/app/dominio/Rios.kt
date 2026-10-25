package pe.simpac.app.dominio

import pe.simpac.app.data.LecturaRio
import pe.simpac.app.data.RioCauceSenal

/** Un rio del departamento con el estado que dicen sus senales de hoy. */
data class RioResumen(val rioAna: String, val nombre: String, val nivel: Nivel, val texto: String, val fuente: String)

/**
 * Estado de un rio con trazo a partir de rio_cauce_senal: la peor estacion de ANA en crecida o el aviso
 * hidrologico vigente de SENAMHI si es mas alto (la misma regla que frontend/src/lib/cauces.js).
 * Un rio en nivel bajo (vaciante) es como mucho "aviso". Sin lecturas ni avisos no hay "normal":
 * se dice "sin senales hoy" con nivel SIN_DATO para no afirmar calma sin medir.
 */
object Rios {
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

    fun resumir(senal: RioCauceSenal, nombre: String): RioResumen {
        var peor = Nivel.SIN_DATO
        var texto = "sin señales hoy"
        var fuente = ""
        for (l in senal.lecturas) {
            val estado = l.estado?.lowercase()
            val nivel = when {
                estado == "emergencia" || estado == "alerta" -> if (esBajo(l)) Nivel.AVISO else Nivel.desde(estado)
                estado == "normal" -> Nivel.NORMAL
                else -> Nivel.SIN_DATO
            }
            if (nivel.orden < peor.orden || (peor == Nivel.SIN_DATO && nivel != Nivel.SIN_DATO)) {
                peor = nivel
                val valor = l.valor?.let { v -> String.format(java.util.Locale.US, "%.2f", v) + " " + (l.unidad ?: "") }
                texto = when {
                    esBajo(l) && (estado == "alerta" || estado == "emergencia") -> "muy bajo en ${l.estacion} ($valor)"
                    nivel == Nivel.NORMAL -> "tranquilo en ${l.estacion} ($valor)"
                    nivel == Nivel.SIN_DATO -> "sin estado en ${l.estacion}"
                    else -> "${nivel.etiqueta.lowercase()} en ${l.estacion} ($valor)"
                }
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
        return RioResumen(senal.rio_ana, nombre, peor, texto, fuente)
    }

    /** El rio que conviene destacar en el chip: el de peor nivel con senales; null si ninguno tiene. */
    fun destacado(rios: List<RioResumen>): RioResumen? =
        rios.filter { it.nivel != Nivel.SIN_DATO }.minByOrNull { it.nivel.orden }
}
