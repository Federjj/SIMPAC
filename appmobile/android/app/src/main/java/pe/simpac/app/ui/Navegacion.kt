package pe.simpac.app.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalView
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import pe.simpac.app.ui.alertas.AlertasScreen
import pe.simpac.app.ui.componentes.Haptica
import pe.simpac.app.ui.componentes.LocalAvisador
import pe.simpac.app.ui.componentes.Transiciones
import pe.simpac.app.ui.componentes.rememberAvisador
import pe.simpac.app.ui.comunidad.ComunidadScreen
import pe.simpac.app.ui.comunidad.ReporteDetalleScreen
import pe.simpac.app.ui.comunidad.ReporteNuevoScreen
import pe.simpac.app.ui.cuenta.CuentaScreen
import pe.simpac.app.ui.inicio.InicioScreen
import pe.simpac.app.ui.mapa.MapaScreen

/** Las 5 pestanas de la barra inferior. "A donde acudir" es una seccion de Inicio y una capa del mapa. */
enum class Pestana(val ruta: String, val etiqueta: String, val icono: ImageVector) {
    INICIO("inicio", "Inicio", Icons.Filled.Home),
    ALERTAS("alertas", "Alertas", Icons.Filled.Warning),
    MAPA("mapa", "Mapa", Icons.Filled.Place),
    COMUNIDAD("comunidad", "Comunidad", Icons.Filled.ThumbUp),
    CUENTA("cuenta", "Cuenta", Icons.Filled.AccountCircle);

    companion object {
        /** Ruta que manda la notificacion ("/alertas", "/cuenta", "/comunidad") -> pestana. */
        fun desdeRuta(ruta: String?): Pestana = when (ruta?.trim()?.trimStart('/')?.substringBefore('/')?.substringBefore('?')) {
            "alertas" -> ALERTAS
            "cuenta" -> CUENTA
            "comunidad" -> COMUNIDAD
            "acudir", "", null -> INICIO
            else -> MAPA
        }
    }
}

/** Rutas dentro de la pestana Comunidad. */
object Rutas {
    const val REPORTE_NUEVO = "comunidad/nuevo"
    const val REPORTE = "comunidad/{id}"
    fun reporte(id: String) = "comunidad/$id"
}

/**
 * Marco de la app: barra inferior + NavHost + snackbar global (`LocalAvisador`, encima de la barra).
 * pestanaInicial cambia cuando llega una notificacion. Las pestanas se cruzan con un fundido de 200 ms
 * y las pantallas de comunidad (nuevo y detalle) entran deslizando desde la derecha (Transiciones).
 */
@Composable
fun AppSimpac(pestanaInicial: Pestana?, vecesPedida: Int) {
    val navController = rememberNavController()
    val compartido: EstadoCompartido = viewModel()
    val entrada by navController.currentBackStackEntryAsState()
    val rutaActual = entrada?.destination?.route
    val avisador = rememberAvisador()
    val vista = LocalView.current

    fun ir(p: Pestana) {
        // volver a tocar la pestana actual no hace nada: navegar a la misma ruta reemplaza la entrada
        // de la pila y la pantalla (el mapa, por ejemplo) cambiaria de ciclo de vida sin recrearse
        if (navController.currentBackStackEntry?.destination?.route == p.ruta) return
        navController.navigate(p.ruta) {
            popUpTo(navController.graph.findStartDestination().id) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }
    fun abrirReporte(id: String) { navController.navigate(Rutas.reporte(id)) { launchSingleTop = true } }
    fun volver() { if (!navController.popBackStack()) ir(Pestana.COMUNIDAD) }
    fun verEnMapa(lat: Double, lon: Double) { compartido.pedirEncuadre(EncuadreMapa(null, lat, lon)); ir(Pestana.MAPA) }

    LaunchedEffect(vecesPedida) {
        if (pestanaInicial != null && vecesPedida > 0) ir(pestanaInicial)
    }
    // El mapa abre el detalle de un reporte al tocar su pin (contrato con ui/mapa)
    DisposableEffect(navController) {
        compartido.abrirReporte = { id -> abrirReporte(id) }
        onDispose { compartido.abrirReporte = null }
    }

    CompositionLocalProvider(LocalAvisador provides avisador) {
        Scaffold(
            snackbarHost = { SnackbarHost(avisador.estado) },
            bottomBar = {
                NavigationBar {
                    Pestana.entries.forEach { p ->
                        NavigationBarItem(
                            selected = rutaActual?.substringBefore('/') == p.ruta,
                            onClick = { Haptica.toque(vista); ir(p) },
                            icon = { Icon(p.icono, contentDescription = null) },
                            label = { Text(p.etiqueta) },
                        )
                    }
                }
            },
        ) { relleno ->
            NavHost(
                navController,
                startDestination = Pestana.INICIO.ruta,
                modifier = Modifier.padding(relleno),
                enterTransition = Transiciones.entrarPestana,
                exitTransition = Transiciones.salirPestana,
                popEnterTransition = Transiciones.entrarPestana,
                popExitTransition = Transiciones.salirPestana,
            ) {
                composable(Pestana.INICIO.ruta) {
                    InicioScreen(
                        irAlertas = { ir(Pestana.ALERTAS) },
                        irReportar = { ir(Pestana.COMUNIDAD); navController.navigate(Rutas.REPORTE_NUEVO) { launchSingleTop = true } },
                        irMapa = { e -> compartido.pedirEncuadre(e); ir(Pestana.MAPA) },
                    )
                }
                composable(Pestana.ALERTAS.ruta) { AlertasScreen() }
                composable(Pestana.MAPA.ruta) { MapaScreen(compartido) }
                composable(Pestana.COMUNIDAD.ruta) {
                    ComunidadScreen(
                        irNuevo = { navController.navigate(Rutas.REPORTE_NUEVO) { launchSingleTop = true } },
                        abrirReporte = { abrirReporte(it) },
                        irCuenta = { ir(Pestana.CUENTA) },
                        verEnMapa = { lat, lon -> verEnMapa(lat, lon) },
                    )
                }
                composable(
                    Rutas.REPORTE_NUEVO,
                    enterTransition = Transiciones.entrarDetalle,
                    exitTransition = Transiciones.salirDetalle,
                    popEnterTransition = Transiciones.popEntrarDetalle,
                    popExitTransition = Transiciones.popSalirDetalle,
                ) {
                    ReporteNuevoScreen(
                        volver = { volver() },
                        abrirReporte = { id -> navController.navigate(Rutas.reporte(id)) { popUpTo(Rutas.REPORTE_NUEVO) { inclusive = true } } },
                        irCuenta = { ir(Pestana.CUENTA) },
                    )
                }
                composable(
                    Rutas.REPORTE,
                    arguments = listOf(navArgument("id") { type = NavType.StringType }),
                    enterTransition = Transiciones.entrarDetalle,
                    exitTransition = Transiciones.salirDetalle,
                    popEnterTransition = Transiciones.popEntrarDetalle,
                    popExitTransition = Transiciones.popSalirDetalle,
                ) { e ->
                    ReporteDetalleScreen(
                        id = e.arguments?.getString("id") ?: "",
                        volver = { volver() },
                        irCuenta = { ir(Pestana.CUENTA) },
                        verEnMapa = { lat, lon -> verEnMapa(lat, lon) },
                    )
                }
                composable(Pestana.CUENTA.ruta) { CuentaScreen(abrirReporte = { abrirReporte(it) }) }
            }
        }
    }
}
