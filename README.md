# SIMPAC

**Sistema de Información Meteorológica y Prevención de Anomalías de Cajamarca.** Plataforma web que
centraliza datos hidrometeorológicos oficiales del Perú, con foco en Cajamarca, para seguir el
fenómeno El Niño y sus efectos: avisos de SENAMHI, estado del sistema de alerta del ENFEN, ríos de la
ANA, lluvia medida y pronosticada, y alertas por zona, explicados en lenguaje claro sobre un mapa.

## Cómo está armado

| Parte | Qué es | Dónde se ve |
|---|---|---|
| `frontend` | Web en React + Vite + Leaflet, servida por nginx | http://localhost:8080 |
| `backend` | API de solo lectura en FastAPI | http://localhost:8000/health |
| `worker` | Celery + beat: cada cierto tiempo baja los datos de las fuentes oficiales y los guarda en la base | (sin puerto; ver sus logs) |
| `redis` | Caché de la API y cola de tareas del worker | solo dentro de la máquina |
| Base de datos | PostgreSQL + PostGIS en Supabase (en la nube, no corre en tu computadora) | — |

La web lee la base directamente con una llave **pública**: los datos los protegen las reglas de
seguridad por fila de la base, no el secreto de la llave. Solo el worker escribe, y para eso
necesita la contraseña de la base.

## Requisitos

- **Docker**
  - Windows 10 (22H2) u 11, y macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop/).
    No hace falta crear una cuenta de Docker (se puede omitir el inicio de sesión). En Windows usa
    WSL 2: si al abrirlo avisa que falta o que hay que actualizarlo, abre PowerShell como
    administrador, ejecuta `wsl --install` (o `wsl --update`) y reinicia la computadora. Si dice que
    la virtualización no está activada, hay que activarla en la BIOS/UEFI.
  - Linux: Docker Engine con los plugins `compose` y `buildx`, siguiendo
    <https://docs.docker.com/engine/install/>. Para usarlo sin `sudo`: `sudo usermod -aG docker $USER`,
    y luego cerrar sesión y volver a entrar.
  - Docker tiene que estar abierto y corriendo antes de ejecutar los comandos.
- **Git** ([descarga](https://git-scm.com/downloads)). En macOS, la primera vez que escribes `git`
  el sistema ofrece instalar las herramientas de línea de comandos: acepta. Sin Git también se puede
  bajar el proyecto en ZIP (paso 1).
- **Conexión a internet** (la base y las fuentes oficiales están en línea).
- Unos **5 GB libres** en disco (las imágenes y su caché ocupan unos 2,5 GB), aparte de Docker.
- Solo si quieres trabajar sin Docker (opcional): **Node.js 22** o superior y **Python 3.12** o
  superior.

Para comprobar lo instalado:

```
docker --version
docker compose version
git --version
```

## Instalación con Docker (recomendada)

Los comandos se escriben en una terminal (PowerShell en Windows; Terminal en macOS o Linux) y son
los mismos en los tres sistemas.

**1. Descargar el proyecto**

```
git clone https://github.com/Federjj/SIMPAC.git
cd SIMPAC
```

Sin Git: en <https://github.com/Federjj/SIMPAC>, botón *Code → Download ZIP*; descomprímelo y entra
con `cd` en la carpeta `SIMPAC-main`.

Todos los comandos que siguen se ejecutan dentro de esa carpeta (la que tiene `docker-compose.yml`).
Si cierras la terminal, vuelve a entrar con `cd` antes de seguir.

**2. Crear el archivo de configuración `.env`** a partir de la plantilla (`cp` también funciona en
PowerShell):

```
cp .env.docker.example .env
```

La plantilla ya trae la dirección de la base y su llave pública: con eso basta para ver la web en
modo solo lectura.

Si tienes la contraseña de la base de datos (la reparten los responsables del proyecto por un canal
privado; nunca va en el repositorio), abre el `.env` (`notepad .env` en Windows, `open -e .env` en
macOS, `nano .env` en Linux) y completa la línea `SUPABASE_DB_URL=` con la cadena de conexión que
viene de ejemplo en el comentario justo encima, reemplazando `TU_PASSWORD` por la contraseña. Si la
contraseña tiene `$`, encierra todo el valor entre comillas simples
(`SUPABASE_DB_URL='postgresql://...'`); si tiene `@ : / # ? %`, escríbelos codificados para URL
(por ejemplo `@` como `%40`).

Si no la tienes, deja `SUPABASE_DB_URL=` vacío. No pongas una contraseña que no sepas si es correcta:
tras varios intentos fallidos, Supabase bloquea tu IP un rato.

**3. Construir y levantar**

La primera vez tarda varios minutos (descarga y construye las imágenes); las siguientes, segundos.

- **Sin la contraseña (modo solo lectura):** levanta la web, la API y Redis. La web muestra los datos
  que mantiene al día el worker del proyecto, que corre en otra máquina.

  ```
  docker compose up -d --build frontend
  ```

  En este modo agrega siempre `frontend` al final de `docker compose up`: sin él también arranca el
  worker, que sin contraseña no puede actualizar nada.

- **Con la contraseña:** levanta todo, incluido el worker que baja los datos de las fuentes
  oficiales y los guarda en la base.

  ```
  docker compose up -d --build
  ```

Al terminar, `docker compose ps` muestra los servicios en estado `Up`.

**4. Abrir la web**

- Web: <http://localhost:8080>. El navegador pide permiso para usar tu ubicación: si lo das, el mapa
  se centra donde estás; si no, se queda en la ciudad de Cajamarca. Los datos aparecen en unos
  segundos. Si el panel dice "sin actualizar desde…", en ese momento no hay ningún worker
  actualizando la base.
- API: <http://localhost:8000/health> (responde `{"ok":true,"service":"simpac-api"}`) y
  <http://localhost:8000/api/snapshot>

Con la contraseña, al arrancar el worker corre una vez todas sus tareas (tarda uno o dos minutos) y
después las repite por su cuenta según su horario. Para verlo:

```
docker compose logs -f worker
```

Cada tarea termina con una línea `Task backend.celery_app.<nombre>[...] succeeded`. `Ctrl + C` sale
de los logs sin detener nada.

**5. Detener**

```
docker compose down
```

Mientras no lo detengas, Docker lo vuelve a levantar solo cada vez que se abre. Para levantarlo más
tarde basta `docker compose up -d frontend` (solo lectura) o `docker compose up -d` (con
contraseña); `--build` solo hace falta si cambió el código o el `.env`.

## Comandos útiles de Docker

| Para qué | Comando |
|---|---|
| Ver qué servicios están corriendo | `docker compose ps` |
| Ver los logs del worker (salir con `Ctrl + C`) | `docker compose logs -f worker` |
| Ver los logs de la API | `docker compose logs -f backend` |
| Levantar de nuevo tras cambiar el código o el `.env` | `docker compose up -d --build` (solo lectura: `docker compose up -d --build frontend`) |
| Reiniciar un servicio | `docker compose restart worker` |
| Detener todo | `docker compose down` |
| Correr las pruebas del backend en un contenedor | `docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 -v "${PWD}:/app" worker python -m unittest discover -s backend/tests -t .` |

Las imágenes no traen las pruebas, por eso el último comando monta la carpeta del proyecto
(`${PWD}` funciona en PowerShell, macOS y Linux; en Git Bash hay que anteponer
`MSYS_NO_PATHCONV=1`). La primera vez construye la imagen del worker.

**Correr una tarea del worker a mano** (con la contraseña en el `.env`):

| Tarea | Qué hace | Comando |
|---|---|---|
| `ingesta` (cada hora) | estaciones y lluvia de SENAMHI, caudales de la ANA, índices El Niño, alertas de ríos | `docker compose run --rm worker python -m backend.ingesta` |
| `enfen` (cada 6 h) | comunicado oficial del ENFEN e índice del mar (ICEN) | `docker compose run --rm worker python -m backend.ingesta.enfen` |
| `avisos` (cada hora) | avisos de SENAMHI como áreas en el mapa, con sus íconos | `docker compose run --rm worker python -m backend.ingesta.avisos` |
| `lluvia_nacional` (cada 30 min) | lluvia de la última hora en ~216 estaciones del país y alertas de lluvia | `docker compose run --rm worker python -m backend.ingesta.lluvia_nacional` |
| `pronostico` (cada hora) | pronóstico de SENAMHI por localidad (hoy, mañana y pasado) | `docker compose run --rm worker python -m backend.ingesta.pronostico` |
| `nowcast` (cada 10 min) | lluvia de las próximas 1 a 2 horas (producto experimental de SENAMHI) | `docker compose run --rm worker python -m backend.ingesta.nowcast` |

## Configuración (`.env`)

| Variable | Qué es | ¿Secreta? |
|---|---|---|
| `SUPABASE_URL` | Dirección del proyecto de Supabase | No |
| `SUPABASE_PUBLISHABLE_KEY` | Llave pública de lectura (la usan la web y la API) | No, es pública por diseño |
| `SUPABASE_DB_URL` | Conexión a la base para que el worker escriba; vacía = modo solo lectura. Usa el *pooler* de Supabase (IPv4): la conexión directa `db.<ref>.supabase.co` es solo IPv6 y Docker no tiene IPv6 | **Sí** |
| `SIMPAC_LLUVIA_DEPTS` | Opcional. Departamentos (slugs de SENAMHI separados por coma, p. ej. `cajamarca,la-libertad`) cuya serie de lluvia hora por hora se guarda. Por defecto `cajamarca` | No |
| `SNAPSHOT_TTL` | Opcional. Segundos que vive la caché de la API (por defecto 900) | No |

El archivo `.env` nunca se sube a git (ya está en `.gitignore`).

## Desarrollo sin Docker (opcional)

**Web con recarga en vivo** (Node.js 22 o superior)

```
cd frontend
npm install
cp .env.example .env
npm run dev
```

`cp .env.example .env` crea `frontend/.env` desde su plantilla (ya trae los valores públicos).
`npm run dev` deja la web en <http://localhost:5173> y ocupa la terminal hasta que la detienes con
`Ctrl + C`; si Windows pregunta por el firewall, basta permitir redes privadas. Dentro de `frontend`
también están `npm test` (pruebas del frontend) y `npm run build` (compilación de producción en
`frontend/dist`). Si `npm install` avisa de vulnerabilidades, no hace falta hacer nada: no corras
`npm audit fix --force`, que cambia de versión mayor herramientas de desarrollo.

En Windows, si PowerShell dice que `npm.ps1` no se puede cargar porque la ejecución de scripts está
deshabilitada, escribe `npm.cmd` en lugar de `npm` (por ejemplo `npm.cmd install`), o usa el Símbolo
del sistema (cmd).

**Pruebas del backend** (Python 3.12 o superior; solo usan la librería estándar, sin red ni base de
datos). Desde la raíz del repositorio (si estás en `frontend`, primero `cd ..`):

```
python -m unittest discover -s backend/tests -t .
```

Necesitan SQLite 3.39 o más nuevo, que ya viene con Python 3.12 en Windows y macOS; en Linux depende
del sistema. Para comprobarlo: `python -c "import sqlite3; print(sqlite3.sqlite_version)"`. Si
`python` no se reconoce, usa `py` en Windows o `python3` en macOS y Linux.

**Vista rápida en consola** de los datos de las fuentes, sin base ni Docker:

```
python -m backend.prototipo.demo
```

## Usar tu propia base de datos (opcional)

Para no depender de la base del proyecto:

1. Crear un proyecto gratuito en [supabase.com](https://supabase.com).
2. Aplicar las migraciones **en orden** (por nombre de archivo) desde `supabase/migrations/`. Lo más
   simple es pegar el contenido de cada archivo, uno por uno, en el *SQL Editor* de Supabase. La
   primera activa PostGIS y crea las tablas; las demás las van completando. No actives PostGIS antes
   desde el panel: la primera migración lo activa donde las demás lo esperan. Si el editor pide
   confirmar una operación destructiva (`drop table`), en un proyecto nuevo es seguro aceptar.
3. En el `.env`, poner la dirección del proyecto y la llave pública (botón **Connect**, o
   *Project Settings → API Keys*) y la cadena del *pooler* (**Connect → Session pooler**), cambiando
   `[YOUR-PASSWORD]` por la contraseña que elegiste al crear el proyecto (se puede cambiar en
   *Project Settings → Database*). Si usas `npm run dev`, pon también la dirección y la llave en
   `frontend/.env`.
4. `docker compose up -d --build`. En los primeros minutos el worker llena la base con datos reales.
5. Los mapas de eventos El Niño pasados se cargan aparte, una sola vez:

   ```
   docker compose run --rm worker python -m backend.mapas.cargar_fen --simplificar 0.005 --decimales 4 --aplicar
   ```

   La capa "Lluvia del mes frente a lo normal" no tiene cargador automático y quedará vacía.

## Problemas comunes

| Síntoma | Qué hacer |
|---|---|
| `Cannot connect to the Docker daemon` o `error during connect` | Docker no está corriendo. Windows y macOS: abre Docker Desktop y espera a que diga *Engine running*. Linux: `sudo systemctl start docker` |
| `permission denied while trying to connect to the Docker daemon socket` (Linux) | `sudo usermod -aG docker $USER`, cierra sesión y vuelve a entrar (o antepone `sudo`) |
| `no configuration file provided: not found` | No estás en la carpeta del proyecto: entra con `cd` a la que tiene `docker-compose.yml` |
| Al levantar sale `The "SUPABASE_URL" variable is not set` y la web queda en blanco | Falta el `.env` en la raíz (paso 2). Créalo y ejecuta `docker compose up -d --build frontend` |
| `port is already allocated`, `address already in use` o `Ports are not available` | Otro programa u otro contenedor usa el puerto 8080, 8000 o 6379. Ciérralo, o en `docker-compose.yml` cambia el número del lado de tu máquina: `"8081:80"` para la web (quedaría en http://localhost:8081), `"8001:8000"` para la API o `"127.0.0.1:6380:6379"` para Redis |
| En los logs del worker: `Falta SUPABASE_DB_URL` | La línea `SUPABASE_DB_URL` del `.env` está vacía: es el modo solo lectura. Si tienes la contraseña, complétala (paso 2) y ejecuta `docker compose up -d` |
| En los logs del worker: `password authentication failed`, `Circuit breaker open` o `connection refused` | La contraseña del `.env` no es correcta. Detén el worker (`docker compose stop worker`) para no acumular intentos fallidos, corrige la contraseña o déjala vacía, y vuelve a levantarlo. Si Supabase bloqueó tu IP, espera unos 30 minutos |
| El worker no conecta a la base (`ENOIDENTIFIER`, *timeout*, *network unreachable*) | Usa la cadena del *pooler* (`...pooler.supabase.com`) y que el usuario sea `postgres.<ref>`, no solo `postgres` |
| Cambié el `.env` y la web sigue igual | La web guarda sus variables al construirse: `docker compose up -d --build frontend` |
| La web carga pero el mapa sale gris | Falta internet o el proveedor del mapa base no respondió. El mapa base (Stadia Maps) es gratuito en `localhost`; publicado en un dominio propio, o abierto desde otra computadora por la IP de la red, pide una llave gratuita de Stadia |
| El panel dice "sin actualizar desde…" | Ningún worker está actualizando la base en ese momento (modo solo lectura) o una fuente oficial no respondió; el panel avisa cuál |
| No aparece la capa de lluvia de las próximas horas | Es un producto experimental de SENAMHI que a veces deja de publicarse; la capa lo explica en su nota y vuelve sola |

## Estructura del repositorio

```
backend/        API (app.py), worker (celery_app.py), conectores a las fuentes (connectors/),
                tareas de ingesta (ingesta/), cargador de mapas (mapas/), prototipo sin
                dependencias (prototipo/) y pruebas (tests/)
frontend/       web en React + Vite + Tailwind + Leaflet (ver frontend/README.md)
supabase/       migraciones de la base (migrations/) y esquema consolidado (schema.sql)
docs/           documentación técnica y estado del proyecto
docker-compose.yml, .env.docker.example
```

## Documentación

- [`docs/README-tecnico.md`](docs/README-tecnico.md): arquitectura, fuentes y sus endpoints, tareas
  del worker, reglas de las alertas y consultas de diagnóstico.
- [`docs/ESTADO.md`](docs/ESTADO.md): qué está hecho y qué falta.
- [`frontend/README.md`](frontend/README.md): capas del mapa, lenguaje claro y cómo lee los datos la
  web.

## Fuentes de datos

SENAMHI (estaciones, avisos, pronóstico, mapas), la ANA (caudales y umbrales de ríos), ENFEN
(comunicados y estado del sistema de alerta), IGP (índice costero El Niño), NOAA (índice RONI) y NASA
(lluvia satelital). Los datos de SENAMHI se muestran con la leyenda que exigen sus términos de uso:
"Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú.
El uso que se le da a esta información es de mi (nuestra) entera responsabilidad".
