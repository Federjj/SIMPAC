package pe.simpac.app.ui.mapa

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.AvisoHidro
import pe.simpac.app.data.AvisoVigente
import pe.simpac.app.data.CaudalActual
import pe.simpac.app.data.ErrorConsulta
import pe.simpac.app.data.EstacionSenamhi
import pe.simpac.app.data.LluviaSenamhiActual
import pe.simpac.app.data.NowcastEstado
import pe.simpac.app.data.NowcastMancha
import pe.simpac.app.data.PronosticoLocalidad
import pe.simpac.app.data.PuntoAcudir
import pe.simpac.app.data.ReporteVigente
import pe.simpac.app.data.Resultado
import pe.simpac.app.data.RioCauceSenal
import pe.simpac.app.data.RioCauceZonaMapa
import pe.simpac.app.data.RioIncidente
import pe.simpac.app.data.RioSenal
import pe.simpac.app.data.RioVigiladoMapa
import pe.simpac.app.data.RioZonaMapa
import pe.simpac.app.dominio.AvisosMapa
import pe.simpac.app.dominio.Caja
import pe.simpac.app.dominio.Cauces
import pe.simpac.app.dominio.Coord
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.DiaMapa
import pe.simpac.app.dominio.EstadoCauce
import pe.simpac.app.dominio.EstadoCauceRio
import pe.simpac.app.dominio.EstadoRio
import pe.simpac.app.dominio.EstadoZona
import pe.simpac.app.dominio.Fen
import pe.simpac.app.dominio.GeoJson
import pe.simpac.app.dominio.Geometria
import pe.simpac.app.dominio.Incidentes
import pe.simpac.app.dominio.Lluvia
import pe.simpac.app.dominio.Nivel
import pe.simpac.app.dominio.NivelZona
import pe.simpac.app.dominio.Nowcast
import pe.simpac.app.dominio.PronosticoMapa
import pe.simpac.app.dominio.TextoRio
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ubicacion.Lectura
import pe.simpac.app.ubicacion.Posicion
import pe.simpac.app.ubicacion.Ubicacion
import java.io.IOException

/** Los grupos del panel de capas, en el orden de la web (map/layers/index.js GRUPOS). */
object GruposCapa {
    const val ALERTAS = "Alertas y avisos"
    const val PRONOSTICO = "Pronóstico"
    const val LLUVIA = "Lluvia"
    const val RIOS = "Ríos y estaciones"
    const val NINO = "El Niño"
    const val COMUNIDAD = "Comunidad"
    const val ACUDIR = "A dónde acudir"
    val ORDEN = listOf(ALERTAS, PRONOSTICO, LLUVIA, RIOS, NINO, COMUNIDAD, ACUDIR)
}

/**
 * Las capas del mapa, con la clave que se guarda en Ajustes, su grupo, desde que zoom se dibujan y si
 * arrancan encendidas (como la web). `nuevaV2`: capas que no existian en la primera version de la app;
 * si Ajustes guardo capas sin la marca "v2", las de fabrica se encienden una vez.
 */
enum class Capa(
    val clave: String, val etiqueta: String, val corta: String, val grupo: String, val desdeZoom: Double,
    val deFabrica: Boolean, val insignia: String? = null, val nuevaV2: Boolean = false,
) {
    AVISOS("avisos", "Avisos de SENAMHI (lluvia, calor, frío, viento)", "Avisos", GruposCapa.ALERTAS, 0.0, true, "Oficial"),
    ZONAS("zonas", "Zonas que un río podría afectar", "Zonas", GruposCapa.ALERTAS, Cauces.ZONAS_DESDE.toDouble(), true),
    PRONOSTICO("pronostico", "Pronóstico por localidad (SENAMHI)", "Pronóstico", GruposCapa.PRONOSTICO, 0.0, true, "Oficial", nuevaV2 = true),
    NOWCAST("nowcast", "Lluvia en las próximas 2 horas", "Próximas 2 h", GruposCapa.PRONOSTICO, 0.0, false, "Experimental", nuevaV2 = true),
    LLUVIA_AHORA("lluvia_ahora", "Lluvia de la última hora (estaciones)", "Lloviendo ahora", GruposCapa.LLUVIA, 0.0, false, nuevaV2 = true),
    LLUVIA_OBSERVADA("lluvia_observada", "Lluvia de ayer / de la semana", "Lluvia ayer", GruposCapa.LLUVIA, 0.0, false, nuevaV2 = true),
    SATELITE("satelite", "Lluvia por satélite (NASA)", "Satélite", GruposCapa.LLUVIA, 0.0, false, nuevaV2 = true),
    RIOS("rios", "Ríos", "Ríos", GruposCapa.RIOS, 0.0, true),
    DESBORDES("desbordes", "Desbordes y daños pasados", "Desbordes", GruposCapa.RIOS, Incidentes.DESDE_ZOOM, true, nuevaV2 = true),
    ESTACIONES("estaciones", "Estaciones SENAMHI", "Estaciones", GruposCapa.RIOS, Cauces.ESTACIONES_DESDE.toDouble(), false),
    FEN("fen", "Eventos El Niño pasados", "El Niño", GruposCapa.NINO, 0.0, false, nuevaV2 = true),
    REPORTES("reportes", "Reportes ciudadanos", "Reportes", GruposCapa.COMUNIDAD, 0.0, true, nuevaV2 = true),
    ACUDIR("acudir", "Salud, comisarías y bomberos", "Acudir", GruposCapa.ACUDIR, Cauces.ACUDIR_DESDE.toDouble(), false);

    companion object {
        const val MARCA_V2 = "v2"
        const val PREFIJO_OPCION = "op:"

        /** Capas encendidas a partir de lo guardado; sin la marca v2 se suman las nuevas de fabrica. */
        fun desdeClaves(claves: Set<String>): Set<Capa> {
            val capas = entries.filter { it.clave in claves }.toMutableSet()
            if (MARCA_V2 !in claves) capas += entries.filter { it.nuevaV2 && it.deFabrica }
            return capas
        }

        /** Opciones guardadas junto a las capas ("op:fen=1997-1998|DEF"). */
        fun opcionesDesdeClaves(claves: Set<String>): Map<String, String> =
            claves.filter { it.startsWith(PREFIJO_OPCION) && it.contains("=") }
                .associate { it.removePrefix(PREFIJO_OPCION).substringBefore("=") to it.substringAfter("=") }

        /** Lo que se guarda en Ajustes: claves de las capas, opciones y la marca v2 (sin comas: Ajustes las separa por coma). */
        fun aClaves(capas: Set<Capa>, opciones: Map<String, String>): Set<String> =
            capas.map { it.clave }.toSet() + opciones.map { (k, v) -> "$PREFIJO_OPCION$k=${v.replace(",", "")}" } + MARCA_V2
    }
}

/** Un aviso de SENAMHI listo para dibujar: su area, su caja y el punto de la insignia. */
data class AvisoDibujo(val aviso: AvisoVigente, val poligonos: Geometria.Poligonos, val caja: Caja, val centro: Coord?, val glifo: String?)

/** Un rio del pais con trazo: estado de hoy y el trazo en tres detalles (el fino llega aparte). */
data class RioDibujo(
    val rioAna: String,
    val nombre: String,
    val departamento: String?,
    val estado: EstadoRio,
    val lecturas: List<CaudalActual>,
    val lejos: List<List<Coord>>,            // ~50 m (zoom 10 a 12)
    val medio: List<List<Coord>>,            // simplificado (zoom 8 y 9)
    val grueso: List<List<Coord>>,           // muy simplificado (pais entero)
    val caja: Caja,
    val fuente: String?,
    val fuenteUrl: String?,
    val licencia: String?,
    val km: Double?,
)

/** El rio vigilado (Mashcon) con cauce, afluentes y estado de la zona de hoy. */
data class MashconDibujo(
    val rio: RioVigiladoMapa,
    val nombre: String,
    val cauce: List<List<Coord>>,
    val afluentes: List<List<Coord>>,
    val caja: Caja?,
    val estado: EstadoZona,
    val cauceEstado: EstadoCauceRio,
    val caudal: CaudalActual?,
    val fuenteCauce: String,
)

/** Una zona que un rio podria afectar, lista para dibujar con el nivel de hoy. */
data class ZonaDibujo(
    val clave: String,
    val rioAna: String,
    val nombreRio: String,
    val tipo: String,                 // estimada | estudio
    val subtipo: String,              // bajo_2m | bajo_3m | menor | mayor
    val nivel: NivelZona,
    val poligonos: Geometria.Poligonos,
    val caja: Caja,
    val areaKm2: Double?,
    val nombre: String?,
    val texto: String?,
    val metodo: String?,
    val fuente: String?,
    val licencia: String?,
    val nota: String?,
    val atribucion: String?,
    val estadoZona: EstadoZona,
    val estacion: String?,
    val esMashcon: Boolean,
)

/** Disco de una estacion de rio de ANA con su estado (o el del aviso hidrologico de su rio). */
data class EstacionRioDibujo(
    val caudal: CaudalActual,
    val t: TextoRio,
    val estado: EstadoCauce,
    val fuerte: Boolean,
    val nombreRio: String,
    val porAviso: Boolean,
    val aviso: AvisoHidro?,
    val colorAviso: String?,
    val fuenteTrazo: String?,
)

/** La franja de atencion referencial de un rio del pais en alerta o emergencia (rio_cauce_mapa.franja). */
data class FranjaDibujo(val rio: RioDibujo, val anchoM: Int?, val poligonos: Geometria.Poligonos, val caja: Caja)

/** Una mancha del nowcasting (un nivel) con su geometria. */
data class ManchaDibujo(val nivel: Int, val mancha: NowcastMancha, val poligonos: Geometria.Poligonos, val caja: Caja)

/** El nowcasting del horizonte elegido: estado, manchas y la nota (fresco, vacio, viejo, error). */
data class NowcastDibujo(val horizonte: Int, val estado: NowcastEstado?, val manchas: List<ManchaDibujo>, val nota: Nowcast.Nota, val obtenidoEn: Long)

/** Una estacion con lluvia de la ultima hora, con su intensidad y si paso la referencia. */
data class LluviaDibujo(val e: LluviaSenamhiActual, val intensidad: String, val ref: Lluvia.Referencia)

/** El mapa de un evento El Nino y un trimestre, con sus poligonos listos. */
data class FenDibujo(val opcion: String, val periodo: String?, val trimestre: String?, val meses: String?, val poligonos: List<Fen.PoligonoFen>, val nota: String)

data class ChipNivel(val nivel: Nivel, val texto: String)

/** Todo lo que pinta la pestana Mapa. */
data class EstadoMapa(
    val cargando: Boolean = true,
    val error: String? = null,
    val capas: Set<Capa> = emptySet(),
    val centro: Posicion? = null,
    val zoomInicial: Double = 13.0,
    val ubicacion: Posicion? = null,
    val chip: ChipNivel? = null,
    val departamento: String = Departamentos.POR_DEFECTO.nombre,
    val dia: DiaMapa = DiaMapa.HOY,
    val avisosTodos: List<AvisoDibujo> = emptyList(),   // todos los vigentes; `avisos` son los del dia elegido
    val avisos: List<AvisoDibujo> = emptyList(),
    val rios: List<RioDibujo> = emptyList(),
    val mashcon: MashconDibujo? = null,
    val estacionesRio: List<EstacionRioDibujo> = emptyList(),
    val zonas: List<ZonaDibujo> = emptyList(),
    val cauceFino: Map<String, List<List<Coord>>> = emptyMap(),
    val estaciones: List<EstacionSenamhi> = emptyList(),
    val acudir: List<PuntoAcudir> = emptyList(),
    val fuentes: List<String> = emptyList(),
    val avisosParciales: List<String> = emptyList(),
    val deCache: Boolean = false,
    val obtenidoEn: Long? = null,
    val obtenidoAvisosEn: Long? = null,
    val obtenidoAcudirEn: Long? = null,
    val obtenidoEstacionesEn: Long? = null,
    // capas nuevas
    val pronostico: List<PronosticoLocalidad> = emptyList(),
    val localidadTuya: String? = null,
    val obtenidoPronosticoEn: Long? = null,
    val nowcastHorizonte: Int = Nowcast.DEFECTO,
    val nowcast: NowcastDibujo? = null,
    val lluviaAhora: List<LluviaDibujo> = emptyList(),
    val obtenidoLluviaEn: Long? = null,
    val lluviaObsOpcion: String = "ayer",
    val lluviaObsNota: String? = null,
    val lluviaObsDia: String? = null,              // dia procesado por SENAMHI (clave de la cache de imagenes)
    val lluviaObsSinServidor: Boolean = false,
    val sateliteHora: String? = null,
    val sateliteNota: String? = null,
    val fenOpcion: String = Fen.DEFECTO,
    val fen: FenDibujo? = null,
    val fenCargando: Boolean = false,
    val incidentes: List<RioIncidente> = emptyList(),
    val obtenidoIncidentesEn: Long? = null,
    val riosVigiladosNombres: Map<String, String> = emptyMap(),
    val reportes: List<ReporteVigente> = emptyList(),
    val obtenidoReportesEn: Long? = null,
    val franjas: List<FranjaDibujo> = emptyList(),
    val errores: Map<Capa, String> = emptyMap(),          // "No se pudo cargar ..." por capa
    val cargandoCapas: Set<Capa> = emptySet(),            // capas que estan pidiendo datos ahora mismo (solo para el indicador)
) {
    /** Verdadero mientras el mapa o alguna capa pide datos (la barra fina bajo el selector de dia). */
    val cargandoAlgo: Boolean get() = cargando || fenCargando || cargandoCapas.isNotEmpty()

    /** Si la capa esta pidiendo datos ahora (para la rueda chica junto a su interruptor). */
    fun cargandoCapa(capa: Capa): Boolean = capa in cargandoCapas || (capa == Capa.FEN && fenCargando)

    /** Lo que la hoja "Capas" dice bajo cada interruptor (la nota de render() de la web). */
    fun nota(capa: Capa): String? {
        errores[capa]?.let { return it }
        return when (capa) {
            Capa.AVISOS -> if (avisosTodos.isEmpty() && cargando) null else PronosticoMapa.notaAvisos(avisos.map { it.aviso }, dia)
            Capa.PRONOSTICO -> if (pronostico.isEmpty()) null else PronosticoMapa.nota(pronostico, dia.fechaIso())
            Capa.NOWCAST -> if (dia != DiaMapa.HOY) "El nowcasting solo vale para hoy: elige \"Hoy\" arriba del mapa para verlo." else nowcast?.nota?.texto
            Capa.LLUVIA_AHORA -> if (obtenidoLluviaEn == null) null else Lluvia.nota(lluviaAhora.map { it.e })
            Capa.LLUVIA_OBSERVADA -> if (lluviaObsSinServidor) Lluvia.SIN_SERVIDOR else lluviaObsNota
            Capa.SATELITE -> sateliteNota
            Capa.FEN -> if (fenCargando) "Leyendo el mapa del evento..." else fen?.nota
            Capa.DESBORDES -> if (obtenidoIncidentesEn == null) null else Incidentes.nota(incidentes, riosVigiladosNombres)
            Capa.ZONAS -> if (franjas.isEmpty()) null else "Franja de atención referencial en ${franjas.size} ${if (franjas.size == 1) "río" else "ríos"} en alerta o emergencia: ${Cauces.lista(franjas.map { it.rio.nombre }, 3)} (desde zoom ${Cauces.DETALLE_DESDE})."
            Capa.REPORTES -> if (obtenidoReportesEn == null) null else if (reportes.isEmpty()) "No hay reportes vigentes de la comunidad a la vista." else "${reportes.size} ${if (reportes.size == 1) "reporte vigente" else "reportes vigentes"} de la comunidad a la vista (leídos ${Tiempo.horaCorta(obtenidoReportesEn)})."
            else -> null
        }
    }

    /** Chip corto sobre el mapa del nowcasting (solo con la capa prendida y "Hoy"). */
    val chipNowcast: String? get() = if (Capa.NOWCAST in capas && dia == DiaMapa.HOY) nowcast?.nota?.corto else null
}

/**
 * ViewModel del mapa nativo: baja los datos (Supabase), los convierte a geometria fuera del hilo
 * principal y sigue la vista (zonas, trazo fino, estaciones, puntos de acudir y reportes solo para lo
 * que se ve). Las capas apagadas no piden nada; al prenderlas se pide lo suyo una vez (y el
 * nowcasting cada 2 min mientras siga prendida). Al salir de la pestana el ViewModel se limpia.
 */
class MapaViewModel(app: Application) : AndroidViewModel(app) {
    private val contenedor = (app as SimpacApp).contenedor
    private val repo = contenedor.repositorio
    private val ajustes = contenedor.ajustes

    private val _estado = MutableStateFlow(EstadoMapa())
    val estado: StateFlow<EstadoMapa> = _estado

    private var trabajoVista: Job? = null
    private val zonasPedidas = mutableSetOf<String>()
    private val finosPedidos = mutableSetOf<String>()
    private val franjasPedidas = mutableSetOf<String>()
    private var ultimaCajaAcudir: Caja? = null
    private var ultimaCajaEstaciones: Caja? = null
    private var ultimaCajaReportes: Caja? = null
    private var reportesPedidosEn = 0L
    private var estadosPais: Map<String, EstadoRio> = emptyMap()
    private var nombresPais: Map<String, String> = emptyMap()
    private var cajasPais: Map<String, Caja> = emptyMap()

    private var trabajoCarga: Job? = null
    private var trabajoNowcast: Job? = null
    private var trabajoFen: Job? = null
    private var trabajoSatelite: Job? = null
    private var pronosticoPedido = false
    private var lluviaPedida = false
    private var incidentesPedidos = false
    private var opciones: Map<String, String> = emptyMap()

    private companion object {
        const val REPORTES_CADA_MS = 2 * 60_000L
        const val NOWCAST_CADA_MS = 2 * 60_000L
    }

    init {
        cargar()
        // El ViewModel sobrevive al cambio de pestana (Navigation guarda la entrada con saveState): si la
        // persona cambia de ciudad o prende "Usar mi ubicacion" en Inicio, el mapa se recarga y se recentra.
        viewModelScope.launch {
            ajustes.flujo.map { it.departamento to it.usarGps }.distinctUntilChanged().drop(1).collect { cargar() }
        }
    }

    fun cargar() {
        trabajoCarga?.cancel()
        trabajoCarga = viewModelScope.launch {
            _estado.update { it.copy(cargando = true, error = null) }
            val conf = ajustes.actual()
            val app = getApplication<Application>()
            val posicion = (if (conf.usarGps && Ubicacion.tienePermiso(app)) Ubicacion.actual(app) else null)?.takeIf { Ubicacion.enPeru(it) }
            val departamento = posicion?.let { runCatching { repo.departamentoDe(it.lat, it.lon) }.getOrNull() } ?: conf.departamento
            val depto = Departamentos.porNombre(departamento) ?: Departamentos.POR_DEFECTO
            val centro = posicion ?: Posicion(depto.lat, depto.lon)
            opciones = Capa.opcionesDesdeClaves(conf.capasMapa)
            val capas = Capa.desdeClaves(conf.capasMapa)
            _estado.update {
                it.copy(
                    capas = capas, centro = centro, ubicacion = posicion, departamento = departamento, zoomInicial = 13.0,
                    nowcastHorizonte = opciones["nowcast"]?.toIntOrNull()?.takeIf { h -> Nowcast.HORIZONTES.any { x -> x.minutos == h } } ?: Nowcast.DEFECTO,
                    lluviaObsOpcion = Lluvia.observada(opciones["lluviaobs"]).clave,
                    fenOpcion = Fen.normalizar(opciones["fen"]),
                )
            }
            val base = withContext(Dispatchers.IO) { armar(departamento) }
            _estado.update { actual ->
                val delDia = PronosticoMapa.avisosDelDia(base.avisosTodos.map { it.aviso }, actual.dia).toSet()
                base.copy(
                    capas = actual.capas, centro = actual.centro, ubicacion = actual.ubicacion, departamento = actual.departamento,
                    zoomInicial = actual.zoomInicial, estaciones = actual.estaciones, acudir = actual.acudir,
                    obtenidoAcudirEn = actual.obtenidoAcudirEn, obtenidoEstacionesEn = actual.obtenidoEstacionesEn,
                    dia = actual.dia, avisos = base.avisosTodos.filter { a -> a.aviso in delDia },
                    nowcastHorizonte = actual.nowcastHorizonte, nowcast = actual.nowcast, pronostico = actual.pronostico,
                    obtenidoPronosticoEn = actual.obtenidoPronosticoEn, lluviaAhora = actual.lluviaAhora, obtenidoLluviaEn = actual.obtenidoLluviaEn,
                    lluviaObsOpcion = actual.lluviaObsOpcion, lluviaObsNota = actual.lluviaObsNota, lluviaObsSinServidor = actual.lluviaObsSinServidor,
                    sateliteHora = actual.sateliteHora, sateliteNota = actual.sateliteNota, fenOpcion = actual.fenOpcion, fen = actual.fen,
                    fenCargando = actual.fenCargando, incidentes = actual.incidentes, obtenidoIncidentesEn = actual.obtenidoIncidentesEn,
                    reportes = actual.reportes, obtenidoReportesEn = actual.obtenidoReportesEn, errores = actual.errores,
                    cargandoCapas = actual.cargandoCapas,
                    localidadTuya = actual.pronostico.takeIf { it.isNotEmpty() }?.let { p -> PronosticoMapa.localidadCercana(p, centro.lat, centro.lon) },
                )
            }
            cargarCapasActivas()
        }
    }

    /** Pide una vez lo que necesitan las capas prendidas que no dependen de la vista. */
    private fun cargarCapasActivas() {
        val capas = _estado.value.capas
        if (Capa.PRONOSTICO in capas) pedirPronostico()
        if (Capa.NOWCAST in capas) seguirNowcast()
        if (Capa.LLUVIA_AHORA in capas) pedirLluviaAhora()
        if (Capa.LLUVIA_OBSERVADA in capas) pedirLluviaObservada()
        if (Capa.SATELITE in capas) pedirSatelite()
        if (Capa.FEN in capas) pedirFen()
        if (Capa.DESBORDES in capas) pedirIncidentes()
        if (Capa.ZONAS in capas) pedirFranjas()
    }

    private fun guardarCapas() {
        val e = _estado.value
        val ops = mapOf("nowcast" to e.nowcastHorizonte.toString(), "lluviaobs" to e.lluviaObsOpcion, "fen" to e.fenOpcion)
        opciones = ops
        viewModelScope.launch { ajustes.guardarCapasMapa(Capa.aClaves(e.capas, ops)) }
    }

    /** Apaga o prende una capa y lo recuerda en Ajustes; al prender, pide lo suyo (si aun no esta). */
    fun alternarCapa(capa: Capa) {
        val prende = capa !in _estado.value.capas
        val nuevas = _estado.value.capas.let { if (prende) it + capa else it - capa }
        _estado.update { it.copy(capas = nuevas) }
        guardarCapas()
        if (prende) when (capa) {
            Capa.PRONOSTICO -> pedirPronostico()
            Capa.NOWCAST -> seguirNowcast()
            Capa.LLUVIA_AHORA -> pedirLluviaAhora()
            Capa.LLUVIA_OBSERVADA -> pedirLluviaObservada()
            Capa.SATELITE -> pedirSatelite()
            Capa.FEN -> pedirFen()
            Capa.DESBORDES -> pedirIncidentes()
            Capa.ZONAS -> pedirFranjas()
            else -> {}
        } else when (capa) {
            Capa.NOWCAST -> { trabajoNowcast?.cancel(); trabajoNowcast = null }
            Capa.FEN -> { trabajoFen?.cancel(); trabajoFen = null; _estado.update { it.copy(fenCargando = false) } }
            Capa.SATELITE -> { trabajoSatelite?.cancel(); trabajoSatelite = null }
            else -> {}
        }
    }

    /** Vuelve a las capas de fabrica (boton "Restablecer" de la hoja Capas); cada cambio pasa por alternarCapa. */
    fun restablecerCapas() {
        for (capa in Capa.entries) if ((capa in _estado.value.capas) != capa.deFabrica) alternarCapa(capa)
    }

    /** El selector Hoy / Manana / Pasado: mueve a la vez los avisos (por su fecha) y el pronostico. */
    fun elegirDia(dia: DiaMapa) {
        _estado.update { e ->
            val delDia = PronosticoMapa.avisosDelDia(e.avisosTodos.map { it.aviso }, dia).toSet()
            e.copy(dia = dia, avisos = e.avisosTodos.filter { it.aviso in delDia })
        }
    }

    fun elegirHorizonteNowcast(min: Int) {
        if (min == _estado.value.nowcastHorizonte) return
        _estado.update { it.copy(nowcastHorizonte = min, nowcast = null) }
        guardarCapas()
        if (Capa.NOWCAST in _estado.value.capas) seguirNowcast()
    }

    fun elegirLluviaObservada(clave: String) {
        val c = Lluvia.observada(clave)
        if (c.clave == _estado.value.lluviaObsOpcion) return
        _estado.update { it.copy(lluviaObsOpcion = c.clave, lluviaObsNota = null, lluviaObsSinServidor = false) }
        guardarCapas()
        if (Capa.LLUVIA_OBSERVADA in _estado.value.capas) pedirLluviaObservada()
    }

    fun elegirFen(valor: String) {
        val v = Fen.normalizar(valor)
        if (v == _estado.value.fenOpcion) return
        _estado.update { it.copy(fenOpcion = v, fen = null) }
        guardarCapas()
        if (Capa.FEN in _estado.value.capas) pedirFen()
    }

    private fun conError(capa: Capa, texto: String?) = _estado.update { e -> e.copy(errores = if (texto == null) e.errores - capa else e.errores + (capa to texto)) }

    /**
     * Texto de un fallo para la pantalla, sin detalles tecnicos: nunca el host de Supabase ni el
     * mensaje de la excepcion. Si fallo la red (sin conexion, tiempo agotado) pide revisar la
     * conexion; si no (el servidor respondio mal o la respuesta no se entendio) pide intentar luego.
     */
    private fun fallo(base: String, e: Throwable?): String =
        if (esDeRed(e)) "$base Revisa tu conexión e inténtalo de nuevo." else "$base Inténtalo de nuevo en un momento."

    /** Http.get envuelve el IOException de OkHttp en un ErrorConsulta con esa causa; un IOException suelto tambien es red. */
    private fun esDeRed(e: Throwable?): Boolean = when (e) {
        null -> false
        is ErrorConsulta -> e.cause is IOException
        is IOException -> true
        else -> false
    }

    /** Marca (o desmarca) que la capa esta pidiendo datos; solo mueve el indicador, no cambia ningun dato. */
    private fun cargandoCapa(capa: Capa, si: Boolean) = _estado.update { e ->
        if (si == (capa in e.cargandoCapas)) e else e.copy(cargandoCapas = if (si) e.cargandoCapas + capa else e.cargandoCapas - capa)
    }

    // ---- pronostico por localidad ----
    private fun pedirPronostico() {
        if (pronosticoPedido) return
        pronosticoPedido = true
        viewModelScope.launch {
            cargandoCapa(Capa.PRONOSTICO, true)
            try {
                val r = withContext(Dispatchers.IO) { repo.pronosticoMapa() }
                val filas = r.dato.filter { it.lat != null && it.lon != null && it.fecha != null }
                _estado.update { e ->
                    val c = e.centro
                    e.copy(pronostico = filas, obtenidoPronosticoEn = r.obtenidoEn, localidadTuya = c?.let { PronosticoMapa.localidadCercana(filas, it.lat, it.lon) })
                }
                conError(Capa.PRONOSTICO, null)
            } catch (ex: Exception) {
                pronosticoPedido = false
                conError(Capa.PRONOSTICO, fallo("No se pudo cargar el pronóstico por localidad.", ex))
            } finally {
                cargandoCapa(Capa.PRONOSTICO, false)
            }
        }
    }

    // ---- nowcasting (cada 2 min mientras la capa este prendida) ----
    private fun seguirNowcast() {
        trabajoNowcast?.cancel()
        trabajoNowcast = viewModelScope.launch {
            while (isActive) {
                pedirNowcast()
                delay(NOWCAST_CADA_MS)
            }
        }
    }

    private suspend fun pedirNowcast() {
        val h = _estado.value.nowcastHorizonte
        // el indicador solo la primera vez (o al cambiar de horizonte): el refresco de cada 2 min es silencioso
        val primera = _estado.value.nowcast == null
        if (primera) cargandoCapa(Capa.NOWCAST, true)
        try {
            val rEstado = runCatching { withContext(Dispatchers.IO) { repo.nowcastEstado() } }
            val rManchas = runCatching { withContext(Dispatchers.IO) { repo.nowcastVigente(h) } }
            val ahora = System.currentTimeMillis()
            val e = rEstado.getOrNull()?.dato?.firstOrNull { it.horizonte_min == h }
            val manchas = rManchas.getOrNull()?.dato
            val nota = Nowcast.nota(e, manchas?.size, h, ahora)
            val dibujos = if (nota.estado == Nowcast.EstadoNota.FRESCO) withContext(Dispatchers.Default) {
                (manchas ?: emptyList()).mapNotNull { m ->
                    val geo = GeoJson.parsear(m.geojson) as? Geometria.Poligonos ?: return@mapNotNull null
                    val caja = GeoJson.caja(geo) ?: return@mapNotNull null
                    ManchaDibujo(m.nivel, m, geo, caja)
                }.sortedBy { it.nivel }
            } else emptyList()
            _estado.update { it.copy(nowcast = NowcastDibujo(h, e, dibujos, nota, ahora)) }
        } finally {
            if (primera) cargandoCapa(Capa.NOWCAST, false)
        }
    }

    // ---- lluvia de la ultima hora ----
    private fun pedirLluviaAhora() {
        if (lluviaPedida && System.currentTimeMillis() - (_estado.value.obtenidoLluviaEn ?: 0L) < 5 * 60_000L) return
        lluviaPedida = true
        viewModelScope.launch {
            cargandoCapa(Capa.LLUVIA_AHORA, true)
            try {
                val r = withContext(Dispatchers.IO) { repo.lluviaAhora() }
                val lista = withContext(Dispatchers.Default) {
                    r.dato.filter { it.lat != null && it.lon != null && it.pp_1h != null }
                        .map { LluviaDibujo(it, Lluvia.intensidad(it.pp_1h) ?: "sin lluvia", Lluvia.referencia(it)) }
                        .sortedWith(compareBy<LluviaDibujo> { if (it.ref.pasa) 1 else 0 }.thenBy { it.e.pp_1h ?: 0.0 })
                }
                _estado.update { it.copy(lluviaAhora = lista, obtenidoLluviaEn = r.obtenidoEn) }
                conError(Capa.LLUVIA_AHORA, null)
            } catch (ex: Exception) {
                lluviaPedida = false
                conError(Capa.LLUVIA_AHORA, fallo("No se pudo cargar la lluvia de las estaciones.", ex))
            } finally {
                cargandoCapa(Capa.LLUVIA_AHORA, false)
            }
        }
    }

    // ---- lluvia observada (WMS de SENAMHI): de que dias es (latido) y si el servidor responde ----
    private fun pedirLluviaObservada() {
        viewModelScope.launch {
            cargandoCapa(Capa.LLUVIA_OBSERVADA, true)
            try {
                val c = Lluvia.observada(_estado.value.lluviaObsOpcion)
                val resumen = runCatching { withContext(Dispatchers.IO) { repo.latido("lluvia_nacional") } }.getOrNull()?.dato?.resumen as? JsonObject
                fun campo(k: String) = (resumen?.get(k) as? JsonPrimitive)?.content?.takeIf { it != "null" }
                val nota = Lluvia.notaObservada(c, campo("prec_1"), campo("prec_1_ac07d_desde"), campo("prec_1_ac07d"))
                _estado.update { it.copy(lluviaObsNota = nota, lluviaObsDia = campo("prec_1"), lluviaObsSinServidor = false) }
                // una imagen de prueba (el pais a zoom 5): si falla, la capa lo dice (como tileerror en la web)
                val responde = repo.pruebaWms(FuenteWmsSenamhi.urlPrueba(c))
                if (!responde) _estado.update { it.copy(lluviaObsSinServidor = true) }
            } finally {
                cargandoCapa(Capa.LLUVIA_OBSERVADA, false)
            }
        }
    }

    // ---- lluvia por satelite (NASA GIBS): la hora del dato mas reciente ----
    private fun pedirSatelite() {
        trabajoSatelite?.cancel()
        trabajoSatelite = viewModelScope.launch {
            while (isActive) {
                cargandoCapa(Capa.SATELITE, true)
                try {
                    val hora = repo.horaSatelite()
                    _estado.update { it.copy(sateliteHora = hora, sateliteNota = Lluvia.notaSatelite(hora, 13.0)) }
                    conError(Capa.SATELITE, null)
                } catch (ex: Exception) {
                    _estado.update { it.copy(sateliteHora = null, sateliteNota = null) }
                    conError(Capa.SATELITE, fallo("No se pudo consultar las imágenes de NASA GIBS.", ex))
                } finally {
                    cargandoCapa(Capa.SATELITE, false)
                }
                delay(30 * 60_000L)
            }
        }
    }

    /** La nota del satelite menciona el zoom ("aleja el mapa"): se recalcula al parar el mapa. */
    fun zoomSatelite(zoom: Double) {
        val e = _estado.value
        if (Capa.SATELITE !in e.capas || e.errores.containsKey(Capa.SATELITE)) return
        val nota = Lluvia.notaSatelite(e.sateliteHora, zoom)
        if (nota != e.sateliteNota) _estado.update { it.copy(sateliteNota = nota) }
    }

    // ---- El Nino pasados ----
    private fun pedirFen() {
        trabajoFen?.cancel()
        val opcion = _estado.value.fenOpcion
        if (_estado.value.fen?.opcion == opcion) return
        trabajoFen = viewModelScope.launch {
            _estado.update { it.copy(fenCargando = true) }
            try {
                val (periodo, trimestre) = Fen.partir(opcion)
                val r = withContext(Dispatchers.IO) { repo.mapaFen(periodo ?: "", trimestre ?: "") }
                val m = r.dato
                val poligonos = withContext(Dispatchers.Default) { Fen.poligonos(m?.geojson) }
                val dibujo = if (m == null || poligonos.isEmpty()) FenDibujo(opcion, periodo, trimestre, null, emptyList(), "No hay mapa para ese evento y trimestre.")
                else FenDibujo(opcion, m.periodo ?: periodo, m.trimestre ?: trimestre, m.meses, poligonos, Fen.nota(m.periodo ?: periodo, m.trimestre ?: trimestre, m.meses))
                _estado.update { it.copy(fen = dibujo, fenCargando = false) }
                conError(Capa.FEN, null)
            } catch (ex: Exception) {
                _estado.update { it.copy(fenCargando = false) }
                conError(Capa.FEN, fallo("No se pudo cargar el mapa del evento.", ex))
            }
        }
    }

    // ---- desbordes y danos pasados ----
    private fun pedirIncidentes() {
        if (incidentesPedidos) return
        incidentesPedidos = true
        viewModelScope.launch {
            cargandoCapa(Capa.DESBORDES, true)
            try {
                val r = withContext(Dispatchers.IO) { repo.incidentesRio() }
                _estado.update { it.copy(incidentes = r.dato, obtenidoIncidentesEn = r.obtenidoEn) }
                conError(Capa.DESBORDES, null)
            } catch (ex: Exception) {
                incidentesPedidos = false
                conError(Capa.DESBORDES, fallo("No se pudieron cargar los desbordes pasados.", ex))
            } finally {
                cargandoCapa(Capa.DESBORDES, false)
            }
        }
    }

    // ---- franja de atencion de los rios del pais en alerta o emergencia ----
    private fun pedirFranjas() {
        val fuertes = _estado.value.rios.filter { Cauces.esFuerte(it.estado) && it.rioAna !in franjasPedidas }
        if (fuertes.isEmpty()) return
        viewModelScope.launch {
            cargandoCapa(Capa.ZONAS, true)
            try {
                for (r in fuertes) {
                    franjasPedidas += r.rioAna
                    val f = try { withContext(Dispatchers.IO) { repo.franjaRio(r.rioAna) }.dato } catch (_: Exception) { franjasPedidas -= r.rioAna; continue }
                    val geo = withContext(Dispatchers.Default) { GeoJson.parsear(f?.franja) as? Geometria.Poligonos } ?: continue
                    val caja = GeoJson.caja(geo) ?: continue
                    _estado.update { e -> e.copy(franjas = e.franjas.filter { it.rio.rioAna != r.rioAna } + FranjaDibujo(r, f?.ancho_m, geo, caja)) }
                }
            } finally {
                cargandoCapa(Capa.ZONAS, false)
            }
        }
    }

    /**
     * Vuelve a leer la ubicacion (boton "Centrar en tu ubicacion"): una lectura activa de alta precision
     * de hasta 20 s. Devuelve la posicion o el motivo exacto de que no la haya (sin permiso, ubicacion
     * del telefono apagada, sin senal), para que la pantalla diga y ofrezca lo justo. Si llega y esta en
     * el Peru, se guarda para el punto azul. Quien llama cancela la espera al irse la app al fondo.
     */
    suspend fun ubicacionAhora(): Lectura {
        val lectura = Ubicacion.leer(getApplication<Application>(), Ubicacion.ESPERA_BOTON_MS)
        if (lectura is Lectura.Hecha && Ubicacion.enPeru(lectura.posicion)) _estado.update { it.copy(ubicacion = lectura.posicion) }
        return lectura
    }

    /**
     * La vista cambio (tras 250 ms quieta): pide lo que falte para lo que se ve. Un movimiento nuevo
     * cancela el pedido anterior; nunca se pide el pais entero.
     */
    fun vistaCambio(caja: Caja, zoom: Double) {
        trabajoVista?.cancel()
        zoomSatelite(zoom)
        trabajoVista = viewModelScope.launch {
            delay(250)
            val capas = _estado.value.capas
            val conMargen = GeoJson.cajaConMargen(caja, 0.2)
            coroutineScope {
                if (Capa.ZONAS in capas && zoom >= Cauces.ZONAS_DESDE) launch { pedirZonas(conMargen, zoom) }
                if (Capa.RIOS in capas && zoom >= Cauces.DETALLE_DESDE) launch { pedirFinos(caja) }
                if (Capa.ESTACIONES in capas && zoom >= Cauces.ESTACIONES_DESDE) launch { pedirEstaciones(conMargen) }
                if (Capa.ACUDIR in capas && zoom >= Cauces.ACUDIR_DESDE) launch { pedirAcudir(conMargen) }
                if (Capa.REPORTES in capas) launch { pedirReportes(conMargen) }
            }
        }
    }

    private suspend fun pedirReportes(caja: Caja) {
        val redonda = GeoJson.cajaRedondeada(caja)
        val ahora = System.currentTimeMillis()
        if (redonda == ultimaCajaReportes && ahora - reportesPedidosEn < REPORTES_CADA_MS) return
        ultimaCajaReportes = redonda
        reportesPedidosEn = ahora
        cargandoCapa(Capa.REPORTES, true)
        try {
            val r = withContext(Dispatchers.IO) { repo.reportesVigentes(redonda) }
            _estado.update { it.copy(reportes = r.dato.filter { x -> x.lat != null && x.lon != null }, obtenidoReportesEn = r.obtenidoEn) }
            conError(Capa.REPORTES, null)
        } catch (ex: Exception) {
            ultimaCajaReportes = null
            conError(Capa.REPORTES, fallo("No se pudieron leer los reportes de la comunidad.", ex))
        } finally {
            cargandoCapa(Capa.REPORTES, false)
        }
    }

    private suspend fun pedirZonas(caja: Caja, zoom: Double) {
        val ids = Cauces.riosParaZonas(cajasPais, caja, zoom).filter { it !in zonasPedidas }
        if (ids.isEmpty()) return
        zonasPedidas += ids
        cargandoCapa(Capa.ZONAS, true)
        try {
            val filas = try {
                withContext(Dispatchers.IO) { repo.zonasCauces(ids) }
            } catch (_: Exception) {
                zonasPedidas -= ids.toSet()   // se vuelve a intentar al mover el mapa
                return
            }
            val nuevas = withContext(Dispatchers.Default) { filas.dato.mapNotNull { zonaPais(it) } }
            if (nuevas.isEmpty()) return
            _estado.update { e -> e.copy(zonas = e.zonas + nuevas.filter { n -> e.zonas.none { it.clave == n.clave } }) }
        } finally {
            cargandoCapa(Capa.ZONAS, false)
        }
    }

    private fun zonaPais(z: RioCauceZonaMapa): ZonaDibujo? {
        if (z.subtipo != "bajo_2m" && z.subtipo != "bajo_3m") return null
        val geo = GeoJson.parsear(z.geojson) as? Geometria.Poligonos ?: return null
        val caja = GeoJson.caja(geo) ?: return null
        val est = estadosPais[z.rio_ana]
        val zona = est?.zona ?: Cauces.estadoZona(null)
        return ZonaDibujo(
            clave = z.clave, rioAna = z.rio_ana, nombreRio = nombresPais[z.rio_ana] ?: z.rio_ana, tipo = "estimada", subtipo = z.subtipo,
            nivel = zona.nivel, poligonos = geo, caja = caja, areaKm2 = z.area_km2, nombre = null, texto = null, metodo = z.metodo,
            fuente = z.fuente, licencia = z.licencia, nota = z.nota, atribucion = z.atribucion, estadoZona = zona,
            estacion = est?.peor?.estacion, esMashcon = false,
        )
    }

    private suspend fun pedirFinos(caja: Caja) {
        val visibles = _estado.value.rios.filter { GeoJson.cajasSeCruzan(it.caja, caja) && it.rioAna !in finosPedidos }.take(6)
        if (visibles.isEmpty()) return
        cargandoCapa(Capa.RIOS, true)
        try {
            for (r in visibles) {
                finosPedidos += r.rioAna
                val detalle = try {
                    withContext(Dispatchers.IO) { repo.cauceFino(r.rioAna) }.dato
                } catch (_: Exception) {
                    finosPedidos -= r.rioAna
                    continue
                }
                val partes = withContext(Dispatchers.Default) { (GeoJson.parsear(detalle?.cauce) as? Geometria.Lineas)?.partes }
                if (partes != null) _estado.update { e -> e.copy(cauceFino = e.cauceFino + (r.rioAna to partes)) }
            }
        } finally {
            cargandoCapa(Capa.RIOS, false)
        }
    }

    private suspend fun pedirEstaciones(caja: Caja) {
        val redonda = GeoJson.cajaRedondeada(caja)
        if (redonda == ultimaCajaEstaciones) return
        ultimaCajaEstaciones = redonda
        cargandoCapa(Capa.ESTACIONES, true)
        try {
            val r = withContext(Dispatchers.IO) { repo.estaciones(redonda) }
            _estado.update { it.copy(estaciones = r.dato.filter { e -> e.lat != null && e.lon != null }, obtenidoEstacionesEn = r.obtenidoEn) }
        } catch (_: Exception) {
            ultimaCajaEstaciones = null
        } finally {
            cargandoCapa(Capa.ESTACIONES, false)
        }
    }

    private suspend fun pedirAcudir(caja: Caja) {
        val redonda = GeoJson.cajaRedondeada(caja)
        if (redonda == ultimaCajaAcudir) return
        ultimaCajaAcudir = redonda
        cargandoCapa(Capa.ACUDIR, true)
        try {
            val r = withContext(Dispatchers.IO) { repo.puntosAcudirMapa(redonda) }
            _estado.update { it.copy(acudir = r.dato.filter { p -> p.lat != null && p.lon != null }, obtenidoAcudirEn = r.obtenidoEn) }
        } catch (_: Exception) {
            ultimaCajaAcudir = null
        } finally {
            cargandoCapa(Capa.ACUDIR, false)
        }
    }

    /** Baja todo lo que no depende de la vista y lo convierte a geometria (en IO/Default). */
    private suspend fun armar(departamento: String): EstadoMapa = coroutineScope {
        val tTitular = async { runCatching { repo.titular(departamento) } }
        val tAvisos = async { runCatching { repo.avisosVigentes() } }
        val tCaudales = async { runCatching { repo.caudales() } }
        val tVigilados = async { runCatching { repo.riosVigilados() } }
        val tZonasVig = async { runCatching { repo.zonasRioVigilado() } }
        val tSenalesVig = async { runCatching { repo.senalesRioVigilado() } }
        val tCauces = async { runCatching { repo.caucesPais() } }
        val tSenalesCauces = async { runCatching { repo.senalesCauces() } }

        val rTitular = tTitular.await(); val rAvisos = tAvisos.await(); val rCaudales = tCaudales.await()
        val rVigilados = tVigilados.await(); val rZonasVig = tZonasVig.await(); val rSenalesVig = tSenalesVig.await()
        val rCauces = tCauces.await(); val rSenalesCauces = tSenalesCauces.await()

        if (rAvisos.isFailure && rCaudales.isFailure && rCauces.isFailure) {
            // sin el motivo tecnico en pantalla (traia el host de Supabase); solo si fue la red o no
            val causa = rCaudales.exceptionOrNull() ?: rAvisos.exceptionOrNull() ?: rCauces.exceptionOrNull()
            return@coroutineScope EstadoMapa(cargando = false, error = fallo("No se pudieron leer los datos del mapa.", causa))
        }
        val parciales = mutableListOf<String>()
        rAvisos.exceptionOrNull()?.let { parciales += fallo("No se pudieron leer los avisos de SENAMHI.", it) }
        rCaudales.exceptionOrNull()?.let { parciales += fallo("No se pudieron leer los niveles de los ríos de ANA.", it) }
        rCauces.exceptionOrNull()?.let { parciales += fallo("No se pudieron leer los trazos de los ríos.", it) }
        rVigilados.exceptionOrNull()?.let { parciales += "No se pudo leer el río Mashcón." }

        val ahora = System.currentTimeMillis()
        val chip = rTitular.getOrNull()?.dato?.let { ChipNivel(Nivel.desde(it.nivel), "${Nivel.desde(it.nivel).etiqueta} en $departamento") }
            ?: ChipNivel(Nivel.SIN_DATO, "Sin datos de $departamento")

        withContext(Dispatchers.Default) {
            // todos los avisos vigentes (de hoy a pasado manana); el dia elegido filtra al dibujar
            val filasAvisos = rAvisos.getOrNull()?.dato ?: emptyList()
            val avisosTodos = filasAvisos.filter { it.geojson != null && AvisosMapa.COLOR_NIVEL.containsKey(it.nivel) }.mapNotNull { a ->
                val geo = GeoJson.parsear(a.geojson) as? Geometria.Poligonos ?: return@mapNotNull null
                val caja = GeoJson.caja(geo) ?: return@mapNotNull null
                val ancla = a.anclas.firstOrNull { it.mayor && it.lat != null && it.lon != null } ?: a.anclas.firstOrNull { it.lat != null && it.lon != null }
                val centro = ancla?.let { Coord(it.lat!!, it.lon!!) } ?: GeoJson.centroideMayor(geo)
                AvisoDibujo(a, geo, caja, centro, AvisosMapa.glifo(a))
            }
            val deHoy = AvisosMapa.deHoy(filasAvisos, ahora).toSet()
            val avisos = avisosTodos.filter { it.aviso in deHoy }

            val caudales = rCaudales.getOrNull()?.dato ?: emptyList()
            val vigilados = rVigilados.getOrNull()?.dato ?: emptyList()
            val senalesVig = rSenalesVig.getOrNull()?.dato ?: emptyList()
            val zonasVig = rZonasVig.getOrNull()?.dato ?: emptyList()
            val cauces = rCauces.getOrNull()?.dato ?: emptyList()
            val senalesCauces = rSenalesCauces.getOrNull()?.dato ?: emptyList()

            // el Mashcon (rio vigilado) con su zona
            val mashconFila = vigilados.firstOrNull()
            val mashcon = mashconFila?.let { armarMashcon(it, caudales, senalesVig.firstOrNull { s -> s.rio == it.id }, ahora) }
            val zonasMashcon = mashcon?.let { m -> zonasVig.filter { it.rio == m.rio.id && it.tipo != "faja" }.mapNotNull { zonaMashcon(it, m) } } ?: emptyList()

            // rios del pais
            val emparejados = Cauces.emparejarCauces(cauces, caudales, vigilados)
            val senalesPorRio = senalesCauces.associateBy { it.rio_ana }
            val rios = mutableListOf<RioDibujo>()
            val estados = HashMap<String, EstadoRio>()
            val nombres = HashMap<String, String>()
            val cajas = HashMap<String, Caja>()
            for (r in emparejados.rios) {
                // las senales de la cuenca (avisos de lluvia, lluvia medida) van tambien al mapa, como en Inicio (Rios.resumir)
                val senal = senalesPorRio[r.fila.rio_ana]
                val est = Cauces.estadoRio(r.lecturas, senal?.avisos_hidro ?: emptyList(), senal?.avisos_lluvia ?: emptyList(), senal?.lluvia_cuenca ?: emptyList(), ahora)
                if (r.lecturas.isEmpty() && est.zona.avisoHidro == null) continue   // la web tampoco lo resalta
                val geo = GeoJson.parsear(r.fila.cauce_lejos) as? Geometria.Lineas ?: continue
                val caja = GeoJson.caja(geo) ?: continue
                val nombre = r.fila.nombre ?: r.fila.rio ?: r.fila.rio_ana
                rios += RioDibujo(
                    rioAna = r.fila.rio_ana, nombre = nombre, departamento = r.fila.departamento, estado = est, lecturas = r.lecturas,
                    lejos = geo.partes,
                    medio = geo.partes.map { GeoJson.simplificar(it, 0.003) }.filter { it.size >= 2 },
                    grueso = geo.partes.map { GeoJson.simplificar(it, 0.01) }.filter { it.size >= 2 },
                    caja = caja, fuente = r.fila.fuente, fuenteUrl = r.fila.fuente_url, licencia = r.fila.licencia, km = r.fila.km,
                )
                estados[r.fila.rio_ana] = est
                nombres[r.fila.rio_ana] = nombre
                cajas[r.fila.rio_ana] = caja
            }
            estadosPais = estados; nombresPais = nombres; cajasPais = cajas

            // discos de las estaciones de ANA: el estado de su lectura o, si es de la estacion del aviso, el del aviso
            val porEstacionAviso = HashMap<CaudalActual, RioDibujo>()
            for (r in rios) if (r.estado.cauce.porAviso) for (c in r.lecturas) if (Cauces.avisoEsDeEstacion(r.estado.zona.avisoHidro, c.estacion)) porEstacionAviso[c] = r
            val nombreRioDe = HashMap<CaudalActual, String>()
            for (r in rios) for (c in r.lecturas) nombreRioDe[c] = r.nombre
            val fuenteDe = HashMap<CaudalActual, String?>()
            for (r in rios) for (c in r.lecturas) fuenteDe[c] = r.fuente
            val estacionesRio = caudales.filter { it.lat != null && it.lon != null }.map { c ->
                val t = Cauces.textoRio(c)
                val esMashcon = mashcon != null && mashcon.caudal == c
                val ref: EstadoCauceRio? = when {
                    esMashcon -> mashcon.cauceEstado
                    porEstacionAviso[c] != null -> porEstacionAviso[c]!!.estado.cauce
                    else -> null
                }
                val porAviso = ref?.porAviso == true
                val estado = if (porAviso) ref.estado else t.estado
                val fuerte = if (porAviso) estado == EstadoCauce.ALERTA || estado == EstadoCauce.EMERGENCIA
                else !t.bajo && (t.estado == EstadoCauce.ALERTA || t.estado == EstadoCauce.EMERGENCIA)
                val aviso = if (porAviso) (if (esMashcon) mashcon.estado.avisoHidro else porEstacionAviso[c]?.estado?.zona?.avisoHidro) else null
                val nombreRio = if (esMashcon) mashcon.nombre else nombreRioDe[c] ?: (if (c.rio == "Titicaca") "Lago Titicaca" else "Río ${c.rio ?: c.estacion}")
                EstacionRioDibujo(c, t, estado, fuerte, nombreRio, porAviso, aviso, ref?.color, if (esMashcon) mashcon.fuenteCauce else fuenteDe[c])
            }

            val fuentes = mutableListOf<String>()
            rAvisos.getOrNull()?.let { fuentes += "Avisos: SENAMHI (áreas simplificadas), leídos ${Tiempo.horaCorta(it.obtenidoEn)}" }
            rCaudales.getOrNull()?.let { fuentes += "Niveles de ríos: ANA, leídos ${Tiempo.horaCorta(it.obtenidoEn)}" }
            rCauces.getOrNull()?.let { fuentes += "Trazo de los ríos del país: ANA - GeoSNIRH; zonas: estimación de SIMPAC con el relieve (Copernicus GLO-30), no es un mapa oficial" }
            if (mashcon != null) fuentes += "Trazo del Mashcón: colaboradores de OpenStreetMap (ODbL)"
            val deCache = listOfNotNull(rAvisos.getOrNull()?.deCache, rCaudales.getOrNull()?.deCache, rCauces.getOrNull()?.deCache).any { it }

            EstadoMapa(
                cargando = false, chip = chip, avisosTodos = avisosTodos, avisos = avisos, rios = rios, mashcon = mashcon, estacionesRio = estacionesRio,
                zonas = zonasMashcon, fuentes = fuentes, avisosParciales = parciales, deCache = deCache,
                obtenidoEn = listOfNotNull(rCaudales.getOrNull()?.obtenidoEn, rAvisos.getOrNull()?.obtenidoEn).minOrNull(),
                obtenidoAvisosEn = rAvisos.getOrNull()?.obtenidoEn,
                riosVigiladosNombres = vigilados.associate { it.id to (it.nombre ?: it.id) },
                franjas = emptyList(),
            ).also { franjasPedidas.clear(); zonasPedidas.clear(); finosPedidos.clear() }
        }
    }

    private fun armarMashcon(r: RioVigiladoMapa, caudales: List<CaudalActual>, senal: RioSenal?, ahora: Long): MashconDibujo? {
        val cauce = GeoJson.parsear(r.cauce) as? Geometria.Lineas ?: return null
        val afluentes = (GeoJson.parsear(r.afluentes) as? Geometria.Lineas)?.partes ?: emptyList()
        val caudal = Cauces.caudalDelRio(r, caudales)
        val estado = Cauces.estadoZona(caudal, senal?.avisos_hidro ?: emptyList(), senal?.avisos_lluvia ?: emptyList(), senal?.lluvia_cuenca ?: emptyList(), ahora)
        val cauceEstado = Cauces.estadoCauce(estado.t, estado.avisoHidro)
        return MashconDibujo(
            rio = r, nombre = r.nombre ?: "Río Mashcón", cauce = cauce.partes, afluentes = afluentes, caja = GeoJson.caja(cauce),
            estado = estado, cauceEstado = cauceEstado, caudal = caudal, fuenteCauce = "colaboradores de OpenStreetMap (ODbL)",
        )
    }

    private fun zonaMashcon(z: RioZonaMapa, m: MashconDibujo): ZonaDibujo? {
        val geo = GeoJson.parsear(z.geojson) as? Geometria.Poligonos ?: return null
        val caja = GeoJson.caja(geo) ?: return null
        val tipo = z.tipo ?: return null
        val subtipo = z.subtipo ?: return null
        if (tipo != "estimada" && tipo != "estudio") return null
        return ZonaDibujo(
            clave = z.clave, rioAna = m.rio.id, nombreRio = m.nombre, tipo = tipo, subtipo = subtipo, nivel = m.estado.nivel,
            poligonos = geo, caja = caja, areaKm2 = z.area_km2, nombre = z.nombre, texto = z.texto, metodo = z.metodo, fuente = z.fuente,
            licencia = z.licencia, nota = null, atribucion = z.atribucion, estadoZona = m.estado, estacion = m.caudal?.estacion, esMashcon = true,
        )
    }

    /** Caja que encuadra el cauce de un rio (lejos) y, si hay, tu punto; null si el rio no esta cargado. */
    fun cajaParaEncuadre(rioAna: String?, lat: Double?, lon: Double?): Caja? {
        val e = _estado.value
        val cajaRio = e.rios.firstOrNull { it.rioAna == rioAna }?.caja
            ?: e.mashcon?.takeIf { it.rio.id == rioAna || it.rio.rio_ana?.lowercase() == rioAna?.lowercase() }?.caja
        if (cajaRio == null && (lat == null || lon == null)) return null
        var o = cajaRio?.oeste ?: lon!!; var s = cajaRio?.sur ?: lat!!; var es = cajaRio?.este ?: lon!!; var n = cajaRio?.norte ?: lat!!
        if (lat != null && lon != null) { o = minOf(o, lon); es = maxOf(es, lon); s = minOf(s, lat); n = maxOf(n, lat) }
        return Caja(o, s, es, n)
    }

    /** Resultado sin red para pruebas manuales (no se usa en produccion). */
    @Suppress("unused")
    private fun <T> vacio(dato: T) = Resultado(dato, System.currentTimeMillis(), false)

    @Suppress("unused")
    private fun senalDe(senales: List<RioCauceSenal>, rioAna: String) = senales.firstOrNull { it.rio_ana == rioAna }
}
