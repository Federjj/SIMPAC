"""
Ejemplo: obtener mapas FEN y guardar GeoJSON localmente.

La lógica productiva está en backend/connectors/senamhi.py:mapas_fen()
que actúa como intermediario entre GeoNetwork y la BD.
"""
import sys
sys.path.insert(0, __file__.rsplit("backend", 1)[0])

from backend.connectors import senamhi
from backend.mapas.mapas_dic_subject import map_subjects

if __name__ == "__main__":
    mapas = senamhi.mapas_fen(map_subjects)

    if not mapas:
        print("No se encontraron mapas FEN")
        sys.exit(1)

    print(f"\n✓ Se encontraron {len(mapas)} mapas:")
    for mapa in mapas:
        print(f"  - {mapa.titulo}")
        print(f"    UUID: {mapa.uuid}")
        print(f"    Período: {mapa.periodo}")
        print(f"    GeoJSON size: {len(mapa.geojson)} bytes")

    # Guardar el primero como ejemplo
    if mapas:
        nombre_archivo = "datos_senamhi.geojson"
        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(mapas[0].geojson)
        print(f"\n✓ Primer mapa guardado en: {nombre_archivo}")