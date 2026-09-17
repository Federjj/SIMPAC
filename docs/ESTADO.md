# SIMPAC — Estado del proyecto

> Panel vivo de "dónde estamos". Actualizado: **2026-09-15**.
> Repo: `github.com/Federjj/SIMPAC` (monorepo, rama `main`).

## Resumen en una línea
Backend + Supabase con datos reales (**ríos a nivel nacional**); **frontend React (Mapa)
funcionando**; **stack dockerizado** (frontend, backend async, worker, redis). Falta correr el
stack con la credencial de BD y construir las demás páginas del front.

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

**Frontend (React + Vite + Leaflet)** — `frontend/`
- [x] Página **Mapa** funcionando y conectada a Supabase: estaciones/ríos/zonas reales, estilo Waze,
      íconos (no emojis), paleta saturada, tipografía formal.
- [x] **Geolocalización** (con permiso) + **selector de ciudades del Perú** (Cajamarca por defecto).
- [x] Componentes: `Sidebar`, `MapView`, `LayersPanel`, `StatusPanel`, `CitySelector`.
      Correr: `npm --prefix frontend install && npm --prefix frontend run dev` → localhost:5173.

**Infraestructura (Docker)** — `docker-compose.yml`
- [x] Stack de 4 servicios: **frontend** (nginx), **backend** (FastAPI **async**), **worker**
      (Celery + beat), **redis** (caché + cola). `docker compose config` validado.
- [x] API async con caché en Redis (snapshot) para aguantar varios usuarios.
- [x] `store_supabase.py` reescrito **nacional + concurrente** (ThreadPool) — lo corre el worker cada hora.
- [ ] **Falta correr el stack**: `cp .env.docker.example .env`, poner `SUPABASE_DB_URL`, `docker compose up --build`.

**Documentación** (`docs/`)
- [x] `README-tecnico.md`, `fuentes-y-endpoints.html`, `frontend-brief.md`, `stack-tecnologico.md`,
      `pre-documentacion-general.html`, y este `ESTADO.md`.

---

## Decisiones del equipo (15 sep)
- **Fuera** el apartado de administración para técnicos de Defensa Civil y la **moderación humana**
  (nada de contratar moderadores). Simplifica la app y evita tocar población/muestra en el informe.
- **La comunidad valida los reportes**: like/dislike + comentarios (la app es intermediaria, no juez).
  BD actualizada: tablas `voto` y `comentario` en vez de `confirmation`; sin roles admin.

## En progreso / parcial
- [ ] **Frontend** — página Mapa lista; faltan las demás (Alertas, Comunidad, Chat, Cuenta, crear
      reporte) + **react-router** para la navegación de la barra lateral. Ver `frontend-brief.md`.
- [ ] Incidentes/usuarios en el mapa son **demo**; se conectan a `report`/`voto` cuando haya login (v2).
- [ ] **Lluvia histórica completa en la BD** — hoy hay solo una estación de muestra; el resto entra
      solo cuando corra el job de ingesta a Supabase.

---

## Siguiente (por hacer)

**Backend / datos**
- [ ] **Levantar el stack** (`docker compose up --build`) con `SUPABASE_DB_URL` en `.env` → el worker
      puebla todo a nivel nacional (estaciones de los 24 dptos + caudales) y refresca la caché solo.
      Ya no hace falta cron: el **beat** de Celery programa la ingesta horaria.
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
  de referencia, riesgo bajo; se puede activar RLS si el jurado lo pide.
- **Umbrales de lluvia = placeholder**, deben calibrarse antes de confiar en las alertas de lluvia.
