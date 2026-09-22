# SIMPAC — Frontend

Web en **React + Vite + Tailwind + shadcn/ui + Leaflet** que lee directo de Supabase. La **página
Mapa ya está construida y funcionando** con datos reales; el diseño de las demás pantallas está en
`docs/frontend-brief.md` (estilo Waze).

## Arranque
```bash
npm install
cp .env.example .env # llaves públicas de Supabase (en PowerShell: Copy-Item .env.example .env)
npm run dev          # http://localhost:5173
```
El `.env` no se sube a git: sin él la app no arranca (`supabaseUrl is required`). Cliente:
`src/lib/supabaseClient.js`.
Imports con alias: `@/` = `src/` (p. ej. `import { LAYERS } from "@/map/layers"`).

## Estructura
```
src/
  App.jsx · main.jsx · index.css
  components/   Sidebar · MapView · LayersPanel · StatusPanel · CitySelector · ui/ (shadcn)
  hooks/        usePanorama (índices + alertas, se refresca solo) · useGeolocation · useLayerVisibility
  map/
    baseMap.js  mapa base (tiles Stadia, zoom, ResizeObserver)
    markers.js  íconos SVG, markerIcon(), popupHtml() y escapeHtml()
    palette.js  colores por nivel, estación y anomalía
    layers/     una capa por archivo + index.js (LAYERS)
  lib/          supabaseClient · queries · nivel (semáforo y titular) · reportTypes (taxonomía)
  data/         cities.js (capitales del Perú)
```

## Capas del mapa
Cada archivo de `src/map/layers/` exporta la misma forma: `id`, `label`, `Icon`,
`defaultVisible`, `legend`, `load()` y `render(group, datos)`; opcional `refreshMs`. `MapView`
carga cada capa la primera vez que se enciende (reintenta si falla) y el panel de capas muestra
su leyenda. **Sumar una capa** = crear su archivo y agregarla a `layers/index.js`.

| Capa | Archivo | Datos |
|---|---|---|
| Ríos | `rios.js` | vista `caudal_actual` (última lectura de ayer u hoy por estación) |
| Zonas de caudal alto | `zonasCaudal.js` | `caudal_actual` en alerta/emergencia |
| Reportes ciudadanos | `incidentes.js` | `report` (la BD solo entrega los vigentes) |
| Estaciones | `estaciones.js` | `estacion` |
| Anomalías de lluvia | `anomalias.js` | `mapa` con `variable = 'precipitacion'` |

**Seguridad:** todo texto que va a un popup pasa por `popupHtml()`, que escapa el HTML. Los
reportes los escriben usuarios: nunca armar HTML con `${...}` a mano.

## Qué tabla alimenta cada parte

| UI | Tabla / consulta | Notas |
|---|---|---|
| Estado, titular y contador | `alerta` (`vigente = true`) | lluvia y caudal; `zona` = departamento |
| Contexto El Niño | `indice` | ICEN y ONI; `ts_captura` = última corrida de la ingesta (aviso "sin actualizar") |
| Ríos | `caudal_actual` | **no** `lectura_caudal`: esa es el historial (repite estaciones) |
| Gráfico de lluvia (detalle) | `lectura_lluvia` (`ts,medido_en,precip_mm,temp_c` where `cod=…`) | ordenar por `medido_en` (ya en hora correcta) |
| Mapas FEN históricos | `mapa` con `variable = 'FEN'` | pedir primero `titulo,periodo` y luego el `geojson` del evento elegido |
| Comunidad | `report`, `voto`, `comentario`, `message`, `perfil` | ver abajo |

> **Coordenadas:** usa las columnas `lat` / `lon` (vienen listas). `geom` es PostGIS y el Data API
> la devuelve en hex; no hace falta tocarla en el cliente para leer.

## Comunidad (reportes estilo Waze)
Todos los ids son **uuid**. **Pedir siempre columnas explícitas, nunca `select("*")`:** la columna
`autor` de `report` y `comentario` (y `geom` de `message`) no es legible, por privacidad, y un `*`
falla con permiso denegado. Solo se ven los reportes vigentes; los propios (también vencidos) con
`supabase.rpc("mis_reportes")`. La BD decide lo que no debe decidir el cliente:
- **Crear reporte** (con sesión): enviar solo `tipo`, `subtipo` (solo atasco: leve/moderado/detenido),
  `descripcion`, `foto_url` y `geom` = **posición GPS real** (`useGeolocation`, sin pin manual).
  `autor`, `estado`, `confianza`, `likes`, `expira_en` (12 h) los pone la BD. Tipos válidos en
  `src/lib/reportTypes.js` (coinciden con el CHECK de la BD). Máximo 5 reportes por hora.
- **Votar**: `upsert({ report_id, valor: 1 | -1 }, { onConflict: "report_id,autor" })`. No se puede
  votar el propio reporte ni uno vencido (ni quitar el voto cuando ya venció). Los contadores
  del reporte se actualizan solos.
- **Comentar**: solo en reportes vigentes; máximo 20 comentarios por hora.
- **Perfil**: se crea solo al registrarse (`auth.signUp({ ..., options: { data: { nombre } } })`).
- **Chat** (`message`): vence a las 2 h, siempre.

```js
// geom desde el GPS, como texto EWKT (ojo: primero lon, después lat)
await supabase.from("report").insert({
  tipo: "inundacion",
  descripcion: "calle anegada",
  geom: `SRID=4326;POINT(${lon} ${lat})`,
});
```

## Notas
- **Lectura pública**: los datos oficiales y los reportes se leen con la publishable key (RLS).
- **Escritura** (reportes, votos, chat): necesita sesión de Supabase Auth.
- Mapa base: Stadia Alidade Smooth (en un dominio real necesita su API key gratuita).
