# SIMPAC

**Sistema de Información Meteorológica y Prevención de Anomalías de Cajamarca.** Plataforma web (y
app Android) que centraliza datos hidrometeorológicos oficiales del Perú, con foco en Cajamarca, para
seguir el fenómeno El Niño y sus efectos: avisos de SENAMHI, estado del sistema de alerta del ENFEN,
ríos de la ANA (el Mashcón vigilado y los 100 ríos del país con estación), lluvia medida y
pronosticada, alertas por zona y a dónde acudir en una emergencia, explicados en lenguaje claro sobre
un mapa. Además del mapa tiene las páginas Alertas, Comunidad (reportes ciudadanos con cuenta), Chat
por departamento, Cuenta e Histórico por estación.

## Cómo está armado

| Parte | Qué es | Dónde se ve |
|---|---|---|
| `frontend` | Web en React + Vite + Leaflet + react-router, servida por nginx (comprimida con gzip y con caché de un año para los archivos con hash) | http://localhost:8080 |
| `backend` | API de solo lectura en FastAPI (CORS solo para los orígenes de la web y la app) | http://localhost:8000/health |
| `worker` | Celery + beat: cada cierto tiempo baja los datos de las fuentes oficiales, los guarda en la base y redacta el titular por departamento | (sin puerto; ver sus logs) |
| `redis` | Caché de la API y cola de tareas del worker | solo dentro de la máquina |
| Base de datos | PostgreSQL + PostGIS en Supabase (en la nube, no corre en tu computadora); también las cuentas (Supabase Auth), las fotos de los reportes (bucket `reportes`) y el chat en vivo (Realtime) | — |
| App Android | La misma web empaquetada con Capacitor (`frontend/android/`); se compila aparte, sin Docker | ver [App Android](#app-android) y [`appmobile/README.md`](appmobile/README.md) |

La web lee la base directamente con una llave **pública**: los datos los protegen las reglas de
seguridad por fila de la base, no el secreto de la llave. Solo el worker escribe los datos oficiales,
y para eso necesita la contraseña de la base; una persona con cuenta solo puede escribir sus propios
reportes, votos y mensajes del chat.

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
- Solo para compilar la app Android (opcional): **JDK 21** y el **Android SDK** (ver
  [App Android](#app-android)).

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

- Web: <http://localhost:8080>. La primera vez muestra la pantalla "Mira cómo está tu zona" y, si
  aceptas, el navegador pide permiso para usar tu ubicación: si lo das, el mapa se centra donde
  estás; si no, se queda en la ciudad de Cajamarca (se puede elegir otra de las 25 ciudades). La hoja
  "Tu zona ahora" muestra el semáforo, el titular y la instrucción en menos de un segundo; las capas
  terminan de cargar en unos tres segundos. Si la hoja dice "sin actualizar desde…", en ese momento
  no hay ningún worker actualizando la base.
- Páginas de la web (todas abren también escribiendo la dirección directa):

  | Ruta | Qué muestra |
  |---|---|
  | `/` | Mapa con la hoja "Tu zona ahora" (semáforo, titular, distancia al río, a dónde acudir, teléfonos 105 y 116 en alerta o emergencia) |
  | `/alertas` | Alertas y avisos vigentes de tu zona o de todo el país, avisos de SENAMHI con sus días, ríos vigilados y pestaña "Pasadas" (hasta 30 días) |
  | `/comunidad`, `/comunidad/nuevo`, `/comunidad/<id>` | Reportes ciudadanos vigentes, formulario para reportar (pide cuenta y GPS) y detalle con votos |
  | `/chat` | Chat del departamento (pide cuenta; los mensajes duran 2 horas) |
  | `/cuenta`, `/cuenta/entrar`, `/cuenta/registro` | Entrar, crear cuenta, recuperar contraseña, nombre, mi zona y mis reportes |
  | `/historico?tipo=rio\|lluvia&id=<estación>&rio=<río>&rango=24h\|7d\|30d` | Gráfico, tabla y CSV de una estación (se abre desde los popups del mapa) |

  En celular las páginas van a pantalla completa sobre el mapa, con una barra inferior de 5 pestañas
  (Mapa, Alertas, Comunidad, Chat, Cuenta); desde 1024 px de ancho, en una columna al lado del mapa.
- API: <http://localhost:8000/health> (responde `{"ok":true,"service":"simpac-api"}`) y
  <http://localhost:8000/api/snapshot> (JSON de unos 46 KB con el resumen que arma el worker)

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
| `rios` (cada hora) | avisos hidrológicos de SENAMHI de todo el país, con su detalle (hora, caudal, umbral rojo y si es de crecida o de vaciante): colorean la zona que el río Mashcón podría afectar y el cauce de los ríos del país | `docker compose run --rm worker python -m backend.ingesta.rios` |
| `titular` (cada 30 min) | titular en lenguaje claro por departamento (24 + Callao) a partir de las alertas, los avisos, los ríos, la lluvia y el ENFEN ya guardados; sin `SIMPAC_LLM_KEY` lo arman reglas fijas (nunca crea alertas) | `docker compose run --rm worker python -m backend.ingesta.titular` |

Además, cada 5 minutos la tarea interna `refresh_cache` rearma el resumen que sirve la API
(`/api/snapshot`). Al arrancar, el worker encola todas las tareas de datos y el titular corre 5
minutos después, cuando las demás ya escribieron.

## Configuración (`.env`)

| Variable | Qué es | ¿Secreta? |
|---|---|---|
| `SUPABASE_URL` | Dirección del proyecto de Supabase | No |
| `SUPABASE_PUBLISHABLE_KEY` | Llave pública de lectura (la usan la web y la API) | No, es pública por diseño |
| `SUPABASE_DB_URL` | Conexión a la base para que el worker escriba; vacía = modo solo lectura. Usa el *pooler* de Supabase (IPv4): la conexión directa `db.<ref>.supabase.co` es solo IPv6 y Docker no tiene IPv6 | **Sí** |
| `SIMPAC_LLUVIA_DEPTS` | Opcional. Departamentos (slugs de SENAMHI separados por coma, p. ej. `cajamarca,la-libertad`) cuya serie de lluvia hora por hora se guarda. Por defecto `cajamarca` | No |
| `SNAPSHOT_TTL` | Opcional. Segundos que vive la caché de la API (por defecto 900) | No |
| `SIMPAC_LLM_KEY` | Opcional. Clave de la API de Anthropic para que la tarea `titular` redacte el titular de cada departamento con un modelo de lenguaje (también vale `ANTHROPIC_API_KEY`). Vacía = el titular lo arman reglas fijas en Python, sin ningún pedido externo. Con clave, se pide una sola redacción por departamento y solo cuando cambian sus datos; el texto se valida contra las cifras antes de guardarse | **Sí** |
| `SIMPAC_LLM_MODELO` | Opcional. Modelo que usa `titular` cuando hay clave (por defecto `claude-haiku-4-5-20251001`) | No |
| `SIMPAC_CORS_ORIGENES` | Opcional. Orígenes (`esquema://host:puerto`, separados por coma) a los que responde la API. Vacío = `http://localhost:8080`, `http://localhost:5173`, `https://localhost` y `capacitor://localhost` (la web de Docker, Vite y la app Android). Publicada en un dominio, poner el de la web | No |

El archivo `.env` nunca se sube a git (ya está en `.gitignore`). Todas las variables están
comentadas en `.env.docker.example`. El mapa base (Stadia Maps) no necesita variable: sirve sin llave
en `localhost` y en la app; para un dominio propio hay que pedir su llave gratuita y agregarla a la
dirección de los tiles en `frontend/src/map/baseMap.js`.

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

6. El río Mashcón (el río resaltado, las zonas que podría afectar y sus desbordes pasados) también
   se carga aparte, una sola vez, desde los archivos de `backend/data/rios/mashcon/`. Sin `--aplicar`
   solo revisa los archivos y muestra el resumen ("13 zonas ..., 14 incidentes"); con `--aplicar`
   los escribe (se puede repetir sin duplicar nada):

   ```
   docker compose run --rm worker python -m backend.mapas.cargar_rios
   docker compose run --rm worker python -m backend.mapas.cargar_rios --aplicar
   ```

   Los avisos hidrológicos del río los trae solo el worker (tarea `rios`).

7. Los ríos del país (el trazo de los 100 ríos que tienen estación de caudal de la ANA o aviso
   hidrológico de SENAMHI) también se cargan una sola vez, después de las migraciones. Sin
   `--aplicar` es una prueba en seco que revisa la lista y muestra una línea por río; con `--aplicar`
   los escribe (se puede repetir sin duplicar nada). `--desde-copia` usa las copias que ya vienen en
   el repo (`backend/data/cauces/`, 105 archivos GeoJSON, 2,98 MB) en vez de consultar a ANA -
   GeoSNIRH en vivo (sin la opción tarda unos 6 minutos):

   ```
   docker compose run --rm worker python -m backend.mapas.cargar_cauces --desde-copia
   docker compose run --rm worker python -m backend.mapas.cargar_cauces --desde-copia --aplicar
   ```

   Los ríos sin trazo (el lago Titicaca, el canal Canopampa, Sumbay y Chunchuca) salen listados y
   no se inventan. Repetir la carga cuando `caudal_actual` gane estaciones: la prueba en seco lista
   los ríos que aún no tienen fila. Otras opciones: `--rio <nombre>` (uno solo), `--forzar`,
   `--recorte KM`, `--podar` (con `--aplicar`, borra los ríos que ya no se buscan).

8. Los lugares de "A dónde acudir" (hospitales y postas, comisarías, bomberos y Defensa Civil) se
   cargan desde los archivos de `backend/data/acudir/` (ya vienen en el repo: salud de Cajamarca,
   comisarías y bomberos de todo el país y 3 puntos de Defensa Civil). Sin `--aplicar` solo valida
   los archivos y muestra el resumen ("2540 puntos: salud 1001 (24 h: 42) ..."); con `--aplicar` los
   escribe (se puede repetir sin duplicar nada). Con `--descargar` vuelve a bajar las fuentes
   oficiales (RENIPRESS, CENEPRED, CGBVP) y con `--pais` carga también la salud de todo el país
   (baja un CSV de 20 MB a una carpeta temporal, no al repo):

   ```
   docker compose run --rm worker python -m backend.mapas.cargar_acudir
   docker compose run --rm worker python -m backend.mapas.cargar_acudir --aplicar
   docker compose run --rm worker python -m backend.mapas.cargar_acudir --descargar --pais --aplicar
   ```

   Sin `--podar` nunca borra nada. Los números de emergencia del panel "Llama a" no están en la
   base: viven en `backend/data/acudir/numeros.json` y en su copia `frontend/src/data/emergencias.js`.
   No hay albergues ni zonas seguras porque ninguna fuente oficial los publica georreferenciados;
   cuando la municipalidad publique su lista se cargarán con su fuente.

9. Para que funcionen las cuentas, los reportes con foto y el chat: la migración
   `20261014105232_comunidad_fotos_y_chat_realtime` crea el bucket público `reportes` (3 MB por
   foto, solo JPEG/PNG/WebP) y publica la tabla del chat por Realtime; en el panel de Supabase hay que
   dejar activo el proveedor *Email* de Authentication y agregar en *Authentication → URL
   Configuration* la dirección de la web (los correos de confirmación y de contraseña nueva vuelven a
   `<dirección de la web>/cuenta`).

La capa "Lluvia del mes frente a lo normal" no tiene cargador automático y quedará vacía.

## App Android

La app es la misma web empaquetada con [Capacitor](https://capacitorjs.com/): un proyecto Android
normal en `frontend/android/` que abre la web compilada en un WebView y usa el GPS del teléfono. No
se compila con Docker. Los detalles (decisiones, firma, Play Console, emulador, notificaciones
pendientes) están en [`appmobile/README.md`](appmobile/README.md).

**Requisitos**: Node.js 22 o superior con las dependencias del front instaladas (`cd frontend && npm
install`), `frontend/.env` (paso "Desarrollo sin Docker"), **JDK 21** y el **Android SDK** con
`platforms;android-36`, `build-tools;36.0.0` y `platform-tools` (los instala Android Studio desde
*SDK Manager*), con `JAVA_HOME` y `ANDROID_HOME` definidos. La primera compilación baja Gradle y las
dependencias (unos 500 MB).

**Comandos** (desde `frontend/`; en macOS y Linux reemplazar `gradlew` por `./gradlew` dentro de
`android/`):

| Comando | Qué hace | Resultado |
|---|---|---|
| `npm run android:sync` | compila la web y la copia al proyecto Android (`npx cap sync android`); hay que correrlo cada vez que cambia la web | `android/app/src/main/assets/public/` |
| `npm run android:apk` | sync + APK de prueba firmado con la llave de depuración, para instalar directo con `adb install -r` | `android/app/build/outputs/apk/debug/app-debug.apk` (5,3 MB el 2026-10-20) |
| `npm run android:aab` | sync + paquete para Play Console (firmado si hay `key.properties`) | `android/app/build/outputs/bundle/release/app-release.aab` |
| `npm run android:apk:release` | sync + APK firmado para repartir fuera de la tienda | `android/app/build/outputs/apk/release/app-release.apk` |
| `npm run android:open` / `npm run android:run` | abrir en Android Studio / instalar y abrir en el emulador o teléfono conectado | — |

En Windows los scripts se corren desde PowerShell (desde Git Bash `gradlew.bat` no se encuentra por
la conversión de rutas de MSYS). La compilación de prueba del 2026-10-20 tardó 9 s de Gradle con el
daemon caliente, más 9 s del build de la web y 2 s del sync.

**Firma para publicar**: Google Play exige un paquete firmado con una llave propia que se crea una
sola vez con `keytool` y no se sube al repo (`key.properties`, `*.jks` y `*.keystore` están en
`.gitignore`). `frontend/android/app/build.gradle` lee la llave de `frontend/android/key.properties`
o, si no existe, de las variables de entorno `SIMPAC_KEYSTORE_FILE`, `SIMPAC_KEYSTORE_PASSWORD`,
`SIMPAC_KEY_ALIAS` y `SIMPAC_KEY_PASSWORD`; sin ninguna de las dos el release se compila sin firmar.
Antes de cada publicación subir `versionCode` y `versionName` en ese mismo archivo. Identificador de la
app: `pe.simpac.app`; Android mínimo 7.0 (API 24), `targetSdk` 36.

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
| Al construir la web en Docker sale `npm warn EBADENGINE` por `@supabase/supabase-js` | La imagen usa `node:20-alpine` y la librería pide Node 22 o superior; compila y corre igual. Pendiente subir `frontend/Dockerfile` a `node:22-alpine` |
| El titular de la hoja dice lo mismo que la barra lateral y no cambia aunque haya clave del LLM | Sin `SIMPAC_LLM_KEY` el titular lo arman reglas (`origen = reglas`); con clave, el worker hay que recrearlo (`docker compose up -d worker`) y el modelo solo se consulta cuando cambian los datos del departamento. `docker compose logs worker` muestra el resumen de cada corrida de `titular` |
| Al compilar la app Android: `Duplicate resources` en `mergeDebugAssets` | El build de la web deja un `.gz` junto a cada `.js`/`.css` y Capacitor los copia al proyecto; `frontend/android/app/build.gradle` ya los excluye con `!*.gz` en `ignoreAssetsPattern`. Si vuelve a pasar, revisar que esa línea siga ahí |
| `gradlew: command not found` o `cmd //c gradlew.bat` no encuentra el script | Correr los comandos `npm run android:*` desde PowerShell (Windows) o usar `./gradlew` dentro de `frontend/android` (macOS, Linux) |

## Estructura del repositorio

```
backend/        API (app.py), worker (celery_app.py), conectores a las fuentes (connectors/),
                tareas de ingesta y el titular (ingesta/), cargadores de mapas, ríos y lugares a
                dónde acudir (mapas/), datos revisados a mano y copias de las fuentes (data/:
                rios/, cauces/, acudir/), prototipo sin dependencias (prototipo/) y pruebas
                (tests/, 657 pruebas)
frontend/       web en React + Vite + Tailwind + Leaflet + react-router (ver frontend/README.md);
                148 pruebas con node --test
frontend/android/  proyecto Android de la app (Capacitor); lo generado por Gradle no se versiona
appmobile/      documentación de la app Android
supabase/       migraciones de la base (migrations/, 32 archivos) y esquema consolidado (schema.sql)
docs/           documentación técnica y estado del proyecto
docker-compose.yml, .env.docker.example
```

## Documentación

- [`docs/README-tecnico.md`](docs/README-tecnico.md): arquitectura, fuentes y sus endpoints, tareas
  del worker, reglas de las alertas y consultas de diagnóstico.
- [`docs/ESTADO.md`](docs/ESTADO.md): qué está hecho y qué falta.
- [`docs/guia-medicion.md`](docs/guia-medicion.md): cómo medir el software para las fichas ISO/IEC
  25010 del curso (casos de prueba, tiempos, carga, guion de usabilidad).
- [`frontend/README.md`](frontend/README.md): capas del mapa, páginas, lenguaje claro y cómo lee los
  datos la web.
- [`appmobile/README.md`](appmobile/README.md): la app Android (compilar, firmar, publicar).
- [`backend/data/acudir/README.md`](backend/data/acudir/README.md): los archivos de "A dónde
  acudir" y su fuente.

## Fuentes de datos y licencias

SENAMHI (estaciones, avisos, avisos hidrológicos, pronóstico, mapas), la ANA (caudales y umbrales de
ríos, faja marginal y emergencias hídricas), ENFEN (comunicados y estado del sistema de alerta), IGP
(índice costero El Niño), NOAA (índice RONI) y NASA (lluvia satelital). Para el río Mashcón, además: el
estudio INDECI-PNUD 2005, el trazo de OpenStreetMap (© colaboradores de OpenStreetMap, licencia ODbL)
y el modelo de elevación Copernicus GLO-30 (© DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH
2014-2018, provisto bajo COPERNICUS por la Unión Europea y la ESA). Los datos de SENAMHI se muestran
con la leyenda que exigen sus términos de uso:
"Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú.
El uso que se le da a esta información es de mi (nuestra) entera responsabilidad".

| Dato | Fuente | Licencia o condición de uso |
|---|---|---|
| Trazo de los ríos del país | ANA - GeoSNIRH: red hidrográfica oficial R.J. N.º 056-2018-ANA (DCERH, 2018) y, donde esa no tiene el río, la Carta Nacional 1:100 000 del IGN publicada por la ANA | Información pública del Estado sin texto de licencia; cada río guarda su fuente, la URL consultada y la atribución, y la web la muestra en el popup |
| Establecimientos de salud | SUSALUD, Registro Nacional de IPRESS (RENIPRESS) vía datosabiertos.gob.pe (CSV del 30-09-2026) | ODC-By, con la atribución "Fuente: SUSALUD, Registro Nacional de IPRESS (RENIPRESS), datosabiertos.gob.pe" |
| Comisarías | MININTER, padrón de comisarías básicas a noviembre de 2019, servido por CENEPRED/COEN como puntos | ODC-By (ficha de MININTER); la web avisa que el padrón es de 2019 |
| Compañías de bomberos | CGBVP (directorio del portal: dirección y teléfono) y CENEPRED/COEN (ubicación) | Información pública institucional sin licencia declarada |
| Defensa Civil, números de emergencia y recomendación de zona segura | Fichas de gob.pe (INDECI, Municipalidad Provincial y Gobierno Regional de Cajamarca, DIRESA) y la campaña "Preparados ante lluvias intensas" de INDECI | Contenido público del Estado; verificados el 14-10-2026, con la fecha guardada por punto |
| Mapa base | Stadia Maps (estilo Alidade Smooth) sobre OpenMapTiles y OpenStreetMap | Gratuito en `localhost` y en la app; en un dominio propio pide su llave gratuita; la atribución va siempre en el mapa |
| Tipografías | Geist e Inter, servidas por Google Fonts | Licencia SIL Open Font |

Las zonas que el río Mashcón podría afectar son una estimación de SIMPAC a partir del relieve o
vienen del estudio INDECI-PNUD 2005, y la web lo dice en cada una: ninguna es un mapa oficial. La app
y la web no son un canal oficial de SENAMHI, la ANA ni INDECI: el aviso oficial llega por SISMATE,
INDECI y Defensa Civil.
