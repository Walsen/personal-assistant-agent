# 06 - Despliegue en Amazon Bedrock AgentCore

Este paso final toma el agente construido en los pasos anteriores (Gmail,
Calendar, Docs, skills, steering, interrupts, session manager, logging) y lo
expone como un servicio HTTP desplegable en **Amazon Bedrock AgentCore
Runtime**, usando el SDK `bedrock-agentcore` y el CLI
`bedrock-agentcore-starter-toolkit`.

## Qué cambió respecto al CLI interactivo

AgentCore Runtime ejecuta el agente como un servicio HTTP sin estado (cada
invocación es una petición independiente), en un contenedor efímero. Esto
requiere tres adaptaciones respecto al chatbot de terminal de los pasos
anteriores:

1. **`main.py`** — un entrypoint HTTP (`BedrockAgentCoreApp`) que envuelve al
   agente existente. Expone `/invocations` (POST) y `/ping` (GET), los
   endpoints que AgentCore Runtime requiere.
2. **Sesiones en S3, no en disco local.** `agent.py` ahora elige entre
   `FileSessionManager` (desarrollo local, como antes) y `S3SessionManager`
   según la variable de entorno `AGENT_SESSIONS_BUCKET` — el disco local de
   un contenedor de AgentCore no es duradero.
3. **Confirmaciones (`delete_email`) sobre HTTP, no por `input()`.** Como no
   hay terminal adjunta a una petición HTTP, un `Interrupt` pendiente se
   devuelve directamente en la respuesta JSON en lugar de bloquear
   esperando entrada. El llamador reanuda con una segunda petición que
   incluye `interrupt_responses`. Ver la sección "Formato de peticiones y
   respuestas" más abajo.

Adicionalmente, `tools/auth.py` ahora soporta leer/guardar el token OAuth
desde **AWS Secrets Manager** (variable `GOOGLE_TOKEN_SECRET_ID`) en lugar
de `token.json` en disco, ya que el flujo de consentimiento por navegador no
puede ejecutarse dentro de un contenedor sin interfaz gráfica.

## Formato de peticiones y respuestas de `/invocations`

**Petición normal:**
```json
{"prompt": "¿Qué tengo en mi calendario esta semana?"}
```

**Respuesta normal:**
```json
{"status": "completed", "message": { "role": "assistant", "content": [...] }}
```

**Respuesta cuando el agente necesita confirmación** (por ejemplo,
`delete_email`):
```json
{
  "status": "interrupt",
  "interrupts": [
    {"id": "...", "name": "gmail-delete-approval", "reason": {"message_id": "...", "subject": "...", "sender": "..."}}
  ]
}
```

**Petición para resolver la confirmación pendiente:**
```json
{
  "interrupt_responses": [
    {"interrupt_id": "<el id recibido arriba>", "response": "y"}
  ]
}
```

## Configuración de Google OAuth (igual que en pasos anteriores)

### 1. Crear un proyecto en Google Cloud

Ve a [console.cloud.google.com](https://console.cloud.google.com/) y crea un proyecto nuevo (o usa uno existente).

### 2. Habilitar las APIs necesarias

En la [consola de Google Cloud](https://console.cloud.google.com/), asegúrate de tener seleccionado el proyecto que creaste en el paso 1 (selector de proyecto en la barra superior).

Luego ve al menú de navegación (ícono ☰ en la esquina superior izquierda) → **APIs & Services → Library** (o busca "API Library" en la barra de búsqueda superior).

Ahí, busca y habilita cada una de estas APIs (haz clic en cada resultado y luego en el botón **Enable**):

- **Gmail API** — busca "Gmail API" o ve directo al [enlace de la API](https://console.cloud.google.com/apis/library/gmail.googleapis.com)
- **Google Calendar API** — busca "Google Calendar API" o ve directo al [enlace de la API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)
- **Google Docs API** — busca "Google Docs API" o ve directo al [enlace de la API](https://console.cloud.google.com/apis/library/docs.googleapis.com)
- **Google Drive API** (necesaria para buscar documentos por nombre) — busca "Google Drive API" o ve directo al [enlace de la API](https://console.cloud.google.com/apis/library/drive.googleapis.com)

> Nota: si usas los enlaces directos, verifica en la parte superior de la página que el proyecto seleccionado sea el correcto antes de hacer clic en **Enable**.

Puedes confirmar que quedaron habilitadas en **APIs & Services → Enabled APIs & services**, donde deberías ver las tres APIs listadas.

### 3. Configurar la pantalla de consentimiento OAuth

- Ve a **APIs & Services → OAuth consent screen**
- Elige **External** (o **Internal** si tienes una organización de Google Workspace)
- Completa el nombre de la app y el correo de soporte
- Ve al menú **Audience** (dentro de la sección OAuth consent screen) y, en la parte de **Test users**, agrega tu propia cuenta de Google (requerido mientras la app esté en estado "Testing")

### 4. Crear las credenciales OAuth

- Ve al menú **Clients** (dentro de **Google Auth Platform**, en la barra lateral izquierda)
- Haz clic en **Create OAuth client**
- Tipo de aplicación: **Desktop app**
- Descarga el archivo JSON generado

### 5. Colocar el archivo de credenciales

Renombra el archivo descargado a `credentials.json` y colócalo en la raíz de este proyecto (`06-agente-AgentCore-deploy/credentials.json`).

Este archivo contiene un secreto y **no debe subirse al repositorio** (ya está incluido en `.gitignore`).

### 6. Generar el token de acceso (localmente, una sola vez)

Ejecuta lo siguiente para iniciar el flujo de autenticación:

```bash
uv run python -c "
from personal_assistant_agent.tools import auth
creds = auth.get_credentials()
print('Authenticated. Token valid:', creds.valid)
"
```

Esto abrirá una ventana del navegador para iniciar sesión y aprobar los permisos solicitados. Al aprobar, se generará automáticamente el archivo `token.json` en la raíz del proyecto.

Este archivo tampoco debe subirse al repositorio (también está incluido en `.gitignore`).

## Probar el entrypoint localmente (antes de desplegar)

```bash
uv run python main.py
```

En otra terminal:
```bash
curl http://localhost:8080/ping

curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: local-test-session-1" \
  -d '{"prompt": "Hola, ¿qué puedes hacer?"}'
```

## Preparar el token para despliegue (AWS Secrets Manager)

Antes de desplegar, sube el contenido de tu `token.json` local a un secreto
de Secrets Manager (el contenedor desplegado no puede abrir un navegador
para autenticarse):

```bash
aws secretsmanager create-secret \
  --name personal-assistant-google-token \
  --secret-string file://token.json
```

Anota el ARN o nombre del secreto — se usará como valor de
`GOOGLE_TOKEN_SECRET_ID` al configurar el despliegue.

## Desplegar a AgentCore Runtime

> ⚠️ Estos pasos crean recursos reales y facturables en tu cuenta de AWS
> (rol de IAM, bucket S3, AgentCore Runtime). Revisa cada paso antes de
> ejecutarlo.

```bash
# 1. Configurar el proyecto (genera .bedrock_agentcore.yaml)
uv run agentcore configure -e main.py

# 2. Desplegar (usa AWS CodeBuild, sin necesidad de Docker local)
uv run agentcore deploy

# 3. Verificar estado
uv run agentcore status

# 4. Invocar el agente ya desplegado
uv run agentcore invoke '{"prompt": "Hola"}'
```

Variables de entorno a configurar en el despliegue (ver
`.bedrock_agentcore.yaml` generado por `agentcore configure`, o la consola
de AgentCore Runtime):

- `AGENT_SESSIONS_BUCKET` — bucket S3 para persistencia de sesiones.
- `GOOGLE_TOKEN_SECRET_ID` — ARN/nombre del secreto de Secrets Manager con el token OAuth.

## Limpieza

Para eliminar los recursos desplegados:

```bash
uv run agentcore destroy
```
