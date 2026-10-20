# Datos de "A dónde acudir"

Archivos que lee `backend/mapas/cargar_acudir.py` para llenar la tabla `punto_acudir` (salud,
comisarías, bomberos y Defensa Civil). Los cuatro primeros los baja y reescribe el propio cargador
con `--descargar` (la fecha, la URL y la licencia de cada uno quedan en `fuentes.json`); los dos
últimos se editan a mano.

| Archivo | Qué es | Fuente y licencia |
|---|---|---|
| `fuentes.json` | url, fecha del dato (`actualizado`), fecha de descarga y licencia de cada archivo bajado | lo escribe `--descargar` |
| `renipress_cajamarca.csv` | RENIPRESS (Registro Nacional de IPRESS) tal cual lo publica SUSALUD (CSV separado por `;`, UTF-8 con BOM, 31 columnas), **solo las filas del departamento de Cajamarca** (unas 1800; el CSV del país pesa 20 MB y no va al repo: `--pais` lo baja a una caché temporal) | SUSALUD vía datosabiertos.gob.pe, ODC-By. Se publica un CSV al mes (`RENIPRESS_dd-mm-aaaa.csv`); `--descargar` toma el más reciente que enlaza la ficha |
| `comisarias_cenepred.json` | capa 12 `ComisariasBasicas` del servicio ArcGIS `sectores/COEN_FEN_2027` de CENEPRED, en GeoJSON WGS84, todo el país (~1320 puntos) | padrón MININTER "comisarías básicas a noviembre de 2019" (datosabiertos.gob.pe, ODC-By) servido por CENEPRED/COEN sin fecha ni licencia propias |
| `bomberos_cenepred.json` | capa 14 `Bomberos` del mismo servicio: el punto de cada compañía (~213) | CENEPRED/COEN; sin fecha en los metadatos |
| `bomberos_cgbvp.json` | directorio del portal del CGBVP: 28 comandancias y sus compañías (código, nombre, dirección, teléfonos, fundación). Se guarda **sin** el nombre del jefe ni la foto | CGBVP, `portal.bomberosperu.gob.pe` (API interna del sitio; responde solo con cabeceras de navegador). Información pública institucional, sin licencia declarada |
| `defensa_civil.json` | puntos capturados a mano de fichas de gob.pe: INDECI Cajamarca, Municipalidad Provincial de Cajamarca y sede del Gobierno Regional; coordenadas del enlace "Ver mapa" de cada ficha | gob.pe (contenido público del Estado). Cada punto lleva `fuente_url` y `detalle.verificado_en` |
| `numeros.json` | números de emergencia (nacionales y de Cajamarca) con su fuente, para el panel "Llama a". No van a la BD: el frontend tiene una copia idéntica en `frontend/src/data/emergencias.js` | gob.pe y RENIPRESS |

Lo que **no** hay aquí, a propósito: albergues, zonas seguras, puntos de reunión ni rutas de
evacuación. Al 14-10-2026 ninguna fuente oficial abierta los publica para Cajamarca ni para el país
(se revisaron el servicio ArcGIS de CENEPRED, SIGRID, el visor y los servidores de INDECI,
datosabiertos.gob.pe y las resoluciones de los planes de contingencia del GORE). Cuando la
municipalidad publique su lista se cargará con su `fuente_url`; nunca se dibuja una zona segura
estimada ni se presentan colegios como albergues.

Para refrescar: `docker compose run --rm worker python -m backend.mapas.cargar_acudir --descargar`
(agrega `--pais --aplicar` para cargar también la salud de todo el país). Si una fuente no responde,
su archivo anterior se queda como está.
