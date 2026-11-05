# SIMPAC — Guía de medición (ISO/IEC 25010)

> Para llenar con datos reales las fichas del curso: **Ficha de registro de medición: Adecuación
> Funcional** (ICF, IPR, IFU), **Ficha de registro de medición: Eficiencia de Desempeño** (TRP, PUR,
> NUS) y los dos cuestionarios (usabilidad del sistema y acceso a la información). Las fichas y los
> cuestionarios están en `Proyecto_G01/` (carpeta del curso, fuera del repo).
> Actualizado: **2026-10-24** (los valores de referencia de la web se midieron la noche del 19 al 20
> de octubre de 2026, sobre el software desplegado en local después de reanudar la BD de Supabase,
> que estuvo pausada del 15 al 19 de octubre; la app Kotlin, el push y las zonas de los ríos del país
> se verificaron el 24 de octubre). Versión del software: la de la rama `main` con las 35
> migraciones aplicadas (última `20261020165455_rio_cauce_zona`).

Reglas de la guía:
- Se mide **lo que existe**: cada función de abajo tiene su archivo y su tabla. Lo que no está se
  cuenta como no implementado, no se maquilla (desde el 24-10 las notificaciones push existen y
  están verificadas; lo que sigue sin confirmar es el mapa nativo de la app en un teléfono real).
- Todo se corre contra el stack local (`docker compose up -d --build` desde la raíz): web en
  `http://localhost:8080`, API en `http://localhost:8000`, worker y redis. La BD es la de Supabase
  (proyecto DATASYMPAC), que la web consulta directo por la API REST de Supabase.
- Las pruebas de carga van **solo contra `localhost:8080` y `localhost:8000`**, nunca contra Supabase
  (es un proyecto gratuito compartido; cargarlo a propósito lo degrada para todos y puede violar sus
  términos). La web real depende de Supabase: eso se dice en la ficha como límite de la medición.
- Anotar siempre fecha, hora de Perú, máquina (CPU, RAM, sistema) y navegador con versión.

---

## 1. Adecuación funcional

### 1.1. ICF: cobertura de las 23 historias de usuario

Fuente: `Product Backlog.xlsx` (HU-01 a HU-23). "Estado real" es el del software al 2026-10-20,
verificado en el navegador, en la BD (consultas de solo lectura con psycopg) y en las pruebas
automáticas. El "Estado del backlog" es el que dice la hoja (desactualizado en varias filas).

| HU | Alias | Estado del backlog | Estado real | Dónde se ve (pantalla) | Código / tabla que lo prueba |
|---|---|---|---|---|---|
| HU-01 | Conector SENAMHI | Hecho | **HECHO** | Capas "Estaciones SENAMHI" y "Lluvia de la última hora"; barras de lluvia 24 h de la hoja "Tu zona ahora" | `backend/connectors/senamhi.py`, `senamhi_umbrales.py`; tarea `ingesta` (1 h) y `lluvia_nacional` (30 min); BD: `estacion` 991 filas en 24 departamentos, `lectura_lluvia` 5443 filas (15 estaciones de Cajamarca, desde el 26-06-2026), `lluvia_senamhi_actual` 176 |
| HU-02 | Conector ANA | Hecho | **HECHO** | Capa "Ríos": disco de cada estación con su nivel; medidor de caudal de la hoja | `backend/connectors/ana.py`; vista `caudal_actual`: 127 estaciones, 96 ríos, 23 departamentos; `lectura_caudal` 5832 filas (desde el 10-09-2026) |
| HU-03 | Conectores IGP + NOAA | Hecho | **HECHO** | Barra lateral ("mar más caliente", RONI) y panel "El Niño en gráficos" (ICEN mes a mes) | `backend/connectors/igp.py`, `noaa.py`; tablas `indice` e `icen_serie` (39 meses, hasta 2026-08) |
| HU-04 | Conector ENFEN | Hecho | **HECHO** | Barra lateral: "Comunicado ENFEN 18-2026, 16 oct. Próximo: 30 oct"; panel El Niño con los 3 pasos del sistema de alerta | `backend/connectors/enfen.py` (PDF con `pypdf`); tarea `enfen` (6 h); tabla `comunicado_enfen` (último: CO 18-2026, "Alerta de El Niño Costero") |
| HU-05 | Base de datos geoespacial | Hecho | **HECHO** | No se ve: lo usa todo | Supabase Postgres + PostGIS: **30 tablas, 16 vistas, 35 migraciones** en `supabase/migrations/` (al 24-10; el 20-10 eran 28, 15 y 32: se sumaron `push_estado`, `rio_cauce_zona` y `rio_cauce_zona_mapa`), RLS activo en 29 de 30 tablas (la que falta es `spatial_ref_sys`, de PostGIS, protegida con trigger); foto en `supabase/schema.sql`; 61 MB el 20-10 más 4,9 MB de `rio_cauce_zona` |
| HU-06 | Ingesta programada + motor de umbrales | Hecho | **HECHO** | Contador de alertas de la barra lateral y de la pestaña Alertas; hora "ríos ANA 00:49 · lluvia SENAMHI 00:49" | `backend/celery_app.py` (beat: `ingesta` cada 3600 s y 9 tareas más, `push` desde el 24-10), `backend/alerts.py` (umbrales de ANA y referencia de lluvia de SENAMHI); vista `alerta_actual`: 43 filas el 20-10 (32 aviso, 6 alerta por avisos de SENAMHI, 5 ríos muy bajos) |
| HU-07 | Mapa interactivo | Hecho | **HECHO** | Página `/` (Mapa): Leaflet con 15 capas en 7 grupos, selector de 25 ciudades, GPS, popups | `frontend/src/pages/Mapa.jsx`, `components/MapView.jsx`, `map/layers/*.js` (15 archivos), `data/cities.js` |
| HU-08 | Mapa de precipitaciones / anomalías con leyenda | Hecho | **HECHO** | Panel de capas, grupo "Lluvia": "Lluvia de la última hora (estaciones)", "Lluvia de ayer / de la semana", "Lluvia por satélite (NASA)", "Lluvia del mes frente a lo normal"; cada una con leyenda y nota de fecha | `map/layers/lluviaAhora.js`, `lluviaObservada.js`, `lluviaSatelite.js`, `anomalias.js`; tabla `mapa` (`variable = 'precipitacion'`, 1 muestra de Cajamarca) y servicios de SENAMHI/NASA en vivo |
| HU-09 | Panorama FEN (eventos pasados) | Hecho | **HECHO** | Panel "El Niño en gráficos" (botón de la barra lateral): estado ENFEN actual, ICEN de 24 meses y botones 1997-1998, 2017 y 2023 que pintan en el mapa cómo llovió; capa "Desbordes y daños pasados" del Mashcón (14 incidentes con fuente) | `components/ElNinoPanel.jsx`, `map/layers/fenHistorico.js`, `map/layers/desbordes.js`; tablas `mapa` (`FEN`, 5 eventos), `rio_incidente` (14) |
| HU-10 | Panel de alertas | Hecho | **HECHO** | Página `/alertas`: pestaña Vigentes con filtros (Mi zona / Todo el país, nivel, tipo), sección "Avisos de SENAMHI vigentes" y "Ríos vigilados" con "Ver en el mapa" | `pages/Alertas.jsx`, `lib/alertas.js` (con pruebas); vistas `alerta_actual`, `aviso_vigente` (4 avisos vigentes el 20-10) |
| HU-11 | API REST segura | Hecho | **HECHO** | No se ve; la usa la app Android y queda para terceros | `backend/app.py`: FastAPI solo GET, `/health` y `/api/snapshot` (46 087 bytes desde Redis), CORS solo a `SIMPAC_CORS_ORIGENES`; Supabase con RLS, permisos por columna, CHECK y triggers; Auth JWT para escribir |
| HU-12 | Configuración persistente (sin registro) | Hecho | **HECHO** | Panel de capas: pie "Tus capas se guardan en este navegador", botón "Restablecer capas"; recargar mantiene las capas | `hooks/useLayerVisibility.js`, `lib/preferencias.js` (`localStorage` clave `simpac.mapa`; con sesión, tabla `preferencia_mapa`) |
| HU-13 | Histórico de alertas | En proceso | **HECHO** | `/alertas`, pestaña "Pasadas": rango de fechas (hasta 30 días) y zona | `pages/Alertas.jsx` (`Pasadas`), `lib/queries.js getAlertasPasadas`; tabla `alerta` (43 filas en los últimos 30 días) |
| HU-14 | Histórico hidrometeorológico | Planificada | **HECHO** (rangos fijos 24 h / 7 d / 30 d, no fechas libres) | `/historico?tipo=rio&id=...` y `?tipo=lluvia&id=...` desde "Ver histórico" del popup de una estación: gráfico, tabla y "Descargar CSV" | `pages/Historico.jsx`, `components/GraficoSerie.jsx`, `lib/historico.js` (con pruebas); tablas `lectura_caudal`, `lectura_lluvia` |
| HU-15 | Mapas de eventos FEN pasados | Planificada | **HECHO** (solo el primer trimestre de cada evento) | Capa "Eventos El Niño pasados" con selector de evento (1982-83, 1997-98, 2017, 2023, 2023-24) y leyenda en mm frente a lo normal | `map/layers/fenHistorico.js`; tabla `mapa` (5 filas `FEN`, catálogo IDESEP de SENAMHI) |
| HU-16 | Titular interpretado (NLG) | En proceso | **HECHO** (por reglas; el redactor con modelo de lenguaje existe pero está apagado hasta poner `SIMPAC_LLM_KEY`) | Hoja "Tu zona ahora": titular corto ("ALERTA en Cajamarca: aviso naranja de SENAMHI por lluvias."; desde el 24-10 la tarjeta usa el `titular_corto` de la BD cuando está fresco y coincide en nivel: "Cajamarca: 3 avisos de SENAMHI por lluvias (el más alto, amarillo).") y chip de arriba; Inicio de la app Kotlin | `frontend/src/lib/zonaAhora.js titularCorto` (en el navegador) y `backend/ingesta/titular.py` (tarea `titular`, 30 min); tabla `titular_zona`: 25 departamentos, origen `reglas`, `titular_corto` de 43 a 100 caracteres |
| HU-17 | Cuentas: registro y login | Vacío | **HECHO** | `/cuenta`, `/cuenta/entrar`, `/cuenta/registro`: entrar, crear cuenta (correo, contraseña, nombre), "Olvidé mi contraseña", contraseña nueva; con sesión, nombre editable y "Cerrar sesión" | `pages/Cuenta.jsx`, `lib/sesion.js`, `hooks/useSesion.js`; Supabase Auth; tabla `perfil` (0 cuentas creadas al 20-10) |
| HU-18 | Reportes ciudadanos | Vacío | **HECHO** | `/comunidad/nuevo` (solo con sesión y GPS): 8 tipos estilo Waze, subtipo de atasco, descripción de hasta 500 letras, foto opcional (hasta 3 MB, reducida a 1280 px); capa "Reportes ciudadanos" y lista `/comunidad` | `pages/ReporteNuevo.jsx`, `lib/comunidad.js`, `lib/reportTypes.js`, `map/layers/incidentes.js`; tabla `report` (0 reportes al 20-10), bucket `reportes` (CHECK: la foto solo puede venir de ese bucket) |
| HU-19 | Validación comunitaria | Vacío | **HECHO** | `/comunidad/:id`: votos a favor / en contra y comentarios (hasta 500 letras) | `components/Votos.jsx`, `pages/ReporteDetalle.jsx`; tablas `voto`, `comentario` (la BD calcula `confianza` y `estado`; nadie vota su propio reporte) |
| HU-20 | Notificaciones push (FCM) | Vacío | **HECHO** (20-10, verificado de extremo a extremo el 24-10) | App Kotlin > Cuenta > interruptor "Avisarme si Cajamarca entra en alerta o emergencia"; la notificación "SIMPAC: ALERTA en <Depto>" (cuerpo = titular corto) llega al teléfono y al tocarla abre Alertas; "SIMPAC: vuelve la calma en <Depto>" al bajar. Nunca por aviso amarillo ni lluvia medida | `backend/ingesta/push.py` (tarea `push`, cada 5 min, 44 pruebas), tabla `push_estado` (memoria del último nivel notificado), `appmobile/android/.../push/` (temas `pais` y `zona_<slug>`); latido `push` del 24-10: `enviados 6` en la primera corrida (las alertas vigentes), después 0; prueba `--prueba --zona Cajamarca` recibida en el emulador. La web no recibe push |
| HU-21 | App móvil Android | Vacío | **HECHO** (app nativa con mapa nativo; falta probarla en un teléfono real) | APK `appmobile/android/app/build/outputs/apk/debug/app-debug.apk` (16 636 171 bytes, compilado el 04-11): app nativa en Kotlin + Compose con Inicio (semáforo y titular, botón "Ver el río en el mapa"), Alertas, **Mapa nativo con osmdroid** (desde el 04-11; antes era la web en un WebView con dos barras de navegación): avisos de SENAMHI, ríos del país con su estado, zonas que podrían inundarse, estaciones de SENAMHI, a dónde acudir, tu ubicación, hojas inferiores en lenguaje claro con fuente y hora; Acudir y Cuenta (la web se abre en el navegador del teléfono); probada en el emulador Pixel_7a | `appmobile/android/` (AGP 9.0.1, Kotlin 2.3.20, Compose BOM 2026.03.01, osmdroid 6.1.20, `pe.simpac.app`, minSdk 26, targetSdk 36, `versionCode 2`), 39 pruebas JVM (parser GeoJSON, estado de los ríos como `lib/cauces.test.js`, colores por nivel, cajas de la vista) + 4 de Compose UI; documentación en `appmobile/README.md`. La app anterior (Capacitor, APK de 5 304 253 bytes del 20-10) se retiró del repo el 24-10 |
| HU-22 | Mi zona y preferencias de notificación | Vacío | **HECHO** (la preferencia de notificación vive en la app, no en la cuenta web) | Web: `/cuenta` > "Mi zona": ciudad guardada en la cuenta (y en este navegador sin cuenta). App: Cuenta > Ajustes > departamento (o por GPS) e interruptor de notificaciones de esa zona (al cambiar de departamento se cambia el tema) | `lib/sesion.js guardarZona` (columna `perfil.zona`, punto de la ciudad), `guardarZonaLocal` (`simpac.zona`); app: `data/Ajustes.kt` (DataStore), `push/PushSimpac.kt` (suscripción a `pais` y `zona_<slug>`). Límite: la preferencia no se sincroniza con la cuenta web (la sesión no se comparte) |
| HU-23 | Chat por zona | Vacío | **HECHO** | `/chat`: canal = departamento, mensajes de 2 horas, en tiempo real, solo con sesión | `pages/Chat.jsx`, `lib/queries.js getMensajes/escucharMensajes/enviarMensaje`; tabla `message` (publicación `supabase_realtime`; 0 mensajes al 20-10) |

**Conteo para la ficha** (A = requeridas e implementadas, B = especificadas):

| Criterio | A | B | ICF |
|---|---|---|---|
| Al 20-10 (estricto: solo HECHO; HU-20 faltaba y HU-22 era parcial) | 21 | 23 | 91,3 % (Aceptable: 80-94 %) |
| **Al 24-10 (estricto: solo HECHO)** | 23 | 23 | **100 %** (Excelente: 95 % o más) |
| Al 24-10, conservador (HU-21 por la mitad mientras el mapa de la app no se confirme en un teléfono real) | 22,5 | 23 | 97,8 % (Excelente) |

Decirlo tal cual en "Observaciones": el push está verificado en el emulador con el envío real del
worker (24-10); la preferencia de notificación de HU-22 vive en la app (no en la cuenta web); el
mapa de la app es nativo desde el 04-11 y se verificó en el emulador; queda por confirmar en un teléfono real.

### 1.2. IPR: casos de prueba

Dos fuentes, y se reportan las dos:

**(a) Pruebas automáticas** (sin red ni BD; se corren desde la raíz del repo):

| Juego | Comando | Resultado el 2026-10-24 (el 20-10: 657 y 148) |
|---|---|---|
| Backend (conectores, ingesta, cargadores, API, titular, push, zonas de relieve) | `python -m unittest discover -s backend/tests -t .` | **720 pruebas, OK** (12 a 90 s según la máquina; 10 se omiten solas si no están numpy y shapely, que son del entorno aparte del relieve) |
| Frontend (lógica pura: nivel, zona, cauces, alertas, comunidad, histórico, acudir, iconos, atribución) | `cd frontend && npm test` (`node --test src/lib/*.test.js src/map/*.test.js`) | **157 pruebas, 157 pasan, 0 fallan** (0,8 a 1,2 s) |
| App Android (lógica pura: parseo, orden de alertas, distancia, slug del tema, "hace X", acudir, pronóstico, ríos) | `cd appmobile/android && .\gradlew.bat testDebugUnitTest` (PowerShell, JDK 21) | **22 pruebas, 0 fallas** (`DominioTest` 16, `ModelosTest` 6); las 4 de Compose UI (`connectedDebugAndroidTest`) necesitan emulador |
| Total | | **899 / 899 = 100 %** |

Anotar en la ficha la fecha, el commit (`git rev-parse --short HEAD`) y pegar la última línea de cada
comando ("Ran 720 tests ... OK", "pass 157 / fail 0" y "BUILD SUCCESSFUL" con el informe de
`app/build/reports/tests/testDebugUnitTest/index.html`).

**(b) Casos manuales.** Un caso por función visible. Cada evaluador ejecuta los casos y marca
Pasa / Falla / No aplica; C = pasan, D = ejecutados (los "No aplica" no cuentan en D). La columna
"Verificado 19/20-10" dice si el caso ya se ejecutó en la verificación adversarial de cierre (Sí) o
todavía no (No: necesita cuenta, GPS real o red cortada). Para los casos con cuenta, crear antes una
cuenta de prueba con un correo que el equipo controle (ver 3.1).

Convenciones: "hoja" = la tarjeta inferior "Tu zona ahora" (en escritorio, abajo a la izquierda);
"celular" = ventana de 375x812 (DevTools > Toggle device toolbar) o el APK.

| ID | Función (HU) | Pasos | Resultado esperado | IFU | Verificado 19/20-10 |
|---|---|---|---|---|---|
| CP-01 | Abrir la web (HU-07) | Abrir `http://localhost:8080` en una pestaña nueva | Mapa de Cajamarca con el río Mashcón rotulado; hoja "Tu zona ahora" con semáforo, titular y hora de las fuentes ("ríos ANA HH:MM · lluvia SENAMHI HH:MM"); chip de nivel arriba ("Alerta en Cajamarca" o el nivel del día); barra lateral con "Estado en Cajamarca" y contador de alertas; sin errores de la app en la consola (en el navegador integrado de la verificación salió solo un aviso al registrar el service worker, no reproducido en Chrome) | Sí | Sí |
| CP-02 | Bienvenida y permiso del GPS | Primera visita (o `localStorage.removeItem('simpac.gps')` y recargar) | Pantalla "Mira cómo está tu zona" con "Usar mi ubicación" y "Ahora no"; con permiso, el mapa va a tu punto (zoom 15) y la hoja dice "Tu ubicación (GPS)"; con "Ahora no" sigue en Cajamarca y no se vuelve a pedir | Sí | Sí |
| CP-03 | Cambiar de ciudad (HU-07) | Botón "Elegir ciudad" > Piura; luego Iquitos; Escape | 25 ciudades; al elegir cambian el chip, la barra lateral, la hoja y el mapa (Piura: "ALERTA en Piura: aviso naranja de SENAMHI por lluvias."; Iquitos: "Aviso en Loreto" con "ríos muy bajos", sin teléfonos); Escape cierra el selector | Sí | Sí |
| CP-04 | Mi ubicación | Botón "Mi ubicación" (ícono de brújula) con el GPS prendido | Mapa centrado en tu punto; la hoja muestra "A N km del río Mashcón" y "Dentro/Fuera de la zona que podría inundarse"; el departamento pasa al de tu posición | Sí | Sí (con posición emulada) |
| CP-05 | Panel de capas (HU-07) | Botón "Capas del mapa"; prender y apagar las 15 capas una por una | Cada capa dibuja algo, muestra su leyenda, su nota (qué es y de cuándo) y su fuente; "Restablecer capas" vuelve a las 6 por defecto (avisos, pronóstico, zonas, ríos, desbordes, reportes) | Sí | Sí |
| CP-06 | Capas recordadas (HU-12) | Prender "Estaciones SENAMHI", cerrar la pestaña, volver a abrir la web | Sigue prendida y el pie dice "Tus capas se guardan en este navegador"; en una ventana privada arranca con las de siempre y no rompe | Sí | Sí |
| CP-07 | Avisos de SENAMHI (HU-10) | Tocar un área de aviso (naranja sobre Cajamarca) | Popup con el número de aviso, nivel (p. ej. "Naranja, nivel 3 de 4"), "día N de M", el texto oficial sin cambios, "También rige aquí" si hay varios y enlace al aviso en senamhi.gob.pe | Sí | Sí |
| CP-08 | Selector de día | Botones Hoy / Mañana / (pasado mañana) | Los avisos y el pronóstico cambian juntos al día elegido; con la capa "Lluvia en las próximas 2 horas" prendida, el chip avisa "El nowcasting es solo para las próximas 2 horas: elige Hoy" | Sí | Sí |
| CP-09 | Pronóstico de 3 días | Agrandar la hoja a "media" (flecha "Agrandar el panel"); tocar el disco de tu localidad en el mapa | Franja de 3 días de tu localidad (SENAMHI) con glifo, máxima y mínima; el popup del disco trae el pronóstico de esa localidad con su fuente | Sí | Sí |
| CP-10 | Río Mashcón (HU-02) | Tocar el disco "Mashcón · Tranquilo 0,42 m³/s" (o el valor del día) | Popup con el caudal, la hora, los niveles de alerta y emergencia de ANA (14 / 18 m³/s), la tendencia y "Ver histórico"; el dato coincide con `caudal_actual` | Sí | Sí |
| CP-11 | Ríos del país | Alejar a zoom 6 (país) y 7 (región); tocar un río resaltado (Jequetepeque, Marañón); acercar a zoom 13 | A zoom 6 o menos los ríos con estación de ANA van en gris fino y solo los de alerta o emergencia conservan color; a zoom 7 u 8, todos más finos con su color; a zoom 13 el trazo fino de ~6 m; popup con el estado en palabras, la estación que manda, la hora de ANA y "SIMPAC resalta el cauce con el trazo de ANA - GeoSNIRH" | Sí | Sí (14-10 y 20-10) |
| CP-12 | Zonas que un río podría afectar | Capa prendida, zoom 13 y 14 sobre el Mashcón; tocar la franja rayada | Rayado (estimación SIMPAC con el relieve) y manchas lisas (INDECI-PNUD 2005), rotuladas como no oficiales y sin metros; "zona que podría inundarse" junto al río y la faja marginal punteada desde zoom 14; popup con "Pasó antes" y fuentes | Sí | Sí |
| CP-13 | Desbordes y daños pasados (HU-09) | Tocar un rombo con año ('14, '16, '25) | Popup con fecha, qué pasó, fuente con enlace; los rombos encimados se juntan ("×n") al alejar | Sí | Sí |
| CP-14 | Capas de lluvia (HU-08) | Prender, una por una: "Lluvia de la última hora (estaciones)", "Lluvia de ayer / de la semana", "Lluvia por satélite (NASA)", "Lluvia del mes frente a lo normal" | Cada una dibuja con leyenda en mm y nota con la fecha del dato; las estaciones que pasaron la referencia de SENAMHI llevan borde amarillo; si el servidor externo no responde, la nota lo dice en vez de quedar vacía | Sí | Sí |
| CP-15 | Quebradas que podrían activarse | Prender "Quebradas que podrían activarse (huaycos)" | Polígonos de SILVIA (SENAMHI) por nivel 2, 3 y 4 con su significado en la leyenda | Sí | Sí |
| CP-16 | Eventos El Niño pasados (HU-15) | Prender "Eventos El Niño pasados"; cambiar el evento en el selector | Polígonos coloreados por cuánto más o menos llovió que lo normal; la nota dice de qué meses es el mapa; los 5 eventos cargan | Sí | Sí |
| CP-17 | El Niño en gráficos (HU-03, HU-04, HU-09) | Botón "El Niño" de la barra lateral (también desde otra ruta) | Diálogo con los 3 pasos del sistema de alerta ENFEN (actual: "Alerta de El Niño Costero", CO 18-2026 del 16-10), barras del ICEN de 24 meses con el estimado punteado, botones 1997-1998 / 2017 / 2023 que prenden la capa en el mapa; Escape lo cierra y devuelve el foco | Sí | Sí |
| CP-18 | Alturas de la hoja | En celular: arrastrar el asa o usar "Agrandar / Achicar el panel"; en escritorio, las flechas | Celular: plegado -> vistazo -> media -> completa (4 alturas; arranca plegada); escritorio: vistazo -> media -> completa. En "media": medidor de caudal, barras de lluvia de 24 h, franja de 3 días y "A dónde acudir" | Sí | Sí |
| CP-19 | A dónde acudir | Botón "A dónde acudir" de la hoja (en alerta es el botón principal; si no, agrandar a "media") | Línea "Si hay emergencia: 105 Policía · 116 Bomberos · 106 SAMU" (enlaces `tel:`), 3 tarjetas: el hospital 24 h más cercano (a menos de 15 km; si no, el establecimiento más cercano), la comisaría y los bomberos, con distancia en línea recta, dirección y teléfono (o "Sin teléfono en la fuente"); "Ver en el mapa" prende la capa y abre el popup del punto. En Cajamarca centro: Hospital II Cajamarca (24 h, ~450 m), Comisaría Central (~170 m), Bomberos N° 59 (~450 m) | Sí | Sí |
| CP-20 | Capa Salud, comisarías y bomberos | Prender la capa; acercar a zoom 11, 12 y 13; tocar un marcador | Desde zoom 11 se dibujan (entre 11 y 12 solo salud 24 h); popup con nombre, categoría, "Atiende las 24 horas, según la fuente" solo si la fuente lo dice, teléfono `tel:`, "Cómo llegar" (Google Maps), fuente y fecha (RENIPRESS 30-09-2026; comisarías: padrón MININTER 2019) | Sí | Sí |
| CP-21 | Simulación de crecida (solo desarrollo) | `npm run dev` en `frontend/`; abrir `http://localhost:5173/?simular=mashcon:19` | Chip rojo "EMERGENCIA EN CAJAMARCA", titular "EMERGENCIA: el río Mashcón pasó su nivel de emergencia (ANA, HH:MM)", instrucción "Aléjate de la orilla…", botones 105 y 116, cauce rojo que late; en la build de producción el parámetro no hace nada | No (desarrollo) | Sí |
| CP-22 | Titular por departamento (HU-16) | Con la ciudad en Cajamarca, comparar el titular de la hoja con `select titular_corto from titular_zona where departamento = 'Cajamarca'`; cambiar a Loreto | El titular dice el nivel y la causa con la fuente ("aviso naranja de SENAMHI por lluvias"); Loreto: "aviso amarillo de SENAMHI por lluvias y 5 ríos muy bajos según ANA", nivel "aviso" (los ríos muy bajos no encienden la alerta); la web usa el texto de la BD solo si su nivel coincide con el que calcula | Sí | Sí |
| CP-23 | Alertas vigentes (HU-10) | Pestaña Alertas; filtros "Mi zona" / "Todo el país", nivel y tipo | Lista priorizada con nivel, fuente, hora y enlace oficial por tarjeta; el total de "Todo el país" coincide con el contador de la barra; "Todo el país" muestra las 5 de Loreto como "Río muy bajo"; el vacío dice la hora de la última revisión | Sí | Sí |
| CP-24 | Alertas pasadas (HU-13) | Pestaña "Pasadas"; rango de fechas (hasta 30 días) y zona | Tabla con las alertas del rango ("N registros entre el dd/mm y el dd/mm"); un rango sin datos muestra "No hubo alertas ni avisos en ese rango"; no deja más de 30 días | Sí | Sí |
| CP-25 | Avisos SENAMHI vigentes y ríos vigilados en Alertas | Misma página, secciones "Avisos de SENAMHI vigentes" y "Ríos vigilados" | Una tarjeta por aviso con el nivel más alto de sus áreas (el 424 y el 427 salen rojos) y los días que rige; "Ver en el mapa" del Mashcón vuelve al mapa con el cauce encuadrado | Sí | Sí |
| CP-26 | Histórico de caudal (HU-14) | Popup de una estación de ANA > "Ver histórico"; botones 24 h / 7 d / 30 d; "Descargar CSV" | `/historico?tipo=rio&id=...`: gráfico con los umbrales de ANA, resumen (último, máximo, mínimo), tabla de la más nueva a la más vieja y un CSV con las filas; un rango sin datos dice desde cuándo hay | Sí | Sí |
| CP-27 | Histórico de lluvia (HU-14) | Popup de una estación de SENAMHI de Cajamarca > "Ver histórico de lluvia" | `/historico?tipo=lluvia&id=<cod>`: mm por hora, total del rango, hora con más lluvia, temperatura si hay, CSV | Sí | Sí |
| CP-28 | Crear cuenta (HU-17) | Cuenta > "Crear cuenta": correo de prueba, contraseña de 6 o más, nombre | Pantalla "revisa tu correo" (o sesión directa si la confirmación está apagada en Supabase Auth); una contraseña corta da "La contraseña tiene que tener al menos 6 caracteres"; un correo inválido lo frena el navegador | Sí | Parcial (validaciones sí; alta real no) |
| CP-29 | Entrar y cerrar sesión (HU-17) | Cuenta > Entrar con la cuenta de prueba; luego "Cerrar sesión" | Con sesión: nombre en la barra lateral y en la pestaña Cuenta, correo, "Reputación: 0", "Mi zona", "Mis reportes"; al salir vuelven "Entrar / Crear cuenta". Entrar vacío da "Escribe un correo válido" | Sí | Parcial |
| CP-30 | Olvidé mi contraseña (HU-17) | "Olvidé mi contraseña" > correo | Formulario de correo, aviso de envío; al volver desde el enlace del correo, formulario de contraseña nueva | Sí | Parcial (formulario sí; correo no) |
| CP-31 | Mi zona (HU-22) | Con sesión: Cuenta > Mi zona > elegir Trujillo; abrir la web en otro navegador sin ciudad elegida y entrar | La zona se guarda en `perfil.zona` (consulta: `select zona from perfil` como el dueño); el segundo navegador arranca en Trujillo | Sí | No |
| CP-32 | Capas guardadas en la cuenta (HU-12) | Con sesión, cambiar capas; cerrar sesión y volver a entrar en otro navegador | El pie del panel dice "Tus capas se guardan en tu cuenta"; las capas vuelven en el otro navegador (tabla `preferencia_mapa`) | Sí | No |
| CP-33 | Comunidad sin sesión (HU-18) | Pestaña Comunidad; botón "Reportar" | Lista de reportes vigentes ordenados por confianza y cercanía, o "No hay reportes vigentes ahora"; "Reportar" sin sesión muestra "Entra para reportar" con botón a Cuenta; pie con el aviso "no oficial" | Sí | Sí |
| CP-34 | Crear un reporte (HU-18) | Con sesión y GPS: Reportar > tipo "Atasco" > subtipo > descripción > foto opcional > Enviar | El reporte aparece en la lista, en el mapa (gota) y en "Mis reportes"; dura 12 h; la descripción de más de 500 letras y la foto de más de 3 MB se rechazan antes de enviar; el sexto reporte en una hora lo rechaza la BD con mensaje en lenguaje claro; sin GPS no se puede enviar (no hay pin manual) | Sí | No (solo en la BD, con usuario temporal en una transacción revertida) |
| CP-35 | Votar y comentar (HU-19) | Con una segunda cuenta: abrir el reporte > "A favor" / "En contra" > comentar | El contador cambia y queda guardado al recargar; el propio reporte no se puede votar; un reporte vencido no admite comentarios ("Este reporte ya venció") | Sí | No |
| CP-36 | Reporte inexistente | Abrir `/comunidad/no-es-uuid` y `/comunidad/00000000-0000-0000-0000-000000000000` | "Este reporte ya venció o no existe", sin errores 4xx en la consola | No | Sí |
| CP-37 | Chat por zona (HU-23) | Con sesión en dos pestañas: Chat > escribir "prueba" (Enter envía) | El mensaje aparece en la otra pestaña sin recargar (realtime; sondeo cada 10 s de respaldo), con "vence en"; sin sesión la página pide entrar; el canal es el departamento (GPS o ciudad elegida); 31 mensajes en una hora los rechaza la BD | Sí | No |
| CP-38 | Rutas con recarga directa | Pegar en la barra `/alertas`, `/comunidad`, `/chat`, `/cuenta`, `/historico?tipo=rio&id=...`, `/noexiste`; botón atrás | Cada ruta carga sola (nginx devuelve `index.html`), el título de la pestaña cambia ("Alertas y avisos · SIMPAC"), el foco va al h1; `/noexiste` dice "Esta página no existe"; atrás vuelve al mapa sin recargarlo | No | Sí |
| CP-39 | Celular (RNF09) | Ventana de 375x812 (o el APK): recorrer Mapa, Alertas, Comunidad, Chat, Cuenta | Barra inferior de 5 pestañas de 56 px con el contador de alertas; hoja plegada de ~295 px con semáforo, titular y botones; atribución del mapa en una línea con botón "más"; sin desplazamiento horizontal; los popups caben entre la hoja y el borde | Sí | Sí |
| CP-40 | Teclado y lector de pantalla | Solo con Tab, Enter y Escape | El foco es visible en cada control; Escape cierra el selector de ciudad y el panel El Niño; con una página abierta sobre el mapa (celular), el mapa queda `inert` y Tab no entra a sus controles | No | Sí |
| CP-41 | API (HU-11) | `curl -i http://localhost:8000/health`; `curl -s http://localhost:8000/api/snapshot \| head -c 300`; `curl -sI -H "Origin: https://ejemplo.com" http://localhost:8000/health` | 200 `{"ok":true,"service":"simpac-api"}`; JSON con contexto El Niño, caudales y alertas; sin `Access-Control-Allow-Origin` para un origen ajeno y con él para `http://localhost:8080`; `HEAD` da 405 (solo GET) | No (técnico) | Sí |
| CP-42 | Worker (HU-01 a HU-06, HU-20) | `docker compose logs --tail=200 worker`; `select servicio, ts from latido order by servicio;` | 10 tareas registradas (avisos, enfen, ingesta, lluvia_nacional, nowcast, pronostico, push, refresh_cache, rios, titular; eran 9 hasta el 20-10), sin `Traceback`; un latido por servicio con hora de hoy; el de `push` con `credenciales: true` si el `.env` tiene la cuenta de servicio | No (técnico) | Sí (24-10) |
| CP-43 | App Android anterior, Capacitor (HU-21) | Instalar el `app-debug.apk` de `frontend/android/` en un teléfono (Android 7 o más) o en el emulador con `-memory 3072`; abrir | La app carga el mapa con sus tiles, el chip de nivel, el río Mashcón con sus rombos, la pantalla de bienvenida del GPS y la barra inferior; el GPS usa el del teléfono. (Desde el 20-10 la app es la Kotlin, CP-45 a CP-49; Capacitor se retiró del repo el 24-10: este caso queda solo como historia) | Sí | Sí (emulador Pixel_7a, 20-10) |
| CP-44 | Sin conexión (condición de error de RE01) | Con la web abierta, cortar la red (DevTools > Network > Offline) y recargar; volver a conectar | Si el service worker quedó registrado, la cáscara de la app abre sin red (`public/sw.js` guarda solo JS, CSS e `index.html`); la hoja dice "No se pudo consultar las alertas. Revisa tu conexión." y nunca sale "Normal" en verde sin datos; al volver la red los datos cargan solos en el siguiente refresco (10 min) o al recargar | No | No |
| CP-45 | App Kotlin: Inicio (HU-21, HU-16) | Instalar `appmobile/android/app/build/outputs/apk/debug/app-debug.apk` (Android 8 o más; emulador con `-memory 3072`); abrir; "Usar mi ubicación" o "Elegir departamento" | Disco grande del nivel con su etiqueta (nunca solo color), "Cajamarca · cambiar", tarjeta "Tu zona ahora" con el `titular_corto` y el detalle de `titular_zona` ("Generado el ... por reglas de SIMPAC con datos oficiales"), chips "N alertas oficiales" y del río con señales, "El Niño ahora" con el comunicado del ENFEN, pronóstico de 3 días de la localidad más cercana, botones "Llamar 105" y "Llamar 116", "Fuentes y hora" y el pie referencial; sin red, franja "Sin conexión" con la hora del último dato; sin titular, "Sin datos" | Sí | Sí (emulador Pixel_7a, 20-10 y 24-10) |
| CP-46 | App Kotlin: Alertas y Acudir (HU-10, HU-21) | Pestañas Alertas (chips Mi zona / Todo el país) y Acudir | Alertas: "N alertas y avisos oficiales en Cajamarca. Revisado <hora>", tarjetas con color + etiqueta, referencia, detalle, hora y "Fuente: SENAMHI"; la lluvia medida aparte y marcada como no oficial. Acudir: 105 / 116 / 115 / 106 (con la salvedad del SAMU y "Fuente: gob.pe"), "Lo más cercano desde ...", salud 24 h o el más cercano, comisaría y bomberos con distancia, "Llamar" y "Cómo llegar"; en Cajamarca centro: Hospital II Cajamarca a 453 m, Comisaría Central a 169 m | Sí | Sí (emulador, 20-10 y 24-10) |
| CP-47 | App Kotlin: notificaciones (HU-20, HU-22) | Cuenta > prender "Avisarme si <Depto> entra en alerta o emergencia" > aceptar el permiso; en el servidor `docker compose exec worker python -m backend.ingesta.push --prueba --zona <Depto>`; tocar la notificación | El interruptor queda encendido y dice "Recibirás avisos de alerta o emergencia de <Depto> y del país"; llega "SIMPAC: prueba en <Depto>" en el canal `alertas` (la primera vez puede tardar unos minutos); al tocarla la app abre la pestaña Alertas. Con una alerta real: "SIMPAC: ALERTA en <Depto>" con el titular corto; nunca por aviso amarillo ni lluvia medida; sin `google-services.json` el interruptor dice "no configuradas en esta instalación" | Sí | Sí (emulador, 24-10) |
| CP-48 | App Kotlin: Mapa nativo (HU-07, HU-21) | Pestaña Mapa; tocar el río Mashcón, un área de aviso y una zona rayada; botón "Capas" y apagar/prender capas; alejar con "−" hasta ver el país; Inicio > "Ver el río en el mapa"; Cuenta > "Abrir mi cuenta en la web" y "Comunidad" | Mapa nativo (tiles de Stadia Maps con la atribución visible abajo) centrado en tu punto o en la capital elegida (zoom 13), con una sola barra de navegación (la de la app); chip arriba "Alerta en Cajamarca" con el color del nivel; área amarilla del aviso de SENAMHI, el Mashcón azul con halo y rótulo "Río Mashcón", zonas rayada (bajo ~2 m) y del estudio INDECI (punteada), disco verde de la estación; al tocar el cauce, hoja "Río Mashcón - tranquilo 0.45 m³/s (ANA, hoy 18:00)" con "Sin señales ahora", niveles de alerta y emergencia, avisos sobre la cuenca, fuente y hora; al tocar el área, hoja "3 avisos de SENAMHI en este punto" con nivel en palabras, texto del día, qué hacer, vigencia y "Ver el aviso oficial"; la hoja "Capas" con interruptores y leyenda; alejado, los ~100 ríos del país con halo, los discos de las estaciones y las insignias (gota, termómetro) de los avisos; "Ver el río en el mapa" encuadra el río Cajamarca con sus estaciones; Cuenta abre el navegador del sistema. **Falta probarlo en un teléfono real** (en el emulador por software todos los cuadros son lentos: mediana 97 ms al desplazar Inicio, 250 ms al arrastrar el mapa a zoom 13, 500 ms a zoom 7) | Sí | Sí (emulador Pixel_7a, 04-11) |
| CP-49 | Zonas estimadas y franja de los ríos del país | Capa "Zonas que un río podría afectar" prendida; ciudad Lima, "Ver el río Rímac en el mapa" (zoom 16); tocar un polígono rayado. Franja: en desarrollo, `http://localhost:5173/?simular=rio:tumbes:alerta` con la ciudad en Tumbes | Junto al Rímac, polígonos rayados (bajo ~2 m) y lisos tenues (bajo ~3 m) con borde blanco, azules sin señales; popup con el método (HAND sobre Copernicus GLO-30), fuente, licencia y "Estimación de SIMPAC con el relieve; no es un mapa oficial", sin metros; la tarjeta dice "A 820 m del río Rímac (trazo de ANA)" y "Fuera de la zona que podría inundarse, a 680 m (estimación SIMPAC con el relieve)"; en Iquitos, "Este río no tiene mapa de zonas; la franja junto al cauce es solo referencial". Con la simulación: franja punteada naranja de 120 m a cada lado del Tumbes, leyenda "Franja de atención junto al río (referencial, no es un mapa de inundación)"; en producción el parámetro no hace nada | Sí | Sí (24-10; el popup de la zona y de la franja solo por código: el clic abrió el aviso) |

Conteo: 49 casos. Los 42 marcados "Sí" en la columna IFU son las funciones visibles para la
persona (F de la sección 1.3). De los 49, **43 ya se ejecutaron** (38 en la verificación del 19/20-10
y 5 de la app y las zonas el 24-10): 39 pasaron completos y 4 parcialmente (CP-28, CP-29 y CP-30,
cuyas validaciones de formulario pasaron pero no se creó ninguna cuenta real; CP-48, el mapa de la app
carga pero no se pintó en el emulador); **6 quedan por ejecutar** con cuenta de prueba, GPS o red
cortada (CP-31, CP-32, CP-34, CP-35, CP-37 y CP-44), más las partes con correo de CP-28 y CP-30 y
CP-48 en un teléfono real. No se declara IPR hasta correrlos: la ficha se llena con C y D reales del
día de la medición.

Cómo anotar una falla: ID del caso, paso en que falló, lo que se vio (captura), navegador, hora, y
si volvió a fallar al repetirlo. Una falla reproducible cuenta una vez aunque la vean 3 evaluadores.

### 1.3. IFU: funciones usadas de verdad

- **F (funciones disponibles) = 42**: las filas con "Sí" en la columna IFU de la tabla anterior (las
  37 del 20-10 más las 5 nuevas del 24-10: 4 de la app Kotlin y 1 de las zonas de los ríos del país;
  si la medición se hace solo en la web, F = 38 sin CP-45 a CP-48).
- **E (usadas regularmente)**: se observa, no se pregunta. Durante las sesiones de usabilidad
  (sección 3) el observador marca, por participante, qué funciones de las 42 usó por su cuenta
  (fuera de las 5 tareas guiadas, dar 5 minutos de uso libre al final). E = funciones que usó al
  menos la mitad de los participantes. Alternativa si solo hay cuestionario: preguntar al final
  "¿cuáles de estas usaría cada semana en temporada de lluvias?" con la lista de 42 y el mismo
  corte de la mitad.
- Las funciones que piden cuenta (CP-28 a CP-32, CP-34, CP-35, CP-37) bajan el IFU a propósito: la
  web está diseñada para consultar sin cuenta ("Para consultar no hace falta cuenta. Solo se pide
  para reportar, votar, comentar y chatear."). Decirlo en "Observaciones".

---

## 2. Eficiencia de desempeño

### 2.1. Preparación (una vez)

1. Stack arriba y fresco: `docker compose up -d --build` desde la raíz; `docker compose ps` debe
   listar `vigiafen-frontend-1` (0.0.0.0:8080->80), `vigiafen-backend-1` (0.0.0.0:8000->8000),
   `vigiafen-worker-1` y `vigiafen-redis-1`, todos `Up`.
2. Esperar 5 minutos después del arranque (el worker encola 9 tareas al arrancar, `titular` a los
   5 min y `push` a los 7, y `refresh_cache` corre a los 5 min: antes de eso `/api/snapshot` puede dar
   503 si Redis está vacío).
3. Cerrar lo demás (Android Studio, el emulador, otros navegadores): consumen CPU y RAM y ensucian
   el PUR.
4. Anotar la máquina. La de referencia: Intel Core i5-9300H (4 núcleos, 8 hilos), Windows 10,
   Docker Desktop con 7,68 GiB para los contenedores, navegador Chromium (el integrado del entorno
   de verificación); el generador de carga corrió en la misma máquina (los números son
   conservadores).

### 2.2. TRP: tiempo de respuesta ante una petición

La ficha pide "tiempo promedio de respuesta en consultas (T)". Se miden tres cosas y se reporta la
que ve la persona (la web) como T; las otras dos van como detalle.

**(a) Web: tiempo hasta ver el titular de "Tu zona ahora"** (lo primero que la persona lee).

Con DevTools (Chrome o Edge):
1. Abrir `http://localhost:8080`, F12, pestaña **Performance**, marcar "Screenshots".
2. Botón "Record and reload" (Ctrl+Shift+E). Esperar a que termine (3 a 5 s) y parar.
3. En la tira de capturas, ubicar el primer cuadro donde se lee el titular (p. ej. "ALERTA en
   Cajamarca: ...") y leer su tiempo. Anotar también LCP (marcador "LCP" en la pista Timings).
4. Repetir 5 veces con caché (recarga normal) y 5 veces sin caché (pestaña Network > "Disable
   cache" marcada). T = promedio de las 10.

Sin tira de capturas (pegar en la consola **después** de que la página cargó; da los mismos números
que la pestaña Network):

```js
const nav = performance.getEntriesByType("navigation")[0];
const rest = performance.getEntriesByType("resource").filter((e) => e.name.includes("/rest/v1/"));
const titular = rest.find((e) => e.name.includes("titular_zona"));
const lcp = await new Promise((r) =>
  new PerformanceObserver((l) => r(l.getEntries().at(-1)?.startTime)).observe({ type: "largest-contentful-paint", buffered: true })
);
console.table({
  domContentLoaded_ms: Math.round(nav.domContentLoadedEventEnd),
  load_ms: Math.round(nav.loadEventEnd),
  lcp_ms: Math.round(lcp),
  consultas_supabase: rest.length,
  primera_consulta_ms: Math.round(Math.min(...rest.map((e) => e.startTime))),
  ultima_respuesta_ms: Math.round(Math.max(...rest.map((e) => e.responseEnd))),
  titular_zona_respondio_ms: Math.round(titular?.responseEnd ?? -1),
});
```

`ultima_respuesta_ms` es cuándo terminó la última de las consultas a Supabase (todo el mapa con
datos); `lcp_ms` es cuándo se pintó el elemento más grande; el titular aparece entre
`titular_zona_respondio_ms` y el fin de las primeras consultas (la hoja también usa `alerta_actual`,
`caudal_actual` y las vistas del río).

**Referencia del 2026-10-20 (00:49 a 01:30, Lima, `localhost:8080`, Chrome, primera carga con caché
fría y luego recarga con assets en caché; medido con un sondeo del DOM cada 25 ms):**

| Medida | Valor |
|---|---|
| Titular visible (recarga con assets en caché) | **468 ms** desde el inicio de la navegación (11 de las 19 consultas ya respondidas) |
| DOMContentLoaded / load (con caché) | 106 ms / 114 ms |
| Consultas a Supabase al abrir | 19 peticiones REST, 0 duplicadas, a 17 vistas/tablas; arrancan a los 483 ms y la última termina a los **3216 ms** (caché fría) |
| `titular_zona` respondió | 727 ms |
| Peso servido (gzip por nginx) | `index-*.js` 154 838 B (445 544 sin comprimir), `supabase-*.js` 58 855, `react-*.js` 45 378, `leaflet-*.js` 43 143, CSS 19 666; páginas perezosas de 2,8 a 16 KB |

Con la ficha: T de la web = 0,47 s (titular) -> **Excelente (< 2 s)**. La última consulta de la
primera carga (3,2 s con caché fría) es el mapa completo con sus 15 capas de datos, no la
consulta: anotarla como detalle.

**(b) API propia** (`/api/snapshot` sale de Redis; `/health` no toca nada). 10 repeticiones:

```bash
# Git Bash / Linux / macOS
for i in $(seq 1 10); do curl -s -o /dev/null -w "snapshot %{http_code} %{time_total}s %{size_download}B\n" http://localhost:8000/api/snapshot; done
for i in $(seq 1 10); do curl -s -o /dev/null -w "health %{http_code} %{time_total}s\n" http://localhost:8000/health; done
for i in $(seq 1 10); do curl -s -o /dev/null -w "web %{http_code} %{time_total}s\n" http://localhost:8080/; done
```
```powershell
# PowerShell (curl.exe, no el alias de Invoke-WebRequest)
1..10 | ForEach-Object { curl.exe -s -o NUL -w "snapshot %{http_code} %{time_total}s %{size_download}B`n" http://localhost:8000/api/snapshot }
```

Referencia del 20-10 (3 repeticiones cada una): `/health` 3,4 a 7,7 ms; `/api/snapshot` 13,1 a
17,0 ms con 46 087 bytes; `index.html` 3,3 a 4,3 ms; `index-*.js` comprimido 3,3 ms. Un pedido
desde el navegador integrado dio 28 ms. Todo muy por debajo de 2 s.

**(c) Supabase (lo que la web consulta de verdad).** Es un servidor externo (São Paulo), así que
este número depende de la red. Se mide con la llave pública del frontend (`frontend/.env`,
`VITE_SUPABASE_PUBLISHABLE_KEY`: es pública por diseño, pero igual se lee del archivo y no se pega
en documentos):

```bash
set -a; . frontend/.env; set +a      # carga VITE_SUPABASE_URL y VITE_SUPABASE_PUBLISHABLE_KEY
for v in "titular_zona?select=departamento,nivel,titular_corto&departamento=eq.Cajamarca" \
         "alerta_actual?select=*" "caudal_actual?select=*" "aviso_vigente?select=id,nivel,fin"; do
  curl -s -o /dev/null -w "$v -> %{http_code} %{time_total}s %{size_download}B\n" \
    -H "apikey: $VITE_SUPABASE_PUBLISHABLE_KEY" -H "Authorization: Bearer $VITE_SUPABASE_PUBLISHABLE_KEY" \
    "$VITE_SUPABASE_URL/rest/v1/$v"
done
```

Repetir 5 veces cada una y promediar. Referencia del 20-10 desde el navegador: la consulta
`titular_zona` respondió a los 727 ms del inicio de la carga (unos 250 ms de ida y vuelta una vez
arrancada). Si la BD está pausada (proyecto gratuito sin uso por 7 días) todo responde error: revisar
primero en el panel de Supabase que el proyecto esté activo.

### 2.3. PUR: uso de recursos

La ficha promedia tres porcentajes (CPU, RAM y red) durante la ejecución; el informe define
PUR = promedio de los tres. Se toman **10 muestras, una cada 30 s, durante 5 minutos**, mientras
una persona usa la web siguiendo el guion de la sección 3 (así la medición es con uso real, no con
la pestaña quieta).

**Del equipo (lo que pide la ficha):** Administrador de tareas (Ctrl+Shift+Esc) > Rendimiento:
- CPU: el porcentaje grande ("Utilización").
- Memoria: "En uso / total" -> B = en uso ÷ total × 100.
- Red (Ethernet o Wi-Fi): el gráfico da kbps; C = (recepción + envío) ÷ velocidad del enlace × 100
  (la velocidad del enlace sale en la misma pantalla, p. ej. 866 Mbps en Wi-Fi). Como la web pesa
  poco (unos 350 KB la primera vez y nada después, salvo tiles y datos), C saldrá cerca de 0 %:
  anotarlo así.
Macos: Monitor de Actividad, pestañas CPU, Memoria y Red. Linux: `top`/`htop` y `nload`.

**De los contenedores (detalle para "Observaciones"):**

```bash
# Git Bash: 30 muestras cada 10 s = 5 min, a un archivo
for i in $(seq 1 30); do docker stats --no-stream --format "{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}} ({{.MemPerc}}) net={{.NetIO}}" >> pur.txt; sleep 10; done
```
```powershell
1..30 | ForEach-Object { docker stats --no-stream --format "{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}} ({{.MemPerc}}) net={{.NetIO}}" | Out-File -Append pur.txt; Start-Sleep 10 }
```

`CPUPerc` de `docker stats` es relativo a **un** núcleo (puede pasar de 100 %); para compararlo con
el equipo dividir entre el número de hilos (8 en la máquina de referencia). `MemPerc` es sobre la
memoria asignada a Docker (7,68 GiB en la de referencia), no la del equipo.

**Referencia del 2026-10-20 (contenedores recién reconstruidos, web abierta en una pestaña):**

| Contenedor | CPU (de un núcleo) | Memoria | Nota |
|---|---|---|---|
| `vigiafen-frontend-1` (nginx) | 0,00 % en reposo; 154 a 170 % con 50 conexiones de carga (= 19 a 21 % de los 8 hilos) | 9,0 MiB (0,11 %) | solo sirve archivos |
| `vigiafen-backend-1` (FastAPI) | 0,13 a 0,50 % en reposo | 43,5 MiB (0,55 %) | sirve el snapshot desde Redis |
| `vigiafen-worker-1` (Celery + beat) | 0,06 a 1,32 % entre corridas | 352,9 MiB (4,49 %) | sube durante las tareas de la hora en punto |
| `vigiafen-redis-1` | 0,71 % | 8,7 MiB (0,11 %) | |

En reposo los 4 contenedores suman menos de 1 % de CPU y unos 415 MiB. El PUR del **equipo** (lo
que pide la ficha) se mide el día de la prueba con el Administrador de tareas; con la máquina de
referencia el navegador con la web abierta es la parte más pesada y el total queda lejos del 40 %,
pero ese número hay que tomarlo, no suponerlo.

### 2.4. NUS: usuarios simultáneos

Qué se mide: cuántas conexiones simultáneas aguanta el stack local sin degradarse. Se sube la
concurrencia en escalera (20, 50, 100) y se busca el mayor escalón que cumple **las dos** condiciones:
0 errores (o menos del 1 %) **y** latencia p95 por debajo de 2 s (el mismo límite del TRP). Ese
escalón es NUS. Se corre contra la web (`:8080`, lo que carga el navegador) y contra la API
(`:8000/api/snapshot`, lo que carga la app Android); **nunca contra Supabase**.

**Con autocannon** (Node; no hace falta instalarlo, `npx` lo baja; versión fijada):

```bash
npx --yes autocannon@7.15.0 -c 20  -d 10 http://localhost:8080/
npx --yes autocannon@7.15.0 -c 50  -d 10 http://localhost:8080/
npx --yes autocannon@7.15.0 -c 100 -d 10 http://localhost:8080/
npx --yes autocannon@7.15.0 -c 50  -d 10 http://localhost:8000/api/snapshot
npx --yes autocannon@7.15.0 -c 100 -d 10 http://localhost:8000/api/snapshot
```

Cómo leer la salida: la tabla "Latency" trae 2,5 %, 50 %, 97,5 % y 99 % (autocannon no imprime el
p95: usar **97,5 % como p95 conservador**; con `--json` sale `latency.p97_5` y `p99`). "Req/Sec" es
el caudal. Al final, "N requests in 10 s" y "M errors": M son conexiones que el servidor cerró o
rechazó. `-c` es la cantidad de conexiones abiertas a la vez, que es lo que la ficha llama usuarios
simultáneos (cada una pide sin pausa, más exigente que una persona real).

**Con k6** (si prefieren p95 exacto y rampa; instalar desde k6.io o `winget install k6`), archivo
`carga.js`:

```js
import http from "k6/http";
import { sleep } from "k6";
export const options = {
  stages: [{ duration: "30s", target: 20 }, { duration: "30s", target: 50 }, { duration: "30s", target: 100 }],
  thresholds: { http_req_duration: ["p(95)<2000"], http_req_failed: ["rate<0.01"] },
};
export default function () {
  http.get("http://localhost:8080/");
  http.get("http://localhost:8000/api/snapshot");
  sleep(1); // una persona no pide sin parar: 1 s entre pedidos
}
```
`k6 run carga.js` imprime `http_req_duration ... p(90) p(95)` y marca en verde o rojo los umbrales;
NUS = el mayor `target` de la rampa en que los dos umbrales siguen en verde (ver la salida por etapa
con `--summary-trend-stats` o repetir con un solo `target`).

**Referencia del 2026-10-20 (autocannon 7.15.0 en la misma máquina que Docker, 10 s por corrida):**

| Objetivo | Conexiones | p50 | p97,5 | p99 | Máx. | Req/s | Pedidos | Errores |
|---|---|---|---|---|---|---|---|---|
| `:8080/` (nginx, `index.html`) | 20 | 5 ms | 21 ms | 27 ms | 91 ms | 5364 | 54 000 | 27 (0,05 %) |
| `:8080/` | 50 | 7 ms | 33 ms | 46 ms | 475 ms | 4971 | 50 000 | 17 (0,03 %) |
| `:8080/` | 100 | 13 ms | 30 ms | 36 ms | 179 ms | 6752 | 68 000 | 0 |
| `:8000/api/snapshot` (46 KB JSON) | 50 | 542 ms | 868 ms | 936 ms | 1380 ms | 89 | 944 | 0 |
| `:8000/api/snapshot` | 100 | 873 ms | 2385 ms | 4996 ms | 9266 ms | 101 | 1000 | 0 |

Lectura: la web estática aguanta 100 conexiones con p99 de 36 ms y 0 errores (los 17 a 27 errores
de las corridas de 20 y 50 son conexiones reiniciadas por el loopback de Windows bajo ráfaga, no
respuestas de error; repetir en Linux o en otra máquina para confirmar). La API cumple con 50
(p99 0,94 s, 0 errores) y con 100 ya pasa de 2 s en el p97,5: su NUS es **50** con un solo proceso
de uvicorn (se sube con `--workers 4` en el `command` del servicio `backend` de
`docker-compose.yml`, lo que no se probó esta noche). Para la ficha: **NUS = 100 para la web y 50
para la API -> Excelente (> 50) y Aceptable (20-50)** respectivamente; reportar el de la API como el
límite honesto del stack propio.

Límite que hay que escribir en "Observaciones": la web real lee Supabase, que no se puede cargar a
propósito. Con 50 personas reales abriendo la web a la vez, cada una hace 19 consultas REST a
Supabase (unas 950 en total); el plan gratuito y el pooler tienen límites de conexiones que SIMPAC no
controla. La API propia y el snapshot en Redis existen justamente para que la app móvil no dependa de
eso.

### 2.5. Resumen para la ficha de Eficiencia

| Indicador | Cómo se llena | Referencia 20-10 | Rango de la ficha |
|---|---|---|---|
| TRP | T = promedio de 10 recargas, tiempo hasta el titular (o LCP) | 0,47 s (titular); API 0,013 a 0,017 s | Excelente < 2 s |
| PUR | (CPU % + RAM % + red %) ÷ 3 del equipo, 10 muestras en 5 min con uso real | contenedores en reposo < 1 % CPU, 415 MiB; equipo: medir ese día | Excelente < 40 % |
| NUS | mayor escalón con 0 errores y p95 < 2 s | web 100; API 50 | Excelente > 50 |

---

## 3. Usabilidad: guion de 5 tareas

Para el "Cuestionario de evaluación de usabilidad del sistema inteligente" (ítems de tiempo por
tarea, tiempo de aprendizaje y errores) y el de "Acceso a información" (minutos para encontrar la
información, tasa de éxito, pasos). Muestra del informe: n = 100, adultos de la ciudad de Cajamarca
con celular o computadora.

### 3.1. Preparación

- Dispositivo: mientras la web solo corra en `localhost:8080`, el celular del participante no
  puede abrirla. Usar la PC del equipo con la web local, o el APK instalado en un teléfono del
  equipo (CP-43), o una dirección pública si para la fecha hay despliegue. Anotar cuál se usó.
- GPS: en PC pedirá permiso de ubicación del navegador (funciona con la ubicación aproximada); en el
  teléfono, GPS prendido. Sin ubicación, la tarea 2 se hace "desde el centro de Cajamarca" (lo dice la
  hoja) y la tarea 5 no se puede completar (el reporte exige GPS): anotarlo como "no aplica", no como
  falla del participante.
- Cuentas: la tarea 5 pide cuenta. Crear antes 2 o 3 cuentas de prueba (`prueba1@...`) con
  contraseña conocida por el equipo, o decidir en Supabase Auth si se apaga la confirmación por
  correo durante las sesiones; las Redirect URLs de Auth para los correos de confirmación y
  recuperación todavía están pendientes de configurar (ver `ESTADO.md`). Los reportes de prueba
  vencen solos a las 12 h; los mensajes del chat a las 2 h.
- Sin explicar la app antes: la persona la ve por primera vez (así el ítem 3 del cuestionario mide
  aprendizaje real). Solo se le dice qué buscar, no dónde.
- Un observador cronometra cada tarea (desde que termina la consigna hasta que la persona dice la
  respuesta), cuenta los **errores** (toques o clics que no llevan a la tarea, volver atrás, abrir
  otra pestaña por equivocación) y anota si pidió ayuda. Estado del día: las respuestas correctas
  dependen de los datos de ese día (el nivel, el aviso vigente); el observador las lee antes en la
  misma pantalla.

### 3.2. Las 5 tareas

| N.º | Consigna (leerla tal cual) | Camino esperado | Respuesta correcta (criterio de éxito) | Tiempo esperado | Pasos mínimos |
|---|---|---|---|---|---|
| T1 | "Dígame cómo está hoy su zona: si hay algo de qué cuidarse y por qué." | Abrir la web; leer el semáforo y el titular de la hoja "Tu zona ahora" (no hay que tocar nada; en celular la hoja arranca plegada con el titular a la vista) | Dice el nivel (p. ej. "alerta") y la causa con la fuente ("aviso naranja de SENAMHI por lluvias") o el estado de calma; en alerta, también la instrucción ("Evita quebradas y laderas...") | **menos de 30 s** | 0 a 1 |
| T2 | "¿El río le puede afectar a usted, donde está ahora?" | Agrandar la hoja a "vistazo" (celular) o leer los chips en escritorio: "A N km del río Mashcón" y "Dentro / Fuera de la zona que podría inundarse"; opcionalmente "Ver mi zona en el mapa" (franja rayada) | Dice la distancia al río y si está dentro o fuera de la zona que podría inundarse; si usa el mapa, señala la franja rayada junto al río | **menos de 1 min** | 1 a 2 |
| T3 | "Si pasara algo grave, ¿a dónde iría o a quién llamaría? Encuéntrelo en la app." | Botón "A dónde acudir" de la hoja (botón principal en alerta/emergencia; si no, agrandar a "media" y bajar a la sección) | Nombra el hospital más cercano con su distancia (Hospital II Cajamarca a ~450 m desde el centro) o la comisaría o los bomberos, o lee los números 105 / 116 / 106 | **menos de 1 min** | 1 a 3 |
| T4 | "¿Va a llover mañana y pasado mañana en su localidad?" | Hoja a "media" -> franja de 3 días de SENAMHI; o selector de día "Mañana" -> disco de la localidad en el mapa y su popup | Dice para los 2 días siguientes si SENAMHI pronostica lluvia (o "puede llover") y, si quiere, las temperaturas | **menos de 1,5 min** | 2 a 3 |
| T5 | "Reporte en la app que hay un atasco leve donde está usted." | Botón "Reportar" (o Comunidad > Reportar) -> "Entra para reportar" -> entrar con la cuenta de prueba (o crearla) -> tipo "Atasco" -> subtipo "Leve" -> descripción corta -> Enviar | El reporte aparece en la lista de Comunidad y en el mapa con la gota del tipo; la persona ve "Es un reporte comunitario, no oficial..." | **menos de 2 min con cuenta ya creada; menos de 4 min creando la cuenta** | 5 a 7 (con cuenta); 9 a 11 (creándola) |

Después de las 5 tareas: 5 minutos de uso libre (para el IFU de 1.3) y el cuestionario.

### 3.3. Qué anotar y a qué ítem va

| Dato observado | Cómo se registra | Ítem del cuestionario que respalda |
|---|---|---|
| Tiempo de T1 (información clave) | cronómetro, segundos | Usabilidad ítem 1; Acceso ítem 1 (comparar con los minutos que declara tardar hoy con otros medios) |
| Tiempo de T2 a T5 (una tarea completa) | segundos por tarea; promedio | Usabilidad ítem 2 |
| Tareas completadas sin ayuda ÷ 5 | por participante; promedio de la muestra | Acceso ítem 2 (tasa de éxito) |
| Pasos que dio en T1 y T4 | contar toques/clics hasta la respuesta | Acceso ítem 3 (pasos para llegar a un reporte completo) |
| Errores en las 5 tareas | toques fuera del camino, retrocesos | Usabilidad ítem 5 |
| Preguntas que hizo y cuánto tardó en resolverlas | minutos | Usabilidad ítem 4 |
| Minutos desde que abrió la app hasta completar T1 y T2 sin ayuda | reloj | Usabilidad ítem 3 (aprendizaje) |

Los tiempos esperados de arriba son el diseño (lo que la interfaz permite en el mejor caso, medido
por el equipo que la conoce); los tiempos de la ficha son los **observados** con los participantes.
Si la mediana observada de T1 supera 2 minutos, la hoja "Tu zona ahora" no está cumpliendo su
objetivo y hay que decirlo.

---

## 4. Trazabilidad de requerimientos

Fuente: `Documentación de requerimientos de software` v1.0 (RE01-RE07, RNF01-RNF11). El documento
cubre el módulo A (v1); los módulos B (Cuentas), C (Comunidad) y D (Chat) también quedaron hechos
(ver HU-17 a HU-19 y HU-23); E (Notificaciones) quedó hecho el 24-10 (HU-20, push por FCM a la app
Kotlin); F (Administración) no, y se descartó por decisión del equipo del 15-09 (sin administración
ni moderación humana).

### 4.1. Requerimientos funcionales

| RE | Requisito | Pantalla / dónde se ve | Código y datos | Estado y evidencia del 20-10 |
|---|---|---|---|---|
| RE01 | Ver la información más reciente sobre eventos FEN al entrar | Página `/`: hoja "Tu zona ahora" (semáforo, titular, hora de las fuentes), barra lateral (estado ENFEN, ICEN/RONI), chip de nivel | `pages/Mapa.jsx`, `components/StatusPanel.jsx`, `TuZona.jsx`, `Sidebar.jsx`; `hooks/usePanorama.js` (refresco cada 10 min), `useZonaAhora.js`; vistas `alerta_actual`, `caudal_actual`, `comunicado_enfen`, `indice`, `latido` | HECHO. Titular a los 468 ms; "sin actualizar desde" en naranja si la ingesta pasa de 3 h (ríos) o 1,5 h (lluvia); nunca "Normal" sin datos ("Sin datos") |
| RE02 | Recolección automática de ANA, IGP, NOAA, SENAMHI y ENFEN | No se ve; se audita en `latido` y en los logs del worker | `backend/connectors/` (12 conectores: senamhi, ana, igp, noaa, enfen, senamhi_avisos, senamhi_umbrales, senamhi_pronostico, senamhi_nowcast, senamhi_avisos_hidro, ana_rios, idesep, más el ayudante `_http.py`), `backend/ingesta/`, `backend/celery_app.py` (10 tareas con Celery beat desde el 24-10, 9 el 20-10; el documento decía apscheduler) | HECHO. Arranque del 20-10 sin Traceback: ingesta 11,2 s (973 estaciones, 720 lluvia, 127 caudales), avisos 7,1 s, enfen 5,7 s, lluvia_nacional 4,9 s, rios 4,3 s, pronostico 2,9 s, nowcast 2,7 s, titular a los 5 min. Fuente caída: se conserva el último dato y queda en `fallas` del latido; TLS siempre verificado |
| RE03 | Información climatológica resaltante | Panel "El Niño en gráficos"; franja de 3 días; barras de lluvia de 24 h; medidor de caudal | `components/ElNinoPanel.jsx`, `FranjaPronostico.jsx`, `BarrasLluvia.jsx`, `MedidorCaudal.jsx`; `icen_serie`, `pronostico_vigente` (236 localidades con punto), `lectura_lluvia`, `caudal_actual` | HECHO |
| RE04 | Buscar y mostrar el mapa correspondiente (por defecto si no hay específico) | Panel de capas (15 capas, 7 grupos); selector de ciudad y GPS deciden la zona; capas sin dato muestran nota en vez de vaciarse | `map/layers/index.js` (`LAYERS`, `GRUPOS`), `components/LayersPanel.jsx`, `MapView.jsx`; `data/cities.js` (25) | HECHO. Un servidor externo caído (NASA, IDESEP) deja la nota "no respondió" y la capa se reintenta |
| RE05 | Mapa de eventos FEN pasados | Capa "Eventos El Niño pasados" con selector de evento; botones del panel El Niño | `map/layers/fenHistorico.js`; tabla `mapa` (5 eventos IDESEP, trimestre inicial de cada uno) | HECHO (pendiente cargar los demás trimestres: `ESTADO.md`) |
| RE06 | Mapa de precipitaciones | Grupo "Lluvia": última hora (estaciones), ayer / semana, satélite NASA, mes frente a lo normal; nowcasting de 2 h (experimental); avisos de SENAMHI como áreas | `map/layers/lluviaAhora.js`, `lluviaObservada.js`, `lluviaSatelite.js`, `anomalias.js`, `nowcast.js`, `avisos.js`; `lluvia_senamhi_actual`, `aviso_vigente`, `nowcast_vigente` | HECHO. Fecha del dato en la nota de cada capa; sin dato reciente (nowcasting > 30 min) la capa se vacía y lo dice |
| RE07 | Histórico hidrometeorológico por estación y rango | `/historico` desde "Ver histórico" del popup; `/alertas` > Pasadas | `pages/Historico.jsx`, `lib/historico.js`, `components/GraficoSerie.jsx`; `lectura_caudal` (desde 10-09-2026), `lectura_lluvia` (15 estaciones de Cajamarca desde 26-06-2026), `alerta` (30 días) | HECHO con rangos fijos 24 h / 7 d / 30 d; vacío con "Hay datos desde el ..." si el rango no tiene; CSV. Fechas libres: no |

### 4.2. Requerimientos no funcionales

| RNF | Requisito | Cómo se cumple (código) | Evidencia / cómo medirlo | Estado |
|---|---|---|---|---|
| RNF01 | Interfaz intuitiva para población sin formación técnica | Lenguaje claro en un solo diccionario (`lib/lenguaje.js`, `lib/zonaAhora.js`, `lib/avisoTexto.js`): "lleva el 1 % del caudal que activa la alerta", "puede llover en algún momento"; semáforo con ícono (nunca solo color); una instrucción por nivel; números 105/116 a un toque | Sección 3 (guion y cuestionario SUS); revisión de textos del 19/20-10 contra las fuentes | HECHO; **falta medir con usuarios** |
| RNF02 | Disponible 99 % del tiempo, sobre todo en eventos FEN | Docker con `restart: unless-stopped`; snapshot en Redis si Supabase cae (la API sirve la última copia buena); SW con la cáscara de la app | Anotar caídas. **Hallazgo real**: la BD de Supabase (plan gratuito) se pausó sola del 15 al 19 de octubre por falta de uso; en ese lapso la web no tenía datos. Para 99 % hace falta plan de pago o un "latido" que la mantenga activa, y un despliegue público (hoy solo local) | **NO CUMPLIDO** en octubre; medir con `uptime` cuando haya despliegue |
| RNF03 | Consultas y mapas en menos de 3 s | gzip precomprimido, chunks separados, preconnect a Supabase, 19 consultas en paralelo sin cascada, caché por vista (`lib/consultaCache.js`), geometrías por zoom (`cauce_lejos` / `cauce`), Redis para la API | Sección 2.2: titular 0,47 s; API 0,013 a 0,017 s; última consulta de la primera carga 3,2 s con caché fría (mapa completo) | HECHO para el titular y la API; el mapa completo en frío queda en el borde |
| RNF04 | Soportar aumento de usuarios y datos | nginx estático + caché inmutable de 1 año; API sin BD (Redis); Supabase administrado con pooler; páginas perezosas | Sección 2.4: web 100 conexiones con p99 36 ms; API 50 conexiones con p99 0,94 s con 1 proceso | HECHO en el stack propio; Supabase es el límite no medido |
| RNF05 | Android 14 (API 34) y navegadores modernos | App Kotlin: minSdk 26 (Android 8.0), targetSdk 36 (`appmobile/android/app/build.gradle.kts`); la anterior de Capacitor, retirada el 24-10, tenía minSdk 24; web probada en Chrome | CP-45 a CP-48 (emulador Pixel_7a con Android 17, 24-10 y 04-11); **no probado en Safari ni Firefox**; el mapa nativo de la app, pendiente en teléfono real | HECHO para Android y Chrome; pendiente Safari/Firefox/Edge |
| RNF06 | Confidencialidad e integridad de datos y credenciales | RLS en todas las tablas de datos (27 de 28; `spatial_ref_sys` con trigger); escritura solo con JWT de Supabase Auth; la BD pone `estado`, `confianza`, vencimientos y límites por hora; CHECK de `report.foto_url` solo al bucket del proyecto; ids uuid; `autor` no legible; API solo GET con CORS por lista; CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy` en nginx; secretos solo en `.env` (no versionado); popups escapados (sin XSS) | `select count(*) filter (where rowsecurity), count(*) from pg_tables where schemaname='public'` -> 27 / 28; `curl -sI -H "Origin: https://ejemplo.com" http://localhost:8000/health` sin `Access-Control-Allow-Origin`; advisor de Supabase; verificación de seguridad del 19/20-10 (hallazgo del bucket corregido con la migración `20261020035127`) | HECHO |
| RNF07 | Información de fuentes oficiales verificadas y actualizada | Cada dato lleva fuente, hora y enlace (popups, tarjetas de Alertas, capas); `latido` por tarea; "sin actualizar desde" cuando una fuente se atrasa; lo que es criterio de SIMPAC se rotula "referencial" o "estimación"; `24 h` solo si la fuente lo dice | Verificación del 19/20-10 contra las fuentes en vivo: aviso 421 de SENAMHI, caudales de ANA (Mashcón 0,42 m³/s, Balsas 93,92, Nanay 122,42 m.s.n.m.), CO 18-2026 del ENFEN = pantalla = BD | HECHO |
| RNF08 | Código modular (frontend, backend, conectores) | Un archivo por conector (`backend/connectors/`), por tarea (`backend/ingesta/`), por capa (`frontend/src/map/layers/`) y por página (`frontend/src/pages/`); lógica pura con pruebas en `frontend/src/lib/*.test.js`; en la app, `dominio/` puro probado en JVM; 899 pruebas (720 + 157 + 22) | `README-tecnico.md` §2 y §3; `frontend/README.md` "Estructura"; `appmobile/README.md` "Estructura" | HECHO |
| RNF09 | Interfaz legible en pantallas pequeñas | Barra inferior de 5 pestañas (56 px, objetivos de 44 px o más), hoja plegable de 4 alturas, atribución de una línea con "más", popups que miden el espacio libre (`map/popups.js`), `inert` del mapa bajo una página | CP-39: 375x812 y 360x740 sin desplazamiento horizontal; tablet 768x1024 | HECHO |
| RNF10 | Android, Windows, macOS, iOS y los navegadores indicados | Web estándar (React, Leaflet) + APK; PWA instalable (`manifest.webmanifest`, `sw.js`) | Probado: Windows + Chrome, Android (emulador). **No probado**: macOS, iOS/Safari, Firefox, Edge; no hay app iOS (no estaba en las HU) | PARCIAL: falta probar en esos navegadores |
| RNF11 | Interfaz y contenido en español para Cajamarca | Todo el texto en español del Perú; ciudad por defecto Cajamarca; río Mashcón vigilado; 1126 puntos de "A dónde acudir" en Cajamarca; horas de Perú (`lib/tiempo.js`) | Recorrido del 19/20-10 | HECHO |

### 4.3. Condiciones de error del documento de requerimientos

| Condición | Dónde está |
|---|---|
| No hay datos recientes: último registro con fecha y aviso de desactualizado | `usePanorama` (`desactualizado`), línea de fuentes de la hoja en naranja ("ríos ANA sin actualizar desde ..."), barra lateral |
| Fuente no disponible: último dato en caché con aviso | `latido.fallas` -> "No se pudo revisar la lluvia de las estaciones de SENAMHI", "Último dato de ANA a las HH:MM; puede haber cambiado"; la API sirve la última copia buena del snapshot |
| Sin conexión: mensaje de error con reintento | `EstadoCarga.jsx` (`ErrorCarga` con "Reintentar"), hoja: "No se pudo consultar las alertas. Revisa tu conexión."; `sw.js` abre la cáscara sin red |
| Sin indicadores: estado vacío honesto | "Sin datos" (nunca verde sin medir); "No hay alertas ni avisos vigentes en Cajamarca"; "No hay reportes vigentes ahora" |
| GeoJSON inválido o capa no cargada: error con reintento | `MapView.jsx` reintenta la capa; nota de la capa dice que el servidor no respondió |
| Sin registros en el rango / rango inválido | `/historico`: "No hay lecturas en ... Hay datos desde el ..."; `/alertas` > Pasadas: `rangoPasadas` corrige fechas invertidas y no pasa de 30 días |
| Sesión expirada / permisos insuficientes | Supabase Auth renueva el token; sin sesión las páginas muestran "Entra para ..."; la BD rechaza con mensaje traducido (`mensajeErrorBD`) |
| Errores 5xx sin detalles técnicos | `ErrorBoundary.jsx` ("Esta página no se pudo mostrar en este navegador"); la API devuelve 503 con texto fijo si no hay snapshot |

---

## 5. Pendientes antes de medir y después

- [ ] Ejecutar los 6 casos manuales que faltan (CP-31, CP-32, CP-34, CP-35, CP-37 y CP-44) y los
      correos de CP-28 y CP-30 con cuentas de prueba, y recién entonces llenar C y D del IPR.
- [ ] Decidir cómo se manejan los correos de Supabase Auth en las sesiones (Redirect URLs o
      confirmación apagada) y crear las cuentas de prueba.
- [ ] Medir el PUR del equipo con el Administrador de tareas el día de la prueba (10 muestras en
      5 min con uso real); lo de esta noche son solo los contenedores.
- [ ] Repetir la escalera de NUS en otra máquina (o en Linux) para descartar que los 17 a 27 errores
      de nginx sean del loopback de Windows, y probar `uvicorn --workers 4` si se quiere subir el
      NUS de la API por encima de 50.
- [ ] Probar la web en Safari (iOS o macOS), Firefox 115 ESR y Edge para RNF05 y RNF10.
- [ ] Despliegue público (hoy todo es `localhost`): sin él no hay medición de disponibilidad (RNF02)
      ni sesiones de usabilidad con el celular del participante. Y mantener la BD activa: el plan
      gratuito de Supabase la pausó del 15 al 19 de octubre.
- [x] HU-20 (push con FCM) y la preferencia de notificación de HU-22: hechos el 20-10 y verificados el
      24-10 en el emulador (ICF 100 % estricto).
- [ ] Ejecutar CP-48 (mapa de la app Kotlin) en un teléfono real y, si se mide la app, CP-45 a CP-47
      también en ese teléfono (hasta ahora solo en el emulador Pixel_7a).
