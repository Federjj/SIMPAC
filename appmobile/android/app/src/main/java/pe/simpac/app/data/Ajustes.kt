package pe.simpac.app.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import pe.simpac.app.BuildConfig
import pe.simpac.app.dominio.Departamentos

private val Context.almacenAjustes: DataStore<Preferences> by preferencesDataStore(name = "simpac_ajustes")

/** Lo que la persona configura: departamento, notificaciones, GPS y capas del mapa. Las direcciones de la API y la web son fijas (del build). */
data class AjustesApp(
    val departamento: String = Departamentos.POR_DEFECTO.nombre,
    val usarGps: Boolean = false,              // la persona acepto usar su ubicacion para la zona
    val gpsExplicado: Boolean = false,         // ya vio la pantalla que explica el permiso
    val apiUrl: String = Ajustes.API_POR_DEFECTO,   // fija: no se puede cambiar desde la app
    val webUrl: String = Ajustes.WEB_POR_DEFECTO,   // fija: a donde vuelven los enlaces de confirmacion de cuenta
    val notificaciones: Boolean = false,       // interruptor de push por zona
    val temaZonaSuscrito: String? = null,      // ultimo tema zona_<slug> suscrito en FCM
    val capasMapa: Set<String> = Ajustes.CAPAS_POR_DEFECTO,   // interruptores de la pestana Mapa
)

/** Ajustes en DataStore (Preferences). No guarda ningun secreto: para eso esta AlmacenSeguro. */
class Ajustes(private val contexto: Context) {
    companion object {
        // Direcciones de fabrica: vienen de las propiedades de Gradle simpac.apiUrl / simpac.webUrl
        // (app/build.gradle.kts). En debug sin propiedades son las del emulador (10.0.2.2 es la PC donde
        // corre Docker: API :8000, web nginx :8080); en release son obligatorias y por https.
        val API_POR_DEFECTO: String = BuildConfig.API_URL
        val WEB_POR_DEFECTO: String = BuildConfig.WEB_URL

        private val DEPARTAMENTO = stringPreferencesKey("departamento")
        private val USAR_GPS = booleanPreferencesKey("usar_gps")
        private val GPS_EXPLICADO = booleanPreferencesKey("gps_explicado")
        private val NOTIFICACIONES = booleanPreferencesKey("notificaciones")
        private val TEMA_ZONA = stringPreferencesKey("tema_zona")
        private val CAPAS_MAPA = stringPreferencesKey("capas_mapa")

        /** Capas encendidas al abrir el mapa por primera vez (igual que la web): avisos, zonas y rios. */
        val CAPAS_POR_DEFECTO: Set<String> = setOf("avisos", "zonas", "rios")
    }

    val flujo: Flow<AjustesApp> = contexto.almacenAjustes.data.map { p ->
        AjustesApp(
            departamento = p[DEPARTAMENTO] ?: Departamentos.POR_DEFECTO.nombre,
            usarGps = p[USAR_GPS] ?: false,
            gpsExplicado = p[GPS_EXPLICADO] ?: false,
            apiUrl = API_POR_DEFECTO,
            webUrl = WEB_POR_DEFECTO,
            notificaciones = p[NOTIFICACIONES] ?: false,
            temaZonaSuscrito = p[TEMA_ZONA],
            capasMapa = p[CAPAS_MAPA]?.let { t -> t.split(",").map { it.trim() }.filter { it.isNotBlank() }.toSet() } ?: CAPAS_POR_DEFECTO,
        )
    }

    suspend fun actual(): AjustesApp = flujo.first()

    suspend fun guardarDepartamento(nombre: String) = contexto.almacenAjustes.edit { it[DEPARTAMENTO] = nombre }
    suspend fun guardarUsarGps(valor: Boolean) = contexto.almacenAjustes.edit { it[USAR_GPS] = valor }
    suspend fun guardarGpsExplicado(valor: Boolean) = contexto.almacenAjustes.edit { it[GPS_EXPLICADO] = valor }
    suspend fun guardarNotificaciones(valor: Boolean) = contexto.almacenAjustes.edit { it[NOTIFICACIONES] = valor }
    suspend fun guardarTemaZona(tema: String?) = contexto.almacenAjustes.edit {
        if (tema == null) it.remove(TEMA_ZONA) else it[TEMA_ZONA] = tema
    }
    /** Se guarda siempre como texto (aunque sea vacio): asi "todas apagadas" no vuelve a las de fabrica. */
    suspend fun guardarCapasMapa(capas: Set<String>) = contexto.almacenAjustes.edit { it[CAPAS_MAPA] = capas.joinToString(",") }
}
