# 04 - Implementación de chatbot interactivo

Este paso construye sobre las herramientas de Google (Gmail, Calendar, Docs) del
paso anterior y convierte al agente en un chatbot interactivo: un loop en la
terminal que mantiene el historial de la conversación entre mensajes.

## Configuración de Google OAuth

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

Renombra el archivo descargado a `credentials.json` y colócalo en la raíz de este proyecto (`04-agente-impl-chatbot/credentials.json`).

Este archivo contiene un secreto y **no debe subirse al repositorio** (ya está incluido en `.gitignore`).

### 6. Generar el token de acceso

Ejecuta lo siguiente para iniciar el flujo de autenticación:

```bash
uv run python -c "
from personal_assistant_agent.tools import auth
creds = auth.get_credentials()
print('Authenticated. Token valid:', creds.valid)
"
```

Esto abrirá una ventana del navegador para iniciar sesión y aprobar los permisos solicitados. Al aprobar, se generará automáticamente el archivo `token.json` en la raíz del proyecto, el cual se reutiliza y refresca en las siguientes ejecuciones.

Este archivo tampoco debe subirse al repositorio (también está incluido en `.gitignore`).
