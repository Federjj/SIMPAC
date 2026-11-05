import java.io.FileInputStream
import java.net.URI
import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.compose.compiler)
    alias(libs.plugins.kotlin.serialization)
}

// Firebase Cloud Messaging: el plugin google-services exige app/google-services.json (se descarga
// de la consola de Firebase y NO se versiona). Sin ese archivo la app compila igual y los
// interruptores de notificaciones dicen "Notificaciones no configuradas en esta instalacion".
val hayGoogleServices = file("google-services.json").exists()
if (hayGoogleServices) {
    apply(plugin = libs.plugins.google.services.get().pluginId)
}

// URL del proyecto y publishable key de Supabase (publicas por diseno; la RLS protege los datos).
// Orden: variables de entorno SIMPAC_SUPABASE_URL / SIMPAC_SUPABASE_KEY, frontend/.env y, si no,
// frontend/.env.example. Asi no se copia ninguna clave a un archivo de este proyecto.
fun leerVariableVite(nombre: String): String? {
    val raiz = rootProject.projectDir.parentFile.parentFile   // appmobile/android -> raiz del repo
    for (archivo in listOf(File(raiz, "frontend/.env"), File(raiz, "frontend/.env.example"))) {
        if (!archivo.exists()) continue
        archivo.readLines().forEach { linea ->
            val limpia = linea.trim()
            if (limpia.startsWith("$nombre=")) return limpia.removePrefix("$nombre=").trim().trim('"')
        }
    }
    return null
}
val supabaseUrl = System.getenv("SIMPAC_SUPABASE_URL") ?: leerVariableVite("VITE_SUPABASE_URL") ?: ""
val supabaseKey = System.getenv("SIMPAC_SUPABASE_KEY") ?: leerVariableVite("VITE_SUPABASE_PUBLISHABLE_KEY") ?: ""

// Direcciones de la API y de la web que la app trae de fabrica (BuildConfig.API_URL / WEB_URL; la
// persona las puede cambiar en Cuenta > Ajustes). Se dan como propiedades de Gradle, en
// gradle.properties o por linea de comandos (-Psimpac.apiUrl=... -Psimpac.webUrl=...).
//   debug:   si no se definen, el emulador apunta al Docker de la PC (10.0.2.2).
//   release: son obligatorias y por https (red_release.xml no deja http salvo a 10.0.2.2/localhost);
//            sin ellas el build falla antes de empaquetar, para no publicar una app apuntando al emulador.
val apiEmulador = "http://10.0.2.2:8000"
val webEmulador = "http://10.0.2.2:8080"
fun propiedadDireccion(nombre: String): String? =
    providers.gradleProperty(nombre).orNull?.trim()?.trimEnd('/')?.takeIf { it.isNotBlank() }
val apiUrlConfigurada = propiedadDireccion("simpac.apiUrl")
val webUrlConfigurada = propiedadDireccion("simpac.webUrl")
val mensajeDireccionesRelease = "Release sin direcciones de produccion: define simpac.apiUrl y simpac.webUrl " +
    "en gradle.properties o -P (por ejemplo -Psimpac.apiUrl=https://<api>.up.railway.app " +
    "-Psimpac.webUrl=https://<web>.vercel.app). Deben ir por https: red_release.xml no permite http " +
    "salvo hacia 10.0.2.2 y localhost."
fun esDireccionDeRelease(url: String): Boolean {
    val uri: URI = runCatching { URI(url) }.getOrNull() ?: return false
    val host = uri.host ?: return false
    return uri.scheme == "https" || host in setOf("10.0.2.2", "localhost", "127.0.0.1")
}
val direccionesReleaseValidas = apiUrlConfigurada != null && webUrlConfigurada != null &&
    esDireccionDeRelease(apiUrlConfigurada) && esDireccionDeRelease(webUrlConfigurada)

// Firma del release: key.properties (no versionado) o variables de entorno; sin ninguno, sin firmar.
val keyProperties = Properties().apply {
    val archivo = rootProject.file("key.properties")
    if (archivo.exists()) FileInputStream(archivo).use { load(it) }
}
val storeFileRuta = keyProperties.getProperty("storeFile") ?: System.getenv("SIMPAC_KEYSTORE_FILE")
val storePasswordValor = keyProperties.getProperty("storePassword") ?: System.getenv("SIMPAC_KEYSTORE_PASSWORD")
val keyAliasValor = keyProperties.getProperty("keyAlias") ?: System.getenv("SIMPAC_KEY_ALIAS")
val keyPasswordValor = keyProperties.getProperty("keyPassword") ?: System.getenv("SIMPAC_KEY_PASSWORD")
val hayFirma = !storeFileRuta.isNullOrBlank() && !storePasswordValor.isNullOrBlank() &&
    !keyAliasValor.isNullOrBlank() && !keyPasswordValor.isNullOrBlank()

android {
    namespace = "pe.simpac.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "pe.simpac.app"      // el mismo que la app de Capacitor: la reemplaza
        minSdk = 26
        targetSdk = 36
        versionCode = 2
        versionName = "2.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "SUPABASE_URL", "\"$supabaseUrl\"")
        buildConfigField("String", "SUPABASE_KEY", "\"$supabaseKey\"")
        buildConfigField("boolean", "FIREBASE_CONFIGURADO", hayGoogleServices.toString())
    }

    signingConfigs {
        if (hayFirma) {
            create("release") {
                storeFile = file(storeFileRuta!!)
                storePassword = storePasswordValor
                keyAlias = keyAliasValor
                keyPassword = keyPasswordValor
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (hayFirma) signingConfig = signingConfigs.getByName("release")
            // Solo https (y la API o la web locales por http si se declaran en red_release.xml)
            manifestPlaceholders["configRed"] = "@xml/red_release"
            // Direcciones de produccion obligatorias (la comprobacion de abajo detiene el build si faltan)
            buildConfigField("String", "API_URL", "\"${apiUrlConfigurada ?: ""}\"")
            buildConfigField("String", "WEB_URL", "\"${webUrlConfigurada ?: ""}\"")
        }
        debug {
            // Para el emulador y un telefono en la misma red: la API y la web locales van por http.
            manifestPlaceholders["configRed"] = "@xml/red_debug"
            // Sin propiedades, el emulador apunta al Docker de la PC
            buildConfigField("String", "API_URL", "\"${apiUrlConfigurada ?: apiEmulador}\"")
            buildConfigField("String", "WEB_URL", "\"${webUrlConfigurada ?: webEmulador}\"")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
        aidl = false
        shaders = false
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

kotlin {
    jvmToolchain(17)
}

// Comprobacion del release: si el grafo va a empaquetar un release (assembleRelease, bundleRelease,
// packageRelease...), falla antes de ejecutar nada si faltan simpac.apiUrl / simpac.webUrl o no van
// por https. Las pruebas JVM (testDebugUnitTest, testReleaseUnitTest) y el debug no pasan por aqui.
val tareasQueEmpaquetanRelease = setOf("assembleRelease", "bundleRelease", "packageRelease", "packageReleaseBundle")
gradle.taskGraph.whenReady {
    val empaquetaRelease = allTasks.any { it.project.path == project.path && it.name in tareasQueEmpaquetanRelease }
    if (empaquetaRelease && !direccionesReleaseValidas) {
        throw GradleException(
            "$mensajeDireccionesRelease Recibido: simpac.apiUrl=${apiUrlConfigurada ?: "(sin definir)"} " +
                "simpac.webUrl=${webUrlConfigurada ?: "(sin definir)"}",
        )
    }
    if (empaquetaRelease) logger.lifecycle("Release de SIMPAC con API $apiUrlConfigurada y web $webUrlConfigurada")
}

dependencies {
    val composeBom = platform(libs.androidx.compose.bom)
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)

    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.core)
    debugImplementation(libs.androidx.compose.ui.tooling)

    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.security.crypto)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.coroutines.play.services)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.okhttp)
    implementation(libs.play.services.location)

    // La dependencia de FCM va siempre; sin google-services.json FirebaseApp no se inicializa y
    // la app lo detecta (push/PushSimpac.kt).
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.messaging)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)

    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    androidTestImplementation(libs.androidx.test.core)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.espresso.core)
}
