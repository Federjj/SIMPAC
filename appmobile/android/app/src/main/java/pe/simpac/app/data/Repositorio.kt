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
        JsonSimpac.decodeFromString(ListSerializer(kotlinx.serialization.serializer<T>()), cuerpo)

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

    /** Snapshot de la API de SIMPAC (contexto El Nino, resumen, alertas con 'oficial', caudales). */
    suspend fun snapshot(apiUrl: String): Resultado<Snapshot> = consultar(
        "snapshot:$apiUrl",
        { api.snapshot(apiUrl) },
        { JsonSimpac.decodeFromString(Snapshot.serializer(), it) },
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
}
