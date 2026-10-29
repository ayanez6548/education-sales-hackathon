# Verificación del proyecto

Fecha: 29 de octubre de 2026. Entorno: Windows, Python 3.14 y Node.js 24.

- Backend: 48 pruebas aprobadas con `python -m pytest backend/tests -q` (14,67 segundos). Incluyen configuración pública, protección de archivos estáticos, webhook y confirmación durable del cursor de Telegram.
- Frontend: `npm run typecheck` y `npm run build` aprobados. El Dockerfile configura la API en el mismo origen y oculta credenciales/simulador de la demo local.
- Docker Compose: `docker compose config --quiet` aprobado.
- Alembic: generación SQL para PostgreSQL de las tres migraciones aprobada, sin conexión a una base externa.
- Navegador: acceso con operador ficticio, conexión SSE autenticada, consulta de Python con falta ortográfica, toma de control y envío humano verificados.
- Regresiones: descarte de IA durante y después de transferencia, IDs de demo únicos, resultado incierto persistente y recuperación de trabajos verificados.
- Fechas: serialización UTC cubierta por prueba; presentación en America/Guayaquil.

## Alcance de esta entrega

La demo local utiliza adaptadores simulados identificados. El bot `@EducationSalesUTA2026Bot` fue creado y su identidad se comprobó con `getMe`. La prueba real de OpenAI fue rechazada por falta de saldo. No se declara una respuesta real de IA exitosa todavía. El catálogo es ficticio y no procesa pagos.

El despliegue público se preparó con Docker, Render y PostgreSQL en `render.yaml`; la IA se configura con el endpoint de Groq. Todavía no hay URL pública verificada ni conversación completa validada por Telegram. Se requiere completar la conexión de las cuentas. No se ejecutaron contenedores ni PostgreSQL real: Docker Desktop no tiene su motor en ejecución. Las instrucciones y límites están en public_demo.md.

La autenticación Supabase incluida espera JWT HS256 con audiencia e issuer configurados; proyectos con claves asimétricas requieren soporte JWKS antes de activarla.

## Comandos reproducibles

Desde backend/: `..\.venv\Scripts\python.exe -m pytest -q`.
Desde frontend/: `npm run build`.
Desde la raíz: `docker compose config --quiet`.
