# SIMPAC — Estado del proyecto

> Panel vivo de "dónde estamos". Actualizado: **2026-09-10**.
> Repo: `github.com/Federjj/SIMPAC` (monorepo, rama `main`).

## Resumen en una línea
Backend prototipo funcionando con datos reales en tiempo real; **base de datos Supabase creada,
con esquema y datos cargados**; falta construir la UI (en diseño) y conectar la ingesta a Supabase.

---

## ✅ Hecho

**Datos / backend (prototipo, corre sin instalar nada)**
- [x] Conectores en vivo: **SENAMHI** (estaciones + lluvia horaria), **ANA** (caudales+umbrales),
      **IGP** (ICEN), **NOAA** (ONI). `backend/connectors/`
- [x] Ingesta → SQLite → API JSON (`ingest.py`, `store.py`, `api.py`) + motor de umbrales (`alerts.py`).
- [x] **Tiempo real verificado** con evidencia: SENAMHI y ANA se actualizan a la hora en curso.

**Base de datos (Supabase)**
- [x] Proyecto **DATASYMPAC** (ref `clrnommkjyksnyrtnisf`, región São Paulo).
- [x] **Esquema aplicado**: 9 tablas + **PostGIS** + **RLS** (`supabase/schema.sql`).
- [x] **Datos cargados**: 93 estaciones (27 automáticas) con geometría (y columnas `lat`/`lon`) ·
      13 ríos de Cajamarca con caudal y umbrales (hoy) · 48 h de lluvia de UNC Cajamarca (muestra) ·
      ICEN 1.98 / ONI 1.8 · capa de **anomalías de precipitación** (muestra Cajamarca, tabla `mapa`).
- [x] **Lectura del frontend verificada**: la publishable key lee estaciones/caudales/índices/mapa
      vía la API REST de Supabase (RLS de lectura pública funcionando).
- [x] **MCP de Supabase** conectado en modo escritura (Claude puede leer/editar la BD).
- [x] **Código de ingesta a Supabase** listo (`backend/store_supabase.py`) — solo falta credencial.

**Documentación** (`docs/`)
- [x] `README-tecnico.md`, `fuentes-y-endpoints.html`, `frontend-brief.md`, `stack-tecnologico.md`,
      `pre-documentacion-general.html`, y este `ESTADO.md`.

---

## 🔄 En progreso / parcial
- [ ] **UI** — en diseño. Concepto: **mapa estilo Waze** (usuarios cercanos + incidentes tipo
      huayco/inundación + **zonas sombreadas** de riesgo/lluvia/inundación). Ver `frontend-brief.md` §4.2.
- [ ] **Lluvia histórica completa en la BD** — hoy hay solo una estación de muestra; el resto entra
      solo cuando corra el job de ingesta a Supabase.

---

## ⬜ Siguiente (por hacer)

**Backend / datos**
- [ ] **Correr la ingesta a Supabase** — el código ya está (`backend/store_supabase.py`); solo falta
      `pip install "psycopg[binary]"` y setear `SUPABASE_DB_URL` (connection string; en variable de
      entorno, no al chat ni a git). Con eso se pobla todo automáticamente.
- [ ] Programar el **job horario** (cron / Programador de tareas / GitHub Actions) para acumular histórico.
- [ ] Conector de **avisos SENAMHI** (scraping de tabla) → alertas oficiales al motor.
- [ ] Reescribir la API en **FastAPI** sobre el mismo `store` (la actual es prototipo desechable).
- [ ] Calibrar los **umbrales de lluvia** (hoy placeholders en `alerts.py`) con Defensa Civil.

**Frontend / móvil (Kevin)**
- [ ] **Web**: React + Vite + Leaflet consumiendo la API; maquetar el mapa Waze del brief con Claude Design.
- [ ] **App móvil**: arrancar `appmobile/` (React Native); GPS + push.
- [ ] Crear el proyecto **Firebase (FCM)** para push y conseguir la server key.

---

## 🧭 Reparto (para no duplicar)
- **Tú (Fabricio) + Claude:** datos, conectores, Supabase/BD, backend, documentación.
- **Kevin:** frontend web + app móvil + cuenta Firebase.

## ⚠️ Notas y riesgos activos
- **ANA es intermitente** (hoy 500/timeout). Es el organismo, no el código; por eso cada fuente
  está aislada y el seed sigue aunque una falle.
- **Token de Supabase con full-access** en variable de entorno: funciona, pero ideal reducir su
  scope al proyecto cuando se pueda. Se puede revocar en cualquier momento.
- **Advisor de Supabase**: `spatial_ref_sys` (tabla interna de PostGIS) sale sin RLS — dato público
  de referencia, riesgo bajo; se puede activar RLS si el jurado lo pide.
- **Umbrales de lluvia = placeholder**, deben calibrarse antes de confiar en las alertas de lluvia.
