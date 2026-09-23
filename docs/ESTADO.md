# SIMPAC — Estado del proyecto

> Panel vivo de "dónde estamos". Actualizado: **2026-09-23**.
> Repo: `github.com/Federjj/SIMPAC` (monorepo, rama `main`).

## Resumen en una línea
Backend + Supabase con datos reales (**ríos a nivel nacional**, **avisos oficiales de SENAMHI
como áreas, con ícono**, **pronóstico oficial por localidad**, **nowcasting experimental**,
**lluvia de la última hora en todo el país**, **serie del ICEN** y **5 mapas históricos de eventos
El Niño**); **frontend React (Mapa) con datos reales, capas de lluvia sombreadas, selector de día,
franja de 3 días y un panel gráfico de El Niño**; **stack dockerizado y corriendo** con 6 tareas de
datos programadas en el worker. Faltan las demás páginas del front (Alertas, Comunidad, Chat, Cuenta).

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
      `supabase/migrations/` (22 migraciones, versionadas en el repo); foto final en
      `supabase/schema.sql`: 19 tablas y 7 vistas con las de los avisos con ícono, el pronóstico
      y el nowcasting (ver abajo).
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
      `backend/mapas/cargar_fen.py` (upsert idempotente por uuid, índice único `mapa_uuid_key`).
      Detalle en `README-tecnico.md` §5.7.

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
      `pre-documentacion-general.html`, y este `ESTADO.md`.
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
  y en `frontend/src/lib/reportTypes.js`; falta la pantalla de creación. Policía quedó fuera.
- **Solo se reporta donde uno está** (GPS, sin pin manual) para evitar reportes troll.

## En progreso / parcial
- [ ] **Frontend** — página Mapa lista; faltan las demás (Alertas, Comunidad, Chat, Cuenta, crear
      reporte) + **react-router** para la navegación de la barra lateral. Ver `frontend-brief.md`.
- [ ] **Reportes reales**: la capa ya lee `report` (vigentes); falta login (Supabase Auth) y la
      pantalla de creación y voto. El contrato para el front está en `frontend/README.md`.
- [x] **Alertas de lluvia desplegadas** (migración aplicada, imágenes reconstruidas). Kevin, tras el
      pull: reconstruir frontend, worker y API. Consulta de control en `README-tecnico.md` §5.6.2.
- [x] **Avisos con ícono, pronóstico y nowcasting desplegados** (migraciones `avisos_iconos`,
      `pronostico_localidad` y `nowcast_senamhi` aplicadas; imágenes reconstruidas). Kevin, tras el
      pull: reconstruir frontend, worker y API. Control con las consultas de `README-tecnico.md`
      §5.6.6.
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

**Frontend / móvil**
- [x] **Web (Mapa)**: React + Vite + Leaflet conectado a Supabase (ya está).
- [x] **Capa FEN en el mapa** (HU-12): polígonos coloreados por `RANGO` + selector de evento
      (geometrías simplificadas: 0,3 a 0,9 MB por evento).
- [ ] **Mapas FEN: cargar los demás trimestres.** Cada registro de IDESEP trae varios (DEF, EFM,
      FMA) y hoy se guarda solo el primero (dic a feb; en 2023, ene a mar), así que el mapa de
      2017 no muestra marzo, cuando se desbordó el río Piura. La capa ya rotula los meses.
- [ ] **Web (resto)**: páginas Alertas, Comunidad, Chat, Cuenta, crear reporte + react-router.
- [ ] **App móvil**: arrancar `appmobile/` (React Native); GPS + push.
- [ ] Crear el proyecto **Firebase (FCM)** para push y conseguir la server key.

---

## Reparto (para no duplicar)
- **Tú (Fabricio) + Claude:** datos, conectores, Supabase/BD, backend, documentación.
- **Kevin:** frontend web + app móvil + cuenta Firebase; hizo el pipeline de mapas FEN históricos.

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
