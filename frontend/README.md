# SIMPAC — Frontend

Web en **React + Vite + Leaflet** que consume la BD de Supabase. La BD **ya está creada y con
datos reales** (ver `docs/ESTADO.md`), así que se puede maquetar contra datos de verdad desde el día 1.
El diseño de pantallas está en `docs/frontend-brief.md` (mapa estilo Waze).

## Arranque
```bash
npm create vite@latest . -- --template react   # (o el setup que prefieras)
npm install @supabase/supabase-js leaflet
cp .env.example .env          # trae la URL + publishable key (públicas)
```
El cliente ya está en `src/lib/supabaseClient.js`.

## Qué tabla alimenta cada parte del mapa (brief §4.2)

| UI | Tabla / consulta | Notas |
|---|---|---|
| Marcadores de estaciones | `estacion` (`cod,nombre,tipo,estado,lat,lon`) | 93 filas; `tipo` M/H, `estado` REAL/AUTOMATICA/DIFERIDO |
| Ríos + estado (círculos inundación) | `lectura_caudal` (`estacion,rio,valor,unidad,estado,umbral_alerta,umbral_emergencia,lat,lon`) | estado normal/alerta/emergencia |
| Gráfico de lluvia (detalle) | `lectura_lluvia` (`ts,precip_mm,temp_c` where `cod=…`) | ordenar por `medido_en` |
| Titular / contexto El Niño | `indice` (`fuente,periodo,valor,categoria`) | ICEN y ONI |
| Alertas vigentes | `alerta` (`tipo,referencia,nivel,detalle`) | hoy 0 (estiaje) |
| Reportes / chat (comunidad) | `report`, `confirmation`, `message` | **requieren usuario autenticado** (fase 2) |

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
```

## Notas
- **Lectura pública**: las tablas de datos oficiales se leen con la publishable key (RLS ya configurado).
- **Escritura** (crear reportes, chat): necesita login con Supabase Auth — se implementa en la fase 2.
- Mapa base recomendado: OSM (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`).
