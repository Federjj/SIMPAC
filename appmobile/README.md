# SIMPAC — App Android

La app Android de SIMPAC es **la misma web del proyecto empaquetada con Capacitor**: un proyecto
Android nativo (Gradle, generado por Capacitor) que abre la web compilada (`frontend/dist`) dentro de
un WebView del sistema y le da acceso al GPS por el plugin `@capacitor/geolocation`. Así la app
tiene exactamente las mismas funciones que la web (mapa con la hoja "Tu zona ahora", capas, avisos,
pronóstico, ríos del país, El Niño, a dónde acudir, y las páginas Alertas, Comunidad con reportes,
Chat, Cuenta e Histórico) y toda mejora de la web llega a la app con un nuevo empaquetado
(`npm run android:sync`).

El proyecto nativo vive en **`frontend/android/`** (Capacitor lo exige al lado del `package.json`
que tiene `@capacitor/cli`); esta carpeta `appmobile/` guarda solo la documentación.

## Decisión y límites

- **Por qué Capacitor y no Kotlin/Compose o React Native desde cero**: la web ya existe y funciona
  con datos reales; reescribirla en Kotlin o React Native son semanas de trabajo. Capacitor permite
  tener hoy una app instalable con paridad total de funciones, publicable en Play Console, y deja la
  puerta abierta a código nativo (el proyecto `frontend/android` es un proyecto Android normal: se
  abre en Android Studio y se le puede sumar Kotlin cuando haga falta).
- **Límites**: es un WebView, no una interfaz nativa (el rendimiento del mapa es el del navegador
  del teléfono; en gama baja va algo más lento que la web en una PC). No hay notificaciones push
  todavía: el siguiente paso es `@capacitor/push-notifications` + Firebase Cloud Messaging (FCM); el
  proyecto ya tiene el plugin de `google-services` preparado para cuando se agregue
  `android/app/google-services.json`. Sin conexión no hay datos (igual que la web).
- **Origen de la web dentro de la app**: `https://localhost` (`androidScheme: https` en
  `frontend/capacitor.config.json`). Esto importa para las tiles del mapa: Stadia Maps sirve sin
  llave solo a `localhost`, y la app cumple esa condición; si Stadia cambia esa regla, hay que pasar
  una llave por `VITE_...` o cambiar la base a OpenStreetMap/CARTO con su atribución
  (`frontend/src/map/baseMap.js`). La API de FastAPI ya acepta por defecto los orígenes
  `https://localhost` y `capacitor://localhost` (`SIMPAC_CORS_ORIGENES` vacío), aunque hoy la web no la
  consulta: lee Supabase directo. El service worker de la web (`frontend/src/pwa.js`) no se registra
  dentro de la app: el WebView ya carga los archivos del APK.
- **Versiones de Android**: `minSdk 24` (Android 7.0, el mínimo que admite Capacitor 8; la matriz de
  riesgos pedía menos que API 34), `targetSdk 36` y `compileSdk 36` (lo que exige Play Console en
  2026). Se definen en `frontend/android/variables.gradle`.

## Qué hay en el repo

| Archivo | Qué es |
|---|---|
| `frontend/capacitor.config.json` | `appId` `pe.simpac.app`, `appName` `SIMPAC`, `webDir` `dist`, esquema `https`, pantalla de inicio y barra de estado |
| `frontend/android/` | Proyecto Android (Gradle). Se versiona; lo generado (`build/`, `.gradle/`, `.idea/`, `*.iml`, `local.properties`, `capacitor-cordova-android-plugins/`, `app/src/main/assets/public/`, `assets/capacitor.config.json`, `assets/capacitor.plugins.json`, `res/xml/config.xml`) y `app/google-services.json` están en el `.gitignore` de la raíz |
| `frontend/android/app/src/main/AndroidManifest.xml` | Permisos: `INTERNET`, `ACCESS_COARSE_LOCATION`, `ACCESS_FINE_LOCATION`; el GPS se declara como no obligatorio |
| `frontend/android/variables.gradle` | `minSdkVersion`, `targetSdkVersion`, `compileSdkVersion` y versiones de AndroidX |
| `frontend/android/app/build.gradle` | `applicationId`, `versionCode`/`versionName` (hoy `1` / `1.0`), la firma del release (lee `key.properties` o variables de entorno) y el `ignoreAssetsPattern` que deja fuera los `.gz` del build de Vite |
| `frontend/android/app/src/main/res/values/strings.xml` | Nombre visible de la app (`SIMPAC`) |
| `frontend/android/app/src/main/res/drawable-v24/ic_launcher_foreground.xml` y `values/ic_launcher_background.xml` | Ícono adaptable (Android 8+): gota blanca sobre azul oscuro, como vector. Para Android 7 (API 24-25) siguen los PNG de `mipmap-*/ic_launcher*.png` que trae Capacitor: reemplazarlos con Android Studio (clic derecho en `res` > New > Image Asset) o con `@capacitor/assets` |
| `frontend/android/app/src/main/res/drawable*/splash.png` | Pantalla de inicio (la de Capacitor por ahora; se cambia con `@capacitor/assets` o reemplazando los PNG) |
| `frontend/src/hooks/useGeolocation.js` | GPS: en la app usa `@capacitor/geolocation` (import dinámico), en la web `navigator.geolocation` |

Versiones usadas en el primer empaquetado: Capacitor 8.5.3 (core, cli, android), plugins
`@capacitor/geolocation` 8.2.3, `@capacitor/app` 8.1.2, `@capacitor/splash-screen` 8.0.2,
`@capacitor/status-bar` 8.0.4; Android Gradle Plugin 8.13.0; Gradle 8.14.3; Java 21.

## Requisitos para compilar

- Node.js 22 o superior y las dependencias del front (`cd frontend && npm install`).
- **JDK 21** (por ejemplo `C:\Program Files\Java\jdk-21.0.11`).
- **Android SDK** con `platforms;android-36`, `build-tools;36.0.0` y `platform-tools` (los instala
  Android Studio desde *SDK Manager*, o `sdkmanager "platforms;android-36" "build-tools;36.0.0"`).
  La primera compilación baja Gradle y las dependencias (unos 500 MB); después es rápida.
- Variables de entorno `JAVA_HOME` y `ANDROID_HOME`. Si no están exportadas, en cada terminal:
  - PowerShell:
    ```powershell
    $env:JAVA_HOME = "C:\Program Files\Java\jdk-21.0.11"
    $env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
    $env:Path = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:Path"
    ```
  - Git Bash / Linux / macOS:
    ```bash
    export JAVA_HOME="C:/Program Files/Java/jdk-21.0.11"      # o la ruta de tu JDK 21
    export ANDROID_HOME="$LOCALAPPDATA/Android/Sdk"            # Linux: ~/Android/Sdk; macOS: ~/Library/Android/sdk
    export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
    ```
- `frontend/.env` con `VITE_SUPABASE_URL` y `VITE_SUPABASE_PUBLISHABLE_KEY` (copiar de
  `frontend/.env.example`). Son llaves **públicas**, pero igual no van al repo: Vite las mete en el
  bundle al compilar, y ese bundle (`frontend/dist` y `frontend/android/app/src/main/assets/public`)
  tampoco se versiona.

## Comandos (desde `frontend/`)

| Comando | Qué hace |
|---|---|
| `npm run android:sync` | `npm run build` (web a `dist/`) + `npx cap sync android` (copia la web al proyecto Android y actualiza los plugins). **Hay que correrlo cada vez que cambia la web.** |
| `npm run android:apk` | sync + `gradlew assembleDebug`: APK de prueba firmado con la llave de depuración, en `android/app/build/outputs/apk/debug/app-debug.apk`. Sirve para instalar directo con `adb install -r`, no para la tienda. |
| `npm run android:aab` | sync + `gradlew bundleRelease`: paquete para Play Console en `android/app/build/outputs/bundle/release/app-release.aab` (firmado si hay `key.properties`). |
| `npm run android:apk:release` | sync + `gradlew assembleRelease`: APK release firmado para repartir fuera de la tienda, en `android/app/build/outputs/apk/release/app-release.apk`. |
| `npm run android:open` | Abre el proyecto en Android Studio. |
| `npm run android:run` | sync + instala y abre la app en el emulador o teléfono conectado. |

Los scripts llaman a `gradlew` tal cual (funciona en Windows, donde resuelve `gradlew.bat`); en
macOS o Linux usar `./gradlew` a mano:
```bash
npm run build && npx cap sync android && cd android && ./gradlew bundleRelease
```

Secuencia equivalente paso a paso, verificada el 2026-10-20 en Windows (PowerShell, con `JAVA_HOME` y
`ANDROID_HOME` definidos como arriba): `npm run build` (9 s), `npx cap sync android` (2 s) y, dentro de
`frontend/android`, `.\gradlew.bat assembleDebug` (9 s con el daemon caliente; la primera vez baja
Gradle y dependencias). Resultado: `android/app/build/outputs/apk/debug/app-debug.apk` de 5,3 MB
(5 304 253 bytes). Desde Git Bash, `cmd //c gradlew.bat` no encuentra el script (conversión de rutas de
MSYS): usar PowerShell o `./gradlew.bat`.

Nota sobre los `.gz`: el build de Vite deja un `.gz` al lado de cada `.js`/`.css` (los sirve nginx en la
web). Capacitor los copia tal cual a `assets/public/` y AAPT los tomaba como duplicados del archivo sin
`.gz` (`mergeDebugAssets` fallaba con "Duplicate resources"); `frontend/android/app/build.gradle` los
excluye con `!*.gz` en `ignoreAssetsPattern`. El WebView no los necesita.

Para probar en un teléfono: activar *Opciones de desarrollador > Depuración USB*, conectarlo y
`adb install -r android/app/build/outputs/apk/debug/app-debug.apk`. En emulador, con el AVD
encendido, el mismo comando.

Emulador sin ventana (probado el 2026-10-20 con el AVD `Pixel_7a`, imagen Google Play x86_64):
```bash
"$ANDROID_HOME/emulator/emulator" -avd Pixel_7a -no-window -gpu swiftshader_indirect -no-snapshot -no-audio -memory 3072 &
adb wait-for-device; adb shell getprop sys.boot_completed      # repetir hasta que diga 1 (unos 50 s)
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -W -n pe.simpac.app/.MainActivity
adb exec-out screencap -p > captura.png
adb emu kill
```
Con los 2 GB que trae el AVD por defecto, la imagen con servicios de Google deja la app sin memoria y
Android la mata a los pocos segundos ("Process pe.simpac.app has died" en `logcat`, sin excepción
propia); con `-memory 3072` la app carga el mapa con sus tiles, el chip de nivel, el río Mashcón y la
barra inferior. En una PC con poca RAM libre el emulador muestra "System UI isn't responding": tocar
*Wait*; no es un error de la app.

## Firma de la app (una sola vez, la guarda quien publica)

Google Play exige que el AAB vaya firmado con una llave propia (la "upload key"). Esa llave se crea
una vez y **no se pierde ni se sube al repo**: `key.properties`, `*.jks` y `*.keystore` ya están en
`.gitignore`. Guardar el archivo y las contraseñas en un lugar seguro del equipo (si se pierde la
upload key, Play permite pedir un reinicio, pero tarda días).

1. Crear el keystore (pide una contraseña para el almacén y otra para la llave; pueden ser la misma):
   ```bash
   keytool -genkeypair -v -keystore simpac-upload.jks -alias simpac -keyalg RSA -keysize 2048 -validity 10000
   ```
   Guardarlo fuera del repo (por ejemplo `C:\Users\<usuario>\claves\simpac-upload.jks`).
2. Decirle a Gradle dónde está, por cualquiera de las dos vías:
   - Archivo `frontend/android/key.properties` (no versionado):
     ```properties
     storeFile=C:/Users/<usuario>/claves/simpac-upload.jks
     storePassword=<contrasena del almacen>
     keyAlias=simpac
     keyPassword=<contrasena de la llave>
     ```
   - O variables de entorno, útiles en un CI: `SIMPAC_KEYSTORE_FILE`, `SIMPAC_KEYSTORE_PASSWORD`,
     `SIMPAC_KEY_ALIAS`, `SIMPAC_KEY_PASSWORD`.
   `frontend/android/app/build.gradle` lee primero `key.properties` y, si no existe, las variables;
   sin ninguna de las dos el release se compila sin firmar (y el debug no se ve afectado).
3. Subir la versión antes de cada publicación en `frontend/android/app/build.gradle`: `versionCode`
   (entero, siempre mayor que el anterior) y `versionName` (texto que ve la gente, p. ej. `1.0.1`).
4. Generar:
   - **AAB para Play Console**: `npm run android:aab` → `android/app/build/outputs/bundle/release/app-release.aab`.
   - **APK firmado para instalar directo** (compartir por enlace, sin tienda): `npm run android:apk:release`
     → `android/app/build/outputs/apk/release/app-release.apk`.
   Comprobar la firma: `apksigner verify --print-certs app-release.apk` (apksigner está en
   `$ANDROID_HOME/build-tools/36.0.0/`) o `jarsigner -verify app-release.aab`.

## Publicar en Google Play

1. **Cuenta de desarrollador** en <https://play.google.com/console>: pago único de 25 USD, verificación
   de identidad (DNI y, para cuenta de organización, documentos de la entidad; una cuenta personal
   nueva además debe hacer una prueba cerrada con al menos 12 probadores durante 14 días antes de poder
   publicar en producción).
2. **Crear la app** en la consola: nombre `SIMPAC`, idioma español (Perú), tipo *App*, gratis.
3. **Ficha de la tienda**: descripción corta y larga en lenguaje claro, ícono de 512x512, imagen de
   portada 1024x500, al menos 2 capturas del teléfono (tomarlas de la app, por ejemplo con
   `adb exec-out screencap -p > captura.png`).
4. **Contenido de la app** (cuestionarios obligatorios):
   - **Política de privacidad**: URL pública (puede ser una página del repo en GitHub Pages o del
     dominio del proyecto) que diga qué datos se usan: la ubicación solo en primer plano y solo para
     centrar el mapa, calcular la distancia al río y a los lugares a dónde acudir, y ubicar un
     reporte; la cuenta es opcional y solo hace falta para reportar, votar y chatear (correo,
     contraseña y un nombre, en Supabase Auth; la zona elegida se guarda en el perfil); los reportes
     con su foto (bucket público `reportes`), los votos y los mensajes del chat (duran 2 horas) que la
     persona envía; sin publicidad, sin venta de datos. Sin cuenta la app no guarda nada en la nube.
   - **Seguridad de los datos**: declarar "Ubicación aproximada y precisa" (recogida, no compartida
     con terceros, opcional, fin "Funcionalidad de la app"); "Información personal: dirección de
     correo electrónico y nombre" (opcional, solo con cuenta, fin "Gestión de la cuenta"); "Fotos",
     "Mensajes" y "Otro contenido generado por el usuario" (los reportes, votos y mensajes del chat,
     opcionales, se publican a las demás personas de la app). Las cuentas se pueden eliminar a pedido:
     anotarlo en la política mientras la app no tenga un botón para borrarla.
   - **Permisos de ubicación**: solo en primer plano (la app no pide `ACCESS_BACKGROUND_LOCATION`, así
     que no hace falta el formulario de ubicación en segundo plano ni video de demostración).
   - Clasificación de contenido (cuestionario IARC: utilidad, apta para todos), público objetivo
     (mayores de 13 o 18, no dirigida a niños), anuncios: no, app gubernamental: no (es un proyecto
     académico que muestra datos oficiales con su fuente; no presentarla como app oficial de SENAMHI,
     ANA ni INDECI).
5. **Nivel de API**: Play exige que las apps nuevas y sus actualizaciones apunten a la API vigente
   (en 2026, API 35 o superior; la app va con `targetSdk 36`). Si Play sube la exigencia, cambiar
   `targetSdkVersion` y `compileSdkVersion` en `frontend/android/variables.gradle` y recompilar.
6. **Firma por Google Play**: al subir el primer AAB, aceptar que Play administre la llave de firma
   (la nuestra queda como upload key).
7. **Subir el AAB** en *Pruebas > Prueba interna* (hasta 100 probadores por correo, se instala en
   minutos) para validar en teléfonos reales; después *Producción* con notas de la versión en
   español. La revisión de Google tarda de horas a varios días la primera vez.

## Qué revisar en el teléfono antes de publicar

- El mapa carga sus tiles (fondo con calles). Si se ve gris, Stadia dejó de aceptar `localhost`:
  ver "Origen de la web" arriba.
- Al tocar "Mi ubicación" o enviar un reporte, Android muestra el diálogo de permiso de ubicación y,
  si se acepta, el mapa se centra en donde estás.
- Las capas, los avisos y la hoja "Tu zona ahora" muestran la hora del dato y su fuente, igual que la
  web; la hoja arranca plegada (unos 300 px) y se agranda con el asa o los botones.
- La barra inferior de 5 pestañas lleva a Alertas, Comunidad, Chat y Cuenta. Entrar con una cuenta ya
  confirmada funciona igual que en la web. Crear la cuenta o pedir contraseña nueva desde la app manda
  un correo cuyo enlace vuelve a `window.location.origin + /cuenta`, que dentro de la app es
  `https://localhost/cuenta` y en el teléfono no abre nada: por ahora crear o confirmar la cuenta
  desde la web y después entrar en la app (pendiente: una dirección de retorno propia para la app).
- Botón "atrás" del teléfono: cierra el popup o panel abierto y, en la pantalla principal, sale de la app.
- Pantalla de inicio azul oscuro con el logo de Capacitor (reemplazar por el de SIMPAC cuando haya diseño).

## Siguientes pasos (no bloquean la primera publicación)

- **Notificaciones push** (avisos nuevos de tu zona): `npm i @capacitor/push-notifications`, proyecto
  en Firebase, `google-services.json` en `frontend/android/app/` (no versionado), y una tarea del
  worker que envíe por FCM cuando entra un aviso de nivel 3 o 4 para el departamento elegido.
- Ícono y pantalla de inicio propios con `@capacitor/assets` (genera todos los tamaños desde un PNG
  de 1024x1024 y un SVG).
- iOS: `npx cap add ios` (requiere macOS y Xcode); el mismo código web sirve.
