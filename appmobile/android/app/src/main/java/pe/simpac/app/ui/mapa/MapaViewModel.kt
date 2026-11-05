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
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import pe.simpac.app.SimpacApp
import pe.simpac.app.data.AvisoHidro
import pe.simpac.app.data.AvisoVigente
import pe.simpac.app.data.CaudalActual
import pe.simpac.app.data.EstacionSenamhi
import pe.simpac.app.data.PuntoAcudir
import pe.simpac.app.data.Resultado
import pe.simpac.app.data.RioCauceSenal
import pe.simpac.app.data.RioCauceZonaMapa
import pe.simpac.app.data.RioSenal
import pe.simpac.app.data.RioVigiladoMapa
import pe.simpac.app.data.RioZonaMapa
import pe.simpac.app.dominio.AvisosMapa
import pe.simpac.app.dominio.Caja
import pe.simpac.app.dominio.Cauces
import pe.simpac.app.dominio.Coord
import pe.simpac.app.dominio.Departamentos
import pe.simpac.app.dominio.EstadoCauce
import pe.simpac.app.dominio.EstadoCauceRio
import pe.simpac.app.dominio.EstadoRio
import pe.simpac.app.dominio.EstadoZona
import pe.simpac.app.dominio.GeoJson
import pe.simpac.app.dominio.Geometria
import pe.simpac.app.dominio.Nivel
import pe.simpac.app.dominio.NivelZona
import pe.simpac.app.dominio.TextoRio
import pe.simpac.app.dominio.Tiempo
import pe.simpac.app.ubicacion.Posicion
import pe.simpac.app.ubicacion.Ubicacion

/** Las capas del mapa, con la clave que se guarda en Ajustes y desde que zoom se dibujan. */
enum class Capa(val clave: String, val etiqueta: String, val desdeZoom: Double) {
    AVISOS("avisos", "Avisos de SENAMHI", 0.0),
    RIOS("rios", "Ríos", 0.0),
    ZONAS("zonas", "Zonas que podrían inundarse", Cauces.ZONAS_DESDE.toDouble()),
    ESTACIONES("estaciones", "Estaciones de SENAMHI", Cauces.ESTACIONES_DESDE.toDouble()),
    ACUDIR("acudir", "A dónde acudir", Cauces.ACUDIR_DESDE.toDouble());

    companion object {
        fun desdeClaves(claves: Set<String>): Set<Capa> = entries.filter { it.clave in claves }.toSet()
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
)

/**
 * ViewModel del mapa nativo: baja los datos (Supabase), los convierte a geometria fuera del hilo
 * principal y sigue la vista (zonas, trazo fino, estaciones y puntos de acudir solo para lo que se ve).
 * Al salir de la pestana el ViewModel se limpia y con el todas sus corrutinas.
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
    private var ultimaCajaAcudir: Caja? = null
    private var ultimaCajaEstaciones: Caja? = null
    private var estadosPais: Map<String, EstadoRio> = emptyMap()
    private var nombresPais: Map<String, String> = emptyMap()
    private var cajasPais: Map<String, Caja> = emptyMap()

    private var trabajoCarga: Job? = null

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
            _estado.update {
                it.copy(capas = Capa.desdeClaves(conf.capasMapa), centro = centro, ubicacion = posicion, departamento = departamento, zoomInicial = 13.0)
            }
            val base = withContext(Dispatchers.IO) { armar(departamento) }
            _estado.update { actual ->
                base.copy(capas = actual.capas, centro = actual.centro, ubicacion = actual.ubicacion, departamento = actual.departamento,
                    zoomInicial = actual.zoomInicial, estaciones = actual.estaciones, acudir = actual.acudir,
                    obtenidoAcudirEn = actual.obtenidoAcudirEn, obtenidoEstacionesEn = actual.obtenidoEstacionesEn)
            }
        }
    }

    /** Apaga o prende una capa y lo recuerda en Ajustes. */
    fun alternarCapa(capa: Capa) {
        val nuevas = _estado.value.capas.let { if (capa in it) it - capa else it + capa }
        _estado.update { it.copy(capas = nuevas) }
        viewModelScope.launch { ajustes.guardarCapasMapa(nuevas.map { it.clave }.toSet()) }
    }

    /** Vuelve a leer la ubicacion (boton "centrar"); null si no hay permiso o no responde. Fuera del Peru no se guarda. */
    suspend fun ubicacionAhora(): Posicion? {
        val app = getApplication<Application>()
        if (!Ubicacion.tienePermiso(app)) return null
        val p = Ubicacion.actual(app)
        if (p != null && Ubicacion.enPeru(p)) _estado.update { it.copy(ubicacion = p) }
        return p
    }

    /**
     * La vista cambio (tras 250 ms quieta): pide lo que falte para lo que se ve. Un movimiento nuevo
     * cancela el pedido anterior; nunca se pide el pais entero.
     */
    fun vistaCambio(caja: Caja, zoom: Double) {
        trabajoVista?.cancel()
        trabajoVista = viewModelScope.launch {
            delay(250)
            val capas = _estado.value.capas
            val conMargen = GeoJson.cajaConMargen(caja, 0.2)
            coroutineScope {
                if (Capa.ZONAS in capas && zoom >= Cauces.ZONAS_DESDE) launch { pedirZonas(conMargen, zoom) }
                if (Capa.RIOS in capas && zoom >= Cauces.DETALLE_DESDE) launch { pedirFinos(caja) }
                if (Capa.ESTACIONES in capas && zoom >= Cauces.ESTACIONES_DESDE) launch { pedirEstaciones(conMargen) }
                if (Capa.ACUDIR in capas && zoom >= Cauces.ACUDIR_DESDE) launch { pedirAcudir(conMargen) }
            }
        }
    }

    private suspend fun pedirZonas(caja: Caja, zoom: Double) {
        val ids = Cauces.riosParaZonas(cajasPais, caja, zoom).filter { it !in zonasPedidas }
        if (ids.isEmpty()) return
        zonasPedidas += ids
        val filas = try {
            withContext(Dispatchers.IO) { repo.zonasCauces(ids) }
        } catch (_: Exception) {
            zonasPedidas -= ids.toSet()   // se vuelve a intentar al mover el mapa
            return
        }
        val nuevas = withContext(Dispatchers.Default) { filas.dato.mapNotNull { zonaPais(it) } }
        if (nuevas.isEmpty()) return
        _estado.update { e -> e.copy(zonas = e.zonas + nuevas.filter { n -> e.zonas.none { it.clave == n.clave } }) }
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
    }

    private suspend fun pedirEstaciones(caja: Caja) {
        val redonda = GeoJson.cajaRedondeada(caja)
        if (redonda == ultimaCajaEstaciones) return
        ultimaCajaEstaciones = redonda
        try {
            val r = withContext(Dispatchers.IO) { repo.estaciones(redonda) }
            _estado.update { it.copy(estaciones = r.dato.filter { e -> e.lat != null && e.lon != null }, obtenidoEstacionesEn = r.obtenidoEn) }
        } catch (_: Exception) {
            ultimaCajaEstaciones = null
        }
    }

    private suspend fun pedirAcudir(caja: Caja) {
        val redonda = GeoJson.cajaRedondeada(caja)
        if (redonda == ultimaCajaAcudir) return
        ultimaCajaAcudir = redonda
        try {
            val r = withContext(Dispatchers.IO) { repo.puntosAcudirMapa(redonda) }
            _estado.update { it.copy(acudir = r.dato.filter { p -> p.lat != null && p.lon != null }, obtenidoAcudirEn = r.obtenidoEn) }
        } catch (_: Exception) {
            ultimaCajaAcudir = null
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
            val motivo = rCaudales.exceptionOrNull()?.message ?: rAvisos.exceptionOrNull()?.message ?: "sin respuesta"
            return@coroutineScope EstadoMapa(cargando = false, error = "No se pudieron leer los datos del mapa ($motivo). Revisa tu conexión.")
        }
        val parciales = mutableListOf<String>()
        rAvisos.exceptionOrNull()?.let { parciales += "No se pudieron leer los avisos de SENAMHI (${it.message})." }
        rCaudales.exceptionOrNull()?.let { parciales += "No se pudieron leer los niveles de los ríos de ANA (${it.message})." }
        rCauces.exceptionOrNull()?.let { parciales += "No se pudieron leer los trazos de los ríos (${it.message})." }
        rVigilados.exceptionOrNull()?.let { parciales += "No se pudo leer el río Mashcón." }

        val ahora = System.currentTimeMillis()
        val chip = rTitular.getOrNull()?.dato?.let { ChipNivel(Nivel.desde(it.nivel), "${Nivel.desde(it.nivel).etiqueta} en $departamento") }
            ?: ChipNivel(Nivel.SIN_DATO, "Sin datos de $departamento")

        withContext(Dispatchers.Default) {
            // avisos de hoy
            val avisos = AvisosMapa.deHoy(rAvisos.getOrNull()?.dato ?: emptyList(), ahora).mapNotNull { a ->
                val geo = GeoJson.parsear(a.geojson) as? Geometria.Poligonos ?: return@mapNotNull null
                val caja = GeoJson.caja(geo) ?: return@mapNotNull null
                val ancla = a.anclas.firstOrNull { it.mayor && it.lat != null && it.lon != null } ?: a.anclas.firstOrNull { it.lat != null && it.lon != null }
                val centro = ancla?.let { Coord(it.lat!!, it.lon!!) } ?: GeoJson.centroideMayor(geo)
                AvisoDibujo(a, geo, caja, centro, AvisosMapa.glifo(a))
            }

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
            val avisosPorRio = senalesCauces.associateBy { it.rio_ana }
            val rios = mutableListOf<RioDibujo>()
            val estados = HashMap<String, EstadoRio>()
            val nombres = HashMap<String, String>()
            val cajas = HashMap<String, Caja>()
            for (r in emparejados.rios) {
                val hidro = avisosPorRio[r.fila.rio_ana]?.avisos_hidro ?: emptyList()
                val est = Cauces.estadoRio(r.lecturas, hidro, ahora)
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
                cargando = false, chip = chip, avisos = avisos, rios = rios, mashcon = mashcon, estacionesRio = estacionesRio,
                zonas = zonasMashcon, fuentes = fuentes, avisosParciales = parciales, deCache = deCache,
                obtenidoEn = listOfNotNull(rCaudales.getOrNull()?.obtenidoEn, rAvisos.getOrNull()?.obtenidoEn).minOrNull(),
                obtenidoAvisosEn = rAvisos.getOrNull()?.obtenidoEn,
            )
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
