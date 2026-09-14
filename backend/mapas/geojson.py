import os
import re
import tempfile
import requests
import geopandas as gpd
from bs4 import BeautifulSoup

def obtener_geojson_por_uuid(uuid: str) -> str:
    """
    Consulta el API de GeoNetwork mediante un UUID, busca un archivo adjunto .zip (Shapefile),
    lo descarga y lo convierte a formato GeoJSON.
    """
    url_base = f"https://idesep.senamhi.gob.pe/geonetwork/srv/api/0.1/records/{uuid}"
    print(f"Consultando metadata HTML: {url_base}")

    # 1. Hacer el GET para obtener el HTML
    respuesta_html = requests.get(url_base)
    respuesta_html.raise_for_status()

    # 2. Buscar el enlace del ZIP en el HTML
    enlace_zip = None
    soup = BeautifulSoup(respuesta_html.text, 'html.parser')
    
    # Estrategia A: Buscar etiquetas <a> con href que termine en .zip
    for a in soup.find_all('a', href=True):
        if a['href'].endswith('.zip') and '/attachments/' in a['href']:
            enlace_zip = a['href']
            break

    # Estrategia B: Si está oculto en un script o metadato, usar Regex
    if not enlace_zip:
        match = re.search(r'(https?://[^"\']+/attachments/[^"\']+\.zip)', respuesta_html.text)
        if match:
            enlace_zip = match.group(1)

    if not enlace_zip:
        raise ValueError(f"No se encontró ningún enlace a un archivo .zip para el UUID: {uuid}")

    print(f"Enlace del Shapefile encontrado: {enlace_zip}")

    # 3. Descargar el archivo ZIP
    print("Descargando el archivo ZIP...")
    respuesta_zip = requests.get(enlace_zip)
    respuesta_zip.raise_for_status()

    # 4. Guardar temporalmente para que GeoPandas pueda leerlo
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
        tmp.write(respuesta_zip.content)
        ruta_temporal = tmp.name

    try:
        # 5. Leer el Shapefile desde el interior del ZIP usando GeoPandas
        print("Procesando Shapefile a GeoJSON...")
        # El protocolo zip:// le dice a Fiona/GeoPandas que lea el interior del archivo comprimido
        gdf = gpd.read_file(f"zip://{ruta_temporal}")

        # Opcional pero crítico: El estándar GeoJSON exige coordenadas WGS84 (EPSG:4326). 
        # Si el Shapefile viene en otro sistema (ej. UTM), esto lo reproyecta automáticamente.
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        # 6. Convertir a GeoJSON
        geojson_str = gdf.to_json()
        
        print("¡Conversión exitosa!")
        return geojson_str

    finally:
        # 7. Limpieza: Asegurarnos de borrar el archivo temporal del disco
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
