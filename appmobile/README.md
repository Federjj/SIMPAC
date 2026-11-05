# SIMPAC — App Android nativa (Kotlin + Jetpack Compose)

La app Android de SIMPAC es una **app nativa en Kotlin con Jetpack Compose** (HU-20 y HU-21 del
backlog) que vive en **`appmobile/android/`**. Lee los mismos datos oficiales que la web (Supabase con
la publishable key y la API de solo lectura de FastAPI), muestra el semáforo de tu zona con su titular
en lenguaje claro, las alertas vigentes, a dónde acudir cerca de ti, un **mapa nativo** (osmdroid,
sin WebView) con los avisos de SENAMHI, los ríos del país con su estado, las zonas que podrían
inundarse, las estaciones de SENAMHI y los puntos de "A dónde acudir", y recibe **notificaciones push
por Firebase Cloud Messaging (FCM)** cuando tu departamento entra en alerta o emergencia.

Reemplaza a la app anterior hecha con Capacitor (la web empaquetada): tiene el mismo `applicationId`
(`pe.simpac.app`), así que instalarla sobre la otra la sustituye. El proyecto de Capacitor se retiró del
repo el 24-10-2026.

## Qué hace (5 pestañas)

| Pestaña | Qué muestra | De dónde sale |
|---|---|---|
| **Inicio** | Semáforo grande del departamento (elegido o detectado por GPS), `titular_corto` y detalle con "Generado el <hora>" y origen (reglas o modelo), chips con cuántas alertas oficiales hay y el río con señales, estado El Niño del ENFEN, pronóstico de 3 días de la localidad más cercana, botones "Llamar 105" y "Llamar 116", fuentes con hora y el pie "Información referencial..." | `titular_zona`, `alerta_actual`, `rio_cauce_mapa` + `rio_cauce_senal`, `pronostico_vigente` (caja alrededor de la posición), `estacion` (para saber el departamento por GPS) y `GET /api/snapshot` (contexto ENFEN) |
| **Alertas** | Lista ordenada emergencia > alerta > aviso, oficiales primero; la "Lluvia medida" va aparte y marcada como no oficial; filtro "Mi zona / Todo el país"; cada tarjeta con color + etiqueta, referencia, zona, detalle, hora y fuente; vacío amable con la hora de la revisión | `alerta_actual` |
| **Mapa** | Mapa **nativo** con osmdroid (ver "Mapa nativo"): chip arriba con el nivel de tu zona, 5 capas con interruptor (avisos de SENAMHI, ríos, zonas que podrían inundarse, estaciones de SENAMHI, a dónde acudir), nombres de los ríos desde zoom 11, punto azul de tu ubicación y botón "centrar"; al tocar un área, un río, una zona o un punto se abre una hoja inferior de Material 3 en lenguaje claro con su fuente y hora; "Ver el aviso oficial" y "Ver el aviso de SENAMHI" abren el navegador. Solo la barra inferior de la app: no hay barras duplicadas | `aviso_vigente`, `caudal_actual`, `rio_vigilado_mapa`, `rio_zona_mapa`, `rio_senal`, `rio_cauce_mapa` (`cauce_lejos` y `cauce`), `rio_cauce_senal`, `rio_cauce_zona_mapa`, `estacion`, `punto_acudir`, `titular_zona`; tiles de Stadia Maps (o de OSM sin llave) |
| **Acudir** | Números de emergencia (105, 116, 115, 106 con su salvedad) y los 3 puntos más cercanos (salud 24 h si está a menos de 15 km o el más cercano, comisaría, bomberos) en una caja de 30 km alrededor de la posición (GPS o centro del departamento), con distancia en línea recta, teléfono (abre el marcador), "Cómo llegar" (`geo:`), fuente y fecha del dato | `punto_acudir` |
| **Cuenta** | Explica que las cuentas se manejan en la web (la sesión no se comparte); "Abrir mi cuenta en la web" y "Comunidad" abren `<WEB>/cuenta` y `<WEB>/comunidad` en el **navegador del teléfono** (`ACTION_VIEW`); Ajustes: departamento, direcciones de la API y la WEB, interruptor de notificaciones por zona; "Acerca de" con fuentes y licencias | DataStore (ajustes) y FCM |

Estados cubiertos: cargando, error con "Reintentar", **dato desactualizado** (el titular lleva más
de 3 h sin revisarse: franja amarilla) y **sin conexión** (cada consulta guarda su última respuesta
en disco y, si la red falla, se muestra con franja naranja y la hora en que se guardó). Nunca se
muestra "Normal" por algo no medido: sin titular el semáforo dice "Sin datos" y lo explica.

Colores del semáforo iguales a la web (`dominio/Nivel.kt`): normal `#15803D`, aviso `#EAB308`
(tinta `#A16207`), alerta `#F58E27` (`#C2410C`), emergencia `#DB0404` (`#B91C1C`), sin dato gris.
Siempre color + etiqueta. Los colores del mapa (`dominio/Paleta.kt`) son los de
`frontend/src/map/palette.js`: cauce azul `#1C7ED6` tranquilo, ámbar `#EAB308`, naranja `#F58E27`,
rojo `#DB0404`, gris `#94A3B8`; zonas azul `#1D4ED8` sin señales, ámbar, naranja, rojo (trazo oscuro
`#1E3A8A`, `#A16207`, `#C2410C`, `#991B1B`); acudir salud `#0F766E`, comisaría `#1D4ED8`, bomberos `#991B1B`.

## Mapa nativo (pestaña Mapa)

Hasta el 04-11-2026 la pestaña Mapa era la web dentro de un `WebView` (dos barras de navegación, todo
apretado). Desde esa fecha es un **mapa nativo con osmdroid 6.1.20** (`org.osmdroid:osmdroid-android`,
Apache 2.0) dentro de Compose (`AndroidView` con el `MapView` en `remember`, `onResume`/`onPause` con el
ciclo de vida y `onDetach` al salir), que replica la lógica y los colores de la web (`lib/cauces.js`,
`lib/zonaRio.js`, `lib/lenguaje.js textoRio`, `map/palette.js`, `map/layers/*.js`):

| Capa (interruptor en la hoja "Capas" y chip en la barra de abajo) | Qué dibuja | Fuente | Desde zoom |
|---|---|---|---|
| Avisos de SENAMHI (prendida) | Polígonos de `aviso_vigente` que rigen hoy (hora del Perú) con relleno del color del nivel al 35 % y borde (amarillo `#EAB308`, naranja `#F58E27`, rojo `#DB0404`); insignia con el glifo del fenómeno (gota, gota con rayo, copo, termómetro, viento) en el ancla mayor o el centroide; solo se dibujan los que tocan la vista. Hoja: título en palabras, nivel ("Naranja (nivel 3 de 4)"), texto del día, qué hacer, vigencia, departamentos, "Ver el aviso oficial" | SENAMHI (áreas simplificadas, `backend` tarea `avisos`) | 5 |
| Ríos (prendida) | Los ~100 ríos de `rio_cauce_mapa.cauce_lejos` (~50 m, 35 000 vértices) con halo blanco y el color del estado de `Cauces.estadoRio` (la peor estación de `caudal_actual` o, si es más alto, el aviso hidrológico de `rio_cauce_senal`); el Mashcón desde `rio_vigilado_mapa.cauce` con sus afluentes; discos de las estaciones de ANA con el color del estado; nombres de hasta 8 ríos a la vista desde zoom 11; trazo fino (`cauce`, ~6 m) por río visible desde zoom 13. Hoja: "Río X - tranquilo 0.42 m³/s (ANA, hoy 20:00)", umbrales de alerta y emergencia, frase y acción, aviso hidrológico si manda, fuente del trazo | ANA (niveles y GeoSNIRH), SENAMHI (avisos hidrológicos), OSM (Mashcón) | 5 (simplificado con Douglas-Peucker por debajo de zoom 10) |
| Zonas que podrían inundarse (prendida) | `rio_zona_mapa` (Mashcón: estimadas bajo_2m rayada con borde oscuro y bajo_3m lisa tenue; estudio INDECI-PNUD 2005 lisa) y `rio_cauce_zona_mapa` (40 zonas de 20 ríos), con el color del nivel de la zona de hoy; se piden solo por los ríos cuya caja toca la vista (nunca el país entero). Hoja: "Zona que podría inundarse si el río se desborda - estimación de SIMPAC con el relieve (Copernicus), no es un mapa oficial", método, fuente, licencia y atribución | SIMPAC con Copernicus GLO-30; INDECI-PNUD 2005 | 12 |
| Estaciones de SENAMHI (apagada) | Puntos pequeños (M azul claro `#3BA5EB`, H azul `#3B3BEB`) por caja alrededor de la vista. Hoja: nombre, tipo, departamento, código | SENAMHI | 10 |
| A dónde acudir (apagada) | Marcadores por tipo con glifo (cruz, escudo, llama) por caja alrededor de la vista. Hoja: nombre, categoría, "Atiende las 24 horas, según la fuente" solo si la fuente lo dice, dónde, "Llamar" (`ACTION_DIAL`), "Cómo llegar" (`geo:`), fuente y fecha | SUSALUD RENIPRESS, MININTER vía CENEPRED, CGBVP | 11 |
| Tu ubicación | Punto azul con halo (permiso pedido en Inicio) y botón flotante "centrar"; al abrir, el mapa centra en tu punto o en la capital del departamento elegido (zoom 13). Desde Inicio, "Ver el río en el mapa" lleva a la pestaña Mapa encuadrando tu punto y el cauce del río destacado | GPS del teléfono | - |

Los interruptores se recuerdan en DataStore (`Ajustes.capasMapa`; de fábrica avisos, zonas y ríos, como
la web). Todo el trabajo de red y parseo va fuera del hilo principal (`MapaViewModel`, `viewModelScope`
+ `Dispatchers.IO`/`Default`); al salir de la pestaña el ViewModel se limpia y cancela sus corrutinas.
El parser GeoJSON (`dominio/GeoJson.kt`: Point, LineString, MultiLineString, Polygon, MultiPolygon,
Feature y FeatureCollection; caja, centroide, punto en polígono, simplificación Douglas-Peucker) y la
lógica de ríos (`dominio/Cauces.kt`) tienen pruebas JVM con los mismos casos que `lib/cauces.test.js`.
Caché en disco con plazo: 10 min para ríos, zonas, estaciones y acudir; 5 min para avisos y señales.

**Tiles.** Con `BuildConfig.STADIA_KEY` (propiedad de Gradle `simpac.stadiaKey` o variable de entorno
`SIMPAC_STADIA_KEY`) usa Stadia Maps *Alidade Smooth*
(`https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png?api_key=...`, `@2x` en pantallas
densas) con la atribución visible abajo "(c) Stadia Maps (c) OpenMapTiles (c) OpenStreetMap - Datos:
SENAMHI, ANA". **Sin llave** (compilación de desarrollo) cae al mapa base de OpenStreetMap (MAPNIK) con
`User-Agent = applicationId`: sirve para desarrollar, pero **para distribuir la app hace falta la llave**
(la política de uso de los tiles de OSM no admite apps publicadas; Gradle avisa al empaquetar un release
sin ella). La llave es pública en el navegador de la web, pero **no se versiona**: va por
`-Psimpac.stadiaKey=...` o en un `gradle.properties` local (nunca en el repo). La caché de tiles vive en
`cacheDir/osmdroid/tiles` (hasta 120 MB; `Configuration.getInstance().osmdroidTileCache`).

**Límites.** Los nombres de los ríos van en una etiqueta recta sobre el tramo visible (osmdroid no
escribe texto a lo largo de la línea como la web); los rótulos «zona que podría inundarse», la faja
marginal de ANA, los desbordes pasados, el pronóstico por localidad, la lluvia por estación y las capas
de El Niño siguen solo en la web. Con varias partes en el trazo fino de un río, se usa la primera por
parte del trazo lejano. Los botones "+" y "−" de zoom van siempre visibles arriba a la izquierda (como
el control de Leaflet en la web). Rendimiento: los ríos fuera de la vista no se dibujan, el trazo se
simplifica por zoom (Douglas-Peucker) y los avisos solo se dibujan si tocan la vista. En el emulador
Pixel_7a con GPU por software (`-gpu swiftshader_indirect`) todos los cuadros son lentos, también sin
mapa: mediana de 97 ms al desplazar Inicio, 250 ms al arrastrar el mapa a zoom 13 y 500 ms a zoom 7
(`adb shell dumpsys gfxinfo pe.simpac.app`, 04-11-2026); en un teléfono con GPU real va acelerado por
hardware. Ese emulador tiene además `/data` casi lleno (392 MB libres): `installd` purga la caché de
tiles y osmdroid anota `SQLITE_READONLY_DBMOVED` en logcat, sin romper el mapa. **Falta probarlo en un
teléfono real.**

## Estructura

```
appmobile/android/
  settings.gradle.kts, build.gradle.kts, gradle.properties
  gradle/libs.versions.toml            versiones (AGP 9.0.1, Kotlin 2.3.20, Compose BOM 2026.03.01...)
  gradle/wrapper/                      Gradle 9.1.0
  app/build.gradle.kts                 applicationId pe.simpac.app, minSdk 26, target/compileSdk 36,
                                       BuildConfig con la URL y la llave publica de Supabase y con las
                                       direcciones de fabrica API_URL / WEB_URL (propiedades simpac.apiUrl
                                       y simpac.webUrl; obligatorias y por https en release), firma,
                                       google-services SOLO si existe app/google-services.json
  app/google-services.json             (NO versionado) credenciales de Firebase, ver mas abajo
  app/src/main/AndroidManifest.xml     permisos INTERNET, ubicacion en primer plano, POST_NOTIFICATIONS;
                                       MainActivity, ServicioMensajes (FCM), canal/icono por defecto
  app/src/main/res/                    icono adaptable de la gota (el mismo de la app anterior), icono
                                       de notificacion, red_release.xml / red_debug.xml (https; http solo
                                       para 10.0.2.2/localhost en release, libre en debug)
  app/src/main/java/pe/simpac/app/
    SimpacApp.kt                       Application: contenedor (ajustes, repositorio, almacen seguro)
                                       y canal de notificaciones "alertas" (importancia alta)
    MainActivity.kt                    abre la pestana que pide la notificacion (extra "ruta")
    dominio/                           logica pura, probada en JVM: Nivel, Departamentos (slug del tema
                                       FCM), Geo (haversine, caja), Tiempo ("hace X", hora de Peru),
                                       Alertas (orden y oficialidad), Acudir, Pronostico, Rios,
                                       GeoJson (parser), Cauces (estado de los rios y zonas como la web),
                                       Paleta (colores del mapa), AvisosMapa (avisos de hoy y sus textos)
    data/                              Modelos (kotlinx.serialization), Http (OkHttp: Supabase REST y
                                       API), CacheDisco (ultima respuesta por consulta), Ajustes
                                       (DataStore), AlmacenSeguro (EncryptedSharedPreferences para el
                                       token de FCM), Repositorio (todas las consultas)
    push/                              PushSimpac (temas "pais" y "zona_<slug>"), ServicioMensajes
    ubicacion/                         una lectura de ubicacion en primer plano (fused o LocationManager)
    ui/                                Navegacion (barra de 5), tema, componentes y las pantallas
                                       inicio/, alertas/, mapa/, acudir/, cuenta/ con sus ViewModel;
                                       ui/mapa/: MapaViewModel (datos y vista), GestorMapa (osmdroid:
                                       tiles, overlays, toques), IconosMapa (dibujos con Canvas),
                                       HojasMapa (hojas inferiores), MapaScreen (Compose)
  app/src/test/                        pruebas JVM (parseo, orden, distancia, slug, "hace X", acudir...)
  app/src/androidTest/                 prueba de Compose UI de la pantalla Inicio con datos falsos
```

La URL del proyecto y la publishable key de Supabase son públicas por diseño (la RLS protege los
datos). El `build.gradle.kts` las toma de las variables de entorno `SIMPAC_SUPABASE_URL` y
`SIMPAC_SUPABASE_KEY`, si no de `frontend/.env` y si no de `frontend/.env.example`; así ningún
archivo de este proyecto lleva una clave escrita.

Direcciones configurables (Cuenta > Ajustes): la app trae de fábrica las que le dio Gradle al
compilar (`BuildConfig.API_URL` y `BuildConfig.WEB_URL`, propiedades `simpac.apiUrl` y
`simpac.webUrl`; ver "Direcciones de producción"). En debug sin propiedades son API
`http://10.0.2.2:8000` y WEB `http://10.0.2.2:8080`, que desde el emulador son el Docker de la PC. En
un teléfono real poner la IP de la PC (solo en la compilación debug, que permite http) o el dominio
real con https (el release solo permite http hacia 10.0.2.2 y localhost: `res/xml/red_release.xml`).
"Restablecer" vuelve a las direcciones de fábrica de esa compilación.

## Requisitos

- **JDK 21** (por ejemplo `C:\Program Files\Java\jdk-21.0.11`). El proyecto compila con toolchain 17
  dentro de ese JDK.
- **Android SDK** con `platforms;android-36`, `build-tools;36.0.0` y `platform-tools` (Android Studio
  > SDK Manager, o `sdkmanager "platforms;android-36" "build-tools;36.0.0" "platform-tools"`). Para
  el emulador, `emulator` y una imagen (`system-images;android-36;google_apis_playstore;x86_64`).
- Variables de entorno `JAVA_HOME` y `ANDROID_HOME`. En PowerShell (Windows):
  ```powershell
  $env:JAVA_HOME = "C:\Program Files\Java\jdk-21.0.11"
  $env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
  $env:Path = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:Path"
  ```
  En Git Bash / Linux / macOS: `export JAVA_HOME=...; export ANDROID_HOME=...`.
- La primera compilación baja Gradle 9.1.0 y las dependencias (unos 600 MB); después tarda segundos.
- En Windows, **`gradlew.bat` se corre desde PowerShell o CMD**, no desde Git Bash (la conversión de
  rutas de MSYS rompe los argumentos).

## Compilar y probar

Desde `appmobile/android/`:

| Comando | Qué hace |
|---|---|
| `.\gradlew.bat assembleDebug` | APK de prueba firmado con la llave de depuración: `app/build/outputs/apk/debug/app-debug.apk`. Con `-Psimpac.stadiaKey=<llave>` el mapa usa Stadia Maps; sin ella, OSM (solo para desarrollar) |
| `.\gradlew.bat testDebugUnitTest` | Pruebas JVM (`app/src/test`): parseo de las respuestas, orden de alertas, distancia, slug del tema, "hace X", regla de "a dónde acudir", pronóstico y ríos. Informe en `app/build/reports/tests/testDebugUnitTest/index.html` |
| `.\gradlew.bat connectedDebugAndroidTest` | Prueba de Compose UI (`app/src/androidTest/InicioScreenTest.kt`) en el emulador o teléfono conectado |
| `.\gradlew.bat bundleRelease -Psimpac.apiUrl=... -Psimpac.webUrl=...` | AAB para Play Console: `app/build/outputs/bundle/release/app-release.aab` (firmado si hay keystore). Sin las dos propiedades el build se detiene con un mensaje claro (ver "Direcciones de producción") |
| `.\gradlew.bat assembleRelease -Psimpac.apiUrl=... -Psimpac.webUrl=...` | APK release firmado para repartir fuera de la tienda (misma regla) |

Verificado el 2026-10-20 (Windows 10, PowerShell, JDK 21, SDK con `android-36`): `assembleDebug`
4 min la primera vez (descargas) y 18 s después; APK debug de 15 758 393 bytes; 22 pruebas JVM en
verde (`DominioTest` 16, `ModelosTest` 6). **Integración del 2026-10-24**: `.\gradlew.bat
testDebugUnitTest assembleDebug` BUILD SUCCESSFUL (22 pruebas, 0 fallas; 22 s con el daemon caliente
tras el ajuste del WebView en `MapaScreen.kt`), APK debug de **15 846 448 bytes (15,1 MiB)**.
**Mapa nativo del 2026-11-04**: `.\gradlew.bat testDebugUnitTest assembleDebug -Psimpac.apiUrl=...
-Psimpac.webUrl=... -Psimpac.stadiaKey=...` BUILD SUCCESSFUL (**39 pruebas JVM**, 0 fallas:
`DominioTest` 16, `ModelosTest` 6, `GeoJsonTest` 7, `CaucesTest` 10; 1 min con el daemon frío), APK
debug de **16 636 171 bytes (15,9 MiB)**, probado en el emulador Pixel_7a (ver CP-48 en
`docs/guia-medicion.md`).

Para instalar en un teléfono: *Opciones de desarrollador > Depuración USB*, conectarlo y
`adb install -r app/build/outputs/apk/debug/app-debug.apk`. Con el emulador encendido, lo mismo.

### Emulador sin ventana (como lo corre el equipo)

```bash
"$ANDROID_HOME/emulator/emulator" -avd Pixel_7a -no-window -gpu swiftshader_indirect -memory 3072 -no-snapshot -no-audio &
adb wait-for-device; adb shell getprop sys.boot_completed      # repetir hasta que diga 1
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -W -n pe.simpac.app/.MainActivity
adb exec-out screencap -p > captura.png
adb emu kill
```

Probado el 2026-10-20 con el AVD `Pixel_7a` (imagen Google Play x86_64, `-memory 3072`), con la
API y la web de Docker en la PC: Inicio con el semáforo "ALERTA" de Cajamarca, el titular corto y el
detalle de `titular_zona` con "Generado el 20 oct, 12:11", los chips "2 alertas oficiales" y del río,
"El Niño ahora: Alerta de El Niño Costero (CO 18-2026)", el pronóstico de 3 días de Cajamarca, los
botones 105/116 y las fuentes con hora; Alertas con el aviso 426 (naranja) y el de 24 h; Mapa con la
web cargada (el árbol de accesibilidad muestra el chip "AVISO NARANJA EN CAJAMARCA", la atribución de
Stadia/OSM y el formulario de `/cuenta`, tras unos 20 s), aunque ese día la captura del WebView salió
en blanco (causa y arreglo del 24-10 más abajo); Acudir con el Hospital II Cajamarca a 453 m (24 h), la Comisaría Central a 169 m y los bomberos; Cuenta con el interruptor de notificaciones
(pide el permiso de Android 13+ y se suscribe a `pais` y `zona_cajamarca`). Con la PC con poca RAM el
emulador muestra "System UI isn't responding": tocar *Wait*; no es un error de la app.

Repetido el 2026-10-24 en la integración (mismo AVD, Android 17 con Play services 26.16.60, APK
instalado con `adb install -r -g`, Docker de la PC reconstruido): Inicio con el disco amarillo "AVISO",
"Cajamarca: 3 avisos de SENAMHI por lluvias (el más alto, amarillo).", "Generado el 24 oct, 16:48
(hace 5 min), por reglas de SIMPAC con datos oficiales", chips "3 alertas oficiales" y "Río Cajamarca:
tranquilo en Jesús Túnel (0.58 m3/s)", El Niño (CO 18-2026); Alertas con los avisos 432 y 435 y la
lluvia de 24 h; Cuenta con el interruptor encendido ("Recibirás avisos de alerta o emergencia de
Cajamarca y del país"; `POST_NOTIFICATIONS` concedido, canal `alertas` de importancia 4); **la
notificación de prueba del worker llegó** y al tocarla abrió Alertas (ver abajo). El **Mapa (WebView)**
primero salía en blanco en la captura de ese emulador, con `-gpu swiftshader_indirect` y con `-gpu
host`, aunque la web cargaba entera (el árbol de accesibilidad traía los 92 nodos con sus medidas, una
página simple como el JSON de la API sí se pintaba en el mismo WebView y Chrome del emulador sí pintaba
la web). **Causa, encontrada el 24-10 con el DevTools remoto del WebView** (`adb forward tcp:9222
localabstract:webview_devtools_remote_<pid>` y `Runtime.evaluate`): `innerHeight` y
`documentElement.clientHeight` daban 705 px, pero `100vh` y `height: 100%` resolvían a 0, así que
`html`, `body`, `#root` y el `div.h-screen` de la web medían 0 px de alto y Leaflet no tenía dónde
pintar. Pasa porque el `WebView(ctx)` creado en el `factory` de `AndroidView` no trae `LayoutParams` y el
`ViewGroup` de Compose le asigna `WRAP_CONTENT`; con alto `WRAP_CONTENT` Chromium (AwLayoutSizer,
`force_zero_layout_height`) deja el alto de layout en 0 para que lo decida el contenido. La app de
Capacitor no lo sufría porque su WebView venía del XML con `match_parent`, y la misma web en ese APK
seguía dando `100vh = 845` con el mismo WebView 155. **Arreglo**: `layoutParams =
ViewGroup.LayoutParams(MATCH_PARENT, MATCH_PARENT)` en `ui/mapa/MapaScreen.kt`; con eso `100vh = 705`,
el contenedor de Leaflet mide 649 px, cargan 16 tiles y la captura del emulador muestra el mapa, el
chip "SIMPAC · Aviso amarillo en Cajamarca", el selector de ciudad, el pronóstico y la hoja "Mira cómo
está tu zona". Sin excepciones de `pe.simpac.app` en logcat.

## Notificaciones push (Firebase Cloud Messaging)

### Qué hace la app

- Sin `app/google-services.json` la app **compila y funciona igual**; en Cuenta el interruptor dice
  "Notificaciones no configuradas en esta instalación". El plugin `com.google.gms.google-services`
  se aplica en `app/build.gradle.kts` solo si ese archivo existe.
- Con el archivo, al prender el interruptor la app pide el permiso `POST_NOTIFICATIONS` (Android
  13+) y se suscribe a los temas **`pais`** y **`zona_<slug>`**, donde el slug es el departamento en
  minúsculas, sin tildes y con los espacios como guion bajo (`zona_cajamarca`, `zona_la_libertad`,
  `zona_madre_de_dios`, `zona_callao`, `zona_lima`; `dominio/Departamentos.kt slugTema`). Al cambiar
  de departamento se desuscribe del anterior; al apagar, de los dos.
- `push/ServicioMensajes.kt` muestra la notificación en el canal **`alertas`** (importancia alta) con
  la gota como ícono y el color del nivel, y al tocarla abre la app en la pestaña **Alertas** (extra
  `ruta`). Con la app en segundo plano la muestra FCM con el canal e ícono por defecto del manifest.
  El token de registro se guarda cifrado (`AlmacenSeguro`, EncryptedSharedPreferences).

### Qué envía el backend (contrato)

Solo niveles **alerta** y **emergencia** oficiales (nunca aviso ni lluvia medida) y un mensaje de
calma cuando la zona baja de alerta a normal/aviso:

```json
{
  "topic": "zona_cajamarca",
  "notification": { "title": "SIMPAC: ALERTA en Cajamarca", "body": "<titular_zona.titular_corto>" },
  "data": { "nivel": "alerta", "zona": "Cajamarca", "generado_en": "2026-10-20T17:11:02+00:00", "ruta": "/alertas" }
}
```
y `"title": "SIMPAC: vuelve la calma en Cajamarca"` al bajar. El tema `pais` recibe los mismos
mensajes de todas las zonas.

### Cómo activarlo (consola de Firebase)

1. En <https://console.firebase.google.com> crear el proyecto (el del equipo se llama **appsimpac**)
   o abrirlo. Google Analytics no hace falta.
2. *Agregar app > Android*: nombre del paquete **`pe.simpac.app`** (tiene que ser exactamente ese),
   apodo "SIMPAC"; la huella SHA-1 no es necesaria para FCM.
3. Descargar **`google-services.json`** y copiarlo en **`appmobile/android/app/google-services.json`**.
   Está en `.gitignore`: no se sube al repo; cada persona que compile lo pone en su copia.
4. Recompilar (`assembleDebug`). En la app, Cuenta > prender el interruptor y aceptar el permiso.
5. Para que el **backend** envíe: en la consola, *Configuración del proyecto > Cuentas de servicio >
   Generar nueva clave privada* (JSON del Admin SDK). Ese archivo es **secreto**: guardarlo fuera del
   repo y poner su ruta en el `.env` de la raíz como `FIREBASE_CREDENCIALES_ARCHIVO=C:/ruta/al/archivo.json`
   (`docker-compose.yml` lo monta de solo lectura en `/run/secrets/firebase.json` dentro del worker;
   luego `docker compose up -d worker`). El envío lo hace la tarea `push` del worker (cada 5 min,
   `backend/ingesta/push.py`) con la API HTTP v1 de FCM (`projects/appsimpac/messages:send`) a los
   temas de arriba; en `docker compose logs worker` cada corrida deja `Push: {... 'credenciales': True}`.
   Prueba desde el backend, con la app suscrita a Cajamarca:
   `docker compose exec worker python -m backend.ingesta.push --prueba --zona Cajamarca`.
   La primera corrida con credenciales avisa una vez las alertas vigentes de ese momento (la memoria
   `push_estado` arranca vacía); para evitarlo, sembrarla antes con
   `insert into push_estado (zona, nivel) select departamento, nivel from titular_zona where nivel <> 'sin_dato'`.
6. Prueba manual sin backend: en la consola, *Messaging > Nueva campaña > Notificaciones de Firebase*,
   título y texto, destino "Tema" `zona_cajamarca` (o `pais`), y en *Opciones adicionales* el canal
   `alertas` y los datos `ruta=/alertas`. Llega al emulador si tiene Google Play Services (la imagen
   `google_apis_playstore` los tiene).

**Verificado de extremo a extremo el 2026-10-24**: con la cuenta de servicio montada en el worker, la
primera corrida de la tarea `push` (21:58 UTC) envió una vez las 6 alertas vigentes del país (Tumbes
emergencia; Piura, Huancavelica, Lima, Ayacucho y Arequipa alerta) a `pais` y a sus `zona_<slug>`, y
las corridas siguientes no repitieron nada (`enviados 0`). `docker compose exec worker python -m
backend.ingesta.push --prueba --zona Cajamarca` llegó al emulador suscrito a `zona_cajamarca` (título
"SIMPAC: prueba en Cajamarca", canal `alertas`; la primera vez tardó unos minutos mientras FCM
propagaba la suscripción) y al tocarla la app abrió la pestaña Alertas. Detalle técnico de la tarea
(reglas, latido, siembra de `push_estado`): `docs/README-tecnico.md` §5.6.12.

## Direcciones de producción

La app lleva "de fábrica" la dirección de la API (FastAPI en Railway) y de la web (Vercel o Netlify);
la persona puede cambiarlas en Cuenta > Ajustes y "Restablecer" vuelve a las de fábrica. Se dan al
compilar como propiedades de Gradle (`simpac.apiUrl` y `simpac.webUrl`), que `app/build.gradle.kts`
expone como `BuildConfig.API_URL` y `BuildConfig.WEB_URL` (`data/Ajustes.kt` las usa como
predeterminadas):

| Variante | Sin propiedades | Con propiedades |
|---|---|---|
| debug | `http://10.0.2.2:8000` y `http://10.0.2.2:8080` (el Docker de la PC desde el emulador) | las que se den (sirve para probar la producción desde un APK debug) |
| release | **el build falla** antes de ejecutar nada: `Release sin direcciones de produccion: define simpac.apiUrl y simpac.webUrl en gradle.properties o -P (...)` | las que se den; deben ir por **https** (una `http://` hacia un dominio real también detiene el build, porque `red_release.xml` la bloquearía en el teléfono) |

Comandos, desde `appmobile/android/` en PowerShell, con el dominio público que dé Railway al servicio
`api` (*Settings > Networking > Generate Domain*) y el de Vercel del frontend:

```powershell
.\gradlew.bat bundleRelease   -Psimpac.apiUrl=https://<api>.up.railway.app -Psimpac.webUrl=https://<web>.vercel.app
.\gradlew.bat assembleRelease -Psimpac.apiUrl=https://<api>.up.railway.app -Psimpac.webUrl=https://<web>.vercel.app
```

Las mismas dos líneas se pueden dejar en `appmobile/android/gradle.properties` (están comentadas al
final del archivo) para no escribirlas cada vez; no son secretos. Si la web vive en Netlify, el valor
es `https://<web>.netlify.app`; con dominio propio, ese dominio.

Qué revisar al cambiar de dominio:

- **Red** (`res/xml/red_release.xml`): el release solo admite https (certificados del sistema), y http
  únicamente hacia `10.0.2.2`, `localhost` y `127.0.0.1`. Railway (`*.up.railway.app`) y Vercel
  (`*.vercel.app`) sirven https con certificados públicos, así que no hay nada que agregar. Supabase
  va siempre por https.
- **Mapa nativo**: no carga la web. Los tiles van por https a `tiles.stadiamaps.com` (o a OSM sin
  llave) y los datos a Supabase; la dirección de la WEB solo se usa para abrir `/cuenta` y
  `/comunidad` en el navegador del teléfono. La llave de Stadia se da con `-Psimpac.stadiaKey=...`.
- **CORS de la API**: la app llama a `GET /api/snapshot` con OkHttp (sin origen, no le afecta CORS).
  La web hoy no llama a la API (lee Supabase directo), pero `SIMPAC_CORS_ORIGENES` del servicio `api`
  lleva igual el dominio de Vercel por si alguna página empieza a usar `/api/snapshot`.
- **Firma**: el keystore y sus contraseñas van en `appmobile/android/key.properties` (no versionado,
  ver "Firma de la app"). Sin keystore, Gradle igual termina `assembleRelease`/`bundleRelease` pero
  deja el paquete **sin firmar** (`app/build/outputs/apk/release/app-release-unsigned.apk`), que ni
  Play ni un teléfono aceptan: es lo esperado hasta que exista `key.properties`.

## Firma de la app (una sola vez, la guarda quien publica)

Google Play exige que el AAB vaya firmado con una llave propia (la "upload key"). Se crea una vez y
**no se pierde ni se sube al repo** (`key.properties`, `*.jks` y `*.keystore` están en `.gitignore`).

1. Crear el keystore:
   ```bash
   keytool -genkeypair -v -keystore simpac-upload.jks -alias simpac -keyalg RSA -keysize 2048 -validity 10000
   ```
   Guardarlo fuera del repo (por ejemplo `C:\Users\<usuario>\claves\simpac-upload.jks`).
2. Decirle a Gradle dónde está, por cualquiera de las dos vías (`app/build.gradle.kts` lee primero el
   archivo y, si no existe, las variables; sin ninguna, el release se compila sin firmar):
   - Archivo `appmobile/android/key.properties` (no versionado):
     ```properties
     storeFile=C:/Users/<usuario>/claves/simpac-upload.jks
     storePassword=<contrasena del almacen>
     keyAlias=simpac
     keyPassword=<contrasena de la llave>
     ```
   - O variables de entorno (útiles en un CI): `SIMPAC_KEYSTORE_FILE`, `SIMPAC_KEYSTORE_PASSWORD`,
     `SIMPAC_KEY_ALIAS`, `SIMPAC_KEY_PASSWORD`.
3. Subir la versión antes de cada publicación en `app/build.gradle.kts`: `versionCode` (entero,
   siempre mayor; hoy `2`, porque la app de Capacitor fue la `1`) y `versionName` (hoy `2.0`).
4. Generar el **AAB** con `.\gradlew.bat bundleRelease` (`app/build/outputs/bundle/release/app-release.aab`)
   o el **APK firmado** con `assembleRelease`. Comprobar la firma: `apksigner verify --print-certs
   app-release.apk` (en `$ANDROID_HOME/build-tools/36.0.0/`) o `jarsigner -verify app-release.aab`.
   El release va con R8 (`isMinifyEnabled`) y las reglas de `proguard-rules.pro` para
   kotlinx.serialization y OkHttp.

## Publicar en Google Play

1. **Cuenta de desarrollador** en <https://play.google.com/console>: pago único de 25 USD y
   verificación de identidad (una cuenta personal nueva debe hacer además una prueba cerrada con al
   menos 12 probadores durante 14 días antes de publicar en producción).
2. **Crear la app**: nombre `SIMPAC`, idioma español (Perú), tipo *App*, gratis.
3. **Ficha de la tienda**: descripción corta y larga en lenguaje claro, ícono 512x512, portada
   1024x500 y al menos 2 capturas (`adb exec-out screencap -p > captura.png`).
4. **Contenido de la app**: política de privacidad pública (ubicación solo en primer plano, para la
   zona, el pronóstico cercano y la distancia a los puntos; sin cuenta la app no guarda nada en la
   nube; las cuentas y los reportes se hacen en la web); seguridad de los datos ("Ubicación aproximada
   y precisa", recogida, no compartida, opcional, fin "Funcionalidad de la app"; las notificaciones
   push usan el token de FCM); permisos de ubicación solo en primer plano (no hace falta formulario de
   segundo plano); clasificación IARC (utilidad, apta para todos); no es app gubernamental (proyecto
   académico que muestra datos oficiales con su fuente; no presentarla como app de SENAMHI, ANA ni
   INDECI).
5. **Nivel de API**: Play exige API 35 o superior en 2026; la app va con `targetSdk 36`.
6. **Firma por Google Play**: al subir el primer AAB aceptar que Play administre la llave de firma (la
   nuestra queda como upload key).
7. Subir el AAB en *Pruebas > Prueba interna*, validar en teléfonos reales y luego *Producción*.

## Límites y pendientes

- El mapa es nativo desde el 04-11-2026 (ver "Mapa nativo"); **falta probarlo en un teléfono real**
  y con la llave de Stadia en un release. La sesión de la web (Supabase Auth) no se comparte con la app.
- El departamento por GPS se decide con la estación de SENAMHI más cercana (como la web) y, si esa
  consulta falla, con la capital más cercana (aproximado en zonas de frontera como Jaén).
- Los chips de ríos salen de `rio_cauce_senal` (ríos con trazo de ANA); el Mashcón vigilado
  (`rio_vigilado`) se ve en el mapa, no en el chip.
- La tarea del worker que envía por FCM (`push`, cada 5 min) ya existe y está verificada (24-10-2026);
  en otro servidor hay que montar la cuenta de servicio (`FIREBASE_CREDENCIALES_ARCHIVO`). Falta la
  política de privacidad pública que pide Play, la firma (keystore) y la cuenta de Play Console. La
  app no tiene iOS.
- `security-crypto` 1.1.0 (`EncryptedSharedPreferences`, `MasterKey`) está marcado como obsoleto por
  AndroidX y compila con avisos; se cambia cuando publiquen el reemplazo.
- El `MapView` de osmdroid (`ui/mapa/MapaScreen.kt`) lleva `LayoutParams(MATCH_PARENT, MATCH_PARENT)`
  explícitos, como antes el WebView: el `ViewGroup` de `AndroidView` pone `WRAP_CONTENT` si la vista no
  trae parámetros. La app anterior con Capacitor se retiró del repo el 24-10-2026; esta la reemplaza en
  el teléfono por tener el mismo `applicationId`.
