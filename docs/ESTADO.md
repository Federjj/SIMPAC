# SIMPAC — Estado del proyecto

> Panel vivo de "dónde estamos". Actualizado: **2026-09-22**.
> Repo: `github.com/Federjj/SIMPAC` (monorepo, rama `main`).

## Resumen en una línea
Backend + Supabase con datos reales (**ríos a nivel nacional** + **5 mapas históricos de eventos
El Niño**); **frontend React (Mapa) con datos reales**; **stack dockerizado y corriendo** con el
ingesta horaria real funcionando (982 estaciones, lluvia horaria de Cajamarca al día). Código
**refactorizado y modular** (22 sep), comunidad con **ids UUID** y permisos por columna. Falta la
capa FEN y la de lluvia en el mapa, y las demás páginas del front.

---

## Hecho

**Datos / backend (prototipo, corre sin instalar nada)**
- [x] Conectores en vivo: **SENAMHI** (estaciones + lluvia horaria), **ANA** (caudales+umbrales),
      **IGP** (ICEN), **NOAA** (RONI), **ENFEN** (comunicado e Informe Técnico, PDF). `backend/connectors/`
- [x] Prototipo sin dependencias: ingesta → SQLite → API JSON, hoy en `backend/prototipo/` (congelado).
- [x] Motor de umbrales (`alerts.py`).
- [x] **Tiempo real verificado** con evidencia: SENAMHI y ANA se actualizan a la hora en curso.

**Base de datos (Supabase)**
- [x] Proyecto **DATASYMPAC** (ref `clrnommkjyksnyrtnisf`, región São Paulo).
- [x] **Esquema aplicado**: 13 tablas + vista `caudal_actual` + **PostGIS** + **RLS**. Historia en
      `supabase/migrations/` (15 migraciones, versionadas en el repo); foto final en `supabase/schema.sql`.
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
  - Lo que es criterio de SIMPAC ("atento", umbrales de lluvia de 24 h) se rotula como referencial.
- [x] **Revisión adversarial de este cambio** (8 agentes, 24 hallazgos confirmados, corregidos). Lo principal:
  - Nunca "Normal" en verde por algo que no se midió: mientras carga, si falla la consulta o si
    SIMPAC no vigila nada en la zona (Callao) sale "Sin datos". En Lima aclara que la lluvia aún no
    se mide ahí.
  - Una alerta de lluvia de 24 h (umbral provisional) sube la zona a "Alerta" como mucho, nunca a
    "Emergencia", y se describe como lo que es: "mucha lluvia acumulada" (referencial).
  - Avisos cuando ANA o SENAMHI no respondieron en la última corrida.
  - La etiqueta dice "La Niña costera" si el ENFEN declara La Niña.
  - La lluvia de otra ciudad ya no queda pegada al cambiar de ciudad.
  - El worker encola `ingesta` y `enfen` al arrancar (el beat pierde su programación al recrear el
    contenedor).
  - La tarea ENFEN aísla el comunicado del Informe Técnico: si uno falla, el otro se guarda igual.
  - No vuelve a bajar 17 MB por un informe ilegible o que ya leyó.

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
- [ ] **Lluvia en más departamentos**: hoy la ingesta baja la lluvia horaria solo de Cajamarca
      (`SIMPAC_LLUVIA_DEPTS`); sumar otros es cambiar esa variable (slugs de SENAMHI).

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
- [ ] **Capas de lluvia en áreas (fase 3)**, todas gratis y sin key (investigadas y verificadas el 22 sep):
  - Avisos meteorológicos de SENAMHI: polígonos oficiales por nivel en la GeoServer de IDESEP
    (`g_aviso:view_aviso`). Van por el worker a Supabase, porque WFS no tiene CORS y el servidor es
    intermitente. También alimentan las alertas (tipo `aviso`).
  - Aviso de lluvia de 24 h (`g_prono_pp_24h:view_aviso24h`), por WMS.
  - Lluvia observada de ayer y de 7 días (`monitoreo_meteorologico:prec_1`, `prec_1_ac07d`), por WMS.
  - Lluvia horaria nacional con umbrales (`g_umbrales:umbrales_precipitacion`): ~180 estaciones,
    26 en Cajamarca.
  - NASA IMERG por GIBS: lluvia satelital de todo el Perú, con 5 a 6 h de retraso.
  - Radar: no hay sobre Cajamarca. Windy, OpenWeatherMap y Tomorrow.io piden key o son pagos.
- [ ] **INPE (Hidroestimador, lluvia casi en tiempo real)**: su sitio exige autorización expresa de
      CPTEC/INPE para reproducirlo en medios de divulgación. Pedirla por correo antes de publicarlo.
- [ ] Calibrar los **umbrales de lluvia** (hoy placeholders en `alerts.py`) con Defensa Civil.

**Frontend / móvil**
- [x] **Web (Mapa)**: React + Vite + Leaflet conectado a Supabase (ya está).
- [ ] **Capa FEN en el mapa** (HU-12): polígonos coloreados por `RANGO` + selector de evento. Leer
      `mapa` con `variable='FEN'`; conviene simplificar geometrías (`cargar_fen --simplificar`) porque
      pesan hasta ~5.5 MB. El render actual de anomalías solo pinta puntos.
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
- **Umbrales de lluvia = placeholder**, deben calibrarse antes de confiar en las alertas de lluvia
  (candidatos: umbrales por estación de `g_umbrales` de SENAMHI o sus percentiles diarios).
- **ANA cambia de juego de umbrales según la temporada** (crecida / nivel bajo). ANA no publica el
  nivel amarillo que sí usa SENAMHI en sus avisos hidrológicos.
- **Worker corriendo como root** en el contenedor: solo un `SecurityWarning` de Celery, inofensivo
  en Docker; si se quiere limpio, correrlo con un usuario no-root en el Dockerfile.
