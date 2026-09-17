# SIMPAC — Documentación técnica (devs)

> **SIMPAC** — Sistema de Información Meteorológica y Prevención de Anomalías de Cajamarca.
> Plataforma web + app móvil que **centraliza datos hidrometeorológicos de Cajamarca** y
> emite **alertas tempranas de lluvia/crecidas** geolocalizadas.
>
> Este documento es la referencia técnica: arquitectura, conectores de datos, los endpoints
> reales de cada organismo y las partes "peludas" de la ingesta. Para el panorama general
> no técnico, ver la *Pre-documentación general*. Para el catálogo visual de endpoints, ver
> [`fuentes-y-endpoints.html`](./fuentes-y-endpoints.html).

---

## 1. TL;DR / Quickstart

Los prototipos de conectores usan **solo la librería estándar** de Python (3.10+), así que
corren sin instalar nada:

```bash
python backend/demo.py      # foto rápida en consola (sin BD)

python backend/ingest.py    # trae datos y los guarda en backend/simpac.db (SQLite)
python backend/api.py       # sirve la API JSON en http://localhost:8000
```

Salida esperada de `demo.py` (datos en vivo — foto de Cajamarca): contexto El Niño (ONI/ICEN),
caudales de ríos con su estado de alerta, y la lluvia horaria de una estación automática.

```
NOAA ONI   JJA 2026: +1.80  -> El Niño
IGP  ICEN  2026-05: +1.98  -> Cálido fuerte
Mashcón            Mashcon      18:00     0.13 m³/s  (normal)
Yónan Gore         Jequetepeque 21:00      2.3 m³/s  (normal)
...
CUTERVO (4726A602) — 48 horas ; último 2026/09/06 - 21  precip=0.0 mm  temp=13.3 °C
```

---

## 2. Estructura del repo

```
VigiaFEN/
├─ backend/
│  ├─ connectors/
│  │  ├─ _http.py        # helpers GET/POST (urllib, sin deps)
│  │  ├─ senamhi.py      # estaciones + serie horaria (lluvia/temp)
│  │  ├─ ana.py          # caudales de ríos + estado de alerta por umbral
│  │  ├─ igp.py          # Índice Costero El Niño (ICEN)
│  │  └─ noaa.py         # ONI (contexto ENSO global)
│  ├─ store.py           # persistencia SQLite (prototipo de la BD)
│  ├─ alerts.py          # motor de umbrales (lluvia + caudal)
│  ├─ ingest.py          # job de ingesta (correr cada hora)
│  ├─ api.py             # API JSON (http.server, sin deps)
│  ├─ demo.py            # prueba de humo en vivo
│  └─ requirements.txt
└─ docs/
   ├─ README-tecnico.md          (este archivo)
   ├─ fuentes-y-endpoints.html   (catálogo visual de endpoints)
   └─ pre-documentacion-general.html
```

---

## 3. Arquitectura

Principio: **un conector aislado por organismo** que normaliza su fuente a estructuras
simples. Los jobs de ingesta corren periódicamente, guardan en PostgreSQL/PostGIS, y la API
(FastAPI) sirve al frontend (React + Leaflet) y a la app (Firebase push).

```mermaid
flowchart LR
  subgraph Fuentes
    S[SENAMHI\nestaciones + avisos]
    A[ANA\ncaudales]
    I[IGP\nICEN]
    N[NOAA\nONI]
    C[CENEPRED\nSIGRID]
  end
  subgraph Ingesta
    K[Conectores\n1 por fuente]
    J[(Jobs horarios\ncron / APScheduler)]
  end
  DB[(PostgreSQL\n+ PostGIS)]
  M[Motor de umbrales\npor zona]
  API[API FastAPI]
  W[Web React+Leaflet]
  F[Firebase\npush geolocalizada]

  S & A & I & N & C --> K --> J --> DB
  DB --> M --> API
  API --> W
  M --> F
```

### 3.1. Convención de un conector

Cada módulo expone funciones puras que devuelven `@dataclass`/listas; **no** guardan estado
ni tocan la BD (de eso se encargan los jobs). Así son testeables y cacheables.

---

## 4. Verificación de "tiempo real" (importante)

No basta con asumirlo; se verificó contra la hora del sistema (Perú, UTC−5):

| Fuente | Endpoint | Última marca observada | Frecuencia | ¿Tiempo real? |
|---|---|---|---|---|
| SENAMHI (est. automática) | `map_red_graf.php` | `2026/09/06 - 21h` (hora en curso, 21:15) | horaria | **Sí** |
| ANA (caudales) | `ReporteNacionalCaudal` | `HORA` hasta `21:00` (RPT 592-2026) | ~horaria | **Sí** |
| IGP ICEN | `ICEN.txt` | mes en curso | mensual | contexto |
| NOAA ONI | `oni.ascii.txt` | trimestre en curso | mensual | contexto |

**Conclusión:** la lluvia (SENAMHI) y el caudal (ANA) se actualizan a la hora en curso —
suficiente para disparar alertas. ICEN/ONI son contexto estacional (El Niño), no gatillan
alertas inmediatas pero alimentan el modelo predictivo y el titular.

---

## 5. Conectores — referencia de endpoints

### 5.1. SENAMHI — estaciones y lluvia horaria

**Inventario de estaciones** (HTML con un array JS `PruebaTest` embebido):

```
GET https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/?dp=cajamarca
```
```js
{"nom":"AUGUSTO WEBERBAUER","cate":"MAP","lat":-7.1675,"lon":-78.49309,
 "ico":"M","cod":"107028","estado":"REAL"}
```
- `ico`: `M` meteorológica · `H` hidrológica.
- `estado`: `REAL` (convencional, 07/13/19h) · `DIFERIDO` · `AUTOMATICA` (**telemetría horaria** → las útiles para alertas).

**Serie horaria por estación** (config de Highcharts embebida en el HTML, **sin CAPTCHA**):

```
GET .../map_red_graf.php?cod={cod}&estado={estado}&tipo_esta={M|H}&cate={cate}&cod_old={cod_old}
```
El parser extrae `xAxis.categories` (timestamps `YYYY/MM/DD - HH`) y las `series[].data`
(precip mm/h y temp °C). **Gotcha:** los textos vienen con escapes `\uXXXX` del lado del
servidor; se busca por palabra clave antes del escape (`"Precipitaci"`, `"Temperatura"`).

```python
from backend.connectors import senamhi
autos = senamhi.estaciones_automaticas("cajamarca")
serie = senamhi.datos_horarios(autos[0])
print(serie.ultimo, serie.precip_acumulada(24))
```

> **Histórico bloqueado por CAPTCHA.** La pestaña "Tabla" (mensual, desde 2021-10) usa
> Cloudflare Turnstile y postea a `__dt_est_tp_0s3n@mH1.php`. **No se automatiza ni se evade.**
> Para series largas usar PISCO o la descarga oficial. El gráfico de 48 h sí es libre.

**Avisos meteorológicos** (tabla HTML, nivel amarillo/naranja/rojo):
```
GET https://www.senamhi.gob.pe/?p=aviso-meteorologico
```
Columnas: `Aviso · Nro · Emisión · Inicio · Fin · Duración · Nivel`. Filtrar títulos de
"SIERRA NORTE"/Cajamarca. (Conector pendiente — es scraping de tabla.)

### 5.2. ANA — caudales de ríos (inundaciones)

```
POST https://snirh.ana.gob.pe/onrh/ServicioReportes.asmx/ReporteNacionalCaudal
Content-Type: application/json; charset=UTF-8
body: {pTipoRPT:1, pFecha:"dd/mm/aaaa", pCodAAA:"00", pCodALA:"00", pCodUbigeo:"00"}
```
**Gotchas del ASMX:**
- El cuerpo **no** es JSON estándar (claves sin comillas) — es el string que arma la web.
  Un `{}` vacío devuelve **HTTP 500**; hay que mandar los 5 parámetros. `"00"` = todos.
- `pFecha` es `dd/mm/aaaa`. La respuesta llega como `{"d":[ ... ]}`.

Cada estación trae su **propio umbral** de alerta y emergencia:
```json
{ "DEPARTAMENTO":"Cajamarca","RIO":"Mashcon","ESTACION":"Mashcón",
  "VALOR":"0.13","UNIDADMEDIDA":"m³/s","UALERTA":"14.00","UEMERGENCIA":"18.00",
  "TENDENCIA":"Ascendente","HORA":"18:00","LONGITUD":"-78.4783","LATITUD":"-7.165" }
```
Estado de riesgo (implementado en `ana.EstacionCaudal.estado`):
```
VALOR ≥ UEMERGENCIA  -> emergencia
VALOR ≥ UALERTA      -> alerta
si no                -> normal   (s.d. si falta valor/umbral)
```
Cajamarca aporta ~12 estaciones (Mashcón —río de la ciudad—, Jesús Túnel, Namora Bocatoma,
Corral Quemado, Chotano, Puente Crisnejas, Yónan Gore, Cañad, …). Ojo: `UNIDADMEDIDA` puede
ser `m³/s` (caudal) **o** `m` (nivel).

**Capas del mapa** (visor por cuenca, para contexto/cruce):
```
POST .../VisorPorCuenca/ServicioGeneral.asmx/ListarMapaGEO   -> [{I,D,O,C:[lon,lat]}]
Visor: https://snirh.ana.gob.pe/VisorPorCuenca/?IdVar={N}
```
IdVar: `228` ríos · `46` embalses · `39` emergencias hídricas · `106` SAMAQ (activación de
quebradas/huaycos) · `220` puntos críticos. **39 y 106 son ideales para el cruce con
reportes ciudadanos.**

### 5.3. IGP — ICEN (contexto El Niño Costero)

```
http://met.igp.gob.pe/datos/ICEN.txt        # yy  mm  ICEN  (líneas '%' = comentario)
http://met.igp.gob.pe/datos/ICEN_91_20.txt  # base 1991-2020 (= base NOAA)
http://met.igp.gob.pe/datos/ICENr.txt       # ITCEN: valor reciente/provisional
```
> **HTTP-only** (Apache 2.2, puerto 80). Una web servida por HTTPS **no puede** hacer
> `fetch` a `http://` (mixed content). El **backend descarga y proxyea** el archivo (cachear
> a diario). Categorías del semáforo en `igp.categoria()`.

### 5.4. NOAA / CPC — ONI (contexto ENSO global)

```
https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt   # SEAS YR TOTAL ANOM (ANOM = ONI)
```
Texto plano, HTTPS, sin auth. La fuente más limpia. `anom ≥ 0.5` → El Niño; `≤ -0.5` → La Niña.

### 5.5. CENEPRED — SIGRID (peligro/riesgo, referencia)

Visor ArcGIS JS 3.41. Config del escenario:
```
POST https://sigrid.cenepred.gob.pe/sigridv3/entorno/traer
  -> { extension, mapa_base, shape(WKT), capas_activas:"cartografiaPeligros=[…];
       cartografiaRiesgos=[…]; elementosExpuestos=[…]" }
```
Capas servidas por **ArcGIS REST (MapServer/FeatureServer)** → `identify`/`query` o WMS.
Uso: capa de contexto de riesgo y para el **cruce** (¿el reporte cae en zona de peligro alto?).
No es tiempo real. *Pendiente:* capturar la URL exacta del MapServer activando una capa.

### 5.6. ENFEN — estado de alerta El Niño Costero

Sitio WordPress (`enfen.imarpe.gob.pe`). Vía: `GET /wp-json/wp/v2/posts?_fields=id,date,title,link`
(comunicados; PDFs por `?wpdmdl={id}`). El valor numérico del índice ya sale del IGP (5.3).
*Pendiente:* no fue accesible desde el entorno de captura (DNS/red); validar desde producción.

---

## 6. Motor de alertas y predicción

**Alertas (reactivas, tiempo real):** el motor compara, por zona de Cajamarca, las entradas
horarias contra umbrales:
- **Lluvia** (SENAMHI automáticas): umbral configurable por estación (mm/h y acumulado 24 h).
- **Caudal** (ANA): usa los umbrales `UALERTA`/`UEMERGENCIA` que la propia fuente entrega.
- **Aviso oficial** (SENAMHI): eleva el nivel cuando el aviso aplica a la zona.

El nivel resultante (normal/aviso/alerta/emergencia) alimenta el titular, el mapa y la push
(Firebase). En fase 2 se **cruza con los reportes ciudadanos** para ponderar su confianza
(un reporte en zona con alerta oficial pesa más).

**Predicción (fase 2+):** con la serie horaria histórica por estación (48 h de SENAMHI +
acumulación propia en la BD) se puede:
1. Empezar simple: **tendencia + umbral** (p. ej. precip acumulada creciente + pronóstico
   de aviso) → probabilidad de crecida en las próximas horas.
2. Luego un modelo de series de tiempo por estación (el ICEN/ONI entran como features de
   contexto estacional El Niño). Guardar histórico propio es clave: las fuentes solo dan
   ventanas cortas en tiempo real (SENAMHI 48 h) y el resto está tras CAPTCHA.

---

## 7. Persistencia, ingesta y API (prototipo)

El prototipo ya tiene el flujo completo **fuentes → ingesta → BD → API**, todo con la
librería estándar para que corra sin instalar nada.

**Persistencia** (`store.py`, SQLite en `backend/simpac.db`). Esquema (refleja el de PostGIS):

| Tabla | Contenido | Clave / dedup |
|---|---|---|
| `estacion` | inventario (cod, nombre, tipo, cat, estado, lat/lon) | `cod` (upsert) |
| `lectura_lluvia` | serie horaria precip/temp por estación | `(cod, ts)` |
| `lectura_caudal` | caudal por estación + umbrales + estado | `(estacion, fecha, hora)` |
| `indice` | último ONI / ICEN | `fuente` |
| `alerta` | alertas vigentes (se reescriben cada corrida) | autoincrement |

**Ingesta** (`ingest.py`): una pasada = inventario + lluvia (automáticas) + caudales +
índices + recálculo de alertas. Última corrida real: `93 estaciones, 672 filas de lluvia,
12 de caudal, 0 alertas` (estiaje). Programarla **cada hora**:

```bash
# Linux/mac (cron):     0 * * * *  cd /ruta/VigiaFEN && python backend/ingest.py
# Windows (Programador de tareas): acción -> python  argumento -> backend\ingest.py
```
Acumular estas pasadas es lo que construye el histórico propio para el modelo predictivo.

**API** (`api.py`, `http.server`, CORS abierto):

| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/api/snapshot` | contexto (ONI/ICEN) + resumen + alertas + caudales |
| GET | `/api/estaciones` | inventario de Cajamarca |
| GET | `/api/caudales` | última lectura por estación, con `estado` |
| GET | `/api/lluvia?cod=107028` | serie horaria de una estación |
| GET | `/api/alertas` | alertas vigentes |
| GET | `/api/contexto` | índices El Niño |

> **Migración a producción:** reemplazar `store.py` por PostgreSQL+PostGIS (mismas firmas) y
> envolver estas consultas en rutas **FastAPI** async. `api.py` (stdlib) es solo para ver el
> flujo hoy; no usarlo en prod (sin validación, sin auth, monohilo básico).

---

## 8. Despliegue con Docker (producción)

Stack completo en `docker-compose.yml` (4 servicios):

| Servicio | Qué es | Puerto |
|---|---|---|
| `frontend` | React build servido por **nginx** | 8080 |
| `backend` | API **FastAPI async** (`backend/app.py`) | 8000 |
| `worker` | **Celery + beat**: ingesta horaria + refresco de caché | — |
| `redis` | caché (snapshot) + cola/broker de Celery | 6379 |

### ¿Por qué esta arquitectura? (van a entrar varias personas a la vez)
- **Redis (caché):** con muchos usuarios no queremos que *cada* visita consulte Supabase y las
  fuentes. El worker deja un *snapshot* en memoria (Redis) y la API lo sirve en milisegundos; así
  la web no se satura ni nos rate-limitea SENAMHI/ANA en picos de tráfico.
- **Worker (Celery + beat):** bajar datos de las fuentes es lento y a veces falla (ANA es
  intermitente). Eso corre **en segundo plano**, aparte de la web, cada hora; si la ingesta tarda o
  falla, la web sigue rápida con lo último cacheado. `beat` es el "reloj" que dispara la tarea.
- **Backend async (FastAPI):** atiende muchas peticiones a la vez sin bloquearse esperando I/O
  (`async`/`await` + consultas en paralelo). Un backend síncrono se traba bajo concurrencia.
- **Redis también como cola/broker:** deja listo repartir tareas pesadas entre **varios workers**
  (p. ej. envío masivo de notificaciones push) sin bloquear la API.
- **Docker Compose:** los 4 servicios se levantan igual en cualquier máquina con un comando; para
  escalar se suben réplicas del backend/worker detrás del mismo Redis.

**Levantar:**
```bash
cp .env.docker.example .env      # pon SUPABASE_DB_URL (secreto) en .env
docker compose up --build
```
- Web en `http://localhost:8080`, API en `http://localhost:8000` (`/health`, `/api/snapshot`).
- El **worker** corre `store_supabase.run()` (nacional, concurrente con ThreadPool) cada hora y
  refresca el snapshot en Redis cada 5 min — sin cron (lo programa el **beat** de Celery).
- **Async / rendimiento:** la API es async (`httpx.AsyncClient` + `redis.asyncio`, consultas en
  paralelo con `asyncio.gather`) y sirve el snapshot **cacheado en Redis**, para aguantar varios
  usuarios sin golpear Supabase en cada request.
- El frontend recibe las llaves públicas por *build-args*; `SUPABASE_DB_URL` (secreto) solo lo usa
  el worker vía `.env` (nunca en git ni en la imagen).

---

## 9. Estrategia de adquisición y buenas prácticas

Orden de preferencia por estabilidad: **API/archivo abierto → API interna (sniffing) →
scraping HTML/PDF.**

| Fuente | Método | Nota |
|---|---|---|
| NOAA ONI | archivo abierto (HTTPS) | trivial |
| IGP ICEN | archivo abierto (**HTTP**) | proxyear desde backend |
| ANA caudal | API interna `.asmx` (POST JSON) | payload exacto, ver 5.2 |
| SENAMHI estaciones/serie | HTML con JSON/Highcharts embebido | scraping estructurado |
| SENAMHI avisos | scraping de tabla | pendiente |
| CENEPRED | ArcGIS REST | referencia |

Reglas:
- **Backend como proxy** siempre (evita CORS y mixed-content; obligatorio para IGP).
- **Caché + rate limit**: todo se actualiza por hora; no martillar los servidores del Estado.
- **User-Agent identificable**; revisar términos de uso y `robots.txt`.
- **Conectores aislados con tests**: las APIs internas cambian sin aviso.
- **Atribución visible** de la fuente en cada dato.
- **Nunca evadir CAPTCHA** (histórico de SENAMHI queda fuera de alcance).

---

## 10. Pendientes

- [ ] Conector de **avisos** SENAMHI (scraping de tabla + filtro Cajamarca).
- [ ] Conector **ENFEN** (`wp-json`) validado desde producción.
- [ ] URL exacta del **MapServer de CENEPRED** (enumerar capas de peligro por lluvia/inundación).
- [x] Persistencia + ingesta + API (prototipo SQLite/stdlib, sección 7).
- [ ] Migrar persistencia a **PostgreSQL + PostGIS** y programar el job horario en el servidor.
- [ ] Reescribir la API en **FastAPI** (auth, validación, paginación) sobre el mismo `store`.
- [ ] Conector de **push** (Firebase) que dispare la notificación cuando `alerta` cambie de nivel.
- [ ] Reejecutar la verificación en **temporada de lluvias (dic–abr)**, cuando disparan los umbrales.

---

*Endpoints capturados por inspección de red de sitios públicos el 2026-09-06. Sujetos a
cambios del lado de cada organismo; por eso cada fuente vive en su propio conector con tests.*
