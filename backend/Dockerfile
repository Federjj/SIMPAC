FROM python:3.12-slim
WORKDIR /app

# Dependencias primero (mejor caché de capas)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend

EXPOSE 8000
# La API async por defecto; el worker sobreescribe el command en docker-compose.
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
