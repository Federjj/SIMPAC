package pe.simpac.app.ui.inicio

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.AlertaActual
import pe.simpac.app.data.ComunicadoEnfen
import pe.simpac.app.data.PronosticoVigente
import pe.simpac.app.data.Resultado
import pe.simpac.app.data.TitularZona
import pe.simpac.app.dominio.Alertas
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.Geo
import pe.simpac.app.dominio.Nivel
import pe.simpac.app.dominio.Pronostico
import pe.simpac.app.dominio.RioResumen
import pe.simpac.app.dominio.Rios
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ubicacion.Posicion
import pe.simpac.app.ubicacion.Ubicacion

/** Una fuente con su hora, para el pie de la pantalla. */
data class Fuente(val nombre: String, val hora: String)

/** Todo lo que pinta la pantalla Inicio. Es un dato puro: la prueba de Compose lo arma a mano. */
data class EstadoInicio(
    val cargando: Boolean = true,
    val error: String? = null,                  // error total: ni titular ni alertas (con reintentar)
    val explicarGps: Boolean = false,           // mostrar la pantalla que explica el permiso
    val departamento: String = Departamentos.POR_DEFECTO.nombre,
    val porGps: Boolean = false,
    val nivel: Nivel = Nivel.SIN_DATO,
    val titular: TitularZona? = null,
    val titularGeneradoMs: Long? = null,
    val titularRevisadoMs: Long? = null,
    val alertasZona: List<AlertaActual> = emptyList(),
    val alertasLeidas: Boolean = false,         // alerta_actual respondio (si no, no se dice "sin alertas")
    val rios: List<RioResumen> = emptyList(),
    val rioDestacado: RioResumen? = null,
    val enfen: ComunicadoEnfen? = null,
    val errorApi: String? = null,
    val pronostico: List<PronosticoVigente> = emptyList(),
    val localidad: String? = null,
    val fuentes: List<Fuente> = emptyList(),
    val obtenidoEn: Long? = null,
    val deCache: Boolean = false,               // alguna consulta salio de la copia en disco
    val desactualizado: Boolean = false,        // el titular tiene mas de 3 h sin revisar
    val avisos: List<String> = emptyList(),     // consultas parciales que fallaron
    val centroLat: Double? = null,              // tu punto (GPS) o el centro del departamento: lo usa "Ver el rio en el mapa"
    val centroLon: Double? = null,
)

class InicioViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val repo = contenedor.repositorio
    private val ajustes = contenedor.ajustes

    private val _estado = MutableStateFlow(EstadoInicio())
    val estado: StateFlow<EstadoInicio> = _estado

    init { cargar() }

    /** La persona ya vio la explicacion del GPS y decidio (usar = acepto el permiso). */
    fun gpsDecidido(usar: Boolean) {
        viewModelScope.launch {
            ajustes.guardarGpsExplicado(true)
            ajustes.guardarUsarGps(usar)
            cargar()
        }
    }

    fun elegirDepartamento(nombre: String) {
        viewModelScope.launch {
            ajustes.guardarDepartamento(nombre)
            ajustes.guardarUsarGps(false)
            cargar()
        }
    }

    fun cargar() {
        viewModelScope.launch {
            _estado.value = _estado.value.copy(cargando = true, error = null)
            val conf = ajustes.actual()
            if (!conf.gpsExplicado) {
                _estado.value = EstadoInicio(cargando = false, explicarGps = true, departamento = conf.departamento)
                return@launch
            }
            val app = getApplication<Application>()
            val posicion: Posicion? = (if (conf.usarGps && Ubicacion.tienePermiso(app)) Ubicacion.actual(app) else null)?.takeIf { Ubicacion.enPeru(it) }
            val departamento = posicion?.let { repo.departamentoDe(it.lat, it.lon) } ?: conf.departamento
            val centro = posicion ?: Departamentos.porNombre(departamento)?.let { Posicion(it.lat, it.lon) }
                ?: Posicion(Departamentos.POR_DEFECTO.lat, Departamentos.POR_DEFECTO.lon)
            _estado.value = armar(departamento, posicion != null, centro, conf.apiUrl)
        }
    }

    private suspend fun armar(departamento: String, porGps: Boolean, centro: Posicion, apiUrl: String): EstadoInicio = coroutineScope {
        val tTitular = async { runCatching { repo.titular(departamento) } }
        val tAlertas = async { runCatching { repo.alertas() } }
        val tPronostico = async { runCatching { repo.pronostico(Geo.cajaAlrededor(centro.lat, centro.lon, 80.0)) } }
        val tRios = async {
            runCatching {
                val rios = repo.riosDelDepartamento(departamento)
                val senales = repo.senalesRios(rios.dato.map { it.rio_ana })
                val nombres = rios.dato.associate { it.rio_ana to (it.nombre ?: it.rio_ana) }
                Resultado(senales.dato.map { Rios.resumir(it, nombres[it.rio_ana] ?: it.rio_ana) }, senales.obtenidoEn, rios.deCache || senales.deCache)
            }
        }
        val tSnapshot = async { runCatching { repo.snapshot(apiUrl) } }

        val rTitular = tTitular.await()
        val rAlertas = tAlertas.await()
        val rPronostico = tPronostico.await()
        val rRios = tRios.await()
        val rSnapshot = tSnapshot.await()

        val titular = rTitular.getOrNull()
        val alertas = rAlertas.getOrNull()
        if (titular == null && alertas == null) {
            val motivo = rTitular.exceptionOrNull()?.message ?: rAlertas.exceptionOrNull()?.message ?: "sin respuesta"
            return@coroutineScope EstadoInicio(cargando = false, error = "No se pudo leer SIMPAC ($motivo). Revisa tu conexión.", departamento = departamento, porGps = porGps)
        }

        val avisos = mutableListOf<String>()
        rTitular.exceptionOrNull()?.let { avisos += "No se pudo leer el titular de la zona (${it.message})." }
        rAlertas.exceptionOrNull()?.let { avisos += "No se pudieron leer las alertas (${it.message})." }
        rPronostico.exceptionOrNull()?.let { avisos += "No se pudo leer el pronóstico de SENAMHI." }
        rRios.exceptionOrNull()?.let { avisos += "No se pudieron leer los ríos del departamento." }
        val errorApi = rSnapshot.exceptionOrNull()?.let { "Sin contexto El Niño: la API de SIMPAC no respondió (${it.message}). Dirección: $apiUrl" }

        val datoTitular = titular?.dato
        val alertasZona = alertas?.let { Alertas.ordenar(Alertas.deZona(it.dato, departamento)) } ?: emptyList()
        val rios = rRios.getOrNull()?.dato ?: emptyList()
        val pron = rPronostico.getOrNull()?.dato ?: emptyList()
        val codigo = Pronostico.localidadCercana(pron, centro.lat, centro.lon)
        val franja = Pronostico.franja(pron, codigo)
        val snapshot = rSnapshot.getOrNull()?.dato

        val generadoMs = Tiempo.parsearMs(datoTitular?.generado_en)
        val revisadoMs = Tiempo.parsearMs(datoTitular?.revisado_en) ?: generadoMs
        val fuentes = mutableListOf<Fuente>()
        if (datoTitular != null) fuentes += Fuente("Titular de SIMPAC (${if (datoTitular.origen == "llm") "redactado por un modelo y validado" else "por reglas"})", Tiempo.horaConHace(generadoMs))
        alertas?.let { r ->
            val masReciente = alertasZona.mapNotNull { Tiempo.parsearMs(it.ts) }.maxOrNull()
            fuentes += Fuente("Alertas oficiales (SENAMHI y ANA)", if (masReciente != null) Tiempo.horaConHace(masReciente) else "leídas " + Tiempo.horaCorta(r.obtenidoEn))
        }
        if (franja.isNotEmpty()) fuentes += Fuente("Pronóstico de SENAMHI, localidad ${franja.first().nombre ?: codigo}", "emisión " + Tiempo.fechaLarga(franja.first().emision))
        snapshot?.enfen?.let { fuentes += Fuente("ENFEN, comunicado ${it.numero}-${it.anio}", Tiempo.fechaLarga(it.fecha)) }
        rRios.getOrNull()?.let { if (rios.isNotEmpty()) fuentes += Fuente("Ríos con estación (ANA y SENAMHI)", "leídos " + Tiempo.horaCorta(it.obtenidoEn)) }

        val deCache = listOfNotNull(titular?.deCache, alertas?.deCache, rPronostico.getOrNull()?.deCache, rRios.getOrNull()?.deCache, rSnapshot.getOrNull()?.deCache).any { it }
        val obtenidoEn = listOfNotNull(titular?.obtenidoEn, alertas?.obtenidoEn).minOrNull()

        EstadoInicio(
            cargando = false,
            departamento = departamento,
            porGps = porGps,
            nivel = if (datoTitular != null) Nivel.desde(datoTitular.nivel) else Nivel.SIN_DATO,
            titular = datoTitular,
            titularGeneradoMs = generadoMs,
            titularRevisadoMs = revisadoMs,
            alertasZona = alertasZona,
            alertasLeidas = alertas != null,
            rios = rios,
            rioDestacado = Rios.destacado(rios),
            enfen = snapshot?.enfen,
            errorApi = errorApi,
            pronostico = franja,
            localidad = franja.firstOrNull()?.nombre,
            fuentes = fuentes,
            obtenidoEn = obtenidoEn,
            deCache = deCache,
            desactualizado = datoTitular != null && Tiempo.desactualizado(revisadoMs),
            avisos = avisos,
            centroLat = centro.lat,
            centroLon = centro.lon,
        )
    }
}
