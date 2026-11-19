package pe.simpac.app.ui.mapa

import org.osmdroid.tileprovider.tilesource.OnlineTileSourceBase
import org.osmdroid.util.MapTileIndex
import pe.simpac.app.dominio.Lluvia
import java.net.URLEncoder

/**
 * Fuentes de imagenes (tiles) de las capas de lluvia que no son datos de SIMPAC sino imagenes de
 * otro servidor, como en la web: la lluvia observada de SENAMHI (WMS de IDESEP, map/senamhi.js) y
 * la lluvia por satelite de la NASA (WMTS de GIBS, map/layers/lluviaSatelite.js). osmdroid las pide
 * tile por tile y las guarda en su cache de tiles.
 */

private fun nombreSeguro(s: String): String = s.replace(Regex("[^A-Za-z0-9_-]"), "_")

/**
 * WMS de SENAMHI pedido como tiles de 256 px en EPSG:3857 con el estilo propio (SLD) de la web:
 * transparente donde casi no llovio y una escala de azules. El nombre lleva el dia procesado para
 * que un dia nuevo no reuse las imagenes guardadas del anterior.
 */
class FuenteWmsSenamhi(val capa: Lluvia.CapaObservada, dia: String?) : OnlineTileSourceBase(
    nombreSeguro("senamhi_${capa.clave}_${dia ?: "sin_fecha"}"), 0, 18, 256, ".png",
    arrayOf("${Lluvia.GEOSERVER}/monitoreo_meteorologico/wms"), Lluvia.ATRIBUCION_SENAMHI,
) {
    private val sld: String = URLEncoder.encode(Lluvia.sldLluvia(capa.capa, capa.cortes), "UTF-8")

    override fun getTileURLString(pMapTileIndex: Long): String =
        url(MapTileIndex.getZoom(pMapTileIndex), MapTileIndex.getX(pMapTileIndex), MapTileIndex.getY(pMapTileIndex))

    fun url(z: Int, x: Int, y: Int): String {
        val n = 1 shl z
        val mundo = 20037508.342789244
        val tam = 2 * mundo / n
        val minX = -mundo + x * tam; val maxX = minX + tam
        val maxY = mundo - y * tam; val minY = maxY - tam
        return baseUrl + "?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1&LAYERS=" + URLEncoder.encode(capa.capa, "UTF-8") +
            "&STYLES=&FORMAT=image%2Fpng&TRANSPARENT=true&SRS=EPSG%3A3857&WIDTH=256&HEIGHT=256" +
            "&BBOX=$minX,$minY,$maxX,$maxY&sld_body=$sld"
    }

    companion object {
        /** Una imagen de prueba: el tile de zoom 5 sobre el Peru (x 8, y 16). */
        fun urlPrueba(capa: Lluvia.CapaObservada): String = FuenteWmsSenamhi(capa, null).url(5, 8, 16)
    }
}

/**
 * NASA GIBS, IMERG de 30 min, en la matriz GoogleMapsCompatible_Level6: solo hay imagenes hasta el
 * zoom 6; mas cerca osmdroid agranda las de zoom 6 que ya tenga guardadas (GestorMapa las baja
 * primero para todo el Peru). `tiempo` es la hora ISO confirmada o "default".
 */
class FuenteGibs(val tiempo: String) : OnlineTileSourceBase(
    nombreSeguro("gibs_imerg_$tiempo"), 0, Lluvia.GIBS_ZOOM_MAX, 256, ".png", arrayOf("${Lluvia.GIBS}/"), Lluvia.ATRIBUCION_GIBS,
) {
    override fun getTileURLString(pMapTileIndex: Long): String =
        baseUrl + tiempo + "/" + Lluvia.GIBS_MATRIZ + "/" + MapTileIndex.getZoom(pMapTileIndex) + "/" +
            MapTileIndex.getY(pMapTileIndex) + "/" + MapTileIndex.getX(pMapTileIndex) + ".png"
}
