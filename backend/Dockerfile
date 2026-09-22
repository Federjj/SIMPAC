FROM python:3.12-slim
WORKDIR /app

# Dependencias primero (mejor caché de capas)
COPY backend/requirements.txt backend/requirements-mapas.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# geopandas (+GDAL) solo en la imagen del worker, que es donde corre el cargador de
# mapas FEN. La imagen de la API pública no lo necesita.
ARG INSTALAR_MAPAS=0
RUN if [ "$INSTALAR_MAPAS" = "1" ]; then pip install --no-cache-dir -r backend/requirements-mapas.txt; fi

COPY backend backend

EXPOSE 8000
# La API async por defecto; el worker sobreescribe el command en docker-compose.
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
