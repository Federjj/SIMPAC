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
- **Usuarios/roles:** visitante (sin cuenta) · ciudadano/agricultor · técnico de Defensa Civil
  · administrador. **Alfabetismo de datos bajo** → todo debe entenderse de un vistazo.
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
| C. Comunidad | Crear reporte · Reportes en mapa · Detalle + confirmar · Reputación | v2 |
| D. Chat en tiempo real | Canal por zona · Mensaje efímero · Reportar/moderar mensaje | v3 |
| E. Notificaciones | Onboarding de permisos · Push · Centro de notificaciones | v3 (móvil) |
| F. Administración | Dashboard admin · Edición de umbrales · Moderación · Estado de conectores · Alerta manual · Usuarios | v2–v3 |

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

### 4.2. Mapa interactivo
- Base OSM de Cajamarca. Marcadores de **estaciones** (meteo/hidro) y **ríos** por estado.
- **Capas conmutables:** estaciones meteo · ríos/caudales · zonas de riesgo (CENEPRED, v2) ·
  reportes ciudadanos (v2). **Leyenda** con semáforo y tipos de marcador. Buscador por nombre.
- **Popup:** nombre, tipo, valor + unidad, estado, hora, tendencia, "ver detalle".

**Datos:** `GET /api/estaciones`, `GET /api/caudales`.

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

- **Crear reporte:** tipo (inundación, huaico, lluvia intensa, deslizamiento…), ubicación
  (mapa/GPS), foto opcional, comentario corto. Aviso de que es comunitario y no oficial.
- **Reportes en el mapa:** marcadores diferenciados de las estaciones; agrupación por cercanía.
- **Detalle de reporte:** contenido, autor (o anónimo), hora, distancia, y **confirmación**
  ("sigue pasando" / "ya no") + contador de confirmaciones.
- **Estado de confianza del reporte:** sin confirmar / confirmado (según corroboración +
  cruce con datos oficiales de la zona) — mostrarlo visualmente.
- **Reputación** del usuario (nivel/insignias por reportes confirmados).

**Datos:** backend propio (Supabase: `report`, `confirmation`, `user`).

---

## 7. D — Chat / mensajería en tiempo real (v3)

- **Canal por zona/barrio:** mensajes en tiempo real entre usuarios cercanos.
- **Mensajes efímeros:** expiran (indicar tiempo restante); pensados para emergencias en curso.
- **Moderación:** botón reportar mensaje; estados de mensaje oculto/eliminado; filtro de
  contenido. Diseñar el aviso de normas de convivencia.
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

## 9. F — Administración (v2–v3)

Solo para técnicos de Defensa Civil / administradores:
- **Dashboard admin:** salud del sistema, últimas ingestas, nº de alertas/reportes.
- **Edición de umbrales:** configurar por estación/zona los umbrales de lluvia (mm/h y
  acumulado) y de caudal; ver el efecto. *(Los de caudal vienen de ANA; los de lluvia son
  propios y hoy son placeholders a calibrar.)*
- **Moderación:** cola de reportes y mensajes reportados; aprobar/ocultar/eliminar.
- **Estado de conectores:** por fuente (SENAMHI/ANA/IGP/NOAA), última corrida, éxito/error.
- **Envío de alerta manual:** publicar una alerta/aviso a una zona (con confirmación).
- **Gestión de usuarios y roles.**

---

## 10. Componentes reutilizables

Titular de estado · Badge de nivel (4 estados) · Tarjeta de índice (ONI/ICEN) · Marcador de
mapa por estado (meteo/hidro/río/reporte) · Popup de estación · Gráfico de serie (barras+línea
y línea con umbrales) · Tarjeta de alerta · Tarjeta de reporte (con confianza y confirmar) ·
Burbuja de chat efímero (con contador de expiración) · Leyenda del mapa · Chip de fuente+hora ·
Franja de disclaimer legal · Selector de zona/ubicación · Cabecera con estado de sesión.

---

## 11. Roles — qué ve cada uno

| | Visitante | Ciudadano | Técnico DC | Admin |
|---|---|---|---|---|
| Panorama, mapa, alertas, detalle | ✓ | ✓ | ✓ | ✓ |
| Crear/confirmar reportes | — | ✓ | ✓ | ✓ |
| Chat de zona | — | ✓ | ✓ | ✓ |
| Recibir push personalizado | — | ✓ | ✓ | ✓ |
| Editar umbrales / alerta manual / moderar | — | — | ✓ | ✓ |
| Gestión de usuarios / conectores | — | — | — | ✓ |

---

## 12. Contenido real de ejemplo (usar esto, no lorem ipsum)

Datos en vivo del 2026-09-06 (temporada seca → todo "normal"):
- **Contexto:** ONI `+1.80 · El Niño`; ICEN `+1.98 · Cálido fuerte`.
- **Ríos (ANA):** Mashcón `0.13 m³/s` (normal, UA 14 / UE 18); Jesús Túnel `0.25 m³/s`; Namora
  Bocatoma `1.14 m³/s`; Yónan Gore `2.30 m³/s` (ascendente); Balsas `86.5 m³/s`.
- **Estación meteo (Cutervo):** última hora `2026/09/06 - 21`, precip `0.0 mm`, temp `13.3 °C`.
- **Alerta de ejemplo (para el estado "con peligro"):** *Emergencia — Río Mashcón (Cajamarca):
  caudal 19.2 m³/s, supera el umbral de emergencia (18). Tendencia ascendente. 21:00 · ANA.*
- **Reporte de ejemplo:** *Inundación en Jr. Los Sauces, Baños del Inca — 2 confirmaciones —
  hace 15 min — "confirmado" (hay alerta oficial en la zona).*

> Diseñar **dos estados del Home**: en **calma** (como hoy) y en **emergencia** (con la alerta
> de ejemplo), para cubrir ambos extremos del semáforo.

---

*La API del núcleo de datos ya existe (ver `docs/README-tecnico.md`, sección 7). Cualquier
pantalla de v1 puede maquetarse contra datos reales corriendo `python backend/api.py`. Las de
v2/v3 usan el backend propio (Supabase: usuarios, reportes, mensajes) + FCM para push.*
