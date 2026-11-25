package pe.simpac.app.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Almacenamiento cifrado (EncryptedSharedPreferences con llave maestra del Keystore de Android) para
 * los tokens que la app recibe: hoy solo el token de registro de FCM. Las llaves publicas de Supabase
 * no son secretos y no van aqui. Queda listo para un token de sesion si la app llega a iniciar sesion.
 */
class AlmacenSeguro(contexto: Context) {
    companion object {
        // Se conserva el nombre de SIMPAC: renombrar el archivo cerraria la sesion de quien ya usa la app.
        const val ARCHIVO = "simpac_seguro"
        private const val TOKEN_FCM = "token_fcm"
    }

    // security-crypto 1.1.0 marca la API como obsoleta pero sigue siendo la forma soportada en AndroidX
    @Suppress("DEPRECATION")
    private val prefs: SharedPreferences? = try {
        val llave = MasterKey.Builder(contexto).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
        EncryptedSharedPreferences.create(
            contexto,
            ARCHIVO,
            llave,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    } catch (_: Exception) {
        null   // Keystore no disponible (raro): la app funciona igual, solo no recuerda el token
    }

    var tokenFcm: String?
        get() = prefs?.getString(TOKEN_FCM, null)
        set(valor) { prefs?.edit()?.apply { if (valor == null) remove(TOKEN_FCM) else putString(TOKEN_FCM, valor) }?.apply() }

    /**
     * Sesion de Supabase Auth (access token, refresh token, vencimiento, id, correo y nombre) como JSON
     * (data/Sesion.kt la arma y la lee). Solo vive aqui, cifrada; nunca en DataStore ni en la cache.
     */
    var sesionJson: String?
        get() = prefs?.getString("sesion_auth", null)
        set(valor) { prefs?.edit()?.apply { if (valor == null) remove("sesion_auth") else putString("sesion_auth", valor) }?.apply() }
}
