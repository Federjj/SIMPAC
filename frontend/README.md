# SIMPAC — Frontend

Web en **React + Vite + Tailwind + shadcn/ui + Leaflet + react-router** que lee directo de Supabase.
Al 14-10-2026 la web está completa: el **mapa** con sus capas, el inicio **"Tu zona ahora"** (hoja
inferior con semáforo y titular), y las páginas **Alertas, Comunidad, Chat, Cuenta e Histórico** con
sesión de Supabase Auth. El diseño original de las pantallas está en `docs/frontend-brief.md`
(estilo Waze). Desde el 20-10-2026 (integrado el 24-10) la hoja de inicio y la capa de zonas cubren
también los **ríos del país con zonas estimadas con el relieve** (ver "Ríos del país"). La **app
Android** es nativa en Kotlin + Compose (`appmobile/android/`, `appmobile/README.md`) y abre esta web
en un WebView solo para el mapa; la app anterior con Capacitor se retiró del repo el 2026-10-24 (ver
"App Android").

## Arranque
```bash
npm install
cp .env.example .env # llaves públicas de Supabase (en PowerShell: Copy-Item .env.example .env)
npm run dev          # http://localhost:5173 (SPA: cualquier ruta recarga bien)
npm test             # 157 pruebas de los módulos puros (node --test src/lib/*.test.js src/map/*.test.js, ~1 s)
npm run build        # compila a dist/ y deja un .gz al lado de cada .js/.css (plugin precomprimir de vite.config.js; no en Vercel ni Netlify)
npm run preview      # sirve dist/ para mirarlo
```
Variables (`.env`, solo públicas; Vite las expone al navegador): `VITE_SUPABASE_URL` y
`VITE_SUPABASE_PUBLISHABLE_KEY` (y, opcional, `VITE_STADIA_API_KEY` para el mapa base en un dominio
real; ver "Despliegue en Vercel"). Sin las dos primeras la app no arranca (`supabaseUrl is required`). Cliente:
`src/lib/supabaseClient.js`. En Docker las inyecta `frontend/Dockerfile` como `ARG` desde
`SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` del `.env` de la raíz (`docker-compose.yml`, servicio
`frontend`, nginx en `:8080`). `index.html` usa `%VITE_SUPABASE_URL%` para el `preconnect`. La web no
llama a la API FastAPI del backend: todo lo lee de Supabase con la publishable key (RLS).
Imports con alias: `@/` = `src/` (p. ej. `import { LAYERS } from "@/map/layers"`).

**Rutas** (`react-router-dom` 6.30, `BrowserRouter` en `main.jsx`, `<Routes>` en `App.jsx`):

| Ruta | Página | Pide sesión |
|---|---|---|
| `/` | Mapa (`pages/Mapa.jsx`), con la hoja "Tu zona ahora" | no |
| `/alertas` | Alertas y avisos | no |
| `/comunidad` · `/comunidad/:id` | Reportes vigentes · detalle con comentarios | leer no; votar y comentar sí |
| `/comunidad/nuevo` | Reportar incidente | sí (y GPS real) |
| `/chat` | Chat del departamento | sí (la BD no entrega mensajes sin sesión) |
| `/cuenta` · `/cuenta/entrar` · `/cuenta/registro` | Entrar, crear cuenta, recuperar contraseña; con sesión el perfil | no |
| `/historico?tipo=rio\|lluvia&id=<estación\|cod>&rio=<río>&rango=24h\|7d\|30d` | Histórico de una estación (gráfico, tabla, CSV) | no |
| cualquier otra | "Esta página no existe" | no |

Las páginas se cargan con `lazy()` + `Suspense` al entrar (el mapa arranca igual de rápido) y se
dibujan **sobre el mapa** a pantalla completa en celular y tablet (`< lg`, 1024 px) o en una
**columna de 28-30 rem** junto al mapa desde `lg`. `MapView` nunca se desmonta: al volver a `/` el
mapa sigue vivo y donde estaba. Mientras una página tapa el mapa, el `<main>` del mapa lleva
`inert` y `aria-hidden` (sus controles tapados no se alcanzan con teclado ni lector de pantalla).
Cada página cambia `document.title` ("Alertas y avisos · SIMPAC") y pasa el foco a su `h1`
(`components/PanelPagina.jsx`). Con recarga directa de cualquier ruta nginx cae en `index.html`
(`try_files`), verificado el 20-10-2026 en `:8080` para `/alertas`, `/comunidad`, `/chat`,
`/cuenta` y `/noexiste`. Los popups del mapa enlazan a las páginas con `<a data-ruta href>` y
`Mapa.jsx` los navega sin recargar.

## Estructura
```
src/
  App.jsx       el marco: SesionProvider + ContextoApp + Sidebar (md+) + BarraInferior (< md) + <Routes>;
                el estado que comparten las páginas (ciudad, zona, GPS, panorama, ríos vigilados, capas)
  main.jsx      BrowserRouter, montarDefsIconos() y registrarServiceWorker() · index.css · pwa.js
  pages/        Mapa (lo que antes era App: paneles, hoja "Tu zona ahora", modo emergencia) · Alertas ·
                Comunidad · ReporteNuevo · ReporteDetalle · Chat · Cuenta · Historico
  components/   Sidebar · BarraInferior (5 pestañas) · MapView · LayersPanel · StatusPanel (la hoja de 4 alturas) ·
                TuZona (semáforo, titular, chips, botón) · MedidorCaudal · BarrasLluvia · AcudirCercanos ·
                OnboardingGps · ElNinoPanel · CitySelector · DiaSelector · ChipNowcast · FranjaPronostico
                (y FranjaMini) · PanelPagina (cabecera con h1, volver, disclaimer) · EstadoCarga (Cargando,
                Vacio, ErrorCarga, EntraPara, Mensaje) · TarjetaAlerta · TarjetaReporte · Votos · IconoReporte ·
                NivelBadge · GraficoSerie (SVG propio) · ContextoApp (useApp) · ErrorBoundary · Glifo ·
                InsigniaCapa · ui/ (shadcn)
  hooks/        usePanorama(depto) (estado de tu zona y del país, se refresca solo) · useGeolocation
                (navigator.geolocation) · useLayerVisibility (capas recordadas, con la cuenta) · usePronosticoLocal ·
                useRiosVigilados(depto) · useZonaAhora (todo lo de la tarjeta de inicio) · useSesion
                (SesionProvider/useSesion) · useAltoHoja (publica --hoja-alto) · useContador (números que cuentan,
                prefers-reduced-motion)
  map/
    baseMap.js    mapa base (tiles Stadia, zoom, atribución corta en celular, ajuste de popups, ResizeObserver)
    atribucion.js línea corta de atribución ("© Stadia Maps · OpenMapTiles · OSM · Datos: SENAMHI, ANA"); puro
    markers.js    íconos SVG, markerIcon(), popupHtml() y escapeHtml()
    iconos.js     glifos del tiempo (SVG en línea y como imagen data: URI, ESTILO_GLIFOS) y sus degradados
    marcadores.js insignia de un aviso, disco de una localidad y disco de un río (L.divIcon de 0x0),
                  rombo de un desborde pasado y punto de un lugar de los avisos hidrológicos
    colocar.js    acomodo en pantalla, puro (qué se ve, qué se junta, qué rótulo cabe)
    acomodo.js    enlace de colocar.js con Leaflet (corre al mover el mapa); escala y banda de zoom
    rotuloBusqueda.js  dónde cabe un nombre sobre una línea (puro, con memoria de puntos)
    rotuloLinea.js nombre de un río escrito sobre su trazo (SVG textPath; DOM)
    popups.js     HTML de los popups y medidas de lo que tapa el mapa en celular (medidasPopup, ajustePopup)
    palette.js    colores por nivel, estación, ENFEN, aro de los avisos, pronóstico, nowcasting, zonas
                  de los ríos (ZONA_HEX, ZONA_OSCURO) y cauce resaltado (CAUCE_HEX)
    senamhi.js    imágenes WMS de la GeoServer de SENAMHI con estilo propio (SLD) y su atribución
    layers/       una capa por archivo + index.js (GRUPOS y LAYERS); nuevas: acudir.js
  lib/          supabaseClient · queries (todas las consultas) · consultaCache (cached/filas/todas/siExiste, puro) ·
                lenguaje (todos los textos en lenguaje claro) · nivel (semáforo, tu zona / el país) · tiempo ·
                ubicacion · reportTypes · geo · pronostico · avisoTexto · zonaRio (zona de un río vigilado,
                estación de un aviso) · zonaAhora (titular, distancias, chips y botón del inicio) · medidor
                (escala del medidor de caudal) · serie24h (barras de lluvia) · cauces (ríos del país con trazo) ·
                acudir (a dónde acudir) · alertas (página Alertas) · comunidad (reportes, votos, chat, errores en
                lenguaje claro, foto) · sesion (Supabase Auth, perfil, mi zona) · historico · preferencias ·
                simulacion (?simular=, solo desarrollo)
  data/         cities.js (capitales con su departamento y su localidad del pronóstico) · emergencias.js
                (números oficiales con fuente; copia de backend/data/acudir/numeros.json)
public/         manifest.webmanifest · sw.js (cáscara de la app, nunca datos) · iconos/ (192, 512, maskable)
```
Los módulos puros (`lib/tiempo.js`, `geo.js`, `pronostico.js`, `avisoTexto.js`, `lenguaje.js`,
`zonaRio.js`, `zonaAhora.js`, `nivel.js`, `medidor.js`, `serie24h.js`, `cauces.js`, `acudir.js`,
`alertas.js`, `comunidad.js`, `historico.js`, `preferencias.js`, `consultaCache.js`, `fen.js`,
`map/colocar.js`, `map/iconos.js`, `map/palette.js`, `map/atribucion.js`, `map/rotuloBusqueda.js`)
usan imports relativos que terminan en `.js` (sin `@/`) para que `node --test` los lea tal cual; sus
pruebas son los `*.test.js` de al lado. Al 25-10-2026: **162 pruebas en 20 archivos** (colocar 21,
zonaAhora 17, cauces 16, zonaRio 16, preferencias 16, alertas 9, acudir 8, comunidad 7, pronostico 7,
avisoTexto 6, historico 6, rotuloLinea 6, medidor 5, consultaCache 4, fen 4, iconos 4, nivel 3,
serie24h 3, atribucion 2, geo 2), todas pasan (el 24-10 eran 157: fen y preferencias sumaron 5 por los
trimestres de los mapas El Niño, HU-15).

## Capas del mapa
Cada archivo de `src/map/layers/` exporta la misma forma (detalle en `layers/index.js`): `id`,
`grupo`, `label`, `Icon`, `defaultVisible`, `legend` (lista o función de la opción), `fuente`,
`opciones` (opcional: un selector, p. ej. el evento y trimestre El Niño; con `vinculo`, las capas del
mismo vínculo comparten la opción; con `migrar(valor)`, un valor recordado con un formato viejo pasa
al actual antes de validarse), `insignia` (opcional: "Oficial" o "Experimental"), `load(opcion)` y
`render(group, datos, { opcion, map, avisar, acomodo })`, que puede devolver una nota corta ("dato
de las 14:30") o un objeto `{texto, corto, estado}` que el panel muestra bajo el switch; opcional
`refreshMs`. `MapView` carga cada capa al encenderla y cada vez que cambia su opción (reintenta a los
5, 15 y 60 s si falla) y **no redibuja** si un refresco trae exactamente los mismos datos (huella
JSON por capa, hasta 400 KB). Las áreas sombreadas van en el pane `areas` (El Niño) y en
`aviso2`/`aviso3`/`aviso4` (el relleno de los avisos, con la transparencia en el pane: dos amarillos
superpuestos no se ven naranja), con los bordes en `avisoBorde`, las zonas que un río podría afectar
en `zonaRio` (encima de los avisos: el toque cae en la zona y su popup cita el aviso), el nowcasting
en `nowcast` y los ríos resaltados en `rios` (halo), `rioFaja` y `rioCauce` (sobre las demás líneas),
debajo de los marcadores. Los grupos son `Alertas y avisos`, `Pronóstico`, `Lluvia`,
`Ríos y estaciones`, `El Niño`, `Comunidad` y `A dónde acudir`.
**Sumar una capa** = crear su archivo y agregarla a `layers/index.js`.

| Grupo | Capa | Archivo | Datos |
|---|---|---|---|
| Alertas y avisos | Avisos de SENAMHI (hoy / mañana / pasado mañana), con insignia | `avisos.js` | vista `aviso_vigente` (tarea `avisos` del worker; `icono`, `lectura`, `texto_dia` y `anclas` de la migración de íconos) |
| Pronóstico | Pronóstico por localidad (SENAMHI) | `pronostico.js` | vista `pronostico_vigente` (tarea `pronostico`): un disco por localidad, del mismo día que los avisos |
| Pronóstico | Lluvia en las próximas 2 horas (experimental) | `nowcast.js` | vistas `nowcast_estado` y `nowcast_vigente` (tarea `nowcast`); solo con "Hoy" |
| Alertas y avisos | Zonas que un río podría afectar | `zonasRio.js` | vistas `rio_zona_mapa`, `rio_senal`, `rio_vigilado_mapa`, tabla `rio_incidente` y `caudal_actual` (nivel en `lib/zonaRio.js`); además, para los ríos del país, `rio_cauce_mapa` y `rio_cauce_senal`: aura del nivel a lo largo del cauce si están en alerta o emergencia (el círculo de 2,5 km queda solo para una estación sin trazo) y, desde el 24-10-2026, las **zonas estimadas con el relieve** de `rio_cauce_zona_mapa` (por río a la vista desde zoom 12, visibles desde 13, mismos estilos que el Mashcón) y la **franja de atención** (`franja` de `rio_cauce_mapa`, solo con el río en alerta o emergencia); ver "Ríos del país" |
| Alertas y avisos | Quebradas que podrían activarse (huaycos) | `huaycos.js` | WMS SENAMHI `silvia:cuencas_nivel_12_prono1_silvia` (niveles 2 a 4) |
| Lluvia | Lluvia de la última hora (estaciones) | `lluviaAhora.js` | vista `lluvia_senamhi_actual` (tarea `lluvia_nacional`); color por intensidad, borde amarillo si pasó la referencia de SENAMHI (1 h o 6 h); se dibuja en un `L.canvas` |
| Lluvia | Lluvia de ayer / de la semana | `lluviaObservada.js` | WMS SENAMHI `prec_1` / `prec_1_ac07d` (superficie interpolada) |
| Lluvia | Lluvia por satélite (NASA) | `lluviaSatelite.js` | NASA GIBS, GPM IMERG 30 min (llega con 5-6 h de retraso) |
| Lluvia | Lluvia del mes frente a lo normal | `anomalias.js` | `mapa` con `variable = 'precipitacion'` |
| Ríos y estaciones | Ríos (disco con rótulo; el Mashcón y los ríos del país con estación resaltados con su trazo) | `rios.js` | vista `caudal_actual` (última lectura de ayer u hoy por estación), `rio_vigilado_mapa` y las fajas de `rio_zona_mapa`; ríos del país: `rio_cauce_mapa` (`cauce_lejos` ~50 m para todo el país de una vez; `cauce` ~6 m por río desde zoom 13) y `rio_cauce_senal` (avisos hidrológicos) |
| Ríos y estaciones | Desbordes y daños pasados | `desbordes.js` | tabla `rio_incidente` (rombo con el año; "×n" si con ese zoom quedarían encimados) |
| Ríos y estaciones | Estaciones SENAMHI | `estaciones.js` | `estacion` |
| El Niño | Eventos El Niño pasados (1982-83, 1997-98, 2017, 2023, 2023-24), con un selector por evento **y trimestre** ("El Niño 1997-1998, dic a feb" / "ene a mar" / "feb a abr": 13 opciones, lista en `lib/fen.js`; valor `"<periodo>\|<trimestre>"`, defecto `1997-1998\|DEF`; un valor recordado viejo como `"1997-1998"` pasa por `opciones.migrar` al primer trimestre). La nota y el popup dicen los meses reales de la BD (columna `meses`) | `fenHistorico.js` | `mapa` con `variable = 'FEN'`, una fila por `periodo` y `trimestre` (miles de polígonos: `L.canvas`) |
| Comunidad | Reportes ciudadanos | `incidentes.js` | `report` (la BD solo entrega los vigentes) |
| A dónde acudir | Salud, comisarías y bomberos (apagada por defecto; la enciende la tarjeta "A dónde acudir" o el panel) | `acudir.js` | tabla `punto_acudir` por caja a la vista (`getPuntosAcudirCaja`: columnas explícitas, filtro `.gte/.lte` por lat/lon, caja redondeada a 0,1 grados, caché 60 min); no dibuja bajo zoom 11, entre 11 y 12 omite salud sin atención 24 h, desde 13 todo; un `L.divIcon` por tipo con glifos lucide y colores fuera del semáforo |

Las capas WMS se piden directo a la GeoServer de SENAMHI (`idesep.senamhi.gob.pe`) con un estilo
propio (`sld_body`): transparente donde no hay nada. Esa GeoServer es intermitente: si una imagen
falla, la capa lo avisa en su nota. **Licencia SENAMHI:** su leyenda literal
(`ATRIBUCION_SENAMHI` en `map/senamhi.js`) va siempre a la vista al pie de la hoja en su altura
completa y al pie del panel de capas; los avisos simplificados se rotulan "basado en el aviso de
SENAMHI" y enlazan al original. NASA GIBS pide reconocer "NASA GIBS, parte de ESDIS": va en la
fuente y en la atribución de la capa satelital. **Atribución del mapa** (`map/baseMap.js`,
`map/atribucion.js`): desde `lg` el texto completo de Leaflet; en celular una sola línea
"© Stadia Maps · OpenMapTiles · OSM · Datos: SENAMHI, ANA" más un botón "más" (`aria-expanded`) que
despliega el texto con sus enlaces. Antes la atribución crecía a 2-3 líneas de ancho completo sobre la
hoja y un toque al mapa abría openstreetmap.org (hallazgo del 19-10-2026, arreglado).

**Rendimiento de las capas** (14-10-2026, ver también "Rendimiento"): los glifos de los marcadores
van como imagen `data:` URI en una hoja de estilos (`.glifo-img[data-g]`, `ESTILO_GLIFOS`) en vez de
~380 SVG en línea con filtros; la ola del disco de río igual (`OLA_URI`); `lluviaAhora` y
`fenHistorico` dibujan en `L.canvas`; `rotuloBusqueda.js` guarda los puntos del trazo por largo
entero, reutiliza los rótulos previos tras un arrastre y espera 120 ms después de `moveend`; las
consultas que comparten varias partes pasan por `cached()` (`lib/consultaCache.js`): una sola
petición por clave mientras dure su TTL (un error no se queda cacheado).

## Avisos con ícono, pronóstico por localidad y nowcasting
**Forma = qué es el dato, color = qué tan fuerte, punteado = no es seguro.**
- **Aviso oficial:** el área sombreada más una **insignia**: disco blanco con aro del color del nivel
  (amarillo, naranja, rojo) y el glifo del fenómeno: gota, gota con rayo (solo si el aviso es de una
  región y SENAMHI afirma descargas), copo; en calor, frío y viento, termómetro o viento (así su
  amarillo no se confunde con el de la lluvia). Va en cada parte grande del aviso (`anclas`, calculadas
  en la BD). El popup (`lib/avisoTexto.js` + `map/popups.js`) dice "puede llover en algún momento en
  esta zona", los mm por subregión con barras (si SENAMHI los da y se leyeron enteros; si no, la cita
  literal), viento, rayos, granizo, nieve y el texto oficial sin cambios. En un punto con varios
  avisos, el popup los junta ("También rige aquí"). Desde zoom 13 el relleno del aviso amarillo
  (pane `aviso2`) baja al 12 % para que se lea la calle (`data-zoom-banda`).
- **Pronóstico por localidad:** disco blanco con el glifo del tiempo (nunca amarillo, naranja ni
  rojo); borde punteado si SENAMHI escribe "tendencia a". Sin fila no hay disco.
- **Nowcasting (experimental):** manchas azules y violeta con borde punteado; si SENAMHI no publica
  hace más de 30 min (lo decide la vista), no se muestran y el chip lo dice.

**Íconos.** `map/iconos.js` (puro) tiene los glifos (`GLIFOS`, `glifoSvg(nombre)`), su versión como
imagen (`glifoDataUri`, `ESTILO_GLIFOS`) y sus degradados (`DEFS_SVG`, ids `simpac-*`), que
`main.jsx` monta una vez con `montarDefsIconos()`. Los mismos glifos van en el mapa, la franja, los
popups y las leyendas (`components/Glifo.jsx`). Los botones y el panel siguen con Lucide.

**Escalas y acomodo.** `MapView` pone `data-escala` en el mapa: `pais` (zoom ≤ 6, todo como puntos),
`region` (7 y 8) y `local` (≥ 9); el CSS de `index.css` cambia los tamaños (también achica los
marcadores de las estaciones, `.mk`, a 62 % en `region` y 45 % en `pais`, para que no tapen avisos
y pronóstico; `acomodo.js` usa el mismo factor, `ESCALA_MK`; los discos de los ríos tienen sus
propios tamaños). `map/acomodo.js` corre
al mover o acercar el mapa y llama a `map/colocar.js` (puro): tu localidad siempre (aro negro y su
nombre); las insignias que se tocan se juntan en una con el chip "2 avisos"; una insignia tapada
prueba 8 lugares dentro de su zona (y si lo que tapa es tu disco y no le queda lugar, se pega a su
lado); los discos que chocan pasan a ser un punto de color; los nombres van a la derecha o a la
izquierda si caben (en `pais` solo el tuyo, en `region` los de tu departamento, en `local` todos).
Los discos de los ríos van antes que los del pronóstico (los de alerta o emergencia, siempre, después
de tu localidad). Los marcadores de las otras capas (estaciones, desbordes, reportes) cuentan como
fijos: un disco del pronóstico encima pasa a punto (debajo de ellos) y los nombres los esquivan. Una insignia cuya ancla queda fuera de la
pantalla (o bajo un panel) sigue a la vista mientras su zona se vea. Los chips y paneles marcados con
`data-tapa-mapa` cuentan como obstáculos (sus cajas se leen de nuevo solo si cambian, para no forzar
el diseño de la página en cada movimiento); con un popup abierto, en pantallas angostas los de
arriba se apartan. Al elegir una ciudad el mapa se corre hacia el punto de su localidad (a no más
de 1 km de él, `centroCiudad`) para que su disco se vea, sin cambiar el zoom.

**Popups en celular** (`map/popups.js`, `map/baseMap.js`): al abrirse, cada popup mide lo que de
verdad tapa el mapa en ese momento (la hoja, `data-tapa-mapa="abajo"`, y la atribución) y toma de ahí
su alto máximo (`max(140, min(480, libre - 50))`) y el relleno del `autoPan`; antes se calculaba con
un 45 % fijo y el popup quedaba bajo la hoja o con el título fuera de la pantalla. Un "Ver en el mapa"
de A dónde acudir abre el popup recién cuando el mapa termina de moverse.

**Día vinculado.** Avisos y pronóstico comparten la opción "Día" (`opciones.vinculo = "dia"`):
`DiaSelector` (Hoy / Mañana / el día de pasado mañana) arriba al centro desde `lg` y dentro de la hoja
(altura media) en pantallas más angostas. El nowcasting solo se ve con "Hoy"; con otro día,
`ChipNowcast` dice "elige Hoy".

**Franja de 3 días.** `FranjaPronostico` (en la hoja, altura media) es
el pronóstico de SENAMHI de tu localidad: la de la ciudad elegida (`cities.js`, campo `localidad`)
o, con GPS, la más cercana (hasta 10 km; de 10 a 30 km lo aclara; más lejos, lo dice y no muestra
días). Tocar un día muestra el texto de SENAMHI.

**Sin la base al día.** Si las vistas nuevas aún no existen (migraciones pendientes), la app sigue:
`getAvisosVigentes` pide las columnas de antes (una vez por sesión) y el mapa va sin insignias,
`getPronosticoVigente` y el nowcasting devuelven `null` (la capa dice que no se pudo cargar y la
franja no se muestra); `siExiste()` de `lib/consultaCache.js` traduce "la vista no existe"
(PGRST205 / 42P01) a `null`.

## Inicio: Tu zona ahora
Lo que se lee en 5 segundos al abrir la app (14-10-2026; ajustes de celular del 19/20-10-2026).

**Piezas y de dónde sale cada dato**
- `components/StatusPanel.jsx`: la **hoja inferior** con cuatro alturas (`ALTURAS`): `plegado`
  (semáforo, titular, instrucción en alerta o emergencia, fuente y hora, botón del nivel y teléfonos;
  ~200-280 px, el mapa queda a la vista), `vistazo` (+ chips de distancia, cómo activar el GPS y el
  pie), `media` (+ medidor del río, lluvia cerca de ti, A dónde acudir, franja de 3 días y el
  selector de día) y `completa` (+ "Qué dicen las fuentes hoy", El Niño, "Qué significa esto",
  Reportar, Ver alertas y la atribución literal de SENAMHI). En celular arranca **plegada**
  (`matchMedia (min-width: 1024px)`; medida el 20-10 a 375x812: 295 px, 36 % de la pantalla, sin
  scroll interno); desde `lg` es una tarjeta de 420 px abajo a la izquierda que arranca en `vistazo`
  (un pedido de `plegado` ahí vale `vistazo`). El asa se arrastra con Pointer Events (40 px cambian
  una altura; la hoja sigue al dedo con `transform`), los botones de flecha y las teclas arriba/abajo
  hacen lo mismo. `pedido` `{vez, altura, forzar, seccion}` desde `pages/Mapa.jsx` abre una altura
  (modo emergencia, botón del nivel); si la persona la movió a mano, un pedido sin `forzar` no la
  toca. La franja superior (`.hoja-franja`) es del color del nivel; en emergencia respira.
  `hooks/useAltoHoja.js` publica `--hoja-alto` en `<html>` (ResizeObserver) para que el zoom y la
  atribución de Leaflet suban sobre la hoja en celular (`index.css`, `.leaflet-bottom`). Limitación
  conocida: con la capa de nowcasting encendida el tope `max-lg:max-h-[min(66vh,calc(100vh-12rem))]`
  se aplica a `media` y `completa` por igual, así que en celular `completa` mide lo mismo que `media`
  (hallazgo del 19-10-2026, pendiente).
- `components/TuZona.jsx`: el **semáforo** (disco de 56 px, 64 desde `lg`, con ícono por nivel y
  etiqueta en mayúsculas: nunca solo color), el **titular** corto de dos líneas (`aria-live`), la
  instrucción única en alerta o emergencia, los chips "A 2 km del río Mashcón" (el número cuenta de 0
  al valor en 700 ms, `useContador`) y "Dentro/Fuera de la zona que podría inundarse", la línea de
  **fuente y hora** ("Desde el centro de Cajamarca · ríos ANA 00:49 · lluvia SENAMHI 00:49", en
  naranja si está desactualizado), el botón por nivel y, en alerta o emergencia, los botones
  `tel:105` y `tel:116` con el pie oficial (SISMATE, INDECI y Defensa Civil).
- `hooks/useZonaAhora.js`: junta `usePanorama` (`p`), `useRiosVigilados` (`rios`), el origen (GPS o
  centro de la ciudad), `rio_zona_mapa` (`getZonasRio`) y `caudal_actual` (`getCaudales`, la misma
  caché que el mapa), el titular de la BD (`getTitular`, tabla `titular_zona`, caché 5 min) y, desde el
  24-10-2026, los **ríos del país con trazo** (`getCaucesRios` + `getSenalesCauces`, la misma caché que
  la capa `rio`; `lib/zonaAhora.js riosTrazados` los empareja con `caudal_actual` y los avisos
  hidrológicos) y las zonas estimadas del río más cercano (`getCaucesZonas([rio_ana])`,
  `rio_cauce_zona_mapa`, solo para ese río). Devuelve `origen`, `porGps`, `nivel`, `titular`,
  `instruccion`, `chips`, `boton`, `fuentes`, `principal` (el vigilado que manda en el titular o, si
  no hay, el trazado a menos de 30 km: alimenta el medidor con la estación que manda), `cercano` (el
  río de los chips: vigilado del departamento o trazado), `verRio` (lo que recibe "Ver el río X en el
  mapa": para un trazado, la caja "tú y el cauce" a zoom 16, `rioParaVer`), `hayTrazadosDepto`,
  `caudal`, `zonas` y `resumenBd`.
- `lib/zonaAhora.js` (puro, 17 pruebas): `nivelMaximo(nivelLocal, rios)` (la zona de un río
  vigilado sube el semáforo aunque `alerta_actual` no lo cuente), `rioPrincipal` (nivel más alto; a
  igual nivel el más cercano), `riosTrazados`, `rioCercano` (entre vigilados y trazados), `rioEnDepto`,
  `rioParaVer`, `chipSinZonas`, `metrosAlCauce`, `puntoCercanoDelCauce`, `distancias`,
  `chipsDistancia` (con un río trazado: "A 820 m del río Rímac (trazo de ANA)", "Dentro/Fuera de la
  zona que podría inundarse (estimación SIMPAC con el relieve)" si tiene filas en `rio_cauce_zona_mapa`
  o "Este río no tiene mapa de zonas; la franja junto al cauce es solo referencial" si no; a más de
  30 km, "El río con trazo más cercano está a 34 km (Chicama)"; "Aquí SIMPAC no vigila ríos con mapa de
  zonas todavía" solo si el departamento no tiene ningún río con trazo ni vigilado; frases en
  `lib/lenguaje.js FRASES_RIO_PAIS`), `titularCorto`
  (prioridad: río vigilado en alerta/emergencia > `alerta_actual` en alerta/emergencia, con la causa
  leída por tipo: ríos de ANA que pasaron su nivel (`p.riosAqui`) o el aviso de SENAMHI del mismo
  nivel > aviso amarillo > lluvia medida ("ATENTOS") > ríos muy bajos según ANA ("RÍO MUY BAJO", sin
  instrucción ni teléfonos) > señales en la cuenca del río vigilado > calma con cobertura > sin
  cobertura; nunca verde sin datos; agrega "Puede haber cambiado." si `p.desactualizado` y "Último
  dato de ANA a las HH:MM" si ANA no respondió), `botonPrincipal` (A dónde acudir / Ver qué puede
  pasar / Ver mi zona en el mapa / Ver avisos del mapa), `lineaFuentes`, `cajaTuYRio`, `TONOS`,
  `TELEFONOS`, `PIE_OFICIAL`, `gpsVisto`/`marcarGpsVisto` (`localStorage` `simpac.gps`).
  `lib/nivel.js` trata `lluvia` y `nivel_bajo` como máximo `aviso` (`nivelEfectivo`) y expone
  `riosAqui` y `bajosAqui`: un río en vaciante ya no enciende el chip, la barra lateral ni el modo
  emergencia (Loreto, 19-10-2026). `lib/lenguaje.js ACCION_AVISO` es la instrucción cuando el nivel
  viene solo de un aviso de SENAMHI por lluvias.
- `components/MedidorCaudal.jsx` (altura media): arco de 180° con `lib/medidor.js escalaMedidor`
  (verde hasta el 80 % del nivel de alerta, ámbar hasta la alerta, naranja hasta la emergencia, rojo
  después; nivel bajo invertido; sin umbral, sin tramos; sin medición, gris), marcas "alerta N" y
  "emergencia N", progreso con `stroke-dashoffset` (900 ms), aguja, número que cuenta, frase y hora de
  `textoRio`/`lecturaRio` (en naranja si es de ayer o `p.desactualizado`). Datos: `caudal_actual`.
- `components/BarrasLluvia.jsx` (altura media; se monta recién al abrirla, así no pide nada al
  cargar): las 3 estaciones automáticas más cercanas a menos de 30 km con la lluvia de la última hora
  frente a la referencia de SENAMHI (`lluvia_senamhi_actual`) y la serie de 24 barras de la más
  cercana (`lectura_lluvia`, hoy solo Cajamarca; hueco = sin dato, no cero). `lib/serie24h.js`
  (`estacionesCercanas`, `serie24`, `resumenSerie`, `codDeEstacion`, `escalaBarras`).
- `components/AcudirCercanos.jsx` (altura media; en alerta o emergencia va primero): ver "A dónde
  acudir" más abajo. "Ver en el mapa" llama a `verPunto` (`pages/Mapa.jsx`): prende la capa `acudir` y
  encuadra tu punto y el destino (línea recta, no ruta).
- `components/OnboardingGps.jsx`: pantalla previa al permiso del GPS ("Mira cómo está tu zona"), una
  vez por navegador (`simpac.gps = "visto"`); `App.jsx` solo pide la ubicación al arrancar si
  `navigator.permissions` dice `granted`. En desarrollo `?bienvenida=1` la fuerza.

**Modo emergencia** (`pages/Mapa.jsx`): cuando `nivelMaximo(p.nivelLocal, rios)` pasa a alerta o
emergencia, una vez por cambio de nivel: pide la hoja plegada (forzado solo en emergencia), prende
`rio` y `zona` y encuadra el cauce del río principal (`verRio`); el chip de arriba
("EMERGENCIA EN CAJAMARCA") y la barra lateral heredan el nivel con fondo fuerte;
`<html data-nivel>` mantiene el pulso de tu ubicación y del río. Nunca se cierra solo: la
información no se borra por una fuente caída.

**Animaciones** (`index.css`, bloque `inicio-impacto`): tokens `--dur-rapida` 150 ms, `--dur-base`
280 ms, `--dur-dato` 900 ms, `--dur-barra` 500 ms, `--dur-vuelo` 800 ms, `--pulso` 1,8 s,
`--respiro` 1,6 s, `--ease-salida`, `--ease-dato`; clases `tz-normal|aviso|alerta|emergencia|sin_dato`
con `--nv` (relleno), `--nv-tinta` (texto sobre claro, contraste ≥ 4,5:1: #15803D, #A16207,
#C2410C, #B91C1C, #6B7280), `--nv-sobre` y `--nv-suave`. Reglas: solo `transform`, `opacity` y
`stroke-dashoffset`; pulsos de 3 ciclos salvo en alerta o emergencia; sin sonido ni vibración; con
`prefers-reduced-motion` todo queda en su estado final (las `--dur` pasan a 0 y `useContador`
muestra el valor final).

**Titular de la BD** (`titular_zona`, tarea `titular` del worker cada 30 min): es **opcional** y
solo reemplaza el **texto** del titular cuando está fresco (menos de 90 min desde `revisado_en`),
mide 110 caracteres o menos, coincide en `nivel` con el calculado aquí y el nivel no es alerta ni
emergencia (ahí manda la frase determinista con fuente y hora); el semáforo y la instrucción nunca
dependen de él. Si se usa, la tarjeta dice "Resumen del servidor de SIMPAC" o "redactado
automáticamente con las cifras oficiales" (`origen` `llm`). Desde el 20-10-2026 (integrado el 24-10)
`getTitular` pide también **`titular_corto`** (≤ 110, que el worker escribe desde la migración
`20261020040343`) y la tarjeta usa esa columna (hoy en Cajamarca: "Cajamarca: 3 avisos de SENAMHI por
lluvias (el más alto, amarillo)."); el `titular` largo (≤ 240) y el `detalle` van en la altura completa
("Qué dicen las fuentes hoy", una condición en `StatusPanel.jsx`). Antes se pedía solo `titular` (de
119 a 234 caracteres) y el texto de la BD nunca cabía en las dos líneas.

**Degradaciones**: sin `alerta_actual` el semáforo es gris ("SIN DATOS", "Consultando las alertas…"
o "No se pudo consultar las alertas. Revisa tu conexión." con Reintentar); sin GPS las distancias
van desde el centro de la ciudad y se ofrece "Usar mi ubicación"; sin ríos vigilados en el
departamento el chip lo dice y el botón lleva a los avisos; un río sin mapa de zonas lo dice; la
hora de ANA o de SENAMHI va en naranja cuando el worker lleva más de 3 h (ríos) o 1,5 h (lluvia) sin
correr. **Simulación** (solo `npm run dev`): `?simular=mashcon:15.4` (alerta), `:19` (emergencia),
`:hidro4`, `:lluvia`, `:calma` mueven también la tarjeta, el chip, la barra lateral y el medidor;
`?simular=rio:<rio_ana>:alerta` o `:emergencia` (p. ej. `rio:tumbes:alerta`; `lib/simulacion.js
simularCauce`) pone un río del país en ese nivel (la peor estación mide 5 % sobre su umbral o, sin
estación con umbrales, un aviso hidrológico falso) para ver la franja, el aura y la tarjeta;
`?simular=calma` a secas no simula nada. Verificado el 20-10-2026 en `:8080`: titular visible a los
468 ms desde el inicio de la navegación con los assets en caché (11 de las 19 consultas ya
respondidas); en la primera carga `titular_zona` responde a los 727 ms.

## Páginas
Todas usan `PanelPagina` (h1 con foco, botón volver en celular, X desde `lg`, pie con el
disclaimer "Información referencial y comunitaria; no reemplaza los canales oficiales de
emergencia (105 / 116)" en Alertas, Comunidad, Reportar y Chat), `EstadoCarga` para cargando /
vacío / error con Reintentar / "Entra para…", y `useApp()` (`components/ContextoApp.jsx`) para la
zona, la posición, el panorama, los ríos vigilados e `irAlMapa` / `verRioEnMapa`.

- **Alertas** (`/alertas`): pestañas **Vigentes** y **Pasadas**; chips "Mi zona (depto)" / "Todo el
  país"; selector de nivel (emergencia, alerta, aviso) y, en Vigentes, chips de tipo (Todo, Ríos,
  Avisos de SENAMHI, Lluvia medida). La lista sale de `alerta_actual` (la misma de `usePanorama`)
  con `lib/alertas.js prepararAlertas`: un aviso de SENAMHI que llega una fila por departamento se
  junta en una tarjeta con sus zonas; orden emergencia > alerta > aviso, las oficiales antes que la
  lluvia medida, después la más reciente. Vacío honesto con la hora de la última revisión de ríos y
  lluvia y el botón "Ver las N del resto del país". Sección **Avisos de SENAMHI vigentes**
  (`aviso_vigente`, `agruparAvisosVigentes`: una tarjeta por aviso con el nivel **máximo** de todas
  sus áreas y días, "Aviso naranja (nivel 3 de 4)", en curso / por empezar, días con su color si
  cambia, rige desde / hasta, departamentos que cubre, el texto oficial y el enlace exacto al aviso;
  antes se tomaba la primera fila y un aviso rojo salía amarillo, hallazgo del 19-10-2026). Sección
  **Ríos vigilados** (frase corta, hasta 3 señales, fuentes y "Ver en el mapa", que vuelve a `/` con
  el cauce encuadrado). **Pasadas**: tabla `alerta` (lectura pública) entre dos fechas de Perú (por
  defecto los últimos 7 días, nunca más de 30: `rangoPasadas` recorta y avisa) y una zona, hasta 500
  registros ("11 registros entre el 12/10/2026 y el 19/10/2026").
- **Comunidad** (`/comunidad`): reportes vigentes (`report`, hasta 500, caché 60 s, refresco cada
  2 min y botón) ordenados por `puntajeReporte` = confianza (la calcula la BD con los votos) menos
  la lejanía (criterio SIMPAC: 50 km restan tanto como bajar de 1 a 0 de confianza; a más de 100 km
  no se castiga más), desde el GPS o la ciudad elegida; `TarjetaReporte` con tipo e ícono, hace
  cuánto, distancia, estado según la comunidad, vence en, foto, `Votos` y "Ver en el mapa" (zoom
  16). Sin sesión se ve todo y aparece "Entra para reportar, votar y comentar".
- **Reportar** (`/comunidad/nuevo`): solo con sesión y con la **posición GPS real** (sin pin
  manual; el texto explica por qué si el permiso se niega). Tipo con `IconoReporte`, subtipo solo
  para atasco (leve / moderado / detenido), descripción opcional de hasta 500 letras, foto opcional
  (JPG, PNG o WebP, hasta 3 MB) que se reduce a 1280 px y JPEG antes de subir. `validarReporte`
  revisa todo antes de enviar (incluido que la posición caiga dentro del Perú, el mismo recuadro que
  el CHECK de `report.geom`); los errores de la BD se traducen (`mensajeErrorBD`: límite por hora,
  propio reporte, fuera del Perú, sesión vencida, permiso, foto grande o de otro tipo, sin red,
  reporte vencido). Al crear navega al detalle.
- **Detalle** (`/comunidad/:id`): valida que el id sea uuid; si la BD no lo entrega ("ya venció o
  no existe") no hay 4xx a la vista; tarjeta completa, votos y comentarios (hasta 200, "Vecino ·
  hace 8 min"); comentar pide sesión y reporte vigente (1 a 500 letras).
- **Chat** (`/chat`): canal = departamento de la persona (GPS o ciudad); solo con sesión (la RLS de
  `message` no entrega filas a `anon`). Mensajes vigentes (2 h, hasta 300) en tiempo real
  (`escucharMensajes`: `postgres_changes` INSERT con filtro `zona=eq.<depto>`, publicación
  `supabase_realtime`) más sondeo cada 10 s por si el canal se cae o para sacar los vencidos; "vence
  en" se refresca cada 30 s; Enter envía, Shift+Enter salta de línea; aviso local de groserías
  antes de enviar (lista corta en `lib/comunidad.js`, se puede "Enviar igual"); "Ocultar" guarda el
  id en `sessionStorage` `simpac.chat.ocultos`; "máximo 30 mensajes por hora" lo aplica la BD. Sin
  sesión: qué es el canal, "Entra para chatear" y los números 105 / 116.
- **Cuenta** (`/cuenta`): ver "Cuentas y sesión".
- **Histórico** (`/historico`): parámetros validados (`validarParametros`: tipo, id, rio, rango;
  sin ellos dice qué falta y cómo llegar desde el mapa); rangos 24 h / 7 días / 30 días; río:
  `lectura_caudal` por estación (y río) desde una fecha de Perú, por páginas, con los umbrales de
  `caudal_actual`; lluvia: `lectura_lluvia` por `cod` con mm por hora y temperatura; gráfico SVG
  propio (`GraficoSerie`, con texto resumen para lectores de pantalla), último / máximo / mínimo,
  tabla de las 120 lecturas más nuevas (botón para todas) y **CSV** (`;`, UTF-8 con BOM,
  `simpac_rio_mashcon_7d.csv`). Si no hay lecturas en el rango dice desde cuándo hay datos.
- **Navegación**: `Sidebar` (desde `md`) y `BarraInferior` (más angosto que `md`: 5 pestañas de
  56 px con `safe-area-inset-bottom`, contador de alertas en Alertas y el nombre de la persona en
  Cuenta) usan `NavLink` con `aria-current`. El botón flotante "Reportar" (desde `lg`) se retira
  mientras el panel de capas está abierto (tapaba el interruptor de Avisos de SENAMHI, hallazgo del
  19-10-2026). Un error de render en una página cae en `ErrorBoundary` ("Esta página no se pudo
  mostrar en este navegador") sin tumbar el mapa.

## Cuentas y sesión
Supabase Auth con correo y contraseña (`hooks/useSesion.js` + `lib/sesion.js`). Solo se piden correo,
contraseña (6 caracteres o más) y un nombre para mostrar (2 a 80 letras); nada más se guarda.
- `SesionProvider` escucha `onAuthStateChange`: `INITIAL_SESSION` apaga `cargando` (así ninguna
  página dice "entra para…" antes de tiempo), `PASSWORD_RECOVERY` enciende `recuperacion`,
  `SIGNED_OUT` limpia el perfil; el perfil se lee fuera del callback (`setTimeout`). Expone
  `usuario`, `perfil` `{id, nombre, reputacion, ciudad}`, `cargando`, `recuperacion`, `nombre`,
  `conSesion`, `recargarPerfil` y `terminarRecuperacion`.
- `lib/sesion.js`: `entrar`, `registrar` (`signUp` con `options.data.nombre`, que el trigger
  `crear_perfil` copia al perfil, y `emailRedirectTo = <origen>/cuenta`), `salir`,
  `pedirNuevaContrasena` (`resetPasswordForEmail` con `redirectTo = <origen>/cuenta`),
  `cambiarContrasena`, `leerPerfil` (traduce `perfil.zona`, un punto en EWKB hex, a la ciudad más
  cercana de `data/cities.js` con `puntoDeWkb`), `guardarZona`, `guardarNombre`, `misReportes`
  (`rpc("mis_reportes")`) y la zona local `simpac.zona` en `localStorage`. Todas devuelven
  `{ ok, error }` con el error ya en lenguaje claro (`mensajeAuth`: credenciales, correo sin
  confirmar, cuenta existente, contraseña corta, límite de correos, enlace vencido, sin red).
- **Confirmación por correo** activa: al crear la cuenta no hay sesión hasta abrir el enlace
  ("Revisa tu correo"). Si el correo ya existía, Supabase devuelve un usuario sin identidades (no
  revela cuentas): la web avisa igual, con la pista de entrar o pedir una contraseña nueva. El enlace
  de confirmación y el de "olvidé mi contraseña" vuelven a `/cuenta`; el segundo llega con
  `PASSWORD_RECOVERY` y Cuenta muestra el formulario de contraseña nueva. **Pendiente**: registrar
  cada origen (`http://localhost:5173/cuenta`, `http://localhost:8080/cuenta`, el dominio real y la
  app) en Supabase Auth > URL Configuration > Redirect URLs; dentro de la app Android el enlace del
  correo abre en el navegador del teléfono (la app vive en `https://localhost`), falta probar ese
  recorrido.
- **Cuenta con sesión**: nombre editable, correo, reputación (suma de votos recibidos, la calcula la
  BD), **Mi zona** (la ciudad con la que arrancan el mapa, las alertas y el chat sin GPS: se guarda
  como punto en `perfil.zona` y en `localStorage`; `App.jsx` la aplica una vez al llegar el perfil
  si este navegador no tenía ciudad elegida ni GPS), **Mis reportes** (vigentes y vencidos, con
  estado y votos) y cerrar sesión. Formularios con `label`, `autocomplete`, `aria-invalid` y
  `aria-describedby`.
- **Capas recordadas con sesión**: `useLayerVisibility` guarda en `preferencia_mapa` (`upsert` por
  usuario) 1,5 s después del último cambio hecho por la persona; al entrar (`SIGNED_IN` o
  `INITIAL_SESSION`) lee la fila y aplica la copia más reciente entre el navegador y la cuenta
  (`masReciente` por `guardado`: un celular nuevo sin cambios no pisa la cuenta). El pie del panel de
  capas dice dónde se guardan (`dondeGuarda`: `cuenta`, `navegador` o `null` si el navegador no deja).
- Textos fijos en `lib/comunidad.js`: `POR_QUE_CUENTA` ("Para consultar no hace falta cuenta. Solo
  se pide para reportar, votar, comentar y chatear."), `DISCLAIMER`, `AVISO_REPORTE`, `NORMAS_CHAT`.
  El subtítulo "SIFEC · Sistema Inteligente de Acceso a Información del Fenómeno El Niño" va en la
  barra lateral y en Cuenta (`SUBTITULO_SIFEC`); la web se llama SIMPAC.

## Ríos vigilados: el río resaltado, la zona que podría afectar y los desbordes pasados
Primero el **Mashcón** (Cajamarca); los datos se cargan una vez con `backend/mapas/cargar_rios.py`
(vistas `rio_vigilado_mapa`, `rio_zona_mapa`, `rio_senal` y tabla `rio_incidente`). Sin esas vistas
(migración pendiente) la app sigue igual: `getRiosVigilados` devuelve `null` (un solo pedido fallido
por hora; las otras tres se piden a la vez que ella, no después, y la bandera `sinRios` evita
insistir), la capa de zonas dice "aún no están cargadas" y el panel no nombra ríos.
- **El río:** halo blanco, cauce azul si su estación de ANA está tranquila (si no, el color de su
  estado o, si es más alto, el del aviso hidrológico de SENAMHI: `estadoCauce`), afluentes finos y
  "Río Mashcón" escrito sobre la línea desde zoom 13 (`map/rotuloLinea.js`: fuera de chips y paneles
  y en tramos sin quiebres cerrados). Grosores por banda de zoom (`MapView` pone `data-zoom-banda`: z10
  hasta el zoom 11, z12, z13, z14 de 14 a 15, z16). La faja marginal de ANA, punteada, desde zoom 14
  (pane `rioFaja`, entre el halo y el cauce: casi toda cae dentro del ancho del halo).
- **Discos de río:** blancos con aro del color del estado, 40 px a escala local (30 en región, punto
  de 14 en país) y rótulo «Mashcón · Tranquilo 0.13 m³/s» (la medida solo a escala local). En alerta
  o emergencia el aro late (quieto con `prefers-reduced-motion`), el rótulo va en una pastilla de color
  y siempre se ven. Con aviso hidrológico de SENAMHI más alto que lo que mide ANA, el disco toma el
  color del aviso: «Mashcón · Aviso rojo SENAMHI  ANA: 0.13 m³/s». Un aviso hidrológico es de **una**
  estación (su título la nombra: "… - ESTACIÓN SAN REGIS"): el disco y el rótulo de una estación solo
  dicen "Aviso" si el aviso es de esa misma estación (`lib/zonaRio.js estacionDeAviso`,
  `avisoEsDeEstacion`); antes el aviso de San Regis teñía 13 estaciones del Marañón y el Huallaga
  (hallazgo del 19-10-2026). Los acomoda `colocar.js` (tipo
  `rio`): antes que los discos del pronóstico; una insignia de aviso encima lo deja como punto, un
  marcador de otra capa no. El de un río vigilado tiene más prioridad (más aún con señales en su zona)
  y, si lo tapa otro disco, se pega a su lado; su rótulo prueba a la derecha, a la izquierda, arriba y
  abajo. El popup de cada estación enlaza a `/historico` ("Ver histórico").
- **La zona** (siempre la de **hoy**, no sigue el selector de día; nunca se relacionan m³/s con su
  extensión). Su nivel es el más alto de sus señales (`lib/zonaRio.js`, `estadoZona`):

| Nivel | Cuándo | Color |
|---|---|---|
| Emergencia | ANA mide el río sobre su nivel de emergencia (de crecida) o SENAMHI tiene un aviso hidrológico **rojo** vigente de su estación | rojo |
| Alerta | ANA, sobre su nivel de alerta, o aviso hidrológico **naranja** | naranja |
| Atentos | el río al 80 % de su caudal de alerta (criterio SIMPAC), aviso hidrológico **amarillo**, aviso de lluvia **naranja o rojo** en curso que toca la cuenca, o una estación de la cuenca que pasó la referencia de SENAMHI | ámbar |
| Sin señales | nada de lo anterior | azul (sigue siendo una zona que podría inundarse) |

  Solo lo que trata del río mismo (ANA o el aviso hidrológico) sube a naranja o rojo. Un río muy bajo
  (vaciante) y un aviso hidrológico de descenso, indeterminado o vencido no cuentan (el `sentido` lo
  decide el conector del backend desde el título y la leyenda del aviso; el 20-10-2026 los 9 avisos
  vigentes, incluidos los "SITUACIÓN ACTUAL DEL NIVEL…", son de descenso); un aviso amarillo de
  lluvia, uno naranja de mañana y un aviso hidrológico de crecida que SENAMHI publica sin nivel
  (`hidro_sin_nivel`) se mencionan en el popup sin subir el nivel. Con SENAMHI caído, la vista sigue
  dando un aviso hidrológico con fin conocido hasta ese fin; si su `visto_en` pasa de 3 h, el popup
  dice que la web de SENAMHI no responde desde esa hora y que es su último aviso conocido
  (`hidro_viejo`).
  Rayada = estimación de SIMPAC con el relieve; lisa = estudio INDECI-PNUD 2005 (ninguna es un mapa
  oficial vigente). Todas con borde blanco y trazo oscuro (ámbar, naranja y rojo son también los
  rellenos de las áreas de los avisos). Desde zoom 13 los polígonos (en zoom 13, con el aura suave
  debajo) y desde zoom 14 «zona que podría inundarse» escrito junto al río donde cabe; si hay
  señales, un "aura" del color del nivel a lo largo del río hasta zoom 13 (se ve con el mapa alejado;
  desde zoom 14 ya no). Con aviso hidrológico (o el río en alerta o emergencia) se marcan los centros
  poblados que SENAMHI nombra en sus avisos. El aviso hidrológico **no** suma al contador
  de alertas. En el popup de una zona, «Pasó antes en el río» lista primero los desbordes más cercanos
  a ella («Cerca de aquí», a menos de 1 km; si no, «En otros tramos del río», con la distancia).
- **Desbordes pasados:** con cada zoom se juntan en un rombo «×n» los que en pantalla quedarían
  encimados (`agruparIncidentes` con el radio de un rombo); el acomodo (`colocar.js`, tipo `rombo`)
  corre el que quedaría bajo el disco de un río, una insignia u otro rombo, con una línea fina hasta su
  punto real: un rombo nunca se oculta.
- **En la hoja y en Alertas:** una línea por río de tu zona con señales («Río Mashcón: tranquilo,
  pero hay aviso de SENAMHI por lluvia fuerte sobre su cuenca. Mira la zona que podría afectar.»; si
  la señal es lluvia medida, «…pero llovió fuerte en su cuenca») y el botón «Ver en el mapa», que
  pliega la hoja, prende las capas del río y de la zona y encuadra el cauce en lo que queda libre
  entre los chips de arriba y la hoja (hasta zoom 14).
- **Simulación (solo `npm run dev`):** `?simular=mashcon:15.4` (caudal de ANA), `mashcon:hidro2` a
  `hidro4` (aviso hidrológico falso), `mashcon:lluvia` (RIO GRANDE GORE con 7,2 mm) o `mashcon:calma`
  (sin señales en la cuenca); varias con coma.
  La nota de la capa dice «SIMULACIÓN (solo desarrollo)». En la compilación de producción no existe.

### Ríos del país
Desde el 14-10-2026 la capa `rio` (y su aura en `zona`) resalta también los ríos del país con
estación de caudal de ANA o aviso hidrológico de SENAMHI, con el trazo de **ANA - GeoSNIRH** (red
hidrográfica R.J. 056-2018-ANA o Carta Nacional del IGN) que carga `backend/mapas/cargar_cauces.py`
en `rio_cauce` (100 ríos; vistas `rio_cauce_mapa` y `rio_cauce_senal`). La lógica es
`lib/cauces.js` (puro, 16 pruebas): emparejar cada trazo con sus filas de `caudal_actual` (mismo río
y estación en la lista, sin tildes), estado del río, detalle por zoom, filtro por la caja de la vista,
tramo visible más largo para el nombre, elección de rótulos y, desde el 24-10-2026, qué ríos piden
zonas (`riosParaZonas`, `ZONAS_DESDE = 12`), el ancho de la franja (`anchoFranja`), cuándo se dibuja
(`conFranja`), `zonasDeCauce` y la nota `notaZonasPais`. Reglas:
1. Cada río con estación de ANA se resalta igual que el Mashcón: halo blanco y cauce del color de la
   **peor** de sus estaciones de crecida (un umbral de nivel bajo cuenta como tranquilo); si hay un
   aviso hidrológico vigente de **crecida** más alto, el color del aviso (`estadoRio`, misma regla que
   `estadoCauce`). Popup con el nombre, el estado en palabras o el aviso, los niveles y la medición
   de ANA con su hora, cuántas estaciones tiene y cuál manda, y "SIMPAC resalta el cauce con el trazo
   de <fuente> (<licencia>); el nivel es de la estación X de ANA".
2. El Mashcón nunca se duplica (`rio_vigilado` manda; `vigilado` en la vista) y un río sin trazo no
   se inventa: queda su disco y la nota de la capa cuenta cuántas estaciones están sin trazo
   (Titicaca, Canopampa, Sumbay, Chunchuca el 14-10-2026).
3. Un río que solo tiene aviso de SENAMHI (sin estación de ANA: Biabo, Pampas…) se resalta solo
   mientras tenga un aviso vigente. El 14-10 se dibujaban 92 ríos (100 menos los 8 solo con aviso).
4. En vista país (zoom ≤ 6, `[data-escala="pais"]`) los ríos sin alerta van en gris fino sin halo y
   solo los de alerta o emergencia conservan color; en zoom 7-8 todos más finos.
5. Nombres sobre la línea desde zoom 10, solo para los ríos a la vista, hasta 8 a la vez (primero
   alerta/emergencia, después el tramo visible más largo), sobre el tramo visible simplificado a 6 px
   (`L.LineUtil.simplify`) y no sobre los 1700 km del Marañón; no se rehacen si tras un arrastre el
   tramo rotulado sigue cubriendo lo visible.
6. En alerta o emergencia la capa `zona` dibuja el aura del nivel a lo largo del trazo (a todo zoom,
   sin polígonos: marca el río a vigilar, no hasta dónde llega el agua) en vez del círculo de 2,5 km,
   que queda solo para estaciones sin trazo. Un río muy bajo no enciende nada.
7. Rendimiento: las geometrías no viajan con los datos de la capa (`GEOMETRIAS` en `lib/cauces.js`,
   `aligerar()`; la huella JSON de `MapView` sigue bajo 400 KB: 145 KB medidos), `cauce_lejos`
   (~50 m, 729 KB para los 100 ríos) llega de una vez con 60 min de caché, el trazo fino se pide por
   río solo a la vista desde zoom 13 (`getCauceRio`, por sesión) y se suelta al alejarse;
   `rio_cauce_senal` solo trae `rio_ana` y `avisos_hidro` (5 min).
8. **Zonas estimadas con el relieve** (24-10-2026; `map/layers/zonasRio.js`): la capa "Zonas que un
   río podría afectar" pide a `rio_cauce_zona_mapa` las zonas de los ríos cuya caja toca la vista (con
   20 % de margen) desde zoom 12 (`getCaucesZonas(rioAnas)`, `rio_ana=in.(...)`, una consulta por río,
   caché 60 min, nunca el país entero; `null` si la vista no existe) y las dibuja desde zoom 13 con los
   mismos estilos del Mashcón: `bajo_2m` rayada, `bajo_3m` lisa y tenue, borde blanco, color por
   `estadoRio` (azul sin señales). Popup en lenguaje claro con el método, la fuente, la licencia y
   "Estimación de SIMPAC con el relieve; no es un mapa oficial." (`FRASES_RIO_PAIS.metodo`); nunca
   metros. Hoy 20 ríos tienen zonas (`backend/mapas/zonas_relieve.py`, `README-tecnico.md` §5.6.11); un
   río sin filas no dibuja nada y la nota de la capa (`notaZonasPais`, actualizada en vivo con
   `avisar`) dice cuántos ríos a la vista tienen zonas y cuántos franja.
9. **Franja de atención** (24-10-2026): solo con el río en **alerta o emergencia**, `getFranjaRio(rioAna)`
   pide `rio_cauce_mapa` (`select=rio_ana,ancho_m,franja&rio_ana=eq.X`, caché 60 min) y la capa dibuja la
   banda de `ancho_m` a cada lado del trazo (60 / 120 / 250 m según el largo del río) con contorno
   punteado y relleno al 10 % del color del nivel, desde zoom 13 (`.zona-franja` se oculta en z10/z12; en
   z13 el aura del río lleva `.con-franja` y se oculta; con el mapa más lejos sigue el aura). Popup propio
   (`FRASES_RIO_PAIS.franjaPopup`) y leyenda "Franja de atención junto al río (referencial, no es un mapa
   de inundación)" (forma `franja` en `LayersPanel`). Verificada el 20/24-10 solo con la simulación
   `?simular=rio:tumbes:alerta` (ningún río del país estaba en alerta o emergencia por crecida).
10. **La tarjeta "Tu zona ahora"** elige el río más cercano entre los vigilados del departamento y los
   ríos trazados (`lib/zonaAhora.js riosTrazados`, `rioCercano`): chips de distancia con "(trazo de
   ANA)", Dentro/Fuera con "(estimación SIMPAC con el relieve)" si el río tiene zonas, "Ver el río X en
   el mapa" que encuadra a la persona y el tramo más cercano del cauce a zoom 16 (`rioParaVer`, no los
   1700 km del Marañón). Verificado el 24-10 en `:8080`: Lima "A 820 m del río Rímac (trazo de ANA)" y
   "Fuera de la zona que podría inundarse, a 680 m"; Tumbes "A 1.1 km del río Tumbes"; Iquitos "A 1.9 km
   del río Itaya" + "Este río no tiene mapa de zonas"; Piura, Trujillo y Chiclayo "El río con trazo más
   cercano está a 31-34 km" (el Piura no tiene estación emparejada, falta un alias; Moche y Reque no
   tienen trazo). Medido el 20-10: zonas por río 320-850 ms (vista vacía), trazo fino 240-580 ms,
   franja de 4 ríos ~140 ms en la BD.

## A dónde acudir
Tarjeta (`components/AcudirCercanos.jsx`) y capa (`map/layers/acudir.js`) sobre la tabla
`punto_acudir` (cargador `backend/mapas/cargar_acudir.py`: 12 915 puntos el 14-10-2026; Cajamarca
región 1126). `lib/acudir.js` (puro, 8 pruebas): `getPuntosAcudir({lat, lon, radioKm = 30})` pide
por caja (nunca la tabla entera) y devuelve los puntos con `distancia_m`; `masCercanos` elige el
mejor de salud (hospital 24 h si está a menos de 15 km; si no, el establecimiento más cercano), la
comisaría y los bomberos más cercanos; `textoDistancia` ("a 850 m", "a 2,3 km"), `telefonos`,
`telHref`, `enlacesComoLlegar` (Google Maps `dir` y `geo:` en Android), `notaFuente` (comisarías:
padrón MININTER 2019 vía CENEPRED, puede haber cambios) y `ZONA_SEGURA` (recomendación general de
INDECI con la URL de su campaña; la zona segura oficial la define la municipalidad). La tarjeta
muestra "Si hay emergencia: 105 Policía · 116 Bomberos · 106 SAMU" con `tel:`
(`data/emergencias.js`, con la salvedad de que gob.pe no lista a Cajamarca entre las regiones con
SAMU), las 3 tarjetas con distancia en línea recta, dirección, teléfono ("Sin teléfono en la fuente"
si no hay), "24 h" solo si `atiende_24h = true`, y "Ver en el mapa" (evento `simpac:acudir-ver`
para abrir el popup del punto); sin posición solo los números. Verificado contra la BD el
19-10-2026 desde el centro de Cajamarca: Hospital II Cajamarca 24 h a 450 m, Comisaría Central a
170 m, Bomberos N° 59 a 450 m. No hay albergues ni zonas seguras: ninguna fuente oficial abierta los
publica georreferenciados (los tipos quedan previstos en la tabla y la leyenda no los muestra).

## Capas recordadas
`hooks/useLayerVisibility.js` + `lib/preferencias.js` (puro, con 15 pruebas). Se guardan en
`localStorage`, clave `simpac.mapa`: `{v: 1, capas, opciones, dia, conocidas, guardado}`.
- Solo se guarda lo distinto de lo de siempre: una capa que la persona nunca tocó sigue el
  `defaultVisible` del código (si el equipo cambia un defecto, le llega).
- El día de avisos y pronóstico vale solo esa fecha de Perú (al día siguiente vuelve a "Hoy").
- Una capa nueva arranca con su defecto y lleva el chip «Nueva» hasta que se cierra el panel de capas;
  una capa que ya no existe se ignora (si cambia de id, `RENOMBRADAS`); una versión desconocida o un
  dato roto vuelven a los valores de siempre.
- Sin `localStorage` (ventana privada, datos del sitio bloqueados: leerlo ya lanza) el mapa arranca con
  los valores de siempre y el pie del panel lo dice. Si otra pestaña cambia las capas, esta la sigue
  (evento `storage`).
- Pie del panel: «Tus capas se guardan en este navegador.» (o «en tu cuenta») y, si algo cambió,
  «Restablecer capas» (también vuelve a lo de siempre en la cuenta).
- Con sesión de Supabase Auth también en la tabla `preferencia_mapa` (RLS: cada quien la suya; gana la
  copia guardada más tarde, y un celular nuevo sin cambios no pisa la cuenta). El inicio de sesión
  está en `/cuenta` (ver "Cuentas y sesión").

## El Niño en gráficos
El botón "Ver gráficos" de la hoja (altura completa) y el de la barra lateral abren `ElNinoPanel`
(la barra lateral navega a `/` con `state.elNino` si estaba en otra ruta): en qué
paso está el Sistema de Alerta del ENFEN (sin alerta, vigilancia, alerta), el ICEN mes a mes de
los últimos 24 meses coloreado por categoría (tabla `icen_serie`; el estimado `ICEN_TMP` va
punteado) y botones que prenden en el mapa la lluvia de otros El Niño. Es un diálogo modal: Escape
lo cierra y devuelve el foco al botón.

**Seguridad:** todo texto que va a un popup pasa por `popupHtml()`, que escapa el HTML. Los
reportes los escriben usuarios: nunca armar HTML con `${...}` a mano. Los enlaces externos de los
popups pasan por `enlaceSeguro` (solo `https:`).

## Lenguaje claro

La app la usa cualquier persona, no un meteorólogo. Todo texto sale de `src/lib/lenguaje.js` (un
solo diccionario: lo mismo se dice igual en la hoja, la barra lateral, las páginas y los popups).
Cada dato va en tres capas: qué pasa (una frase), qué significa o qué hacer, y el número con su mes
y su fuente en chico. Primero la zona del usuario (departamento de la ciudad elegida o del GPS) y
después el país. Nunca se dice "todo normal" a secas: solo lo que SIMPAC mide.

| Dato | Regla | Fuente |
|---|---|---|
| Estado ENFEN | Vigilancia / Alerta / Sin alerta, con número y fecha del comunicado | Comunicado oficial ENFEN |
| Mar frente al Perú (ICEN) | neutra -0.7..+0.5 · débil..+1.3 · moderada..+2.1 · fuerte..+3.5 · extraordinaria | Nota Técnica ENFEN 01-2024 |
| Pacífico central (RONI) | El Niño/La Niña si \|x\| ≥ 0.5; débil, moderado, fuerte, muy fuerte cada 0.5 | NOAA CPC (desde feb-2026) |
| Ríos (caudal m³/s) | % del caudal que activa la alerta; "atento" desde el 80 % | ANA; "atento" es criterio SIMPAC |
| Ríos (nivel en m) | cuánto falta para el nivel de alerta; "atento" a 0.5 m | ANA; "atento" es criterio SIMPAC |
| Ríos con nivel bajo | si UEMERGENCIA < UALERTA el peligro es que baje (vaciante); en el semáforo vale como máximo `aviso` ("Río muy bajo") | ANA |
| Lluvia por hora (intensidad) | ligera ≤2 · moderada ≤15 · fuerte ≤30 · muy fuerte ≤60 · torrencial | AEMET (referencia); solo para el color y el tamaño del punto en el mapa, no para las alertas |
| Lluvia sobre la referencia | pasa si `pp_1h > umbral_1h` o `pp_6h > umbral_6h` (mayor estricto; solo si la estación trae `pp_1h` y `umbral_1h > 0`). Nivel siempre `aviso`, con el rótulo "Atentos a la lluvia"; siempre "no es un aviso oficial" | Referencia de SENAMHI por estación (capa `g_umbrales`). `referenciaLluvia` (`lenguaje.js`) es la misma regla que `backend/alerts.py` |
| Lluvia del mes | clases oficiales ±15/±30/±60 %; si lo normal es < 10 mm se habla en mm | SENAMHI; lo de 10 mm es criterio SIMPAC |
| Instrucción en alerta o emergencia | una sola frase: la del río (`textoRio(c).accion`, `fraseCorta`) o, si el nivel viene solo de un aviso de SENAMHI por lluvias, `ACCION_AVISO` | textos fijos de SIMPAC (`lenguaje.js`, `zonaRio.js`); el aviso oficial es el de SENAMHI, INDECI y Defensa Civil |

## Qué tabla alimenta cada parte

| UI | Tabla / consulta | Notas |
|---|---|---|
| Tu zona ahora (semáforo, titular, chips) | `alerta_actual` (vía `usePanorama`), `rio_vigilado_mapa` + `rio_senal` (vía `useRiosVigilados`), `rio_zona_mapa`, `caudal_actual`, `rio_cauce_mapa` + `rio_cauce_senal` (los ríos del país, misma caché que la capa `rio`), `rio_cauce_zona_mapa` solo del río más cercano, y opcional `titular_zona` (`departamento,titular,titular_corto,detalle,nivel,generado_en,revisado_en,origen` where `departamento = …`) | el nivel y la instrucción se calculan en el cliente; `titular_corto` de la BD solo si está fresco (90 min), cabe (110) y coincide en nivel (ver "Inicio"); caché 5 min; `null` si la tabla no existe |
| Zonas estimadas de los ríos del país | `rio_cauce_zona_mapa` (`clave,rio_ana,subtipo,area_km2,metodo,fuente,licencia,atribucion,nota,geojson` con `rio_ana=in.(...)`) | una consulta por río a la vista desde zoom 12 (`getCaucesZonas`), caché 60 min por río; `null` si la vista no existe; nunca el país entero |
| Franja de atención de un río del país | `rio_cauce_mapa` (`rio_ana,ancho_m,franja` where `rio_ana = …`) | solo con el río en alerta o emergencia (`getFranjaRio`), caché 60 min; PostgREST calcula la columna al vuelo |
| Medidor del río | `caudal_actual` (fila del río principal) | misma caché que el mapa |
| Lluvia cerca de ti | `lluvia_senamhi_actual` + `lectura_lluvia` (`cod,medido_en,precip_mm,estacion!inner(nombre,departamento)` del depto, 24 h) | se pide al abrir la altura media |
| A dónde acudir (tarjeta y capa) | `punto_acudir` (`COLUMNAS_ACUDIR`: `clave,tipo,nombre,categoria,atiende_24h,direccion,distrito,provincia,departamento,telefono,lat,lon,fuente,fuente_url,atribucion,actualizado,detalle`) por caja `.gte/.lte` de lat/lon | nunca `select("*")` ni la tabla entera; caja redondeada a 0,1 grados; por páginas de 1000; caché 60 min |
| Franja de 3 días | `pronostico_vigente` (`codigo,nombre,departamento,lat,lon,fecha,emision,tmax,tmin,texto,tipo,posible,por,lluvia_segura,granizo,intensidad,momento,cielo,url`) | por páginas de 1000, en caché 10 min; la comparte con la capa del mapa y el "cerca de" del nowcasting |
| Chip del nowcasting | `nowcast_estado` (`vigente`, `vence_en`) y `nowcast_vigente` | en caché 60 s; el umbral de 30 min vive en la vista, no en el cliente |
| Estado, titular y contador | vista `alerta_actual` (las vigentes; la lluvia medida, solo con 3 h o menos) | tipos `caudal`, `nivel_bajo`, `aviso` (SENAMHI: amarillo = `aviso`, naranja = `alerta`, rojo = `emergencia`) y `lluvia` (una estación que pasó la referencia de SENAMHI: siempre `aviso`, `valor` y `umbral` de la ventana `ventana_h`, 1 o 6 h, y `detalle` listo para mostrar); `zona` = departamento. El contador y el color de la métrica "alertas y avisos" son solo de lo oficial: la lluvia no cuenta; `nivel_bajo` vale como máximo `aviso` para el semáforo |
| Página Alertas (Vigentes) | `alerta_actual` (la misma) + `aviso_vigente` (agrupada por aviso con nivel máximo) + ríos vigilados | ver "Páginas" |
| Página Alertas (Pasadas) | tabla `alerta` (`id,tipo,referencia,zona,nivel,detalle,valor,umbral,ventana_h,vigente,ts` entre dos fechas de Perú, `zona` opcional, hasta 500) | sin lat/lon; máximo 30 días |
| El Niño costero | `comunicado_enfen` (el más reciente) | lo llena la tarea `enfen` del worker (el 20-10-2026, CO 18-2026 del 16 de octubre) |
| Mar y Pacífico | `indice` | `ICEN` (+ `ICEN_TMP`) con su `origen`, y `RONI` |
| Gráfico del ICEN | `icen_serie` (`mes,valor,categoria,origen`) | IGP y tabla del Informe Técnico ENFEN (el ENFEN manda) |
| Cobertura de lluvia | `lluvia_senamhi_actual` + `latido` (`servicio = 'lluvia_nacional'`) | estaciones del departamento con lluvia de la hora y referencia (`referenciaLluvia(e).evaluable`). "Ninguna pasa la referencia" solo si el latido trae `alertas` no nulo (la última corrida evaluó) y la consulta respondió; si no, "No se pudo revisar la lluvia…". La frase del resto del país lo dice solo si hay estaciones evaluables fuera de la zona (`cobertura.lluviaFuera`) |
| "ríos ANA HH:MM · lluvia SENAMHI HH:MM" | `latido` (`servicio = 'ingesta'` y `'lluvia_nacional'`) | "sin actualizar desde" si pasan 3 h (ríos) o 1.5 h (lluvia). Si `lluvia_nacional` trae la falla `umbrales`, se avisa que la lluvia de la última hora puede estar atrasada |
| Ríos | `caudal_actual` | **no** `lectura_caudal`: esa es el historial (repite estaciones) |
| Ríos vigilados (trazo, rótulo, lugares) | `rio_vigilado_mapa` (`id,nombre,departamento,estacion_ana,rio_ana,estacion_senamhi,centro_lat,centro_lon,zoom,cauce,afluentes,guia_rotulo,lugares_aviso,fuentes`) | GeoJSON listo; caché 60 min; se empareja con `caudal_actual` por estación y río (sin tildes) |
| Ríos del país (trazo) | `rio_cauce_mapa` (`rio_ana,rio,nombre,departamento,estaciones,estaciones_senamhi,capa,km,dist_estacion_m,nota,fuente,fuente_url,licencia,atribucion,fecha_fuente,vigilado,cauce_lejos`; y `cauce` por `rio_ana` desde zoom 13) | `cauce_lejos` de una vez (caché 60 min); `cauce` por río y por sesión; `null` si la vista no existe |
| Ríos del país (avisos) | `rio_cauce_senal` (`rio_ana,avisos_hidro`) | las lecturas de ANA ya vienen en `caudal_actual`; caché 5 min; el nivel lo decide `lib/cauces.js estadoRio` |
| Zonas y faja marginal | `rio_zona_mapa` (`clave,rio,tipo,subtipo,orden,nombre,texto,fuente,fuente_url,licencia,atribucion,metodo,fecha_fuente,area_km2,geojson`) | ordenadas por `orden`; caché 60 min |
| Señales de la zona | `rio_senal` (`rio,avisos_lluvia,lluvia_cuenca,avisos_hidro`) | las cruza la BD con la cuenca; caché 5 min; el nivel lo decide `lib/zonaRio.js` |
| Desbordes pasados | `rio_incidente` (`fecha desc nulls last`) | solo los que nombran al río en su fuente; caché 60 min |
| Capas recordadas (con sesión) | `preferencia_mapa` (`usuario,version,datos`) | RLS por usuario; sin sesión, solo `localStorage` |
| Histórico de un río | `lectura_caudal` (`fecha,hora,valor,unidad,umbral_alerta,umbral_emergencia,tendencia,estado` where `estacion = …` [and `rio = …`] and `fecha >= …`), por páginas; umbrales de `caudal_actual` | la primera lectura guardada para decir "hay datos desde…" |
| Histórico de lluvia | `lectura_lluvia` (`ts,medido_en,precip_mm,temp_c` where `cod = …` and `medido_en >= …`) + `estacion` para el nombre | ordenar por `medido_en` (ya en hora correcta) |
| Mapas FEN históricos | `mapa` con `variable = 'FEN'` (`titulo,periodo,trimestre,meses,fuente,geojson`) | se pide el `geojson` del evento y trimestre elegidos (`periodo` + `trimestre`, `getMapaFEN("1997-1998\|DEF")`); solo trae la propiedad `RANGO` (mm frente a lo normal) |
| Comunidad (lista y detalle) | `report` (`id,tipo,subtipo,descripcion,foto_url,likes,dislikes,confianza,estado,creado_en,expira_en,lat,lon`, hasta 500), `voto` (`report_id,valor` de los propios), `comentario` (`id,report_id,texto,creado_en`, hasta 200) | la capa del mapa pide `report` sin `foto_url` ni `confianza` |
| Chat | `message` (`id,autor,zona,contenido,expira_en,creado_en` where `zona = depto` and `expira_en > now`, hasta 300) + canal realtime `postgres_changes` | solo con sesión |
| Cuenta | `perfil` (`id,nombre,reputacion,zona`) y `rpc mis_reportes` | `zona` llega como EWKB hex; `mis_reportes` es la única forma de ver los propios (`autor` no es legible) |

> **Coordenadas:** usa las columnas `lat` / `lon` (vienen listas). `geom` es PostGIS y el Data API
> la devuelve en hex; no hace falta tocarla en el cliente para leer.

## Comunidad (reportes estilo Waze)
Todos los ids son **uuid**. **Pedir siempre columnas explícitas, nunca `select("*")`:** la columna
`autor` de `report` y `comentario` (y `geom` de `message`) no es legible, por privacidad, y un `*`
falla con permiso denegado. Solo se ven los reportes vigentes; los propios (también vencidos) con
`supabase.rpc("mis_reportes")`. La BD decide lo que no debe decidir el cliente:
- **Crear reporte** (con sesión, `lib/queries.js crearReporte`): enviar solo `tipo`, `subtipo` (solo
  atasco: leve/moderado/detenido), `descripcion` (≤ 500), `foto_url` y `geom` = **posición GPS
  real** (`useGeolocation`, sin pin manual; dentro del Perú). `autor`, `estado`, `confianza`,
  `likes`, `expira_en` (12 h) los pone la BD. Tipos válidos en `src/lib/reportTypes.js` (coinciden
  con el CHECK de la BD). Máximo **5 reportes por hora** (trigger `report_limite`).
- **Foto** (`subirFotoReporte`): se reduce en el navegador a 1280 px de lado y JPEG al 85 %
  (`reducirFoto`, con `createImageBitmap` y la orientación de la imagen), límite 3 MB y solo
  JPG/PNG/WebP (lo mismo que el bucket), y sube al bucket público `reportes` en
  `<uid>/<timestamp>-<azar>.jpg`; la política de Storage solo deja subir dentro de la carpeta del
  propio uid. `report.foto_url` solo admite la **URL pública de ese bucket de este proyecto** con la
  carpeta del autor y extensión jpg/jpeg/png/webp (CHECK `report_foto_url_check` + trigger
  `report_foto_validar`, migración `20261020035127_report_foto_solo_bucket`): un enlace o una imagen
  de terceros no se guarda (hallazgo bloqueante del 19-10-2026, arreglado).
- **Votar** (`votar`): `upsert({ report_id, valor: 1 | -1 }, { onConflict: "report_id,autor" })`;
  tocar el mismo voto lo quita (`delete`). No se puede votar el propio reporte ni uno vencido. Los
  contadores los recalcula la BD (`confianza = (likes+1)/(likes+dislikes+2)`, `estado` por saldo ±3,
  reputación del autor): tras votar la web vuelve a pedir el reporte.
- **Comentar** (`comentar`): solo en reportes vigentes, 1 a 500 letras; máximo 20 comentarios por
  hora (trigger `comentario_limite`).
- **Perfil**: se crea solo al registrarse (`auth.signUp({ ..., options: { data: { nombre } } })`,
  trigger `crear_perfil`).
- **Chat** (`message`): vence a las 2 h, siempre; máximo 30 mensajes por hora (`message_limite`);
  tiempo real por la publicación `supabase_realtime` (respeta la RLS) y sondeo cada 10 s.
- Textos fijos (`lib/comunidad.js`): `DISCLAIMER`, `AVISO_REPORTE` ("Es un reporte comunitario, no
  oficial. Para emergencias llama al 105 o 116."), `NORMAS_CHAT`, `POR_QUE_CUENTA`.

```js
// geom desde el GPS, como texto EWKT (ojo: primero lon, después lat): lib/comunidad.js ewkt(lat, lon)
await supabase.from("report").insert({
  tipo: "inundacion",
  descripcion: "calle anegada",
  geom: `SRID=4326;POINT(${lon} ${lat})`,
});
```

## Rendimiento
Trabajo del 14-10-2026 (plan de la auditoría de rendimiento: puntos 1-7, 9 y 11 aplicados; 8 y 10
evaluados y descartados con datos; 5b, fuentes autoalojadas, pendiente: siguen en Google Fonts).
- **Entrega estática** (`nginx.conf`, `vite.config.js`): gzip + `gzip_static` con los `.gz` que deja
  el build (plugin `precomprimir`, zlib de Node, sin dependencias; archivos de 1 KB o más);
  `Cache-Control: public, max-age=31536000, immutable` para `/assets/` y `no-cache` para
  `index.html`, `manifest.webmanifest` y `sw.js`; cabeceras CSP (compatible con Supabase y su
  `wss:`, Stadia, NASA GIBS, IDESEP, fuentes de Google, `data:`/`blob:`), `X-Content-Type-Options`,
  `X-Frame-Options SAMEORIGIN`, `Referrer-Policy` y `access_log off` (no se guardan IPs). Si se suma
  un dominio externo nuevo (imágenes, `fetch`, websocket) hay que agregarlo a la CSP en los **tres**
  bloques. Validar sin reconstruir:
  `docker run --rm -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" nginx:alpine nginx -t`.
  Brotli no se sirve (nginx:alpine no trae el módulo).
- **Chunks** (`manualChunks`): `react`, `leaflet` y `supabase` en archivos propios; un cambio en el
  código de SIMPAC solo invalida `index-*.js` y las páginas perezosas, no los vendors que el
  navegador ya tiene. Radix no se separa (dependencia circular con React en otro chunk).
- **`index.html`**: `preconnect` a Supabase (URL inyectada con `%VITE_SUPABASE_URL%`), Stadia y
  Google Fonts, y las fuentes por `<link>` (ya no hay `@import` en `index.css`); manifest y
  `theme-color`.
- **Consultas**: `cached()` evita pedidos repetidos (una promesa por clave y TTL); las cuatro vistas
  de los ríos vigilados se piden a la vez (antes la ola 2 esperaba a `rio_vigilado_mapa`); las
  páginas y la hoja comparten la caché del mapa; la capa de A dónde acudir pide solo la caja a la
  vista. `BarrasLluvia` se monta recién al abrir la hoja.
- **Dibujo**: glifos como imagen `data:` URI (sin ~380 SVG en línea ni filtros), `L.canvas` para la
  lluvia de la última hora y los mapas FEN, memoria y reutilización de rótulos en
  `rotuloBusqueda.js`, huella por capa en `MapView` (un refresco igual no redibuja), geometrías de
  los ríos del país fuera de los datos de la capa, trazo fino solo a la vista desde zoom 13.
- **PWA**: `public/manifest.webmanifest`, `public/iconos/`, `public/sw.js` (solo la cáscara:
  `/assets/` con caché primero, `index.html` y manifest con red primero; nunca datos de Supabase ni
  tiles: sin red la app misma lo dice) y `src/pwa.js` (registra solo en `PROD`). Pendiente de confirmar en Chrome: en el navegador integrado del 20-10-2026 el
  registro falló ("An unknown error occurred when fetching the script") aunque nginx sirve `/sw.js`
  con 200, 2227 bytes y `no-cache`.

**Mediciones, antes y después** (14-10-2026, Vite dev, misma pestaña, 800x600 salvo indicación):

| Qué | Antes | Después |
|---|---|---|
| Consultas al abrir (todas distintas) | 14 | 14 |
| Inicio de la ola 2 (`rio_zona_mapa`, `rio_senal`, `rio_incidente`) | 836 ms (ola 1 a los 618) | las 14 arrancan juntas, 404-408 ms (móvil 422-427; última respuesta 861) |
| SVG en línea / filtros / `path` de marcadores | 382 / 192 / 582 | 0 / 0 / 0 |
| Nodos del DOM | 4 691 | 2 900 |
| `getPointAtLength` por arrastre · por zoom 13 a 14 | 2 050 · 3 463 | 456 (364-742 según vista; con rótulos libres < 60) · 648-742 |
| Pan de 1 px · zoom 13 a 14 | 17,4 ms · 66 ms | 10,5 ms · 47 ms |
| Render (JIT caliente) rio · pronóstico · zona | 85 · 64 · 19 ms | 27 · 29 · 11 ms |
| JS principal · CSS en la red | 323 876 B · 68 553 B sin comprimir | 112 280 B · 17 005 B gzip, precomprimidos |
| nginx comprime | no | sí (gzip; vendors ~148 KB gz con caché de un año) |

Sin cambios: `path` y vértices del pane `zonaRio` (11 `path`; 439/397/397 a zoom 13), textos e
iconografía.

**Build del 20-10-2026** (con las páginas y los ríos del país; `npm run build`, 9,43 s, 1801
módulos): `index-*.js` 444,38 kB (154,97 gzip), `supabase-*.js` 227,45 (59,01), `leaflet-*.js`
149,58 (43,36), `react-*.js` 141,39 (45,45), `index-*.css` 80,19 (19,72); páginas perezosas Alertas
16,25, Historico 15,06, Cuenta 11,79, ReporteNuevo 7,09, Chat 6,00, TarjetaReporte 4,26,
ReporteDetalle 3,54, Comunidad 2,81 kB. Vite avisa que `lib/queries.js` se importa dinámico y
estático a la vez (sin efecto). Servido por nginx en `:8080`: `index-*.js` llega con
`Content-Encoding: gzip`, 154 838 bytes de 445 544 (34,8 %), los mismos `.gz` del build. Primera
carga con caché fría: 19 peticiones REST a 17 vistas/tablas, 0 duplicadas, de los 483 a los 3216 ms;
con assets en caché `DOMContentLoaded` 106 ms, `load` 114 ms y el titular visible a los 468 ms. Al
cambiar de ciudad solo se suman `titular_zona`, `punto_acudir` por caja, nowcast y `report`.
Imagen Docker: `frontend/Dockerfile` es `node:22-alpine` desde el 20-10-2026 (antes `node:20-alpine`
con el aviso `EBADENGINE` de `@supabase/supabase-js` 2.116.0); build del 24-10 OK en 11,6 s, 1801
módulos.

**Cómo medir** (lo que se usó): DevTools > Network con filtro `rest/v1` para contar consultas, sus
tiempos de inicio y si alguna se repite; Performance para grabar un arrastre o un zoom y leer el
tiempo de script; en la consola `document.querySelectorAll("*").length` y
`document.querySelectorAll(".leaflet-overlay-pane path").length` para nodos y `path`;
`performance.getEntriesByType("navigation")[0]` para `domContentLoadedEventEnd` y `loadEventEnd`;
`npm run build` para los tamaños de los chunks y
`curl -sI -H "Accept-Encoding: gzip, br" http://localhost:8080/assets/<archivo>` para lo que sirve
nginx. Comparar siempre la misma vista, el mismo tamaño de ventana y la misma pestaña.

## App Android
**Desde el 20-10-2026 la app de SIMPAC es nativa en Kotlin + Jetpack Compose** y vive en
`appmobile/android/` (`applicationId` `pe.simpac.app`, `versionCode 2`; guía en `appmobile/README.md`,
técnica en `docs/README-tecnico.md` §8.4). Lee Supabase y la API por su cuenta y abre **esta web en un
WebView solo en la pestaña Mapa** (URL configurable; por defecto `http://10.0.2.2:8080`, el Docker de la
PC visto desde el emulador) y `<WEB>/cuenta` desde su pestaña Cuenta; la sesión de Supabase Auth no se
comparte. Recibe push por FCM (temas `pais` y `zona_<slug>`) cuando la tarea `push` del worker avisa
una alerta o emergencia. Lo que cambie en esta web lo ve la app al recargar el WebView, sin recompilar.

**App anterior (Capacitor), retirada el 2026-10-24:** entre el 14-10 y el 24-10 la app fue esta misma
web empaquetada con Capacitor 8.5.3 (`frontend/android/`, `capacitor.config.json`, origen
`https://localhost`, GPS por `@capacitor/geolocation`). La app Kotlin la reemplazó al instalarse (mismo
`applicationId`) y, al confirmarse el 24-10 que su WebView pinta el mapa (el `WebView` dentro de
`AndroidView` necesitaba `LayoutParams` `MATCH_PARENT`: con `WRAP_CONTENT` Chromium resuelve `100vh` y
`height: 100%` como 0 y esta web, que usa `h-screen`, quedaba en blanco), se retiró todo lo de
Capacitor: la carpeta `android/`, `capacitor.config.json`, los scripts `android:*` de `package.json`,
las dependencias `@capacitor/*`, la rama nativa de `hooks/useGeolocation.js` (ahora solo
`navigator.geolocation`, que el WebView de la app Kotlin atiende con el GPS del sistema) y la condición
`window.Capacitor` de `src/pwa.js`. Requisitos, firma, publicación en Play y emulador sin ventana de la
app actual (Kotlin) en **`appmobile/README.md`**.

## Despliegue en Vercel
Desde el 04-11-2026 la web se puede publicar en **Vercel** sin Docker: `frontend/vercel.json` repite
el contrato de `nginx.conf` (SPA, CSP y cabeceras, caché) y Vercel compila con `npm run build`. El
backend (API, worker y Redis) va aparte, en Railway; la web no lo llama (lee Supabase directo), así
que el orden no importa. Netlify es la alternativa equivalente (`frontend/netlify.toml`, al final).

**Qué hace `vercel.json`** (sintaxis vigente de https://vercel.com/docs/project-configuration/vercel-json):
- `framework: "vite"`, `buildCommand: "npm run build"`, `outputDirectory: "dist"` (valen aunque el
  panel diga otra cosa) y `trailingSlash: false` (`/alertas/` redirige 308 a `/alertas`).
- **SPA**: `rewrites` manda a `/index.html` toda ruta que no empiece por `/assets/` ni `/iconos/` ni
  sea `/sw.js` o `/manifest.webmanifest` (patrón `/:ruta((?!assets/|iconos/|sw\.js|manifest\.webmanifest).*)`).
  Vercel sirve primero los archivos que existen y recién después aplica el rewrite, así que
  `/assets/noexiste.js` responde 404 (nunca `index.html` con tipo de script), igual que en nginx.
- **Cabeceras**: en `/(.*)` la misma `Content-Security-Policy` de `nginx.conf` (letra por letra; si se
  suma un dominio externo nuevo hay que cambiarla en `nginx.conf`, `vercel.json` y `netlify.toml`),
  `X-Content-Type-Options nosniff`, `X-Frame-Options SAMEORIGIN` y `Referrer-Policy
  strict-origin-when-cross-origin`; `Cache-Control: public, max-age=31536000, immutable` en
  `/assets/(.*)` y `no-cache` en todo lo demás salvo `/iconos/` (cubre `index.html`, `sw.js`, el manifest
  y las rutas de la SPA, que también entregan `index.html`). La CSP no necesita nada más para Vercel:
  no se usan Analytics ni Speed Insights. En un **preview** con la barra de Vercel (vercel.live)
  activada la CSP la bloquea y sale un error en consola, sin efecto en la web; en producción no se
  inyecta nada.
- **Compresión**: Vercel comprime (gzip y brotli) por su cuenta, así que el plugin `precomprimir` de
  `vite.config.js` no corre cuando existe la variable `VERCEL` (ni `NETLIFY`), que la plataforma
  define sola en su build; los `.gz` solo serían archivos de más. Localmente y en Docker sigue igual.

**Mapa base en un dominio real.** Las tiles de Stadia salen sin llave solo desde `localhost`. Para el
dominio de Vercel hay dos caminos (https://docs.stadiamaps.com/authentication/): autorizar el
**dominio** en el panel de Stadia (recomendado para el navegador, no hay llave en el código; Stadia
revisa el `Origin` y el `Referer`, que nuestra `Referrer-Policy` sí manda) o una **API key** gratuita
en la variable `VITE_STADIA_API_KEY`, que `map/baseMap.js` agrega a la URL de las tiles como
`?api_key=...` (pública en el navegador, como la de Supabase). Vacía o ausente, la URL queda como
siempre. La CSP ya permite `https://tiles.stadiamaps.com` en `img-src` y `connect-src`.

**Pasos en el panel de Vercel** (todo desde https://vercel.com, sin CLI):
1. **Add New > Project > Import Git Repository**: conectar la cuenta de GitHub y elegir
   `github.com/Federjj/SIMPAC` (rama `main`).
2. En la pantalla de configuración: **Root Directory** = `frontend` (botón Edit); **Framework
   Preset** = Vite (lo toma de `vercel.json`; Build Command `npm run build` y Output Directory
   `dist` quedan iguales).
3. **Environment Variables** (las tres son públicas; nunca la secret key ni la connection string):
   `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (los valores de `frontend/.env.example`) y
   `VITE_STADIA_API_KEY` (la llave creada en stadiamaps.com, o vacía si se autorizó el dominio).
   Marcar Production y Preview.
4. **Deploy**. El build tarda 1 a 2 min; al terminar Vercel da un dominio `*.vercel.app`.
5. **Dominio**: Settings > Domains para sumar uno propio (CNAME a `cname.vercel-dns.com` o los
   registros que indique). Cada cambio de variable pide un **Redeploy** (Deployments > ... > Redeploy),
   porque Vite las copia en el build.

**Después del primer deploy** (fuera de Vercel):
- **Stadia**: en stadiamaps.com > Manage Properties > Authentication Configuration autorizar
  `<dominio>.vercel.app` y el dominio propio (los subdominios van explícitos).
- **Supabase Auth**: Authentication > URL Configuration > Redirect URLs: agregar
  `https://<dominio>/cuenta` (la confirmación de correo y "olvidé mi contraseña" vuelven ahí; ver
  "Cuentas y sesión") y, si se quiere, poner `https://<dominio>` como Site URL.
- **API en Railway**: sumar `https://<dominio>` a `SIMPAC_CORS_ORIGENES` del servicio `api`
  (separados por coma, sin barra final). Hoy la web no llama a la API, pero así queda listo si una
  página empieza a usar `/api/snapshot`.

**Cómo verificar** (con el dominio real):
```bash
curl -sI https://<dominio>/ | grep -i -E "content-security-policy|x-frame|x-content-type|referrer-policy|cache-control"
curl -sI https://<dominio>/alertas | grep -i -E "^HTTP|cache-control"      # 200 y no-cache (es index.html)
curl -sI https://<dominio>/assets/noexiste.js | grep -i "^HTTP"            # 404
curl -sI "https://<dominio>/assets/$(curl -s https://<dominio>/ | grep -o 'assets/index-[^"]*\.js' | head -1 | cut -d/ -f2)" | grep -i cache-control  # immutable
curl -sI https://<dominio>/sw.js | grep -i cache-control                   # no-cache
```
En el navegador: abrir `https://<dominio>/alertas` y **recargar** (debe seguir en Alertas, no 404);
el mapa debe pintar tiles (si quedan grises, la pestaña Red muestra 401 de `tiles.stadiamaps.com`:
falta autorizar el dominio o la llave); crear una cuenta y ver que el correo de confirmación vuelve a
`/cuenta`. Nota: `npm run build` local con `VERCEL=1` reproduce la build de Vercel (sin `.gz`).

**Netlify (alternativa)**: `frontend/netlify.toml` hace lo mismo (`[build]` con `command = "npm run
build"` y `publish = "dist"`, redirect `/* -> /index.html 200` sin `force`, así un archivo que existe se
sirve primero, y las mismas cabeceras por `[[headers]]`). En el panel: Add new site > Import from Git >
el repo, **Base directory** = `frontend` (ahí lee el `netlify.toml`), las mismas tres variables en
Environment variables y Deploy. Diferencia: en Netlify `/assets/noexiste.js` responde `index.html` con
200 (el redirect no distingue carpetas); el resto, igual. Las URLs de Supabase, Stadia y CORS se
registran igual que arriba.

## Notas
- **Lectura pública**: los datos oficiales y los reportes se leen con la publishable key (RLS).
- **Escritura** (reportes, votos, comentarios, chat, perfil, preferencias): necesita sesión de
  Supabase Auth (`/cuenta`).
- **Mapa base**: Stadia Alidade Smooth sirve sin llave solo a `localhost`. En un **dominio real**
  hay que autorizar el dominio en la cuenta de Stadia o poner su API key gratuita en
  `VITE_STADIA_API_KEY` (`map/baseMap.js` la agrega como `?api_key=…`; ver "Despliegue en Vercel" y
  `.env.example`). La **app Android** cumple hoy la condición
  porque su origen es `https://localhost`; si Stadia cambia esa regla, pasar la llave o cambiar la
  base a OpenStreetMap/CARTO con su atribución (`appmobile/README.md`).
- **CSP**: cualquier dominio externo nuevo va en los tres bloques de `nginx.conf`.
- **Auth**: las Redirect URLs de cada origen se registran en Supabase (ver "Cuentas y sesión").
- **Supabase pausado** (del 15 al 19 de octubre de 2026): la web arranca igual, el semáforo queda en
  "SIN DATOS" con "No se pudo consultar las alertas. Revisa tu conexión." y Reintentar; nada se
  inventa.

## Ríos del país con zonas y franja (24-10-2026)
Resumen de lo integrado el 24-10 (detalle en "Inicio: Tu zona ahora" y en "Ríos del país", reglas 8
a 10; `npm test` 157, `npm run build` OK):
- `lib/zonaAhora.js` elige el río más cercano entre los vigilados del departamento y los ríos con trazo
  de ANA (`rio_cauce_mapa`); chips "A X km del río Y (trazo de ANA)", "Dentro/Fuera de la zona que
  podría inundarse (estimación SIMPAC con el relieve)" cuando el río tiene filas en
  `rio_cauce_zona_mapa`, y "Este río no tiene mapa de zonas; la franja junto al cauce es solo
  referencial" cuando no. "Ver el río X en el mapa" encuadra a la persona y el tramo más cercano.
- Capa `zona` (`map/layers/zonasRio.js`): zonas de `rio_cauce_zona_mapa` por río visible desde zoom 12
  (caché 60 min, nunca el país entero), visibles desde zoom 13; franja de atención (`franja` de
  `rio_cauce_mapa`) solo con el río en alerta o emergencia. Simulación DEV:
  `?simular=rio:<rio_ana>:alerta|emergencia`.
- Verificado el 24-10 con la build de Docker (`node:22-alpine`): Cajamarca (Mashcón, "Fuera de la zona"),
  Lima ("A 820 m del río Rímac", "Fuera de la zona ..., a 680 m", zonas del Rímac dibujadas),
  Tumbes ("A 1.1 km del río Tumbes", "Fuera de la zona"), Iquitos (Itaya, sin mapa de zonas); Trujillo,
  Chiclayo y Piura todavía muestran "El río con trazo más cercano está a 31-34 km" (Moche y Reque no
  tienen trazo; la estación del Piura no quedó emparejada: falta un alias en
  `backend/data/rios/cauces_alias.json`).
