# Hackathon: ventas educativas por Telegram

Sistema independiente para un centro de capacitación ficticio. Un bot de Telegram atiende prospectos en español, un backend FastAPI orquesta reglas comerciales y un dashboard React permite a un asesor tomar el control.

Este repositorio no depende de otros proyectos. El código vive en `backend/`, `frontend/` y `docs/`.

## Qué está implementado

- Webhook de Telegram y canal **simulado** etiquetado para demo local sin credenciales.
- Orquestación LLM configurable (`LLM_ADAPTER=demo|openai`). El adaptador demo está claramente marcado como simulado.
- Clasificación comercial, catálogo ficticio, objeciones, solicitud de inscripción (no es matrícula pagada).
- Máquina de atención (`ai_active`, `human_pending`, `human_active`, `closed`) con `control_version`, handover y exclusión entre operadores.
- Dashboard en español: lista, historial, perfil, métricas y eventos en vivo.
- Autenticación demo (JWT local) y ruta de integración Supabase (audiencia e issuer obligatorios).
- Cola de trabajos en base de datos y trabajador (empotrado en demo o proceso aparte).

## Demo pública sin depender del PC

El despliegue está definido en `render.yaml` y el `Dockerfile` de la raíz: panel y API en un servicio HTTPS, PostgreSQL y Telegram real, con IA compatible con OpenAI configurada para Groq. Las claves se guardan como secretos de Render. Consulta [la guía de demo pública](docs/public_demo.md) para los pasos, las verificaciones y los límites del plan gratuito. La configuración preparada no significa que la demo ya esté publicada.

## Demo local sin Docker ni credenciales

Ejecuta los pasos desde la raíz de esta carpeta. Usa una terminal separada para cada servidor.

1. Crea el entorno (ya puedes usar el `.venv` de la raíz):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm --prefix frontend ci
```

2. Arranca la API (SQLite + adaptadores simulados):

```powershell
.\scripts\start-demo.ps1
```

3. En otra terminal:

```powershell
cd frontend
npm run dev
```

4. Abre `http://localhost:5173`. Entra con `operador@demo.local` / `demo-operador`. Usa **Simular mensaje entrante**.

La demo local **no sustituye** un bot y un dashboard desplegados para el jurado.

## Límites de SQLite frente a PostgreSQL

SQLite sirve para desarrollar y para pruebas automatizadas sin motor Docker:

- No hay `FOR UPDATE SKIP LOCKED` real; la exclusión entre workers es más débil.
- El bloqueo de escritura es de toda la base, no por fila. Un escritor a la vez.
- No hay Row Level Security ni Realtime de Supabase.
- Tipos JSON y UUID son de compatibilidad, no el dialecto de producción.

Para la demo del jurado y producción usa PostgreSQL (Compose o Supabase) y `alembic upgrade head`.

## Producción: fallo cerrado

Si `APP_ENV=production`, `DEMO_MODE` debe ser `false` y los adaptadores no pueden ser `demo`. Faltar `TELEGRAM_BOT_TOKEN`, `LLM_API_KEY` o secretos de Supabase **no** activa la simulación: el proceso termina con error.

## Comandos

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest

# Desde la raíz del repositorio
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Documentación: [arquitectura](docs/architecture.md), [despliegue](docs/deployment.md), [guion de demo](docs/demo_script.md), [defensa](docs/defense.md), [rúbrica](docs/rubric_mapping.md).

## Repositorio publicado

Código: [ayanez6548/education-sales-hackathon](https://github.com/ayanez6548/education-sales-hackathon).

```powershell
git clone https://github.com/ayanez6548/education-sales-hackathon.git
cd education-sales-hackathon
```

La carpeta contiene un repositorio Git independiente. `.env`, `.runtime`, `.venv`, `node_modules`, bases de datos y compilaciones quedan excluidos. Las verificaciones del backend y frontend se ejecutan también en GitHub Actions. Para actualizar una copia existente después de revisar tus cambios, usa `git pull`.
