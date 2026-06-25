# LogistAI runtime image. Runs fully offline (no AI SDK in the base install).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code.
COPY . .

# Persisted SQLite lives here (mounted volume in compose).
RUN mkdir -p /data
ENV DATABASE_URL=sqlite:////data/logistai.db

# Entrypoint applies migrations, then execs the given command.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "app.runner"]
