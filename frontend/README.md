# SIMPAC — Frontend

Web en **React + Vite + Leaflet** que consume la BD de Supabase. La **página Mapa ya está construida
y funcionando** con datos reales; el diseño de las demás pantallas está en `docs/frontend-brief.md`
(estilo Waze).

## Arranque
El proyecto ya existe (React + Vite). Solo:
```bash
npm install
npm run dev          # http://localhost:5173
```
El `.env` con las llaves públicas ya está (`.env.example` de respaldo). Cliente: `src/lib/supabaseClient.js`.

## Estructura
```
src/
  App.jsx · main.jsx · index.css · icons.jsx
  lib/        supabaseClient.js · queries.js
  data/       cities.js (ciudades del Perú) · incidents.js (demo)
  components/ Sidebar · MapView · LayersPanel · StatusPanel · CitySelector
```

## Página Mapa (hecha)
- Leaflet + OSM centrado en Cajamarca; **geolocalización** (con permiso) y **selector de ciudades
  del Perú** (Cajamarca por defecto).
- Marcadores: estaciones y ríos (círculo con ícono), incidentes (rombo por tipo), **usuarios
  cercanos (pin tipo Waze)** y **tu ubicación (flecha de navegación)**.
- Capas conmutables, zonas sombreadas, botón Reportar, panel de estado.
- Incidentes y usuarios son **demo** hasta que haya login (v2 → tablas `report` / `voto`).

## Qué tabla alimenta cada parte del mapa (brief §4.2)

| UI | Tabla / consulta | Notas |
|---|---|---|
| Marcadores de estaciones | `estacion` (`cod,nombre,tipo,estado,lat,lon`) | 93 filas; `tipo` M/H, `estado` REAL/AUTOMATICA/DIFERIDO |
| Ríos + estado (círculos inundación) | `lectura_caudal` (`estacion,rio,valor,unidad,estado,umbral_alerta,umbral_emergencia,lat,lon`) | estado normal/alerta/emergencia |
| Gráfico de lluvia (detalle) | `lectura_lluvia` (`ts,precip_mm,temp_c` where `cod=…`) | ordenar por `medido_en` |
| Titular / contexto El Niño | `indice` (`fuente,periodo,valor,categoria`) | ICEN y ONI |
| Alertas vigentes | `alerta` (`tipo,referencia,nivel,detalle`) | hoy 0 (estiaje) |
| Capa de anomalías (mapas SENAMHI) | `mapa` (`titulo,variable,periodo,geojson`) | el `geojson` va directo a `L.geoJSON(...)` en Leaflet |
| Reportes + votos + comentarios (comunidad) | `report`, `voto` (like/dislike), `comentario`, `message` | lectura pública; **crear/votar/comentar requiere login** (fase 2) |

> **Coordenadas:** usa las columnas `lat` / `lon` (ya vienen listas). La columna `geom` es PostGIS
> y no hace falta tocarla en el cliente.

## Ejemplos
```js
import { supabase } from "./lib/supabaseClient";

// estaciones para el mapa
const { data: estaciones } = await supabase
  .from("estacion").select("cod,nombre,tipo,estado,lat,lon").limit(1000);

// ríos con su estado (para los círculos de inundación)
const { data: rios } = await supabase
  .from("lectura_caudal").select("estacion,rio,valor,unidad,estado,lat,lon");

// serie horaria de lluvia de una estación (para el detalle)
const { data: lluvia } = await supabase
  .from("lectura_lluvia").select("ts,precip_mm,temp_c")
  .eq("cod", "472645F0").order("medido_en");

// contexto El Niño (titular)
const { data: indices } = await supabase.from("indice").select("*");

// capa de anomalías mensual (puntos por estación): usar getMapaAnomalias() de src/lib/queries.js.
// Siempre filtrar por variable: sin filtro baja los 5 mapas FEN (~17 MB) en orden arbitrario.
const { data: mensual } = await supabase.from("mapa").select("titulo,periodo,geojson")
  .eq("variable", "precipitacion").order("periodo", { ascending: false }).limit(1);

// mapas históricos de eventos El Niño (polígonos con la propiedad RANGO), uno por evento
const { data: eventos } = await supabase.from("mapa").select("titulo,periodo")
  .eq("variable", "FEN").order("periodo");   // luego pedir el geojson solo del evento elegido
```

## Notas
- **Lectura pública**: las tablas de datos oficiales se leen con la publishable key (RLS ya configurado).
- **Escritura** (crear reportes, chat): necesita login con Supabase Auth — se implementa en la fase 2.
- Mapa base recomendado: OSM (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`).
