FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_URL="" VITE_DEMO_MODE=false
RUN npm run typecheck && npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend STATIC_DIRECTORY=/app/frontend/dist
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser backend/ ./backend/
COPY --from=frontend --chown=appuser:appuser /build/dist/ ./frontend/dist/
USER appuser
EXPOSE 10000
CMD ["python", "-m", "app.cloud"]
