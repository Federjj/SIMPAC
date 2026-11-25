package pe.simpac.app.ui.mapa

import android.content.res.Resources
import android.graphics.Bitmap
import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
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

    // ---- pronostico por localidad (map/iconos.js: sol, sol_nube, nube, tendencia, lluvia, tormenta, nieve) ----

    /** Nube de tres circulos y un rectangulo (viewBox 32), con degradado blanco a gris azulado (u oscuro para la tormenta). */
    private fun nube(c: Canvas, dy: Float, oscura: Boolean = false) {
        val p = Paint(Paint.ANTI_ALIAS_FLAG)
        p.shader = LinearGradient(0f, 4f + dy, 0f, 25f + dy,
            if (oscura) 0xFFA9B6C8.toInt() else Color.WHITE, if (oscura) 0xFF5B6B82.toInt() else 0xFFB4C1D3.toInt(), Shader.TileMode.CLAMP)
        val sombra = paint(0x50000000)
        c.save(); c.translate(0f, dy)
        // sombra suave debajo
        c.save(); c.translate(0f, 0.9f)
        c.drawCircle(10f, 19f, 6f, sombra); c.drawCircle(17f, 13.5f, 7.5f, sombra); c.drawCircle(23.5f, 19.5f, 5.5f, sombra); c.drawRect(RectF(10f, 17f, 23.5f, 25f), sombra)
        c.restore()
        c.drawCircle(10f, 19f, 6f, p); c.drawCircle(17f, 13.5f, 7.5f, p); c.drawCircle(23.5f, 19.5f, 5.5f, p); c.drawRect(RectF(10f, 17f, 23.5f, 25f), p)
        c.restore()
    }

    private fun gotita(c: Canvas, x: Float, y: Float, k: Float = 1f) {
        val p = Paint(Paint.ANTI_ALIAS_FLAG)
        p.shader = LinearGradient(0f, -3.6f, 0f, 3.2f, 0xFF6CCBFF.toInt(), 0xFF1673D9.toInt(), Shader.TileMode.CLAMP)
        c.save(); c.translate(x, y); c.scale(k, k)
        c.drawPath(Path().apply {
            moveTo(0f, -3.6f); cubicTo(0f, -3.6f, -2.3f, -0.8f, -2.3f, 0.9f)
            arcTo(RectF(-2.3f, -1.4f, 2.3f, 3.2f), 180f, -180f)
            cubicTo(2.3f, -0.8f, 0f, -3.6f, 0f, -3.6f); close()
        }, p)
        c.restore()
    }

    private fun sol(c: Canvas, cx: Float, cy: Float, r: Float) {
        val rayos = paint(0xFFF7B32B.toInt(), Paint.Style.STROKE, 2f)
        for (i in 0 until 8) {
            val a = i * Math.PI / 4
            c.drawLine(cx + (Math.cos(a) * (r + 2.2)).toFloat(), cy + (Math.sin(a) * (r + 2.2)).toFloat(),
                cx + (Math.cos(a) * (r + 4.3)).toFloat(), cy + (Math.sin(a) * (r + 4.3)).toFloat(), rayos)
        }
        val p = Paint(Paint.ANTI_ALIAS_FLAG)
        p.shader = RadialGradient(cx - r * 0.2f, cy - r * 0.3f, r * 1.4f, intArrayOf(0xFFFFE9A3.toInt(), 0xFFFFC53D.toInt(), 0xFFF59E0B.toInt()), floatArrayOf(0f, 0.55f, 1f), Shader.TileMode.CLAMP)
        c.drawCircle(cx, cy, r, p)
    }

    private fun copito(c: Canvas, cx: Float, cy: Float, r: Float = 2.6f) {
        val p = paint(0xFF2F95E8.toInt(), Paint.Style.STROKE, 1.6f)
        for (a in listOf(90.0, 30.0, 150.0)) {
            val dx = (Math.cos(Math.toRadians(a)) * r).toFloat(); val dy = (Math.sin(Math.toRadians(a)) * r).toFloat()
            c.drawLine(cx - dx, cy - dy, cx + dx, cy + dy, p)
        }
    }

    private fun rayoGrande(c: Canvas) {
        // el rayo de la web (M17.6 15.5 11.8 23.4h4.4l-2.4 7.1 7.6-9.7h-4.7l3-5.3z) centrado y un 12 % mas grande, subido
        val p = Path().apply { moveTo(17.6f, 15.5f); lineTo(11.8f, 23.4f); lineTo(16.2f, 23.4f); lineTo(13.8f, 30.5f); lineTo(21.4f, 20.8f); lineTo(16.7f, 20.8f); lineTo(19.7f, 15.5f); close() }
        val m = android.graphics.Matrix()
        m.postTranslate(-16.4f, -17.4f); m.postScale(1.12f, 1.12f); m.postTranslate(16.4f - 0.4f, 17.4f - 1.2f)
        p.transform(m)
        val rel = Paint(Paint.ANTI_ALIAS_FLAG)
        rel.shader = LinearGradient(0f, 14f, 0f, 30f, 0xFFFFE066.toInt(), 0xFFF59E0B.toInt(), Shader.TileMode.CLAMP)
        c.drawPath(p, paint(Color.WHITE, Paint.Style.STROKE, 1.3f))
        c.drawPath(p, rel)
    }

    /** Glifo del tiempo del pronostico (cuadro de 32): el mismo dibujo que map/iconos.js, sin SVG. */
    private fun glifoTiempo(c: Canvas, glifo: String) {
        when (glifo) {
            "sol" -> sol(c, 16f, 16f, 7f)
            "nube" -> nube(c, -1.5f)
            "tendencia" -> { nube(c, -3.5f); gotita(c, 16f, 27.2f, 1.05f) }
            "lluvia" -> { nube(c, -3.5f); gotita(c, 10.5f, 26.6f); gotita(c, 16.5f, 28.4f); gotita(c, 22.5f, 26.6f) }
            "tormenta" -> { nube(c, -5f, oscura = true); rayoGrande(c) }
            "nieve" -> { nube(c, -3.5f); copito(c, 10.5f, 27.3f); copito(c, 16.5f, 28.6f); copito(c, 22.5f, 27.3f) }
            else -> { // sol_nube
                sol(c, 12.5f, 12.5f, 6.4f)
                c.save(); c.translate(9.5f, 8.5f); c.scale(0.7f, 0.7f); nube(c, 0f); c.restore()
            }
        }
    }

    /**
     * Disco de una localidad del pronostico: blanco con el glifo del tiempo; borde punteado gris si
     * SENAMHI dice "tendencia a" (posible); tu localidad con aro negro (punteado si es posible). Los
     * secos son algo mas chicos (web: .loc-seco 24 px frente a 28 px).
     */
    fun discoLocalidad(res: Resources, glifo: String, posible: Boolean, tuya: Boolean, seco: Boolean): BitmapDrawable =
        cache.getOrPut("loc:$glifo:$posible:$tuya:$seco") {
            val t = if (tuya) 36f else if (seco) 26f else 30f
            bitmap(res, t + 4f) { c, s ->
                val cx = s / 2
                val r = t / 2 * (s / (t + 4f))
                c.drawCircle(cx, cx + dp(res, 1f), r, paint(0x40000000))   // sombra
                c.drawCircle(cx, cx, r, paint(Color.WHITE))
                if (tuya || posible) {
                    val borde = paint(if (tuya) 0xFF0F172A.toInt() else 0xFF475569.toInt(), Paint.Style.STROKE, dp(res, if (tuya) 3f else 2f))
                    if (posible) borde.pathEffect = android.graphics.DashPathEffect(floatArrayOf(dp(res, 3f), dp(res, 2.5f)), 0f)
                    c.drawCircle(cx, cx, r - dp(res, if (tuya) 1.5f else 1f), borde)
                }
                val lado = s * (if (seco) 0.56f else 0.64f)
                val k = lado / 32f
                c.save(); c.translate((s - lado) / 2, (s - lado) / 2); c.scale(k, k)
                glifoTiempo(c, glifo)
                c.restore()
            }
        }

    /** Punto chico de una localidad (vista pais): del color de su tono, borde blanco; tu localidad con aro negro. */
    fun puntoLocalidad(res: Resources, color: Long, tuya: Boolean): BitmapDrawable = cache.getOrPut("locpunto:$color:$tuya") {
        bitmap(res, if (tuya) 14f else 11f) { c, s ->
            c.drawCircle(s / 2, s / 2, s / 2, paint(if (tuya) 0xFF0F172A.toInt() else Color.WHITE))
            c.drawCircle(s / 2, s / 2, s / 2 - dp(res, if (tuya) 2.5f else 1.5f), paint(color.toInt()))
        }
    }

    /** Glifo suelto para la leyenda del pronostico (fondo transparente). */
    fun glifoLeyenda(res: Resources, glifo: String): BitmapDrawable = cache.getOrPut("gl:$glifo") {
        bitmap(res, 24f) { c, s -> val k = s / 32f; c.scale(k, k); glifoTiempo(c, glifo) }
    }

    // ---- lluvia de la ultima hora ----

    /** Circulo de una estacion con lluvia: tamano y color por mm; borde amarillo grueso si paso la referencia. */
    fun discoLluvia(res: Resources, color: Long, radioDp: Float, pasa: Boolean, conLluvia: Boolean): BitmapDrawable =
        cache.getOrPut("lluvia:$color:$radioDp:$pasa:$conLluvia") {
            val borde = if (pasa) 3f else 1f
            bitmap(res, (radioDp + borde) * 2 + 2f) { c, s ->
                val cx = s / 2
                c.drawCircle(cx, cx, dp(res, radioDp + borde), paint(if (pasa) pe.simpac.app.dominio.Lluvia.BORDE_REFERENCIA.toInt() else Color.WHITE))
                c.drawCircle(cx, cx, dp(res, radioDp), paint((color.toInt() and 0x00FFFFFF) or (if (conLluvia) 0xE6000000.toInt() else 0x80000000.toInt())))
            }
        }

    // ---- desbordes pasados: rombo con el ano ----

    /** Rombo pizarra de 24 dp con el ano corto en blanco y, si agrupa varios, una pastilla "x2". */
    fun rombo(res: Resources, anio: String, n: Int): BitmapDrawable = cache.getOrPut("rombo:$anio:$n") {
        bitmap(res, 38f) { c, s ->
            val cx = s / 2; val cy = s / 2
            val h = dp(res, 10.5f)   // media diagonal del rombo de 21 dp
            val p = Path().apply { moveTo(cx, cy - h); lineTo(cx + h, cy); lineTo(cx, cy + h); lineTo(cx - h, cy); close() }
            c.drawPath(p, paint(0x40000000))
            c.drawPath(p, paint(pe.simpac.app.dominio.Incidentes.COLOR_ROMBO.toInt()))
            c.drawPath(p, paint(Color.WHITE, Paint.Style.STROKE, dp(res, 1.5f)))
            val texto = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE; textSize = dp(res, 10f); textAlign = Paint.Align.CENTER; typeface = android.graphics.Typeface.DEFAULT_BOLD }
            c.drawText(anio, cx, cy + dp(res, 3.5f), texto)
            if (n > 1) {
                val tx = cx + dp(res, 11f); val ty = cy - dp(res, 10f)
                val etiqueta = "×$n"
                val tp = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE; textSize = dp(res, 9f); textAlign = Paint.Align.CENTER; typeface = android.graphics.Typeface.DEFAULT_BOLD }
                val ancho = tp.measureText(etiqueta) + dp(res, 6f)
                c.drawRoundRect(RectF(tx - ancho / 2, ty - dp(res, 7f), tx + ancho / 2, ty + dp(res, 7f)), dp(res, 7f), dp(res, 7f), paint(0xFF0F172A.toInt()))
                c.drawText(etiqueta, tx, ty + dp(res, 3.2f), tp)
            }
        }
    }

    // ---- reportes de la comunidad: gota (pin) del color del tipo con glifo blanco (map/markers.js SVG) ----

    private fun glifoReporte(c: Canvas, tipo: String) {
        val blanco = paint(Color.WHITE, Paint.Style.STROKE, 2f)
        val relleno = paint(Color.WHITE)
        when (tipo) {
            "inundacion" -> c.drawPath(Path().apply { moveTo(12f, 22f); cubicTo(16f, 22f, 19f, 19f, 19f, 15f); cubicTo(19f, 10f, 12f, 2f, 12f, 2f); cubicTo(12f, 2f, 5f, 10f, 5f, 15f); cubicTo(5f, 19f, 8f, 22f, 12f, 22f); close() }, relleno)
            "huayco" -> c.drawPath(Path().apply { moveTo(3f, 20f); lineTo(21f, 20f); lineTo(14f, 6f); lineTo(10f, 13f); lineTo(7f, 10f); close() }, relleno)
            "lluvia_intensa" -> {
                c.drawPath(Path().apply { moveTo(18f, 15f); cubicTo(20.5f, 15f, 22f, 13f, 22f, 11f); cubicTo(22f, 9f, 20.5f, 7.3f, 18f, 7.1f); cubicTo(17f, 4f, 14.5f, 2f, 11.5f, 2f); cubicTo(8f, 2f, 5f, 5f, 5f, 8.5f); cubicTo(5f, 10f, 5.5f, 11.5f, 6f, 13f) }, blanco)
                c.drawLine(8f, 19f, 8f, 21f, blanco); c.drawLine(12f, 18f, 12f, 21f, blanco); c.drawLine(16f, 17f, 16f, 19f, blanco)
            }
            "via_bloqueada" -> { c.drawLine(4f, 19f, 20f, 5f, blanco); c.drawLine(4f, 5f, 20f, 19f, blanco) }
            "atasco" -> {
                c.drawPath(Path().apply { moveTo(5f, 17f); lineTo(19f, 17f); lineTo(19f, 13f); lineTo(17f, 8f); lineTo(7f, 8f); lineTo(5f, 13f); close() }, blanco)
                c.drawCircle(8f, 17f, 1.5f, relleno); c.drawCircle(16f, 17f, 1.5f, relleno)
            }
            "bache" -> { c.drawOval(RectF(4f, 10f, 20f, 18f), blanco); c.drawPath(Path().apply { moveTo(8f, 13f); lineTo(10f, 14f); lineTo(13f, 12f); lineTo(16f, 14f) }, blanco) }
            "accidente" -> { c.drawPath(Path().apply { moveTo(12f, 3f); lineTo(2f, 20f); lineTo(22f, 20f); close() }, blanco); c.drawLine(12f, 10f, 12f, 14f, blanco); c.drawCircle(12f, 17f, 0.9f, relleno) }
            else -> { c.drawLine(12f, 5f, 12f, 14f, blanco); c.drawCircle(12f, 18f, 1f, relleno) }
        }
    }

    /** Pin (gota) de un reporte: color del tipo, glifo blanco, punta abajo; la opacidad va en el marcador. */
    fun pinReporte(res: Resources, tipo: String, color: Long): BitmapDrawable = cache.getOrPut("rep:$tipo:$color") {
        val ancho = 30f; val alto = 40f
        val px = dp(res, ancho).toInt(); val py = dp(res, alto).toInt()
        val bmp = Bitmap.createBitmap(px, py, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        val w = px.toFloat(); val r = w / 2 - dp(res, 1f)
        val cx = w / 2; val cy = r + dp(res, 1f)
        val gota = Path().apply {
            addCircle(cx, cy, r, Path.Direction.CW)
            moveTo(cx - r * 0.62f, cy + r * 0.78f); lineTo(cx, py - dp(res, 1f)); lineTo(cx + r * 0.62f, cy + r * 0.78f); close()
        }
        c.drawPath(gota, paint(Color.WHITE))
        val interior = Path().apply {
            addCircle(cx, cy, r - dp(res, 1.5f), Path.Direction.CW)
            moveTo(cx - r * 0.55f, cy + r * 0.75f); lineTo(cx, py - dp(res, 3f)); lineTo(cx + r * 0.55f, cy + r * 0.75f); close()
        }
        c.drawPath(interior, paint(color.toInt()))
        val lado = r * 1.25f
        val k = lado / 24f
        c.save(); c.translate(cx - lado / 2, cy - lado / 2); c.scale(k, k)
        glifoReporte(c, tipo)
        c.restore()
        BitmapDrawable(res, bmp)
    }

    private val rayados = HashMap<NivelZona, Shader>()

    /**
     * Rayado a 45 grados de una zona bajo_2m: franjas del tono oscuro del nivel sobre blanco tenue (como
     * sifec-rayado-*). Un shader por nivel, compartido por todos los poligonos de ese nivel (antes se
     * dibujaba un bitmap nuevo por poligono cada vez que llegaban zonas).
     */
    fun shaderRayado(res: Resources, nivel: NivelZona): Shader = rayados.getOrPut(nivel) {
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
        BitmapShader(bmp, Shader.TileMode.REPEAT, Shader.TileMode.REPEAT)
    }
}
