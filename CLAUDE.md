# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es SIMPAC

Plataforma web + app Android que **centraliza datos hidrometeorológicos de Cajamarca (Perú)**,
emite **alertas de lluvia/crecidas** y (fases posteriores) suma reportes ciudadanos y chat tipo
Waze. Contenido y comentarios en **español (Perú)**.

## Comandos (backend, Python 3.10+)

Los prototipos usan **solo la librería estándar** — corren sin instalar nada:

```bash
python backend/demo.py      # foto en consola de datos en vivo (no toca la BD)
python backend/ingest.py    # trae datos de las fuentes y los guarda en backend/simpac.db
python backend/api.py       # API JSON en http://localhost:8000
```

No hay aún tests, linter ni build configurados. `backend/requirements.txt` lista solo las
dependencias **recomendadas para producción** (FastAPI, httpx, geopandas, psycopg…), no las del
prototipo. `appmobile/` es un placeholder vacío del futuro app móvil.

## Arquitectura (big picture)

Flujo de datos: **conectores → ingesta → store → API → (frontend/app)**.

- **`backend/connectors/`** — un módulo aislado por organismo (`senamhi`, `ana`, `igp`, `noaa`).
  Cada uno normaliza su fuente a `@dataclass`/listas; son funciones **puras** (no tocan la BD).
  Todo el HTTP pasa por `_http.py` (helpers `get`/`post_json` sobre `urllib`).
- **`backend/ingest.py`** — una "pasada": llama a los conectores, escribe en el store y
  recalcula alertas. Pensado para correr **cada hora** (cron / Programador de tareas). Acumular
  estas pasadas es lo que construye el histórico propio (las fuentes solo dan ventanas cortas).
- **`backend/store.py`** — persistencia. Hoy **SQLite** (`backend/simpac.db`) con un esquema que
  **espeja el de PostGIS**; en producción se reemplaza por PostgreSQL+PostGIS (Supabase) sin
  cambiar las firmas de las funciones.
- **`backend/alerts.py`** — motor de umbrales. El caudal usa los umbrales que ANA ya entrega
  por estación; la lluvia usa umbrales **placeholder que hay que calibrar** (están todos juntos
  al inicio del archivo, a propósito).
- **`backend/api.py`** — API JSON hecha con `http.server` de la stdlib. Es un **prototipo
  desechable** para ver el flujo; en producción se reescribe en **FastAPI** sobre el mismo
  `store`. No invertir en endurecerla.

## Convenciones y trampas (leer antes de tocar conectores)

- **Mantener los prototipos sin dependencias externas** (solo stdlib). Si se agrega una lib,
  actualizar `requirements.txt` y avisar; el objetivo es que `demo/ingest/api` corran en limpio.
- **IGP es HTTP-only**: el navegador (web HTTPS) no puede hacer `fetch` a `http://` (mixed
  content). Siempre descargar/proxyear desde el backend.
- **ANA (ASMX)**: el POST necesita el payload exacto
  `{pTipoRPT:1, pFecha:"dd/mm/aaaa", pCodAAA:"00", pCodALA:"00", pCodUbigeo:"00"}`; un cuerpo
  vacío devuelve HTTP 500.
- **SENAMHI**: el inventario viene como JSON embebido (`PruebaTest`) y la serie horaria como
  config de Highcharts embebida (textos con escapes `\uXXXX`). El histórico tabular está tras
  **CAPTCHA (Cloudflare Turnstile) — no automatizar ni evadir**; solo la ventana de 48 h es libre.
- **Datos en tiempo real verificados**: SENAMHI y ANA se actualizan a la hora en curso.
- **Un conector por fuente con caché/rate-limit**: las APIs internas cambian sin aviso; aislarlas
  contiene el daño. No martillar los servidores del Estado.

## Documentación (en `docs/`)

- `README-tecnico.md` — referencia técnica: endpoints, esquema de BD, motor de alertas, cómo
  programar el job. **Empezar por aquí.**
- `fuentes-y-endpoints.html` — catálogo visual de los endpoints reales por organismo.
- `frontend-brief.md` — brief de diseño (todas las pantallas/fases) para Claude Design.
- `stack-tecnologico.md` — stack por capa con el estado de cada tecnología.
- `pre-documentacion-general.html` — visión general no técnica del proyecto.

## Stack de producción (decidido, aún por construir)

Backend **FastAPI** · BD **Supabase (PostgreSQL + PostGIS)** · Auth/Realtime/Storage **Supabase**
· Push **Firebase Cloud Messaging (FCM)** (solo la entrega al celular; no como BD) · Web **React +
Vite + Leaflet/GeoJSON** · Móvil **React Native** (o Kotlin + MapLibre) · ETL geoespacial
**GeoPandas** · Scraping **BeautifulSoup4 / pdfplumber**.
