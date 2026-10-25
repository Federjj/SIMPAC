package pe.simpac.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest

/** Lo que devolvio una consulta: el dato, cuando se obtuvo y si salio de la cache (sin conexion). */
data class Resultado<T>(val dato: T, val obtenidoEn: Long, val deCache: Boolean)

/**
 * Cache en disco de la ultima respuesta de cada consulta (un archivo por clave en
 * <filesDir>/simpac_cache). Sirve para mostrar lo ultimo guardado, con su hora, cuando no hay
 * conexion. Nunca se usa para fingir un dato fresco: quien lo lee recibe obtenidoEn y deCache.
 */
class CacheDisco(private val carpeta: File) {
    private fun archivo(clave: String): File {
        val hash = MessageDigest.getInstance("SHA-256").digest(clave.toByteArray())
            .joinToString("") { "%02x".format(it) }.take(40)
        return File(carpeta, "$hash.json")
    }

    suspend fun guardar(clave: String, cuerpo: String, ahoraMs: Long = System.currentTimeMillis()) = withContext(Dispatchers.IO) {
        try {
            carpeta.mkdirs()
            val tmp = File(carpeta, archivo(clave).name + ".tmp")
            tmp.writeText("$ahoraMs\n$cuerpo")
            if (!tmp.renameTo(archivo(clave))) {
                archivo(clave).writeText("$ahoraMs\n$cuerpo")
                tmp.delete()
            }
        } catch (_: Exception) {
            // sin espacio o sin permiso: la app sigue, solo pierde el modo sin conexion
        }
    }

    /** (cuerpo, guardadoEn) o null si no hay nada guardado. */
    suspend fun leer(clave: String): Pair<String, Long>? = withContext(Dispatchers.IO) {
        try {
            val f = archivo(clave)
            if (!f.exists()) return@withContext null
            val texto = f.readText()
            val salto = texto.indexOf('\n')
            if (salto <= 0) return@withContext null
            val ms = texto.substring(0, salto).toLongOrNull() ?: return@withContext null
            texto.substring(salto + 1) to ms
        } catch (_: Exception) {
            null
        }
    }

    suspend fun limpiar() = withContext(Dispatchers.IO) {
        try { carpeta.listFiles()?.forEach { it.delete() } } catch (_: Exception) { }
    }
}
