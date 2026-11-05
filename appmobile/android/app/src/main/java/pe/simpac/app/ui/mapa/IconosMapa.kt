package pe.simpac.app.ui.mapa

import android.content.res.Resources
import android.graphics.Bitmap
import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.drawable.BitmapDrawable
import pe.simpac.app.dominio.NivelZona
import pe.simpac.app.dominio.Paleta

/**
 * Iconos del mapa dibujados con Canvas (sin recursos ni SVG): discos de las estaciones, insignias de
 * los avisos con su glifo (gota, gota con rayo, copo, termometro, viento, como map/iconos.js de la
 * web), puntos de "A donde acudir" con su glifo (cruz, escudo, llama), estaciones de SENAMHI y tu
 * ubicacion. Cada dibujo se hace una vez por clave y se reusa en todos los marcadores.
 */
object IconosMapa {
    private val cache = HashMap<String, BitmapDrawable>()

    private fun dp(res: Resources, v: Float): Float = v * res.displayMetrics.density

    private fun bitmap(res: Resources, tamanoDp: Float, pintar: (Canvas, Float) -> Unit): BitmapDrawable {
        val px = dp(res, tamanoDp).toInt().coerceAtLeast(4)
        val bmp = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888)
        pintar(Canvas(bmp), px.toFloat())
        return BitmapDrawable(res, bmp)
    }

    private fun paint(color: Int, estilo: Paint.Style = Paint.Style.FILL, ancho: Float = 0f) = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        this.color = color; style = estilo; strokeWidth = ancho; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND
    }

    /** Disco de una estacion de rio: relleno del estado, aro blanco; los fuertes (alerta/emergencia) mas grandes con aro doble. */
    fun disco(res: Resources, color: Long, fuerte: Boolean): BitmapDrawable = cache.getOrPut("disco:$color:$fuerte") {
        val t = if (fuerte) 26f else 18f
        bitmap(res, t) { c, s ->
            val cx = s / 2
            if (fuerte) c.drawCircle(cx, cx, s / 2, paint((color.toInt() and 0x00FFFFFF) or 0x50000000))
            c.drawCircle(cx, cx, s / 2 - dp(res, if (fuerte) 5f else 2f), paint(Color.WHITE))
            c.drawCircle(cx, cx, s / 2 - dp(res, if (fuerte) 6.5f else 3.5f), paint(color.toInt()))
        }
    }

    /** Estacion de SENAMHI: punto pequeno del color del tipo con borde blanco. */
    fun estacion(res: Resources, color: Long): BitmapDrawable = cache.getOrPut("est:$color") {
        bitmap(res, 11f) { c, s ->
            c.drawCircle(s / 2, s / 2, s / 2, paint(Color.WHITE))
            c.drawCircle(s / 2, s / 2, s / 2 - dp(res, 1.5f), paint(color.toInt()))
        }
    }

    /** Tu ubicacion: punto azul con halo. */
    fun ubicacion(res: Resources): BitmapDrawable = cache.getOrPut("ubicacion") {
        bitmap(res, 40f) { c, s ->
            c.drawCircle(s / 2, s / 2, s / 2, paint((Paleta.UBICACION.toInt() and 0x00FFFFFF) or 0x33000000))
            c.drawCircle(s / 2, s / 2, dp(res, 8f), paint(Color.WHITE))
            c.drawCircle(s / 2, s / 2, dp(res, 6f), paint(Paleta.UBICACION.toInt()))
        }
    }

    /** Insignia de un aviso: disco blanco con aro del color del nivel y el glifo del fenomeno. */
    fun insigniaAviso(res: Resources, glifo: String, nivel: Int?): BitmapDrawable = cache.getOrPut("aviso:$glifo:$nivel") {
        val color = (Paleta.AVISO_ARO[nivel] ?: Paleta.SIN_DATO).toInt()
        bitmap(res, 34f) { c, s ->
            c.drawCircle(s / 2, s / 2, s / 2, paint((color and 0x00FFFFFF) or 0x40000000))
            c.drawCircle(s / 2, s / 2, s / 2 - dp(res, 2f), paint(Color.WHITE))
            c.drawCircle(s / 2, s / 2, s / 2 - dp(res, 2f), paint(color, Paint.Style.STROKE, dp(res, 2.5f)))
            // el glifo se dibuja en un cuadro de 32 unidades centrado (como el viewBox de la web)
            val lado = s * 0.62f
            val k = lado / 32f
            c.save()
            c.translate((s - lado) / 2, (s - lado) / 2)
            c.scale(k, k)
            glifo(c, glifo)
            c.restore()
        }
    }

    private fun glifo(c: Canvas, glifo: String) {
        when (glifo) {
            "gota" -> gota(c)
            "gota_rayo" -> { gota(c); rayo(c) }
            "copo" -> copo(c)
            "termometro" -> termometro(c, 0xFFE03E1A.toInt())
            "termometro_frio" -> termometro(c, 0xFF2563EB.toInt())
            "viento" -> viento(c)
            else -> gota(c)
        }
    }

    private fun gota(c: Canvas) {
        val p = Path().apply {
            moveTo(16f, 2.5f)
            cubicTo(16f, 2.5f, 7f, 12.6f, 7f, 18.9f)
            arcTo(RectF(7f, 9.9f, 25f, 27.9f), 180f, -180f)
            cubicTo(25f, 12.6f, 16f, 2.5f, 16f, 2.5f)
            close()
        }
        c.drawPath(p, paint(0xFF1E88E5.toInt()))
        c.drawOval(RectF(11f, 16f, 14.4f, 22.4f), paint(0x8CFFFFFF.toInt()))
    }

    private fun rayo(c: Canvas) {
        val p = Path().apply { moveTo(17.9f, 11.2f); lineTo(12.4f, 19.6f); lineTo(16.3f, 19.6f); lineTo(14.4f, 26.2f); lineTo(20.7f, 16.9f); lineTo(16.7f, 16.9f); lineTo(19.3f, 11.2f); close() }
        c.drawPath(p, paint(Color.WHITE, Paint.Style.STROKE, 1.6f))
        c.drawPath(p, paint(0xFFF5A623.toInt()))
    }

    private fun copo(c: Canvas) {
        val halo = paint(Color.WHITE, Paint.Style.STROKE, 4.2f)
        val tinta = paint(0xFF4BA8EE.toInt(), Paint.Style.STROKE, 2.6f)
        for (pt in listOf(halo, tinta)) {
            for (a in listOf(0f, 60f, 120f)) {
                c.save(); c.rotate(a, 16f, 16f)
                c.drawLine(16f, 3.5f, 16f, 28.5f, pt)
                c.drawLine(12f, 6.5f, 16f, 10f, pt); c.drawLine(20f, 6.5f, 16f, 10f, pt)
                c.drawLine(12f, 25.5f, 16f, 22f, pt); c.drawLine(20f, 25.5f, 16f, 22f, pt)
                c.restore()
            }
        }
    }

    private fun termometro(c: Canvas, color: Int) {
        c.drawRoundRect(RectF(12.5f, 3f, 19.5f, 22f), 3.5f, 3.5f, paint(Color.WHITE))
        c.drawRoundRect(RectF(12.5f, 3f, 19.5f, 22f), 3.5f, 3.5f, paint(0xFF94A3B8.toInt(), Paint.Style.STROKE, 1.3f))
        c.drawCircle(16f, 23.5f, 5.6f, paint(color))
        c.drawCircle(16f, 23.5f, 5.6f, paint(Color.WHITE, Paint.Style.STROKE, 1.2f))
        c.drawRoundRect(RectF(14.4f, 10f, 17.6f, 22f), 1.6f, 1.6f, paint(color))
    }

    private fun viento(c: Canvas) {
        val pt = paint(0xFF64748B.toInt(), Paint.Style.STROKE, 2.2f)
        c.save(); c.translate(4f, 4f)
        c.drawPath(Path().apply { moveTo(2f, 12f); lineTo(19.5f, 12f); cubicTo(23.5f, 12f, 23.5f, 6f, 19.5f, 6f) }, pt)
        c.drawPath(Path().apply { moveTo(2f, 8f); lineTo(11f, 8f); cubicTo(14f, 8f, 14f, 3.5f, 11f, 3.5f) }, pt)
        c.drawPath(Path().apply { moveTo(2f, 16f); lineTo(14f, 16f); cubicTo(17f, 16f, 17f, 20.5f, 14f, 20.5f) }, pt)
        c.restore()
    }

    /** Punto de "A donde acudir": disco del color del tipo con glifo blanco (cruz, escudo, llama, edificio). */
    fun acudir(res: Resources, tipo: String?): BitmapDrawable = cache.getOrPut("acudir:$tipo") {
        val color = Paleta.acudir(tipo).toInt()
        bitmap(res, 28f) { c, s ->
            c.drawCircle(s / 2, s / 2, s / 2, paint(Color.WHITE))
            c.drawCircle(s / 2, s / 2, s / 2 - dp(res, 1.5f), paint(color))
            val lado = s * 0.56f
            val k = lado / 24f
            c.save(); c.translate((s - lado) / 2, (s - lado) / 2); c.scale(k, k)
            val blanco = paint(Color.WHITE, Paint.Style.STROKE, 2.4f)
            when (tipo) {
                "salud" -> {
                    c.drawRoundRect(RectF(9f, 2f, 15f, 22f), 1.5f, 1.5f, paint(Color.WHITE))
                    c.drawRoundRect(RectF(2f, 9f, 22f, 15f), 1.5f, 1.5f, paint(Color.WHITE))
                }
                "comisaria" -> c.drawPath(Path().apply {
                    moveTo(12f, 2.5f); lineTo(20f, 5.5f); lineTo(20f, 12f); cubicTo(20f, 17f, 16f, 20f, 12f, 22f)
                    cubicTo(8f, 20f, 4f, 17f, 4f, 12f); lineTo(4f, 5.5f); close()
                }, blanco)
                "bomberos" -> c.drawPath(Path().apply {
                    moveTo(12f, 3f); cubicTo(10f, 7f, 7f, 9f, 7f, 14f); cubicTo(7f, 17.5f, 9.5f, 21f, 12f, 21f)
                    cubicTo(14.5f, 21f, 17f, 17.5f, 17f, 14f); cubicTo(17f, 11f, 15f, 9f, 14f, 7f); cubicTo(13.5f, 9.5f, 12.5f, 10f, 12f, 11f)
                    cubicTo(11.5f, 9f, 12f, 6f, 12f, 3f); close()
                }, paint(Color.WHITE))
                else -> {
                    c.drawRect(RectF(6f, 3f, 18f, 21f), blanco)
                    c.drawLine(10f, 8f, 14f, 8f, blanco); c.drawLine(10f, 12f, 14f, 12f, blanco); c.drawLine(10f, 16f, 14f, 16f, blanco)
                }
            }
            c.restore()
        }
    }

    /** Rayado a 45 grados de una zona bajo_2m: franjas del tono oscuro del nivel sobre blanco tenue (como simpac-rayado-*). */
    fun shaderRayado(res: Resources, nivel: NivelZona): Shader {
        val oscuro = Paleta.zonaOscuro(nivel).toInt()
        val tenue = nivel == NivelZona.SIN_SENALES
        val s = dp(res, 8f).toInt().coerceAtLeast(6)
        val bmp = Bitmap.createBitmap(s, s, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        c.drawColor(0x73FFFFFF)
        val pt = paint((oscuro and 0x00FFFFFF) or (if (tenue) 0x8C000000L else 0xBF000000L).toInt(), Paint.Style.STROKE, s * 0.4f).apply { strokeCap = Paint.Cap.BUTT }
        val f = s.toFloat()
        c.drawLine(-f, -f, 2 * f, 2 * f, pt)
        c.drawLine(0f, -f, 2 * f, f, pt)
        c.drawLine(-f, 0f, f, 2 * f, pt)
        return BitmapShader(bmp, Shader.TileMode.REPEAT, Shader.TileMode.REPEAT)
    }
}
