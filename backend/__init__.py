"""
Backend de SIMPAC.

  app.py         API FastAPI async (Docker: servicio backend)
  celery_app.py  worker + beat (Docker: servicio worker)
  config.py      configuración (variables de entorno) en un solo lugar
  db.py          conexión a Supabase para quien escribe (worker y cargadores)
  snapshot.py    panorama cacheado en Redis que sirve la API
  alerts.py      motor de umbrales (caudal de ANA; lluvia con la referencia de SENAMHI)
  ingesta/       ingesta horaria y tareas del worker: recolectar de las fuentes y guardar en la BD
  connectors/    un conector por fuente (solo librería estándar)
  data/          catálogo de coordenadas del pronóstico por localidad (revisado a mano)
  mapas/         cargador de mapas históricos FEN y semilla del catálogo de localidades
  prototipo/     prototipo sin dependencias (SQLite + http.server), congelado
  tests/         pruebas sin red: python -m unittest discover -s backend/tests -t .
"""
