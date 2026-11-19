package pe.simpac.app.ui.mapa

import android.content.Context
import android.graphics.Color
import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.DashPathEffect
import android.graphics.Paint
import org.osmdroid.config.Configuration
import org.osmdroid.events.DelayedMapListener
import org.osmdroid.events.MapListener
import org.osmdroid.events.ScrollEvent
import org.osmdroid.events.ZoomEvent
import org.osmdroid.tileprovider.MapTileProviderBasic
import org.osmdroid.tileprovider.cachemanager.CacheManager
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
import org.osmdroid.views.overlay.TilesOverlay
import pe.simpac.app.BuildConfig
import pe.simpac.app.data.EstacionSenamhi
import pe.simpac.app.data.PronosticoLocalidad
import pe.simpac.app.data.PuntoAcudir
import pe.simpac.app.data.ReporteVigente
import pe.simpac.app.data.RioIncidente
import pe.simpac.app.dominio.Caja
import pe.simpac.app.dominio.Cauces
import pe.simpac.app.dominio.Coord
import pe.simpac.app.dominio.Fen
import pe.simpac.app.dominio.GeoJson
import pe.simpac.app.dominio.Geometria
import pe.simpac.app.dominio.Incidentes
import pe.simpac.app.dominio.Lluvia
import pe.simpac.app.dominio.Nowcast
import pe.simpac.app.dominio.Paleta
import pe.simpac.app.dominio.PronosticoMapa
import pe.simpac.app.dominio.Reportes
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
    /** Una localidad del pronostico: la fila del dia elegido y sus 3 dias. */
    data class Localidad(val fila: PronosticoLocalidad, val propias: List<PronosticoLocalidad>, val tuya: Boolean) : Seleccion()
    data class ManchaNowcast(val mancha: ManchaDibujo, val horizonte: Int, val lat: Double, val lon: Double) : Seleccion()
    data class LluviaEstacion(val lluvia: LluviaDibujo) : Seleccion()
    data class PoligonoFen(val poligono: Fen.PoligonoFen, val fen: FenDibujo) : Seleccion()
    data class Incidentes(val grupo: pe.simpac.app.dominio.Incidentes.Grupo, val nombreRio: String?) : Seleccion()
    data class Reporte(val reporte: ReporteVigente) : Seleccion()
    data class Franja(val franja: FranjaDibujo) : Seleccion()
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
 * capas van en FolderOverlay, de abajo hacia arriba como los panes de la web: imagenes de lluvia
 * (SENAMHI y NASA), El Nino pasados, avisos, nowcasting, zonas, franjas, rios, estaciones de rio,
 * desbordes, lluvia de la hora, estaciones de SENAMHI, pronostico, acudir, reportes, nombres, tu
 * ubicacion. Lo que depende del zoom (detalle del trazo, nombres, capas que solo se ven de cerca,
 * poligonos de El Nino a la vista, agrupacion de rombos) se revisa al parar el mapa (150 ms), en el
 * hilo principal pero con listas ya calculadas.
 */
class GestorMapa(
    val mapa: MapView,
    private val alTocar: (Seleccion) -> Unit,
    private val alCambiarVista: (Caja, Double) -> Unit,
) {
    private val res = mapa.resources
    private val densidad = res.displayMetrics.density
    private val capaFen = FolderOverlay()
    private val capaAvisos = FolderOverlay()
    private val capaNowcast = FolderOverlay()
    private val capaZonas = FolderOverlay()
    private val capaFranjas = FolderOverlay()
    private val capaRios = FolderOverlay()
    private val capaEstacionesRio = FolderOverlay()
    private val capaDesbordes = FolderOverlay()
    private val capaLluvia = FolderOverlay()
    private val capaEstaciones = FolderOverlay()
    private val capaPronostico = FolderOverlay()
    private val capaAcudir = FolderOverlay()
    private val capaReportes = FolderOverlay()
    private val capaRotulos = FolderOverlay()
    private val capaUbicacion = FolderOverlay()

    private companion object {
        /** Relleno del area de un aviso: 28 % (dos avisos encimados no llegan a verse opacos). */
        const val ALFA_AVISO = 0x47000000
        /** Desde este zoom el area amarilla baja al 12 % (web: index.css, bandas z13+). */
        const val AVISO_AMARILLO_TENUE_DESDE = 13.0
        /** Vista pais: los discos del pronostico pasan a puntos de color (web: data-escala="pais"). */
        const val PRONOSTICO_PUNTO_HASTA = 8.0
        /** Hasta este zoom El Nino usa los anillos simplificados. */
        const val FEN_LEJOS_HASTA = 9.0
        /** El Peru con margen, para bajar las imagenes de zoom 3 a 6 del satelite. */
        val PERU = BoundingBox(0.5, -68.0, -18.6, -81.8)
    }

    private class Trazo(val rio: RioDibujo, val halo: Polyline, val linea: Polyline, var detalle: String)
    private val trazos = ArrayList<Trazo>()
    private val avisosDibujados = ArrayList<Pair<AvisoDibujo, List<Overlay>>>()
    private var finos: Map<String, List<List<Coord>>> = emptyMap()
    private var capas: Set<Capa> = emptySet()
    private var bandaRios = ""
    private var marcadorUbicacion: Marker? = null
    private var mashconDibujado: MashconDibujo? = null

    // pronostico: un marcador por localidad del dia elegido, con lo que hace falta para cambiar de icono por zoom
    private class Localidad(val marcador: Marker, val aspecto: PronosticoMapa.Aspecto, val tuya: Boolean)
    private val localidades = ArrayList<Localidad>()
    private var pronosticoEnPuntos: Boolean? = null
    // El Nino: poligonos creados una vez; a la vista y con el detalle del zoom
    private class PoligonoFenDibujado(val dato: Fen.PoligonoFen, val overlays: List<Polygon>, var detalle: String, var enCapa: Boolean = false)
    private val fenDibujados = ArrayList<PoligonoFenDibujado>()
    // desbordes: se reagrupan al cambiar el zoom entero
    private var incidentes: List<RioIncidente> = emptyList()
    private var nombresRiosVigilados: Map<String, String> = emptyMap()
    private var zoomRombos = -1
    // nowcasting: solo con "Hoy"
    private var nowcastHoy = true
    // imagenes de lluvia
    private var lluviaObsOverlay: TilesOverlay? = null
    private var lluviaObsProveedor: MapTileProviderBasic? = null
    private var lluviaObsClave: String? = null
    private var sateliteOverlay: TilesOverlay? = null
    private var sateliteProveedor: MapTileProviderBasic? = null
    private var sateliteTiempo: String? = null
    private var sateliteDescarga: CacheManager.CacheManagerTask? = null

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
        listOf(
            capaFen, capaAvisos, capaNowcast, capaZonas, capaFranjas, capaRios, capaEstacionesRio, capaDesbordes, capaLluvia,
            capaEstaciones, capaPronostico, capaAcudir, capaReportes, capaRotulos, capaUbicacion,
        ).forEach { mapa.overlays.add(it) }
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

    /** Al salir de la pestana: suelta los proveedores de imagenes y el MapView. */
    fun soltar() {
        sateliteDescarga?.cancel(true)
        lluviaObsProveedor?.detach(); sateliteProveedor?.detach()
        mapa.onDetach()
    }

    fun capasVisibles(nuevas: Set<Capa>) {
        capas = nuevas
        aplicarVisibilidad()
        mapa.invalidate()
    }

    /** El nowcasting solo se dibuja con "Hoy" elegido arriba del mapa. */
    fun nowcastSoloHoy(hoy: Boolean) {
        nowcastHoy = hoy
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
        capaFranjas.isEnabled = Capa.ZONAS in capas && zoom >= Cauces.DETALLE_DESDE
        capaEstaciones.isEnabled = Capa.ESTACIONES in capas && zoom >= Cauces.ESTACIONES_DESDE
        capaAcudir.isEnabled = Capa.ACUDIR in capas && zoom >= Cauces.ACUDIR_DESDE
        capaPronostico.isEnabled = Capa.PRONOSTICO in capas
        capaNowcast.isEnabled = Capa.NOWCAST in capas && nowcastHoy
        capaLluvia.isEnabled = Capa.LLUVIA_AHORA in capas
        capaFen.isEnabled = Capa.FEN in capas
        capaDesbordes.isEnabled = Capa.DESBORDES in capas && zoom >= Incidentes.DESDE_ZOOM
        capaReportes.isEnabled = Capa.REPORTES in capas
        lluviaObsOverlay?.isEnabled = Capa.LLUVIA_OBSERVADA in capas
        sateliteOverlay?.isEnabled = Capa.SATELITE in capas
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
                        p.outlinePaint.pathEffect = DashPathEffect(floatArrayOf(3f * densidad, 3f * densidad), 0f)
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

    // ---- franja de atencion de los rios del pais en alerta o emergencia ----
    fun mostrarFranjas(franjas: List<FranjaDibujo>) {
        vaciar(capaFranjas)
        for (f in franjas) {
            val nivel = f.rio.estado.zona.nivel
            val oscuro = Paleta.zonaOscuro(nivel).toInt()
            val claro = Paleta.zona(nivel).toInt()
            for (pol in f.poligonos.poligonos) {
                val p = Polygon(mapa)
                p.points = puntos(pol.first())
                if (pol.size > 1) p.holes = pol.drop(1).map { puntos(it) }
                p.fillPaint.color = (claro and 0x00FFFFFF) or 0x1A000000       // relleno muy suave (10 %)
                p.outlinePaint.color = oscuro
                p.outlinePaint.alpha = 230
                p.outlinePaint.strokeWidth = 1.5f * densidad
                p.outlinePaint.pathEffect = DashPathEffect(floatArrayOf(6f * densidad, 4f * densidad), 0f)   // contorno punteado
                p.infoWindow = null
                p.setOnClickListener { _, _, _ -> alTocar(Seleccion.Franja(f)); true }
                capaFranjas.add(p)
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

    // ---- pronostico por localidad (del dia elegido) ----
    /**
     * Un disco blanco por localidad con el glifo del dia elegido; punteado si SENAMHI dice "tendencia
     * a"; tu localidad con aro negro. Sin fila no hay disco (nunca se pinta "sin lluvia" donde SENAMHI
     * no publica). En vista pais los discos pasan a puntos de color (revisarVista).
     */
    fun mostrarPronostico(filas: List<PronosticoLocalidad>, fecha: String, tuya: String?) {
        vaciar(capaPronostico)
        localidades.clear()
        pronosticoEnPuntos = null
        val propiasPorCodigo = filas.groupBy { it.codigo }
        val delDia = filas.filter { it.fecha == fecha && it.lat != null && it.lon != null }
        // tu localidad al final (encima); los de mas prioridad (tormenta, lluvia) encima de los secos
        for (f in delDia.sortedWith(compareBy<PronosticoLocalidad> { if (it.codigo == tuya) 1 else 0 }.thenBy { PronosticoMapa.aspecto(it).prioridad })) {
            val a = PronosticoMapa.aspecto(f)
            val esTuya = f.codigo == tuya
            val m = Marker(mapa)
            m.position = GeoPoint(f.lat!!, f.lon!!)
            m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
            m.infoWindow = null
            m.title = f.nombre
            m.setOnMarkerClickListener { _, _ -> alTocar(Seleccion.Localidad(f, propiasPorCodigo[f.codigo] ?: listOf(f), esTuya)); true }
            capaPronostico.add(m)
            localidades += Localidad(m, a, esTuya)
        }
        revisarVista()
    }

    private fun iconosPronostico(zoom: Double) {
        val enPuntos = zoom < PRONOSTICO_PUNTO_HASTA
        if (enPuntos == pronosticoEnPuntos) return
        pronosticoEnPuntos = enPuntos
        for (l in localidades) {
            l.marcador.icon = if (enPuntos) IconosMapa.puntoLocalidad(res, l.aspecto.color, l.tuya)
            else IconosMapa.discoLocalidad(res, l.aspecto.glifo, l.aspecto.posible, l.tuya, l.aspecto.clase == "seco")
        }
    }

    // ---- nowcasting ----
    fun mostrarNowcast(n: NowcastDibujo?) {
        vaciar(capaNowcast)
        if (n == null) { mapa.invalidate(); return }
        for (m in n.manchas) {
            val color = (Nowcast.COLOR[m.nivel] ?: Nowcast.COLOR.getValue(1)).toInt()
            for (pol in m.poligonos.poligonos) {
                val p = Polygon(mapa)
                p.points = puntos(pol.first())
                if (pol.size > 1) p.holes = pol.drop(1).map { puntos(it) }
                p.fillPaint.color = (color and 0x00FFFFFF) or ((Nowcast.ALFA[m.nivel] ?: 0x80) shl 24)
                p.outlinePaint.color = color
                p.outlinePaint.strokeWidth = 1.5f * densidad
                p.outlinePaint.pathEffect = DashPathEffect(floatArrayOf(4f * densidad, 3f * densidad), 0f)
                p.infoWindow = null
                p.setOnClickListener { _, _, pos -> alTocar(Seleccion.ManchaNowcast(m, n.horizonte, pos.latitude, pos.longitude)); true }
                capaNowcast.add(p)
            }
        }
        mapa.invalidate()
    }

    // ---- lluvia de la ultima hora ----
    fun mostrarLluviaAhora(lista: List<LluviaDibujo>) {
        vaciar(capaLluvia)
        for (l in lista) {   // ya viene ordenada: las que pasaron la referencia al final (encima)
            val m = Marker(mapa)
            m.position = GeoPoint(l.e.lat!!, l.e.lon!!)
            m.icon = IconosMapa.discoLluvia(res, Lluvia.color(l.intensidad), Lluvia.radio(l.intensidad, l.ref.pasa), l.ref.pasa, (l.e.pp_1h ?: 0.0) > 0)
            m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
            m.infoWindow = null
            m.setOnMarkerClickListener { _, _ -> alTocar(Seleccion.LluviaEstacion(l)); true }
            capaLluvia.add(m)
        }
        mapa.invalidate()
    }

    // ---- lluvia observada (imagenes WMS de SENAMHI) ----
    /** Pone (o quita, con null) la imagen WMS del periodo; `dia` es el dia procesado (clave de la cache). */
    fun mostrarLluviaObservada(capa: Lluvia.CapaObservada?, dia: String?) {
        val clave = capa?.let { "${it.clave}|${dia ?: ""}" }
        if (clave == lluviaObsClave) return
        lluviaObsClave = clave
        lluviaObsOverlay?.let { mapa.overlays.remove(it) }
        lluviaObsProveedor?.detach()
        lluviaObsOverlay = null; lluviaObsProveedor = null
        if (capa != null) {
            val proveedor = MapTileProviderBasic(mapa.context, FuenteWmsSenamhi(capa, dia))
            val overlay = TilesOverlay(proveedor, mapa.context)
            overlay.loadingBackgroundColor = Color.TRANSPARENT
            overlay.loadingLineColor = Color.TRANSPARENT
            overlay.isEnabled = Capa.LLUVIA_OBSERVADA in capas
            mapa.overlays.add(0, overlay)   // debajo de todo lo demas (pane "areas" de la web)
            lluviaObsOverlay = overlay; lluviaObsProveedor = proveedor
        }
        mapa.invalidate()
    }

    // ---- lluvia por satelite (NASA GIBS) ----
    /** Pone (o quita, con null) las imagenes IMERG de esa hora ("default" si no hay hora confirmada), al 70 %. */
    fun mostrarSatelite(tiempo: String?) {
        if (tiempo == sateliteTiempo) return
        sateliteTiempo = tiempo
        sateliteDescarga?.cancel(true); sateliteDescarga = null
        sateliteOverlay?.let { mapa.overlays.remove(it) }
        sateliteProveedor?.detach()
        sateliteOverlay = null; sateliteProveedor = null
        if (tiempo != null) {
            val fuente = FuenteGibs(tiempo)
            val proveedor = MapTileProviderBasic(mapa.context, fuente)
            val overlay = TilesOverlay(proveedor, mapa.context)
            overlay.loadingBackgroundColor = Color.TRANSPARENT
            overlay.loadingLineColor = Color.TRANSPARENT
            overlay.setColorFilter(ColorMatrixColorFilter(ColorMatrix(floatArrayOf(
                1f, 0f, 0f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 0f, 0f, 0.7f, 0f,
            ))))
            overlay.isEnabled = Capa.SATELITE in capas
            mapa.overlays.add(if (lluviaObsOverlay != null) 1 else 0, overlay)
            sateliteOverlay = overlay; sateliteProveedor = proveedor
            // GIBS solo tiene imagenes hasta el zoom 6: se bajan las del Peru (zoom 3 a 6, ~20 imagenes) a la
            // cache y osmdroid agranda la de zoom 6 cuando el mapa esta mas cerca
            try {
                val gestor = CacheManager(proveedor, proveedor.tileWriter, 0, Lluvia.GIBS_ZOOM_MAX)
                sateliteDescarga = gestor.downloadAreaAsyncNoUI(mapa.context, PERU, 3, Lluvia.GIBS_ZOOM_MAX, object : CacheManager.CacheManagerCallback {
                    override fun onTaskComplete() { mapa.post { proveedor.clearTileCache(); mapa.invalidate() } }
                    override fun onTaskFailed(errors: Int) { mapa.post { proveedor.clearTileCache(); mapa.invalidate() } }
                    override fun updateProgress(progress: Int, currentZoomLevel: Int, zoomMin: Int, zoomMax: Int) {}
                    override fun downloadStarted() {}
                    override fun setPossibleTilesInArea(total: Int) {}
                })
            } catch (_: Exception) {
                // sin descarga previa la capa igual se ve con el mapa alejado (zoom 6 o menos)
            }
        }
        mapa.invalidate()
    }

    // ---- El Nino pasados ----
    /** Crea los poligonos una vez (fuera de la capa); revisarVista pone en la capa los de la vista con el detalle del zoom. */
    fun mostrarFen(f: FenDibujo?) {
        vaciar(capaFen)
        fenDibujados.clear()
        if (f != null) for (d in f.poligonos) {
            val color = (d.clase?.color ?: Fen.COLOR_SIN_CLASE).toInt()
            val overlays = ArrayList<Polygon>(d.lejos.size)
            for (anillo in d.lejos) {
                val p = Polygon(mapa)
                p.points = puntos(anillo)
                p.fillPaint.color = (color and 0x00FFFFFF) or (Fen.alfa(d.clase) shl 24)
                p.outlinePaint.color = Color.TRANSPARENT
                p.outlinePaint.strokeWidth = 0f
                p.infoWindow = null
                p.setOnClickListener { _, _, _ -> alTocar(Seleccion.PoligonoFen(d, f)); true }
                overlays += p
            }
            fenDibujados += PoligonoFenDibujado(d, overlays, "lejos")
        }
        revisarVista()
    }

    /**
     * Solo los poligonos que tocan la vista (con margen) estan en la capa: osmdroid consulta los toques
     * en TODOS los overlays de una carpeta, esten o no habilitados, y un poligono fuera de la vista
     * guarda el trazo de pantalla de su ultimo dibujo; sacarlo de la carpeta evita que se lleve un
     * toque y que se recorra en cada cuadro. De lejos (zoom 9 o menos) van los anillos simplificados.
     */
    private fun ajustarFen(zoom: Double, vista: Caja) {
        if (fenDibujados.isEmpty()) return
        val detalle = if (zoom <= FEN_LEJOS_HASTA) "lejos" else "fino"
        val conMargen = GeoJson.cajaConMargen(vista, 0.3)
        for (d in fenDibujados) {
            val visible = Capa.FEN in capas && GeoJson.cajasSeCruzan(d.dato.caja, conMargen)
            if (visible && d.detalle != detalle) {
                val anillos = if (detalle == "fino") d.dato.anillos else d.dato.lejos
                for ((i, p) in d.overlays.withIndex()) anillos.getOrNull(i)?.let { p.points = puntos(it) }
                d.detalle = detalle
            }
            if (visible != d.enCapa) {
                if (visible) d.overlays.forEach { capaFen.add(it) } else d.overlays.forEach { capaFen.remove(it) }
                d.enCapa = visible
            }
        }
    }

    // ---- desbordes y danos pasados (rombos agrupados por zoom) ----
    fun mostrarIncidentes(lista: List<RioIncidente>, nombres: Map<String, String>) {
        incidentes = Incidentes.dibujables(lista)
        nombresRiosVigilados = nombres
        zoomRombos = -1
        revisarVista()
    }

    private fun rombos(zoom: Double) {
        val z = Math.round(zoom).toInt()
        if (z == zoomRombos) return
        zoomRombos = z
        vaciar(capaDesbordes)
        if (incidentes.isEmpty()) return
        val lat0 = incidentes.sumOf { it.lat!! } / incidentes.size
        for (g in Incidentes.agrupar(incidentes, Incidentes.radioM(lat0, z.toDouble()))) {
            val i = g.incidentes.first()   // el mas nuevo
            val m = Marker(mapa)
            m.position = GeoPoint(g.lat, g.lon)
            m.icon = IconosMapa.rombo(res, Incidentes.anioCorto(i), g.incidentes.size)
            m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
            m.infoWindow = null
            m.setOnMarkerClickListener { _, _ -> alTocar(Seleccion.Incidentes(g, nombresRiosVigilados[i.rio])); true }
            capaDesbordes.add(m)
        }
    }

    // ---- reportes de la comunidad ----
    fun mostrarReportes(lista: List<ReporteVigente>) {
        vaciar(capaReportes)
        for (r in lista) {
            val tipo = Reportes.tipo(r.tipo)
            val m = Marker(mapa)
            m.position = GeoPoint(r.lat!!, r.lon!!)
            m.icon = IconosMapa.pinReporte(res, tipo.id, tipo.color)
            m.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM)
            m.alpha = Reportes.opacidad(r.estado, r.likes, r.dislikes)
            m.infoWindow = null
            m.setOnMarkerClickListener { _, _ -> alTocar(Seleccion.Reporte(r)); true }
            capaReportes.add(m)
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

    /** Al parar el mapa: detalle de los rios, nombres, que avisos tocan la vista, El Nino a la vista, rombos y aviso al ViewModel. */
    fun revisarVista() {
        if (mapa.width == 0 || mapa.height == 0) return
        val zoom = mapa.zoomLevelDouble
        val vista = caja
        aplicarVisibilidad()
        ajustarDetalleRios(zoom, vista)
        rotulos(zoom, vista)
        iconosPronostico(zoom)
        ajustarFen(zoom, vista)
        if (capaDesbordes.isEnabled) rombos(zoom)
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
