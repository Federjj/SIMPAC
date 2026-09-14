import requests
from types import MappingProxyType
import xml.etree.ElementTree as ET
from mapas_dic_subject import map_subjects

def buscar_mapa(titulo_buscar) -> list[str]:    
    res = []

    constraint_str = ""

    for subj in map_subjects[titulo_buscar]:
        if constraint_str != "":
            constraint_str += " AND "

        constraint_str += f"Subject = '{subj}'"

    print(f"-> Iniciando búsqueda para: {titulo_buscar}")

    url = "https://idesep.senamhi.gob.pe/geonetwork/srv/eng/csw"
    
    params = {
        "service": "CSW",
        "version": "2.0.2",
        "request": "GetRecords",
        "resultType": "results",
        "elementSetName": "summary",
        "typeNames": "csw:Record",
        "maxRecords": "10",
        "constraintLanguage": "CQL_TEXT",
        "constraint_language_version": "1.1.0",
        # Buscamos coincidencias en el título
        "constraint": constraint_str
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status() 

        print(f"-> Petición GET exitosa.")
        #print(f"-> URL generada: {response.url}\n")
        print("=== RESULTADO DEL SERVIDOR ===")
        print(response.text)
        """
        Devuelve esto...
        <?xml version="1.0" encoding="UTF-8"?>
<csw:GetRecordsResponse xmlns:csw="http://www.opengis.net/cat/csw/2.0.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/cat/csw/2.0.2 http://schemas.opengis.net/csw/2.0.2/CSW-discovery.xsd">
  <csw:SearchStatus timestamp="2026-09-13T17:41:36" />
  <csw:SearchResults numberOfRecordsMatched="1" numberOfRecordsReturned="1" elementSet="summary" nextRecord="0">
    <csw:SummaryRecord xmlns:dct="http://purl.org/dc/terms/" xmlns:geonet="http://www.fao.org/geonetwork" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:identifier>cea18ed0-13b7-423d-842f-109e16959453</dc:identifier>
      <dc:title>Temperatura Mínima Extrema - Percentil 5</dc:title>
      <dc:subject>temperatura, mínima, extrema, percentil 5</dc:subject>
      <dc:subject>climatologyMeteorologyAtmosphere</dc:subject>
      <dc:format>ESRI Shapefile</dc:format>
      <dct:abstract>Provee información climatológica (periodo 1965-2020) de la temperatura mínima extrema para los meses de mayo, junio, julio y agosto. El mapa muestra la distribución de las temperaturas mínimas extremas por debajo del percentil 5 a nivel nacional.</dct:abstract>
    </csw:SummaryRecord>
  </csw:SearchResults>
</csw:GetRecordsResponse>
        """
        root = ET.fromstring(response.content)
        namespaces = {
            'csw': 'http://www.opengis.net/cat/csw/2.0.2',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }

        identificadores = root.findall('.//dc:identifier', namespaces)

        print("\n=== IDENTIFICADORES ENCONTRADOS ===")
        if identificadores:
            for idx, ident in enumerate(identificadores, 1):
                print(f"Resultado {idx}: {ident.text}")
                res.append(ident.text)
        else:
            print("No se encontró ningún dc:identifier en la respuesta.")
        
        return res

    except requests.exceptions.RequestException as e:
        print(f"Ocurrió un error de conexión: {e}")
