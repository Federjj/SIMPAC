package pe.simpac.app.data

import kotlinx.serialization.builtins.ListSerializer
import pe.simpac.app.dominio.Caja
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.Geo

/**
 * Todas las consultas de la app en un solo lugar. Cada una pide a la red y guarda la respuesta en
 * disco; si la red falla y hay copia, devuelve la copia con deCache = true y la hora en que se guardo.
 * Si no hay ni red ni copia, lanza ErrorConsulta con un mensaje para la pantalla.
 */
class Repositorio(
    private val supabase: ClienteSupabase,
    private val api: ClienteApi,
    private val cache: CacheDisco,
) {
    private suspend fun <T> consultar(clave: String, pedir: suspend () -> String, convertir: (String) -> T): Resultado<T> {
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

    suspend fun limpiarCache() = cache.limpiar()
}
