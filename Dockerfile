FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/__init__.py ./app/
COPY app/core ./app/core
COPY app/speech ./app/speech
ENV SPEECH_MODEL_PATH=/opt/models/vosk-model-small-ru-0.22
RUN python -m app.speech.prepare

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY data ./data
COPY --from=frontend /app/static/ui ./app/static/ui

RUN useradd --create-home app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
