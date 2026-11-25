package pe.simpac.app.data

import kotlinx.serialization.builtins.ListSerializer
import pe.simpac.app.dominio.Caja
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.Geo

/**
 * Todas las consultas de la app en un solo lugar. Cada una pide a la red y guarda la respuesta en
 * disco; si la red falla y hay copia, devuelve la copia con deCache = true y la hora en que se guardo.
 * Si no hay ni red ni copia, lanza ErrorConsulta con un mensaje para la pantalla.
 * Las consultas del mapa llevan ademas un plazo (ttlMs): si la copia en disco es mas nueva que el
 * plazo se devuelve sin ir a la red (deCache = false: es un dato vigente), asi cambiar de pestana o
 * mover el mapa no vuelve a bajar 750 KB de trazos.
 */
class Repositorio(
    private val supabase: ClienteSupabase,
    private val api: ClienteApi,
    private val cache: CacheDisco,
) {
    companion object {
        const val TTL_RIOS_MS = 10 * 60_000L
        const val TTL_AVISOS_MS = 5 * 60_000L
    }

    private suspend fun <T> consultar(clave: String, pedir: suspend () -> String, convertir: (String) -> T): Resultado<T> =
        consultarConPlazo(clave, 0L, pedir, convertir)

    private suspend fun <T> consultarConPlazo(clave: String, ttlMs: Long, pedir: suspend () -> String, convertir: (String) -> T): Resultado<T> {
        if (ttlMs > 0) {
            val copia = cache.leer(clave)
            if (copia != null && System.currentTimeMillis() - copia.second < ttlMs) {
                try {
                    return Resultado(convertir(copia.first), copia.second, false)
                } catch (_: Exception) { }
            }
        }
        try {
            val cuerpo = pedir()
            val dato = convertir(cuerpo)   // si no se entiende, no se guarda
            cache.guardar(clave, cuerpo)
            return Resultado(dato, System.currentTimeMillis(), false)
        } catch (e: Exception) {
            val copia = cache.leer(clave)
            if (copia != null) {
                try {
                    return Resultado(convertir(copia.first), copia.second, true)
                } catch (_: Exception) { }
            }
            throw if (e is ErrorConsulta) e else ErrorConsulta("No se pudo leer la respuesta (${e.javaClass.simpleName})", e)
        }
    }

    private inline fun <reified T> lista(cuerpo: String): List<T> =
        JsonSifec.decodeFromString(ListSerializer(kotlinx.serialization.serializer<T>()), cuerpo)

    /** titular_zona del departamento (null si la tarea titular aun no escribio ese departamento). */
    suspend fun titular(departamento: String): Resultado<TitularZona?> = consultar(
        "titular:$departamento",
        { supabase.get("titular_zona", mapOf(
            "select" to "departamento,nivel,titular_corto,titular,detalle,generado_en,revisado_en,origen",
            "departamento" to "eq.$departamento", "limit" to "1")) },
        { lista<TitularZona>(it).firstOrNull() },
    )

    /** Todas las alertas vigentes del pais (alerta_actual); la zona se filtra en la app. */
    suspend fun alertas(): Resultado<List<AlertaActual>> = consultar(
        "alertas",
        { supabase.get("alerta_actual", mapOf(
            "select" to "tipo,referencia,zona,nivel,detalle,valor,umbral,ventana_h,ts,lat,lon",
            "order" to "ts.desc", "limit" to "1000")) },
        { lista<AlertaActual>(it) },
    )

    /** Pronostico de las localidades dentro de la caja (hoy, manana y pasado). */
    suspend fun pronostico(caja: Caja): Resultado<List<PronosticoVigente>> = consultar(
        "pronostico:${caja.oeste},${caja.sur},${caja.este},${caja.norte}",
        { supabase.get("pronostico_vigente", mapOf(
            "select" to "codigo,nombre,departamento,lat,lon,fecha,emision,tmax,tmin,texto,tipo,posible,lluvia_segura,intensidad,momento,cielo,url",
            "lat" to "gte.${caja.sur}", "and" to "(lat.lte.${caja.norte},lon.gte.${caja.oeste},lon.lte.${caja.este})",
            "order" to "codigo,fecha", "limit" to "1000")) },
        { lista<PronosticoVigente>(it) },
    )

    /** Puntos de "A donde acudir" dentro de la caja (nunca la tabla entera: hay mas de 12 000). */
    suspend fun puntosAcudir(caja: Caja): Resultado<List<PuntoAcudir>> = consultar(
        "acudir:${caja.oeste},${caja.sur},${caja.este},${caja.norte}",
        { supabase.get("punto_acudir", mapOf(
            "select" to "clave,tipo,nombre,categoria,atiende_24h,direccion,distrito,provincia,departamento,telefono,lat,lon,fuente,fuente_url,atribucion,actualizado",
            "lat" to "gte.${caja.sur}", "and" to "(lat.lte.${caja.norte},lon.gte.${caja.oeste},lon.lte.${caja.este})",
            "order" to "clave", "limit" to "3000")) },
        { lista<PuntoAcudir>(it) },
    )

    /** Rios con trazo del departamento (rio_cauce_mapa sin geometria). */
    suspend fun riosDelDepartamento(departamento: String): Resultado<List<RioCauceResumen>> = consultar(
        "rios:$departamento",
        { supabase.get("rio_cauce_mapa", mapOf(
            "select" to "rio_ana,nombre,departamento",
            "departamento" to "ilike.*${Departamentos.sinTildes(departamento)}*", "order" to "nombre", "limit" to "200")) },
        { lista<RioCauceResumen>(it) },
    )

    /** Senales de hoy de esos rios (rio_cauce_senal). */
    suspend fun senalesRios(riosAna: List<String>): Resultado<List<RioCauceSenal>> {
        if (riosAna.isEmpty()) return Resultado(emptyList(), System.currentTimeMillis(), false)
        val enLista = riosAna.joinToString(",") { "\"" + it.replace("\"", "") + "\"" }
        return consultar(
            "senales:${riosAna.sorted().joinToString("|")}",
            { supabase.get("rio_cauce_senal", mapOf("select" to "rio_ana,lecturas,avisos_hidro", "rio_ana" to "in.($enLista)")) },
            { lista<RioCauceSenal>(it) },
        )
    }

    /** Estaciones de SENAMHI cerca de un punto: con ellas se sabe el departamento donde esta la persona. */
    suspend fun estacionesCerca(lat: Double, lon: Double): Resultado<List<EstacionBreve>> {
        val caja = Geo.cajaAlrededor(lat, lon, 60.0)
        return consultar(
            "estaciones:${caja.oeste},${caja.sur},${caja.este},${caja.norte}",
            { supabase.get("estacion", mapOf(
                "select" to "departamento,lat,lon",
                "lat" to "gte.${caja.sur}", "and" to "(lat.lte.${caja.norte},lon.gte.${caja.oeste},lon.lte.${caja.este})",
                "limit" to "500")) },
            { lista<EstacionBreve>(it) },
        )
    }

    /** Snapshot de la API de SIFEC (contexto El Nino, resumen, alertas con 'oficial', caudales). */
    suspend fun snapshot(apiUrl: String): Resultado<Snapshot> = consultar(
        "snapshot:$apiUrl",
        { api.snapshot(apiUrl) },
        { JsonSifec.decodeFromString(Snapshot.serializer(), it) },
    )

    /** Departamento en el que esta la persona: la estacion de SENAMHI mas cercana; si falla, la capital mas cercana. */
    suspend fun departamentoDe(lat: Double, lon: Double): String {
        try {
            val estaciones = estacionesCerca(lat, lon).dato.filter { it.lat != null && it.lon != null && !it.departamento.isNullOrBlank() }
            val cercana = estaciones.minByOrNull { Geo.distanciaKm(lat, lon, it.lat!!, it.lon!!) }
            val nombre = cercana?.departamento?.let { Departamentos.porNombre(it)?.nombre }
            if (nombre != null) return nombre
        } catch (_: Exception) { }
        return Departamentos.masCercano(lat, lon).nombre
    }

    // ---- mapa nativo (pestana Mapa) ----

    /** Avisos de SENAMHI que no han terminado, con su area en GeoJSON (aviso_vigente; 5 min). */
    suspend fun avisosVigentes(): Resultado<List<AvisoVigente>> = consultarConPlazo(
        "avisos_vigentes", TTL_AVISOS_MS,
        { supabase.get("aviso_vigente", mapOf(
            "select" to "id,tipo,anio,numero,mapa,nivel,titulo,tema,descripcion,inicio,fin,en_curso,departamentos,url,icono,texto_dia,anclas,geojson",
            "order" to "nivel", "limit" to "300")) },
        { lista<AvisoVigente>(it) },
    )

    /** Ultima lectura de cada estacion de rio de ANA (caudal_actual; 10 min). */
    suspend fun caudales(): Resultado<List<CaudalActual>> = consultarConPlazo(
        "caudales", TTL_RIOS_MS,
        { supabase.get("caudal_actual", mapOf(
            "select" to "estacion,rio,departamento,fecha,hora,valor,unidad,umbral_alerta,umbral_emergencia,tendencia,estado,lat,lon",
            "order" to "estacion", "limit" to "1000")) },
        { lista<CaudalActual>(it) },
    )

    /** Rios vigilados con cauce y afluentes (rio_vigilado_mapa; hoy solo el Mashcon; 10 min). */
    suspend fun riosVigilados(): Resultado<List<RioVigiladoMapa>> = consultarConPlazo(
        "rios_vigilados", TTL_RIOS_MS,
        { supabase.get("rio_vigilado_mapa", mapOf(
            "select" to "id,nombre,departamento,estacion_ana,rio_ana,centro_lat,centro_lon,zoom,cauce,afluentes,fuentes", "limit" to "20")) },
        { lista<RioVigiladoMapa>(it) },
    )

    /** Zonas que un rio vigilado podria afectar (rio_zona_mapa; 10 min). */
    suspend fun zonasRioVigilado(): Resultado<List<RioZonaMapa>> = consultarConPlazo(
        "zonas_rio_vigilado", TTL_RIOS_MS,
        { supabase.get("rio_zona_mapa", mapOf(
            "select" to "clave,rio,tipo,subtipo,orden,nombre,texto,fuente,fuente_url,licencia,atribucion,metodo,fecha_fuente,area_km2,geojson",
            "order" to "orden", "limit" to "200")) },
        { lista<RioZonaMapa>(it) },
    )

    /** Senales de hoy de los rios vigilados (rio_senal; 5 min). */
    suspend fun senalesRioVigilado(): Resultado<List<RioSenal>> = consultarConPlazo(
        "senales_rio_vigilado", TTL_AVISOS_MS,
        { supabase.get("rio_senal", mapOf("select" to "rio,avisos_lluvia,lluvia_cuenca,avisos_hidro", "limit" to "20")) },
        { lista<RioSenal>(it) },
    )

    /** Los ~100 rios del pais con el trazo de ~50 m (rio_cauce_mapa.cauce_lejos, ~750 KB; 10 min). */
    suspend fun caucesPais(): Resultado<List<RioCauceMapa>> = consultarConPlazo(
        "cauces_pais", TTL_RIOS_MS,
        { supabase.get("rio_cauce_mapa", mapOf(
            "select" to "rio_ana,rio,nombre,departamento,estaciones,km,fuente,fuente_url,licencia,vigilado,cauce_lejos",
            "order" to "rio_ana", "limit" to "300")) },
        { lista<RioCauceMapa>(it) },
    )

    /** Trazo fino (~6 m) de un rio, solo cuando esta a la vista de cerca (10 min). */
    suspend fun cauceFino(rioAna: String): Resultado<RioCauceDetalle?> = consultarConPlazo(
        "cauce_fino:$rioAna", TTL_RIOS_MS,
        { supabase.get("rio_cauce_mapa", mapOf("select" to "rio_ana,cauce", "rio_ana" to "eq.$rioAna", "limit" to "1")) },
        { lista<RioCauceDetalle>(it).firstOrNull() },
    )

    /** Avisos hidrologicos vigentes por rio con trazo (rio_cauce_senal; 5 min). */
    suspend fun senalesCauces(): Resultado<List<RioCauceSenal>> = consultarConPlazo(
        "senales_cauces", TTL_AVISOS_MS,
        { supabase.get("rio_cauce_senal", mapOf("select" to "rio_ana,lecturas,avisos_hidro", "limit" to "300")) },
        { lista<RioCauceSenal>(it) },
    )

    /** Zonas estimadas con el relieve de los rios pedidos (rio_cauce_zona_mapa), nunca el pais entero (10 min). */
    suspend fun zonasCauces(riosAna: List<String>): Resultado<List<RioCauceZonaMapa>> {
        val ids = riosAna.filter { it.isNotBlank() }.distinct().sorted()
        if (ids.isEmpty()) return Resultado(emptyList(), System.currentTimeMillis(), false)
        val enLista = ids.joinToString(",") { "\"" + it.replace("\"", "") + "\"" }
        return consultarConPlazo(
            "zonas_cauces:${ids.joinToString("|")}", TTL_RIOS_MS,
            { supabase.get("rio_cauce_zona_mapa", mapOf(
                "select" to "clave,rio_ana,subtipo,area_km2,metodo,fuente,licencia,nota,atribucion,geojson",
                "rio_ana" to "in.($enLista)", "order" to "clave", "limit" to "200")) },
            { lista<RioCauceZonaMapa>(it) },
        )
    }

    /** Estaciones de SENAMHI dentro de la caja (tabla estacion; 10 min). */
    suspend fun estaciones(caja: Caja): Resultado<List<EstacionSenamhi>> = consultarConPlazo(
        "estaciones_mapa:${caja.oeste},${caja.sur},${caja.este},${caja.norte}", TTL_RIOS_MS,
        { supabase.get("estacion", mapOf(
            "select" to "cod,nombre,tipo,estado,departamento,lat,lon",
            "lat" to "gte.${caja.sur}", "and" to "(lat.lte.${caja.norte},lon.gte.${caja.oeste},lon.lte.${caja.este})",
            "order" to "cod", "limit" to "1000")) },
        { lista<EstacionSenamhi>(it) },
    )

    /** Puntos de "A donde acudir" para el mapa: la misma consulta por caja, con plazo de 10 min. */
    suspend fun puntosAcudirMapa(caja: Caja): Resultado<List<PuntoAcudir>> = consultarConPlazo(
        "acudir:${caja.oeste},${caja.sur},${caja.este},${caja.norte}", TTL_RIOS_MS,
        { supabase.get("punto_acudir", mapOf(
            "select" to "clave,tipo,nombre,categoria,atiende_24h,direccion,distrito,provincia,departamento,telefono,lat,lon,fuente,fuente_url,atribucion,actualizado",
            "lat" to "gte.${caja.sur}", "and" to "(lat.lte.${caja.norte},lon.gte.${caja.oeste},lon.lte.${caja.este})",
            "order" to "clave", "limit" to "3000")) },
        { lista<PuntoAcudir>(it) },
    )

    suspend fun limpiarCache() = cache.limpiar()

    // ---- comunidad (reportes ciudadanos) y cuenta ----

    /**
     * Escrituras con sesion (crear reporte, votar, comentar, foto, mis reportes, perfil). Lo pone el
     * Contenedor (SifecApp) al arrancar; null si la app no tiene Supabase configurado.
     */
    var comunidad: ComunidadSupabase? = null
    private fun comunidadOFalla(): ComunidadSupabase = comunidad ?: throw ErrorConsulta("Falta la dirección o la llave pública de Supabase")

    /**
     * Reportes vigentes dentro de la caja (la RLS solo entrega los que no vencieron; sin la columna
     * autor). Los mas nuevos primero; el orden por confianza y cercania lo hace dominio/Comunidad.kt.
     * La pestana Comunidad pide Comunidad.CAJA_PERU; el mapa, su vista. Siempre va a la red; la copia
     * en disco solo sirve sin conexion (deCache = true).
     */
    suspend fun reportesVigentes(caja: Caja): Resultado<List<ReporteVigente>> = consultar(
        "reportes:${caja.oeste},${caja.sur},${caja.este},${caja.norte}",
        { supabase.get("report", mapOf(
            "select" to ComunidadSupabase.COLS_REPORTE,
            "lat" to "gte.${caja.sur}", "and" to "(lat.lte.${caja.norte},lon.gte.${caja.oeste},lon.lte.${caja.este})",
            "order" to "creado_en.desc", "limit" to "500")) },
        { lista<ReporteVigente>(it) },
    )

    /** Un reporte por id; null si no existe o ya vencio (la RLS no lo entrega). */
    suspend fun reporte(id: String): Resultado<ReporteVigente?> = consultar(
        "reporte:$id",
        { supabase.get("report", mapOf("select" to ComunidadSupabase.COLS_REPORTE, "id" to "eq.$id", "limit" to "1")) },
        { lista<ReporteVigente>(it).firstOrNull() },
    )

    /** Comentarios de un reporte (lectura publica, sin autor), del mas viejo al mas nuevo. */
    suspend fun comentarios(reportId: String): Resultado<List<ComentarioReporte>> = consultar(
        "comentarios:$reportId",
        { supabase.get("comentario", mapOf(
            "select" to ComunidadSupabase.COLS_COMENTARIO, "report_id" to "eq.$reportId", "order" to "creado_en", "limit" to "200")) },
        { lista<ComentarioReporte>(it) },
    )

    suspend fun misReportes(): List<ReporteVigente> = comunidadOFalla().misReportes()

    suspend fun crearReporte(tipo: String, subtipo: String?, descripcion: String?, fotoUrl: String?, lat: Double, lon: Double): ReporteVigente =
        comunidadOFalla().crearReporte(tipo, subtipo, descripcion, fotoUrl, lat, lon)

    /** valor 1 o -1; null quita el voto. */
    suspend fun votar(reportId: String, valor: Int?) = comunidadOFalla().votar(reportId, valor)

    suspend fun comentar(reportId: String, texto: String): ComentarioReporte = comunidadOFalla().comentar(reportId, texto)

    /** Sube un JPEG (ya reducido a 1280 px) al bucket "reportes" en la carpeta del uid; devuelve la URL publica. */
    suspend fun subirFoto(jpeg: ByteArray, uid: String): String = comunidadOFalla().subirFoto(jpeg, uid)

    suspend fun perfilPropio(): PerfilPropio? = comunidadOFalla().perfil()

    suspend fun misVotos(ids: List<String>): Map<String, Int> = comunidadOFalla().misVotos(ids)

    // ---- capas del mapa nativo que faltaban frente a la web (ui/mapa) ----

    /** Pronostico de todas las localidades (hoy, manana y pasado; ~700 filas) para la capa del mapa; 30 min. */
    suspend fun pronosticoMapa(): Resultado<List<PronosticoLocalidad>> = consultarConPlazo(
        "pronostico_mapa", 30 * 60_000L,
        { supabase.get("pronostico_vigente", mapOf(
            "select" to "codigo,nombre,departamento,lat,lon,fecha,emision,tmax,tmin,texto,tipo,posible,por,lluvia_segura,granizo,intensidad,momento,cielo,url",
            "order" to "codigo,fecha", "limit" to "3000")) },
        { lista<PronosticoLocalidad>(it) },
    )

    /** Estado del nowcasting por horizonte (nowcast_estado). Siempre a la red: si falla, el error se muestra. */
    suspend fun nowcastEstado(): Resultado<List<NowcastEstado>> = consultar(
        "nowcast_estado",
        { supabase.get("nowcast_estado", mapOf(
            "select" to "horizonte_min,fichero,emision,valido_desde,valido_hasta,manchas,ts_captura,vence_en,vigente", "limit" to "10")) },
        { lista<NowcastEstado>(it) },
    )

    /** Manchas vigentes de un horizonte (nowcast_vigente, 0 | 60 | 120 min); vacio si SENAMHI no publica hace mas de 30 min. */
    suspend fun nowcastVigente(horizonteMin: Int): Resultado<List<NowcastMancha>> = consultar(
        "nowcast_vigente:$horizonteMin",
        { supabase.get("nowcast_vigente", mapOf(
            "select" to "horizonte_min,nivel,emision,valido_desde,valido_hasta,geojson", "horizonte_min" to "eq.$horizonteMin", "limit" to "10")) },
        { lista<NowcastMancha>(it) },
    )

    /** Lluvia de la ultima hora en las estaciones automaticas de SENAMHI (lluvia_senamhi_actual; 5 min). */
    suspend fun lluviaAhora(): Resultado<List<LluviaSenamhiActual>> = consultarConPlazo(
        "lluvia_ahora", TTL_AVISOS_MS,
        { supabase.get("lluvia_senamhi_actual", mapOf(
            "select" to "clave,nombre,departamento,provincia,distrito,pp_1h,umbral_1h,pp_6h,umbral_6h,medido_en,lat,lon", "limit" to "2000")) },
        { lista<LluviaSenamhiActual>(it) },
    )

    /** Desbordes y danos pasados de los rios vigilados (rio_incidente), del mas nuevo al mas viejo; 60 min. */
    suspend fun incidentesRio(): Resultado<List<RioIncidente>> = consultarConPlazo(
        "incidentes_rio", 60 * 60_000L,
        { supabase.get("rio_incidente", mapOf(
            "select" to "id,rio,fecha,fecha_texto,tipo,titulo,lugar,detalle,precision,precision_texto,caudal_m3s,fuente_tipo,fuente,fuente_url,otras_fuentes,lat,lon",
            "order" to "fecha.desc.nullslast", "limit" to "500")) },
        { lista<RioIncidente>(it) },
    )

    /** Mapa de un evento El Nino y un trimestre (tabla mapa, variable FEN; ~750 KB); un dia en disco (no cambia). */
    suspend fun mapaFen(periodo: String, trimestre: String): Resultado<MapaFen?> = consultarConPlazo(
        "fen:$periodo|$trimestre", 24 * 60 * 60_000L,
        { supabase.get("mapa", mapOf(
            "select" to "titulo,periodo,trimestre,meses,fuente,geojson", "variable" to "eq.FEN",
            "periodo" to "eq.$periodo", "trimestre" to "eq.$trimestre", "limit" to "1")) },
        { lista<MapaFen>(it).firstOrNull() },
    )

    /** Franja de atencion referencial de un rio del pais (rio_cauce_mapa.franja); 10 min. */
    suspend fun franjaRio(rioAna: String): Resultado<RioCauceFranja?> = consultarConPlazo(
        "franja:$rioAna", TTL_RIOS_MS,
        { supabase.get("rio_cauce_mapa", mapOf("select" to "rio_ana,ancho_m,franja", "rio_ana" to "eq.$rioAna", "limit" to "1")) },
        { lista<RioCauceFranja>(it).firstOrNull() },
    )

    /** Latido de una ingesta (p. ej. lluvia_nacional: trae las fechas de las capas WMS de SENAMHI); 10 min. */
    suspend fun latido(servicio: String): Resultado<Latido?> = consultarConPlazo(
        "latido:$servicio", TTL_RIOS_MS,
        { supabase.get("latido", mapOf("select" to "servicio,ts,resumen", "servicio" to "eq.$servicio", "limit" to "1")) },
        { lista<Latido>(it).firstOrNull() },
    )

    /**
     * Hora del dato mas reciente de la lluvia por satelite (NASA GIBS, IMERG 30 min), como la web: un
     * HEAD a "default" trae Layer-Time-Actual, pero a veces anuncia un paso que aun no publico (404):
     * se confirma con otro HEAD y, si falta, se retrocede de a 30 min hasta 6 veces. null si no hay
     * hora confirmada (la capa usa "default"). Lanza ErrorConsulta si GIBS no responde.
     */
    suspend fun horaSatelite(): String? = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        val base = pe.simpac.app.dominio.Lluvia.GIBS
        val matriz = pe.simpac.app.dominio.Lluvia.GIBS_MATRIZ
        val celda = "5/16/9"   // una celda (z/y/x) sobre el Peru
        fun head(url: String): okhttp3.Response = Http.cliente.newCall(
            okhttp3.Request.Builder().url(url).head().header("User-Agent", "SIFEC-Android").build(),
        ).execute()
        val anunciada: Long = try {
            head("$base/default/$matriz/$celda.png").use { r ->
                if (!r.isSuccessful) throw ErrorConsulta("GIBS respondió ${r.code}")
                pe.simpac.app.dominio.Tiempo.parsearMs(r.header("Layer-Time-Actual")) ?: return@withContext null
            }
        } catch (e: java.io.IOException) {
            throw if (e is ErrorConsulta) e else ErrorConsulta("No se pudo conectar con gibs.earthdata.nasa.gov", e)
        }
        for (i in 0 until 6) {
            val ms = anunciada - i * 30 * 60_000L
            val hora = java.time.Instant.ofEpochMilli(ms).toString().replace(".000Z", "Z")
            val existe = try { head("$base/$hora/$matriz/$celda.png").use { it.isSuccessful } } catch (_: java.io.IOException) { false }
            if (existe) return@withContext hora
        }
        null
    }

    /** GET de prueba de una imagen WMS de SENAMHI (una celda del pais): false si el servidor no responde. */
    suspend fun pruebaWms(url: String): Boolean = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        try {
            Http.cliente.newCall(okhttp3.Request.Builder().url(url).get().header("User-Agent", "SIFEC-Android").build()).execute().use { r ->
                r.isSuccessful && (r.header("Content-Type") ?: "").startsWith("image/")
            }
        } catch (_: java.io.IOException) { false }
    }
}
