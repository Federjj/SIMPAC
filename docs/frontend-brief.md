# SIMPAC — Brief de diseño de frontend (producto completo)

> **Para quién es:** para pegar en **Claude Design**. Describe *qué* pantallas y componentes
> necesita SIMPAC, *qué datos* muestra cada uno y *cómo se comporta*. El **estilo visual**
> (paleta fina, tipografía, espaciado, ilustración) lo decide el diseño; aquí se fijan los
> roles funcionales (p. ej. el semáforo de alerta, que es semántico).
>
> **Importante:** se diseña **TODO ahora**. Las etiquetas `v1 / v2 / v3` indican el **orden
> de desarrollo**, no de diseño — así, cuando toque programar, no se pierde tiempo diseñando.

---

## 1. Contexto

- **Producto:** SIMPAC — centraliza datos hidrometeorológicos de **Cajamarca (Perú)**, avisa de
  **lluvias/crecidas** con anticipación y suma una **capa comunitaria** (reportes + chat) tipo
  Waze para el detalle calle a calle.
- **Usuarios/roles:** visitante (sin cuenta) · ciudadano/agricultor. **Sin roles de
  administración ni moderadores humanos** — la validación de reportes la hace la propia comunidad
  (la app es intermediaria de información, no juez). **Alfabetismo de datos bajo** → todo debe
  entenderse de un vistazo.
- **Plataformas:** web responsive + app Android. Diseñar **mobile-first**.
- **Idioma:** español (Perú). Nombre del producto: *por decidir* (placeholder).
- **Principio rector:** en 5 segundos el usuario sabe **¿hay peligro? ¿dónde? ¿qué hago?**

---

## 2. Reglas transversales (aplican a todo)

- **Semáforo de alerta** — 4 niveles, con color **y** etiqueta/ícono (nunca solo color):
  | Nivel | Color | Significado |
  |---|---|---|
  | Normal | verde | sin peligro |
  | Aviso | amarillo | vigilancia |
  | Alerta | naranja | superó umbral de alerta |
  | Emergencia | rojo | superó umbral de emergencia |
- **Titular primero:** cada pantalla abre con una frase clara en lenguaje natural, no una tabla.
- **Trazabilidad:** todo dato oficial muestra su **fuente** (SENAMHI/ANA/IGP/NOAA) y su **hora**.
- **Disclaimer legal** en todo lo de alertas y comunidad: *"Información referencial y
  comunitaria; no reemplaza los canales oficiales de emergencia (105 / 116)."*
- **Estados por vista:** cargando · vacío · error de fuente · dato desactualizado (>2 h) · sin
  conexión · (si aplica) no autenticado.
- **Sesión:** diseñar cada pantalla en su versión **con y sin cuenta** cuando cambie (p. ej.
  botón "reportar" pide login).

---

## 3. Mapa de pantallas (resumen)

| Área | Pantallas | Fase |
|---|---|---|
| A. Núcleo de datos | Panorama · Mapa · Detalle de estación · Alertas · Contexto El Niño · Histórico | v1 |
| B. Cuentas | Registro · Login · Recuperar · Perfil · Mi zona · Preferencias de notificación | v2 |
| C. Comunidad | Crear reporte · Reportes en mapa · Detalle + votar (like/dislike) + comentar | v2 |
| D. Chat en tiempo real | Canal por zona · Mensaje efímero · Reportar mensaje | v3 |
| E. Notificaciones | Onboarding de permisos · Push · Centro de notificaciones | v3 (móvil) |

---

## 4. A — Núcleo de datos (v1)

### 4.1. Panorama / Home
Foto instantánea del estado de Cajamarca. De arriba a abajo:
1. **Titular de estado** grande, con color del nivel más alto vigente.
   *Ej.:* "Cajamarca en condiciones normales. Fenómeno El Niño activo (cálido fuerte)."
2. **Mapa** con estaciones y ríos por estado (ver 4.2).
3. **Tira de contexto El Niño:** ONI `+1.80 · El Niño` · ICEN `+1.98 · Cálido fuerte`.
4. **Alertas vigentes** (o vacío "Sin alertas activas").
5. **Avisos oficiales SENAMHI** que aplican a la sierra norte, con su nivel.

**Datos:** `GET /api/snapshot`.

### 4.2. Mapa interactivo — **pantalla principal, estilo Waze**
Es LA pantalla central de SIMPAC (como en Waze, el mapa *es* el home). Al entrar se centra en la
ubicación del usuario (GPS o zona elegida). El panel de Panorama (4.1) va como *bottom-sheet*
deslizable encima del mapa, no como página aparte.

**Capas (de abajo hacia arriba), todas conmutables con una leyenda:**
1. **Mapa base** OSM de Cajamarca, limpio y orientado a la acción.
2. **Zonas sombreadas** (el diferencial sobre Waze — círculos/polígonos translúcidos):
   - **Alto riesgo** — polígonos de peligro de CENEPRED/SIGRID (deslizamiento, huayco, inundación).
   - **Lluvia/precipitación activa** — círculos o *heatmap* alrededor de estaciones con lluvia
     en la última hora (intensidad = opacidad/color), a partir de los datos horarios de SENAMHI.
   - **Inundación / caudal alto** — círculos alrededor de ríos en estado alerta/emergencia (ANA).
3. **Incidentes ciudadanos** (estilo Waze) — pines por tipo (ver taxonomía abajo). Con contador
   de **likes/dislikes** y color según cómo lo valora la comunidad.
4. **Estaciones oficiales** (982 en todo el Perú) — capa conmutable, marcador meteo/hidro.

(La capa de "usuarios cercanos" se descartó: no se muestra la posición de otras personas.)

**Controles estilo Waze:**
- Botón flotante grande **“＋ Reportar”** (abre el flujo de la sección 6).
- Botón **recentrar en mi ubicación**.
- Toggle de capas + **leyenda** (semáforo + tipos de pin + significado de cada sombreado).
- **Tap en un pin** → tarjeta emergente: qué es, cuándo, a qué distancia, **like/dislike**, comentar / ver detalle.

**Datos:** `GET /api/estaciones`, `GET /api/caudales`, `GET /api/alertas` (zonas y ríos en alerta);
lluvia por estación desde `GET /api/lluvia?cod=`; incidentes y usuarios desde el backend propio
(Supabase: `report`, posiciones aproximadas de `perfil`). Las zonas sombreadas se derivan de esos
datos (no hay una capa "oficial" de círculos; se generan en el cliente/servidor).

> **Nota de diseño:** las 3 clases de sombreado deben distinguirse claramente entre sí y de los
> pines de incidente — usar color + patrón/borde, no solo color, y mantenerlas translúcidas para
> no tapar el mapa ni los pines.

**Taxonomía de incidentes (pines) e íconos sugeridos:**

La lista la valida la BD (`report.tipo`); en el código está en `frontend/src/lib/reportTypes.js`.

| Tipo (`id`) | Ícono sugerido | Color base |
|---|---|---|
| Inundación (`inundacion`) | gota / casa con agua | azul #3B3BEB |
| Huayco / deslizamiento (`huayco`) | ladera con flujo | rojo #EB3B3B |
| Lluvia intensa (`lluvia_intensa`) | nube con lluvia | cian #3BEBEB |
| Vía bloqueada (`via_bloqueada`) | barrera / cono | negro #111111 |
| Atasco (`atasco`, subtipo leve / moderado / detenido) | auto | amarillo #EBEB3B |
| Bache (`bache`) | hoyo en la pista | naranja #F58E27 |
| Accidente (`accidente`) | triángulo de aviso | rojo #DB0404 |
| Otro (`otro`) | signo de exclamación | gris #6B7280 |

Cada pin lleva un badge con **likes/dislikes** y su opacidad refleja la **valoración de la
comunidad** (saldo de votos): más apoyo = más sólido; muy rechazado = se atenúa.

**Cómo se calculan las zonas sombreadas** (para front/datos — no vienen "dibujadas" de la fuente):
- **Lluvia:** por cada estación automática con `precip_mm > 0` en la última hora, un círculo
  (radio escalado por intensidad, p. ej. 3–8 km) con opacidad ∝ mm/h; o un *heatmap* ponderado por
  esos puntos. Fuente: `/api/lluvia` por estación + coordenadas de `/api/estaciones`.
- **Inundación/caudal:** círculo alrededor de cada río en estado alerta/emergencia
  (`/api/caudales` o `/api/alertas`); naranja = alerta, rojo = emergencia.
- **Riesgo:** polígonos de peligro de CENEPRED/SIGRID como GeoJSON (capa estática de
  referencia). Mientras no se integre SIGRID, se puede omitir o usar un placeholder.
- Todas translúcidas (~20–35 % de opacidad) y por debajo de los pines.

> **Estado real (22 sep).** Hecho: círculos de **ríos en alerta/emergencia** (dato ANA) y
> **anomalía mensual de lluvia** como puntos por estación (color = % sobre/bajo lo normal). Se
> quitaron las zonas de demostración y la capa de usuarios cercanos (decisión del 15 sep).
> Pendiente: **áreas FEN históricas** (datos listos en `mapa` con `variable='FEN'`: polígonos con
> la propiedad `RANGO`; conviene un selector de evento y simplificar geometrías), **lluvia ahora**
> (datos ya disponibles: la ingesta horaria llena `lectura_lluvia` con las estaciones automáticas de
> Cajamarca) y **riesgo** (CENEPRED). Íconos SVG, nunca emojis.

### 4.3. Detalle de estación
- Cabecera: nombre, distrito, tipo, código, fuente.
- **Meteo:** precipitación (mm/h, barras) + temperatura (°C, línea), 48 h; acumulado 24 h vs umbral.
- **Hidro/río:** caudal (m³/s o nivel m) con líneas de **umbral de alerta** y **emergencia**;
  estado y tendencia (↑/↓/→).

**Datos:** `GET /api/lluvia?cod={cod}`, caudal desde `/api/caudales`.

### 4.4. Alertas
Lista priorizada (emergencia → alerta → aviso). Cada tarjeta: nivel, referencia (estación/río +
zona), detalle, hora, fuente. Filtros por nivel y tipo. Estado vacío amable.
**Datos:** `GET /api/alertas`.

### 4.5. Contexto El Niño
Explica en simple qué es El Niño y cómo está: ONI e ICEN con su categoría, mini serie mensual,
y un párrafo en lenguaje natural. **Datos:** `GET /api/contexto`.

### 4.6. Histórico (v1.5)
Serie histórica de una estación más allá de 48 h (desde la BD propia acumulada): selector de
rango, comparar lluvia/caudal, marcar eventos de alerta pasados, exportar CSV.

---

## 5. B — Cuentas y personalización (v2)

- **Registro / Login / Recuperar contraseña** (Supabase Auth). Login social opcional.
- **Perfil:** nombre, rol, datos de contacto.
- **Mi zona:** definir ubicación (mapa o GPS) y radio de interés → filtra alertas y reportes.
- **Preferencias de notificación:** qué niveles y tipos recibir por push, horarios, silenciar.

Diseñar los estados **logueado / no logueado** y el gate de "necesitas cuenta para X".

---

## 6. C — Comunidad / reportes ciudadanos (v2)

La **comunidad valida**, no la app ni un moderador: cada quien sube su reporte con foto y los
demás lo **votan (like/dislike)** y **comentan**. SIMPAC solo es el intermediario que muestra la
información; la veracidad la juzga la gente.

- **Crear reporte:** tipo (ver taxonomía de §4.2), ubicación = **posición GPS actual** (sin
  elegir un punto en el mapa: solo se reporta donde uno está, para evitar reportes troll),
  **foto** opcional, comentario corto. Aviso de que es comunitario y no oficial.
- **Reportes en el mapa:** marcadores diferenciados de las estaciones; agrupación por cercanía.
- **Detalle de reporte:** contenido, foto, autor (o anónimo), hora, distancia, **botones
  like / dislike** con sus contadores, y **hilo de comentarios**.
- **Orden/priorización:** los reportes con mejor saldo de votos se ven más arriba/sólidos; los muy
  rechazados se atenúan. **No hay aprobación manual.**

**Datos:** backend propio (Supabase: `report`, `voto`, `comentario`).

> **Opcional (no bloquea nada):** además del voto, se puede mostrar un badge automático
> *"coincide con dato oficial"* si el reporte cae en una zona con alerta de SENAMHI/ANA — es solo
> una señal extra de contexto; la validación la sigue haciendo la comunidad.

---

## 7. D — Chat / mensajería en tiempo real (v3)

- **Canal por zona/barrio:** mensajes en tiempo real entre usuarios cercanos.
- **Mensajes efímeros:** expiran (indicar tiempo restante); pensados para emergencias en curso.
- **Autocontrol, sin moderadores:** filtro automático de groserías + rate limit; botón *reportar*
  y *ocultar/bloquear* a nivel de usuario; normas de convivencia visibles. No hay cola de
  moderación humana.
- Adjuntar ubicación o foto a un mensaje.

**Datos:** Supabase Realtime (`message` con expiración).

---

## 8. E — Notificaciones push (v3, móvil)

- **Onboarding de permisos:** explicar por qué se pide ubicación y notificaciones; permitir modo
  manual (elegir zona) si el usuario no da GPS.
- **Push de alerta:** nivel + zona + acción sugerida; al abrir → detalle.
- **Centro de notificaciones** dentro de la app: historial de alertas recibidas, marcar leídas.

**Entrega:** FCM (Firebase Cloud Messaging); la alerta nace en el backend (Supabase).

---

## 9. Componentes reutilizables

Titular de estado · Badge de nivel (4 estados) · Tarjeta de índice (ONI/ICEN) · Marcador de
estación por estado (meteo/hidro) · Popup de estación · Gráfico de serie (barras+línea
y línea con umbrales) · Tarjeta de alerta · Tarjeta de reporte (con like/dislike y comentarios) ·
Burbuja de chat efímero (con contador de expiración) · Leyenda del mapa · Chip de fuente+hora ·
Franja de disclaimer legal · Selector de zona/ubicación · Cabecera con estado de sesión.

**Del mapa estilo Waze (4.2):** Pin de incidente por tipo (taxonomía de 4.2) · Overlay de zona
sombreada en 3 variantes (riesgo / lluvia / inundación) · Botón flotante “＋ Reportar” · Botón
recentrar en mi ubicación · Tarjeta emergente de pin (qué/cuándo/distancia · like·dislike·comentar).

---

## 10. Roles — qué ve cada uno

| | Visitante | Ciudadano |
|---|---|---|
| Ver panorama, mapa, alertas, detalle | | |
| Crear reportes · votar (like/dislike) · comentar | — | |
| Chat de zona | — | |
| Recibir push personalizado | — | |

---

## 11. Contenido real de ejemplo (usar esto, no lorem ipsum)

Datos en vivo del 2026-09-06 (temporada seca → todo "normal"):
- **Contexto:** ONI `+1.80 · El Niño`; ICEN `+1.98 · Cálido fuerte`.
- **Ríos (ANA):** Mashcón `0.13 m³/s` (normal, UA 14 / UE 18); Jesús Túnel `0.25 m³/s`; Namora
  Bocatoma `1.14 m³/s`; Yónan Gore `2.30 m³/s` (ascendente); Balsas `86.5 m³/s`.
- **Estación meteo (Cutervo):** última hora `2026/09/06 - 21`, precip `0.0 mm`, temp `13.3 °C`.
- **Alerta de ejemplo (para el estado "con peligro"):** *Emergencia — Río Mashcón (Cajamarca):
  caudal 19.2 m³/s, supera el umbral de emergencia (18). Tendencia ascendente. 21:00 · ANA.*
- **Reporte de ejemplo:** *Inundación en Jr. Los Sauces, Baños del Inca — 12 a favor / 1 en contra —
  3 comentarios — hace 15 min.*

> Diseñar **dos estados del Home**: en **calma** (como hoy) y en **emergencia** (con la alerta
> de ejemplo), para cubrir ambos extremos del semáforo.

---

*La API del núcleo de datos ya existe (ver `docs/README-tecnico.md`, sección 7). Cualquier
pantalla de v1 puede maquetarse contra datos reales leyendo Supabase directo (ver
`frontend/README.md`). Las de v2/v3 usan Supabase (usuarios, reportes, mensajes) + FCM para push.*
