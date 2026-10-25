package pe.simpac.app.ui.mapa

import android.Manifest
import android.annotation.SuppressLint
import android.net.Uri
import android.view.ViewGroup
import android.webkit.GeolocationPermissions
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import pe.simpac.app.BuildConfig
import pe.simpac.app.SimpacApp
import pe.simpac.app.ubicacion.Ubicacion
import pe.simpac.app.ui.EstadoCompartido
import pe.simpac.app.ui.Intents

/**
 * El mapa es la misma web de SIMPAC dentro de un WebView: JavaScript y geolocalizacion habilitados,
 * sin acceso a archivos locales; la geolocalizacion solo se concede al origen de la WEB configurada.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun MapaScreen(compartido: EstadoCompartido) {
    val contexto = LocalContext.current
    val ajustes = remember { (contexto.applicationContext as SimpacApp).contenedor.ajustes }
    val conf by ajustes.flujo.collectAsStateWithLifecycle(initialValue = null)
    val rutaPedida by compartido.rutaWeb.collectAsStateWithLifecycle()
    var error by remember { mutableStateOf<String?>(null) }
    var webView by remember { mutableStateOf<WebView?>(null) }
    var puedeVolver by remember { mutableStateOf(false) }
    var permisoPendiente by remember { mutableStateOf<Pair<String, GeolocationPermissions.Callback>?>(null) }

    val pedirPermiso = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { r ->
        val ok = r[Manifest.permission.ACCESS_FINE_LOCATION] == true || r[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        permisoPendiente?.let { (origen, cb) -> cb.invoke(origen, ok, false) }
        permisoPendiente = null
    }

    val webUrl = conf?.webUrl ?: return
    val origenWeb = remember(webUrl) { origenDe(webUrl) }

    BackHandler(enabled = puedeVolver) { webView?.goBack() }

    LaunchedEffect(rutaPedida, webView) {
        val ruta = rutaPedida ?: return@LaunchedEffect
        val wv = webView ?: return@LaunchedEffect
        wv.loadUrl(webUrl.trimEnd('/') + "/" + ruta.trimStart('/'))
        compartido.rutaWebAtendida()
    }

    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Mapa de SIMPAC", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            OutlinedButton(onClick = { error = null; webView?.reload() }) { Text("Recargar") }
            OutlinedButton(onClick = { Intents.abrirNavegador(contexto, webView?.url ?: webUrl) }) { Text("Navegador") }
        }
        Box(Modifier.fillMaxSize()) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    WebView(ctx).apply {
                        // Alto MATCH_PARENT explicito: AndroidView mete el WebView en un ViewGroup que, si la
                        // vista no trae LayoutParams, le pone WRAP_CONTENT. Con alto WRAP_CONTENT Chromium
                        // (AwLayoutSizer, force_zero_layout_height) resuelve 100vh y height:100% como 0 px, y
                        // la web (html/body/#root al 100 % y el mapa con h-screen) quedaba con alto 0: el DOM
                        // se cargaba completo pero no se pintaba nada. La app de Capacitor no lo sufria porque
                        // su WebView viene del XML con match_parent.
                        layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        // La web trae su meta viewport (width=device-width): asi el WebView la acomoda al ancho real
                        settings.useWideViewPort = true
                        settings.loadWithOverviewMode = true
                        settings.setGeolocationEnabled(true)
                        settings.allowFileAccess = false
                        settings.allowContentAccess = false
                        settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
                        // Inspeccion con chrome://inspect solo en debug (adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>)
                        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
                        webViewClient = object : WebViewClient() {
                            override fun onPageFinished(view: WebView, url: String?) { puedeVolver = view.canGoBack() }
                            override fun onReceivedError(view: WebView, request: WebResourceRequest, err: WebResourceError) {
                                if (request.isForMainFrame) error = "La web de SIMPAC no respondió en $webUrl (${err.description}). Revisa la dirección en Cuenta > Ajustes o tu conexión."
                            }
                            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                                // Los enlaces a otros sitios (fuentes oficiales) se abren en el navegador
                                val destino = request.url
                                return if (origenDe(destino.toString()) != origenWeb) { Intents.abrirNavegador(ctx, destino.toString()); true } else false
                            }
                        }
                        webChromeClient = object : WebChromeClient() {
                            override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
                                val mismoOrigen = origin.trimEnd('/') == origenWeb
                                when {
                                    !mismoOrigen -> callback.invoke(origin, false, false)
                                    Ubicacion.tienePermiso(ctx) -> callback.invoke(origin, true, false)
                                    else -> { permisoPendiente = origin to callback; pedirPermiso.launch(Ubicacion.PERMISOS) }
                                }
                            }
                        }
                        loadUrl(webUrl)
                        webView = this
                    }
                },
            )
            error?.let { mensaje ->
                Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("No se pudo abrir el mapa", style = MaterialTheme.typography.titleLarge)
                    Text(mensaje, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center, modifier = Modifier.padding(vertical = 10.dp))
                    Button(onClick = { error = null; webView?.loadUrl(webUrl) }) { Text("Reintentar") }
                }
            }
        }
    }
}

/** "http://10.0.2.2:8080/alertas" -> "http://10.0.2.2:8080" (esquema + host + puerto). */
fun origenDe(url: String): String {
    val u = Uri.parse(url)
    val esquema = u.scheme ?: return url
    val puerto = if (u.port > 0 && !((esquema == "http" && u.port == 80) || (esquema == "https" && u.port == 443))) ":${u.port}" else ""
    return "$esquema://${u.host}$puerto"
}
