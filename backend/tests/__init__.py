"""
Pruebas sin red ni BD (las fuentes y Supabase se simulan). Desde la raíz del repo:

    python -m unittest discover -s backend/tests -t .

No necesitan Docker ni instalar nada: solo usan módulos de la librería estándar
(no importan FastAPI, Celery, Redis ni geopandas).
"""
