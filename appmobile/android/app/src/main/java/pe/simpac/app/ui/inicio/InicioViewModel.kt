package pe.simpac.app.ui.inicio

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import pe.simpac.app.SifecApp
import pe.simpac.app.data.AlertaActual
import pe.simpac.app.data.ComunicadoEnfen
import pe.simpac.app.data.PronosticoVigente
import pe.simpac.app.data.Resultado
import pe.simpac.app.data.RioCauceSenal
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

/** Los rios con trazo del departamento: sus senales de hoy (rio_cauce_senal) y el nombre de cada uno (rio_cauce_mapa). */
private data class CaucesZona(val senales: List<RioCauceSenal>, val nombres: Map<String, String>)

/** Todo lo que pinta la pantalla Inicio. Es un dato puro: la prueba de Compose lo arma a mano. */
data class EstadoInicio(
    val cargando: Boolean = true,
    val error: String? = null,                  // error total: ni titular ni alertas (con reintentar)
    val explicarGps: Boolean = false,           // mostrar la pantalla que explica el permiso
    val leyendoAjustes: Boolean = false,        // aun no se leyeron los ajustes: no se sabe si toca explicar el GPS, asi que no se dibuja nada (ni el esqueleto)
    val departamento: String = Departamentos.POR_DEFECTO.nombre,
    val porGps: Boolean = false,
    val ubicacionApagada: Boolean = false,      // "Usar mi ubicacion" con permiso, pero el interruptor de ubicacion del telefono esta apagado: se muestra el departamento guardado
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
) {
    /**
     * Ya hay algo que mostrar (titular o alertas leidas): con datos, una recarga no vuelve al esqueleto
     * (va con "tirar para actualizar") y un error de recarga se avisa abajo sin tapar la pantalla.
     */
    val tieneDatos: Boolean get() = titular != null || alertasLeidas
}

class InicioViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SifecApp).contenedor
    private val repo = contenedor.repositorio
    private val ajustes = contenedor.ajustes

    // Arranca "leyendo ajustes": hasta saber si hay que explicar el GPS no se dibuja el esqueleto, asi la
    // primera apertura no muestra la silueta de los datos para despues cruzar a "Tu ubicacion".
    private val _estado = MutableStateFlow(EstadoInicio(leyendoAjustes = true))
    val estado: StateFlow<EstadoInicio> = _estado

    init { cargar() }

    /** La persona ya vio la explicacion del GPS y decidio (usar = acepto el permiso). */
    fun gpsDecidido(usar: Boolean) {
        viewModelScope.launch {
            ajustes.guardarGpsExplicado(true)
            ajustes.guardarUsarGps(usar)
            // la explicacion se va de inmediato: mientras se lee la zona se ve el esqueleto, no la pantalla del permiso
            _estado.value = _estado.value.copy(explicarGps = false)
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
            // ya se sabe que no toca explicar el GPS: recien ahora se ve el esqueleto (solo pasa en el primer cargado)
            if (_estado.value.leyendoAjustes) _estado.value = _estado.value.copy(leyendoAjustes = false)
            val app = getApplication<Application>()
            // paraZona: si la primera posicion es peor que 2 km (solo red celular) espera unos segundos por
            // una mejor antes de decidir el departamento; con una precisa o sin permiso preciso no espera
            val usarGps = conf.usarGps && Ubicacion.tienePermiso(app)
            // con el interruptor de ubicacion del telefono apagado no habra posicion: la pantalla lo dice y ofrece "Activar"
            val ubicacionApagada = usarGps && !Ubicacion.ubicacionActiva(app)
            val posicion: Posicion? = (if (usarGps && !ubicacionApagada) Ubicacion.paraZona(app) else null)?.takeIf { Ubicacion.enPeru(it) }
            val departamento = posicion?.let { repo.departamentoDe(it.lat, it.lon) } ?: conf.departamento
            val centro = posicion ?: Departamentos.porNombre(departamento)?.let { Posicion(it.lat, it.lon) }
                ?: Posicion(Departamentos.POR_DEFECTO.lat, Departamentos.POR_DEFECTO.lon)
            val nuevo = armar(departamento, posicion != null, ubicacionApagada, centro, conf.apiUrl)
            val actual = _estado.value
            // Si la recarga de la misma zona falla con datos ya en pantalla, se conservan y el error va
            // aparte (la pantalla lo avisa abajo con "Reintentar"); con otra zona si se muestra el error.
            _estado.value = if (nuevo.error != null && actual.tieneDatos && actual.departamento == nuevo.departamento) {
                actual.copy(cargando = false, error = nuevo.error)
            } else {
                nuevo
            }
        }
    }

    private suspend fun armar(departamento: String, porGps: Boolean, ubicacionApagada: Boolean, centro: Posicion, apiUrl: String): EstadoInicio = coroutineScope {
        val tTitular = async { runCatching { repo.titular(departamento) } }
        val tAlertas = async { runCatching { repo.alertas() } }
        val tPronostico = async { runCatching { repo.pronostico(Geo.cajaAlrededor(centro.lat, centro.lon, 80.0)) } }
        // rios con trazo del departamento (rio_cauce_senal) con su nombre
        val tRios = async {
            runCatching {
                val rios = repo.riosDelDepartamento(departamento)
                val senales = repo.senalesRios(rios.dato.map { it.rio_ana })
                val nombres = rios.dato.associate { it.rio_ana to (it.nombre ?: it.rio_ana) }
                Resultado(CaucesZona(senales.dato, nombres), senales.obtenidoEn, rios.deCache || senales.deCache)
            }
        }
        // el rio vigilado de la zona (el Mashcon, que no tiene fila en rio_cauce) con la lectura de su estacion de ANA
        // y las senales de su cuenca (rio_senal: avisos de lluvias, lluvia medida); son las consultas del mapa, con su cache
        val tVigilados = async { runCatching { repo.riosVigilados() } }
        val tSenalesVig = async { runCatching { repo.senalesRioVigilado() } }
        val tCaudales = async { runCatching { repo.caudales() } }
        val tSnapshot = async { runCatching { repo.snapshot(apiUrl) } }

        val rTitular = tTitular.await()
        val rAlertas = tAlertas.await()
        val rPronostico = tPronostico.await()
        val rRios = tRios.await()
        val rVigilados = tVigilados.await()
        val rSenalesVig = tSenalesVig.await()
        val rCaudales = tCaudales.await()
        val rSnapshot = tSnapshot.await()

        val titular = rTitular.getOrNull()
        val alertas = rAlertas.getOrNull()
        if (titular == null && alertas == null) {
            val motivo = rTitular.exceptionOrNull()?.message ?: rAlertas.exceptionOrNull()?.message ?: "sin respuesta"
            return@coroutineScope EstadoInicio(cargando = false, error = "No se pudo leer SIFEC ($motivo). Revisa tu conexión.", departamento = departamento, porGps = porGps, ubicacionApagada = ubicacionApagada)
        }

        val avisos = mutableListOf<String>()
        rTitular.exceptionOrNull()?.let { avisos += "No se pudo leer el titular de la zona (${it.message})." }
        rAlertas.exceptionOrNull()?.let { avisos += "No se pudieron leer las alertas (${it.message})." }
        rPronostico.exceptionOrNull()?.let { avisos += "No se pudo leer el pronóstico de SENAMHI." }
        rRios.exceptionOrNull()?.let { avisos += "No se pudieron leer los ríos del departamento." }
        // sin las senales o la lectura del vigilado el chip lo diria sin su cuenca o sin su medicion: se avisa (solo donde hay uno)
        val vigilados = rVigilados.getOrNull()?.dato?.let { Rios.vigiladosDe(it, departamento) } ?: emptyList()
        if (vigilados.isNotEmpty() && (rSenalesVig.isFailure || rCaudales.isFailure)) {
            avisos += "No se pudieron leer las señales de hoy del " + vigilados.joinToString(" y del ") { (it.nombre ?: it.id).replaceFirstChar { c -> c.lowercase() } } + "."
        }
        val errorApi = rSnapshot.exceptionOrNull()?.let { "Sin contexto El Niño: la API de SIFEC no respondió (${it.message}). Dirección: $apiUrl" }

        val datoTitular = titular?.dato
        val alertasZona = alertas?.let { Alertas.ordenar(Alertas.deZona(it.dato, departamento)) } ?: emptyList()
        val cauces = rRios.getOrNull()?.dato
        val rios = Rios.resumirZona(
            departamento, vigilados, rSenalesVig.getOrNull()?.dato ?: emptyList(), rCaudales.getOrNull()?.dato ?: emptyList(),
            cauces?.senales ?: emptyList(), cauces?.nombres ?: emptyMap(),
        )
        val pron = rPronostico.getOrNull()?.dato ?: emptyList()
        val codigo = Pronostico.localidadCercana(pron, centro.lat, centro.lon)
        val franja = Pronostico.franja(pron, codigo)
        val snapshot = rSnapshot.getOrNull()?.dato

        val generadoMs = Tiempo.parsearMs(datoTitular?.generado_en)
        val revisadoMs = Tiempo.parsearMs(datoTitular?.revisado_en) ?: generadoMs
        val fuentes = mutableListOf<Fuente>()
        if (datoTitular != null) fuentes += Fuente("Titular de SIFEC (${if (datoTitular.origen == "llm") "redactado por un modelo y validado" else "por reglas"})", Tiempo.horaConHace(generadoMs))
        alertas?.let { r ->
            val masReciente = alertasZona.mapNotNull { Tiempo.parsearMs(it.ts) }.maxOrNull()
            fuentes += Fuente("Alertas oficiales (SENAMHI y ANA)", if (masReciente != null) Tiempo.horaConHace(masReciente) else "leídas " + Tiempo.horaCorta(r.obtenidoEn))
        }
        if (franja.isNotEmpty()) fuentes += Fuente("Pronóstico de SENAMHI, localidad ${franja.first().nombre ?: codigo}", "emisión " + Tiempo.fechaLarga(franja.first().emision))
        snapshot?.enfen?.let { fuentes += Fuente("ENFEN, comunicado ${it.numero}-${it.anio}", Tiempo.fechaLarga(it.fecha)) }
        val obtenidoRios = listOfNotNull(rRios.getOrNull()?.obtenidoEn, rSenalesVig.getOrNull()?.obtenidoEn, rCaudales.getOrNull()?.obtenidoEn).minOrNull()
        if (rios.isNotEmpty() && obtenidoRios != null) fuentes += Fuente("Ríos con estación (ANA y SENAMHI)", "leídos " + Tiempo.horaCorta(obtenidoRios))

        val deCache = listOfNotNull(
            titular?.deCache, alertas?.deCache, rPronostico.getOrNull()?.deCache, rRios.getOrNull()?.deCache,
            rVigilados.getOrNull()?.deCache, rSenalesVig.getOrNull()?.deCache, rCaudales.getOrNull()?.deCache, rSnapshot.getOrNull()?.deCache,
        ).any { it }
        val obtenidoEn = listOfNotNull(titular?.obtenidoEn, alertas?.obtenidoEn).minOrNull()

        EstadoInicio(
            cargando = false,
            departamento = departamento,
            porGps = porGps,
            ubicacionApagada = ubicacionApagada,
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
