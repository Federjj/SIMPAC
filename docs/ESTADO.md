# SIMPAC — Estado del proyecto

> Panel vivo de "dónde estamos". Actualizado: **2026-09-16**.
> Repo: `github.com/Federjj/SIMPAC` (monorepo, rama `main`).

## Resumen en una línea
Backend + Supabase con datos reales (**ríos a nivel nacional**); **frontend React (Mapa)
funcionando**; **stack dockerizado y corriendo** (frontend, backend async, worker Celery, redis)
con el worker refrescando la caché sin errores. Falta poblar todo a nivel nacional con el job de
ingesta (credencial de BD) y construir las demás páginas del front.

---

## Hecho

**Datos / backend (prototipo, corre sin instalar nada)**
- [x] Conectores en vivo: **SENAMHI** (estaciones + lluvia horaria), **ANA** (caudales+umbrales),
      **IGP** (ICEN), **NOAA** (ONI). `backend/connectors/`
- [x] Ingesta → SQLite → API JSON (`ingest.py`, `store.py`, `api.py`) + motor de umbrales (`alerts.py`).
- [x] **Tiempo real verificado** con evidencia: SENAMHI y ANA se actualizan a la hora en curso.

**Base de datos (Supabase)**
- [x] Proyecto **DATASYMPAC** (ref `clrnommkjyksnyrtnisf`, región São Paulo).
- [x] **Esquema aplicado**: 11 tablas + **PostGIS** + **RLS** (`supabase/schema.sql`).
- [x] **Datos cargados**: 93 estaciones (27 automáticas) con geometría (y columnas `lat`/`lon`) ·
      13 ríos de Cajamarca con caudal y umbrales (hoy) · 48 h de lluvia de UNC Cajamarca (muestra) ·
      ICEN 1.98 / ONI 1.8 · capa de **anomalías de precipitación** (muestra Cajamarca, tabla `mapa`).
- [x] **Ríos a nivel NACIONAL**: 138 estaciones de caudal en 23 departamentos (2 en emergencia, Loreto).
- [x] **Lectura del frontend verificada**: la publishable key lee estaciones/caudales/índices/mapa
      vía la API REST de Supabase (RLS de lectura pública funcionando).
- [x] **MCP de Supabase** conectado en modo escritura (Claude puede leer/editar la BD).
- [x] **Código de ingesta a Supabase** listo (`backend/store_supabase.py`) — solo falta credencial.

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
      **por corrida** y la API usa uno persistente por `lifespan` (`backend/cache.py`, `backend/app.py`).
- [x] API async con caché en Redis (snapshot) para aguantar varios usuarios.
- [x] `store_supabase.py` reescrito **nacional + concurrente** (ThreadPool) — lo corre el worker cada hora.
- [ ] **Falta la ingesta nacional completa**: poner `SUPABASE_DB_URL` en `.env` para que la tarea
      `ingesta` (horaria) pueble estaciones/lluvia de los 24 dptos. La caché ya sirve lo cargado por MCP.

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
- **Reporte tipo Waze** (por construir): selector rápido de tipo con subtipos, p. ej.
  Inundación · Huayco/Deslizamiento · Lluvia intensa · Vía bloqueada · Atasco (leve/moderado/detenido)
  · Bache · Accidente. (Policía y similares quedan opcionales; el foco es clima/agua + impacto en vías.)

## En progreso / parcial
- [ ] **Frontend** — página Mapa lista; faltan las demás (Alertas, Comunidad, Chat, Cuenta, crear
      reporte) + **react-router** para la navegación de la barra lateral. Ver `frontend-brief.md`.
- [ ] **Incidentes reales**: la capa queda vacía hasta conectar la tabla `report` de Supabase (con
      login) y construir el flujo de creación (reporte tipo Waze). "Usuarios cercanos" se descartó.
- [ ] **Lluvia histórica completa en la BD** — hoy hay solo una estación de muestra; el resto entra
      solo cuando corra el job de ingesta a Supabase.

---

## Siguiente (por hacer)

**Backend / datos**
- [x] **Levantar el stack** (`docker compose up --build`): ya corre; el **beat** de Celery programa
      la ingesta horaria y el refresco de caché (sin cron).
- [ ] **Poner `SUPABASE_DB_URL` en `.env`** para que la tarea `ingesta` pueble a nivel nacional
      (estaciones de los 24 dptos + lluvia). Hoy la caché sirve lo que ya se cargó por MCP.
- [ ] **Revocar `EXECUTE`** de la función `rls_auto_enable()` al rol `anon` (aviso del advisor).
- [ ] Conector de **avisos SENAMHI** (scraping de tabla) → alertas oficiales al motor.
- [ ] Reescribir la API en **FastAPI** sobre el mismo `store` (la actual es prototipo desechable).
- [ ] Calibrar los **umbrales de lluvia** (hoy placeholders en `alerts.py`) con Defensa Civil.

**Frontend / móvil**
- [x] **Web (Mapa)**: React + Vite + Leaflet conectado a Supabase (ya está).
- [ ] **Web (resto)**: páginas Alertas, Comunidad, Chat, Cuenta, crear reporte + react-router.
- [ ] **App móvil**: arrancar `appmobile/` (React Native); GPS + push.
- [ ] Crear el proyecto **Firebase (FCM)** para push y conseguir la server key.

---

## Reparto (para no duplicar)
- **Tú (Fabricio) + Claude:** datos, conectores, Supabase/BD, backend, documentación.
- **Kevin:** frontend web + app móvil + cuenta Firebase.

## Notas y riesgos activos
- **ANA es intermitente** (hoy 500/timeout). Es el organismo, no el código; por eso cada fuente
  está aislada y el seed sigue aunque una falle.
- **Token de Supabase con full-access** en variable de entorno: funciona, pero ideal reducir su
  scope al proyecto cuando se pueda. Se puede revocar en cualquier momento.
- **Advisor de Supabase**: `spatial_ref_sys` (tabla interna de PostGIS) sale sin RLS — dato público
  de referencia, riesgo bajo. Pendiente menor: `rls_auto_enable()` es `SECURITY DEFINER` y hoy la
  puede llamar `anon` por RPC; revocarle el `EXECUTE`.
- **La anon key es pública por diseño** (no es fuga): viaja en cada request y se ve en el navegador;
  lo que protege es **RLS**, que está activo en todas las tablas de datos.
- **Umbrales de lluvia = placeholder**, deben calibrarse antes de confiar en las alertas de lluvia.
- **Worker corriendo como root** en el contenedor: solo un `SecurityWarning` de Celery, inofensivo
  en Docker; si se quiere limpio, correrlo con un usuario no-root en el Dockerfile.
