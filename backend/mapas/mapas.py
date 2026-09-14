from buscar_mapa import buscar_mapa
from geojson import obtener_geojson_por_uuid

if __name__ == "__main__":
    
    identifier = buscar_mapa("Anomalía de Precipitación – Mensual")[0]

    try:
        resultado_geojson = obtener_geojson_por_uuid(identifier)
        # Imprime solo los primeros 500 caracteres para no saturar la consola
        print("\n=== FRAGMENTO DEL GEOJSON ===")
        print(resultado_geojson[:500] + " ... [CONTENIDO TRUNCADO]")
        with open("datos_senamhi.geojson", "w", encoding="utf-8") as f:
            f.write(resultado_geojson)
    except Exception as e:
        print(f"Error durante el proceso: {e}")