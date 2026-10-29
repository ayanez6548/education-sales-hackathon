# Verificación de la demo local

Fecha: 29 de octubre de 2026. Entorno: Windows, Python 3.14 y Node.js 24.

- Backend: 31 pruebas aprobadas con `python -m pytest -q` (22,15 segundos).
- Frontend: `npm run build` aprobado; incluye la comprobación de TypeScript.
- Docker Compose: `docker compose config --quiet` aprobado.
- Alembic: generación SQL para PostgreSQL de las tres migraciones aprobada, sin conexión a una base externa.
- Navegador: acceso con operador ficticio, conexión SSE autenticada, consulta de Python con falta ortográfica, toma de control y envío humano verificados.
- Regresiones: descarte de IA durante y después de transferencia, IDs de demo únicos, resultado incierto persistente y recuperación de trabajos verificados.
- Fechas: serialización UTC cubierta por prueba; presentación en America/Guayaquil.

## Alcance de esta entrega

Telegram y LLM utilizan adaptadores simulados identificados. El catálogo y los operadores son ficticios. La demo local no envía mensajes a servicios externos.

No se ejecutaron contenedores ni una base PostgreSQL real. No se validaron en vivo Telegram, un proveedor LLM, Supabase ni hosting público. Las instrucciones para configurarlos están en deployment.md.

La autenticación Supabase incluida espera JWT HS256 con audiencia e issuer configurados; proyectos con claves asimétricas requieren soporte JWKS antes de activarla.

## Comandos reproducibles

Desde backend/: `..\.venv\Scripts\python.exe -m pytest -q`.
Desde frontend/: `npm run build`.
Desde la raíz: `docker compose config --quiet`.
