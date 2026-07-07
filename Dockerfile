# VittaLens — single-container image: FastAPI backend + static frontend.
#
# Build:  docker build -t vittalens .
# Run:    docker run -d --name vittalens -p 8030:8030 vittalens
# Then open http://<host>:8030
FROM python:3.12-slim

# Install dependencies first so this layer caches across code changes.
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Application code (frontend is served statically by FastAPI).
COPY backend/ backend/
COPY frontend/ frontend/

# Run as a non-root user; the app writes runtime data (cache, alert rules,
# dummy model outputs) under backend/data.
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8030

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8030/api/health', timeout=4)" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8030"]
