package pe.simpac.app.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import pe.simpac.app.ui.acudir.AcudirScreen
import pe.simpac.app.ui.alertas.AlertasScreen
import pe.simpac.app.ui.cuenta.CuentaScreen
import pe.simpac.app.ui.inicio.InicioScreen
import pe.simpac.app.ui.mapa.MapaScreen

/** Las 5 pestanas de la barra inferior. */
enum class Pestana(val ruta: String, val etiqueta: String, val icono: ImageVector) {
    INICIO("inicio", "Inicio", Icons.Filled.Home),
    ALERTAS("alertas", "Alertas", Icons.Filled.Warning),
    MAPA("mapa", "Mapa", Icons.Filled.Place),
    ACUDIR("acudir", "Acudir", Icons.Filled.Call),
    CUENTA("cuenta", "Cuenta", Icons.Filled.AccountCircle);

    companion object {
        /** Ruta que manda la notificacion ("/alertas", "/cuenta") -> pestana. */
        fun desdeRuta(ruta: String?): Pestana = when (ruta?.trim()?.trimStart('/')?.substringBefore('/')?.substringBefore('?')) {
            "alertas" -> ALERTAS
            "cuenta" -> CUENTA
            "acudir" -> ACUDIR
            "", null -> INICIO
            else -> MAPA
        }
    }
}

/** Marco de la app: barra inferior + NavHost. pestanaInicial cambia cuando llega una notificacion. */
@Composable
fun AppSimpac(pestanaInicial: Pestana?, vecesPedida: Int) {
    val navController = rememberNavController()
    val compartido: EstadoCompartido = viewModel()
    val entrada by navController.currentBackStackEntryAsState()
    val rutaActual = entrada?.destination?.route

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

    LaunchedEffect(vecesPedida) {
        if (pestanaInicial != null && vecesPedida > 0) ir(pestanaInicial)
    }

    Scaffold(
        bottomBar = {
            NavigationBar {
                Pestana.entries.forEach { p ->
                    NavigationBarItem(
                        selected = rutaActual == p.ruta,
                        onClick = { ir(p) },
                        icon = { Icon(p.icono, contentDescription = null) },
                        label = { Text(p.etiqueta) },
                    )
                }
            }
        },
    ) { relleno ->
        NavHost(navController, startDestination = Pestana.INICIO.ruta, modifier = Modifier.padding(relleno)) {
            composable(Pestana.INICIO.ruta) {
                InicioScreen(
                    irAlertas = { ir(Pestana.ALERTAS) },
                    irAcudir = { ir(Pestana.ACUDIR) },
                    irMapa = { e -> compartido.pedirEncuadre(e); ir(Pestana.MAPA) },
                )
            }
            composable(Pestana.ALERTAS.ruta) { AlertasScreen() }
            composable(Pestana.MAPA.ruta) { MapaScreen(compartido) }
            composable(Pestana.ACUDIR.ruta) { AcudirScreen() }
            composable(Pestana.CUENTA.ruta) { CuentaScreen() }
        }
    }
}
