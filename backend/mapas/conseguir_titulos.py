import requests
import xml.etree.ElementTree as ET

def obtener_todos_los_titulos():
    url = "https://idesep.senamhi.gob.pe/geonetwork/srv/eng/csw"
    
    # Petición GET sin el parámetro "constraint" para traer todos los registros
    params = {
        "service": "CSW",
        "version": "2.0.2",
        "request": "GetRecords",
        "resultType": "results",
        "elementSetName": "summary",
        "typeNames": "csw:Record",
        "maxRecords": "1000" # Un límite alto para asegurar que traiga todo el catálogo
    }

    try:
        print("-> Consultando el catálogo completo del Senamhi...")
        response = requests.get(url, params=params)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        namespaces = {
            'csw': 'http://www.opengis.net/cat/csw/2.0.2',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }

        # Extraer todas las etiquetas <dc:title>
        nodos_titulo = root.findall('.//dc:title', namespaces)
        
        # Limpiar espacios y eliminar duplicados convirtiendo la lista en un set
        titulos = sorted(list(set([t.text.strip() for t in nodos_titulo if t.text])))

        print(f"\n=== SE ENCONTRARON {len(titulos)} MAPAS ===")
        for idx, titulo in enumerate(titulos, 1):
            print(f"{idx}. {titulo}")

    except Exception as e:
        print(f"Ocurrió un error al conectar o parsear: {e}")

if __name__ == "__main__":
    obtener_todos_los_titulos()