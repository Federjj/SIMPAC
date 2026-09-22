# SIMPAC — Stack tecnológico

> Tecnologías del proyecto por capa, con su **estado**:
> **hecho** = implementado (prototipo) · **decidido** = decidido, por construir · **evaluar** = a evaluar.
> SIMPAC = plataforma web + app Android que centraliza datos hidrometeorológicos de Cajamarca,
> emite alertas de lluvia/crecidas y suma una capa comunitaria (reportes + chat) tipo Waze.

---

## 1. Resumen (tabla maestra)

| Capa | Tecnología | Para qué | Estado |
|---|---|---|---|
| Lenguaje backend | **Python 3.10+** | conectores, ingesta, API | hecho |
| Lenguaje frontend | **TypeScript / JavaScript** | web y app | decidido |
| API backend | **FastAPI (async)** | API REST cacheada | hecho *(dockerizado; prototipo stdlib también)* |
| Cliente HTTP | `urllib` (conectores, con reintentos) · **httpx** (API → Supabase) | consumo de fuentes | hecho |
| Base de datos | **PostgreSQL + PostGIS** (vía **Supabase**) | datos relacionales + geoespaciales | hecho *(migraciones en `supabase/migrations/`)* |
| Autenticación | **Supabase Auth** | cuentas y roles | decidido |
| Tiempo real (in-app) | **Supabase Realtime** | chat y alertas en vivo | decidido |
| Almacenamiento | **Supabase Storage** | fotos de reportes | decidido |
| Notificaciones push | **Firebase Cloud Messaging (FCM)** | avisos al celular | decidido |
| Scraping HTML | **BeautifulSoup4** | avisos SENAMHI, tablas | decidido |
| Parsing de PDF | **pypdf** | comunicados e Informe Técnico ENFEN | hecho |
| ETL geoespacial | **GeoPandas + Shapely** | shapefile → GeoJSON | hecho *(cargador de mapas FEN; import perezoso)* |
| Mapas (frontend) | **Leaflet** (tiles Stadia Alidade Smooth) | visualización en mapa | hecho |
| Gráficos (frontend) | **Recharts / Chart.js** | series de lluvia/caudal | evaluar |
| Framework web | **React + Vite** | SPA (página Mapa lista) | hecho |
| UI / estilos | **Tailwind CSS + shadcn/ui** (Radix + lucide) | sistema de diseño y componentes | hecho |
| App móvil | **React Native** (o Kotlin + MapLibre) | Android + GPS | evaluar |
| Worker / ingesta | **Celery + beat** (sobre Redis) | ingesta horaria nacional + caché | hecho *(corriendo; beat activo)* |
| Contenedores | **Docker + docker-compose** | frontend · backend · worker · redis | hecho *(stack corriendo)* |
| Caché / cola | **Redis** | snapshot cacheado + broker de Celery | hecho *(refresco cada 5 min OK)* |
| Interpretación (NLG) | **API de un LLM** | titular en lenguaje natural | evaluar |
| Diseño de UI | **Claude Design** | maquetas | decidido *(en curso)* |
| Control de versiones | **Git + GitHub** (monorepo) | código y docs | hecho |
| Despliegue | **Docker compose** (frontend/backend/worker/redis) · Supabase (BD) | hosting | decidido |

---

## 2. Detalle por capa

### 2.1. Backend
- **Python** como lenguaje único de servidor: sirve para scraping, procesamiento geoespacial,
  PDF, API y jobs — un solo stack para el equipo.
- **FastAPI** en producción (REST + WebSockets en un mismo framework, async, tipado), ya en
  `backend/app.py`. El prototipo con `http.server` de la librería estándar quedó congelado en
  `backend/prototipo/`.
- Los conectores usan `urllib` de la librería estándar (`connectors/_http.py`: TLS estricto,
  timeouts y reintentos); **httpx** async solo lo usa la API para leer Supabase.

### 2.2. Base de datos
- **PostgreSQL + PostGIS** a través de **Supabase**. PostGIS es obligatorio por lo geoespacial
  (estaciones, ríos, reportes con lat/lon; consultas "a X km de mí"). El prototipo usa **SQLite**
  con un esquema espejo para funcionar sin servidor.
- Tablas núcleo: `estacion`, `lectura_lluvia`, `lectura_caudal`, `indice`, `alerta`, `mapa`, y
  (comunidad) `perfil`, `report`, `voto`, `comentario`, `message`.

### 2.3. Adquisición de datos (scraping / conectores)
- **Inspección de red** (DevTools) para descubrir APIs internas no documentadas.
- **`urllib`/`httpx`** + **regex** para extraer JSON embebido (inventario de estaciones de
  SENAMHI) y series de **Highcharts** (lluvia horaria).
- **BeautifulSoup4** para tablas HTML (avisos meteorológicos de SENAMHI).
- **pypdf** (pure Python) para los PDF del ENFEN: comunicado oficial e Informe Técnico (solo en el worker).
- **GeoPandas + Shapely** para convertir shapefiles (mapas de anomalías de SENAMHI/IDESEP) a
  GeoJSON.
- Un **conector aislado por fuente**, con caché y rate-limit (ver `docs/README-tecnico.md`).

### 2.4. Frontend web
- **React + Vite** (JavaScript). **Leaflet** para el mapa, con tiles **Stadia Alidade Smooth**
  (claro y con detalle de calles; gratis en localhost, al desplegar a un dominio pide API key gratuita).
- **Tailwind CSS + shadcn/ui** como sistema de diseño (tema claro estilo dashboard, componentes
  sobre Radix + iconos lucide, sin emojis). La página Mapa ya está construida y es responsive.
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
- **Ingesta horaria con Celery beat** (worker en Docker Compose, sin cron).
- Despliegue actual: **Docker Compose** (frontend nginx, API, worker, Redis) + **Supabase** (BD,
  auth, realtime, storage). Un hosting público (VPS o similar) queda para después de la entrega.

---

## 3. Fuentes de datos externas y sus protocolos

| Fuente | Aporta | Protocolo / formato |
|---|---|---|
| **SENAMHI** | estaciones, lluvia/temp horaria, avisos | HTML+JSON embebido, Highcharts, tabla HTML; IDESEP = GeoNetwork/CSW + shapefiles |
| **ANA** (SNIRH/ONRH) | caudales de ríos + umbrales | Web services **ASMX** (POST → JSON) |
| **IGP** | ICEN (El Niño Costero) | archivo de texto (**HTTP**, requiere proxy) |
| **NOAA / CPC** | RONI (ENSO global, oficial desde feb-2026) | archivo de texto (HTTPS) |
| **CENEPRED** (SIGRID) | peligro/riesgo | **ArcGIS REST** (MapServer/FeatureServer) |
| **ENFEN** | estado de alerta El Niño Costero + ICEN al día | PDF (gob.pe / SENAMHI) |

Detalle completo de endpoints en `docs/fuentes-y-endpoints.html` y `docs/README-tecnico.md`.

---

## 4. Estructura del monorepo

```
VigiaFEN/
├─ backend/          # Python: conectores, ingesta, motor de alertas, API
│  ├─ connectors/    #   un módulo por fuente
│  ├─ ingesta/       #   ingesta horaria a Supabase (recolectar + guardar)
│  ├─ app.py  celery_app.py  snapshot.py  alerts.py  config.py  db.py
│  ├─ prototipo/     #   versión sin dependencias (SQLite), congelada
│  └─ tests/         #   pruebas sin red
├─ supabase/         # migraciones de la BD + schema.sql consolidado
├─ frontend/         # React + Vite + Tailwind + shadcn/ui + Leaflet (pagina Mapa lista)
├─ appmobile/        # (por crear) React Native / Android
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

- **Implementado (corre hoy, 22 sep):** conectores SENAMHI/ANA/IGP/NOAA/IDESEP; Supabase con
  PostGIS y RLS; ingesta horaria en el worker (Celery + beat) y caché en Redis; API FastAPI async;
  5 mapas históricos de eventos El Niño cargados; frontend React (página Mapa con datos reales);
  todo en Docker. Datos en tiempo real verificados.
- **Decidido, por construir:** auth, realtime (chat), push (FCM), app móvil, capas de áreas FEN y
  de lluvia en el mapa, resto de páginas del front.
- **A evaluar:** librería de gráficos, framework móvil final, proveedor de despliegue, LLM.
