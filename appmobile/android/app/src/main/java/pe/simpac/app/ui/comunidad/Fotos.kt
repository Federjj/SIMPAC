package pe.simpac.app.ui.comunidad

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import pe.simpac.app.dominio.Comunidad
import java.io.ByteArrayOutputStream
import java.io.File

/**
 * La foto de un reporte: archivo temporal para la camara (FileProvider, cacheDir/fotos) y la
 * reduccion a 1280 px de lado en JPEG al 85 % antes de subirla (lo mismo que reducirFoto en la web,
 * respetando la orientacion EXIF). Nunca se guarda la original ni su ubicacion EXIF: el JPEG nuevo
 * sale sin metadatos.
 */
object Fotos {
    private const val CARPETA = "fotos"

    /** Uri (content://) de un archivo nuevo en cacheDir/fotos para que la app de camara escriba ahi. */
    fun uriParaCamara(contexto: Context): Uri {
        val carpeta = File(contexto.cacheDir, CARPETA).apply { mkdirs() }
        carpeta.listFiles()?.filter { System.currentTimeMillis() - it.lastModified() > 24 * 3_600_000L }?.forEach { it.delete() }
        val archivo = File(carpeta, "camara-${System.currentTimeMillis()}.jpg")
        return FileProvider.getUriForFile(contexto, contexto.packageName + ".archivos", archivo)
    }

    /** Lee la imagen del uri (camara o galeria), la reduce a `lado` px y la devuelve como JPEG. */
    suspend fun reducirJpeg(contexto: Context, uri: Uri, lado: Int = Comunidad.LADO_FOTO, calidad: Int = 85): ByteArray = withContext(Dispatchers.IO) {
        val resolver = contexto.contentResolver
        val limites = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, limites) } ?: throw IllegalStateException("No se pudo leer la foto.")
        if (limites.outWidth <= 0 || limites.outHeight <= 0) throw IllegalStateException("No se pudo leer la foto.")
        var muestra = 1
        while (limites.outWidth / (muestra * 2) >= lado && limites.outHeight / (muestra * 2) >= lado) muestra *= 2
        val opciones = BitmapFactory.Options().apply { inSampleSize = muestra }
        val bruto = resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, opciones) } ?: throw IllegalStateException("No se pudo leer la foto.")
        val rotacion = try { resolver.openInputStream(uri)?.use { grados(ExifInterface(it).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) } ?: 0f } catch (_: Exception) { 0f }
        val k = minOf(1f, lado.toFloat() / maxOf(bruto.width, bruto.height))
        val matriz = Matrix().apply { if (k < 1f) postScale(k, k); if (rotacion != 0f) postRotate(rotacion) }
        val listo = if (k < 1f || rotacion != 0f) Bitmap.createBitmap(bruto, 0, 0, bruto.width, bruto.height, matriz, true) else bruto
        val salida = ByteArrayOutputStream()
        listo.compress(Bitmap.CompressFormat.JPEG, calidad, salida)
        if (listo !== bruto) listo.recycle()
        bruto.recycle()
        salida.toByteArray()
    }

    private fun grados(orientacion: Int): Float = when (orientacion) {
        ExifInterface.ORIENTATION_ROTATE_90 -> 90f
        ExifInterface.ORIENTATION_ROTATE_180 -> 180f
        ExifInterface.ORIENTATION_ROTATE_270 -> 270f
        else -> 0f
    }
}
