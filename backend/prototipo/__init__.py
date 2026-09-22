"""
Prototipo de SIMPAC sin dependencias (SQLite + http.server), congelado.

Fue la primera versión: sirve para mostrar los conectores funcionando sin Docker
ni Supabase. Lo que corre en producción es app.py + celery_app.py + ingesta/.

    python -m backend.prototipo.demo     # foto rápida en consola (sin BD)
    python -m backend.prototipo.ingest   # guarda una pasada en backend/prototipo/simpac.db
    python -m backend.prototipo.api      # API JSON en http://localhost:8000
"""
