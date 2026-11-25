# SIFEC — App Android nativa (Kotlin + Jetpack Compose)

La app Android de SIFEC es una **app nativa en Kotlin con Jetpack Compose** (HU-20 y HU-21 del
backlog) que vive en **`appmobile/android/`**. Lee los mismos datos oficiales que la web (Supabase con
la publishable key y la API de solo lectura de FastAPI), muestra el semáforo de tu zona con su titular
en lenguaje claro, las alertas vigentes, a dónde acudir cerca de ti, un **mapa nativo** (osmdroid,
sin WebView) con los avisos de SENAMHI, los ríos del país con su estado, las zonas que podrían
inundarse, las estaciones de SENAMHI y los puntos de "A dónde acudir", tiene la **comunidad nativa**
(reportes ciudadanos con foto, votos y comentarios) con **cuentas de Supabase Auth dentro de la app**
(HU-17, HU-18 y HU-19 en Android, 19-11-2026), y recibe **notificaciones push por Firebase Cloud
Messaging (FCM)** cuando tu departamento entra en alerta o emergencia.

Reemplaza a la app anterior hecha con Capacitor (la web empaquetada): tiene el mismo `applicationId`
(`pe.simpac.app`), así que instalarla sobre la otra la sustituye. El proyecto de Capacitor se retiró del
repo el 24-10-2026.

## Qué hace (5 pestañas)

| Pestaña | Qué muestra | De dónde sale |
|---|---|---|
| **Inicio** | Semáforo grande del departamento (elegido o detectado por GPS), `titular_corto` y detalle con "Generado el <hora>" y origen (reglas o modelo), chips con cuántas alertas oficiales hay y el río con señales (primero el río vigilado del departamento, el Mashcón, que no tiene fila en `rio_cauce` y se arma con `rio_vigilado_mapa`, `rio_senal` y su lectura en `caudal_actual`; en empate de nivel manda el río con señal de cuenca, el mismo que nombra el titular. Si su cuenca tiene un aviso de lluvias de SENAMHI en curso o lluvia medida sobre la referencia, el chip dice la medición con su estación, «Río Mashcón · Estación Mashcón (ANA): tranquila (0.34 m³/s)», y debajo va la línea «Cuenca: aviso naranja de SENAMHI por lluvias vigente hoy; el caudal puede subir.» con «Ver el aviso oficial»: las dos cosas son ciertas a la vez), estado El Niño del ENFEN, pronóstico de 3 días de la localidad más cercana, botones "Llamar 105" y "Llamar 116", la sección **"A dónde acudir"** (antes era una pestaña: los 3 puntos más cercanos, salud 24 h si está a menos de 15 km o el más cercano, comisaría y bomberos, en 30 km alrededor de la posición, con distancia en línea recta, teléfono, "Cómo llegar", fuente y fecha, y los números 105, 116, 115 y 106), la tarjeta "Comunidad" con el botón **"Reportar"** (lleva al formulario de reporte), fuentes con hora y el pie "Información referencial..." | `titular_zona`, `alerta_actual`, `rio_cauce_mapa` + `rio_cauce_senal`, `rio_vigilado_mapa` + `rio_senal` + `caudal_actual` (el río vigilado), `pronostico_vigente` (caja alrededor de la posición), `estacion` (para saber el departamento por GPS), `punto_acudir` y `GET /api/snapshot` (contexto ENFEN) |
| **Alertas** | Lista ordenada emergencia > alerta > aviso, oficiales primero; la "Lluvia medida" va aparte y marcada como no oficial; filtro "Mi zona / Todo el país"; cada tarjeta con color + etiqueta, referencia, zona, detalle, hora y fuente; vacío amable con la hora de la revisión | `alerta_actual` |
| **Mapa** | Mapa **nativo** con osmdroid (ver "Mapa nativo"): chip arriba con el nivel de tu zona, 5 capas con interruptor (avisos de SENAMHI, ríos, zonas que podrían inundarse, estaciones de SENAMHI, a dónde acudir), nombres de los ríos desde zoom 11, punto azul de tu ubicación y botón "centrar"; al tocar un área, un río, una zona o un punto se abre una hoja inferior de Material 3 en lenguaje claro con su fuente y hora; "Ver el aviso oficial" y "Ver el aviso de SENAMHI" abren el navegador. Solo la barra inferior de la app: no hay barras duplicadas | `aviso_vigente`, `caudal_actual`, `rio_vigilado_mapa`, `rio_zona_mapa`, `rio_senal`, `rio_cauce_mapa` (`cauce_lejos` y `cauce`), `rio_cauce_senal`, `rio_cauce_zona_mapa`, `estacion`, `punto_acudir`, `titular_zona`; tiles de Stadia Maps (o de OSM sin llave) |
| **Comunidad** | Reportes de vecinos vigentes (12 h) ordenados por confianza y cercanía, cada uno con el glifo y color de su tipo, descripción, foto, "hace X", distancia, estado según la comunidad y vencimiento, votos a favor / en contra (con sesión) y "Ver en el mapa"; "Reportar incidente" (formulario con GPS real, tipo, subtipo del atasco, descripción, foto por cámara o galería); detalle con comentarios y caja para comentar (con sesión). Sin sesión se consulta todo y se invita a entrar para reportar, votar y comentar (ver "Comunidad y cuentas") | `report`, `comentario`, `voto`, bucket `reportes` (Storage) |
| **Cuenta** | **Nativa** (Supabase Auth por correo y contraseña): pestañas Entrar / Crear cuenta, "Olvidé mi contraseña" y la pantalla "Revisa tu correo"; con sesión: nombre, correo, reputación del perfil, "Mis reportes" (vigentes y vencidos, con estado y votos) y cerrar sesión. Debajo siguen Ajustes (departamento e interruptor de notificaciones por zona) y "Acerca de" con fuentes y licencias. Las direcciones de la API y la web no se pueden cambiar desde la app: vienen fijas del build (`-Psimpac.apiUrl` y `-Psimpac.webUrl`) | GoTrue (`/auth/v1`), `perfil`, `rpc mis_reportes`, DataStore (ajustes) y FCM |

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
| Zonas que podrían inundarse (prendida) | `rio_zona_mapa` (Mashcón: estimadas bajo_2m rayada con borde oscuro y bajo_3m lisa tenue; estudio INDECI-PNUD 2005 lisa) y `rio_cauce_zona_mapa` (40 zonas de 20 ríos), con el color del nivel de la zona de hoy; se piden solo por los ríos cuya caja toca la vista (nunca el país entero). Hoja: "Zona que podría inundarse si el río se desborda - estimación de SIFEC con el relieve (Copernicus), no es un mapa oficial", método, fuente, licencia y atribución | SIFEC con Copernicus GLO-30; INDECI-PNUD 2005 | 12 |
| Estaciones de SENAMHI (apagada) | Puntos pequeños (M azul claro `#3BA5EB`, H azul `#3B3BEB`) por caja alrededor de la vista. Hoja: nombre, tipo, departamento, código | SENAMHI | 10 |
| A dónde acudir (apagada) | Marcadores por tipo con glifo (cruz, escudo, llama) por caja alrededor de la vista. Hoja: nombre, categoría, "Atiende las 24 horas, según la fuente" solo si la fuente lo dice, dónde, "Llamar" (`ACTION_DIAL`), "Cómo llegar" (`geo:`), fuente y fecha | SUSALUD RENIPRESS, MININTER vía CENEPRED, CGBVP | 11 |
| Tu ubicación | Punto azul con halo y botón flotante "Centrar en tu ubicación": lectura activa de alta precisión de hasta 20 s con rueda de progreso en el propio botón (no se puede tocar dos veces) y zoom 15 si la posición es precisa (100 m o menos). Cada causa tiene su mensaje y su acción: sin permiso lo pide ahí mismo y al concederlo centra (ya no manda a Inicio); con la ubicación del teléfono apagada, aviso con "Activar" (ajustes del sistema); sin señal, "No se pudo obtener tu posición; prueba a cielo abierto" con "Reintentar". Al abrir, el mapa centra en tu punto o en la capital del departamento elegido (zoom 13). Desde Inicio, "Ver el río en el mapa" lleva a la pestaña Mapa encuadrando tu punto y el cauce del río destacado | GPS del teléfono (ver "Ubicación del teléfono") | - |

Los interruptores se recuerdan en DataStore (`Ajustes.capasMapa`; de fábrica avisos, zonas y ríos, como
la web). Todo el trabajo de red y parseo va fuera del hilo principal (`MapaViewModel`, `viewModelScope`
+ `Dispatchers.IO`/`Default`); al salir de la pestaña el ViewModel se limpia y cancela sus corrutinas.
El parser GeoJSON (`dominio/GeoJson.kt`: Point, LineString, MultiLineString, Polygon, MultiPolygon,
Feature y FeatureCollection; caja, centroide, punto en polígono, simplificación Douglas-Peucker) y la
lógica de ríos (`dominio/Cauces.kt`) tienen pruebas JVM con los mismos casos que `lib/cauces.test.js`.
Caché en disco con plazo: 10 min para ríos, zonas, estaciones y acudir; 5 min para avisos y señales.

**Río tranquilo que puede subir (23-11-2026).** El estado "Tranquilo" de un río es la medición de ANA en
su estación; el aviso naranja de SENAMHI por lluvias sobre su cuenca es un pronóstico: las dos cosas son
ciertas a la vez y antes la hoja y el chip solo decían la primera. Ahora `dominio/Rios.kt` redacta la señal
de la cuenca a partir de las señales de `Cauces.estadoZona` (`Rios.cuenca`: el aviso de lluvias en curso
naranja o rojo o, si no hay, la lluvia medida sobre la referencia) y `Rios.medicion` la medición con su
estación. En las hojas del río, del Mashcón y de la estación de ANA, con una señal en la cuenca la medición
va como «Estación Mashcón (ANA): tranquila» (el valor con paréntesis solo lo lleva el chip de Inicio, porque
en las hojas ya va en el título) y debajo la línea «Cuenca: aviso naranja de SENAMHI
por lluvias vigente hoy; el caudal puede subir.» con punto ámbar y el botón «Ver el aviso oficial de
lluvias»; la pastilla y el color del cauce siguen siendo el estado de ANA. En el mapa, los ríos cuya zona
tiene señales (`NivelZona` distinto de `SIN_SENALES`: aviso de lluvia o lluvia medida sobre la cuenca,
cerca del nivel de alerta, alerta o emergencia) llevan debajo del halo blanco un **halo que late**: un
trazo ancho (18 dp; 13 dp bajo zoom 10; 9 dp en vista país y solo si el río está fuerte) del color del
nivel de la zona (ámbar `#EAB308`, naranja, rojo) cuyo alfa va de 0,25 a 0,75 en una onda de ~2,5 s. Lo
dibuja `GestorMapa.Latido`, un `Overlay` que va primero en la capa de ríos: los pulsos no son overlays de
la capa (ni `Polyline`), Latido los pinta él mismo como un solo `Path` por color con todas las partes a la
vista, en píxeles de pantalla y con una pintura translúcida con el alfa del cuadro; dentro de un mismo
`drawPath` el trazo no se suma donde las partes se solapan (el cauce del Mashcón llega de OSM en varias), y
no hace falta una capa fuera de pantalla (`saveLayerAlpha` costaba medio cuadro en el emulador). Los `Path`
se rehacen solo cuando cambia la vista o los pulsos; después pide el siguiente cuadro con
`postInvalidateDelayed(90)` (~11 cuadros por segundo, sin `ValueAnimator`). `revisarVista` apaga los pulsos
cuyo río no toca la vista, también los del Mashcón (antes estos nunca se apagaban y el mapa seguía
redibujándose a ~9 cuadros por segundo con el cauce a 50 km): si ninguno queda prendido no se dibuja ni se
pide otro cuadro, y si el mapa no se dibuja (otra pestaña, app detrás, capa de ríos apagada) tampoco, así la
cadena se corta sola y arranca con el primer dibujo; con la escala de animaciones del sistema en 0
(`Settings.Global.ANIMATOR_DURATION_SCALE`) el halo queda fijo. La leyenda de la capa Ríos lo explica
("Halo que late: aviso de lluvia o lluvia medida sobre su cuenca, el río puede subir"). Las señales de la
cuenca solo las trae `rio_senal` (río vigilado: el Mashcón), y el Mashcón no tiene fila en `rio_cauce` (su
trazo es el de OSM revisado a mano y el cargador lo salta), así que antes nunca llegaba al chip de Inicio y
el chip decía el Marañón «muy bajo» en Borja mientras el titular hablaba del Mashcón. Ahora `InicioViewModel`
pide también `rio_vigilado_mapa`, `rio_senal` y `caudal_actual` (las consultas del mapa, con la misma caché
en disco) y `Rios.resumirZona` arma el vigilado del departamento con `Rios.deVigilado` (un `RioCauceSenal`
con la lectura de su estación de ANA y los campos opcionales `avisos_lluvia` y `lluvia_cuenca`), lo pone
primero en la lista sin repetir un trazo del mismo río, y `Rios.destacado` desempata a favor del río con
señal de cuenca: el chip dice «Río Mashcón · Estación Mashcón (ANA): tranquila (0.34 m³/s)» y debajo la línea
de la cuenca con «Ver el aviso oficial». Si fallan `rio_senal` o `caudal_actual`, el vigilado sale sin
cuenca o sin medición y la pantalla lo avisa abajo. Pruebas en `app/src/test/.../RiosTest.kt`. En las hojas
del mapa la línea «Estación Mashcón (ANA): tranquila» va sin el valor entre paréntesis porque el título ya lo
dice («Río Mashcón - tranquilo 0.34 m³/s (ANA, hoy 18:00)»); el chip de Inicio sí lo lleva. `Cauces.estadoRio`
(ríos con trazo del mapa) recibe también `avisos_lluvia` y `lluvia_cuenca` de `rio_cauce_senal` (hoy vacíos)
con la misma regla que el Mashcón, para que el halo y la hoja digan lo mismo que Inicio si el backend los
llena algún día (prueba en `CaucesTest.kt`).

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

## Comunidad y cuentas (HU-17, HU-18, HU-19 en Android)

Desde el 19-11-2026 la app no manda a la web para reportar ni para entrar: replica **exactamente** las
reglas y textos de `frontend/README.md` ("Comunidad" y "Cuentas y sesión"), `lib/comunidad.js`,
`lib/sesion.js`, `lib/queries.js`, `lib/reportTypes.js` y las páginas `Comunidad.jsx`,
`ReporteNuevo.jsx`, `ReporteDetalle.jsx` y `Cuenta.jsx`. La BD sigue decidiendo lo que no debe decidir
el cliente (autor, confianza, estado, vencimiento, límites por hora, foto solo del bucket propio).

**Sesión (`data/AuthSupabase.kt`, `data/Sesion.kt`).** GoTrue por REST con la publishable key:
`POST /auth/v1/signup?redirect_to=<WEB>/cuenta` (`{email, password, data: {nombre}}`; el trigger
`crear_perfil` copia el nombre al perfil), `POST /auth/v1/token?grant_type=password`,
`POST /auth/v1/token?grant_type=refresh_token`, `POST /auth/v1/recover?redirect_to=<WEB>/cuenta`,
`POST /auth/v1/logout` y `GET /auth/v1/user`. La sesión (access token, refresh token, vencimiento, id,
correo y nombre) vive **solo en `AlmacenSeguro`** (EncryptedSharedPreferences con llave del Keystore;
excluida de las copias de seguridad) y se refresca sola cuando faltan menos de 60 s para vencer; si
Auth rechaza el refresh token la sesión se borra y la pantalla vuelve a "Entra para...". `Sesion.estado`
es un `StateFlow` (`Cargando`, `SinSesion`, `ConSesion`) que observan todas las pantallas. Con la
**confirmación por correo** activa, crear la cuenta no abre sesión: la app muestra "Revisa tu correo"
(si el correo ya existía, Auth devuelve un usuario sin identidades y el texto lo dice sin revelar
cuentas); el enlace del correo abre **la web** (`<WEB>/cuenta`, la dirección fija del build) y
después la persona entra en la app con su correo y contraseña. Lo mismo con "Olvidé mi contraseña": la
contraseña nueva se elige en la web. **Pendiente:** `<WEB>/cuenta` debe estar en Supabase Auth > URL
Configuration > Redirect URLs (como ya se pedía para la web). Los errores de Auth se traducen con
`Comunidad.mensajeAuth` (credenciales, correo sin confirmar, cuenta existente, contraseña corta, límite
de correos, enlace vencido, sin red), igual que `mensajeAuth` de `lib/comunidad.js`.

**Escrituras (`data/ComunidadSupabase.kt`, expuestas por `Repositorio`).** Todas con `apikey` y
`Authorization: Bearer <access_token>`:
- `crearReporte`: `POST /rest/v1/report?select=<columnas>` con `Prefer: return=representation` y la
  fila `{tipo, subtipo, descripcion, foto_url, geom}` donde `geom` es el EWKT del GPS
  (`SRID=4326;POINT(lon lat)`); nada más (autor, estado, confianza, likes, expira_en los pone la BD).
  Máximo 5 por hora (trigger `report_limite`).
- `votar`: `POST /rest/v1/voto?on_conflict=report_id,autor` con `Prefer:
  resolution=merge-duplicates,return=minimal` y `{report_id, valor: 1 | -1}`; tocar el mismo voto lo
  quita (`DELETE /rest/v1/voto?report_id=eq.<id>`). No al propio ni a uno vencido (lo dice la BD).
  Tras votar la app vuelve a pedir el reporte: los contadores los recalcula la BD.
- `comentar`: `POST /rest/v1/comentario` con `{report_id, texto}` (1 a 500 letras; 20 por hora).
- `subirFoto`: la foto (cámara con `TakePicture` + `FileProvider` en `cacheDir/fotos`, o galería con
  `PickVisualMedia`) se **reduce a 1280 px de lado y JPEG al 85 %** (`ui/comunidad/Fotos.kt`,
  respetando la orientación EXIF y sin copiar metadatos) y va por `POST
  /storage/v1/object/reportes/<uid>/<ms>-<aleatorio>.jpg` (`Content-Type: image/jpeg`, `x-upsert:
  false`); `foto_url` es la URL pública de ese objeto, la única que admite `report_foto_url_check`.
- `misReportes`: `POST /rest/v1/rpc/mis_reportes` (la única forma de ver los propios, también
  vencidos). `perfilPropio`: `GET /rest/v1/perfil?select=id,nombre,reputacion`. `misVotos`: `GET
  /rest/v1/voto?select=report_id,valor&report_id=in.(...)`.
- Errores de PostgREST y Storage traducidos con `Comunidad.mensajeErrorBD` (límite por hora, propio
  reporte, fuera del Perú, sesión vencida, sin permiso, foto pesada o de otro tipo, reporte vencido).

**Lecturas públicas (sin cuenta).** `Repositorio.reportesVigentes(caja)` pide `report` con columnas
explícitas (nunca `autor`) dentro de una caja (la pestaña Comunidad usa la del Perú; el mapa, su
vista); `reporte(id)` y `comentarios(reportId)`. La lista se ordena en `dominio/Comunidad.kt` con el
mismo criterio que la web: confianza (0 a 1) menos un castigo por lejanía (50 km restan 1, tope a 100
km) y, en empate, el más nuevo primero; distancias desde el GPS o desde la capital del departamento
elegido ("Distancias desde ...").

**Reglas de la pantalla de reporte.** Solo con sesión y con la **posición GPS real** (sin pin manual):
sin permiso explica que no se puede reportar sin ubicación y ofrece dar el permiso; con la ubicación del
teléfono apagada ofrece "Activar la ubicación" (ajustes del sistema); sin señal, volver a buscar; fuera
del Perú no deja enviar. La posición se **afina** (`Ubicacion.afinar`): se usa la primera que llega y se
siguen pidiendo hasta 25 s quedándose con la de mejor precisión (para antes si baja de 30 m); la pantalla
dice "Precisión: unos N m", muestra "Afinando la posición..." mientras tanto y ofrece "Mejorar precisión"
si quedó peor que 30 m. Si la app solo tiene permiso de ubicación aproximada (Android 12+, unos 2 km) lo
dice y lleva a los ajustes de la app. Chips de tipo con glifo y color (`inundacion`, `huayco`, `lluvia_intensa`,
`via_bloqueada`, `atasco` con leve / moderado / detenido, `bache`, `accidente`, `otro`), descripción
de hasta 500 letras con contador, foto opcional, el aviso fijo **"Es un reporte comunitario, no
oficial. Para emergencias llama al 105 o 116."**, estados "Subiendo la foto..." / "Enviando..." y, al
terminar, abre el detalle del reporte creado. La app nunca pide más que correo y nombre, no muestra
autores ("Vecino" en los comentarios) y repite el texto fijo "Para consultar no hace falta cuenta.
Solo se pide para reportar, votar y comentar".

**Navegación.** Pestañas Inicio, Alertas, Mapa, Comunidad y Cuenta; rutas `comunidad/nuevo` y
`comunidad/{id}` dentro de la pestaña Comunidad (`ui/Navegacion.kt Rutas`). `EstadoCompartido.abrirReporte`
la pone `AppSifec` y la usa el mapa al tocar el pin de un reporte. "Ver en el mapa" encuadra el punto
del reporte en la pestaña Mapa. La notificación sigue abriendo la pestaña que dice su ruta
(`/alertas`, `/cuenta`, `/comunidad`; `/acudir` ahora abre Inicio).

**Permisos nuevos.** `CAMERA` (se pide solo al tocar "Tomar foto"; `uses-feature camera.any` con
`required=false`: la app se instala sin cámara) y el `FileProvider` `${applicationId}.archivos` con
`res/xml/rutas_archivos.xml` (solo `cacheDir/fotos`). Dependencia nueva: Coil 2.7.0 (`coil-compose`,
Apache 2.0) para las fotos.

**Pruebas JVM (`app/src/test/ComunidadTest.kt`).** Sin red, con un transporte simulado
(`TransporteHttp`): cuerpos JSON y cabeceras de signup, token, refresh, recover, logout, crear
reporte, votar, quitar voto, comentar, foto, rpc y perfil; parseo de la respuesta de Auth y la ida y
vuelta por el almacén; registro con confirmación y con correo repetido; traducción de errores de la BD
y de Auth; orden por confianza y distancia; textos de distancia y vencimiento; validaciones del
reporte, de la cuenta y del comentario.

## Ubicación del teléfono (`ubicacion/Ubicacion.kt`)

Solo en **primer plano**: se lee cuando una pantalla la necesita y toda espera se cancela al irse la
app al fondo (`ON_STOP` en Mapa y en el reporte nuevo) o al limpiarse el ViewModel; la cancelación corta
el pedido al teléfono (`CancellationToken`, `CancellationSignal`, `removeLocationUpdates`). Nunca en
segundo plano.

- `leer(contexto, maxEsperaMs)` devuelve una `Lectura`: la `Posicion` (con `precisionM` y `tomadaEnMs`,
  opcionales para que `Posicion(lat, lon)` siga valiendo) o el **motivo** exacto de que no la haya
  (`SIN_PERMISO`, `UBICACION_APAGADA` con `LocationManagerCompat.isLocationEnabled`, `SIN_SENAL`).
  Primero Google Play Services (fused): la última posición conocida si es fresca (menos de 2 min) y
  precisa (100 m o menos); si no, `getCurrentLocation(PRIORITY_HIGH_ACCURACY)` hasta el plazo; sin
  Play Services, `LocationManagerCompat.getCurrentLocation` con GPS y red a la vez. Si la lectura activa
  no responde pero hay una última posición de menos de 10 min, vale esa.
- Plazos: 10 s para las pantallas que cargan datos (Inicio, Mapa al abrir, Comunidad, Acudir), 20 s para
  el botón "Centrar en tu ubicación", 25 s para afinar un reporte.
- `afinar(contexto)` (reportes) emite cada posición mejor que la anterior con `requestLocationUpdates` de
  alta precisión y termina al bajar de 30 m o al cumplirse el plazo.
- `paraZona(contexto)` (Inicio): si la primera posición es peor que 2 km (solo red celular) y la app
  tiene permiso preciso, espera hasta 6 s por una mejor antes de decidir el departamento.
- Inicio: con "Usar mi ubicación" elegido y el permiso dado pero el interruptor del teléfono apagado,
  `InicioViewModel` lo detecta con `ubicacionActiva` (`EstadoInicio.ubicacionApagada`), muestra el
  departamento guardado y lo dice arriba ("La ubicación del teléfono está apagada...") con "Activar"
  (ajustes del sistema); al volver con la ubicación prendida la pantalla recarga sola (`LifecycleResumeEffect`).
- Antes (hasta el 23-11-2026) `actual()` devolvía null cuando ninguna app había pedido la posición hace
  poco (`lastLocation` vacío y 8 s de espera) y el mapa decía "Activa tu ubicación en Inicio" aunque el
  permiso estaba dado; ese mensaje ya no existe.

Prueba en el emulador: `adb emu geo fix -78.5003 -7.1638` (Cajamarca) y tocar el botón de ubicación del
mapa; con la ubicación del sistema apagada debe salir el aviso con "Activar".

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
  app/src/main/AndroidManifest.xml     permisos INTERNET, ubicacion en primer plano, POST_NOTIFICATIONS,
                                       CAMERA (opcional); MainActivity, ServicioMensajes (FCM),
                                       FileProvider de las fotos, canal/icono por defecto
  app/src/main/res/                    icono adaptable de la gota (el mismo de la app anterior), icono
                                       de notificacion, red_release.xml / red_debug.xml (https; http solo
                                       para 10.0.2.2/localhost en release, libre en debug)
  app/src/main/java/pe/simpac/app/
    SifecApp.kt                       Application: contenedor (ajustes, repositorio, almacen seguro)
                                       y canal de notificaciones "alertas" (importancia alta)
    MainActivity.kt                    abre la pestana que pide la notificacion (extra "ruta")
    dominio/                           logica pura, probada en JVM: Nivel, Departamentos (slug del tema
                                       FCM), Geo (haversine, caja), Tiempo ("hace X", hora de Peru),
                                       Alertas (orden y oficialidad), Acudir, Pronostico, Rios,
                                       GeoJson (parser), Cauces (estado de los rios y zonas como la web),
                                       Paleta (colores del mapa), AvisosMapa (avisos de hoy y sus textos),
                                       Comunidad (orden, validaciones y errores claros de la comunidad)
    data/                              Modelos (kotlinx.serialization), Http (OkHttp: Supabase REST y
                                       API), Transporte (peticiones de escritura, simulables en pruebas),
                                       CacheDisco (ultima respuesta por consulta), Ajustes (DataStore),
                                       AlmacenSeguro (EncryptedSharedPreferences: token de FCM y sesion),
                                       AuthSupabase (GoTrue REST), Sesion (estado de la sesion),
                                       ComunidadSupabase (escrituras con sesion), Repositorio (consultas)
    push/                              PushSifec (temas "pais" y "zona_<slug>"), ServicioMensajes
    ubicacion/                         ubicacion en primer plano (fused o LocationManager): lectura con
                                       motivo, afinado por precision, posicion para la zona
    ui/                                Navegacion (barra de 5 y rutas de comunidad), tema, componentes y
                                       las pantallas: inicio (con la seccion de acudir), alertas, mapa,
                                       comunidad (lista, reporte nuevo, detalle, fotos), cuenta
                                       (sesion nativa y ajustes), acudir (seccion reutilizable)
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

Direcciones de la API y la web: fijas, las que le dio Gradle al compilar (`BuildConfig.API_URL` y
`BuildConfig.WEB_URL`, propiedades `simpac.apiUrl` y `simpac.webUrl`; ver "Direcciones de
producción"); no se pueden cambiar desde la app. En debug sin propiedades son API
`http://10.0.2.2:8000` y WEB `http://10.0.2.2:8080`, que desde el emulador son el Docker de la PC. Para
probar en un teléfono contra la PC, compilar en debug con `-Psimpac.apiUrl=http://<IP de la PC>:8000`
(solo debug permite http); el release exige https (y solo permite http hacia 10.0.2.2 y localhost:
`res/xml/red_release.xml`).

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
| `.\gradlew.bat testDebugUnitTest` | Pruebas JVM (`app/src/test`): parseo de las respuestas, orden de alertas, distancia, slug del tema, "hace X", regla de "a dónde acudir", pronóstico, ríos, GeoJSON y cauces, y la comunidad (peticiones de Auth y de escritura sin red, errores claros, orden y validaciones). Informe en `app/build/reports/tests/testDebugUnitTest/index.html` |
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
(hace 5 min), por reglas de SIFEC con datos oficiales", chips "3 alertas oficiales" y "Río Cajamarca:
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
chip "SIFEC · Aviso amarillo en Cajamarca", el selector de ciudad, el pronóstico y la hoja "Mira cómo
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
  "notification": { "title": "SIFEC: ALERTA en Cajamarca", "body": "<titular_zona.titular_corto>" },
  "data": { "nivel": "alerta", "zona": "Cajamarca", "generado_en": "2026-10-20T17:11:02+00:00", "ruta": "/alertas" }
}
```
y `"title": "SIFEC: vuelve la calma en Cajamarca"` al bajar. El tema `pais` recibe los mismos
mensajes de todas las zonas.

### Cómo activarlo (consola de Firebase)

1. En <https://console.firebase.google.com> crear el proyecto (el del equipo se llama **appsimpac**)
   o abrirlo. Google Analytics no hace falta.
2. *Agregar app > Android*: nombre del paquete **`pe.simpac.app`** (tiene que ser exactamente ese),
   apodo "SIFEC" (el registro del equipo quedó con el apodo SIMPAC, que es solo una etiqueta); la huella
   SHA-1 no es necesaria para FCM.
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
"SIFEC: prueba en Cajamarca", canal `alertas`; la primera vez tardó unos minutos mientras FCM
propagaba la suscripción) y al tocarla la app abrió la pestaña Alertas. Detalle técnico de la tarea
(reglas, latido, siembra de `push_estado`): `docs/README-tecnico.md` §5.6.12.

## Direcciones de producción

La app lleva fijas la dirección de la API (FastAPI en Railway) y de la web (Vercel); no se pueden
cambiar desde la app (los campos de Cuenta > Ajustes se retiraron el 19-11-2026 para dejarla lista
para usuarios finales). Se dan al compilar como propiedades de Gradle (`simpac.apiUrl` y
`simpac.webUrl`), que `app/build.gradle.kts` expone como `BuildConfig.API_URL` y
`BuildConfig.WEB_URL` (`data/Ajustes.kt` las expone en `AjustesApp.apiUrl` / `webUrl`):

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
   keytool -genkeypair -v -keystore sifec-upload.jks -alias sifec -keyalg RSA -keysize 2048 -validity 10000
   ```
   Guardarlo fuera del repo (por ejemplo `C:\Users\<usuario>\claves\sifec-upload.jks`).
2. Decirle a Gradle dónde está, por cualquiera de las dos vías (`app/build.gradle.kts` lee primero el
   archivo y, si no existe, las variables; sin ninguna, el release se compila sin firmar):
   - Archivo `appmobile/android/key.properties` (no versionado):
     ```properties
     storeFile=C:/Users/<usuario>/claves/sifec-upload.jks
     storePassword=<contrasena del almacen>
     keyAlias=sifec
     keyPassword=<contrasena de la llave>
     ```
   - O variables de entorno (útiles en un CI): `SIMPAC_KEYSTORE_FILE`, `SIMPAC_KEYSTORE_PASSWORD`,
     `SIMPAC_KEY_ALIAS`, `SIMPAC_KEY_PASSWORD`.
3. Subir la versión antes de cada publicación en `app/build.gradle.kts`: `versionCode` (entero,
   siempre mayor; hoy `3`: la app de Capacitor fue la `1`, el último APK publicado como SIMPAC la `2`
   y el primero con el nombre SIFEC es el `3`) y `versionName` (hoy `2.1`). Con el `versionCode`
   mayor, el teléfono instala el APK nuevo como actualización y no pide desinstalar.
4. Generar el **AAB** con `.\gradlew.bat bundleRelease` (`app/build/outputs/bundle/release/app-release.aab`)
   o el **APK firmado** con `assembleRelease`. Comprobar la firma: `apksigner verify --print-certs
   app-release.apk` (en `$ANDROID_HOME/build-tools/36.0.0/`) o `jarsigner -verify app-release.aab`.
   El release va con R8 (`isMinifyEnabled`) y las reglas de `proguard-rules.pro` para
   kotlinx.serialization y OkHttp.

## APK de descarga directa en la web (`frontend/public/descargas/SIFEC.apk`)

La página `/app` de la web y el botón "Descargar la app" de `/cuenta` sirven el archivo
`frontend/public/descargas/SIFEC.apk` (ruta `/descargas/SIFEC.apk`; la ruta vieja
`/descargas/SIMPAC.apk` redirige con 301). Se regenera a mano porque hace falta la llave de Stadia
Maps (`-Psimpac.stadiaKey=...`, nunca en el repo). **Hoy no hay keystore propio**: todos los APK
publicados (el `2.0` del 23-11-2026 y el `2.1` del 25-11-2026) salen de `assembleDebug` firmados con
la llave de depuración (`~/.android/debug.keystore`) de la PC del equipo. Android solo instala una
actualización encima si lleva la misma firma, así que mientras no exista el keystore del proyecto hay
que seguir compilando en esa misma PC y con esa misma receta; el día que se pase a `assembleRelease`
con la llave propia (ver "Firma de la app"), quien ya tenga la app deberá desinstalarla una vez.
Pasos, desde `appmobile/android/` en PowerShell y con `JAVA_HOME` y `ANDROID_HOME` definidos:

1. Subir `versionCode` y `versionName` en `app/build.gradle.kts` (el `2.1` publicado va con `3`).
2. `.\gradlew.bat assembleDebug "-Psimpac.apiUrl=https://simpac-production.up.railway.app" "-Psimpac.webUrl=https://simpac-v7nf.vercel.app" "-Psimpac.stadiaKey=<llave>"`
   (entrecomillar cada `-P`: PowerShell parte el punto). Sale `app/build/outputs/apk/debug/app-debug.apk`.
3. Copiarlo sobre `frontend/public/descargas/SIFEC.apk` y comprobar con `aapt dump badging` que dice
   `versionCode='3'` (o el nuevo) y `package: name='pe.simpac.app'`, y con Python `zipfile` que
   `resources.arsc` no contiene `SIMPAC` (el `application-label` dice SIFEC desde el 10-11-2026, así
   que no distingue un APK viejo de uno nuevo; lo que distingue es el `versionCode`).
4. Desplegar la web (Vercel) para que `/descargas/SIFEC.apk` sea el archivo nuevo.

**Estado al 25-11-2026:** el `SIFEC.apk` publicado es el `2.1` (`versionCode 3`) compilado ese día con
el código ya renombrado: ningún texto dice SIMPAC por dentro; misma firma de depuración que el `2.0`,
así que se instala encima sin desinstalar.

## Publicar en Google Play

1. **Cuenta de desarrollador** en <https://play.google.com/console>: pago único de 25 USD y
   verificación de identidad (una cuenta personal nueva debe hacer además una prueba cerrada con al
   menos 12 probadores durante 14 días antes de publicar en producción).
2. **Crear la app**: nombre `SIFEC`, idioma español (Perú), tipo *App*, gratis.
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

- **Keystore propio**: el APK publicado (`frontend/public/descargas/SIFEC.apk`, `2.1`) va firmado con
  la llave de depuración de una sola PC (ver "APK de descarga directa en la web"); crear la llave del
  proyecto pronto y, al cambiar a ella, avisar que hay que desinstalar la app una vez.
- El mapa es nativo desde el 04-11-2026 (ver "Mapa nativo"); **falta probarlo en un teléfono real**
  y con la llave de Stadia en un release.
- Cuentas y comunidad nativas desde el 19-11-2026 (ver "Comunidad y cuentas"). La sesión de la app
  es propia (no se comparte con el navegador). **Pendiente:** registrar `<WEB>/cuenta` en Supabase
  Auth > Redirect URLs y probar con una cuenta real el recorrido completo (crear cuenta, confirmar en
  la web, entrar en la app, reportar con foto, votar y comentar): en el emulador se verificaron los
  formularios con datos inválidos, la lista pública y el formulario sin sesión. La contraseña nueva
  (enlace de "Olvidé mi contraseña") se elige en la web, no en la app. El chat por departamento sigue
  solo en la web.
- El departamento por GPS se decide con la estación de SENAMHI más cercana (como la web) y, si esa
  consulta falla, con la capital más cercana (aproximado en zonas de frontera como Jaén).
- Los chips de ríos salen de `rio_cauce_senal` (ríos con trazo de ANA) más el río vigilado del
  departamento (`rio_vigilado_mapa` + `rio_senal` + `caudal_actual`: el Mashcón, sin fila en `rio_cauce`);
  otro río vigilado solo necesita su fila en `rio_vigilado`.
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

## Interfaz: esqueletos, animaciones y estados

Desde el 19-11-2026 la app tiene un kit común en `ui/componentes/` para que todas las pantallas se
sientan iguales: nada bloquea la interacción, todo dura entre 150 y 300 ms con el easing de Material,
y ninguna animación se repite al recomponer ni al volver a una pestaña.

| Archivo | Qué hay | Cuándo usarlo |
|---|---|---|
| `Esqueletos.kt` | `Modifier.esqueleto(forma)` con brillo (shimmer) sobre `surfaceVariant`, correcto en modo oscuro; `EsqueletoLinea`, `EsqueletoBloque`, `EsqueletoCirculo`, `EsqueletoTarjeta` (mismo borde que `Seccion`) y `EsqueletoLista`; `ProveedorEsqueleto` / `rememberEsqueleto` (una sola transición infinita por pantalla, compartida por `LocalEsqueleto`; la banda de luz se calcula con la posición en la ventana, así que recorre toda la pantalla como una sola) | Primer cargado de una pantalla: en vez de "Cargando..." se dibuja la silueta de lo que va a aparecer. `ContenidoConEstado` ya pone el proveedor; fuera de él, envolver con `ProveedorEsqueleto` |
| `Estados.kt` | `ContenidoConEstado(cargando, error, onReintentar, esqueleto, contenido)` cruza esqueleto, error y contenido con fundido de 220 ms y tamaño animado; `ErrorReintentar(mensaje, onReintentar)` (icono, título, mensaje, botón, aparece con fundido; antes estaba en `Comunes.kt`); `EstadoVacio(icono, titulo, texto, accionTexto, onAccion)` sobrio y centrado | Toda pantalla que lea datos; listas sin resultados ("No hay alertas vigentes...") y pantallas sin sesión |
| `Animaciones.kt` | `Transiciones` (pestañas: fundido 200 ms; detalle: deslizamiento del 30 % + fundido 250 ms con sus inversos al volver; `aparecer` / `desaparecer` para `AnimatedVisibility`); `AparecerEscalonado(indice)` (fundido + subida de 12 dp con 35 ms por elemento, hasta 6, solo la primera vez: `rememberSaveable`); `Modifier.presionable(interactionSource)` (escala a 0,97 al pulsar); `ContadorAnimado(valor)` (el número sube o baja); `Haptica.toque / confirmar / rechazar(view)` con `HapticFeedbackConstants`, sin permisos | Entrada escalonada de las primeras tarjetas de cada pantalla, tarjetas que se tocan, contadores de votos y comentarios, vibración al votar, enviar o fallar |
| `Refrescar.kt` | `RefrescarAlTirar(refrescando, onRefrescar) { ... }` sobre `PullToRefreshBox` de Material 3 | Listas y pantallas con scroll que se recargan; `refrescando` es "recargando con datos ya en pantalla" (el primer cargado va con esqueleto) |
| `Avisador.kt` | `LocalAvisador` (un `SnackbarHostState` en el `Scaffold` de `AppSifec`, encima de la barra inferior) y `Avisador.avisar(mensaje, accion, duracion, onAccion)`, con un ámbito que vive lo que la app | Confirmaciones y errores breves ("Voto registrado", "Sin conexión" con "Reintentar") desde cualquier pantalla, también justo antes de navegar |
| `Comunes.kt` | `Seccion(titulo, modifier, accion) { ... }` (forma `medium` 14 dp, sin sombra, borde fino `outline`; `accion` opcional a la derecha del título), `bordeTarjeta()`, `AvisoDato` con tintas para claro y oscuro, `temaOscuro()`, `Cargando` (rueda, solo para esperas cortas sin silueta, como "Revisando tu sesión...") | Secciones de todas las pantallas |

`ui/Navegacion.kt` aplica `Transiciones` al `NavHost` (pestañas con fundido; `comunidad/nuevo` y
`comunidad/{id}` entran deslizando desde la derecha y vuelven hacia la derecha) y provee el snackbar
global; tocar una pestaña da una vibración corta. `ui/theme/Theme.kt` define las formas (`small` 8 dp,
`medium` 14 dp, `large` 20 dp) y completa los dos esquemas de color (contenedores, chips
seleccionados, snackbar, error) con la misma escala de grises azulados en claro y oscuro.

**Pantalla de arranque.** `androidx.core:core-splashscreen` 1.0.1: `MainActivity` usa el tema
`Theme.SIFEC.Splash` (`res/values/themes.xml`: fondo `@color/ic_launcher_background`, icono
`@drawable/ic_splash`, la gota al 80 % centrada en el área segura, y `postSplashScreenTheme`
`Theme.SIFEC`), llama `installSplashScreen()` antes de `super.onCreate` y pasa sola al tema normal con
el primer cuadro de Compose. El fondo de la ventana (`@color/fondo_app`, con variante en `values-night`)
es el mismo de la app para que no haya un destello al arrancar.
