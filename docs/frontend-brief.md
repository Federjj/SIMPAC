# SIMPAC — Brief de diseño de frontend

> **Para quién es este documento:** para pegar en **Claude Design** (o dárselo a un
> diseñador). Describe *qué* pantallas y componentes necesita SIMPAC, *qué datos* muestra
> cada uno (mapeados a la API real) y *cómo se comporta*. El **estilo visual** (paleta fina,
> tipografía, espaciado, ilustración) queda a criterio del diseño; aquí solo se fijan los
> roles funcionales (p. ej. los colores del semáforo de alerta, que son semánticos).

---

## 1. Contexto

- **Producto:** SIMPAC — centraliza datos hidrometeorológicos de **Cajamarca (Perú)** y avisa
  de **lluvias/crecidas** con anticipación.
- **Usuarios:** ciudadanía general, agricultores y técnicos de Defensa Civil. **Alfabetismo
  de datos bajo** → todo debe entenderse de un vistazo, sin jerga.
- **Plataformas:** primero **web** (responsive), luego **app Android**. Diseñar **mobile-first**.
- **Idioma:** español (Perú). Nombre del producto: *por decidir* (usar placeholder).
- **Principio rector:** en 5 segundos el usuario debe saber **¿hay peligro? ¿dónde? ¿qué hago?**

---

## 2. Reglas transversales (aplican a todo)

- **Semáforo de alerta** — 4 niveles, con color **y** etiqueta/ícono (nunca solo color, por
  accesibilidad y daltonismo):
  | Nivel | Rol de color | Significado |
  |---|---|---|
  | Normal | verde | sin peligro |
  | Aviso | amarillo | vigilancia / aviso amarillo |
  | Alerta | naranja | superó umbral de alerta |
  | Emergencia | rojo | superó umbral de emergencia |
- **Titular primero:** cada pantalla abre con una frase clara en lenguaje natural (generada
  por el backend), no con una tabla.
- **Trazabilidad:** todo dato muestra su **fuente** (SENAMHI / ANA / IGP / NOAA) y su **hora**.
- **Disclaimer legal** siempre visible en alertas: *"Información referencial y comunitaria; no
  reemplaza los canales oficiales de emergencia (105 / 116)."*
- **Estados a diseñar para cada vista:** cargando · vacío (sin alertas) · error de fuente ·
  dato desactualizado (> 2 h) · sin conexión.

---

## 3. Pantallas (v1 — web, solo lectura)

### 3.1. Panorama / Home
**Propósito:** foto instantánea del estado de Cajamarca.
Contiene, de arriba a abajo:
1. **Titular de estado** grande, con color del semáforo (el nivel más alto vigente).
   *Ej.:* "Cajamarca en condiciones normales. Fenómeno El Niño activo (cálido fuerte)."
2. **Mapa** de la provincia con estaciones y ríos coloreados por estado (ver 3.2).
3. **Tira de contexto El Niño** — 2 tarjetas:
   - ONI (global): `+1.80 · El Niño`
   - ICEN (costero, Perú): `+1.98 · Cálido fuerte`
4. **Alertas vigentes** — lista corta (o estado vacío "Sin alertas activas").
5. **Avisos oficiales SENAMHI** que aplican a la sierra norte, con su nivel.

**Datos:** `GET /api/snapshot` → `{contexto:{ONI,ICEN}, resumen, alertas, caudales}`.

### 3.2. Mapa interactivo
**Propósito:** explorar el territorio.
- Base: mapa de Cajamarca (OSM). Marcadores de **estaciones** (meteo/hidro) y **ríos
  monitoreados**, coloreados por estado (semáforo).
- **Capas conmutables:** estaciones meteorológicas · ríos/caudales · (fase 2) zonas de riesgo
  (CENEPRED) · (fase 2) reportes ciudadanos.
- **Leyenda** con el semáforo y los tipos de marcador.
- **Popup al tocar un marcador:** nombre, tipo, valor actual + unidad, estado, hora, tendencia,
  botón "ver detalle".
- Buscador de estación por nombre.

**Datos:** `GET /api/estaciones` (ubicaciones), `GET /api/caudales` (estado de ríos).
Los marcadores traen `lat`/`lon`, `estado`, `valor`, `unidad`, `hora`.

### 3.3. Detalle de estación
**Propósito:** ver la evolución de una estación.
- Cabecera: nombre, distrito, tipo, código, fuente, altitud si existe.
- **Estación meteorológica** → gráfico de **precipitación (mm/h)** en barras + **temperatura
  (°C)** en línea, últimas 48 h. Debajo: acumulado 24 h y su comparación con el umbral.
- **Estación hidrológica / río** → **caudal (m³/s o nivel m)** con dos líneas de referencia:
  **umbral de alerta** y **umbral de emergencia**; estado y tendencia (↑/↓/→).
- Marca de tiempo del último dato; aviso si está desactualizado.

**Datos:** `GET /api/lluvia?cod={cod}` (serie 48 h de meteo) · caudal desde `/api/caudales`
(trae `valor`, `ualerta`, `uemergencia`, `tendencia`, `hora`).

### 3.4. Alertas
**Propósito:** todo lo que está activo, priorizado.
- Lista de tarjetas ordenadas por nivel (emergencia → alerta → aviso). Cada tarjeta: nivel
  (semáforo), referencia (estación/río + zona), detalle (p. ej. "Caudal 130 m³/s, tendencia
  ascendente"), hora, fuente.
- Filtros: por nivel y por tipo (lluvia / caudal / aviso oficial).
- Estado vacío amable cuando no hay nada activo.

**Datos:** `GET /api/alertas`.

---

## 4. App móvil (v3) — pantallas extra

- **Onboarding + permiso de ubicación** (manual o GPS) para recibir alertas de tu zona.
- **Push de alerta:** notificación con nivel + zona + acción sugerida; al abrir → detalle.
- **Mis alertas / mi zona:** resumen personalizado por ubicación.
- **(Fase 2) Reportar:** formulario corto — tipo de incidente (inundación, huaico, lluvia
  intensa…), ubicación (mapa/GPS), foto opcional, comentario. Aviso de que es comunitario.
- **(Fase 2) Reportes cercanos:** verlos en el mapa y **confirmar** ("sigue pasando / ya no").

---

## 5. Componentes reutilizables a diseñar

1. **Titular de estado** (badge de nivel + frase en lenguaje natural).
2. **Tarjeta de índice** (ONI / ICEN: valor grande, categoría, mini-tendencia).
3. **Marcador de mapa por estado** (meteo vs hidro; 4 colores del semáforo).
4. **Popup de estación** (compacto).
5. **Gráfico de serie** (barras+línea para lluvia/temp; línea con umbrales para caudal).
6. **Badge de nivel** (normal/aviso/alerta/emergencia) — usado en todos lados.
7. **Tarjeta de alerta.**
8. **Leyenda del mapa.**
9. **Franja de disclaimer legal.**
10. **Chip de fuente + hora** ("SENAMHI · 21:00").

---

## 6. Contenido real de ejemplo (usar esto, no lorem ipsum)

Datos en vivo capturados el 2026-09-06 (temporada seca → todo "normal"):

- **Contexto:** ONI `+1.80 · El Niño`; ICEN `+1.98 · Cálido fuerte`.
- **Ríos de Cajamarca (ANA):** Mashcón `0.13 m³/s` (normal, UA 14 / UE 18); Jesús Túnel
  `0.25 m³/s` (normal); Namora Bocatoma `1.14 m³/s`; Yónan Gore `2.30 m³/s` (ascendente);
  Balsas `86.5 m³/s`.
- **Estación meteo automática (Cutervo):** última hora `2026/09/06 - 21`, precip `0.0 mm`,
  temp `13.3 °C`, acumulado 24 h `0.0 mm`.
- **Ejemplo de alerta (para diseñar el estado "con peligro"):** *Emergencia — Río Mashcón
  (Cajamarca): caudal 19.2 m³/s, supera el umbral de emergencia (18). Tendencia ascendente.
  21:00 · ANA.*

> Diseñar **dos versiones del Home**: una en **calma** (todo normal, como hoy) y una en
> **emergencia** (con la alerta de ejemplo), para ver ambos extremos del semáforo.

---

## 7. Fuera de alcance de v1 (no diseñar aún)
Chat en tiempo real, cuentas de usuario, panel de administración, histórico largo (>48 h),
edición de umbrales. Van en fases posteriores.

---

*La API que alimenta todo esto ya existe (ver `docs/README-tecnico.md`, sección 7). Cualquier
pantalla puede maquetarse contra datos reales corriendo `python backend/api.py`.*
