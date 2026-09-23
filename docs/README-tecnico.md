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

El stack real corre en Docker (§8). Los conectores, el prototipo y las pruebas usan **solo la
librería estándar** de Python (3.10+), así que corren sin instalar nada (desde la raíz del repo):

```bash
python -m unittest discover -s backend/tests -t .   # pruebas sin red ni BD (solo stdlib)

python -m backend.prototipo.demo     # foto rápida en consola (sin BD)
python -m backend.prototipo.ingest   # guarda una pasada en backend/prototipo/simpac.db (SQLite)
python -m backend.prototipo.api      # API JSON del prototipo en http://localhost:8000
```

Salida esperada de `demo` (datos en vivo — foto de Cajamarca): contexto El Niño (RONI/ICEN),
caudales de ríos con su estado de alerta, y la lluvia horaria de una estación automática.

```
NOAA RONI  JJA 2026: +1.36  -> El Niño moderado
IGP  ICEN  2026-05: +1.98  -> Cálida moderada
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
│  │  ├─ _http.py        # helpers GET/POST/descarga binaria (urllib, sin deps)
│  │  ├─ senamhi.py      # estaciones + serie horaria (lluvia/temp)
│  │  ├─ ana.py          # caudales de ríos + estado de alerta por umbral
│  │  ├─ igp.py          # Índice Costero El Niño (ICEN)
│  │  ├─ noaa.py         # RONI (contexto ENSO global, índice oficial de NOAA desde feb-2026)
│  │  ├─ enfen.py        # comunicado oficial ENFEN (estado de alerta) + ICEN del Informe Técnico (PDF)
│  │  ├─ senamhi_avisos.py   # avisos oficiales de SENAMHI (tabla HTML + polígonos WFS + párrafos) y aviso de 24 h
│  │  ├─ senamhi_umbrales.py # lluvia de la última hora en ~216 estaciones (WFS) + fechas de prec_1
│  │  ├─ senamhi_pronostico.py # pronóstico oficial por localidad (una página HTML, ~277 localidades)
│  │  ├─ senamhi_nowcast.py  # nowcasting de lluvia (visor + WFS g_nowcasting), experimental
│  │  └─ idesep.py       # catálogo GeoNetwork de SENAMHI: shapefile -> GeoJSON (no lo importa __init__)
│  ├─ ingesta/
│  │  ├─ recolectar.py   # baja de todas las fuentes en paralelo -> Pasada (no toca la BD)
│  │  ├─ guardar.py      # escribe una Pasada en Supabase (una transacción)
│  │  ├─ departamentos.py # slugs de SENAMHI y nombres canónicos de departamento
│  │  ├─ enfen.py        # tarea 'enfen' (cada 6 h): comunicado + ICEN del Informe Técnico
│  │  ├─ avisos.py       # tarea 'avisos' (cada hora): áreas de avisos SENAMHI + ícono + alertas por departamento
│  │  ├─ lectura_aviso.py # puro: ícono del aviso y lectura de su texto (descargas, granizo, mm/día)
│  │  ├─ lluvia_nacional.py # tarea 'lluvia_nacional' (cada 30 min): lluvia de la última hora en el país + alertas de lluvia
│  │  ├─ pronostico.py   # tarea 'pronostico' (cada hora): pronóstico por localidad
│  │  ├─ lectura_pronostico.py # puro: qué dice cada día del pronóstico (lluvia, tormenta, "tendencia a")
│  │  └─ nowcast.py      # tarea 'nowcast' (cada 10 min): manchas de lluvia de las próximas 2 horas
│  ├─ data/
│  │  └─ localidades_senamhi.json # coordenadas de las localidades del pronóstico (revisado a mano)
│  ├─ mapas/
│  │  ├─ cargar_fen.py   # carga los mapas históricos de eventos El Niño a la tabla mapa
│  │  └─ semilla_localidades.py # arma localidades_senamhi.json (se corre una vez, §5.6.4)
│  ├─ prototipo/         # versión sin dependencias (SQLite + http.server), congelada
│  ├─ tests/             # pruebas sin red (unittest); muestras reales chicas en tests/muestras/
│  ├─ app.py             # API FastAPI async (Docker)
│  ├─ celery_app.py      # worker + beat (tareas programadas, §7.1)
│  ├─ config.py          # variables de entorno, en un solo lugar
│  ├─ db.py              # conexión a Supabase para quien escribe (worker, cargadores)
│  ├─ snapshot.py        # panorama cacheado en Redis que sirve la API
│  ├─ alerts.py          # motor de umbrales (caudal ANA + referencia de lluvia SENAMHI)
│  └─ requirements.txt   # + requirements-mapas.txt (geopandas, solo worker)
├─ frontend/             # React + Vite + Leaflet (ver frontend/README.md)
├─ supabase/
│  ├─ migrations/        # historia de la BD: un archivo por cambio, en orden
│  └─ schema.sql         # foto consolidada del estado final
└─ docs/
   ├─ README-tecnico.md          (este archivo)
   ├─ ESTADO.md                  (dónde estamos)
   ├─ catalogo-idesep.md         (catálogo de mapas de IDESEP)
   ├─ fuentes-y-endpoints.html   (catálogo visual de endpoints)
   └─ pre-documentacion-general.html
```

---

## 3. Arquitectura

Principio: **un conector aislado por organismo** que normaliza su fuente a estructuras
simples. La ingesta (Celery beat, cada hora) guarda en PostgreSQL/PostGIS (Supabase). La web
(React + Leaflet) lee **Supabase directo** con la llave pública, protegida por RLS. La API
(FastAPI) sirve un resumen cacheado en Redis para otros consumidores (app móvil, terceros).

```mermaid
flowchart LR
  subgraph Fuentes
    S[SENAMHI\nestaciones + avisos]
    A[ANA\ncaudales]
    I[IGP\nICEN]
    N[NOAA\nRONI]
    C[CENEPRED\nSIGRID]
  end
  subgraph Ingesta
    K[Conectores\n1 por fuente]
    J[(Ingesta horaria\nCelery beat)]
  end
  DB[(PostgreSQL\n+ PostGIS)]
  M[Motor de umbrales\npor estación]
  API[API FastAPI]
  W[Web React+Leaflet]
  F[Firebase\npush geolocalizada]

  S & A & I & N & C --> K --> J --> DB
  J --> M --> DB
  DB --> W
  DB --> API
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
| NOAA RONI | `RONI.ascii.txt` | trimestre en curso | mensual | contexto |
| ENFEN | comunicado + Informe Técnico (PDF) | quincenal / mensual | quincenal | estado oficial de alerta |

**Conclusión:** la lluvia (SENAMHI) y el caudal (ANA) se actualizan a la hora en curso —
suficiente para disparar alertas. ICEN/RONI son contexto estacional (El Niño), no gatillan
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

> **Las hidrológicas automáticas también miden lluvia horaria** (verificado el 22-09-2026 en 63
> estaciones, 10 de ellas en Cajamarca): la serie viene si se pide con `tipo_esta=M`; con
> `tipo_esta=H` viene vacía. El conector pide con el tipo de la estación y la ingesta solo baja las
> de tipo `M`, así que `lectura_lluvia` no las tiene (pendiente, §10). La tarea `lluvia_nacional`
> sí trae su última hora (§5.6.2).

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
Columnas: `Aviso · Nro · Emisión · Inicio · Fin · Duración · Nivel`. Conector y tarea en §5.6.1
(en todo el país, no solo Cajamarca).

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
umbrales de crecida (UEMERGENCIA >= UALERTA):     umbrales de NIVEL BAJO (UEMERGENCIA < UALERTA):
VALOR ≥ UEMERGENCIA  -> emergencia                VALOR ≤ UEMERGENCIA  -> emergencia
VALOR ≥ UALERTA      -> alerta                    VALOR ≤ UALERTA      -> alerta
si no                -> normal                    si no                -> normal
(s.d. si falta valor o umbral)
```
> **Gotcha de temporada:** en temporada seca ANA cambia, en algunos ríos amazónicos, a umbrales
> de **nivel bajo** (vaciante): el peligro es que el río baje (navegación). Se reconocen porque el
> de emergencia queda por debajo del de alerta. Ej. Enapu Perú (Iquitos): mar-jul 116.50/117.00,
> desde agosto 108.78/107.97. Leerlos como crecida daba "emergencia" falsa. Esas alertas son de
> tipo `nivel_bajo` y el mapa no dibuja zona de desborde. `RPT_PERIODO` no sirve para saberlo
> (dice "PERÍODO DE ESTIAJE" todo el año). ANA no publica el nivel amarillo que usa SENAMHI.
>
> El reporte de un día solo trae las estaciones que YA midieron ese día (de madrugada viene casi
> vacío): la ingesta pide ayer y hoy. Hay estaciones homónimas (San Pedro en el Charanal y en el
> Santa): la clave es (estación, río, fecha, hora).
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
> a diario).

Categorías en `igp.categoria()`, según la **Nota Técnica ENFEN 01-2024** (la que citan los
comunicados de 2026): neutra -0.7 a +0.5 · cálida débil hasta +1.3 · moderada hasta +2.1 · fuerte
hasta +3.5 · extraordinaria encima. Los cortes antiguos (2012: 0.4/1.0/1.7/3.0) fallaban en 6 de 11
meses. Para las condiciones frías el ENFEN usa percentiles sin cortes numéricos: se dice "Fría".

> **El IGP se atrasa:** en setiembre 2026 `ICEN.txt` seguía en mayo (Last-Modified 06-07-2026),
> mientras el ENFEN ya había publicado julio (+3.38) y un estimado de agosto (+3.73). La tabla
> `indice` guarda el mes más nuevo de los dos (columna `origen`: IGP o ENFEN).

**Serie mes a mes (`icen_serie`, para el gráfico de El Niño).** La ingesta horaria escribe los
últimos 36 meses del IGP y la tarea `enfen`, los meses de la tabla de cada Informe Técnico nuevo
(normalmente 12). Un mes del ENFEN nunca lo pisa el IGP; el IGP completa los meses que el ENFEN no
tiene. Nada se borra. La categoría de los meses del ENFEN es la oficial de su tabla; la de los
del IGP la calcula SIMPAC con `igp.categoria()`. Protecciones:
- Un mes posterior al mes anterior al actual (hora de Perú) se descarta: el IGP se baja por http
  y una fila futura quedaría para siempre en la serie y en `indice`.
- Si la tabla no tiene meses del ENFEN, o si la relectura encontró un informe más viejo que el
  leído (marca `serie_pendiente` en el latido `enfen`), se relee el informe vigente como mucho una
  vez cada 24 h.
- El campo `icen_serie` de los latidos cuenta meses insertados o cambiados, no enviados.

El estimado `ICEN_TMP` no entra en la serie (no es definitivo): el gráfico lo dibuja punteado.

### 5.3.1. ENFEN — comunicado oficial (estado del Sistema de Alerta)

El ENFEN publica cada ~2 semanas un comunicado en PDF con el **estado del Sistema de Alerta**
(Vigilancia / Alerta de El Niño o La Niña costeros, No activo) y la fecha del próximo. No hay API:
`connectors/enfen.py` descubre el último comunicado (gob.pe, SENAMHI, web ENFEN), baja el PDF y
extrae el texto con `pypdf` (solo en el worker). La tarea Celery `enfen` corre cada 6 h en el mismo
worker y beat de la ingesta (y una vez al arrancar), y guarda en `comunicado_enfen`.

Los comunicados no traen el valor del ICEN: sale de la Tabla 3 del **Informe Técnico ENFEN** (SENAMHI
y gob.pe, ~17 MB), que se escribe en `indice` como `ICEN` e `ICEN_TMP` con origen ENFEN.
- **Se baja solo si es un informe nuevo.** El latido `enfen` guarda el informe leído (`informe`):
  URL, fecha de publicación, número, portada y alias, que son otras URL del mismo informe. Una
  candidata con la misma URL o fecha de publicación no se baja, ni una más vieja. Si la portada
  resulta igual a la del leído, la URL queda como alias. Si es anterior, se descarta.
- **Informe que se bajó pero no sirve** (PDF ilegible, sin la tabla, meses fuera de rango): queda en
  `informe_fallido` y no se vuelve a bajar antes de 24 h. Los errores de red se reintentan en
  cada corrida.
- **Comunicado e informe son independientes:** si falla uno, el otro se guarda igual. La falla
  queda en `fallas` y `avisos` del latido. Si fallan los dos, la tarea termina en error.

Corrida suelta: `docker compose run --rm worker python -m backend.ingesta.enfen`.

### 5.4. NOAA / CPC — RONI (contexto ENSO global)

```
https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt   # SEAS YR ANOM (ANOM = RONI)
```
Texto plano, HTTPS, sin auth. **Desde febrero de 2026 el CPC vigila El Niño con el RONI** (el ONI
relativo al calentamiento de todo el trópico), no con el ONI clásico (`oni.ascii.txt`): en jun-ago
2026 el RONI daba +1.36 y el ONI +1.80. `≥ 0.5` El Niño, `≤ -0.5` La Niña; magnitud en pasos de
0.5 (débil, moderado, fuerte, muy fuerte ≥ 2.0). El CPC puede corregir un valor hasta 2 meses después.

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

Implementado: ver §5.3.1 (`connectors/enfen.py`). No se usa el `wp-json` del WordPress del ENFEN
(no existe su API REST y su DNS no resuelve desde Docker): el comunicado y el Informe Técnico se
descubren en gob.pe y SENAMHI y se leen del PDF con `pypdf`. El ICEN al día sale del Informe
Técnico (Tabla 3), no del comunicado ni del IGP (que se atrasa).

### 5.6.1. SENAMHI — avisos oficiales como áreas (tarea `avisos`)

`connectors/senamhi_avisos.py` + `ingesta/avisos.py`, cada hora y al arrancar el worker.
```
GET https://www.senamhi.gob.pe/?p=aviso-meteorologico          # tabla HTML: qué avisos están emitidos o vigentes
GET https://www.senamhi.gob.pe/?p=aviso-meteorologico-vigente&a=..&b=..   # párrafos oficiales: general y por día (opcional)
GET https://idesep.senamhi.gob.pe/geoserver/g_aviso/ows?service=WFS&request=GetFeature
    &typeName=g_aviso:view_aviso&viewparams=qry:{nro}_{mapa}_{año}&cql_filter=nivel<>'Nivel 1'
    &outputFormat=application/json                             # polígonos: un mapa por día de vigencia
GET https://idesep.senamhi.gob.pe/geoserver/g_prono_pp_24h/ows?...typeName=g_prono_pp_24h:view_aviso24h
    &cql_filter=nivel<>'Nivel 1'                               # aviso de lluvia de 24 h (rige desde las 13:00)
```
- **Niveles:** 2 amarillo, 3 naranja, 4 rojo (el 1 es "sin aviso" y cubre el resto del país).
- **Tabla `aviso_senamhi`:** una fila por aviso, mapa (día) y nivel. Los polígonos del mismo nivel
  se unen y se simplifican (0,005°) en SQL. Los departamentos salen de las estaciones que caen
  dentro (o de la más cercana a menos de 0,1°). La vista `aviso_vigente` da los que no terminaron,
  con el polígono en GeoJSON, ordenados por nivel (el rojo encima).
- **Alertas:** una por aviso de lluvia (vigente o que empieza en menos de 48 h, contando todas sus
  áreas) y por departamento, tipo `aviso`. Nivel 2 da `aviso`, 3 `alerta` y 4 `emergencia`. El
  detalle va en lenguaje claro ("Lluvias de ligera a moderada intensidad en la sierra norte, del
  23 al 24 set").
- **Nunca borrar por una fuente rota:**
  - Si la tabla cambia de formato (cabecera distinta, filas activas sin etiqueta), falla y no se
    borra nada.
  - Si el WFS de un aviso viene vacío o falla, se conserva lo guardado (falla `aviso N`).
  - Si el aviso de 24 h viene vacío, se confirma con una consulta liviana antes de borrarlo.
  - Las "ACTUALIZACIÓN DEL AVISO N" reemplazan al original.
  - Candado (`pg_advisory_xact_lock`) contra corridas simultáneas.
- Un aviso guardado hace menos de 6 h no se vuelve a bajar (sus polígonos no cambian), salvo que
  sea de lluvia y no tenga ícono: así, tras la migración de íconos, los avisos de lluvia se vuelven
  a bajar solos y quedan con ícono. Un texto que falta (el párrafo general o el de un día) se
  reintenta cada 6 h, con los polígonos, no en cada corrida: no se le pide a la GeoServer cada hora
  un aviso cuyo párrafo no está en la página.

**Íconos y lectura del texto** (migración `avisos_iconos`; `ingesta/lectura_aviso.py`, puro). Todo
es derivado y el frontend lo rotula "basado en el aviso de SENAMHI" junto a la cita literal. Cada
fila de `aviso_senamhi` suma cuatro columnas:
- **`texto_dia`**: el párrafo oficial de ese día (mapa), literal. La página de vigentes trae una
  pestaña por día; cada párrafo se empareja con su mapa por el iframe que lo sigue (`av`, `mp`,
  `fc`; los ids de las pestañas son internos y no sirven) **y además** su fecha ("El miércoles 23
  de setiembre...") tiene que coincidir con la del mapa: el número del día y, además, el mes o el
  nombre del día (SENAMHI a veces yerra el mes: el 377 de 2024 dice "sábado 14 de noviembre" en el
  mapa del sábado 14 de diciembre; sin mes, basta el número). Si no coincide (el 375 mapa 2 decía
  "martes 22" en el mapa del 24), queda `null` y el latido lo anota en `fecha_no_coincide`.
- **`icono`**: `gota`, `gota_rayo` o `copo` (`null` si no es de lluvia, llovizna ni nevada). Ningún
  campo del WFS dice tormenta: las descargas eléctricas salen solo del párrafo general.
  **Regla del rayo:** `gota_rayo` solo si el título nombra UNA región (costa, sierra o selva), el
  párrafo no nombra otra y afirma las descargas (no "no se descarta", "podría", "posible"... hasta
  el fin de la cláusula de las descargas: en "acompañadas de descargas eléctricas y ráfagas de
  viento, con velocidades que podrían alcanzar hasta los 50 km/h" se afirman). En
  un aviso de varias regiones la frase puede valer para una sola (el 376, "sierra norte y costa
  norte", las dice solo para la sierra), y sin una capa de regiones no se sabe a qué parte va: lleva
  gota y el popup cita la frase. Sin párrafo general también es gota: el rayo nunca se inventa. El
  aviso de 24 h siempre es gota. Sobre 439 avisos de 2024 a 2026: 245 gota con rayo, 182 gota, 12
  copo.
- **`lectura`** (jsonb, `v = 1`): fenómeno, dónde, intensidad, regiones, `descargas`
  (`si`/`condicional`/`no`) con su frase literal, granizo y nieve (con la altura, "2 800" = 2800),
  ráfagas y `montos`. `null` en un aviso de lluvia = aún no se leyó su párrafo general: se
  reintenta cada 6 h.
  **Montos por día, "todo o nada":** "hasta los 12 mm/día en Tumbes, cercanos a los 6 mm/día en la
  costa de Piura y valores entre los 7 mm/día y 15 mm/día en la sierra norte" da Tumbes hasta 12,
  Costa de Piura cerca de 6 y Sierra norte de 7 a 15. Si un solo monto no se entiende, no tiene
  lugar claro, el lugar tiene cifras, un día de la semana o una frase que no es lugar ("en
  promedio", "en horas de la tarde"), un rango va al revés, o sobra un número (salvo los de la
  fecha: en "20, 30 y 40 mm/día en la selva norte, centro y sur" el 20 queda suelto), el párrafo
  entero queda en `null` y el frontend muestra la cita literal (nunca un monto en otro lugar).
  Sobre 1027 párrafos se lee el 92% (945), sin ningún lugar mal atribuido.
- **`anclas`**: dónde va la insignia: una por parte del MultiPolygon de 300 km² o más (y siempre la
  más grande), en el centro del mayor círculo inscrito (`st_maximuminscribedcircle`; el centroide
  de una parte en forma de C cae afuera), con `radio_km` para que el frontend oculte la de una parte
  que en pantalla se ve chica. Se calculan en el mismo `insert` (y la migración llena las de las
  filas ya guardadas). Van también en los avisos de calor, frío y viento.

Si la tabla no tiene aún esas columnas, la tarea guarda los avisos igual, sin íconos
(`SQL_PREVIOS_V1`, `SQL_AREA_V1`), y el latido avisa "falta la migración de íconos": los avisos
oficiales nunca dejan de actualizarse. Si la página de vigentes cae, se conservan los textos ya
guardados. El latido `avisos` suma la clave `lectura` (`null` sin la migración):

| Clave | Qué es |
|---|---|
| `iconos` | ícono de cada aviso escrito: `{"376": "gota", "24h": "gota"}` |
| `fecha_no_coincide` | `"aviso 375 mapa 2"`: párrafo de otro día, no se guardó |
| `mm_literal` | con párrafo del día pero sin montos leídos: el popup lo muestra literal |
| `sin_general` | avisos de lluvia sin párrafo general (van con gota; se reintentan cada 6 h) |

### 5.6.2. SENAMHI — lluvia de la última hora en todo el país y alertas de lluvia (tarea `lluvia_nacional`)

`connectors/senamhi_umbrales.py` + `ingesta/lluvia_nacional.py`, cada 30 min (las estaciones
reportan cada hora, pero no todas a la misma hora).
```
GET https://idesep.senamhi.gob.pe/geoserver/g_umbrales/ows?service=WFS&request=GetFeature
    &typeName=g_umbrales:umbrales_precipitacion&outputFormat=application/json
```
~216 estaciones automáticas de 24 departamentos (25 en Cajamarca), una petición de ~90 KB. Entre
ellas hay hidrológicas automáticas que la ingesta horaria no baja (§5.1). Campos: `pp` = mm de la
hora; `pp_acum` = **las últimas 6 h** (no el día; verificado contra las series horarias);
`umbral` = referencia de SENAMHI por estación (1 a 25 mm/h, no documentado como umbral oficial de
alerta) y `umb_acum` = la de 6 h (3 × `umbral` en las 216). Tabla `lluvia_senamhi` (una fila por
estación, con `pp_1h`, `umbral_1h`, `pp_6h` y `umbral_6h`; una lectura más vieja no pisa a la
guardada) y vista `lluvia_senamhi_actual` (solo las de las últimas 3 h).

**Alertas de lluvia** (tipo `lluvia`). Las escribe solo esta tarea, en todo el país; la ingesta
horaria ya no las evalúa ni las borra. Regla en `alerts.py` (`evaluar_lluvia_referencia`):
- **Cuándo pasa:** `pp_1h > umbral_1h` o `pp_6h > umbral_6h`, siempre mayor estricto (igual a la
  referencia no pasa). Solo se evalúa la estación que trae `pp_1h` y `umbral_1h > 0`; sin eso
  tampoco se mira la de 6 h. El frontend usa la misma regla (`referenciaLluvia` en `lenguaje.js`).
- **Una fila por estación:** `ventana_h` = 1 si pasó la de 1 h (aunque pase también la de 6 h), si
  no 6; `valor` y `umbral` son los de esa ventana. `referencia` = `lluvia_senamhi.clave`, `zona` =
  departamento (null = resto del país), `geom` = punto de la estación, `ts` = hora de la medición.
- **Nivel siempre `aviso`**, asegurado en tres lugares: literal en el INSERT, restricción
  `alerta_lluvia_referencia_check` en la BD y tope en el frontend (`nivelEfectivo`). En la interfaz
  se rotula "Atentos a la lluvia". La referencia no está documentada como umbral de alerta (la
  palabra "Alerta" solo aparece en la leyenda del visor, y ese estado cambia con el reloj) y,
  según las curvas IDF de SENAMHI, se supera casi cada año en 2 de cada 3 estaciones (20 de 25 en
  Cajamarca). El detalle termina en "Es lo que midió la estación, no un aviso oficial." y nunca dice
  "fuerte", "intensa", "alerta", "emergencia", "peligro" ni "extrema".
- **Reemplazo:** en la misma transacción, después del upsert, se leen de la BD las estaciones con
  `medido_en` de las últimas 3 h (también las que no vinieron en esta corrida; si la BD guarda una
  lectura más nueva que la de la capa, manda la de la BD), se borran todas las `tipo='lluvia'` y se
  insertan las que pasan. El candado `pg_advisory_xact_lock(hashtext('lluvia_nacional'))` es la
  primera sentencia de la transacción, siempre (también con la capa caída): pone en serie el beat y
  una corrida suelta, y también la lectura y escritura del latido. El índice único
  `alerta_lluvia_referencia_key` (una por estación) hace que un error falle en vez de duplicar.
- **No se toca ninguna** si la capa está caída o vacía, si no trae lecturas vigentes, si ninguna
  estación es evaluable o si falta la migración (se mira con `to_regclass` de ese índice). En los
  dos últimos casos queda un aviso en el latido (no una falla) y `lluvia_senamhi` se escribe igual.
- **Vigencia:** la vista **`alerta_actual`** (la que leen el frontend y el snapshot) muestra la
  lluvia solo mientras su `ts` tenga 3 h o menos, igual que `lluvia_senamhi_actual`: si el worker se
  detiene, desaparecen solas. También oculta las filas `lluvia` sin `ventana_h` (formato viejo).
- **UNC CAJAMARCA** (472645F0), una de las 14 de `lectura_lluvia`, no está en la capa y no tiene
  referencia: queda fuera de las alertas y de la cobertura, y sigue en el resumen de 24 h.

Claves del latido `lluvia_nacional` para las alertas. Van siempre (que existan indica worker
nuevo). El frontend solo dice "ninguna pasa la referencia" si `alertas` no es nulo (esa corrida de
verdad evaluó) y su consulta a `lluvia_senamhi_actual` respondió; la frase del resto del país,
además, solo si hay estaciones evaluables fuera de la zona.

| Clave | Qué es |
|---|---|
| `evaluadas` | estaciones vigentes en la BD, después del upsert, con `pp_1h` y referencia mayor que 0 |
| `alertas` | filas `tipo='lluvia'` escritas; `null` = en esta corrida no se tocaron |
| `alertas_6h` | de esas, las que pasaron solo por las 6 h |
| `sobre_umbral` | vigentes del lote de la capa con `pp_1h > umbral_1h` (solo 1 h; no son las alertas) |

`fallas` puede traer `"umbrales"` (capa caída, vacía o sin lecturas vigentes) y el panel lo avisa:
"la lluvia de la última hora puede estar atrasada".

**Despliegue** (migración `alerta_lluvia_referencia_senamhi`), en este orden:
1. La migración, que es aditiva: el frontend viejo sigue leyendo `alerta`, que hoy no tiene filas
   de lluvia.
2. El frontend: lee `alerta_actual` y, mientras el latido no traiga `alertas`, dice "No se pudo
   revisar la lluvia…", que es cierto.
3. Worker y API (reconstruir las dos imágenes, §8). La primera corrida, que se encola al arrancar,
   borra todas las `tipo='lluvia'` e inserta las nuevas.

Si el worker se adelanta a la migración no rompe: se salta las alertas con aviso. Lo que no puede
adelantarse es el worker al frontend: el frontend viejo describiría las nuevas como "lluvia fuerte"
o con "umbral referencial de SIMPAC". Control después del despliegue (los dos números iguales, y
`count(*)` igual a `latido.alertas`):
```sql
select count(*), count(distinct referencia) from alerta where tipo = 'lluvia';
```

**Fechas de la lluvia observada** (capas WMS `prec_1` y `prec_1_ac07d` que el frontend pide
directo): salen del visor `monitoreo-precipitacion.php` y van al latido (`prec_1`,
`prec_1_ac07d`, `prec_1_ac07d_desde`). "prec_1 del 21 set" es la lluvia de las 07:00 del 21 a las
07:00 del 22. El visor calcula la fecha con el reloj, así que de madrugada anuncia un día que
SENAMHI aún no procesó: se compara una huella de `prec_1_all_points` y, si no cambió, se conserva
la fecha anterior (`prec_1_pendiente`). Si el visor cae, se conservan las fechas del latido
anterior.

### 5.6.3. Capas de mapa que el navegador pide directo (sin worker)

| Capa | Servicio | Nota |
|---|---|---|
| Lluvia de ayer / 7 días | WMS `monitoreo_meteorologico:prec_1`, `prec_1_ac07d` | estilo propio por `sld_body` (ColorMap, transparente bajo el primer corte) |
| Quebradas que podrían activarse | WMS `silvia:cuencas_nivel_12_prono1_silvia` | pronóstico SILVIA por microcuenca, niveles 2 y 3 |
| Lluvia por satélite | NASA GIBS WMTS `IMERG_Precipitation_Rate_30min` | `.../epsg3857/best/.../default/{Time}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png`, zoom nativo máx. 6, 5-6 h de retraso |

La GeoServer de SENAMHI es intermitente (3 a 8 s por imagen): si falla, la capa lo avisa. GIBS
anuncia a veces en `default` una hora que aún no publicó (404 al pedirla): el frontend la
confirma y retrocede de a 30 min.

> **Licencia SENAMHI** (https://www.senamhi.gob.pe/?p=terminos-condiciones): uso libre sin
> comercializar, con la leyenda literal "Información recopilada y trabajada por el Servicio
> Nacional de Meteorología e Hidrología del Perú. El uso que se le da a esta información es de mi
> (nuestra) entera responsabilidad" en todo soporte. Los polígonos simplificados se rotulan
> "basado en el aviso de SENAMHI" y enlazan al original. Los términos dicen también que la página
> es "para el uso personal y del usuario": conviene mencionarlo al presentar el proyecto.

### 5.6.4. SENAMHI — pronóstico oficial por localidad (tarea `pronostico`)

`connectors/senamhi_pronostico.py` + `ingesta/lectura_pronostico.py` + `ingesta/pronostico.py`,
cada hora y al arrancar el worker (migración `pronostico_localidad`).
```
GET https://www.senamhi.gob.pe/?p=pronostico-meteorologico      # una página de ~770 KB con todo el país
```
- **Qué trae:** ~277 localidades (17 en Cajamarca), cada una con 3 a 5 días: el ícono que eligió
  el pronosticador, máxima, mínima y un texto ("Cielo nublado parcial variando a cielo nublado...
  con lluvia."). La emisión ("Emisión: martes, 22 de septiembre del 2026") no tiene hora: sale una
  por día hábil, de noche; en fines de semana y feriados sigue la del último día hábil.
- **Una página cambiada falla, no se lee como "sin pronóstico"** (`ValueError`, no se escribe
  nada): sin emisión o con una posterior a hoy, con menos de 200 o más de 400 localidades
  legibles, o con más del 10% de los bloques sin entender. Un bloque cuyo número de fechas no
  coincide con los días leídos va a `problemas` entero. Temperaturas fuera de −30 a 50 °C, o una
  mínima mayor que la máxima, van como `null`. La página viene en UTF-8: un byte dañado se
  reemplaza (y se anota en `problemas`) sin pasar la página entera a Windows-1252, que solo se usa
  si casi nada se lee como UTF-8.
- **Tabla `pronostico_localidad`:** una fila por localidad y día, upsert por `(codigo, fecha)`. Una
  emisión más vieja no pisa una más nueva (`where excluded.emision >= pronostico_localidad.emision`);
  la misma sí se reescribe. Solo se borran las fechas pasadas (hoy se conserva todo el día). Con la
  página caída, o con el catálogo ilegible (las filas irían sin punto y pisarían los guardados), no
  se escribe ni se borra nada. La vista **`pronostico_vigente`** da hoy, mañana y
  pasado (hora de Perú), solo las localidades ubicadas y de una emisión de 5 días o menos, con el
  enlace a la página de la localidad.
- **Es un punto por localidad**, no un área: el frontend nunca sombrea el distrito, y donde no hay
  localidad no dice nada (no quiere decir que no llueva).

**Qué dice cada día** (`clasificar(icono, texto)`, el texto manda y el ícono solo suma o pone en
duda: SENAMHI usa sus íconos con libertad), en orden:
1. Negación ("sin lluvias", "no se prevén lluvias") → `sin_lluvia`.
2. Texto con tormenta, descargas, truenos o relámpagos → `tormenta`.
3. Texto con nieve, o granizo sin lluvia → `nieve`.
4. Texto con lluvia: con el ícono de tormenta (010, 011, 037) → `tormenta` posible (`por = 'icono'`;
   `lluvia_segura` si la lluvia no va bajo "tendencia a"); si no → `lluvia`.
5. Solo el ícono de lluvia, tormenta o nieve (006–017, 035–037) → `lluvia` posible (`por = 'icono'`).
6. Si no → `sin_lluvia` con el `cielo` (despejado, parcial, nublado, neblina).

`posible` también es verdadero si la palabra queda bajo "tendencia a" (sin CON, `;`, `.` ni
VARIANDO en medio): el frontend lo dibuja punteado y dice "puede llover". `momento` es la frase de
hora pegada a la palabra ("en la tarde"); "durante el día" no cuenta, porque describe el cielo.
Verificado con la emisión del 22-09 para el 23-09: Cajamarca 7 lluvia, 6 "puede llover", 4 sin
lluvia; el país 57 / 42 / 4 tormenta posible / 174.

**Catálogo de coordenadas** (`backend/data/localidades_senamhi.json`, revisado a mano; es `.json`
porque el `.dockerignore` excluye los `*.geojson`). La página no trae coordenadas: cada localidad
casi siempre coincide con una estación meteorológica de SENAMHI del mismo nombre y departamento.
Hoy tiene 236 de 277 localidades con punto (213 por estación, 23 por el centro de la ciudad),
entre ellas las 17 de Cajamarca y las 25 ciudades del selector (24 códigos: Lima y Callao comparten
`15-0001`). Las 41 que no se ubicaron están en la clave `sin_ubicar`: se guardan con `lat` nula, la
vista no las muestra y el latido las lista. La tarea descarta un punto fuera del Perú con un aviso
y avisa si SENAMHI cambió el nombre de un código (el punto se usa igual).

Se arma **una vez** (o cuando SENAMHI sume localidades) con `backend/mapas/semilla_localidades.py`,
con red y BD (solo lee `estacion`): empareja por nombre normalizado en el mismo departamento,
prefiere las convencionales (CO, CP, MAP), usa `ALIAS` (Cajamarca = AUGUSTO WEBERBAUER, San Miguel
de Pallaques = la CO San Miguel) y `MANUAL` (ciudades sin estación homónima, con
`ubicacion: "ciudad (centro aproximado)"`), e imprime las no resueltas y las que tenían varias
estaciones posibles. Su salida se revisa y se sube al repo: la tarea nunca inventa un punto.
Montando el repo para que el archivo quede en el host (PowerShell; en Git Bash, `$PWD` y
`MSYS_NO_PATHCONV=1` como en §5.7):
```powershell
docker compose run --rm -v "${PWD}:/app" worker python -m backend.mapas.semilla_localidades
# --html ARCHIVO: lee una página guardada en vez de bajarla · --salida RUTA: otro destino
```

Claves del latido `pronostico`:

| Clave | Qué es |
|---|---|
| `emision` | fecha de la emisión leída (`null` si la página falló) |
| `localidades` | localidades legibles de la página |
| `filas` / `escritas` | días enviados al upsert (desde hoy) / filas de verdad escritas (menos si la BD ya tenía una emisión más nueva) |
| `purgadas` | filas de fechas pasadas borradas |
| `sin_ubicacion` | localidades sin punto en el catálogo (máx. 30) |
| `problemas` | bloques o días de la página que no se entendieron (máx. 20) |
| `cajamarca`, `pais` | `{fecha: {lluvia, posible, tormenta, nieve, sin_lluvia}}` (`posible` = "puede llover") |
| `fallas` | `pagina` (caída o ilegible) o `catalogo` (no se pudo leer): no se escribe nada y la tarea termina en error después de escribir el latido; `migracion` (falta la tabla) |
| `avisos` | detalle; si la emisión tiene más de 3 días: "SENAMHI no publica un pronóstico nuevo desde el ..." |

Corrida suelta: `docker compose run --rm worker python -m backend.ingesta.pronostico`.

### 5.6.5. SENAMHI — nowcasting de lluvia, experimental (tarea `nowcast`)

`connectors/senamhi_nowcast.py` + `ingesta/nowcast.py`, cada 10 min y al arrancar el worker
(migración `nowcast_senamhi`). SENAMHI no lo documenta; todo se verificó en vivo el 22-09-2026.
```
GET https://www.senamhi.gob.pe/mapas/mapa-nowcasting/nowcasting-pronostico-1h.php   # visor: última emisión
GET https://idesep.senamhi.gob.pe/geoserver/ows?service=WFS&version=2.0.0&request=GetFeature
    &typeNames=g_nowcasting:view_nowcasting&outputFormat=application/json
    &viewparams=fichero:{fichero}&CQL_FILTER=nivel>0&propertyName=nivel,fecha1,fecha2,fichero,geom
```
- **Qué es:** manchas de celdas de ~2 km con lluvia de nivel 1, 2 y 3 (moderada, fuerte y extrema
  según la leyenda del visor) para ahora (análisis), +1 h y +2 h. SENAMHI lo llama "producto
  referencial y aún en etapa de calibración": el frontend lo rotula **Experimental**, en azules y
  violeta (nunca los colores de los avisos) y sin rayos (el texto por nivel del visor es la
  plantilla del aviso de 24 h, no un dato de rayos).
- **Ficheros:** el visor trae el último en `var fichero = "nowcasting_20260922-2040_forecast_..."`
  (hora de Lima). De la emisión T salen tres: `nowcasting_{T}_analysis_{T}_web` (ahora) y
  `nowcasting_{T}_forecast_{T+1h}_web` / `_{T+2h}_web` (cruzan la medianoche). La validez sale de
  `fecha1`/`fecha2` (UTC): [T, T] el análisis, [T, T+1 h] el +1 h y [T, T+2 h] el +2 h, así que
  "en 2 horas" es "entre T y T+2 h".
- **Trampas:** sin `viewparams` la capa da 0 elementos. En WFS 2.0 el BBOX del CQL va en orden
  lat,lon y al revés devuelve 0 elementos sin error: no se usa BBOX; se recorta al Perú en SQL
  (`st_intersects` con el recuadro, la mancha que cruza la frontera se guarda entera) y se
  controla el orden de ejes del primer vértice. Un XML de excepción con HTTP 200 es falla, no "sin
  manchas". Una respuesta filtrada vacía se confirma con una consulta sin filtro de un elemento: si
  también viene vacía, el fichero aún no existe (`ProductoNoPublicado`, falla de ese horizonte).
  Con peticiones en paralelo la GeoServer corta: todo va en serie, con 1,5 s de pausa.
- **Tablas:** `nowcast_producto` (una fila por horizonte, upsert: una emisión más vieja no pisa) y
  `nowcast_mancha` (una fila por horizonte y nivel, con la unión de las manchas simplificada a
  ~330 m). Una emisión ya guardada no se vuelve a pedir: si SENAMHI no publicó nada nuevo, la
  corrida solo lee el visor.
- **Umbral de 30 min:** vive **solo** en las vistas. `nowcast_estado` da cada producto con
  `vigente` y `vence_en`; `nowcast_vigente` da las manchas solo si la emisión tiene 30 min o menos.
  Nada se borra por una falla ni por antigüedad: cuando SENAMHI se detiene (el 22-09 no publicó
  nada desde las 20:40 hasta pasadas las 23:25), el mapa se vacía solo y el chip dice desde cuándo.
  El frontend no recalcula el umbral.
- **Tiempos:** la tarea tiene 240 s (`soft_time_limit`); cada pedido al WFS se intenta 2 veces y,
  pasados 90 s desde el inicio, no se pide otro horizonte (queda como falla `hNN`), así que el
  latido se escribe siempre. En el beat va con `expires` de 540 s: si la cola se atrasa, una
  corrida vieja se descarta en vez de juntarse con la siguiente.

Claves del latido `nowcast`:

| Clave | Qué es |
|---|---|
| `emision`, `edad_min` | T según el visor (hora de Perú) y sus minutos de antigüedad (`null` si el visor falló) |
| `bajados`, `reusados` | horizontes bajados y escritos / que ya tenían T (o una más nueva) guardada |
| `manchas` | `{"60": 62}`: elementos de nivel 1 a 3 que tocan el Perú, de los bajados |
| `retraso_min` | edad de T cuando se bajó algo: cuánto tarda SENAMHI en publicar (para calibrar los 30 min) |
| `detenido` | la emisión tiene más de 30 min; si el visor respondió no es falla, va a `avisos` ("SENAMHI no publica el nowcasting desde las 20:40") |
| `fallas` | `visor` (caído, sin fichero o con hora futura; la tarea termina en error después del latido), `h0` / `h60` / `h120` (ese horizonte no se bajó y su fila no se toca), `migracion` |

Corrida suelta: `docker compose run --rm worker python -m backend.ingesta.nowcast`.

### 5.6.6. Diagnóstico de avisos, pronóstico y nowcasting (solo lectura)

```sql
-- íconos y anclas de los avisos de lluvia (hoy: 376 mapa 1 -> gota, 2 anclas)
select numero, mapa, nivel, icono, jsonb_array_length(anclas), lectura->'montos'
from aviso_vigente where tema = 'lluvia';
-- pronóstico de hoy: filas y cuántas sin ubicar
select count(*), count(*) filter (where lat is null) from pronostico_localidad
where fecha = (now() at time zone 'America/Lima')::date;
select tipo, posible, count(*) from pronostico_vigente
where fecha = (now() at time zone 'America/Lima')::date group by 1, 2;
-- nowcasting: emisión, validez y si sigue vigente
select * from nowcast_estado;
-- latidos de las tres tareas
select servicio, ts, resumen->'fallas', resumen->'avisos' from latido
where servicio in ('avisos', 'pronostico', 'nowcast');
```
Además, en el *advisor* de Supabase: RLS activo en las tablas nuevas y las vistas con
`security_invoker`.

### 5.7. IDESEP (SENAMHI) — mapas históricos de eventos El Niño

IDESEP es el catálogo GeoNetwork de SENAMHI. Conector: `backend/connectors/idesep.py`.
```
GET https://idesep.senamhi.gob.pe/geonetwork/srv/eng/csw?service=CSW&request=GetRecords&...
    -> catálogo paginado (dc:identifier = uuid, dc:title = título)
GET https://idesep.senamhi.gob.pe/geonetwork/srv/api/0.1/records/<uuid>
    -> página HTML con el enlace al .zip del shapefile (dentro de /attachments/)
```
El .zip se convierte a GeoJSON (EPSG:4326) con **geopandas**, que se importa solo dentro de
`geojson_de_registro()`. `idesep` no se importa desde `connectors/__init__.py`, así los demás
conectores siguen sin dependencias. Los 5 eventos cargados tienen su **uuid fijo** en
`EVENTOS_FEN` (`cargar_fen.py`); para sumar uno nuevo basta su título, que se busca en el catálogo
de forma normalizada (sin distinguir mayúsculas, tipo de guion ni espacios). Solo se descargan
adjuntos del propio `idesep.senamhi.gob.pe` por HTTPS, con tope de 80 MB y reintentos ante fallas
de red (los errores 4xx no se reintentan).

Mapas cargados en la tabla `mapa` con `variable='FEN'` (el mensual usa `variable='precipitacion'`):

| Evento | periodo | Polígonos |
|---|---|---|
| El Niño 82-83 | 1982-1983 | 2620 |
| El Niño 97-98 | 1997-1998 | 1694 |
| El Niño Costero 2017 | 2017 | 1590 |
| El Niño Costero 2023 | 2023 | 944 |
| El Niño 2023-2024 | 2023-2024 | 2197 |

Cada feature trae solo la propiedad `RANGO` (rango de anomalía en texto, p. ej. `"-120 - -60"`).
Cobertura nacional; pesan hasta ~5.5 MB cada uno (0,3 a 0,9 MB con `--simplificar 0.005`).

> **Ojo: son de un trimestre, no de todo el evento.** Cada registro de IDESEP trae un .zip por
> trimestre (p. ej. 1997-98: DEF 1997-1998, EFM 1998 y FMA 1998) y `geojson_de_registro()` toma
> el primero. Quedaron cargados diciembre a febrero (1982-83, 1997-98, 2017, 2023-24) y enero a
> marzo (2023). El frontend rotula cada evento con sus meses. Pendiente: cargar los demás
> trimestres y dejar elegirlos.

**Carga** (única vía de escritura; son mapas estáticos, no van en la ingesta horaria):
```bash
docker compose run --rm worker python -m backend.mapas.cargar_fen            # prueba en seco
docker compose run --rm worker python -m backend.mapas.cargar_fen --aplicar  # upsert por uuid
```
Opciones: `--simplificar 0.005` (aligerar geometrías), `--decimales 5`, `--exportar DIR`
(GeoJSON para `backend/mapas/visor_geojson.html`), `--catalogo` (lista uuid + título).
El upsert usa el índice único `mapa_uuid_key`, así que correrlo varias veces no duplica filas.
Sale con código 1 si algún evento falla o no aparece en el catálogo.

Para `--exportar` dentro de Docker hay que montar una carpeta del host (con `--rm` el contenedor
se borra y los archivos con él). En PowerShell:
```powershell
docker compose run --rm -v "${PWD}/backend/mapas:/out" worker python -m backend.mapas.cargar_fen --exportar /out
```
En Git Bash hay que desactivar la conversión de rutas de MSYS (si no, `/out` se vuelve
`C:/Program Files/Git/out`):
```bash
MSYS_NO_PATHCONV=1 docker compose run --rm -v "$PWD/backend/mapas:/out" worker python -m backend.mapas.cargar_fen --exportar /out
```
geopandas solo está en la imagen del **worker** (`requirements-mapas.txt`, build arg
`INSTALAR_MAPAS=1`); la imagen de la API no lo trae.

> **Legal:** los GeoJSON de SENAMHI ya no se guardan en el repo (`backend/mapas/*.geojson` está en
> `.gitignore` y `.dockerignore`), aunque el archivo que se subió antes sigue en el historial de git
> hasta el commit `aaf5aaa`; borrarlo de ahí requiere reescribir el historial (decisión del equipo).
> Los mapas viven en la tabla `mapa`, que es de **lectura pública** vía la API de Supabase (como el
> resto de datos oficiales), siempre con la atribución a SENAMHI/IDESEP.

---

## 6. Motor de alertas y predicción

**Alertas (reactivas, tiempo real):** el motor (`alerts.py`, puro y sin red) compara cada
lectura, estación por estación y en todo el país, con el umbral que da la propia fuente:
- **Caudal** (ANA): usa los umbrales `UALERTA`/`UEMERGENCIA` que la propia fuente entrega (de
  crecida o de nivel bajo). Lo evalúa la ingesta horaria.
- **Lluvia** (SENAMHI automáticas): la referencia de SENAMHI de cada estación (capa `g_umbrales`),
  en la última hora o sumando las últimas 6 h (§5.6.2). Nivel siempre `aviso`, con el rótulo
  "Atentos a la lluvia". **No es un aviso oficial**: es lo que midió una estación. Lo evalúa la
  tarea `lluvia_nacional`.
- **Aviso oficial** (SENAMHI): eleva el nivel cuando el aviso aplica a la zona.

Se retiraron los umbrales provisionales de SIMPAC para la lluvia (20 y 40 mm en 24 h, 15 mm en
1 h): eran los mismos en todo el país y no se ajustaban a cada lugar (20 mm en 24 h es lluvia
normal en la selva).

Los avisos de SENAMHI llegan como alertas tipo `aviso` (§5.6.1): amarillo = `aviso`, naranja =
`alerta`, rojo = `emergencia`. El nivel resultante (normal/aviso/alerta/emergencia) alimenta el
titular, el mapa y la push (Firebase). La lluvia medida va aparte de lo oficial:
- Si la zona está en `aviso` solo por lluvia medida, el rótulo es "Atentos a la lluvia"; con un
  aviso amarillo de SENAMHI además, "Aviso amarillo".
- No cuenta en la insignia ni en la métrica "alertas y avisos" (en temporada de lluvias serían
  decenas de estaciones).
- **No dispara una push como alerta**: el snapshot la marca `oficial: false` (§8).

En fase 2 se **cruza con los reportes ciudadanos** para ponderar su confianza (un reporte en zona
con alerta oficial pesa más).

**Predicción (fase 2+):** con la serie horaria histórica por estación (48 h de SENAMHI +
acumulación propia en la BD) se puede:
1. Empezar simple: **tendencia + umbral** (p. ej. precip acumulada creciente + pronóstico
   de aviso) → probabilidad de crecida en las próximas horas.
2. Luego un modelo de series de tiempo por estación (el ICEN/RONI entran como features de
   contexto estacional El Niño). Guardar histórico propio es clave: las fuentes solo dan
   ventanas cortas en tiempo real (SENAMHI 48 h) y el resto está tras CAPTCHA.

---

## 7. Persistencia, ingesta y API

### 7.1. Producción (Supabase + worker)

**Ingesta** (`backend/ingesta/`, la corre el worker cada hora):
1. `recolectar()` baja, en paralelo, el inventario de los 24 departamentos de SENAMHI (982
   estaciones; ojo, un slug mal escrito no da error: SENAMHI devuelve todo el país), la lluvia
   horaria de las estaciones automáticas de `SIMPAC_LLUVIA_DEPTS`, el reporte de ANA de **ayer y
   hoy** (fechas de Perú; el de un día solo trae las estaciones que ya midieron, y de madrugada
   viene casi vacío) y los índices IGP/NOAA. Cada fuente va protegida por separado: si una
   falla, queda anotada en `Pasada.fallas` y la corrida sigue.
2. `guardar()` escribe todo en una transacción. Las horas de SENAMHI se guardan con zona horaria
   (`medido_en`, UTC-5). **Regla de alertas de ríos** (`caudal`, `nivel_bajo`): solo se
   reemplazan las de las estaciones que se volvieron a evaluar con dato (si ANA o una estación no
   respondió, su alerta se queda) y las que nadie refresca caducan a las 6 h. La ingesta ya no
   evalúa ni borra las de lluvia: las escribe la tarea `lluvia_nacional` (§5.6.2).
3. El resultado de la tarea Celery es el resumen: `estaciones`, `lluvia`, `caudal`, `alertas` (de
   ríos), `icen_serie`, `fallas`, `avisos`. Corrida suelta: `docker compose run --rm worker python -m backend.ingesta`.

**Tareas del worker** (`backend/celery_app.py`; todas menos `refresh_cache` también corren al
arrancar, porque el beat pierde su programación al recrear el contenedor). Cada una deja su latido
en la tabla `latido` (servicio = nombre de la tarea) con lo que escribió, `fallas` y `avisos`:

| Tarea | Cada | Qué hace |
|---|---|---|
| `ingesta` | 1 h | estaciones, lluvia de Cajamarca (24 h), caudales, índices, serie ICEN del IGP, alertas de ríos |
| `enfen` | 6 h | comunicado ENFEN + ICEN del Informe Técnico (§5.3.1) |
| `avisos` | 1 h | avisos oficiales de SENAMHI como áreas, con ícono y lectura del texto + alertas tipo `aviso` (§5.6.1) |
| `lluvia_nacional` | 30 min | lluvia de la última hora en ~216 estaciones del país + alertas de lluvia con la referencia de SENAMHI (§5.6.2) |
| `pronostico` | 1 h | pronóstico oficial de SENAMHI en ~277 localidades, 3 a 5 días (§5.6.4); límite de 300 s |
| `nowcast` | 10 min | nowcasting de SENAMHI para ahora, +1 h y +2 h (§5.6.5); límite de 240 s y `expires` de 540 s |
| `refresh_cache` | 5 min | snapshot en Redis para la API |

**Despliegue de avisos con ícono, pronóstico y nowcasting**, en este orden (todo es aditivo: si
algo sale mal, el worker y el frontend anteriores siguen funcionando):
1. Las migraciones `avisos_iconos`, `pronostico_localidad` y `nowcast_senamhi`, en ese orden, y
   `schema.sql`. La primera llena las anclas de los avisos ya guardados.
2. El catálogo `localidades_senamhi.json` revisado (17 de Cajamarca y las ciudades del selector
   con punto; §5.6.4). Ya está en el repo: solo se vuelve a correr la semilla si SENAMHI suma
   localidades.
3. El worker: `docker compose up -d --build worker` (y `backend`, §8). El arranque encola
   `avisos`, `pronostico` y `nowcast`; revisar con las consultas de §5.6.6. Si el worker se
   adelanta a las migraciones no rompe: los avisos se guardan sin íconos y las otras dos tareas
   solo escriben su latido con la falla `migracion`.
4. El frontend, **solo después** del paso 1: pide las columnas nuevas de `aviso_vigente` (si no
   existen, vuelve a las de antes una vez por sesión y el mapa va sin insignias) y las vistas nuevas.

**BD:** la estructura está en `supabase/migrations/` (historia) y `supabase/schema.sql` (foto).
`lectura_caudal` es el historial; la vista **`caudal_actual`** da la última lectura de ayer u
hoy de cada estación (es la que usan el mapa y el snapshot). La vista **`alerta_actual`** da las
alertas que se muestran: las vigentes, y la lluvia medida solo con 3 h o menos (§5.6.2); la leen el
frontend y el snapshot, no la tabla `alerta`. El frontend lee también `aviso_vigente` (con ícono y
anclas), `pronostico_vigente` (hoy, mañana y pasado) y `nowcast_estado` / `nowcast_vigente` (el
umbral de 30 min está en la vista). Todo cambio de BD va como migración nueva.

### 7.2. Prototipo (sin dependencias, congelado)

`backend/prototipo/` es la primera versión del flujo **fuentes → ingesta → BD → API**, toda con la
librería estándar. Sirve para mostrar los conectores sin Docker ni Supabase; no se usa en producción.

**Persistencia** (`prototipo/store.py`, SQLite en `backend/prototipo/simpac.db`). Esquema:

| Tabla | Contenido | Clave / dedup |
|---|---|---|
| `estacion` | inventario (cod, nombre, tipo, cat, estado, lat/lon) | `cod` (upsert) |
| `lectura_lluvia` | serie horaria precip/temp por estación | `(cod, ts)` |
| `lectura_caudal` | caudal por estación + umbrales + estado | `(estacion, fecha, hora)` |
| `indice` | último RONI / ICEN | `fuente` |
| `alerta` | alertas vigentes (se reescriben cada corrida) | autoincrement |

**Ingesta** (`prototipo/ingest.py`): una pasada = inventario + lluvia (automáticas) + caudales +
índices + recálculo de alertas (solo de caudal: el prototipo ya no evalúa lluvia). Última corrida real: `93 estaciones, 672 filas de lluvia,
12 de caudal, 0 alertas` (estiaje). Programarla **cada hora**:

```bash
# Linux/mac (cron):     0 * * * *  cd /ruta/VigiaFEN && python -m backend.prototipo.ingest
# Windows (Programador de tareas): acción -> python  argumentos -> -m backend.prototipo.ingest
```
Acumular estas pasadas es lo que construye el histórico propio para el modelo predictivo.

**API** (`prototipo/api.py`, `http.server`, CORS abierto):

| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/api/snapshot` | contexto (RONI/ICEN) + resumen + alertas + caudales |
| GET | `/api/estaciones` | inventario de Cajamarca |
| GET | `/api/caudales` | última lectura por estación, con `estado` |
| GET | `/api/lluvia?cod=107028` | serie horaria de una estación |
| GET | `/api/alertas` | alertas vigentes |
| GET | `/api/contexto` | índices El Niño |

> En producción esto ya lo hacen Supabase (PostgreSQL + PostGIS), `backend/ingesta/` y la API
> FastAPI (§8). `prototipo/api.py` no se usa en prod (sin validación, sin auth).

---

## 8. Despliegue con Docker (producción)

Stack completo en `docker-compose.yml` (4 servicios):

| Servicio | Qué es | Puerto |
|---|---|---|
| `frontend` | React build servido por **nginx** | 8080 |
| `backend` | API **FastAPI async** (`backend/app.py`) | 8000 |
| `worker` | **Celery + beat**: ingesta horaria, ENFEN cada 6 h, avisos SENAMHI, lluvia nacional, pronóstico por localidad, nowcasting, refresco de caché | — |
| `redis` | caché (snapshot) + cola/broker de Celery | 6379 |

### ¿Por qué esta arquitectura? (van a entrar varias personas a la vez)
- **Nadie consulta las fuentes por visita:** SENAMHI/ANA solo los consulta el worker (de cada
  10 min en el nowcasting a cada 6 h en el ENFEN), así no nos rate-limitean en picos de tráfico.
  La **web lee Supabase directo** (RLS, con la llave pública, y un caché en memoria por pestaña: 60 s,
  10 min el pronóstico): cada visita hace unas pocas consultas a Supabase, más una por capa que se
  enciende, y ahí está el límite a vigilar si el tráfico crece.
- **Redis (caché de la API):** el worker deja un *snapshot* (índices, último caudal por estación,
  alertas vigentes) y la API lo sirve en milisegundos a consumidores que no son la web (app
  móvil, terceros). Si algún día la web necesita aguantar más, puede leer ese snapshot con un
  proxy `/api` en nginx en vez de consultar Supabase.
- **Worker (Celery + beat):** bajar datos de las fuentes es lento y a veces falla (ANA es
  intermitente). Eso corre **en segundo plano**, aparte de la web: la ingesta cada hora, la tarea
  `enfen` cada 6 h y las demás según §7.1. `beat` es el "reloj" que dispara las tareas; como su
  programación se pierde al recrear el contenedor, al arrancar encola una vez todas menos
  `refresh_cache` (señal `beat_init`). Cada corrida deja su **latido** (tabla `latido`) con lo que
  falló, y el frontend lo muestra.
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
- El **worker** corre la ingesta (`backend/ingesta/`, nacional y concurrente) cada hora y refresca
  el snapshot en Redis cada 5 min — sin cron (lo programa el **beat** de Celery).
- La API es **de solo lectura**: `GET /health` y `GET /api/snapshot` (índices, último caudal por
  estación, alertas vigentes). El snapshot vive `SNAPSHOT_TTL` s (900) y hay una copia sin
  vencimiento que se sirve si Supabase no responde.
- **Alertas del snapshot** (vista `alerta_actual`): `tipo, referencia, zona, nivel, detalle, valor,
  umbral, ventana_h, ts, lat, lon` más `oficial`, que pone el snapshot (`alerts.es_oficial`).
  - `aviso`, `caudal` y `nivel_bajo` tienen `oficial: true`.
  - `lluvia` tiene `oficial: false`: una estación midió más que la referencia de SENAMHI para ese
    lugar, no es un aviso. Su `umbral` es de esa estación y se lee con `ventana_h` (1 = mm en la
    última hora, 6 = mm en las últimas 6 h). Una app o una push nunca deben tratarla como alerta
    oficial.
  - `resumen.alertas` sigue contando filas (compatibilidad); `alertas_oficiales` y
    `lluvia_sobre_referencia` las separan.
- **Async / rendimiento:** la API es async (`httpx.AsyncClient` + `redis.asyncio`, consultas en
  paralelo con `asyncio.gather`) y sirve el snapshot **cacheado en Redis**: sus clientes no golpean
  Supabase en cada request (la web, en cambio, lee Supabase directo).
- El frontend recibe las llaves públicas por *build-args*; `SUPABASE_DB_URL` (secreto) solo lo usa
  el worker vía `.env` (nunca en git, ni en la imagen, ni en el contenedor de la API).
- **`SUPABASE_DB_URL` debe ser la del pooler** (`...pooler.supabase.com:5432`, usuario
  `postgres.<ref>`, con `?sslmode=require`). La conexión directa `db.<ref>.supabase.co` es **solo
  IPv6** y la red de Docker no tiene IPv6: desde los contenedores falla con "Network is unreachable".
- **Redis** se publica solo en `127.0.0.1:6379` (no queda expuesto a la red local ni al wifi).
- **TLS:** los conectores verifican siempre el certificado de los portales; si alguno falla, la
  petición falla (no hay modo "sin verificar").
- **Backend y worker tienen imágenes distintas** (mismo Dockerfile). Si cambia código de
  `backend/`, reconstruir los dos: `docker compose up -d --build backend worker`. Si solo se
  reconstruye uno, el otro sigue corriendo código viejo.

> **Gotcha (worker + Redis):** un cliente `redis.asyncio` ata su pool al event loop donde se usa
> primero. El worker corre cada tarea con `asyncio.run()` (loop nuevo y cerrado en cada corrida),
> así que **no** puede compartir un cliente global — daba `RuntimeError: Event loop is closed`.
> Solución: el worker crea/cierra un cliente Redis **por corrida** (`snapshot._redis_ctx`), y la API
> (loop persistente de uvicorn) inyecta **uno** de larga vida por `lifespan`. Ver `backend/snapshot.py`.

### 8.1. Seguridad: llave anon pública y RLS
- Supabase expone dos llaves: la **publishable/anon** (va en el frontend, es **pública por
  diseño** — visible en el navegador y en el bundle) y la **secret/service_role** (solo backend,
  **bypasea RLS**, jamás al cliente ni a git).
- La anon key **viaja en cada request** (header `apikey`); no es un secreto que robar: cualquiera
  que abra la web la ve. La protección real es **RLS**, no ocultar la llave. Todo va por **HTTPS**,
  así que un intermediario no la lee en tránsito, pero igual es pública.
- **RLS en todas las tablas** y **permisos por columna** en las de comunidad: el cliente solo puede
  escribir las columnas que le tocan (p. ej. en `report`: tipo, subtipo, descripción, foto y
  posición). `estado`, `confianza`, `likes`, vencimientos y fechas los pone la BD, y la reputación
  la mueven solo los votos (trigger `voto_aplicar`).
- **Ids uuid** en `report`, `voto`, `comentario` y `message` (y los usuarios, de Supabase Auth): no
  se pueden recorrer adivinando números.
- **Privacidad de ubicación:** la columna `autor` de `report` y `comentario` no es legible (con
  autor + GPS + hora se arma el historial de dónde estuvo alguien), los reportes vencidos dejan de
  ser públicos y `message` no expone su posición. Cada quien ve los suyos con
  `rpc('mis_reportes')`. Límites por hora: 5 reportes, 20 comentarios, 30 mensajes.
- Las funciones de los triggers viven en el esquema `privado` (el Data API no lo expone), son
  `SECURITY DEFINER` con `search_path` vacío y no se pueden llamar por RPC.
- `anon`/`authenticated` no tienen TRUNCATE, TRIGGER, REFERENCES ni MAINTAIN, tampoco en tablas
  futuras (default privileges). `rls_auto_enable()` ya no es llamable.
- Avisos que quedan en el *advisor*, todos de PostGIS y fuera del alcance del rol postgres: la
  tabla `spatial_ref_sys` sin RLS. El Data API la dejaba **escribible** por anon; ahora un trigger
  rechaza esas escrituras. También quedan la extensión en `public` y `st_estimatedextent`.
- **La ingesta escribe con el rol `postgres`** (dueño de las tablas) vía `SUPABASE_DB_URL`;
  `service_role` no tiene permisos de escritura en estas tablas.

---

## 9. Estrategia de adquisición y buenas prácticas

Orden de preferencia por estabilidad: **API/archivo abierto → API interna (sniffing) →
scraping HTML/PDF.**

| Fuente | Método | Nota |
|---|---|---|
| NOAA RONI | archivo abierto (HTTPS) | trivial |
| ENFEN | PDF (comunicado e Informe Técnico) descubierto en gob.pe / SENAMHI | pypdf |
| IGP ICEN | archivo abierto (**HTTP**) | proxyear desde backend |
| ANA caudal | API interna `.asmx` (POST JSON) | payload exacto, ver 5.2 |
| SENAMHI estaciones/serie | HTML con JSON/Highcharts embebido | scraping estructurado |
| SENAMHI avisos | scraping de tabla + WFS de la GeoServer | polígonos por WFS; párrafos de la página de vigentes (§5.6.1) |
| SENAMHI pronóstico por localidad | scraping de una página HTML | una petición por hora; coordenadas de un catálogo propio (§5.6.4) |
| SENAMHI nowcasting | visor HTML + WFS de la GeoServer | en serie y con pausas; experimental (§5.6.5) |
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

- [x] Conector de **avisos** SENAMHI: áreas por nivel + alertas por departamento (§5.6.1).
- [x] Conector **ENFEN** por PDF: estado del Sistema de Alerta y ICEN del Informe Técnico (§5.3.1).
- [ ] URL exacta del **MapServer de CENEPRED** (enumerar capas de peligro por lluvia/inundación).
- [x] Persistencia + ingesta + API (prototipo SQLite/stdlib, sección 7).
- [x] Persistencia en **PostgreSQL + PostGIS** (Supabase) con job horario en el worker (Celery beat).
- [x] Conector **IDESEP** + 5 mapas históricos de eventos El Niño en la tabla `mapa` (sección 5.7).
- [x] API en **FastAPI** async con caché en Redis (sección 8), de solo lectura.
- [x] Refactor modular del backend y frontend + pruebas sin red (22 sep).
- [x] Comunidad con **ids uuid**, permisos por columna y votos calculados por la BD (sección 8.1).
- [x] Capa de **áreas FEN** en el frontend (polígonos por `RANGO` + selector de evento).
- [x] Capa de **lluvia ahora** en todo el país (§5.6.2), más lluvia observada, satélite y SILVIA (§5.6.3).
- [x] **Serie del ICEN** (`icen_serie`) y panel gráfico de El Niño en el frontend.
- [x] **Alertas de lluvia con la referencia de SENAMHI** por estación, en todo el país (§5.6.2); se
      retiraron los umbrales provisionales de SIMPAC.
- [x] **Avisos con ícono** (gota, gota con rayo, copo; §5.6.1), **pronóstico oficial por localidad**
      (§5.6.4) y **nowcasting experimental** (§5.6.5), con sus capas en el frontend.
- [ ] Ubicar las **41 localidades del pronóstico sin punto** (`sin_ubicar` en
      `localidades_senamhi.json`): hoy se guardan pero no se muestran.
- [ ] **Nowcasting:** calibrar el umbral de 30 min con `retraso_min` del latido (cuánto tarda
      SENAMHI en publicar) y revisar cada cuánto se detiene.
- [ ] Conector de **push** (Firebase) que dispare la notificación cuando `alerta` cambie de nivel,
      solo con lo oficial (`oficial: true`): la lluvia medida no se notifica como alerta.
- [ ] Reejecutar la verificación en **temporada de lluvias (oct–abr)** y revisar las alertas de lluvia:
  - cada cuánto salen (`latido.alertas` y `alertas_6h`);
  - las 8 estaciones de valle amazónico con referencia de 5 mm/h y lluvia de llano amazónico (Jaén,
    San Ignacio, Cumba y Huallape en Cajamarca; Bagua, Corral Quemado, Naranjito y Magunchal en
    Amazonas), que la pasarían muy seguido;
  - las 16 de la costa de Lima, Ica y Arequipa con 1 mm/h, donde basta una lectura mala (CONTA GORE
    marcó 9.9 mm en una hora con las 6 vecinas en 0).
- [ ] Serie horaria de las **hidrológicas automáticas** con `tipo_esta=M` (§5.1): 63 en el país, 10 en
      Cajamarca. La lluvia de 24 h de Cajamarca pasaría de 14 a unas 24 estaciones.
- [ ] **Candado** (`pg_advisory_xact_lock`) en `guardar()`: con corridas simultáneas las alertas de
      caudal pueden duplicarse.

---

*Endpoints capturados por inspección de red de sitios públicos el 2026-09-06. Sujetos a
cambios del lado de cada organismo; por eso cada fuente vive en su propio conector con tests.*
