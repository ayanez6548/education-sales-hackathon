# Despliegue

## Variables

Copia `.env.example` a `.env` y `frontend/.env.example` a `frontend/.env`. El bundle web solo puede llevar `VITE_API_URL` y `VITE_DEMO_MODE`. Los secretos del bot, JWT, LLM y `service_role` de Supabase permanecen en el servidor.

## Base de datos

PostgreSQL 16 o Supabase. Desde `backend/`:

```text
alembic upgrade head
```

Crea un operador en `operator_profiles` con `auth_user_id` igual al `sub` de Supabase, `role` `operator` o `admin`, y `enabled=true`. Un JWT válido sin esa fila recibe 403.

## Bot de Telegram (pendiente de credenciales reales)

1. Crea el bot con BotFather y guarda el token **fuera** del git.
2. Publica la API por HTTPS.
3. Registra el webhook:

```text
https://api.telegram.org/bot<TOKEN>/setWebhook?url=<PUBLIC_API_URL>/webhooks/telegram&secret_token=<TELEGRAM_WEBHOOK_SECRET>
```

4. `TELEGRAM_ADAPTER=live`. Sin token el proceso no arranca en modo live.

## LLM

`LLM_ADAPTER=openai` con `LLM_API_KEY` y, si aplica, `LLM_BASE_URL`. Sin clave no hay degradación silenciosa a demo.

## Autenticación Supabase

`AUTH_ADAPTER=supabase` exige `SUPABASE_JWT_SECRET`, `SUPABASE_JWT_AUDIENCE` e `SUPABASE_JWT_ISSUER`. Se valida audiencia e issuer siempre. El rol efectivo sale de `operator_profiles`, no del claim `role=authenticated`.

## Contenedores

```text
docker compose up --build
```

Compose ejecuta primero el servicio `migrate`; inicia la API cuando las migraciones terminan y el trabajador cuando la API está saludable. En despliegues externos aplica las migraciones antes de recibir tráfico. La configuración de Compose de este repo usa adaptadores **demo** a propósito; cámbiala para un entorno de jurado.

## Verificación

- HTTPS en el webhook y el dashboard.
- `/health/live` y `/health/ready`.
- CORS limitado a orígenes reales.
- Operador sin perfil: no lee chats ni eventos.
- Eventos en vivo y reconexión del tablero.
- El trabajador está vivo (proceso aparte o `EMBED_WORKER`).

SQLite no replica el aislamiento de PostgreSQL: hay un escritor por archivo de base, no un lock por conversación.

## Lo no verificado en vivo

No se declara bot público, URL de producción ni integración Telegram/LLM/Supabase comprobada hasta ejecutar esos pasos con secretos reales. Este documento no inventa hosts.
