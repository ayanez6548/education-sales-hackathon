# Arquitectura

## Capas

1. **Canal.** Telegram Bot API (webhook HTTPS) o `DemoTelegramAdapter` (simulado, etiquetado). Los `message_id` de Telegram solo son únicos por chat; la restricción es `(telegram_chat_id, telegram_message_id)`.
2. **API FastAPI.** Autoridad de reglas, autenticación, persistencia inmediata del update y encolado de trabajo. El webhook responde tras persistir, no tras la inferencia.
3. **Trabajador.** Toma `processing_jobs` y `outbound_messages` con reserva. Antes de enviar adquiere el mismo bloqueo de conversación que takeover/resume y revalida `control_version`, modo y turno.
4. **Dashboard React/TypeScript.** Autenticación de operadores, lista, chat, perfil, métricas y SSE mediante fetch autenticado.
5. **PostgreSQL.** Fuente de verdad. Supabase puede alojar la base, Auth y Realtime. SQLite es solo atajo local: el bloqueo de escritor aplica a toda la base, no a una fila.

## Agentes lógicos (un solo backend)

- Clasificación: intención, termómetro y necesidad de humano.
- Comercial: respuesta con catálogo, perfil e historial acotado.
- Resumen: contexto breve al transferir o con historial largo.

No hace falta una llamada al modelo por agente. La salida se valida en servidor. Precios solo del **curso seleccionado**, nunca de otro ítem del catálogo.

El historial del prospecto se envía al modelo como datos no confiables en el rol `user`, nunca como `system`.

## Estados de atención

`ai_active` → `human_pending` (persona o frustración) → `human_active` (tomar control). Reanudar IA y cerrar son acciones explícitas. Un chat cerrado que recibe un mensaje reabre en `human_pending`. `control_version` sube en cada transferencia. Un operador no reanuda, cierra ni envía un chat ya asignado a otro.

## Datos principales

`operator_profiles`, `contacts`, `courses`, `conversations`, `messages`, `lead_profiles`, `enrollment_requests`, `processing_jobs`, `outbound_messages` (con puertas de envío persistidas), `audit_events`, `app_events`, `telegram_updates`, `idempotency_keys`.

## Eventos

La API emite `app_events` y el dashboard se suscribe a `/api/events` con `Authorization` (fetch SSE, cursor `after_id` y reconexión). El token no viaja en la URL. En producción se puede complementar con Realtime de Supabase bajo las mismas políticas de operador habilitado.
