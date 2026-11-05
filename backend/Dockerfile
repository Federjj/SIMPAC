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
# La API async por defecto; el worker sobreescribe el command en docker-compose (y el start command
# en Railway). Escucha en $PORT si la plataforma lo asigna (Railway lo inyecta y lo usa para el
# healthcheck y el dominio publico); sin esa variable, 8000 como siempre (docker compose). Forma shell
# para que la variable se expanda; exec deja a uvicorn como PID 1 (recibe SIGTERM al detener).
CMD ["/bin/sh", "-c", "exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
