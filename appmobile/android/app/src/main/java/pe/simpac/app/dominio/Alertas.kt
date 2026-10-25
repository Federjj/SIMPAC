package pe.simpac.app.dominio

import pe.simpac.app.data.AlertaActual

/**
 * Reglas de la lista de alertas (las mismas de frontend/src/lib/alertas.js):
 * - la lluvia medida (tipo 'lluvia') NO es oficial y siempre vale "aviso", venga como venga;
 * - un rio muy bajo (tipo 'nivel_bajo') tambien es como mucho "aviso";
 * - orden: emergencia > alerta > aviso; dentro del nivel, oficiales primero; despues la mas reciente.
 */
object Alertas {
    fun esOficial(a: AlertaActual): Boolean = a.tipo != "lluvia"

    fun nivelDe(a: AlertaActual): Nivel = when (a.tipo) {
        "lluvia", "nivel_bajo" -> Nivel.AVISO
        else -> when (val n = Nivel.desde(a.nivel)) {
            Nivel.EMERGENCIA, Nivel.ALERTA, Nivel.AVISO -> n
            else -> Nivel.AVISO
        }
    }

    fun ordenar(alertas: List<AlertaActual>): List<AlertaActual> =
        alertas.sortedWith(
            compareBy<AlertaActual> { nivelDe(it).orden }
                .thenBy { if (esOficial(it)) 0 else 1 }
                .thenByDescending { Tiempo.parsearMs(it.ts) ?: 0L }
        )

    /** Las del departamento (zona canonica; se compara sin tildes ni mayusculas). */
    fun deZona(alertas: List<AlertaActual>, departamento: String): List<AlertaActual> {
        val clave = Departamentos.sinTildes(departamento).lowercase()
        return alertas.filter { Departamentos.sinTildes(it.zona ?: "").lowercase() == clave }
    }

    /** Cuantas oficiales hay (nunca cuenta la lluvia medida). */
    fun cuantasOficiales(alertas: List<AlertaActual>): Int = alertas.count { esOficial(it) }

    /** Que tipo de cosa es, en lenguaje claro. */
    fun tipoTexto(a: AlertaActual): String = when (a.tipo) {
        "aviso" -> "Aviso de SENAMHI"
        "caudal" -> "Río sobre su nivel (ANA)"
        "nivel_bajo" -> "Río muy bajo (ANA)"
        "lluvia" -> "Lluvia medida (no es un aviso oficial)"
        else -> a.tipo ?: "Alerta"
    }

    /** De donde sale el dato. */
    fun fuenteTexto(a: AlertaActual): String = when (a.tipo) {
        "aviso" -> "SENAMHI"
        "caudal", "nivel_bajo" -> "ANA"
        "lluvia" -> "estación de SENAMHI, comparada con su referencia por SIMPAC"
        else -> "fuente oficial"
    }
}
