# Matriz de rúbrica

Evidencia de implementación. Lo no ejecutado en un entorno real se marca como pendiente.

| Criterio | Dónde está | Evidencia local | Pendiente en vivo |
| --- | --- | --- | --- |
| Bot Telegram y conversación natural | `inbox`, adaptadores Telegram, catálogo, `DemoLLMAdapter` | Flujo demo inbound + pruebas de consulta/objeción | Webhook HTTPS con token real |
| Dashboard autenticado y en vivo | `frontend/`, `/api/auth/login`, `/api/events` | UI en español, SSE mediante fetch autenticado | Hosting público y Auth Supabase |
| Repositorio y despliegue | README, `docs/deployment.md`, Dockerfiles, `.env.example`, Alembic | Archivos en este repo | Cuentas y URLs reales |
| Clasificación / termómetro | `domain/states.py`, dashboard badges con texto | Labels Interesado/Dudoso/Frustrado/Lead caliente | — |
| Handover seguro | `services/control.py`, puertas en `outbound_messages` | Pruebas de takeover y 409 entre operadores | Carga con dos asesores reales |
| Seguridad comercial | `domain/validation.py`, `adapters/llm.py` | Precios del curso seleccionado; historial no-system | Red team con modelo vivo |
| Métricas y resumen | `services/metrics.py`, perfil del tablero | Definiciones visibles en el footer | Medición de latencia en hosting |
| Resiliencia | cola `processing_jobs`, estados de entrega | Pruebas de lease y descarte | Caída real del worker en prod |
| Accesibilidad | etiquetas, no solo color, `aria` | Tablero con texto de estado | Auditoría con lector de pantalla |

Puntos del organizador (100): este archivo relaciona cada bloque con código y con lo que aún exige infraestructura externa.
