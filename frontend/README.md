# SIMPAC — Frontend

Web en **React + Vite + Tailwind + shadcn/ui + Leaflet** que lee directo de Supabase. La **página
Mapa ya está construida y funcionando** con datos reales; el diseño de las demás pantallas está en
`docs/frontend-brief.md` (estilo Waze).

## Arranque
```bash
npm install
cp .env.example .env # llaves públicas de Supabase (en PowerShell: Copy-Item .env.example .env)
npm run dev          # http://localhost:5173
npm test             # pruebas de los módulos puros (node --test, sin dependencias nuevas)
npm run build        # compila a dist/
```
El `.env` no se sube a git: sin él la app no arranca (`supabaseUrl is required`). Cliente:
`src/lib/supabaseClient.js`.
Imports con alias: `@/` = `src/` (p. ej. `import { LAYERS } from "@/map/layers"`).

## Estructura
```
src/
  App.jsx · main.jsx · index.css
  components/   Sidebar · MapView · LayersPanel · StatusPanel · ElNinoPanel · CitySelector · DiaSelector ·
                ChipNowcast · FranjaPronostico (y FranjaMini) · Glifo · InsigniaCapa · ui/ (shadcn)
  hooks/        usePanorama(depto) (estado de tu zona y del país, se refresca solo) · useGeolocation ·
                useLayerVisibility (con opciones vinculadas; recuerda las capas) · usePronosticoLocal
                (franja de 3 días) · useRiosVigilados(depto) (ríos vigilados de tu zona con su nivel)
  map/
    baseMap.js    mapa base (tiles Stadia, zoom, ResizeObserver)
    markers.js    íconos SVG, markerIcon(), popupHtml() y escapeHtml()
    iconos.js     glifos del tiempo con relleno suave (viewBox 32) y sus degradados (DEFS_SVG)
    marcadores.js insignia de un aviso, disco de una localidad y disco de un río (L.divIcon de 0x0),
                  rombo de un desborde pasado y punto de un lugar de los avisos hidrológicos
    colocar.js    acomodo en pantalla, puro (qué se ve, qué se junta, qué rótulo cabe)
    acomodo.js    enlace de colocar.js con Leaflet (corre al mover el mapa); escala y banda de zoom
    rotuloLinea.js nombre de un río escrito sobre su trazo (SVG textPath)
    popups.js     HTML de los popups de avisos, pronóstico, nowcasting, zonas de los ríos y desbordes
    palette.js    colores por nivel, estación, ENFEN, aro de los avisos, pronóstico, nowcasting, zonas
                  de los ríos (ZONA_HEX, ZONA_OSCURO) y cauce resaltado (CAUCE_HEX)
    senamhi.js    imágenes WMS de la GeoServer de SENAMHI con estilo propio (SLD) y su atribución
    layers/       una capa por archivo + index.js (GRUPOS y LAYERS)
  lib/          supabaseClient · queries · lenguaje (todos los textos en lenguaje claro) · nivel (semáforo,
                tu zona / el país) · tiempo (horas de Perú) · ubicacion (departamento del GPS) · reportTypes ·
                geo (distancias y punto en polígono) · pronostico (ícono y frase de cada día, franja) ·
                avisoTexto (textos de los avisos) · zonaRio (nivel de la zona de un río vigilado) ·
                preferencias (capas recordadas) · simulacion (?simular=, solo desarrollo)
  data/         cities.js (capitales del Perú con su departamento y su localidad del pronóstico de SENAMHI)
```
Los módulos puros (`lib/tiempo.js`, `lib/geo.js`, `lib/pronostico.js`, `lib/avisoTexto.js`,
`lib/lenguaje.js`, `lib/zonaRio.js`, `lib/preferencias.js`, `map/colocar.js`, `map/iconos.js`,
`map/palette.js`) usan imports relativos que terminan en `.js` (sin `@/`) para que
`node --test` los lea tal cual; sus pruebas son los `*.test.js` de al lado.

## Capas del mapa
Cada archivo de `src/map/layers/` exporta la misma forma (detalle en `layers/index.js`): `id`,
`grupo`, `label`, `Icon`, `defaultVisible`, `legend` (lista o función de la opción), `fuente`,
`opciones` (opcional: un selector, p. ej. el evento El Niño; con `vinculo`, las capas del mismo
vínculo comparten la opción), `insignia` (opcional: "Oficial" o "Experimental"), `load(opcion)` y
`render(group, datos, { opcion, map, avisar, acomodo })`, que puede devolver una nota corta ("dato
de las 14:30") o un objeto `{texto, corto, estado}` que el panel muestra bajo el switch; opcional
`refreshMs`. `MapView` carga cada capa al encenderla y cada vez que cambia su opción (reintenta si
falla). Las áreas sombreadas van en el pane `areas` (El Niño) y en `aviso2`/`aviso3`/`aviso4` (el
relleno de los avisos, con la transparencia en el pane: dos amarillos superpuestos no se ven
naranja), con los bordes en `avisoBorde`, las zonas que un río podría afectar en `zonaRio` (encima
de los avisos: el toque cae en la zona y su popup cita el aviso), el nowcasting en `nowcast` y los
ríos resaltados en `rios` (sobre las demás líneas), debajo de los marcadores.
**Sumar una capa** = crear su archivo y agregarla a `layers/index.js`.

| Grupo | Capa | Archivo | Datos |
|---|---|---|---|
| Alertas y avisos | Avisos de SENAMHI (hoy / mañana / pasado mañana), con insignia | `avisos.js` | vista `aviso_vigente` (tarea `avisos` del worker; `icono`, `lectura`, `texto_dia` y `anclas` de la migración de íconos) |
| Pronóstico | Pronóstico por localidad (SENAMHI) | `pronostico.js` | vista `pronostico_vigente` (tarea `pronostico`): un disco por localidad, del mismo día que los avisos |
| Pronóstico | Lluvia en las próximas 2 horas (experimental) | `nowcast.js` | vistas `nowcast_estado` y `nowcast_vigente` (tarea `nowcast`); solo con "Hoy" |
| Alertas y avisos | Zonas que un río podría afectar | `zonasRio.js` | vistas `rio_zona_mapa`, `rio_senal`, `rio_vigilado_mapa`, tabla `rio_incidente` y `caudal_actual` (nivel en `lib/zonaRio.js`); un río sin mapa de zonas que crece hasta su alerta, el círculo de 2,5 km de antes |
| Alertas y avisos | Quebradas que podrían activarse (huaycos) | `huaycos.js` | WMS SENAMHI `silvia:cuencas_nivel_12_prono1_silvia` (niveles 2 a 4) |
| Lluvia | Lluvia de la última hora (estaciones) | `lluviaAhora.js` | vista `lluvia_senamhi_actual` (tarea `lluvia_nacional`); color por intensidad, borde amarillo si pasó la referencia de SENAMHI (1 h o 6 h) |
| Lluvia | Lluvia de ayer / de la semana | `lluviaObservada.js` | WMS SENAMHI `prec_1` / `prec_1_ac07d` (superficie interpolada) |
| Lluvia | Lluvia por satélite (NASA) | `lluviaSatelite.js` | NASA GIBS, GPM IMERG 30 min (llega con 5-6 h de retraso) |
| Lluvia | Lluvia del mes frente a lo normal | `anomalias.js` | `mapa` con `variable = 'precipitacion'` |
| Ríos y estaciones | Ríos (disco con rótulo; el Mashcón resaltado con su nombre y la faja marginal de ANA) | `rios.js` | vista `caudal_actual` (última lectura de ayer u hoy por estación), `rio_vigilado_mapa` y las fajas de `rio_zona_mapa` |
| Ríos y estaciones | Desbordes y daños pasados | `desbordes.js` | tabla `rio_incidente` (rombo con el año; "×n" si con ese zoom quedarían encimados) |
| Ríos y estaciones | Estaciones SENAMHI | `estaciones.js` | `estacion` |
| El Niño | Eventos El Niño pasados (1982-83, 1997-98, 2017, 2023, 2023-24; un trimestre de cada uno) | `fenHistorico.js` | `mapa` con `variable = 'FEN'` |
| Comunidad | Reportes ciudadanos | `incidentes.js` | `report` (la BD solo entrega los vigentes) |

Las capas WMS se piden directo a la GeoServer de SENAMHI (`idesep.senamhi.gob.pe`) con un estilo
propio (`sld_body`): transparente donde no hay nada. Esa GeoServer es intermitente: si una imagen
falla, la capa lo avisa en su nota. **Licencia SENAMHI:** su leyenda literal
(`ATRIBUCION_SENAMHI` en `map/senamhi.js`) va siempre a la vista al pie del panel de estado (también
plegado) y al pie del panel de capas; los avisos simplificados se rotulan "basado en el aviso de
SENAMHI" y enlazan al original. NASA GIBS pide reconocer "NASA GIBS, parte de ESDIS": va en la
fuente y en la atribución de la capa satelital.

## Avisos con ícono, pronóstico por localidad y nowcasting
**Forma = qué es el dato, color = qué tan fuerte, punteado = no es seguro.**
- **Aviso oficial:** el área sombreada más una **insignia**: disco blanco con aro del color del nivel
  (amarillo, naranja, rojo) y el glifo del fenómeno: gota, gota con rayo (solo si el aviso es de una
  región y SENAMHI afirma descargas), copo; en calor, frío y viento, termómetro o viento (así su
  amarillo no se confunde con el de la lluvia). Va en cada parte grande del aviso (`anclas`, calculadas
  en la BD). El popup (`lib/avisoTexto.js` + `map/popups.js`) dice "puede llover en algún momento en
  esta zona", los mm por subregión con barras (si SENAMHI los da y se leyeron enteros; si no, la cita
  literal), viento, rayos, granizo, nieve y el texto oficial sin cambios. En un punto con varios
  avisos, el popup los junta ("También rige aquí").
- **Pronóstico por localidad:** disco blanco con el glifo del tiempo (nunca amarillo, naranja ni
  rojo); borde punteado si SENAMHI escribe "tendencia a". Sin fila no hay disco.
- **Nowcasting (experimental):** manchas azules y violeta con borde punteado; si SENAMHI no publica
  hace más de 30 min (lo decide la vista), no se muestran y el chip lo dice.

**Íconos.** `map/iconos.js` (puro) tiene los glifos (`GLIFOS`, `glifoSvg(nombre)`) y sus degradados
(`DEFS_SVG`, ids `simpac-*`), que `main.jsx` monta una vez con `montarDefsIconos()`. Los mismos
glifos van en el mapa, la franja, los popups y las leyendas (`components/Glifo.jsx`). Los botones y
el panel siguen con Lucide.

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

**Día vinculado.** Avisos y pronóstico comparten la opción "Día" (`opciones.vinculo = "dia"`):
`DiaSelector` (Hoy / Mañana / el día de pasado mañana) arriba al centro desde `lg` y en la columna de
la izquierda en pantallas más angostas. El nowcasting solo se ve con "Hoy"; con otro día,
`ChipNowcast` dice "elige Hoy".

**Franja de 3 días.** `FranjaPronostico` (en el panel de estado, entre los avisos y las métricas) es
el pronóstico de SENAMHI de tu localidad: la de la ciudad elegida (`cities.js`, campo `localidad`)
o, con GPS, la más cercana (hasta 10 km; de 10 a 30 km lo aclara; más lejos, lo dice y no muestra
días). Tocar un día muestra el texto de SENAMHI. Con el panel plegado queda `FranjaMini`. En el
celular (menos de 640 px) el panel arranca plegado y sigue al ancho de la pantalla hasta que la
persona lo abre o lo pliega a mano.

**Sin la base al día.** Si las vistas nuevas aún no existen (migraciones pendientes), la app sigue:
`getAvisosVigentes` pide las columnas de antes (una vez por sesión) y el mapa va sin insignias,
`getPronosticoVigente` y el nowcasting devuelven `null` (la capa dice que no se pudo cargar y la
franja no se muestra).

## Ríos vigilados: el río resaltado, la zona que podría afectar y los desbordes pasados
Primero el **Mashcón** (Cajamarca); los datos se cargan una vez con `backend/mapas/cargar_rios.py`
(vistas `rio_vigilado_mapa`, `rio_zona_mapa`, `rio_senal` y tabla `rio_incidente`). Sin esas vistas
(migración pendiente) la app sigue igual: `getRiosVigilados` devuelve `null` (un solo pedido fallido
por hora; las otras tres ni se piden), la capa de zonas dice "aún no están cargadas" y el panel no
nombra ríos.
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
  color del aviso: «Mashcón · Aviso rojo SENAMHI  ANA: 0.13 m³/s». Los acomoda `colocar.js` (tipo
  `rio`): antes que los discos del pronóstico; una insignia de aviso encima lo deja como punto, un
  marcador de otra capa no. El de un río vigilado tiene más prioridad (más aún con señales en su zona)
  y, si lo tapa otro disco, se pega a su lado; su rótulo prueba a la derecha, a la izquierda, arriba y
  abajo.
- **La zona** (siempre la de **hoy**, no sigue el selector de día; nunca se relacionan m³/s con su
  extensión). Su nivel es el más alto de sus señales (`lib/zonaRio.js`, `estadoZona`):

| Nivel | Cuándo | Color |
|---|---|---|
| Emergencia | ANA mide el río sobre su nivel de emergencia (de crecida) o SENAMHI tiene un aviso hidrológico **rojo** vigente de su estación | rojo |
| Alerta | ANA, sobre su nivel de alerta, o aviso hidrológico **naranja** | naranja |
| Atentos | el río al 80 % de su caudal de alerta (criterio SIMPAC), aviso hidrológico **amarillo**, aviso de lluvia **naranja o rojo** en curso que toca la cuenca, o una estación de la cuenca que pasó la referencia de SENAMHI | ámbar |
| Sin señales | nada de lo anterior | azul (sigue siendo una zona que podría inundarse) |

  Solo lo que trata del río mismo (ANA o el aviso hidrológico) sube a naranja o rojo. Un río muy bajo
  (vaciante) y un aviso hidrológico de descenso o vencido no cuentan; un aviso amarillo de lluvia, uno
  naranja de mañana y un aviso hidrológico de crecida que SENAMHI publica sin nivel (`hidro_sin_nivel`)
  se mencionan en el popup sin subir el nivel. Con SENAMHI caído, la vista sigue dando un aviso
  hidrológico con fin conocido hasta ese fin; si su `visto_en` pasa de 3 h, el popup dice que la web
  de SENAMHI no responde desde esa hora y que es su último aviso conocido (`hidro_viejo`).
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
- **Panel de estado:** una línea por río de tu zona con señales («Río Mashcón: tranquilo, pero hay
  aviso de SENAMHI por lluvia fuerte sobre su cuenca. Mira la zona que podría afectar.»; si la señal es
  lluvia medida, «…pero llovió fuerte en su cuenca»), también con el panel plegado («Río Mashcón:
  atentos, hay señales en su cuenca»), y el botón «Ver en el mapa», que pliega el panel, prende las
  capas del río y de la zona y encuadra el cauce entre los chips de arriba y el panel (hasta zoom 14).
- **Simulación (solo `npm run dev`):** `?simular=mashcon:15.4` (caudal de ANA), `mashcon:hidro2` a
  `hidro4` (aviso hidrológico falso), `mashcon:lluvia` (RIO GRANDE GORE con 7,2 mm) o `mashcon:calma`
  (sin señales en la cuenca); varias con coma.
  La nota de la capa dice «SIMULACIÓN (solo desarrollo)». En la compilación de producción no existe.

## Capas recordadas
`hooks/useLayerVisibility.js` + `lib/preferencias.js` (puro, con pruebas). Se guardan en
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
- Pie del panel: «Tus capas se guardan en este navegador.» y, si algo cambió, «Restablecer capas».
- Con sesión de Supabase Auth también en la tabla `preferencia_mapa` (RLS: cada quien la suya; gana la
  copia guardada más tarde, y un celular nuevo sin cambios no pisa la cuenta). La app aún no tiene
  pantalla de inicio de sesión: queda lista.

## El Niño en gráficos
El chip "El Niño costero" del mapa (y el botón de la barra lateral) abre `ElNinoPanel`: en qué
paso está el Sistema de Alerta del ENFEN (sin alerta, vigilancia, alerta), el ICEN mes a mes de
los últimos 24 meses coloreado por categoría (tabla `icen_serie`; el estimado `ICEN_TMP` va
punteado) y botones que prenden en el mapa la lluvia de otros El Niño.

**Seguridad:** todo texto que va a un popup pasa por `popupHtml()`, que escapa el HTML. Los
reportes los escriben usuarios: nunca armar HTML con `${...}` a mano.

## Lenguaje claro

La app la usa cualquier persona, no un meteorólogo. Todo texto sale de `src/lib/lenguaje.js` (un
solo diccionario: lo mismo se dice igual en el panel, la barra lateral y los popups). Cada dato va
en tres capas: qué pasa (una frase), qué significa o qué hacer, y el número con su mes y su fuente
en chico. Primero la zona del usuario (departamento de la ciudad elegida o del GPS) y después el
país. Nunca se dice "todo normal" a secas: solo lo que SIMPAC mide.

| Dato | Regla | Fuente |
|---|---|---|
| Estado ENFEN | Vigilancia / Alerta / Sin alerta, con número y fecha del comunicado | Comunicado oficial ENFEN |
| Mar frente al Perú (ICEN) | neutra -0.7..+0.5 · débil..+1.3 · moderada..+2.1 · fuerte..+3.5 · extraordinaria | Nota Técnica ENFEN 01-2024 |
| Pacífico central (RONI) | El Niño/La Niña si \|x\| ≥ 0.5; débil, moderado, fuerte, muy fuerte cada 0.5 | NOAA CPC (desde feb-2026) |
| Ríos (caudal m³/s) | % del caudal que activa la alerta; "atento" desde el 80 % | ANA; "atento" es criterio SIMPAC |
| Ríos (nivel en m) | cuánto falta para el nivel de alerta; "atento" a 0.5 m | ANA; "atento" es criterio SIMPAC |
| Ríos con nivel bajo | si UEMERGENCIA < UALERTA el peligro es que baje (vaciante) | ANA |
| Lluvia por hora (intensidad) | ligera ≤2 · moderada ≤15 · fuerte ≤30 · muy fuerte ≤60 · torrencial | AEMET (referencia); solo para el color y el tamaño del punto en el mapa, no para las alertas |
| Lluvia sobre la referencia | pasa si `pp_1h > umbral_1h` o `pp_6h > umbral_6h` (mayor estricto; solo si la estación trae `pp_1h` y `umbral_1h > 0`). Nivel siempre `aviso`, con el rótulo "Atentos a la lluvia"; siempre "no es un aviso oficial" | Referencia de SENAMHI por estación (capa `g_umbrales`). `referenciaLluvia` (`lenguaje.js`) es la misma regla que `backend/alerts.py` |
| Lluvia del mes | clases oficiales ±15/±30/±60 %; si lo normal es < 10 mm se habla en mm | SENAMHI; lo de 10 mm es criterio SIMPAC |

## Qué tabla alimenta cada parte

| UI | Tabla / consulta | Notas |
|---|---|---|
| Franja de 3 días | `pronostico_vigente` (`codigo,nombre,departamento,lat,lon,fecha,emision,tmax,tmin,texto,tipo,posible,por,lluvia_segura,granizo,intensidad,momento,cielo,url`) | por páginas de 1000, en caché 10 min; la comparte con la capa del mapa y el "cerca de" del nowcasting |
| Chip del nowcasting | `nowcast_estado` (`vigente`, `vence_en`) y `nowcast_vigente` | en caché 60 s; el umbral de 30 min vive en la vista, no en el cliente |
| Estado, titular y contador | vista `alerta_actual` (las vigentes; la lluvia medida, solo con 3 h o menos) | tipos `caudal`, `nivel_bajo`, `aviso` (SENAMHI: amarillo = `aviso`, naranja = `alerta`, rojo = `emergencia`) y `lluvia` (una estación que pasó la referencia de SENAMHI: siempre `aviso`, `valor` y `umbral` de la ventana `ventana_h`, 1 o 6 h, y `detalle` listo para mostrar); `zona` = departamento. El contador y el color de la métrica "alertas y avisos" son solo de lo oficial: la lluvia no cuenta |
| El Niño costero | `comunicado_enfen` (el más reciente) | lo llena la tarea `enfen` del worker |
| Mar y Pacífico | `indice` | `ICEN` (+ `ICEN_TMP`) con su `origen`, y `RONI` |
| Gráfico del ICEN | `icen_serie` (`mes,valor,categoria,origen`) | IGP y tabla del Informe Técnico ENFEN (el ENFEN manda) |
| Cobertura de lluvia | `lluvia_senamhi_actual` + `latido` (`servicio = 'lluvia_nacional'`) | estaciones del departamento con lluvia de la hora y referencia (`referenciaLluvia(e).evaluable`). "Ninguna pasa la referencia" solo si el latido trae `alertas` no nulo (la última corrida evaluó) y la consulta respondió; si no, "No se pudo revisar la lluvia…". La frase del resto del país lo dice solo si hay estaciones evaluables fuera de la zona (`cobertura.lluviaFuera`) |
| Lluvia de tu zona (24 h) | `lectura_lluvia` + `estacion!inner(nombre,departamento)` | hoy solo Cajamarca tiene lluvia horaria |
| "ríos: actualizado HH:MM · lluvia: actualizada HH:MM" | `latido` (`servicio = 'ingesta'` y `'lluvia_nacional'`) | "sin actualizar desde" si pasan 3 h (ríos) o 1.5 h (lluvia). Si `lluvia_nacional` trae la falla `umbrales`, se avisa que la lluvia de la última hora puede estar atrasada |
| Ríos | `caudal_actual` | **no** `lectura_caudal`: esa es el historial (repite estaciones) |
| Ríos vigilados (trazo, rótulo, lugares) | `rio_vigilado_mapa` (`id,nombre,departamento,estacion_ana,rio_ana,estacion_senamhi,centro_lat,centro_lon,zoom,cauce,afluentes,guia_rotulo,lugares_aviso,fuentes`) | GeoJSON listo; caché 60 min; se empareja con `caudal_actual` por estación y río (sin tildes) |
| Zonas y faja marginal | `rio_zona_mapa` (`clave,rio,tipo,subtipo,orden,nombre,texto,fuente,fuente_url,licencia,atribucion,metodo,fecha_fuente,area_km2,geojson`) | ordenadas por `orden`; caché 60 min |
| Señales de la zona | `rio_senal` (`rio,avisos_lluvia,lluvia_cuenca,avisos_hidro`) | las cruza la BD con la cuenca; caché 5 min; el nivel lo decide `lib/zonaRio.js` |
| Desbordes pasados | `rio_incidente` (`fecha desc nulls last`) | solo los que nombran al río en su fuente; caché 60 min |
| Capas recordadas (con sesión) | `preferencia_mapa` (`usuario,version,datos`) | RLS por usuario; sin sesión, solo `localStorage` |
| Gráfico de lluvia (detalle) | `lectura_lluvia` (`ts,medido_en,precip_mm,temp_c` where `cod=…`) | ordenar por `medido_en` (ya en hora correcta) |
| Mapas FEN históricos | `mapa` con `variable = 'FEN'` | se pide el `geojson` del evento elegido (`periodo`); solo trae la propiedad `RANGO` (mm frente a lo normal) |
| Comunidad | `report`, `voto`, `comentario`, `message`, `perfil` | ver abajo |

> **Coordenadas:** usa las columnas `lat` / `lon` (vienen listas). `geom` es PostGIS y el Data API
> la devuelve en hex; no hace falta tocarla en el cliente para leer.

## Comunidad (reportes estilo Waze)
Todos los ids son **uuid**. **Pedir siempre columnas explícitas, nunca `select("*")`:** la columna
`autor` de `report` y `comentario` (y `geom` de `message`) no es legible, por privacidad, y un `*`
falla con permiso denegado. Solo se ven los reportes vigentes; los propios (también vencidos) con
`supabase.rpc("mis_reportes")`. La BD decide lo que no debe decidir el cliente:
- **Crear reporte** (con sesión): enviar solo `tipo`, `subtipo` (solo atasco: leve/moderado/detenido),
  `descripcion`, `foto_url` y `geom` = **posición GPS real** (`useGeolocation`, sin pin manual).
  `autor`, `estado`, `confianza`, `likes`, `expira_en` (12 h) los pone la BD. Tipos válidos en
  `src/lib/reportTypes.js` (coinciden con el CHECK de la BD). Máximo 5 reportes por hora.
- **Votar**: `upsert({ report_id, valor: 1 | -1 }, { onConflict: "report_id,autor" })`. No se puede
  votar el propio reporte ni uno vencido (ni quitar el voto cuando ya venció). Los contadores
  del reporte se actualizan solos.
- **Comentar**: solo en reportes vigentes; máximo 20 comentarios por hora.
- **Perfil**: se crea solo al registrarse (`auth.signUp({ ..., options: { data: { nombre } } })`).
- **Chat** (`message`): vence a las 2 h, siempre.

```js
// geom desde el GPS, como texto EWKT (ojo: primero lon, después lat)
await supabase.from("report").insert({
  tipo: "inundacion",
  descripcion: "calle anegada",
  geom: `SRID=4326;POINT(${lon} ${lat})`,
});
```

## Notas
- **Lectura pública**: los datos oficiales y los reportes se leen con la publishable key (RLS).
- **Escritura** (reportes, votos, chat): necesita sesión de Supabase Auth.
- Mapa base: Stadia Alidade Smooth (en un dominio real necesita su API key gratuita).
