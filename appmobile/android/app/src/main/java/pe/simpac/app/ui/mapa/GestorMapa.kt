package pe.simpac.app.ui.mapa

import android.content.Context
import android.graphics.Color
import android.graphics.Paint
import org.osmdroid.config.Configuration
import org.osmdroid.events.DelayedMapListener
import org.osmdroid.events.MapListener
import org.osmdroid.events.ScrollEvent
import org.osmdroid.events.ZoomEvent
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.tileprovider.tilesource.XYTileSource
import org.osmdroid.util.BoundingBox
import org.osmdroid.util.GeoPoint
import org.osmdroid.util.MapTileIndex
import org.osmdroid.views.CustomZoomButtonsController
import org.osmdroid.views.CustomZoomButtonsDisplay
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.FolderOverlay
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Overlay
import org.osmdroid.views.overlay.Polygon
import org.osmdroid.views.overlay.Polyline
import pe.simpac.app.BuildConfig
import pe.simpac.app.data.EstacionSenamhi
import pe.simpac.app.data.PuntoAcudir
import pe.simpac.app.dominio.Caja
import pe.simpac.app.dominio.Cauces
import pe.simpac.app.dominio.Coord
import pe.simpac.app.dominio.GeoJson
import pe.simpac.app.dominio.Geometria
import pe.simpac.app.dominio.Paleta
import pe.simpac.app.ubicacion.Posicion
import java.io.File

/** Lo que la persona toco en el mapa: la hoja inferior lo explica en lenguaje claro. */
sealed class Seleccion {
    data class Avisos(val avisos: List<AvisoDibujo>) : Seleccion()
    data class Rio(val rio: RioDibujo) : Seleccion()
    data class Mashcon(val mashcon: MashconDibujo) : Seleccion()
    data class EstacionRio(val estacion: EstacionRioDibujo) : Seleccion()
    data class Zona(val zona: ZonaDibujo) : Seleccion()
    data class Estacion(val estacion: EstacionSenamhi) : Seleccion()
    data class Acudir(val punto: PuntoAcudir) : Seleccion()
}

/** Tiles de Stadia Maps (Alidade Smooth) con la llave en la URL; en pantallas densas pide los de 512 px (@2x). */
private class FuenteStadia(private val llave: String, retina: Boolean) : XYTileSource(
    "StadiaAlidadeSmooth", 2, 20, if (retina) 512 else 256, if (retina) "@2x.png" else ".png",
    arrayOf("https://tiles.stadiamaps.com/tiles/alidade_smooth/"), "(c) Stadia Maps (c) OpenMapTiles (c) OpenStreetMap",
) {
    override fun getTileURLString(pMapTileIndex: Long): String =
        baseUrl + MapTileIndex.getZoom(pMapTileIndex) + "/" + MapTileIndex.getX(pMapTileIndex) + "/" + MapTileIndex.getY(pMapTileIndex) +
            mImageFilenameEnding + "?api_key=" + llave
}

/** Configuracion de osmdroid (una vez por proceso): User-Agent = applicationId y cache de tiles en el cache de la app. */
object OsmdroidSimpac {
    @Volatile private var listo = false
    val conLlaveStadia: Boolean get() = BuildConfig.STADIA_KEY.isNotBlank()
    val atribucion: String
        get() = if (conLlaveStadia) "(c) Stadia Maps (c) OpenMapTiles (c) OpenStreetMap - Datos: SENAMHI, ANA"
        else "(c) colaboradores de OpenStreetMap - Datos: SENAMHI, ANA"

    fun preparar(contexto: Context) {
        if (listo) return
        val conf = Configuration.getInstance()
        conf.load(contexto.applicationContext, contexto.getSharedPreferences("osmdroid", Context.MODE_PRIVATE))
        conf.userAgentValue = BuildConfig.APPLICATION_ID
        val base = File(contexto.cacheDir, "osmdroid")
        conf.osmdroidBasePath = base
        conf.osmdroidTileCache = File(base, "tiles")
        conf.tileFileSystemCacheMaxBytes = 120L * 1024 * 1024
        conf.tileFileSystemCacheTrimBytes = 90L * 1024 * 1024
        conf.isMapViewHardwareAccelerated = true
        listo = true
    }

    fun fuenteTiles(contexto: Context) = if (conLlaveStadia) {
        FuenteStadia(BuildConfig.STADIA_KEY, contexto.resources.displayMetrics.density >= 1.75f)
    } else TileSourceFactory.MAPNIK
}

/**
 * Dibuja el estado del mapa sobre un MapView de osmdroid y traduce los toques a una Seleccion. Las
 * capas van en FolderOverlay (de abajo hacia arriba: avisos, zonas, rios, estaciones de rio,
 * estaciones de SENAMHI, acudir, nombres, tu ubicacion). Lo que depende del zoom (detalle del trazo,
 * nombres, capas que solo se ven de cerca) se revisa al parar el mapa (150 ms), en el hilo principal
 * pero con listas ya calculadas.
 */
class GestorMapa(
    val mapa: MapView,
    private val alTocar: (Seleccion) -> Unit,
    private val alCambiarVista: (Caja, Double) -> Unit,
) {
    private val res = mapa.resources
    private val densidad = res.displayMetrics.density
    private val capaAvisos = FolderOverlay()
    private val capaZonas = FolderOverlay()
    private val capaRios = FolderOverlay()
    private val capaEstacionesRio = FolderOverlay()
    private val capaEstaciones = FolderOverlay()
    private val capaAcudir = FolderOverlay()
    private val capaRotulos = FolderOverlay()
    private val capaUbicacion = FolderOverlay()

    private companion object {
        /** Relleno del area de un aviso: 28 % (dos avisos encimados no llegan a verse opacos). */
        const val ALFA_AVISO = 0x47000000
        /** Desde este zoom el area amarilla baja al 12 % (web: index.css, bandas z13+). */
        const val AVISO_AMARILLO_TENUE_DESDE = 13.0
    }

    private class Trazo(val rio: RioDibujo, val halo: Polyline, val linea: Polyline, var detalle: String)
    private val trazos = ArrayList<Trazo>()
    private val avisosDibujados = ArrayList<Pair<AvisoDibujo, List<Overlay>>>()
    private var finos: Map<String, List<List<Coord>>> = emptyMap()
    private var capas: Set<Capa> = emptySet()
    private var bandaRios = ""
    private var marcadorUbicacion: Marker? = null
    private var mashconDibujado: MashconDibujo? = null

    init {
        mapa.setTileSource(OsmdroidSimpac.fuenteTiles(mapa.context))
        mapa.setMultiTouchControls(true)
        mapa.setTilesScaledToDpi(true)
        // botones de zoom siempre visibles arriba a la izquierda (como el control de Leaflet en la web)
        mapa.zoomController.setVisibility(CustomZoomButtonsController.Visibility.ALWAYS)
        mapa.zoomController.display.setPositions(false, CustomZoomButtonsDisplay.HorizontalPosition.LEFT, CustomZoomButtonsDisplay.VerticalPosition.TOP)
        mapa.zoomController.display.setMarginPadding(0.4f, 0.4f)
        mapa.minZoomLevel = 5.0
        mapa.maxZoomLevel = 18.0
        mapa.isHorizontalMapRepetitionEnabled = false
        mapa.isVerticalMapRepetitionEnabled = false
        // el Peru con margen: no vale la pena cargar tiles de otro continente
        mapa.setScrollableAreaLimitDouble(BoundingBox(2.5, -66.0, -20.5, -84.5))
        listOf(capaAvisos, capaZonas, capaRios, capaEstacionesRio, capaEstaciones, capaAcudir, capaRotulos, capaUbicacion).forEach { mapa.overlays.add(it) }
        mapa.addMapListener(DelayedMapListener(object : MapListener {
            override fun onScroll(event: ScrollEvent?): Boolean { revisarVista(); return true }
            override fun onZoom(event: ZoomEvent?): Boolean { revisarVista(); return true }
        }, 150))
    }

    private fun gp(c: Coord) = GeoPoint(c.lat, c.lon)
    private fun puntos(parte: List<Coord>): List<GeoPoint> = parte.map { gp(it) }

    val caja: Caja
        get() = mapa.boundingBox.let { Caja(it.lonWest, it.latSouth, it.lonEast, it.latNorth) }

    private fun vaciar(folder: FolderOverlay) {
        // tras MapView.onDetach() el FolderOverlay devuelve null: no hay nada que vaciar
        val items = folder.items?.toList() ?: return
        items.forEach { folder.remove(it) }
    }

    fun capasVisibles(nuevas: Set<Capa>) {
        capas = nuevas
        aplicarVisibilidad()
        mapa.invalidate()
    }

    private fun aplicarVisibilidad() {
        val zoom = mapa.zoomLevelDouble
        capaAvisos.isEnabled = Capa.AVISOS in capas
        capaRios.isEnabled = Capa.RIOS in capas
        capaEstacionesRio.isEnabled = Capa.RIOS in capas
        capaRotulos.isEnabled = Capa.RIOS in capas && zoom >= Cauces.ROTULOS_DESDE
        capaZonas.isEnabled = Capa.ZONAS in capas && zoom >= Cauces.ZONAS_DESDE
        capaEstaciones.isEnabled = Capa.ESTACIONES in capas && zoom >= Cauces.ESTACIONES_DESDE
        capaAcudir.isEnabled = Capa.ACUDIR in capas && zoom >= Cauces.ACUDIR_DESDE
    }

    // ---- avisos ----
    fun mostrarAvisos(avisos: List<AvisoDibujo>) {
        vaciar(capaAvisos)
        avisosDibujados.clear()
        for (a in avisos.sortedBy { it.aviso.nivel ?: 0 }) {
            val color = Paleta.aviso(a.aviso.nivel).toInt()
            val overlays = ArrayList<Overlay>()
            for (pol in a.poligonos.poligonos) {
                val p = Polygon(mapa)
                p.points = puntos(pol.first())
                if (pol.size > 1) p.holes = pol.drop(1).map { puntos(it) }
                p.fillPaint.color = (color and 0x00FFFFFF) or ALFA_AVISO   // 28 % (dos avisos encimados no llegan a verse opacos)
                p.outlinePaint.color = color
                p.outlinePaint.strokeWidth = 1.5f * densidad
                p.infoWindow = null
                p.setOnClickListener { _, _, pos ->
                    val aqui = avisosDibujados.map { it.first }.filter { x -> capaAvisos.isEnabled && GeoJson.contiene(x.poligonos, pos.latitude, pos.longitude) }
                    alTocar(Seleccion.Avisos(if (aqui.isEmpty()) listOf(a) else aqui))
                    true
                }
                capaAvisos.add(p); overlays += p
            }
            val glifo = a.glifo
            val centro = a.centro
            if (glifo != null && centro != null) {
                val m = Marker(mapa)
                m.position = gp(centro)
                m.icon = IconosMapa.insigniaAviso(res, glifo, a.aviso.nivel)
                m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
                m.infoWindow = null
                m.setOnMarkerClickListener { _, _ -> alTocar(Seleccion.Avisos(listOf(a))); true }
                capaAvisos.add(m); overlays += m
            }
            avisosDibujados += a to overlays
        }
        revisarVista()
    }

    // ---- rios ----
    fun mostrarRios(rios: List<RioDibujo>, mashcon: MashconDibujo?) {
        vaciar(capaRios)
        trazos.clear()
        bandaRios = ""
        mashconDibujado = mashcon
        mashcon?.let { m ->
            for (parte in m.afluentes) {
                val a = Polyline(mapa)
                a.setPoints(puntos(parte))
                a.outlinePaint.color = Paleta.AFLUENTE.toInt()
                a.outlinePaint.strokeWidth = 2f * densidad
                a.outlinePaint.alpha = 230
                a.infoWindow = null
                capaRios.add(a)
            }
            for (parte in m.cauce) {
                val halo = linea(parte, Paleta.HALO.toInt(), 11f, 235)
                capaRios.add(halo)
            }
            for (parte in m.cauce) {
                val l = linea(parte, Paleta.cauce(m.cauceEstado.estado).toInt(), 5.5f, 255)
                l.setOnClickListener { _, _, _ -> alTocar(Seleccion.Mashcon(m)); true }
                capaRios.add(l)
            }
        }
        for (r in rios) {
            val color = Paleta.cauce(r.estado.cauce.estado).toInt()
            for (parte in r.grueso) {
                val halo = linea(parte, Paleta.HALO.toInt(), 10f, 230)
                val l = linea(parte, color, 4.5f, 255)
                l.setOnClickListener { _, _, _ -> alTocar(Seleccion.Rio(r)); true }
                capaRios.add(halo); capaRios.add(l)
                trazos += Trazo(r, halo, l, "grueso")
            }
        }
        // los halos de todos van debajo de todas las lineas: se reordenan
        val halos = trazos.map { it.halo }
        halos.forEach { capaRios.remove(it) }
        val lineas = capaRios.items.toList()
        lineas.forEach { capaRios.remove(it) }
        halos.forEach { capaRios.add(it) }
        lineas.forEach { capaRios.add(it) }
        revisarVista()
    }

    private fun linea(parte: List<Coord>, color: Int, anchoDp: Float, alfa: Int): Polyline {
        val l = Polyline(mapa)
        l.setPoints(puntos(parte))
        l.outlinePaint.color = color
        l.outlinePaint.alpha = alfa
        l.outlinePaint.strokeWidth = anchoDp * densidad
        l.outlinePaint.strokeCap = Paint.Cap.ROUND
        l.outlinePaint.strokeJoin = Paint.Join.ROUND
        l.infoWindow = null
        return l
    }

    fun mostrarFinos(nuevos: Map<String, List<List<Coord>>>) {
        finos = nuevos
        bandaRios = ""
        revisarVista()
    }

    /** Detalle del trazo por zoom: grueso (pais), medio, lejos (~50 m) o fino (~6 m) si llego y esta a la vista. */
    private fun ajustarDetalleRios(zoom: Double, vista: Caja) {
        val banda = when {
            zoom < 8 -> "grueso"
            zoom < 10 -> "medio"
            zoom < Cauces.DETALLE_DESDE -> "lejos"
            else -> "fino"
        }
        val cambio = banda != bandaRios
        bandaRios = banda
        // una parte por trazo: cuando un rio tiene varias partes se dibujo una Polyline por parte del grueso;
        // al cambiar de banda se le ponen las partes equivalentes (misma cantidad y orden)
        val porRio = trazos.groupBy { it.rio.rioAna }
        for ((_, lista) in porRio) {
            val r = lista.first().rio
            val visible = GeoJson.cajasSeCruzan(r.caja, vista)
            val quiere = when {
                banda == "fino" && visible && finos.containsKey(r.rioAna) -> "fino"
                banda == "fino" -> "lejos"
                else -> banda
            }
            val partes: List<List<Coord>> = when (quiere) {
                "fino" -> finos[r.rioAna] ?: r.lejos
                "lejos" -> r.lejos
                "medio" -> r.medio
                else -> r.grueso
            }
            for ((i, t) in lista.withIndex()) {
                if (t.detalle == quiere && !cambio) continue
                if (t.detalle == quiere) continue
                val parte = partes.getOrNull(i) ?: continue
                val pts = puntos(parte)
                t.halo.setPoints(pts); t.linea.setPoints(pts)
                t.detalle = quiere
            }
            // partes extra del detalle (el fino puede traer mas partes): se omiten (la primera parte alcanza para verlo)
        }
        // en vista pais los rios tranquilos van finos y grises, los fuertes de color; lo que no toca la
        // vista (con margen) no se dibuja: osmdroid igual proyectaria sus vertices en cada cuadro
        val pais = zoom <= 6.5
        val conMargen = GeoJson.cajaConMargen(vista, 0.3)
        for (t in trazos) {
            val fuerte = Cauces.esFuerte(t.rio.estado)
            val visible = GeoJson.cajasSeCruzan(t.rio.caja, conMargen)
            t.linea.isEnabled = visible
            t.halo.isEnabled = visible && (!pais || fuerte)
            t.linea.outlinePaint.strokeWidth = (if (pais && !fuerte) 1.5f else if (zoom < 10) 3f else 4.5f) * densidad
            t.linea.outlinePaint.color = if (pais && !fuerte) Paleta.cauce(pe.simpac.app.dominio.EstadoCauce.SD).toInt() else Paleta.cauce(t.rio.estado.cauce.estado).toInt()
        }
    }

    private fun rotulos(zoom: Double, vista: Caja) {
        vaciar(capaRotulos)
        if (zoom < Cauces.ROTULOS_DESDE || Capa.RIOS !in capas) return
        data class Candidato(val rio: RioDibujo, val punto: Coord, val adentro: Int, val fuerte: Boolean)
        val cand = ArrayList<Candidato>()
        val rios = trazos.map { it.rio }.distinctBy { it.rioAna }
        for (r in rios) {
            if (!GeoJson.cajasSeCruzan(r.caja, vista)) continue
            var mejorParte: List<Coord>? = null; var mejorN = 0
            for (parte in r.lejos) {
                val n = parte.count { GeoJson.dentro(it, vista) }
                if (n > mejorN) { mejorN = n; mejorParte = parte }
            }
            val parte = mejorParte ?: continue
            val adentro = parte.filter { GeoJson.dentro(it, vista) }
            if (adentro.size < 2) continue
            cand += Candidato(r, adentro[adentro.size / 2], adentro.size, Cauces.esFuerte(r.estado))
        }
        cand.sortWith(compareByDescending<Candidato> { it.fuerte }.thenByDescending { it.adentro })
        for (c in cand.take(Cauces.MAX_ROTULOS)) {
            val rio = c.rio
            capaRotulos.add(rotulo(c.punto, rio.nombre, rio.estado.cauce.estado) { alTocar(Seleccion.Rio(rio)) })
        }
        // el Mashcon (rio vigilado) lleva tambien su nombre
        val m = mashconDibujado ?: return
        if (!GeoJson.cajasSeCruzan(m.caja, vista)) return
        val parte = m.cauce.maxByOrNull { p -> p.count { GeoJson.dentro(it, vista) } } ?: return
        val adentro = parte.filter { GeoJson.dentro(it, vista) }
        if (adentro.size < 2) return
        capaRotulos.add(rotulo(adentro[adentro.size / 2], m.nombre, m.cauceEstado.estado) { alTocar(Seleccion.Mashcon(m)) })
    }

    private fun rotulo(punto: Coord, nombre: String, estado: pe.simpac.app.dominio.EstadoCauce, alTocarRotulo: () -> Unit): Marker {
        val m = Marker(mapa)
        m.position = gp(punto)
        m.setTextLabelBackgroundColor(0xE6FFFFFF.toInt())
        m.setTextLabelForegroundColor(if (estado == pe.simpac.app.dominio.EstadoCauce.NORMAL) 0xFF0F4C81.toInt() else Paleta.cauce(estado).toInt())
        m.setTextLabelFontSize((12 * densidad).toInt())
        m.setTextIcon(nombre)
        m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM)
        m.infoWindow = null
        m.setOnMarkerClickListener { _, _ -> alTocarRotulo(); true }
        return m
    }

    // ---- estaciones de rio (ANA) ----
    fun mostrarEstacionesRio(lista: List<EstacionRioDibujo>) {
        vaciar(capaEstacionesRio)
        for (e in lista.sortedBy { if (it.fuerte) 1 else 0 }) {
            val m = Marker(mapa)
            m.position = GeoPoint(e.caudal.lat!!, e.caudal.lon!!)
            m.icon = IconosMapa.disco(res, Paleta.rio(e.estado), e.fuerte)
            m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
            m.infoWindow = null
            m.setOnMarkerClickListener { _, _ -> alTocar(Seleccion.EstacionRio(e)); true }
            capaEstacionesRio.add(m)
        }
        mapa.invalidate()
    }

    // ---- zonas ----
    fun mostrarZonas(zonas: List<ZonaDibujo>) {
        vaciar(capaZonas)
        // bajo_3m y estudio primero (debajo), bajo_2m encima
        val orden = zonas.sortedBy { if (it.subtipo == "bajo_2m") 1 else 0 }
        for (z in orden) {
            val oscuro = Paleta.zonaOscuro(z.nivel).toInt()
            val claro = Paleta.zona(z.nivel).toInt()
            val tenue = z.nivel == pe.simpac.app.dominio.NivelZona.SIN_SENALES
            for (pol in z.poligonos.poligonos) {
                if (z.subtipo == "bajo_2m" || z.tipo == "estudio") {
                    // borde blanco debajo: se lee tambien sobre el area de un aviso del mismo color
                    val b = Polygon(mapa)
                    b.points = puntos(pol.first())
                    if (pol.size > 1) b.holes = pol.drop(1).map { puntos(it) }
                    b.fillPaint.color = Color.TRANSPARENT
                    b.outlinePaint.color = Color.WHITE
                    b.outlinePaint.alpha = 240
                    b.outlinePaint.strokeWidth = 5.5f * densidad
                    b.infoWindow = null
                    capaZonas.add(b)
                }
                val p = Polygon(mapa)
                p.points = puntos(pol.first())
                if (pol.size > 1) p.holes = pol.drop(1).map { puntos(it) }
                when {
                    z.tipo == "estimada" && z.subtipo == "bajo_3m" -> {
                        p.fillPaint.color = (oscuro and 0x00FFFFFF) or (if (tenue) 0x1F000000 else 0x33000000)
                        p.outlinePaint.color = Color.TRANSPARENT
                        p.outlinePaint.strokeWidth = 0f
                    }
                    z.tipo == "estimada" && z.subtipo == "bajo_2m" -> {
                        p.fillPaint.color = Color.WHITE
                        p.fillPaint.shader = IconosMapa.shaderRayado(res, z.nivel)
                        p.outlinePaint.color = oscuro
                        p.outlinePaint.strokeWidth = 2.5f * densidad
                    }
                    z.tipo == "estudio" && z.subtipo == "menor" -> {
                        p.fillPaint.color = (claro and 0x00FFFFFF) or (if (tenue) 0x38000000 else 0x4D000000)
                        p.outlinePaint.color = oscuro
                        p.outlinePaint.strokeWidth = 2.5f * densidad
                        p.outlinePaint.pathEffect = android.graphics.DashPathEffect(floatArrayOf(3f * densidad, 3f * densidad), 0f)
                    }
                    else -> {   // estudio mayor
                        p.fillPaint.color = (claro and 0x00FFFFFF) or (if (tenue) 0x66000000 else 0x80000000.toInt())
                        p.outlinePaint.color = oscuro
                        p.outlinePaint.strokeWidth = 2.5f * densidad
                    }
                }
                p.infoWindow = null
                p.setOnClickListener { _, _, _ -> alTocar(Seleccion.Zona(z)); true }
                capaZonas.add(p)
            }
        }
        mapa.invalidate()
    }

    // ---- estaciones de SENAMHI ----
    fun mostrarEstaciones(lista: List<EstacionSenamhi>) {
        vaciar(capaEstaciones)
        for (e in lista) {
            val m = Marker(mapa)
            m.position = GeoPoint(e.lat!!, e.lon!!)
            m.icon = IconosMapa.estacion(res, Paleta.ESTACION[e.tipo] ?: Paleta.SIN_DATO)
            m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
            m.infoWindow = null
            m.setOnMarkerClickListener { _, _ -> alTocar(Seleccion.Estacion(e)); true }
            capaEstaciones.add(m)
        }
        mapa.invalidate()
    }

    // ---- a donde acudir ----
    fun mostrarAcudir(lista: List<PuntoAcudir>) {
        vaciar(capaAcudir)
        for (p in lista) {
            val m = Marker(mapa)
            m.position = GeoPoint(p.lat!!, p.lon!!)
            m.icon = IconosMapa.acudir(res, p.tipo)
            m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
            m.infoWindow = null
            m.setOnMarkerClickListener { _, _ -> alTocar(Seleccion.Acudir(p)); true }
            capaAcudir.add(m)
        }
        mapa.invalidate()
    }

    // ---- tu ubicacion ----
    fun mostrarUbicacion(p: Posicion?) {
        vaciar(capaUbicacion)
        marcadorUbicacion = null
        if (p == null) { mapa.invalidate(); return }
        val m = Marker(mapa)
        m.position = GeoPoint(p.lat, p.lon)
        m.icon = IconosMapa.ubicacion(res)
        m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
        m.infoWindow = null
        m.setOnMarkerClickListener { _, _ -> true }
        capaUbicacion.add(m)
        marcadorUbicacion = m
        mapa.invalidate()
    }

    fun centrar(p: Posicion, zoom: Double? = null) {
        mapa.controller.animateTo(GeoPoint(p.lat, p.lon), zoom ?: mapa.zoomLevelDouble, 400L)
    }

    fun encuadrar(c: Caja) {
        val bb = BoundingBox(c.norte, c.este, c.sur, c.oeste)
        mapa.post { mapa.zoomToBoundingBox(bb, true, (24 * densidad).toInt()) }
    }

    /** Al parar el mapa: detalle de los rios, nombres, que avisos tocan la vista y aviso al ViewModel. */
    fun revisarVista() {
        if (mapa.width == 0 || mapa.height == 0) return
        val zoom = mapa.zoomLevelDouble
        val vista = caja
        aplicarVisibilidad()
        ajustarDetalleRios(zoom, vista)
        rotulos(zoom, vista)
        // como en la web (index.css [data-zoom-banda] .leaflet-aviso2-pane): de cerca (zoom 13 o mas) el
        // amarillo baja al 12 %, porque a esa escala el area cubre toda la pantalla y se lee como fondo
        val alfaAmarillo = if (zoom >= AVISO_AMARILLO_TENUE_DESDE) 0x1F000000 else ALFA_AVISO
        for ((a, overlays) in avisosDibujados) {
            val toca = GeoJson.cajasSeCruzan(a.caja, vista)
            val alfa = if (a.aviso.nivel == 2) alfaAmarillo else ALFA_AVISO
            overlays.forEach {
                it.isEnabled = toca
                if (it is Polygon) it.fillPaint.color = (it.fillPaint.color and 0x00FFFFFF) or alfa
            }
        }
        mapa.invalidate()
        alCambiarVista(vista, zoom)
    }
}
