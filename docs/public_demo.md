# Demo pública sin depender del PC

El repositorio incluye un `Dockerfile` que compila React y sirve el panel desde FastAPI en el mismo dominio HTTPS. Un solo servicio de Render ejecuta la API y su trabajador; PostgreSQL conserva conversaciones y trabajos fuera del contenedor. Telegram entrega mensajes al webhook público. La IA usa una API compatible con OpenAI, con una configuración de Groq en `render.yaml`.

## Estado

La configuración está preparada. La publicación solo queda verificada cuando existe una URL accesible y se comprueba un mensaje real de Telegram. No confundir una compilación local con un despliegue completado.

## Publicar

1. Crear un repositorio de GitHub y subir los archivos versionados. No subir `.env`, `.runtime`, `data`, `.venv` ni `node_modules`.
2. En Render, crear un Blueprint conectado al repositorio. Revisar que tanto el servicio como PostgreSQL usen el plan **Free**. No seleccionar ampliaciones de pago.
3. Configurar únicamente como secretos del servidor `TELEGRAM_BOT_TOKEN` y `LLM_API_KEY` (clave de Groq). Render genera `JWT_SECRET`, `TELEGRAM_WEBHOOK_SECRET` y las dos contraseñas de operadores. Ninguna clave se incorpora al frontend.
4. Esperar al despliegue. El arranque migra PostgreSQL, registra el webhook con una cabecera secreta sin descartar mensajes pendientes y levanta la API en el puerto asignado por Render.
5. Abrir la URL HTTPS. Ingresar con `operador@demo.local` y la contraseña generada en Render. El segundo operador usa `operador-b@demo.local` y su propia contraseña.
6. Escribir a `@EducationSalesUTA2026Bot`, comprobar que llega al panel y que la respuesta procede del modelo real. Tomar el control, responder como asesor y reanudar la IA. Revisar también el rechazo a un descuento no autorizado.

`AUTH_ADAPTER=demo` mantiene el inicio de sesión local con contraseñas privadas y JWT. Este despliegue usa `APP_ENV=public_demo`, no se presenta como una instalación de producción con Supabase Auth/RLS. No hay simulador de Telegram ni claves de ejemplo en el panel compilado para la nube. El catálogo continúa siendo ficticio y no procesa pagos.

## Límites del nivel gratuito

- Render puede suspender el servicio tras 15 minutos sin tráfico entrante; el siguiente acceso puede tardar aproximadamente un minuto. Abrir el panel antes de presentar y esperar a que esté listo.
- El PostgreSQL gratuito de Render caduca a los 30 días. Exportar los datos o migrarlos antes; esta configuración no promete almacenamiento gratuito permanente.
- Groq aplica cuotas de solicitudes y tokens. Una respuesta de cuota agotada no cambia a un simulador: el trabajo sigue la política de reintentos y errores del backend.
- El servicio no necesita el PC encendido. Si el alojamiento está suspendido, Telegram reintenta entregas, pero una suspensión prolongada puede superar la retención del proveedor.

Fuentes: [Render Free](https://render.com/docs/free), [Render Blueprint](https://render.com/docs/blueprint-spec), [compatibilidad de Groq](https://console.groq.com/docs/openai), [límites de Groq](https://console.groq.com/docs/rate-limits).

## Verificación antes de entregar

- `GET /health/live` y `/health/ready` responden correctamente desde internet.
- La página principal pide credenciales; `/api/me` rechaza accesos sin token.
- `getWebhookInfo` muestra la URL pública esperada, sin errores de entrega recientes.
- La conversación real demuestra catálogo, clasificación, handover y reanudación.
- Los cambios llegan a GitHub y sus verificaciones pasan.
- Guardar las URL finales y las evidencias de prueba en `docs/verification.md` después de comprobarlas.
