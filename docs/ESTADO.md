# SIMPAC — Estado del proyecto

> Panel vivo de "dónde estamos". Actualizado: **2026-10-24** (fase "app Kotlin, push y zonas de los
> ríos del país" construida el 20-10 e integrada y verificada el 24-10; antes, verificación y
> despliegue del software terminado la noche del 19 al 20 de octubre).
> Repo: `github.com/Federjj/SIMPAC` (monorepo, rama `main`).

## Resumen en una línea
**Software terminado y desplegado en local**: web completa con react-router (Mapa, Alertas,
Comunidad, Chat, Cuenta, Histórico) e **inicio de sesión** con Supabase Auth; inicio **"Tu zona
ahora"** con semáforo, titular corto de la BD, distancia al río más cercano del país y **a dónde
acudir** (12 915 puntos oficiales); **100 ríos del país resaltados con el trazo de ANA**, 20 de
ellos con **zonas que podrían inundarse estimadas con el relieve** y franja de atención, más el
Mashcón vigilado; **titular automático por departamento** (tarea `titular`, por reglas; el LLM queda
apagado hasta poner la clave); **app Android nativa en Kotlin + Jetpack Compose** (`appmobile/android/`,
APK debug de 15,1 MiB probado en emulador) con **notificaciones push por FCM** que ya llegan de
extremo a extremo (tarea `push` del worker, HU-20); backend + Supabase con datos reales (avisos de
SENAMHI con ícono, pronóstico por localidad, nowcasting, lluvia de la última hora en todo el país,
ICEN, mapas FEN de 5 eventos por trimestre (13 filas), ENFEN); **stack dockerizado y corriendo** con 10
tareas en el worker; 726 pruebas del backend, 162 del frontend y 22 JVM de la app; 36 migraciones. Pendiente: probar el WebView del
Mapa de la app en un teléfono real, firma y Play Console, clave del LLM y validar con usuarios.

---

## Hecho

**Datos / backend (prototipo, corre sin instalar nada)**
- [x] Conectores en vivo: **SENAMHI** (estaciones + lluvia horaria), **ANA** (caudales+umbrales),
      **IGP** (ICEN), **NOAA** (RONI), **ENFEN** (comunicado e Informe Técnico, PDF). `backend/connectors/`
- [x] Prototipo sin dependencias: ingesta → SQLite → API JSON, hoy en `backend/prototipo/` (congelado).
- [x] Motor de umbrales (`alerts.py`): caudal con los umbrales de ANA; lluvia con la referencia de
      SENAMHI de cada estación.
- [x] **Tiempo real verificado** con evidencia: SENAMHI y ANA se actualizan a la hora en curso.

**Base de datos (Supabase)**
- [x] Proyecto **DATASYMPAC** (ref `clrnommkjyksnyrtnisf`, región São Paulo).
- [x] **Esquema aplicado**: 16 tablas + vistas `caudal_actual`, `aviso_vigente`,
      `lluvia_senamhi_actual` y `alerta_actual` + **PostGIS** + **RLS**. Historia en
      `supabase/migrations/` (**32 migraciones**, versionadas en el repo y las 32 registradas en
      `supabase_migrations.schema_migrations` de la BD; las 7 últimas son del 14 y del 20 oct:
      `comunidad_fotos_y_chat_realtime`, `punto_acudir`, `rio_cauce`, `titular_zona`,
      `report_foto_solo_bucket`, `aviso_hidrologico_sentido_indeterminado`,
      `titular_zona_titular_corto`); foto final en `supabase/schema.sql`: **27 tablas y 13 vistas**
      propias (la BD lista 28 y 15 contando `spatial_ref_sys` y las vistas de PostGIS), más el
      bucket `reportes` y la publicación realtime de `message` (sección D del schema).
      **Al 24-10-2026: 35 migraciones** (las 3 nuevas del 20-10, aplicadas y registradas:
      `push_estado`, `rio_cauce_mapa_franja`, `rio_cauce_zona`), **29 tablas y 14 vistas** propias
      (la BD lista 30 y 16 con las de PostGIS); secciones G, H e I del schema. **Al 25-10-2026: 36**
      (`mapa_trimestre`: `mapa.trimestre`, `mapa.meses` e índice único `(uuid, coalesce(trimestre, ''))`).
- [x] **Datos (22 sep, los llena la ingesta horaria)**: 982 estaciones SENAMHI en 24 departamentos
      (con `lat`/`lon`) · lluvia horaria de las 14 automáticas de Cajamarca · ~120 ríos con caudal y
      umbrales en 23 departamentos · ICEN / RONI / estado ENFEN · capa de **anomalías de
      precipitación** (muestra Cajamarca) y 5 mapas FEN en la tabla `mapa`.
- [x] **Lectura del frontend verificada**: la publishable key lee estaciones/caudales/índices/mapa
      vía la API REST de Supabase (RLS de lectura pública funcionando).
- [x] **MCP de Supabase** conectado en modo escritura (Claude puede leer/editar la BD).
- [x] **Código de ingesta a Supabase** listo (`backend/ingesta/`), con `SUPABASE_DB_URL` real.
- [x] **Mapas históricos de eventos El Niño** (aporte de Kevin, consolidado el 22 sep): 5 eventos
      (82-83, 97-98, Costero 2017, Costero 2023, 2023-2024) en la tabla `mapa` con `variable='FEN'`,
      desde el catálogo IDESEP de SENAMHI. Conector `connectors/idesep.py` + cargador
      `backend/mapas/cargar_fen.py`. **Desde el 25-10-2026 (HU-15): una fila por evento y trimestre**,
      13 filas (DEF, EFM y FMA en 82-83, 97-98 y 2017; EFM y FMA en Costero 2023; DEF y EFM en
      2023-2024), con `trimestre` y `meses` ("diciembre de 1997 a febrero de 1998") y upsert idempotente
      por `(uuid, trimestre)` (índice único `mapa_uuid_trimestre_key`). Detalle en `README-tecnico.md` §5.7.

**Frontend (React + Vite + Tailwind + shadcn/ui + Leaflet)** — `frontend/`
- [x] Página **Mapa** con **solo datos reales**: estaciones y ríos/caudales de Supabase; el círculo
      de zona aparece únicamente alrededor de ríos en **alerta/emergencia** (dato de ANA). Íconos
      lucide (no emojis).
- [x] **Quitado todo lo demo** del mapa: zonas sombreadas ficticias, capa "usuarios cercanos"
      (descartada) e incidentes de ejemplo. La capa de incidentes queda lista pero vacía hasta
      conectar reportes reales.
- [x] **Rediseño UI con Tailwind + shadcn/ui** (tema claro neutral estilo template: Geist, primario
      casi negro): sidebar, panel de estado, panel de capas con switches, selector de ciudad, tooltips.
      Mapa con tiles **Stadia Alidade Smooth** (limpio + detallado) y `ResizeObserver`. Responsive
      (mobile-first) verificado en desktop y móvil.
- [x] **Geolocalización** (con permiso) + **selector de ciudades del Perú** (Cajamarca por defecto).
- [x] Componentes: `Sidebar`, `MapView`, `LayersPanel`, `StatusPanel`, `CitySelector` + `components/ui/`
      (shadcn). Correr: `npm --prefix frontend install && npm --prefix frontend run dev` → localhost:5173.
- [x] **Desde el 14 oct la web está completa**: `App.jsx` es el marco con react-router, el mapa vive
      en `pages/Mapa.jsx` y hay páginas Alertas, Comunidad (con crear reporte y detalle), Chat,
      Cuenta (Supabase Auth) e Histórico, barra inferior de 5 pestañas en celular y la hoja "Tu zona
      ahora". Detalle en "Software terminado (14 oct)" más abajo.

**Infraestructura (Docker)** — `docker-compose.yml`
- [x] Stack de 4 servicios: **frontend** (nginx), **backend** (FastAPI **async**), **worker**
      (Celery + beat), **redis** (caché + cola). `docker compose config` validado.
- [x] **Stack corriendo**: redis + worker (con beat) + API arriba; el **beat** dispara `refresh_cache`
      cada 5 min y **refresca el snapshot en Redis sin errores** (138 caudales, 2 en alerta).
- [x] **Bug del worker corregido**: el cliente `redis.asyncio` era global y reventaba con
      `Event loop is closed` en cada corrida de Celery. Ahora el worker crea/cierra un cliente Redis
      **por corrida** y la API usa uno persistente por `lifespan` (`backend/snapshot.py`, `backend/app.py`).
- [x] API async con caché en Redis (snapshot) para aguantar varios usuarios.
- [x] Ingesta **nacional + concurrente** (ThreadPool) — la corre el worker cada hora (`backend/ingesta/`).
- [x] **`SUPABASE_DB_URL` real en `.env`, vía pooler (IPv4)**: la conexión directa es solo IPv6 y
      desde Docker fallaba. Verificado: el worker conecta y el cargador FEN escribe.
- [x] **Imagen del worker actualizada** (22 sep): seguía con código del 16 sep y volvía a salir
      `Event loop is closed`. Backend y worker tienen imágenes separadas; hay que reconstruir ambos.
- [x] **Ingesta real verificada (22 sep)**: corrió en 9 s y dejó 827 estaciones, 14 estaciones de
      Cajamarca con lluvia horaria al día (hora en curso), 121 caudales del día e índices frescos.
      Conectores con TLS siempre verificado; BD por pooler con `sslmode=require`.
- [x] **Endurecido**: Redis publicado solo en `127.0.0.1`; geopandas solo en la imagen del worker
      (`requirements-mapas.txt`), la imagen de la API bajó a ~310 MB.
- [x] **Worker con 9 tareas** (20 oct): `ingesta` (1 h), `refresh_cache` (5 min), `enfen` (6 h),
      `avisos` (1 h), `lluvia_nacional` (30 min), `pronostico` (1 h), `nowcast` (10 min), `rios`
      (1 h) y `titular` (30 min; al arrancar se encola 5 min después de las demás). Arranque del
      20-10 sin ningún Traceback: nowcast 2,7 s, pronostico 2,9 s (277 localidades, 831 filas),
      rios 4,3 s (1695 filas, 9 avisos hidrológicos vigentes), lluvia_nacional 4,9 s (154
      estaciones, 6 lloviendo), enfen 5,7 s (CO 18-2026), avisos 7,1 s (38 alertas), ingesta 11,2 s
      (973 estaciones, 720 lluvia, 127 caudales), titular 25 departamentos por reglas.
- [x] **Worker con 10 tareas** (24 oct): se suma `push` (cada 5 min, soft 60 / hard 90 s; al arrancar
      se encola 7 min después, cuando `titular` ya escribió). Reconstrucción del 24-10: beat registra
      las 10 (avisos, enfen, ingesta, lluvia_nacional, nowcast, pronostico, push, refresh_cache, rios,
      titular), sin tracebacks; la imagen del worker suma `google-auth` (solo para firmar el JWT).
- [x] **nginx del frontend** (14 oct): gzip + `gzip_static` con los `.gz` que deja el build, caché
      inmutable de 1 año para `/assets/`, `no-cache` para `index.html`, manifest y `sw.js`,
      cabeceras CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` y `access_log
      off`. Comprobado el 20-10 en `localhost:8080`: `index-*.js` 445 544 B -> 154 838 B servidos
      (34,8 %), `/assets/noexiste.js` -> 404, `/alertas` con recarga directa -> la página.
- [x] **CORS en la API** (14 oct): responde solo a los orígenes de `SIMPAC_CORS_ORIGENES` (vacío =
      `http://localhost:8080`, `http://localhost:5173`, `https://localhost` y
      `capacitor://localhost` para la app; `*` se ignora) y solo GET. `/health` -> 200 con
      `vary: Origin`; `/api/snapshot` -> 46 125 bytes en 0,028 s.

**Software terminado (14 oct)** — implementado el 14 oct por 8 frentes en paralelo y sometido a una
verificación adversarial los días 19 y 20 oct (4 verificadores en navegador: escritorio, celular,
veracidad de textos y rendimiento, más seguridad y backend/BD): **51 hallazgos** (1 bloqueante, 18
graves, 32 menores) y 13 confirmados antes; dos rondas de arreglos y la reverificación final sin
graves ni bloqueantes. Cierre del 20-10 (00:49, hora de Lima): **657 pruebas** del backend sin red
(`python -m unittest discover -s backend/tests -t .`, 12 s) y **148** del frontend (`npm test`,
0,9 s), `npm run build` OK (9,4 s, 1801 módulos), **7 migraciones** aplicadas y registradas,
imágenes de frontend, backend y worker reconstruidas, web recorrida en `localhost:8080` en
escritorio y celular emulado (375x812), APK de Android compilado y probado en emulador. La BD de
Supabase estuvo **pausada del 15 al 19 oct** (proyecto gratuito) y se reanudó el 19-10 a las 22:10;
los datos de abajo son de después de reanudarla.
- [x] **Rendimiento** (plan de la auditoría: puntos 1-7, 9 y 11; 8 y 10 descartados con datos).
      Medido en Vite, misma pestaña, 800x600, antes -> después:
  - Entrega: nginx no comprimía y ahora sirve gzip precomprimido (plugin `precomprimir` de
    `vite.config.js`, zlib, sin dependencias): JS principal 323 876 B -> 112 280 B, CSS 68 553 ->
    17 005. Chunks `react`/`leaflet`/`supabase` aparte (45/43/59 KB gzip, cacheados un año): un
    cambio propio invalida solo `index-*.js`. Build del 20-10: index 444,38 kB (154,97 gzip),
    supabase 227,45 (59,01), leaflet 149,58 (43,36), react 141,39 (45,45), CSS 80,19 (19,72) y las
    páginas perezosas (Alertas 16,25 kB, Histórico 15,06, Cuenta 11,79, ReporteNuevo 7,09, Chat
    6,00, Comunidad 2,81).
  - Consultas: la cascada `conRios` (la ola 2 arrancaba a los 836 ms, la 1 a los 618) desapareció:
    las 14 arrancan juntas a los 404-408 ms (celular 422-427). En 8080, primera carga en frío: 19
    peticiones REST a 17 vistas/tablas, 0 duplicadas; con assets en caché el titular se ve a los
    468 ms (DOMContentLoaded 106 ms).
  - Mapa: SVG en línea 382 -> 0, filtros 192 -> 0, paths de marcadores 582 -> 0, nodos del DOM
    4691 -> 2900 (glifos como `data:` URI); `getPointAtLength` por arrastre 2050 -> 456 y por zoom
    13->14 3463 -> 648-742 (`rotuloBusqueda.js`, memoria de puntos y debounce de 120 ms); pan de
    1 px 17,4 -> 10,5 ms; zoom 13->14 66 -> 47 ms; render río 85 -> 27 ms, pronóstico 64 -> 29,
    zona 19 -> 11. Un refresco con los mismos datos no redibuja (huella por capa).
  - `index.html` con `preconnect` a Supabase (URL inyectada en el build), Stadia y Google Fonts y
    fuentes por `<link>`. PWA: `manifest.webmanifest`, íconos y `sw.js` (solo la cáscara propia,
    nunca datos de Supabase ni tiles), registrado desde `main.jsx` solo en producción.
  - Pendiente: fuentes autoalojadas (punto 5b). El Dockerfile del frontend ya es `node:22-alpine`
    desde el 20-10 (imagen reconstruida el 24-10, sin el aviso `EBADENGINE`).
- [x] **Páginas y cuentas** (`react-router-dom` 6): `App.jsx` es el marco (`SesionProvider`,
      `ContextoApp`, `Sidebar`, `BarraInferior` de 5 pestañas en celular, `Routes` con `lazy`) y el
      mapa está en `pages/Mapa.jsx`; `MapView` nunca se desmonta: las páginas van a pantalla
      completa sobre el mapa en celular/tablet y en una columna de 28-30 rem desde `lg`. Rutas `/`,
      `/alertas`, `/comunidad`, `/comunidad/nuevo`, `/comunidad/:id`, `/chat`, `/cuenta` (`/entrar`,
      `/registro`), `/historico` y "Esta página no existe"; todas cargan con recarga directa
      (nginx cae en `index.html`), el foco pasa al `h1` y cambia `document.title`.
  - **Alertas**: lista priorizada de `alerta_actual` agrupada por aviso, filtros nivel / tipo / mi
    zona o país, vacío con hora de la última revisión, avisos de SENAMHI vigentes con sus días
    (nivel = el máximo de todas sus áreas y días: el 419 rojo y el 421/426 naranja salían amarillos),
    ríos vigilados con "Ver en el mapa" y pestaña Pasadas sobre la tabla `alerta` (rango de hasta
    30 días y zona).
  - **Cuenta** (Supabase Auth): entrar, crear cuenta con nombre, olvidé mi contraseña, pantalla
    "revisa tu correo", contraseña nueva al volver del enlace; con sesión: nombre editable, correo,
    reputación, "Mi zona" en `perfil.zona` (punto de la ciudad) y en `localStorage`, "Mis reportes"
    (rpc `mis_reportes`) y cerrar sesión. Formularios con `label`, `autocomplete`, errores con
    `aria-describedby`. Al 20-10 no hay ningún usuario en `auth.users` (nadie se ha registrado).
  - **Histórico** (`/historico?tipo=rio|lluvia&id=...&rango=24h|7d|30d`): `lectura_caudal` con los
    umbrales de `caudal_actual` o `lectura_lluvia`, gráfico SVG propio, tabla y CSV; se llega desde
    el popup de la estación ("Ver histórico").
  - Accesibilidad: bajo una página a pantalla completa el `<main>` del mapa queda `inert` y
    `aria-hidden` (sus controles ya no están en el orden de tabulación); barra inferior de 56 px con
    objetivos de 44 px y contador de alertas; sin desborde horizontal en 375 ni 360 px.
- [x] **Comunidad y chat** (migración `comunidad_fotos_y_chat_realtime`): `/comunidad` lista los
      reportes vigentes por confianza y cercanía, con votos (upsert), detalle y "Ver en el mapa";
      `/comunidad/nuevo` solo con sesión y GPS real (tipos estilo Waze con ícono lucide, subtipo de
      atasco, descripción de hasta 500 caracteres, foto opcional reducida a 1280 px y subida al
      bucket público `reportes` en `<uid>/<archivo>.jpg`, 3 MB); `/chat` por zona (= departamento)
      con realtime (tabla `message` en la publicación `supabase_realtime`) más sondeo cada 10 s;
      normas y aviso legal fijos en `lib/comunidad.js`. Arreglo del 20-10 (hallazgo de seguridad):
      `report.foto_url` aceptaba cualquier `https://`; ahora el CHECK y el trigger
      `report_foto_validar` exigen la URL pública del bucket `reportes` del proyecto, con carpeta
      `<uuid>` y extensión jpg/jpeg/png/webp (migración `report_foto_solo_bucket`, 12 de 12 casos
      en una transacción revertida). Al 20-10: 0 reportes y 0 mensajes en la BD.
- [x] **Ríos a nivel nacional**: conector `backend/connectors/ana_rios.py` (ANA - GeoSNIRH, dos
      capas ArcGIS REST: red hidrográfica R.J. 056-2018-ANA y Carta Nacional del IGN; `LIKE` con
      comodín de tildes, filtro por punto y radio, paginación, tope de 15 MB) y cargador
      `backend/mapas/cargar_cauces.py` (prueba en seco por defecto; `--aplicar`, `--desde-copia`,
      `--rio`, `--forzar`, `--recorte`, `--podar`). Emparejamiento por nombre normalizado + tramos a
      2000 m de una estación + río completo por conectividad; 25 alias en
      `backend/data/rios/cauces_alias.json`. Tabla `rio_cauce` (`geom` ~6 m y `geom_lejos` ~50 m)
      y vistas `rio_cauce_mapa` y `rio_cauce_senal` (migración `rio_cauce`). **Carga del 14-10,
      verificada en la BD el 20-10**: 104 ríos buscados, **100 cargados** (79 RJ056, 21 IGN; 352
      tramos; 18 636 km), 4 sin trazo (Titicaca, Canopampa, Chunchuca, Sumbay), 26 con nota; tabla de
      5,6 MB; copias en `backend/data/cauces/` (105 GeoJSON, 2,98 MB, versionados: los 100
      cargados, los 4 pendientes y el Mantaro). El Mashcón no
      se duplica (`rio_vigilado` manda) y un río sin trazo no se inventa.
  - **Mapa**: `lib/cauces.js` (puro, con pruebas) empareja los trazos con `caudal_actual`; estado =
    la peor estación de ANA en crecida o el aviso hidrológico vigente si es más alto (la misma regla
    del Mashcón); `cauce_lejos` para todo el país hasta zoom 12 y `cauce` fino por río desde zoom
    13; nombres sobre la línea desde zoom 10 (máximo 8, primero los de alerta); en alerta o
    emergencia la capa "Zonas que un río podría afectar" dibuja el aura a lo largo del trazo en vez
    del círculo de 2,5 km. 92 ríos dibujados hoy (los 8 que solo tienen aviso de SENAMHI se
    resaltan solo con aviso vigente).
  - Arreglos del 20-10: los avisos "SITUACIÓN ACTUAL DEL NIVEL..." de SENAMHI (vaciante en la
    selva) se guardaban como crecida; ahora `sentido` sale del título y de la leyenda del detalle
    (`crecida`, `descenso` o `indeterminado`; CHECK y trigger, migración
    `aviso_hidrologico_sentido_indeterminado`) y la tarea `rios` pide el detalle de todos los
    vigentes del país: hoy 9 avisos vigentes, 9 `descenso`, 0 `crecida`, y el popup del Itaya ya no
    afirma una crecida. Un aviso hidrológico tiñe solo la estación que nombra su título
    (`avisoEsDeEstacion`), no todas las del río (20 discos de ANA salían con "Aviso").
- [x] **A dónde acudir**: tabla `punto_acudir` (migración `punto_acudir`; clave `<fuente>:<id>`,
      tipo, `atiende_24h` solo si la fuente lo dice, dirección, teléfono, lat/lon, fuente, licencia,
      atribución, `detalle`; RLS de lectura pública) y cargador `backend/mapas/cargar_acudir.py`
      (en seco, `--aplicar`, `--podar`, `--descargar`, `--pais`) con los datos en
      `backend/data/acudir/`. **Carga del 14-10, verificada en la BD el 20-10: 12 915 puntos**
      (salud 11 376, comisarías 1323, bomberos 213, Defensa Civil 3); Cajamarca 1126 (salud 1001,
      42 de 24 h; comisarías 118; bomberos 4; Defensa Civil 3). Fuentes: RENIPRESS de SUSALUD del
      30-09-2026 (ODC-By), comisarías del padrón MININTER de nov. 2019 servido por CENEPRED,
      bomberos del CGBVP con ubicación de CENEPRED, fichas de gob.pe para Defensa Civil; números de
      emergencia en `backend/data/acudir/numeros.json` y `frontend/src/data/emergencias.js`.
  - **Frontend**: capa `acudir` (grupo "A dónde acudir", apagada por defecto; pide `punto_acudir`
    por caja a la vista, desde zoom 11) y tarjeta `AcudirCercanos` con "105 Policía · 116 Bomberos ·
    106 SAMU", los 3 puntos más cercanos (salud, comisaría, bomberos) con distancia en línea recta,
    teléfono `tel:`, "Cómo llegar" y "Ver en el mapa"; `lib/acudir.js`: caja de 30 km y regla
    "hospital de 24 h si está a menos de 15 km; si no, el establecimiento más cercano". Verificado
    contra la BD: Hospital II Cajamarca a 450 m (453 en PostGIS, 24 h según la fuente), Comisaría
    Central a 170 m (168; sin teléfono en la fuente, padrón 2019), Bomberos N° 59 a 450 m (452).
  - **Sin albergues ni zonas seguras**: al 14-10 ninguna fuente oficial abierta los publica
    georreferenciados (se revisaron el ArcGIS de CENEPRED, SIGRID, el visor y los servidores de
    INDECI, datosabiertos.gob.pe y los planes de contingencia del GORE Cajamarca). Los tipos quedan
    previstos en la tabla; la web muestra la recomendación general de INDECI con su enlace.
- [x] **Inicio con impacto visual ("Tu zona ahora")**: `StatusPanel` es una hoja inferior de 4
      alturas (plegado, vistazo, media, completa; asa arrastrable y botones accesibles; tarjeta de
      420 px en escritorio) con franja del color del nivel. `TuZona`: semáforo con ícono (nunca
      solo color), titular corto (`titularCorto`: río vigilado en alerta > alerta oficial > aviso
      amarillo > lluvia medida > señales en la cuenca > calma > sin datos; nunca verde sin datos),
      chips "A 2 km del río Mashcón" (2026 m desde el centro de Cajamarca al cauce, en PostGIS) y
      "Fuera de la zona que podría inundarse", línea de fuente y hora, botón por nivel; en alerta o
      emergencia una sola instrucción, botones `tel:105` y `tel:116` y el pie SISMATE/INDECI.
      En la altura media: `MedidorCaudal` (arco con los umbrales de ANA), `BarrasLluvia` (24 h con
      la referencia de SENAMHI) y "A dónde acudir". `OnboardingGps` explica el permiso una sola vez
      (`simpac.gps`); la app ya no pide la ubicación al arrancar. Modo emergencia: abre la hoja,
      prende río y zona, encuadra el cauce; el chip de arriba y la barra lateral heredan el nivel;
      `html[data-nivel]`. Hoy en 8080: "ALERTA en Cajamarca: aviso naranja de SENAMHI por lluvias."
  - Arreglos del 19/20-10: un río en **nivel bajo** y la lluvia medida cuentan como máximo "aviso"
    (`lib/nivel.js` y `titular.py`, misma regla): Loreto salía en "ALERTA" con teléfonos por 5 ríos
    en vaciante y ahora dice "Ríos muy bajos"; la causa de una alerta se decide por el tipo de fila
    (Piura ya no inventa "un río pasó su nivel"); en celular la hoja arranca **plegada** (295-299
    px, 36-37 % de la pantalla) y el cauce queda visible; atribución de Leaflet propia de una línea
    con "más"; los popups miden lo que de verdad tapa el mapa; el botón "Reportar" desaparece
    mientras el panel de capas está abierto; las 3 pruebas que dependían de la fecha del 14-10
    construyen su fecha con el día de Perú.
- [x] **Titular automático (HU-16)**: tarea `titular` (`backend/ingesta/titular.py`, cada 30 min)
      calcula para los 24 departamentos y el Callao los insumos con la misma regla que
      `lib/nivel.js` (nivel vigente, alertas oficiales, avisos por color, ríos sobre su nivel y muy
      bajos, lluvia de la última hora, señales del río vigilado, ENFEN, hora de cada fuente) y
      escribe `titular_zona` (`titular`, `titular_corto` de hasta 110 caracteres siempre por reglas,
      `detalle`, `insumos`, huella sha256, `origen`). Con `SIMPAC_LLM_KEY` pide una redacción por
      departamento a la API de Anthropic (modelo por defecto `claude-haiku-4-5-20251001`,
      `temperature` 0, 200 tokens) que se valida antes de guardarse (una línea, 240 caracteres, sin
      URL, cada cifra en los insumos, sin afirmar emergencia ni normalidad que no esté en los
      datos); si falla o no hay clave, reglas. Migraciones `titular_zona` y
      `titular_zona_titular_corto`. **Al 20-10**: 25 filas, todas `origen = 'reglas'`,
      `titular_corto` de 43 a 100 caracteres (p. ej. "Loreto: aviso amarillo de SENAMHI por lluvias
      y 5 ríos muy bajos según ANA."), llm 0, fallas 0, aviso "sin clave de API (SIMPAC_LLM_KEY):
      titulares por reglas". La web lee `titular_zona` y usa el titular de la BD solo si su nivel
      coincide con el que calcula ella.
- [x] **App Android con Capacitor** (`frontend/android/`, documentación en `appmobile/README.md`):
      la misma web en un WebView con GPS por `@capacitor/geolocation` (import dinámico en
      `useGeolocation.js`). Capacitor 8.5.3, `appId` `pe.simpac.app`, origen `https://localhost`,
      `minSdk` 24, `targetSdk`/`compileSdk` 36, AGP 8.13, Gradle 8.14.3, JDK 21; `versionCode` 1.
      **Compilado el 20-10**: `npm run build` (9,4 s) + `npx cap sync android` (1,7 s) + `gradlew
      assembleDebug` (9 s, 214 tareas) -> `app-debug.apk` de **5 304 253 bytes (5,06 MiB)**.
      Arreglo: los `.gz` del build se excluyen con `!*.gz` en `ignoreAssetsPattern` (AAPT los tomaba
      como recursos duplicados). Probado en el emulador Pixel_7a sin ventana (`-memory 3072`): carga
      el mapa con sus tiles, el chip "Aviso naranja en Cajamarca", el río Mashcón con sus rombos, el
      onboarding del GPS y la barra inferior; con los 2 GB por defecto del AVD Android mata la app.
      Scripts `android:sync`, `android:apk`, `android:aab`, `android:apk:release` en `package.json`;
      la firma lee `key.properties` o variables de entorno (ninguno en el repo). **Desde el 20-10 la
      reemplaza la app nativa en Kotlin** (`appmobile/android/`, mismo `applicationId`; ver el bloque
      "App Android nativa, push y zonas de los ríos del país"); el proyecto de Capacitor se retiró del
      repo el 24-10 (`frontend/android/`, `capacitor.config.json`, scripts `android:*`, `@capacitor/*`).
- [x] **ENFEN, CO 17-2026 corregido**: el Comunicado Oficial 17-2026 (28-09-2026) cambió el formato
      (sin rótulo "Estado del sistema de alerta" ni "RESUMEN EJECUTIVO", el estado en una línea
      suelta bajo la fecha, un título en mayúsculas y la fecha con el año errado "28 septiembre
      2027") y el conector no lo leía. `backend/connectors/enfen.py` ahora reconoce el estado
      suelto (sin confundirlo con una mención dentro de una frase), salta el título, corrige una
      fecha futura con el año del encabezado (con aviso en el log) y corta la prosa donde empieza
      la leyenda de una figura; muestra real en `backend/tests/muestras/comunicado_enfen_17_2026.txt`
      con pruebas de punta a punta. En la BD **no hay fila del CO 17**: la tarea solo lee el último
      comunicado publicado y cuando corrió ya estaba el **CO 18-2026** (16-10, "Alerta de El Niño
      Costero", próximo el 30-10), que es lo que muestra la web; el 16-2026 sigue como anterior.
- **Pendiente de este bloque** (ver "Siguiente"): firma y Play Console, clave del LLM, Redirect
  URLs y SMTP de Supabase Auth, validar con usuarios, otros ríos vigilados con desbordes pasados y
  radios de "A dónde acudir". El push por FCM, `titular_corto` en la tarjeta, `node:22-alpine` y las
  zonas de otros ríos quedaron hechos el 20/24-10 (bloque siguiente).

**App Android nativa, push y zonas de los ríos del país (20 oct; integrado y verificado el 24 oct)**
— cuatro frentes en paralelo el 20-10 (app Kotlin, avisador push, zonas de relieve, frontend de ríos
del país) e integración el 24-10: **720 pruebas** del backend sin red (`python -m unittest discover
-s backend/tests -t .`, 10 omitidas por dependencias opcionales), **157** del frontend (`npm test`),
`npm run build` OK (11,6 s, 1801 módulos), **22 pruebas JVM** de la app (`gradlew testDebugUnitTest`)
más 4 de Compose UI (`connectedDebugAndroidTest`, en emulador), **3 migraciones** aplicadas
(`20261020164538_push_estado`, `20261020164715_rio_cauce_mapa_franja`, `20261020165455_rio_cauce_zona`;
35 en total), imágenes de frontend (`node:22-alpine`), backend y worker reconstruidas el 24-10, web
recorrida en `localhost:8080` (escritorio y 375x812) y app probada en el emulador Pixel_7a.
- [x] **App Android nativa en Kotlin + Jetpack Compose** (`appmobile/android/`, `applicationId`
      `pe.simpac.app`, `versionCode 2`, `versionName 2.0`; reemplaza a la de Capacitor al instalarse).
      AGP 9.0.1, Kotlin 2.3.20, Compose BOM 2026.03.01, Gradle 9.1.0, minSdk 26, target/compileSdk 36,
      Navigation Compose 2.9.5, DataStore 1.1.7, security-crypto 1.1.0, OkHttp 4.12.0,
      kotlinx-serialization 1.9.0, play-services-location 21.3.0, Firebase BOM 34.0.0 +
      firebase-messaging; 36 archivos Kotlin. Cinco pestañas: **Inicio** (semáforo del departamento
      elegido o por GPS, `titular_corto` y detalle de `titular_zona` con "Generado el", chips de alertas
      oficiales y del río con señales, ENFEN del `/api/snapshot`, pronóstico de 3 días, botones 105 y
      116, fuentes con hora; estados cargando / error / desactualizado / sin conexión con caché en
      disco), **Alertas** (ordenadas, la lluvia medida aparte y marcada como no oficial, filtro mi zona /
      país), **Mapa** (la web en un WebView; geolocalización solo para el origen configurado),
      **Acudir** (105/116/115/106 y los 3 puntos más cercanos de `punto_acudir`) y **Cuenta** (ajustes,
      interruptor de notificaciones por zona, Acerca de). La URL y la publishable key de Supabase se
      inyectan en `BuildConfig` desde `frontend/.env` o `.env.example` (ningún archivo del proyecto
      lleva la clave); release con R8 y `network-security-config` (https; http solo a 10.0.2.2 y
      localhost). **Compilado el 24-10**: `gradlew testDebugUnitTest assembleDebug` BUILD SUCCESSFUL,
      APK debug `appmobile/android/app/build/outputs/apk/debug/app-debug.apk` de **15 846 448 bytes
      (15,1 MiB)**. Probada en el emulador Pixel_7a sin ventana (`-memory 3072`): Inicio con el disco
      "AVISO", "Cajamarca: 3 avisos de SENAMHI por lluvias (el más alto, amarillo).", chips, ENFEN
      (CO 18-2026) y pronóstico; Alertas con los avisos 432 / 435 y la lluvia de 24 h; Acudir con el
      Hospital II Cajamarca a 453 m, la Comisaría Central a 169 m y los bomberos; Cuenta con el
      interruptor que pide `POST_NOTIFICATIONS` y se suscribe a `pais` y `zona_cajamarca`.
      **Límite conocido:** el **Mapa (WebView) carga la web pero la captura sale en blanco** en ese
      emulador sin GPU (el árbol de accesibilidad muestra la web entera; una página simple sí se pinta
      y Chrome del emulador sí pinta la web de SIMPAC): falta probarlo en un teléfono real. Detalle en
      `appmobile/README.md` y `README-tecnico.md` §8.4.
- [x] **Notificaciones push (HU-20) de extremo a extremo**: tarea `push` del worker
      (`backend/ingesta/push.py`, cada 5 min; 44 pruebas en `test_push.py`) lee `titular_zona`, compara
      con la memoria `push_estado` (migración `push_estado`, RLS sin lectura pública) y manda por FCM
      (API HTTP v1, token OAuth2 firmado con `google-auth`) "SIMPAC: ALERTA|EMERGENCIA en <Depto>" con
      el `titular_corto` de cuerpo solo cuando el nivel sube a alerta o emergencia, y "SIMPAC: vuelve
      la calma en <Depto>" cuando baja a normal o aviso; nunca por aviso amarillo ni lluvia medida,
      nunca dos veces lo mismo, y `sin_dato` (fuente caída) no toca nada. Temas `pais` y `zona_<slug>`
      con una condición para que quien está en los dos lo reciba una vez. La cuenta de servicio de
      Firebase (proyecto `appsimpac`) se monta en el worker desde `FIREBASE_CREDENCIALES_ARCHIVO` del
      `.env` (`/run/secrets/firebase.json`, solo lectura); sin credenciales la tarea solo deja su
      latido. **Verificado el 24-10**: la primera corrida con credenciales (21:58 UTC) envió una vez las
      6 alertas vigentes (Tumbes emergencia; Piura, Huancavelica, Lima, Ayacucho y Arequipa alerta) a
      `pais` y a sus `zona_*`; las corridas siguientes `enviados 0`; `python -m backend.ingesta.push
      --prueba --zona Cajamarca` llegó al emulador suscrito a `zona_cajamarca` (canal `alertas`) y al
      tocarla abrió la pestaña Alertas. Al 24-10 22:23 UTC: `push_estado` con 23 filas, latido
      `credenciales: true`, `fallas []`.
- [x] **Zonas que podrían inundarse junto a los ríos del país** (`backend/mapas/zonas_relieve.py`,
      pipeline reproducible sin GDAL: HAND sobre Copernicus DEM GLO-30 con el trazo de ANA grabado,
      tramo de hasta 60 km alrededor de la estación o la ciudad, corredor de 2,5 km, malla de 30 m,
      umbrales ~2 m y ~3 m, control de calidad; 19 pruebas en `test_zonas_relieve.py`). **20 ríos
      calculados** (Rímac, Chillón, Piura, Chira, Tumbes, Cajamarca, Jequetepeque, Santa, Ica, Chili,
      Mayo, Utcubamba, Huallaga, Cumbaza, Chancay-Lambayeque, La Leche, Zaña, Chicama, Tambo,
      Vilcanota): los 20 pasaron el control (zona de 2 m entre el 1,7 % y el 8,4 % del corredor), en
      total 213 km² bajo ~2 m y 286 km² bajo ~3 m; **6 descartados con nota** por selva baja muy
      plana (Amazonas, Ucayali, Napo, Nanay, Itaya y Marañón; el tramo alto del Marañón queda pendiente
      como río aparte). Archivos en `backend/data/cauces_zonas/` (20 GeoJSON + `_indice.json`, 3,1 MB,
      versionados) y **cargados el 24-10** con `cargar_cauces_zonas --aplicar`: 40 filas en
      `rio_cauce_zona` (4,9 MB), vista `rio_cauce_zona_mapa` leída por PostgREST. Cada zona lleva
      método, fuente, licencia, atribución (Copernicus y ANA), fecha y la nota de estimación: **no es un
      mapa oficial y nunca se muestran metros**.
- [x] **Frontend de ríos del país con zonas y franja**: la capa "Zonas que un río podría afectar"
      (`zonasRio.js`) dibuja las zonas de `rio_cauce_zona_mapa` de los ríos cuya caja toca la vista desde
      zoom 12 (una consulta por río, caché 60 min, nunca el país entero; visibles desde zoom 13 con los
      estilos del Mashcón) y, solo con el río en alerta o emergencia, la **franja de atención**
      (columnas `ancho_m` y `franja` de `rio_cauce_mapa`, migración `rio_cauce_mapa_franja`: 60 / 120 /
      250 m a cada lado según el largo del río), punteada y rotulada "referencial, no es un mapa de
      inundación". La tarjeta "Tu zona ahora" elige el río más cercano entre los vigilados del
      departamento y los ~100 ríos con trazo de ANA (`lib/zonaAhora.js riosTrazados`, `rioCercano`,
      `rioParaVer`): chips "A 820 m del río Rímac (trazo de ANA)", "Dentro/Fuera de la zona que podría
      inundarse (estimación SIMPAC con el relieve)" o "Este río no tiene mapa de zonas; la franja junto
      al cauce es solo referencial", y a más de 30 km "El río con trazo más cercano está a 34 km
      (Chicama)"; "Ver el río X en el mapa" encuadra a la persona y el tramo más cercano a zoom 16.
      `getTitular` ya pide `titular_corto` y la tarjeta lo usa (misma regla de frescura y nivel).
      Simulación DEV `?simular=rio:<rio_ana>:alerta|emergencia`. **Verificado el 24-10 en 8080**:
      Cajamarca ("A 2 km del río Mashcón", "Fuera de la zona"), Lima (ALERTA; "A 820 m del río Rímac",
      "Fuera de la zona ..., a 680 m"; 2 polígonos rayados del Rímac confirmados por DOM), Tumbes
      (EMERGENCIA; "A 1.1 km del río Tumbes"), Iquitos ("A 1.9 km del río Itaya", sin mapa de zonas);
      Piura, Trujillo y Chiclayo dicen "El río con trazo más cercano está a 31-34 km" (ver pendientes).
- **Pendiente de este bloque** (ver "Siguiente"): WebView del Mapa en un teléfono real; alias del
  río Piura (`backend/data/rios/cauces_alias.json`: la estación Puente Sánchez Cerro no quedó
  emparejada); Moche y Reque sin trazo en `rio_cauce`; popup de las zonas y de la franja probado
  solo por código (el clic abrió el aviso); Capacitor retirado el 24-10; firma y Play Console; mover el JSON de la cuenta de servicio fuera del repo.

**Ríos vigilados: el Mashcón (03 oct)** — **532 pruebas** del backend sin red y **68** del frontend
(`npm test`), build OK. Diseño verificado en vivo contra las fuentes (URLs y datos de hoy);
migraciones, cargador y vistas probados en PostGIS desechable y contra la BD real en transacciones
revertidas. **Desplegado**: migraciones `rios_vigilados`, `preferencia_mapa` y
`rios_aviso_vigente_fuente_caida` aplicadas, el Mashcón cargado (13 zonas, 14 incidentes), la tarea
`rios` corriendo (1680 avisos hidrológicos del país; el Mashcón sin aviso vigente hoy) e imágenes de
worker y backend reconstruidas. Una verificación adversarial posterior dejó las correcciones de abajo
(zona azul sin señales, aviso hidrológico en el cauce, fuente caída, guardas de la tarea y del
cargador). Detalle en `README-tecnico.md` §5.6.7 y `frontend/README.md` ("Ríos vigilados" y "Capas
recordadas").
- [x] **El río se ve siempre:** el Mashcón con halo blanco, su color según la estación de ANA y
      "Río Mashcón" escrito sobre la línea (trazo de OpenStreetMap). Su disco pasa a 40 px con el
      rótulo «Mashcón · Tranquilo 0.13 m³/s»; en alerta o emergencia late y siempre se ve. Si un aviso
      hidrológico de SENAMHI (también el amarillo) es más alto que la lectura de ANA, el cauce y el
      disco toman el color del aviso y lo dicen («Mashcón · Aviso rojo SENAMHI», con la cifra de ANA
      al lado): así la zona no sale roja con el río "tranquilo".
- [x] **La zona que podría afectar, sin leer nada:** una franja rayada (estimación de SIMPAC con el
      relieve, Copernicus GLO-30) y manchas lisas (estudio INDECI-PNUD 2005 pasado a coordenadas).
      Ninguna es un mapa oficial vigente y nunca se dan metros. Los polígonos, desde zoom 13; desde
      zoom 14, «zona que podría inundarse» escrito junto al río y el límite de la faja marginal
      aprobada por ANA (4 resoluciones, 6 líneas). Si hay señales, un aura del color del nivel a lo
      largo del río hasta zoom 13 (en zoom 13, suave debajo de los polígonos): se ve con el mapa
      alejado.
- [x] **El color sale de las señales de hoy:** azul sin señales (sigue siendo una zona que podría
      inundarse; un gris no se leía como peligro); ámbar con lluvia fuerte medida en la cuenca, aviso
      de lluvia naranja o rojo en curso sobre ella, el río al 80 % de su alerta o un aviso
      hidrológico amarillo; naranja o rojo **solo** con ANA sobre su alerta o emergencia, o con un
      aviso hidrológico naranja o rojo de SENAMHI. La BD cruza los avisos y las estaciones con la
      cuenca (vista `rio_senal`); el nivel lo decide `lib/zonaRio.js`. El popup menciona sin subir el
      nivel un aviso de crecida que SENAMHI publica sin nivel y, si SENAMHI no responde hace más de
      3 h, que el aviso que se muestra es su último aviso conocido.
- [x] **Avisos hidrológicos de SENAMHI** (tarea `rios`, cada hora): la lista del país (12 meses) y el
      detalle solo de los avisos vigentes de los ríos vigilados (caudal, umbral rojo, centros poblados
      que podrían verse afectados), que se vuelve a pedir si la lista cambia su fin o su nivel. Con la
      lista caída o rara (menos de 500 filas) no escribe nada; si el texto "(vigente)" y la marca de
      la fila no coinciden, no apaga ningún aviso; un valor imposible (más de 10 veces el umbral) no
      se guarda; no crea alertas. Con SENAMHI caído, un aviso con fin conocido se sigue viendo hasta
      ese fin (migración `rios_aviso_vigente_fuente_caida`).
- [x] **Desbordes y daños pasados:** rombos con su año (’14, ’16, ’25...), 11 incidentes
      con fuente verificada (10 en el mapa) y 3 crecidas medidas en rojo. Solo los que nombran al
      Mashcón en su fuente (ANA, INDECI, Red Integrada de Salud Cajamarca del Gobierno Regional,
      Municipalidad de Cajamarca, SENAMHI, prensa, una tesis). Con cada zoom se juntan («×n») los
      que en pantalla quedarían encimados, y el acomodo corre el que quedaría tapado, con una línea
      fina hasta su lugar real (nunca se oculta). En el popup de la zona, «Pasó antes» va por
      cercanía a la zona tocada («Cerca de aquí» / «En otros tramos del río»).
- [x] **Panel de estado:** «Río Mashcón: ...» cuando su zona tiene señales, también con el panel
      plegado, con el botón «Ver en el mapa» (pliega el panel y encuadra el cauce). El contador y el
      badge no cambian.
- [x] **Capas recordadas** en el navegador (`localStorage`, `simpac.mapa`), con chip «Nueva» y
      «Restablecer capas»; sin `localStorage` (ventana privada) arranca con lo de siempre. Tabla
      `preferencia_mapa` (RLS por dueño) lista para cuando haya inicio de sesión.
- [x] **Simulación solo en desarrollo** (`?simular=mashcon:15.4`, `:19`, `:hidro2` a `:hidro4`,
      `:lluvia`, `:calma`) para ver la alerta sin esperar una crecida, o un día sin señales.
- [x] **Cargador con guardas:** exige al menos una zona estimada o de estudio y un incidente; con
      `--aplicar` cancela la carga si iba a borrar más de la mitad de lo que el río tiene en la BD
      (salvo con `--podar`) o si un id de incidente ya es de otro río.
- **Descartado:** SILVIA como disparador (es de huaycos y no tiene CORS), los tramos críticos de ANA
  (están en los afluentes) y la susceptibilidad de CENEPRED e INGEMMET (pinta todo el valle de
  "Alto"). SIGRID pide token: no se usa el que incrusta su visor.
- **Decisiones abiertas** (del usuario): ofrecer el trazo y lo derivado bajo ODbL o pasar a un cauce
  de Copernicus; si el aviso hidrológico suma al contador y al badge; validar con usuarios el rayado
  ámbar sobre un aviso naranja y la zona azul (sin señales) desde zoom 13.

**Avisos con ícono, pronóstico por localidad y nowcasting (23 sep)** — **467 pruebas** del backend
sin red, 24 del frontend (`npm test`) y build OK; cada tarea probada contra la BD real en
transacciones revertidas (con su migración aplicada adentro). **Desplegado**: migraciones
aplicadas e imágenes reconstruidas; primera corrida con 277 localidades, 3 avisos con ícono y el
nowcasting detenido por SENAMHI desde las 20:40 del 22 (la capa se oculta y lo explica). Revisado
en el navegador en escritorio y celular. Diseño aprobado por el usuario sobre una maqueta con
datos reales; 20 hallazgos de 2 verificadores corregidos (entre ellos un XSS en el tooltip de
las localidades).
- [x] **Íconos en los avisos de SENAMHI**: sobre cada área, una insignia redonda (disco blanco con
      aro del color del nivel) con gota, gota con rayo o copo; en calor, frío y viento, termómetro o
      viento (así su amarillo no se confunde con el de la lluvia).
  - **El rayo nunca se inventa:** solo si el aviso es de UNA región y SENAMHI afirma las descargas.
    Sobre 439 avisos de 2024 a 2026: 245 gota con rayo, 182 gota, 12 copo. El 376 ("sierra norte y
    costa norte") lleva gota y el popup cita la frase de las descargas.
  - **Popup en lenguaje claro:** "puede llover en algún momento en esta zona" (no en toda ni todo el
    día), los mm por subregión con barras, viento, rayos, granizo, nieve y el texto oficial sin
    cambios. Los mm se leen "todo o nada" (el 92% de los párrafos, ninguno atribuido a otro lugar);
    si no, va la cita literal.
  - El párrafo de cada día se empareja por su mapa **y** por su fecha: el 375 decía "martes 22" en
    el mapa del jueves 24 y no se muestra.
- [x] **Pronóstico oficial de SENAMHI por localidad** (tarea `pronostico`, cada hora): 277
      localidades (17 en Cajamarca), cada una como un disco blanco con el glifo del tiempo, nunca
      como área; punteado si SENAMHI escribe "tendencia a". Catálogo de coordenadas revisado a mano
      (236 con punto, entre ellas las 17 de Cajamarca y las 25 ciudades del selector). En el panel de
      estado, **franja de 3 días** de tu localidad (la de la ciudad elegida o, con GPS, la más cercana).
- [x] **Nowcasting de SENAMHI, experimental** (tarea `nowcast`, cada 10 min): manchas azules y
      violeta de lluvia moderada, fuerte o extrema para la próxima hora, en 2 horas o ahora. Si
      SENAMHI no publica hace más de 30 min no se muestra nada y el chip dice desde cuándo (el 22-09
      se detuvo a las 20:40). Apagado por defecto.
- [x] **Selector de día** (Hoy / Mañana / Viernes) que mueve a la vez los avisos y el pronóstico; el
      nowcasting solo va con "Hoy".
- [x] **Acomodo en pantalla**: tres escalas por zoom; las insignias que se tocan se juntan ("2
      avisos"), los discos que chocan pasan a punto de color, tu localidad siempre se ve (aro negro y
      nombre) y la insignia sigue a la vista aunque su punto salga de la pantalla. Dos amarillos
      superpuestos ya no se ven naranja.
- [x] **Robustez**: si el worker llega antes que las migraciones, los avisos se guardan igual (sin
      íconos) y las otras dos tareas solo dejan su latido; si el frontend no encuentra las columnas
      nuevas, vuelve a las de antes. Una página de SENAMHI cambiada falla y lo dice el latido (nunca
      se muestra "sin lluvia" por error). Nada se borra por una fuente caída; candado por tarea.
- **Fuera de alcance:** ETA, Open-Meteo, GLM (rayos por satélite) y `appmobile`.
- **Decisiones del usuario:** al elegir una ciudad el zoom sigue en 14 (la insignia sigue a la
  vista); sin modo "ejemplo grabado" para la presentación.

**Datos correctos y lenguaje claro (22 sep, noche)** — investigación en vivo verificada por agentes
- [x] **Falsas emergencias de Loreto corregidas**: en temporada seca ANA publica, para algunos ríos
      amazónicos, umbrales de **nivel bajo** (vaciante: el de emergencia queda por DEBAJO del de alerta).
      Se leían como crecida y el panel entero salía en "Emergencia". Ahora `ana.py` los reconoce
      (`umbral_bajo`), la alerta es de tipo `nivel_bajo` y el mapa no dibuja zona de desborde.
- [x] **ICEN con los cortes oficiales** (Nota Técnica ENFEN 01-2024): +1.98 es "cálida moderada", no
      "fuerte" (los cortes de 2012 fallaban en 6 de 11 meses). El IGP no publica desde julio: el ICEN
      al día sale de la **Tabla 3 del Informe Técnico ENFEN** (hoy julio +3.38 fuerte y el estimado
      de agosto +3.73 extraordinaria). Se guarda el mes más nuevo con su `origen` y nunca retrocede.
- [x] **RONI en vez de ONI**: NOAA vigila El Niño con el RONI desde feb-2026 (jun-ago: +1.36,
      moderado; el ONI viejo daba +1.80).
- [x] **Estado oficial del ENFEN** (Vigilancia / Alerta de El Niño Costero): conector que descubre
      el último comunicado PDF (gob.pe, SENAMHI, web ENFEN) y lo lee con `pypdf`, más el ICEN de la
      Tabla 3 del Informe Técnico (solo se baja cuando sale uno nuevo). Tarea `enfen` del worker cada
      6 h; tabla `comunicado_enfen`. Hoy: CO 16-2026 "Alerta de El Niño Costero", próximo el 28 set.
- [x] **Latido de la ingesta** (tabla `latido`): el aviso "sin actualizar" ya no depende de los índices.
- [x] **Lenguaje claro** (`frontend/src/lib/lenguaje.js`, un solo diccionario):
  - Primero tu zona y después el país: el departamento sale de la ciudad elegida o del GPS
    (estación SENAMHI más cercana; Jaén ya no cae en Amazonas).
  - Ríos: "lleva el 1 % del caudal que activa la alerta", "le faltan 3.68 m", "río bajo por la
    temporada seca".
  - Lluvia de las últimas 24 h de tu departamento.
  - El Niño en palabras ("El Niño costero: Alerta", "mar más caliente"), con su mes y su fuente.
  - Anomalías con las clases oficiales de SENAMHI.
  - Lo que es criterio de SIMPAC ("atento" de los ríos) se rotula como referencial. La lluvia ya no
    usa umbrales de SIMPAC: se compara con la referencia de SENAMHI de cada estación (ver "Alertas
    de lluvia con la referencia de SENAMHI").
- [x] **Revisión adversarial de este cambio** (8 agentes, 24 hallazgos confirmados, corregidos). Lo principal:
  - Nunca "Normal" en verde por algo que no se midió: mientras carga, si falla la consulta o si
    SIMPAC no vigila nada en la zona (Callao) sale "Sin datos". En Lima aclaraba que la lluvia aún
    no se medía ahí (hoy la lluvia de la última hora cubre todo el país).
  - La lluvia medida sube la zona a "Aviso" como mucho (rótulo "Atentos a la lluvia"), nunca a
    "Alerta" ni "Emergencia", y se describe como lo que es: lo que midió una estación frente a la
    referencia de SENAMHI, no un aviso oficial. Reemplazó a la alerta de 24 h con umbral
    provisional, que llegaba hasta "Alerta".
  - Avisos cuando ANA o SENAMHI no respondieron en la última corrida.
  - La etiqueta dice "La Niña costera" si el ENFEN declara La Niña.
  - La lluvia de otra ciudad ya no queda pegada al cambiar de ciudad.
  - El worker encola `ingesta` y `enfen` al arrancar (el beat pierde su programación al recrear el
    contenedor).
  - La tarea ENFEN aísla el comunicado del Informe Técnico: si uno falla, el otro se guarda igual.
  - No vuelve a bajar 17 MB por un informe ilegible o que ya leyó.

**Fase 3: El Niño y alertas en gráficos (22 sep, noche)** — probado con datos reales, imágenes reconstruidas
- [x] **Avisos oficiales de SENAMHI como áreas sombreadas** (tarea `avisos`, cada hora): polígonos
      por nivel (amarillo, naranja, rojo) de los avisos meteorológicos y del aviso de lluvia de 24 h,
      en la tabla `aviso_senamhi`. Los de lluvia generan alertas por departamento (tipo `aviso`) y
      suben el estado de la zona: hoy Cajamarca sale en "Aviso" por el 376 (lluvias de ligera a
      moderada intensidad en la sierra norte, 23 y 24 set) y el de 24 h.
- [x] **Lluvia de la última hora en todo el país** (tarea `lluvia_nacional`, cada 30 min): ~216
      estaciones automáticas de SENAMHI en 24 departamentos, con la referencia de lluvia de cada una
      (1 h y 6 h). La misma tarea escribe ahora las alertas de lluvia (ver el bloque siguiente).
- [x] **Serie del ICEN** mes a mes (`icen_serie`: IGP + tabla del Informe Técnico ENFEN, el ENFEN
      manda) para el gráfico.
- [x] **Capas nuevas en el mapa**, agrupadas en el panel (Alertas y avisos, Lluvia, Ríos y
      estaciones, El Niño, Comunidad), con selector, leyenda y una nota de qué muestra y de cuándo es:
  - Avisos de SENAMHI (vigentes o próximos días), prendida por defecto.
  - Quebradas que podrían activarse hoy (SILVIA de SENAMHI).
  - Lloviendo ahora (estaciones), lluvia de ayer / 7 días (superficie de SENAMHI) y lluvia por
    satélite (NASA IMERG).
  - Eventos El Niño pasados (1982-83, 1997-98, 2017, 2023, 2023-24), coloreados por cuánto más o
    menos llovió que lo normal.
- [x] **Panel "El Niño en gráficos"** (chip del mapa y botón de la barra lateral): los 3 pasos del
      Sistema de Alerta ENFEN con el actual resaltado, el ICEN de los últimos 24 meses coloreado por
      categoría (con el estimado del mes siguiente punteado) y botones que muestran en el mapa cómo
      llovió en otros El Niño.
- [x] **Licencia de SENAMHI**: su leyenda literal va al pie del panel de capas y en "Qué significa
      esto"; los avisos simplificados se rotulan "basado en el aviso de SENAMHI" con enlace al original.
- [x] **Revisión del frontend** (un revisor de código y otro de "¿esto es cierto?" contra las
      fuentes oficiales), 25 hallazgos corregidos. Lo principal: los mapas FEN dicen de qué meses son
      (no de todo el evento); la capa de huaycos muestra el nivel 4 y qué significa cada color; ya no
      se dice que El Niño trae lluvias fuertes a toda Cajamarca (es la costa norte y el oeste de
      Cajamarca); la leyenda del satélite usa los colores reales de NASA; los avisos de calor ya no
      se confunden con lluvia; un aviso cuenta una vez aunque cubra 17 departamentos; si el nivel
      de la zona sale de un aviso se dice "Aviso amarillo", no "Alerta"; la leyenda literal de
      SENAMHI queda siempre a la vista.
- [x] **Verificación adversarial** de cada frente del backend (un agente implementa y otro intenta
      romperlo, con pruebas contra la BD real en transacciones revertidas). Se corrigieron, entre
      otros: una tabla de SENAMHI con otro formato o un WFS vacío ya no borran avisos y alertas;
      las actualizaciones de un aviso reemplazan al original; una fila futura del IGP no queda
      fija; la fecha de la lluvia de "ayer" no se adelanta de madrugada. **312 pruebas** sin red.

**Alertas de lluvia con la referencia de SENAMHI (22 sep, noche)** — **338 pruebas** sin red,
migración `alerta_lluvia_referencia_senamhi` aplicada e imágenes reconstruidas (primera corrida: 213
estaciones evaluadas, 1 alerta real de 6 h en Cotahuasi, Arequipa)
- [x] **Fuera los umbrales provisionales de SIMPAC** (20 y 40 mm en 24 h, 15 mm en 1 h): eran los
      mismos en todo el país. 20 mm en 24 h es lluvia normal en la selva, y 15 mm/h casi no se
      alcanzaría en Cajamarca.
- [x] **Regla nueva** (`alerts.py`, tarea `lluvia_nacional`): una estación pasa si la lluvia de su
      última hora supera la referencia de SENAMHI para ella (1 a 25 mm) o si la de las últimas 6 h
      supera la de 6 h (hoy, el triple). Mayor estricto, una fila por estación, en todo el país. Se
      evalúa desde la BD, con candado, y deja de verse a las 3 h de la medición (vista
      `alerta_actual`). Detalle en `README-tecnico.md` §5.6.2.
- [x] **Solo "Aviso", nunca "Alerta"**: SENAMHI no documenta esa referencia como umbral de alerta y,
      según sus curvas IDF, se supera casi cada año en 2 de cada 3 estaciones (20 de 25 en
      Cajamarca). El nivel queda fijo en el SQL, en una restricción de la BD y en el frontend.
- [x] **En la web**:
  - Rótulo "Atentos a la lluvia"; si además hay un aviso amarillo de SENAMHI, gana "Aviso amarillo".
  - Hasta 3 líneas "Lluvia medida:" con el texto del worker, que termina en "no un aviso oficial".
  - La insignia y la métrica "alertas y avisos" cuentan solo lo oficial.
  - "Ninguna de sus N estaciones... pasa la referencia" solo si la última corrida de
    `lluvia_nacional` de verdad evaluó (`alertas` no nulo en el latido) y la consulta respondió; si
    no, "No se pudo revisar la lluvia de las estaciones de SENAMHI". La frase del resto del país
    solo lo dice si hay estaciones evaluables fuera de tu zona.
  - Lima, Piura o Loreto ya no dicen "SIMPAC aún no mide la lluvia aquí": la cobertura sale de
    las estaciones de SENAMHI del departamento.
  - La cabecera separa "ríos" y "lluvia", cada una con su hora y su aviso de atraso.
  - En el mapa, borde amarillo en las estaciones que pasaron la referencia (1 h o 6 h).
- [x] **API**: cada alerta del snapshot trae `oficial` (la lluvia, `false`) y el resumen suma
      `alertas_oficiales` y `lluvia_sobre_referencia`. Si la vista `alerta_actual` no existiera
      (worker desplegado antes que la migración), lee la tabla sin la lluvia.
- [x] **Verificación adversarial** (3 verificadores: backend con la migración y la BD real en
      transacciones revertidas, frontend con los módulos reales en node, y textos contra la
      especificación): 10 hallazgos, 9 corregidos (el décimo era el nombre provisional de la
      migración). Entre ellos: la restricción aceptaba nivel nulo; faltaban pruebas del snapshot y
      de la consulta de vigentes; dos casos en que la web decía "ninguna pasa" sin haber revisado.
- [x] **Hallazgo**: las hidrológicas automáticas sí dan lluvia horaria si se piden con `tipo_esta=M`
      (el repo decía que no). Sumarlas a la ingesta queda pendiente (ver "En progreso").

**Refactor y correcciones (22 sep)** — probado y corriendo (imágenes reconstruidas el 22 sep)
- [x] **Backend modular**: `config.py` (variables de entorno en un solo lugar), `db.py` (conexión),
      `ingesta/` (`recolectar.py` baja, `guardar.py` escribe, `departamentos.py`), `snapshot.py`
      (antes `cache.py`), `prototipo/` (lo viejo, fuera de las imágenes) y `tests/` (**pruebas sin
      red**: `python -m unittest discover -s backend/tests -t .`). Borrados los `seed_*` muertos.
- [x] **Bugs de datos corregidos**:
  - Departamento real en las estaciones (antes las 827 decían 'Cajamarca').
  - **Faltaban 155 estaciones** (982 reales, se guardaban 827):
    - 3 slugs estaban mal (`la-libertad`, `madre-de-dios` y `san-martin` llevan guion).
    - SENAMHI escribe una coordenada de Loreto como `-.1172`, que no es JSON válido.
    - El código viejo se tragaba esos errores sin avisar.
  - Hora de la lluvia: se guardaba 5 h antes. Corregida en el código y en la BD (720 filas).
  - Fecha de Perú, no la UTC del contenedor (desde las 19:00 pedía el reporte de "mañana").
  - Si ANA falla, sus alertas **ya no se borran** como si todo estuviera normal. Una alerta que no se
    pudo re-evaluar caduca a las 6 h.
  - IGP/NOAA ya no tumban la corrida.
  - Una estación sin temperatura ya no pierde su lluvia.
  - Nombres de departamento unificados entre SENAMHI y ANA.
  - Dos estaciones de ANA se llaman "San Pedro" (ríos Charanal y Santa) y una pisaba a la otra:
    la clave ahora incluye el río (migración `caudal_clave_con_rio`).
- [x] **API**: fuera `POST /api/refresh` (no tenía autenticación); el snapshot lee el último caudal
      por estación y las alertas vigentes, y si Supabase cae sirve la última copia buena.
- [x] **Frontend**:
  - Cada capa del mapa es su propio archivo en `src/map/layers/`, así sumar la capa FEN es un archivo.
  - Hooks (`usePanorama` se refresca cada 10 min, `useGeolocation`, `useLayerVisibility`).
  - **Popups escapados** (sin XSS).
  - El estado sale de la tabla `alerta` y dice "Perú", no "Cajamarca".
  - Contaba 4 ríos en alerta cuando eran 2: leía el historial, ahora lee `caudal_actual`.
  - Leyenda por capa, y la capa de reportes lee `report` real.
- [x] **Comunidad con UUID y permisos por columna** (migración `comunidad_uuid_y_permisos`):
  - `report`, `voto`, `comentario` y `message` con id uuid, que no se puede recorrer.
  - La BD pone `estado`, `confianza`, `likes`, vencimientos y fechas: nadie se auto-confirma.
  - No se vota el propio reporte ni uno vencido, ni se mueve un voto.
  - Perfil automático al registrarse, y la reputación solo la mueven los votos.
  - 5 reportes y 30 mensajes por hora como máximo.
  - Reportes solo dentro del Perú, y tipos estilo Waze validados en la BD.
  - Probado con ~40 casos (usuarios simulados) en una transacción revertida antes de aplicar.
- [x] **Revisión adversarial del refactor** (8 agentes: 4 revisan, 4 intentan refutar): 21 hallazgos
      confirmados, todos corregidos. Los más importantes:
  - **De madrugada se borraban las emergencias de caudal unas 6 h.** El reporte de ANA de un día
    solo trae las estaciones que ya midieron. Ahora se piden ayer y hoy, y las alertas se
    reemplazan estación por estación.
  - **Privacidad** (migración `comunidad_privacidad_y_limites`):
    - `autor` ya no es legible: con autor + GPS + hora se armaba el historial de ubicación de alguien.
    - Los reportes vencidos dejan de ser públicos.
    - Los comentarios tienen límite por hora.
    - No se quita un voto de un reporte vencido.
    - El límite por hora ya no se evade con requests en paralelo.
  - `caudal_actual` solo muestra lecturas de ayer u hoy.
  - En el mapa:
    - La gota de los reportes marcaba unos 140 m al costado.
    - Si una capa falla al cargar, se reintenta.
    - Estaciones con paginación.
    - Horas de Perú.
    - Aviso "sin actualizar" si la ingesta se detiene.
- [x] **Permisos del API endurecidos**:
  - `rls_auto_enable()` ya no se puede llamar.
  - Fuera TRUNCATE/TRIGGER a `anon`/`authenticated`.
  - `spatial_ref_sys` protegido con trigger.

**Seguridad (verificada 16 sep)**
- [x] **RLS activo en todas las tablas de datos** (confirmado con el *advisor* de Supabase). Únicos
      avisos: internos de PostGIS (`spatial_ref_sys`, extensión en `public`, `st_estimatedextent`).
- [x] Aclarado el modelo de llaves: la **anon key es pública por diseño** (va en el frontend y en
      cada request); la protección real es RLS. La **secret key** nunca sale del backend. Detalle en
      `README-tecnico.md` §8.1.

**Documentación** (`docs/`)
- [x] `README-tecnico.md`, `fuentes-y-endpoints.html`, `frontend-brief.md`, `stack-tecnologico.md`,
      `catalogo-idesep.md`, `pre-documentacion-general.html`, `guia-medicion.md` (cómo llenar las
      fichas ISO/IEC 25010 del curso con datos reales) y este `ESTADO.md`.
- [x] `README.md` de la raíz (instalación con Docker y carga de datos), `frontend/README.md`
      (capas, tablas que alimentan cada parte, comunidad), `appmobile/README.md` (compilar, firmar
      y publicar la app Android) y `backend/data/acudir/README.md` (fuentes de "A dónde acudir").
- [x] **Sin emojis** en toda la documentación y el código (solo texto e íconos SVG).

---

## Decisiones del equipo (15 sep)
- **Fuera** el apartado de administración para técnicos de Defensa Civil y la **moderación humana**
  (nada de contratar moderadores). Simplifica la app y evita tocar población/muestra en el informe.
- **La comunidad valida los reportes**: like/dislike + comentarios (la app es intermediaria, no juez).
  BD actualizada: tablas `voto` y `comentario` en vez de `confirmation`; sin roles admin.
- **Solo datos reales en el mapa**: se eliminó todo lo de demostración (zonas ficticias, usuarios
  cercanos, incidentes de ejemplo). Los incidentes serán **reportes reales** de la comunidad.
- **Reporte tipo Waze**: Inundación · Huayco/Deslizamiento · Lluvia intensa · Vía bloqueada · Atasco
  (leve/moderado/detenido) · Bache · Accidente · Otro. Ya validado en la BD (CHECK en `report.tipo`)
  y en `frontend/src/lib/reportTypes.js`; la pantalla de creación (`/comunidad/nuevo`) se hizo el
  14 oct. Policía quedó fuera.
- **Solo se reporta donde uno está** (GPS, sin pin manual) para evitar reportes troll.

## En progreso / parcial
- [x] **Frontend** — páginas Alertas, Comunidad (con crear reporte y detalle), Chat, Cuenta e
      Histórico con react-router (14 oct; ver "Software terminado"). `frontend-brief.md` queda como
      el brief original.
- [x] **Reportes reales**: login con Supabase Auth, pantalla de creación (solo con GPS real, foto
      opcional al bucket `reportes`), votos y detalle (14 oct). Todavía sin reportes ni usuarios
      reales en la BD (0 y 0 al 20-10; al 24-10 hay 2 usuarios en `auth.users`, de pruebas del equipo,
      y sigue sin reportes).
- [x] **App Kotlin, push y zonas de relieve desplegados (24 oct)**: 3 migraciones aplicadas
      (`push_estado`, `rio_cauce_mapa_franja`, `rio_cauce_zona`), zonas de 20 ríos cargadas, tarea
      `push` corriendo con credenciales; frontend, worker y API de Docker reconstruidos. Kevin, tras el
      pull: reconstruir frontend, worker y API (`docker compose up -d --build frontend backend worker`);
      **no hay que cargar nada** (las zonas ya están en la BD). Para que su worker también envíe push
      necesita el JSON de la cuenta de servicio de Firebase (fuera del repo) en
      `FIREBASE_CREDENCIALES_ARCHIVO`; sin él, la tarea solo deja su latido y no pasa nada.
- [x] **Software terminado desplegado (20 oct)**: 7 migraciones aplicadas (`comunidad_fotos_y_chat_realtime`,
      `punto_acudir`, `rio_cauce`, `titular_zona`, `report_foto_solo_bucket`,
      `aviso_hidrologico_sentido_indeterminado`, `titular_zona_titular_corto`), ríos del país y
      puntos de "A dónde acudir" cargados, tarea `titular` corriendo; frontend, worker y API de
      Docker reconstruidos. Kevin, tras el pull: reconstruir frontend, worker y API (`docker compose
      up -d --build frontend backend worker`); **no hay que cargar nada**: los datos ya están en la
      BD.
- [ ] **Supabase Auth en un dominio real**: el registro y "olvidé mi contraseña" mandan al usuario
      de vuelta a la URL de la web (`emailRedirectTo` / `redirectTo`); en el panel de Supabase hay
      que agregar esa URL (y la de la app, `https://localhost`) a las Redirect URLs y configurar un
      SMTP propio antes de tener usuarios reales (ver "Notas y riesgos").
- [x] **Alertas de lluvia desplegadas** (migración aplicada, imágenes reconstruidas). Kevin, tras el
      pull: reconstruir frontend, worker y API. Consulta de control en `README-tecnico.md` §5.6.2.
- [x] **Avisos con ícono, pronóstico y nowcasting desplegados** (migraciones `avisos_iconos`,
      `pronostico_localidad` y `nowcast_senamhi` aplicadas; imágenes reconstruidas). Kevin, tras el
      pull: reconstruir frontend, worker y API. Control con las consultas de `README-tecnico.md`
      §5.6.6.
- [x] **Ríos vigilados desplegados** (3 migraciones aplicadas, Mashcón cargado, tarea `rios`
      corriendo; worker, backend y frontend de Docker reconstruidos). Kevin, tras el pull:
      reconstruir frontend, worker y API (no hace falta volver a cargar el río: ya está en la BD).
      Control con las consultas de `README-tecnico.md` §5.6.7.
- [ ] **Serie de lluvia (24 h) en más estaciones y departamentos**: hoy la ingesta baja la serie
      horaria solo de Cajamarca (`SIMPAC_LLUVIA_DEPTS`; sumar otros es cambiar esa variable) y solo
      de las meteorológicas. Las hidrológicas automáticas también la dan si se pide con
      `tipo_esta=M` (63 en el país, 10 en Cajamarca; con `tipo_esta=H` la serie viene vacía):
      sumarlas lleva la lluvia de 24 h de Cajamarca de 14 a unas 24 estaciones. La lluvia de la
      última hora y sus alertas ya cubren todo el país (tarea `lluvia_nacional`).

---

## Siguiente (por hacer)

**Backend / datos**
- [x] **Levantar el stack** (`docker compose up --build`): ya corre; el **beat** de Celery programa
      la ingesta horaria y el refresco de caché (sin cron).
- [x] **`SUPABASE_DB_URL` en `.env`** (pooler + SSL): la ingesta horaria ya puebla la BD (verificado).
- [x] **Imágenes reconstruidas con el refactor** (22 sep): ingesta nueva verificada contra la BD real
      (982 estaciones en 24 departamentos, 672 filas de lluvia, 122 caudales, 2 alertas, sin fallas).
- [x] **Departamento de las estaciones**: corregido (ver refactor).
- [x] **Password de la BD reseteada** (22 sep); compartirla solo por canal privado.
- [x] **Revocado `EXECUTE`** de `rls_auto_enable()` (migración `permisos_api_endurecidos`).
- [x] **Capas de lluvia en áreas (fase 3)**: hechas (ver arriba). Radar: no hay sobre Cajamarca;
      Windy, OpenWeatherMap y Tomorrow.io piden key o son pagos.
- [ ] Repetir entre la 01:00 y las 08:00 la prueba de la fecha de la lluvia de "ayer" (la huella de
      `prec_1_all_points` supone que SENAMHI publica los puntos y el ráster juntos).
- [ ] **INPE (Hidroestimador, lluvia casi en tiempo real)**: su sitio exige autorización expresa de
      CPTEC/INPE para reproducirlo en medios de divulgación. Pedirla por correo antes de publicarlo.
- [x] **Umbrales de lluvia**: los placeholders de `alerts.py` se reemplazaron por la referencia de
      SENAMHI de cada estación (ver "Alertas de lluvia con la referencia de SENAMHI").
- [ ] Validar con SENAMHI o Defensa Civil, en temporada de lluvias (oct–abr), esa referencia como
      disparador de "Atentos a la lluvia": cada cuánto sale (`latido.alertas`, `alertas_6h`), las
      estaciones de valle amazónico con 5 mm/h y las de la costa con 1 mm/h (`README-tecnico.md` §10).
- [ ] **Otros ríos vigilados con zonas**: el Chonta, el San Lucas y el Namora (estación SENAMHI
      220206, que también tiene avisos hidrológicos). Hoy esos ríos ya salen resaltados con el trazo
      de ANA si tienen estación (capa nacional), pero sin zona que podría afectar ni desbordes
      pasados. Por río: una carpeta en `backend/data/rios/<id>/` con sus 6 archivos revisados y
      `cargar_rios --rio <id> --aplicar`; la tarea `rios` ya baja sus avisos si tiene
      `estacion_senamhi`.
- [ ] **Recargar los cauces del país** cuando `caudal_actual` gane estaciones (`cargar_cauces
      --desde-copia` en seco lista los ríos sin fila); RJ056 es de 2018 y la capa IGN cambió en
      abril de 2026. No hay tarea Celery: es carga a mano.
- [ ] **Clave del LLM** (`SIMPAC_LLM_KEY` en `.env` y `docker compose up -d worker`): hoy los 25
      titulares salen por reglas. Antes de prenderla, acordar el gasto (ver "Notas y riesgos") y
      revisar una semana de `latido.resumen` de `titular` (descartados y motivos).
- [ ] **Albergues y zonas seguras** de "A dónde acudir": pedir la lista georreferenciada a la
      Municipalidad Provincial de Cajamarca / COER (mesa de partes); los servidores de INDECI
      (`geoserver.indeci.gob.pe`, `geosinpad`) no respondían el 14-10. Los tipos `albergue` y
      `zona_segura` ya existen en la tabla.
- [x] **Imagen del frontend a `node:22-alpine`** (`frontend/Dockerfile`, 20-10; reconstruida el 24-10
      sin el aviso `EBADENGINE`).
- [ ] Decidir lo abierto de los ríos vigilados: ODbL (o cauce de Copernicus) y si el aviso
      hidrológico suma al contador y al badge.
- [ ] **Alias del río Piura** en `backend/data/rios/cauces_alias.json` (la estación de ANA "Puente
      Sanchez Cerro" no quedó emparejada al trazo: `rio_cauce.estaciones = []`), recargar con
      `cargar_cauces --desde-copia --rio Piura --aplicar`; el mapa no lo resalta y desde Piura la
      tarjeta dice "El río con trazo más cercano está a 34 km (Chira)". Moche (Trujillo) y Reque
      (Chiclayo) no tienen fila en `rio_cauce` (no tienen estación de ANA ni aviso).
- [ ] **Zonas de relieve de más ríos**: el tramo alto del Marañón (Balsas, Corral Quemado) con
      `zonas_relieve --rio maranon --centro LAT,LON --etiqueta ...` y cualquier otro de `rio_cauce`;
      revisar visualmente los 17 ríos que no tuvieron captura (solo Cajamarca, Piura y Rímac se
      miraron en el navegador). Los 6 de selva baja no se calculan (el HAND no distingue nada).
- [ ] **Mover el JSON de la cuenta de servicio de Firebase fuera del repo**: está en la raíz
      (ignorado por `*firebase-adminsdk*.json`), pero conviene guardarlo en una carpeta de claves y
      apuntar `FIREBASE_CREDENCIALES_ARCHIVO` ahí.

**Frontend / móvil**
- [x] **Web (Mapa)**: React + Vite + Leaflet conectado a Supabase (ya está).
- [x] **Capa FEN en el mapa** (HU-12): polígonos coloreados por `RANGO` + selector de evento
      (geometrías simplificadas: 0,3 a 0,9 MB por evento).
- [x] **Mapas FEN por trimestre (HU-15, 25-10-2026).** Cada registro de IDESEP trae un .zip por
      trimestre (DEF, EFM, FMA; cada .zip una sola capa con `RANGO`) y antes se guardaba solo el
      primero. Ahora la tabla `mapa` tiene 13 filas FEN (5 eventos; 2017 trae feb a abr, que incluye
      marzo de 2017, el desborde del Piura), el selector de la capa ofrece "El Niño 1997-1998, dic a
      feb" / "ene a mar" / "feb a abr" (`lib/fen.js`; lo recordado con el valor viejo se migra al
      primer trimestre), la nota y el popup dicen los meses reales de la BD y el panel El Niño ofrece
      los otros trimestres de cada evento como chips.
- [x] **Web (resto)**: páginas Alertas, Comunidad, Chat, Cuenta, crear reporte, Histórico y
      react-router (14 oct).
- [x] **Inicio de sesión** (Supabase Auth): entrar, registro, recuperar contraseña, perfil y "Mis
      reportes" (14 oct). Con sesión, las capas recordadas también se guardan en la cuenta
      (`useLayerVisibility.js` sube a `preferencia_mapa` 1,5 s después del último cambio y al
      entrar aplica la copia más reciente entre el navegador y la cuenta); sin sesión, solo en el
      navegador. Probado sin usuarios reales (0 en `auth.users`).
- [ ] **Validar con usuarios** (gente de Cajamarca sin formación técnica): la hoja "Tu zona ahora"
      (se entiende el semáforo y la instrucción en 5 segundos), las zonas de los ríos (rayado ámbar
      sobre un aviso naranja; zona azul sin señales desde zoom 13), los textos de "Ríos muy bajos" y
      el flujo de reportar. Hasta ahora todo se probó con los verificadores, no con usuarios.
- [ ] **Radios de "A dónde acudir"**: la tarjeta busca en una caja de 30 km y prefiere un hospital
      de 24 h si está a menos de 15 km; son criterios de SIMPAC, no de una norma. Revisarlos con
      Defensa Civil o la DIRESA (en zona rural 30 km puede dejar la tarjeta vacía).
- [ ] **Pendientes de la hoja**: nowcasting animado de 3 cuadros, recorrido "Si el río se desborda"
      y la línea recta hasta el punto de acudir.
- [x] **App móvil**: Android con Capacitor sobre la misma web (`frontend/android/`, APK de 5,06 MiB
      compilado y probado en emulador el 20-10). Queda descartado reescribirla en React Native.
      **Desde el 20-10 (integrada el 24-10) la app es nativa en Kotlin + Jetpack Compose**
      (`appmobile/android/`, guía en `appmobile/README.md`), por decisión del usuario; la de Capacitor
      se retiró del repo el 24-10.
- [x] **WebView del Mapa en blanco** (24-10): la web cargaba (DOM completo) pero no se pintaba porque
      el `WebView` creado dentro de `AndroidView` quedaba con alto `WRAP_CONTENT` y Chromium resuelve
      `100vh` y `height: 100%` como 0 (la web usa `h-screen`; la app de Capacitor no lo sufría porque su
      WebView venía del XML con `match_parent`). Arreglado con `LayoutParams(MATCH_PARENT,
      MATCH_PARENT)` en `ui/mapa/MapaScreen.kt`: el emulador sin ventana ya muestra tiles, chip SIMPAC y
      hoja. Queda probarlo en un teléfono real y revisar `canGoBack` del botón atrás tras abrir `/cuenta`
      (una vez volvió a Inicio en vez de retroceder).
- [x] **Notificaciones push (FCM)** (HU-20, 20/24-10): proyecto Firebase `appsimpac`,
      `google-services.json` en `appmobile/android/app/` (ignorado), app suscrita a `pais` y
      `zona_<slug>`, tarea `push` del worker con la cuenta de servicio montada; envío real recibido
      en el emulador el 24-10. Solo lo oficial: nunca aviso amarillo ni lluvia medida.
- [x] **Capacitor retirado** (24-10): fuera `frontend/android/`, `frontend/capacitor.config.json`, los
      scripts `android:*` de `frontend/package.json` y las dependencias `@capacitor/*`;
      `useGeolocation.js` solo con `navigator.geolocation` y `pwa.js` sin la condición de
      `window.Capacitor`; `npm test` y `npm run build` OK.
- [ ] **Publicar en Play Console**: crear la upload key (`keytool`, fuera del repo), `key.properties`
      o `SIMPAC_KEYSTORE_*`, `.\gradlew.bat bundleRelease` en `appmobile/android/` (`versionCode 2` ya
      puesto), cuenta de desarrollador (25 USD; una cuenta personal nueva exige prueba cerrada con 12
      probadores durante 14 días), ficha, política de privacidad pública y cuestionario de seguridad
      de datos (ubicación solo en primer plano; token de FCM). Opcional: limpiar los avisos de
      deprecación de `security-crypto` 1.1.0 cuando AndroidX publique el reemplazo.
- [x] **Stadia Maps fuera de localhost**: la web en Vercel usa la API key de Stadia
      (`VITE_STADIA_API_KEY`); los tiles cargan en el dominio real (verificado el 2026-11-05).

**Despliegue en la nube (preparado el 04-11-2026; ejecutado el 05-11-2026)**
- [x] **En producción**: web `https://simpac-v7nf.vercel.app` (Vercel, Root Directory `frontend`,
      cabeceras y caché de `vercel.json` verificadas con curl, rutas con recarga, 404 en assets
      inexistentes, brotli, service worker activo, 17 consultas a Supabase sin fallas); API
      `https://simpac-production.up.railway.app` (`/health` 200 y `/api/snapshot` 200 en 1,2 s);
      `worker` en Railway con las 10 tareas (ENFEN leyó el CO 19-2026 del 30-10 en la primera
      corrida) y `Redis` de Railway. Railway no acepta *config as code* en servicios nuevos: los
      ajustes se escribieron en Settings (Dockerfile vía `RAILWAY_DOCKERFILE_PATH=backend/Dockerfile`,
      `PORT=8000`, healthcheck `/health`; el worker con `--concurrency 2` e `INSTALAR_MAPAS=1`).
- [ ] **Tras el primer deploy**: `SIMPAC_CORS_ORIGENES=https://simpac-v7nf.vercel.app` en la API de
      Railway, `https://simpac-v7nf.vercel.app/cuenta` en las Redirect URLs de Supabase Auth y la app
      Android en release con `-Psimpac.apiUrl=https://simpac-production.up.railway.app
      -Psimpac.webUrl=https://simpac-v7nf.vercel.app`.
- [x] **Archivos y guía**: `railway.api.json` y `railway.worker.json` en la raíz, `backend/Dockerfile`
      arranca uvicorn en `$PORT` (8000 si no existe: `docker compose` igual que antes), guía en
      `README-tecnico.md` §8.5 y resumen en el `README.md` ("Despliegue en Railway y Vercel").
- [x] **Railway, proyecto desde `Federjj/SIMPAC`** (hecho el 05-11-2026; el servicio de la API se
      llama `SIMPAC` en el panel): servicio Redis; servicio `api` (ajustes de
      `railway.api.json` escritos en Settings: Dockerfile `backend/Dockerfile`, start command, healthcheck
      `/health`, reinicio On failure; variables `REDIS_URL=${{Redis.REDIS_URL}}`, `SUPABASE_URL`,
      `SUPABASE_PUBLISHABLE_KEY`, `SNAPSHOT_TTL`, `SIMPAC_CORS_ORIGENES` con el dominio de Vercel,
      `PORT=8000`, dominio público generado); servicio `worker` (ajustes de `railway.worker.json` en
      Settings, las de la API
      más `SUPABASE_DB_URL` del pooler, `SIMPAC_LLUVIA_DEPTS`, `FIREBASE_CREDENCIALES` en base64,
      `FIREBASE_PROYECTO=appsimpac`, `INSTALAR_MAPAS=1`, `SIMPAC_LLM_KEY` opcional; sin dominio).
      Comprobar `/health`, `/api/snapshot` y los logs del worker (las 10 tareas con `succeeded`).
- [x] **Base64 de la cuenta de servicio de Firebase** (hecho el 05-11-2026) con el comando de PowerShell de §8.5 (al
      portapapeles, sin mostrarlo ni guardarlo) y pegarlo en `FIREBASE_CREDENCIALES` del worker. La
      primera corrida de `push` con credenciales en un servidor nuevo avisa una vez las alertas vigentes
      (`push_estado` ya está sembrada en la BD compartida, así que desde Railway no se repite).
- [ ] **Plan y límite de gasto en Railway**: el plan Free (USD 1/mes, 0,5 GB por servicio) no alcanza
      para el worker las 24 h; con Hobby (USD 5/mes con 5 incluidos) el stack sale en unos USD 7-9 al
      mes. Poner un límite de uso con alerta (Workspace > Usage > Set Usage Limits) y dejar *Serverless*
      apagado en `api` y `worker`. Vigilar la memoria del worker en Metrics (local: ~365 MiB al arrancar
      con la concurrencia por defecto; en Railway va con `--concurrency 2`).
- [ ] **Railway ya no lee `railway.*.json` en servicios nuevos** (config as code deprecado; en los
      viejos deja de leerlos el 2026-12-01): los dos archivos quedan como referencia versionada y lo mismo
      se escribe a mano en Settings de cada servicio (Dockerfile path, start command, healthcheck,
      restart). Migrar a Infrastructure as Code (`.railway/railway.ts`, `railway config migrate`, con la
      CLI y sesión iniciada) cuando el proyecto ya exista en Railway.
- [ ] **Después de la API en Railway**: `SIMPAC_CORS_ORIGENES` con el dominio definitivo de Vercel (y el
      propio si lo hay); en la app Android, Cuenta > Ajustes con `https://<api>.up.railway.app` y la web
      de Vercel (o cambiar los valores por defecto de `data/Ajustes.kt` antes del release); Redirect
      URLs de Supabase Auth con el dominio de Vercel; región de Railway lo más cerca de São Paulo
      (`sa-east-1`, donde está el pooler de Supabase) si el plan lo permite.

---

## Reparto (para no duplicar)
- **Tú (Fabricio) + Claude:** datos, conectores, Supabase/BD, backend, frontend (páginas, hoja
  "Tu zona ahora", ríos del país con zonas, a dónde acudir), app Android (Capacitor y ahora la nativa
  en Kotlin), push por FCM (proyecto Firebase `appsimpac`) y documentación.
- **Kevin:** hizo el pipeline de mapas FEN históricos; le queda la cuenta de Play Console. **Tras el
  pull del 24 oct**: reconstruir frontend, worker y API (`docker compose up -d --build frontend
  backend worker`); **no cargar nada**: migraciones, ríos del país, zonas de relieve, puntos de "A
  dónde acudir" y titulares ya están en la BD compartida. Para compilar la app: JDK 21, Android SDK
  36 y `.\gradlew.bat assembleDebug` desde `appmobile/android/` en PowerShell (ver
  `appmobile/README.md`); para que la app reciba push, `google-services.json` en
  `appmobile/android/app/` (se descarga de la consola de Firebase; no va al repo).

## Notas y riesgos activos
- **Conexión a la BD: usar el pooler**, no `db.<ref>.supabase.co` (solo IPv6; falla en Docker y en
  redes sin IPv6, como le pasó a Kevin por wifi). Usuario del pooler: `postgres.<ref>`; si falta el
  `.<ref>` sale `ENOIDENTIFIER`.
- **Tras cambiar código de `backend/`, reconstruir backend y worker** (imágenes separadas).
- **TLS estricto en los conectores**: si un portal del Estado rompe su certificado, la ingesta de esa
  fuente falla (a propósito, en vez de aceptar datos sin verificar).
- **Ningún endpoint de la API escribe en la BD**: las escrituras van por el worker o por scripts
  (`cargar_fen.py`). La API no recibe `SUPABASE_DB_URL`.
- **ANA es intermitente** (a veces 500/timeout). Es el organismo, no el código: cada fuente está
  aislada, la corrida sigue aunque una falle y queda anotada en `fallas` del resumen de la tarea.
- **Token de Supabase con full-access** en variable de entorno: funciona, pero ideal reducir su
  scope al proyecto cuando se pueda. Se puede revocar en cualquier momento.
- **Advisor de Supabase** (quedan solo avisos de PostGIS que el rol postgres no puede tocar):
  `spatial_ref_sys` sin RLS (el Data API la dejaba **escribible** por anon; ahora un trigger rechaza
  esas escrituras), PostGIS en `public` y `st_estimatedextent`. Moverlo de esquema sería recrear la
  extensión y las columnas geom: queda para después de la entrega. También avisa de `mis_reportes()`
  (SECURITY DEFINER llamable con sesión): es a propósito, solo devuelve los reportes propios.
- **Cambios de BD = archivo nuevo en `supabase/migrations/`** (y reflejarlo en `schema.sql`).
- **La anon key es pública por diseño** (no es fuga): viaja en cada request y se ve en el navegador;
  lo que protege es **RLS**, que está activo en todas las tablas de datos.
- **Referencia de lluvia no documentada**: la de SENAMHI por estación (capa `g_umbrales`) no tiene
  documentación pública ni se presenta como umbral de alerta. Por eso la lluvia medida queda en
  "Aviso" ("Atentos a la lluvia") y cada texto dice que no es un aviso oficial. En temporada de
  lluvias saldrá seguido (se supera casi cada año en 2 de cada 3 estaciones), y donde la referencia
  es de 1 mm/h (costa de Lima, Ica y Arequipa) basta una lectura mala de una sola estación.
- **ANA cambia de juego de umbrales según la temporada** (crecida / nivel bajo). ANA no publica el
  nivel amarillo que sí usa SENAMHI en sus avisos hidrológicos.
- **Worker corriendo como root** en el contenedor: solo un `SecurityWarning` de Celery, inofensivo
  en Docker; si se quiere limpio, correrlo con un usuario no-root en el Dockerfile.
- **HTML de SENAMHI sin API**: el pronóstico por localidad y los párrafos de los avisos se leen de
  páginas HTML. Si SENAMHI cambia su formato, la tarea falla y lo dice el latido (`fallas`), en vez
  de mostrar "sin lluvia"; los avisos siguen saliendo, con gota. Sus pruebas usan muestras reales
  guardadas (`backend/tests/muestras/`).
- **Huecos del nowcasting**: SENAMHI lo publica cada 10 min, pero con huecos (el 22-09 no publicó
  nada entre las 20:40 y pasadas las 23:25) y lo llama "referencial y en calibración". Pasados 30 min
  el mapa se vacía solo y el chip lo dice; `retraso_min` del latido sirve para calibrar ese umbral.
- **Localidades sin ubicar**: 41 de las 277 del pronóstico no tienen punto en el catálogo (no
  coinciden con una estación): se guardan pero no se ven. Van en `sin_ubicar` del catálogo y en
  `sin_ubicacion` del latido.
- **Términos de SENAMHI**: además de la leyenda literal, dicen que la página es "para el uso
  personal y del usuario". Conviene mencionarlo al presentar el proyecto.
- **Límites del relieve (zona estimada de los ríos)**: Copernicus GLO-30 es un modelo de superficie
  (techos y árboles) con 2 a 3 m de error vertical, del orden de los umbrales. En la ciudad se queda
  corto (las manchas de INDECI 2005 caen solo entre un 5 % y un 36 % dentro de la zona de 3 m) y dos
  estimaciones independientes coincidieron solo en un 44 %. Por eso la web la rotula como
  estimación, muestra también el estudio de 2005, nunca da metros y nunca relaciona m³/s con la
  extensión. No existe un mapa oficial de inundación del Mashcón.
- **ODbL**: el trazo de OpenStreetMap y lo derivado de él (zonas estimadas, cuenca) se leen por la API
  pública de Supabase, así que hay que ofrecerlos bajo ODbL con atribución (va en la fuente de las
  capas y en cada zona). Pendiente la decisión del usuario; la alternativa es un cauce de Copernicus.
- **Overpass sin uso en vivo**: saturado en 4 de 7 consultas durante la investigación. El trazo del
  río se bajó una vez por la API 0.6 de OSM y vive en el repo y en la BD; nada consulta OSM, ANA ni
  GEOCATMIN por visita. Si OSM corrige el río, hay que volver a armar los archivos y cargarlos.
- **Avisos hidrológicos de SENAMHI sin API**: se leen de una página HTML (~700 KB por pedido). Si
  cambia, la tarea `rios` falla con `lista_rara` (menos de 500 filas: no escribe nada) o con
  `vigente_ambiguo` (guarda la lista, pero no apaga ningún aviso); sus pruebas usan muestras reales.
  Con SENAMHI caído o la página cambiada, un aviso con fin conocido se sigue viendo hasta ese fin
  (pasadas 3 h, el popup dice que es su último aviso conocido) y uno sin fin conocido deja de verse
  a las 3 h de la última lectura de la lista.
- **Ubicación de los incidentes**: es aproximada (prensa, municipio, ANA); cada rombo cita su fuente y
  su precisión.
- **Supabase gratuito se pausa**: el proyecto estuvo pausado del 15 al 19 oct (se reanudó el 19-10
  a las 22:10 desde el panel). Mientras está pausado la web no carga datos y el worker falla en
  cada tarea; al reanudar todo vuelve solo. Si va a quedar días sin uso, entrar al panel o pasar a
  un plan de pago antes de la entrega.
- **Stadia Maps en un dominio real y en la app**: las tiles salen sin llave solo desde `localhost`.
  La app cumple porque su origen es `https://localhost` (`androidScheme`), pero la web publicada en
  un dominio necesita una API key de Stadia (variable `VITE_...` en el build) o cambiar la base a
  OpenStreetMap/CARTO con su atribución (`frontend/src/map/baseMap.js`). Si Stadia cambia su regla
  de `localhost`, la app se queda sin fondo (el mapa se ve gris).
- **Correo de confirmación de Supabase Auth**: el registro exige confirmar el correo y el servidor
  de correo que trae Supabase por defecto tiene un límite bajo de envíos por hora y puede caer en
  spam; para usuarios reales hay que configurar un SMTP propio (Authentication > SMTP) y agregar la
  URL de la web y `https://localhost` a las Redirect URLs. Hoy (0 usuarios) no se ha probado un
  registro de punta a punta con correo real.
- **Costo del LLM del titular** (solo si se pone `SIMPAC_LLM_KEY`): Haiku 4.5 cuesta USD 1 por
  millón de tokens de entrada y 5 por millón de salida; cada pedido lleva unos 900-1200 tokens de
  entrada y devuelve 60-120 (tope 200): ~USD 0,0015 por pedido. Se pide una vez por departamento y
  solo cuando cambia la huella de sus insumos. Peor caso teórico (los 25 cambian en las 48 corridas
  del día): 1200 pedidos, ~USD 1,80/día (~54/mes); realista en lluvias, 150-500 pedidos/día (USD
  0,25-0,75); en época seca, centavos. Sin clave no sale ningún pedido a internet. El modelo solo
  redacta sobre cifras ya calculadas y el texto se descarta si no pasa la validación.
- **Licencias de los datos nuevos**: el trazo de los ríos del país es de ANA - GeoSNIRH (RJ056 2018
  e IGN), que no publica texto de licencia: se trata como información pública del Estado con
  atribución obligatoria y cada fila guarda `fuente`, `licencia`, `atribucion` y `url_consulta`;
  no se deriva de él ninguna zona inundable. RENIPRESS (SUSALUD) es ODC-By; el padrón de comisarías
  (MININTER 2019) es ODC-By pero el servicio de CENEPRED que lo sirve no declara licencia y es de
  2019 (la web lo dice); el directorio del CGBVP es información institucional sin licencia
  declarada. Todo se muestra con fuente, fecha y atribución; nada se redistribuye como propio.
- **Avisos hidrológicos de vaciante**: en temporada seca SENAMHI publica "SITUACIÓN ACTUAL DEL
  NIVEL" de ríos amazónicos (descenso); desde el 20-10 se guardan con `sentido = 'descenso'` o
  `'indeterminado'` y no tiñen el río ni la zona. Un título nuevo que no diga descenso ni crecida
  queda `indeterminado` (se muestra como información, nunca como crecida).
- **Service worker**: `sw.js` solo cachea la cáscara propia. En el navegador integrado de la
  verificación el registro falló ("An unknown error occurred when fetching the script") aunque nginx
  sirve `/sw.js` con 200; no se pudo confirmar en Chrome. La app no depende de él.
- **Dockerfile del frontend**: ya es `node:22-alpine` (20-10); el aviso `EBADENGINE` de
  `@supabase/supabase-js` 2.116.0 desapareció al reconstruir el 24-10.
- **Push (desde el 24-10 existe)**: la alerta llega al teléfono solo a quien tenga la app Kotlin
  con el interruptor de notificaciones encendido (tema `zona_<slug>` de su departamento y `pais`).
  Llega como mucho ~35 min después de que SENAMHI o ANA publiquen (la tarea `titular` corre cada
  30 min y `push` cada 5). La primera corrida con credenciales avisa una vez las alertas vigentes de
  ese momento (eso pasó el 24-10 con 6 departamentos); para evitarlo en otro servidor, sembrar
  `push_estado` antes (consulta en `README-tecnico.md` §5.6.12). La web no recibe push (no hay Web
  Push); quien usa solo la web sigue teniendo que abrirla.
- **Cuenta de servicio de Firebase**: es un secreto (`*firebase-adminsdk*.json` está en
  `.gitignore`); hoy el archivo está en la raíz del repo de la PC de desarrollo y el `.env` apunta a
  él. Moverlo a una carpeta de claves. Si se filtra, revocarlo en la consola de Firebase
  (Configuración > Cuentas de servicio) y generar otro.
- **WebView del Mapa de la app Kotlin**: arreglado el 24-10 (alto 0 por `LayoutParams` `WRAP_CONTENT`;
  ya pinta en el emulador sin ventana); falta confirmarlo en un teléfono real. Capacitor ya no está en
  el repo.
- **Zonas de relieve de los ríos del país**: mismos límites que las del Mashcón (modelo de
  superficie con 2-3 m de error vertical; en ciudades la zona queda corta porque el DSM incluye
  edificios: Piura, Sullana, Lima; no considera muros, defensas ni drenajes; el trazo de ANA es la
  línea central de 2018, no la orilla de hoy). Por eso cada zona dice "Estimación de SIMPAC con el
  relieve; no es un mapa oficial" y nunca da metros. La franja de atención de `rio_cauce_mapa` es solo
  una banda de ancho fijo junto al trazo, no un mapa de inundación, y se ve solo en alerta o
  emergencia.

## Integración del 24-10-2026 (app Kotlin, push, zonas de relieve, ríos del país)

Lo construido el 20-10 por cuatro agentes en paralelo se integró y verificó el 24-10: el detalle
está en el bloque **"App Android nativa, push y zonas de los ríos del país"** de "Hecho" y en
`README-tecnico.md` §5.6.11 (zonas de relieve y franja), §5.6.12 (push) y §8.4 (app Kotlin). Resumen
de la verificación:
- `docker compose up -d --build frontend backend worker` -> imágenes nuevas (frontend con
  `node:22-alpine`, worker con `google-auth`), `/health` ok, web 200, beat con 10 tareas, `push`
  encolada al arrancar y cada 300 s.
- Push: primera corrida con credenciales (24-10 21:58 UTC) `enviados 6` (las alertas vigentes:
  Tumbes emergencia; Piura, Huancavelica, Lima, Ayacucho, Arequipa alerta), después `enviados 0`;
  `--prueba --zona Cajamarca` recibido en el emulador y abre la pestaña Alertas.
- Zonas: 40 filas en `rio_cauce_zona` (20 ríos), la web dibuja las del Rímac y usa el chip
  Dentro/Fuera; 3,1 MB en `backend/data/cauces_zonas/`.
- App: `gradlew testDebugUnitTest assembleDebug` OK (22 pruebas JVM), APK de 15 846 448 bytes;
  Inicio, Alertas, Acudir y Cuenta verificados en el emulador; el Mapa (WebView) pinta desde el 24-10
  (arreglo de `LayoutParams` en `MapaScreen.kt`); pendiente confirmarlo en un teléfono real.
- Pendientes nuevos: alias del río Piura; Moche y Reque sin trazo; JSON de la cuenta de servicio
  fuera del repo. Capacitor retirado el 24-10.
