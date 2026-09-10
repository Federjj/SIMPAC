# SIMPAC — Stack tecnológico

> Tecnologías del proyecto por capa, con su **estado**:
> ✅ implementado (prototipo) · 🔵 decidido · 🟡 a evaluar.
> SIMPAC = plataforma web + app Android que centraliza datos hidrometeorológicos de Cajamarca,
> emite alertas de lluvia/crecidas y suma una capa comunitaria (reportes + chat) tipo Waze.

---

## 1. Resumen (tabla maestra)

| Capa | Tecnología | Para qué | Estado |
|---|---|---|---|
| Lenguaje backend | **Python 3.10+** | conectores, ingesta, API | ✅ |
| Lenguaje frontend | **TypeScript / JavaScript** | web y app | 🔵 |
| API backend | **FastAPI** | REST + WebSockets | 🔵 *(prototipo con `http.server` stdlib ✅)* |
| Cliente HTTP | `urllib` → **httpx** | consumo de fuentes | ✅ → 🔵 |
| Base de datos | **PostgreSQL + PostGIS** (vía **Supabase**) | datos relacionales + geoespaciales | 🔵 *(prototipo SQLite ✅)* |
| Autenticación | **Supabase Auth** | cuentas y roles | 🔵 |
| Tiempo real (in-app) | **Supabase Realtime** | chat y alertas en vivo | 🔵 |
| Almacenamiento | **Supabase Storage** | fotos de reportes | 🔵 |
| Notificaciones push | **Firebase Cloud Messaging (FCM)** | avisos al celular | 🔵 |
| Scraping HTML | **BeautifulSoup4** | avisos SENAMHI, tablas | 🔵 |
| Parsing de PDF | **pdfplumber** | comunicados ENFEN | 🔵 |
| ETL geoespacial | **GeoPandas + Shapely** | shapefile → GeoJSON | 🔵 |
| Mapas (frontend) | **Leaflet + GeoJSON** | visualización en mapa | 🔵 |
| Gráficos (frontend) | **Recharts / Chart.js** | series de lluvia/caudal | 🟡 |
| Framework web | **React + Vite** | SPA | 🔵 |
| App móvil | **React Native** (o Kotlin + MapLibre) | Android + GPS | 🟡 |
| Jobs / ingesta | **cron / Programador de tareas / APScheduler / GitHub Actions** | pasadas horarias | ✅ *(manual)* → 🔵 |
| Interpretación (NLG) | **API de un LLM** | titular en lenguaje natural | 🟡 |
| Diseño de UI | **Claude Design** | maquetas | 🔵 *(en curso)* |
| Control de versiones | **Git + GitHub** (monorepo) | código y docs | ✅ |
| Despliegue | **Vercel/Netlify** (web) · **Supabase** (BD/back) · **Render/Railway** (jobs) | hosting | 🟡 |

---

## 2. Detalle por capa

### 2.1. Backend
- **Python** como lenguaje único de servidor: sirve para scraping, procesamiento geoespacial,
  PDF, API y jobs — un solo stack para el equipo.
- **FastAPI** en producción (REST + WebSockets en un mismo framework, async, tipado). El
  prototipo actual usa `http.server` de la librería estándar solo para correr sin instalar nada;
  la lógica vive en `store.py` y migra 1:1 a FastAPI.
- **httpx** como cliente HTTP con timeouts/reintentos (el prototipo usa `urllib`).

### 2.2. Base de datos
- **PostgreSQL + PostGIS** a través de **Supabase**. PostGIS es obligatorio por lo geoespacial
  (estaciones, ríos, reportes con lat/lon; consultas "a X km de mí"). El prototipo usa **SQLite**
  con un esquema espejo para funcionar sin servidor.
- Tablas núcleo: `estacion`, `lectura_lluvia`, `lectura_caudal`, `indice`, `alerta`, y (comunidad)
  `usuario`, `report`, `confirmation`, `message`.

### 2.3. Adquisición de datos (scraping / conectores)
- **Inspección de red** (DevTools) para descubrir APIs internas no documentadas.
- **`urllib`/`httpx`** + **regex** para extraer JSON embebido (inventario de estaciones de
  SENAMHI) y series de **Highcharts** (lluvia horaria).
- **BeautifulSoup4** para tablas HTML (avisos meteorológicos de SENAMHI).
- **pdfplumber** para PDFs (comunicados de ENFEN).
- **GeoPandas + Shapely** para convertir shapefiles (mapas de anomalías de SENAMHI/IDESEP) a
  GeoJSON.
- Un **conector aislado por fuente**, con caché y rate-limit (ver `docs/README-tecnico.md`).

### 2.4. Frontend web
- **React + Vite** (TypeScript). **Leaflet + GeoJSON** para el mapa (soporte nativo de GeoJSON).
- Gráficos de series con **Recharts** o **Chart.js** (a definir).
- Diseño de la interfaz con **Claude Design** (ver `docs/frontend-brief.md`).

### 2.5. App móvil (Android)
- **React Native** recomendado para reusar lógica, tipos y capa de API del web (mapas con
  `react-native-maps`, que soporta GeoJSON). Alternativa nativa: **Kotlin + MapLibre**.
- GPS del dispositivo para geolocalizar alertas y reportes.

### 2.6. Alertas, tiempo real y notificaciones
- **Motor de umbrales** propio (Python): compara lluvia y caudal contra umbrales por zona.
- **Supabase Realtime** para el chat y las alertas dentro de la app (WebSockets sobre Postgres).
- **Firebase Cloud Messaging (FCM)** para la entrega de push al celular (única vía real para
  despertar la app en Android; convive con Supabase, no lo reemplaza).

### 2.7. Interpretación (NLG / LLM)
- **API de un LLM** para redactar el titular en lenguaje natural, **con los números fijados** en
  el prompt (no inventa cifras). El estado/valor siempre es trazable a la fuente oficial.

### 2.8. Ingesta programada y despliegue
- **Jobs horarios** con cron / Programador de tareas de Windows / APScheduler / GitHub Actions.
- Despliegue tentativo: **Supabase** (BD + auth + realtime + storage), **Vercel/Netlify** (web),
  **Render/Railway/Fly** o **Supabase Edge Functions** (API y jobs).

---

## 3. Fuentes de datos externas y sus protocolos

| Fuente | Aporta | Protocolo / formato |
|---|---|---|
| **SENAMHI** | estaciones, lluvia/temp horaria, avisos | HTML+JSON embebido, Highcharts, tabla HTML; IDESEP = GeoNetwork/CSW + shapefiles |
| **ANA** (SNIRH/ONRH) | caudales de ríos + umbrales | Web services **ASMX** (POST → JSON) |
| **IGP** | ICEN (El Niño Costero) | archivo de texto (**HTTP**, requiere proxy) |
| **NOAA / CPC** | ONI (ENSO global) | archivo de texto (HTTPS) |
| **CENEPRED** (SIGRID) | peligro/riesgo | **ArcGIS REST** (MapServer/FeatureServer) |
| **ENFEN** | estado de alerta El Niño Costero | WordPress **wp-json** / PDF |

Detalle completo de endpoints en `docs/fuentes-y-endpoints.html` y `docs/README-tecnico.md`.

---

## 4. Estructura del monorepo

```
VigiaFEN/
├─ backend/          # Python: conectores, ingesta, motor de alertas, API
│  ├─ connectors/    #   un módulo por fuente
│  ├─ store.py       #   persistencia (SQLite prototipo → PostGIS)
│  ├─ alerts.py  ingest.py  api.py
│  └─ requirements.txt
├─ frontend/         # (por crear) React + Vite + Leaflet
├─ mobile/           # (por crear) React Native / Android
└─ docs/             # documentación (este archivo, README-técnico, briefs, endpoints)
```

---

## 5. Decisiones clave (resumen)

- **Python en el backend:** un solo lenguaje para todo el lado servidor.
- **Supabase (PostGIS) como BD**, no Firestore: el modelo es geoespacial y relacional.
- **FCM solo para push**, no como base de datos: es la única vía para notificar al celular.
- **Leaflet + GeoJSON** en el mapa: estándar abierto, reutilizable en web y móvil.
- **Un conector por fuente:** las APIs internas cambian sin aviso; aislarlas contiene el daño.

---

## 6. Madurez actual

- **Implementado (prototipo, corre hoy):** conectores SENAMHI/ANA/IGP/NOAA, ingesta a SQLite,
  API JSON, motor de umbrales. Datos en tiempo real verificados.
- **Decidido, por construir:** Supabase/PostGIS, FastAPI, frontend React, auth, realtime, push,
  app móvil.
- **A evaluar:** librería de gráficos, framework móvil final, proveedor de despliegue, LLM.
