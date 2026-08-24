# Adaptación a Amazon Bedrock AgentCore y guía de despliegue

Este documento detalla, en dos partes:

1. **Qué se tuvo que cambiar** en el agente construido en los pasos 01-05
   (chatbot de terminal) para que sea desplegable como servicio en Amazon
   Bedrock AgentCore Runtime, incluyendo las librerías nuevas agregadas.
2. **Los comandos exactos** para configurar y desplegar el agente en AWS
   usando el **AgentCore CLI** (`@aws/agentcore`) — la herramienta que AWS
   recomienda actualmente.

> **Nota sobre el CLI usado.** Inicialmente se documentó este flujo con el
> paquete Python `bedrock-agentcore-starter-toolkit` (comando `agentcore`
> instalado vía `pip`/`uv`). AWS marcó ese toolkit como no soportado en
> favor de un nuevo CLI basado en Node.js, `@aws/agentcore`. Este documento
> ya usa directamente el CLI recomendado — no queda ningún paso pendiente
> de migración.

## Parte 1: Cambios de adaptación

### Por qué se necesitó adaptar el código

AgentCore Runtime ejecuta el agente como un **servicio HTTP sin estado**,
dentro de un **contenedor efímero** que AWS puede reemplazar en cualquier
momento. El chatbot construido en los pasos anteriores asumía cosas que
dejan de ser ciertas en ese entorno:

| Suposición del chatbot de terminal | Realidad en AgentCore Runtime |
|---|---|
| Hay un proceso de larga duración con memoria en RAM | Cada invocación es una petición HTTP independiente |
| Hay una terminal donde se puede llamar `input()` para pedir confirmación | No hay terminal adjunta a una petición HTTP |
| Se puede abrir un navegador para el consentimiento OAuth de Google | El contenedor no tiene interfaz gráfica ni navegador |
| El disco local (`.sessions/`, `token.json`) persiste entre ejecuciones | El disco del contenedor es efímero, puede desaparecer en cualquier redeploy/reinicio |

A continuación, el detalle de cada cambio.

### 1. Estructura de proyecto según el AgentCore CLI

El AgentCore CLI espera una estructura de proyecto específica, distinta de
la de los pasos 01-05:

```
06-agente-AgentCore-deploy/
├── agentcore/
│   ├── agentcore.json       # Configuración del proyecto (runtimes, memorias, credenciales...)
│   ├── aws-targets.json     # Cuenta/región de despliegue
│   ├── .env.local           # Secretos locales (gitignored)
│   ├── .llm-context/        # Definiciones de tipos para asistentes de IA
│   └── cdk/                 # Infraestructura CDK generada por el CLI (TypeScript)
├── app/
│   └── personal_assistant_agent/    # Código real del agente (empaquetado/desplegado)
│       ├── main.py                  # Entrypoint HTTP (BedrockAgentCoreApp)
│       ├── personal_assistant_agent/  # El paquete del agente (tools, skills, steering, etc.)
│       ├── skills/
│       └── pyproject.toml
├── agentcore-cli-tools/      # Instalación local (no global) del CLI @aws/agentcore
├── infra/                    # Stack de CDK en Python para los prerrequisitos (bucket S3, secreto)
└── src/personal_assistant_agent/   # Copia usada por el chatbot de terminal (pasos 04-05, sin cambios)
```

El código real del agente (`app/personal_assistant_agent/personal_assistant_agent/`)
es una copia exacta del paquete usado en los pasos anteriores — **no se
modificó ninguna herramienta, skill, ni la lógica de steering/interrupts**.
Lo único nuevo en esta ubicación es `main.py` (ver punto 2).

### 2. Nuevo entrypoint HTTP: `app/personal_assistant_agent/main.py`

Envuelve al agente existente (`personal_assistant_agent/agent.py`, sin
modificar su lógica de negocio) usando `bedrock_agentcore.runtime.BedrockAgentCoreApp`:

```python
from bedrock_agentcore import BedrockAgentCoreApp
from personal_assistant_agent.agent import build_agent

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload: dict, context) -> dict:
    session_id = context.session_id or "default"
    agent = build_agent(session_id)
    ...
```

Este decorador expone automáticamente los dos endpoints que AgentCore
Runtime exige:
- `POST /invocations` — recibe el payload y devuelve la respuesta del agente
- `GET /ping` — health check

`agentcore.json` referencia este archivo mediante
`"entrypoint": "main.py"` y `"codeLocation": "app/personal_assistant_agent/"`.

### 3. Sesiones por invocación y sin estado local: `agent.py`

**Antes:** un único objeto `agent` global, con un `FileSessionManager` fijo
apuntando a `.sessions/` en disco, usado por todas las llamadas del CLI.

**Ahora:** una función `build_agent(session_id)` que construye un `Agent`
nuevo por invocación, ligado al `session_id` del llamador (obtenido de
`context.session_id` en `main.py`). Esto evita que las conversaciones o
confirmaciones pendientes de un usuario se mezclen con las de otro si llegan
peticiones concurrentes.

Además, el `session_manager` interno se elige dinámicamente:

```python
def _build_session_manager(session_id: str):
    if SESSIONS_BUCKET:  # AGENT_SESSIONS_BUCKET configurado
        from strands.session.s3_session_manager import S3SessionManager
        return S3SessionManager(session_id=session_id, bucket=SESSIONS_BUCKET, prefix=SESSIONS_S3_PREFIX)

    return FileSessionManager(session_id=session_id, storage_dir=str(SESSIONS_DIR))
```

- **Localmente** (sin `AGENT_SESSIONS_BUCKET`): sigue usando `FileSessionManager`
  en `.sessions/`, exactamente como en el paso 05.
- **Desplegado** (con `AGENT_SESSIONS_BUCKET` configurado como variable de
  entorno del runtime en `agentcore.json`): usa `S3SessionManager`, ya que
  el disco del contenedor no es duradero.

### 4. Confirmaciones (`delete_email`) sobre HTTP en vez de `input()`

**Antes:** el loop del CLI (`_resolve_interrupts` en `agent.py`) llamaba a
`input()` directamente en la terminal para pedir confirmación al usuario
cuando `delete_email` disparaba un `Interrupt`.

**Ahora:** `main.py` verifica `result.stop_reason == "interrupt"` después de
invocar al agente. Si hay un interrupt pendiente, lo devuelve directamente
en el cuerpo de la respuesta HTTP en vez de bloquear:

```python
if result.stop_reason == "interrupt":
    return {
        "status": "interrupt",
        "interrupts": [{"id": i.id, "name": i.name, "reason": i.reason} for i in result.interrupts],
    }
```

El llamador debe entonces enviar una **segunda petición** con
`interrupt_responses` para resolverlo. El `session_manager` (S3 o disco,
según el entorno) es lo que permite que el interrupt pendiente "sobreviva"
entre esas dos peticiones HTTP independientes.

Esto se verificó de extremo a extremo contra la API real de Gmail, incluso
después de migrar al layout del nuevo CLI: se envió un correo de prueba, se
pidió su eliminación vía `/invocations` (la respuesta contuvo el interrupt
pendiente sin ejecutar nada), y una segunda petición con `"response": "y"`
sí ejecutó la eliminación real (confirmado por la etiqueta `TRASH` en el
mensaje).

### 5. Autenticación de Google sin navegador: `tools/auth.py`

**Antes:** `get_credentials()` siempre leía/escribía `token.json` en disco,
y si no existía o estaba vencido sin refresh token, abría un navegador con
`InstalledAppFlow.run_local_server()`.

**Ahora:** se agregó una variable de entorno `GOOGLE_TOKEN_SECRET_ID`. Si
está configurada, el token se lee/escribe desde un secreto de **AWS Secrets
Manager** en lugar de `token.json`, y el flujo de navegador **nunca** se
intenta en ese modo — si el secreto no tiene un token válido, se lanza un
`AuthenticationError` explícito indicando que hay que reprovisionar el
token localmente y volver a subirlo.

```python
GOOGLE_TOKEN_SECRET_ID = os.environ.get("GOOGLE_TOKEN_SECRET_ID")

def _load_stored_token() -> str | None:
    if GOOGLE_TOKEN_SECRET_ID:
        return _load_token_from_secrets_manager()
    if os.path.exists("token.json"):
        ...
```

### Librerías nuevas agregadas

| Paquete | Dónde | Por qué se agregó |
|---|---|---|
| `bedrock-agentcore` | `pyproject.toml` (raíz y `app/personal_assistant_agent/`) | SDK en tiempo de ejecución. Provee `BedrockAgentCoreApp` (usada en `main.py`). |
| `boto3` | `pyproject.toml` (raíz y `app/personal_assistant_agent/`) | Cliente de AWS. Usado directamente para leer/escribir el token de Google en Secrets Manager (`tools/auth.py`), y de forma indirecta por `S3SessionManager` de Strands. |
| `@aws/agentcore` (CLI) | `agentcore-cli-tools/package.json` | El CLI recomendado por AWS (`agentcore configure/deploy/invoke/...`). Instalado como dependencia de proyecto (no global), ya que instalar paquetes npm globales falló en este entorno (nix store de solo lectura). |
| `aws-cdk-lib` / `constructs` | `infra/pyproject.toml` | Librerías de CDK en Python. Usadas por el stack `infra/stacks/prerequisites_stack.py`, que provisiona el bucket S3 de sesiones y el secreto de Secrets Manager de forma reproducible y reversible — **separado** del CDK que el AgentCore CLI genera para el runtime en sí (`agentcore/cdk/`, en TypeScript). |
| `aws-cdk` (CLI) | `infra/package.json` | El comando `cdk` para el stack de prerrequisitos. |

Nota: `bedrock-agentcore-starter-toolkit` (el toolkit Python deprecado) **no**
se usa en este proyecto.

### Lo que **no** cambió

La lógica de negocio del agente (herramientas de Gmail/Calendar/Docs,
skills, steering, la definición de `delete_email` con su `Interrupt`,
logging y manejo de errores de los pasos anteriores) permanece intacta. La
adaptación fue exclusivamente en la capa de "cómo se invoca, empaqueta y
persiste el agente", no en su comportamiento — verificado repitiendo las
mismas pruebas end-to-end contra la API real de Gmail antes y después de la
migración al layout del nuevo CLI.

---

## Parte 2: Comandos para desplegar en AgentCore Runtime

> ⚠️ Los siguientes comandos crean y destruyen **recursos reales y
> facturables** en tu cuenta de AWS (rol de IAM, bucket S3, AgentCore
> Runtime). Revisa cada paso antes de ejecutarlo.

> A lo largo de esta parte se usan **tres directorios de trabajo
> distintos**:
> - `06-agente-AgentCore-deploy/` (**raíz del proyecto**) — aquí se ejecuta
>   el CLI de AgentCore (`agentcore deploy`/`status`/`invoke`/`logs`/...).
>   El CLI opera sobre `agentcore/agentcore.json` **relativo al directorio
>   actual**, así que estos comandos deben correrse desde la raíz, no desde
>   `agentcore-cli-tools/`. Aquí también subes el token a Secrets Manager.
> - `06-agente-AgentCore-deploy/infra/` — para el stack de CDK en Python
>   que provisiona los prerrequisitos (bucket S3 de sesiones, secreto).
> - `06-agente-AgentCore-deploy/app/personal_assistant_agent/` — el código
>   real del agente que se prueba localmente antes de desplegar.
>
> Cada bloque de comandos indica explícitamente en qué directorio ejecutarlo.

### Paso 0: Requisitos previos

- Credenciales de AWS configuradas (`aws sts get-caller-identity` debe funcionar).
- Acceso al modelo Claude habilitado en Amazon Bedrock, en la región de despliegue.
- Node.js 20+ (para el CLI de AgentCore y CDK).
- Un `token.json` local válido (generado con el flujo de OAuth de los pasos anteriores).

### Paso 1: Instalar el AgentCore CLI (local al proyecto)

📁 Directorio: `06-agente-AgentCore-deploy/agentcore-cli-tools/`

```bash
cd agentcore-cli-tools
npm install
```

Esto instala `@aws/agentcore` como dependencia de proyecto (no global). El
binario queda en `./node_modules/.bin/agentcore`. Como los comandos deben
correrse desde la raíz del proyecto (ver nota arriba), lo más práctico es
invocarlo con una ruta relativa desde ahí, por ejemplo:
```bash
cd ..   # volver a la raíz
./agentcore-cli-tools/node_modules/.bin/agentcore --version
```

O agregar un alias en tu shell:
```bash
alias agentcore="$(pwd)/agentcore-cli-tools/node_modules/.bin/agentcore"
```

### Paso 2: Instalar dependencias del agente y probar el entrypoint localmente

📁 Directorio: `06-agente-AgentCore-deploy/app/personal_assistant_agent/`

```bash
cd app/personal_assistant_agent
uv venv --python 3.12
uv sync --python .venv/bin/python
```

Copia tus credenciales de Google locales (usadas solo para pruebas locales;
en el despliegue real se usa Secrets Manager, ver Paso 5):
```bash
cp ../../credentials.json ../../token.json .
```

Prueba el servidor local:
```bash
./.venv/bin/python main.py
```

En otra terminal (mismo directorio):
```bash
curl http://localhost:8080/ping

curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: local-test-session-1" \
  -d '{"prompt": "Hola, ¿qué puedes hacer?"}'
```

### Paso 3: Provisionar los prerrequisitos con CDK (`infra/`)

> Nota: este stack de CDK (en Python, distinto del CDK en TypeScript que el
> AgentCore CLI genera para el runtime en `agentcore/cdk/`) crea el
> **bucket de sesiones** y el **secreto de Secrets Manager** (vacío, como
> placeholder).

📁 Directorio: `06-agente-AgentCore-deploy/infra/`

> ⚠️ Ambos comandos (`npm install`, `npx cdk ...`) deben ejecutarse **desde
> dentro de `infra/`** — ahí es donde viven `package.json` y `cdk.json`. Si
> los corres desde la raíz del proyecto (`06-agente-AgentCore-deploy/`),
> `npm install` fallará con `ENOENT ... package.json` y `npx cdk` intentará
> descargar una versión nueva de `cdk` en lugar de usar la instalada
> localmente, y fallará con `--app is required`.

```bash
cd infra   # ruta absoluta o relativa a donde estés; asegúrate de terminar dentro de infra/
uv sync                  # instala aws-cdk-lib y constructs
npm install               # instala el CLI de cdk (a nivel de proyecto, no global)

# Vista previa de los recursos a crear (no crea nada, solo diff de solo lectura)
npx cdk diff

# Crear los recursos reales en AWS
npx cdk deploy
```

Al finalizar, `cdk deploy` imprime tres outputs:
- `AgentSessionsBucketName` — el nombre del bucket, para usarlo como `AGENT_SESSIONS_BUCKET`.
- `GoogleTokenSecretArn` / `GoogleTokenSecretName` — el ARN/nombre del secreto, para usarlo como `GOOGLE_TOKEN_SECRET_ID`.

### Paso 4: Subir el token real de Google al secreto

El secreto se crea **vacío** (con un valor placeholder) — CDK no puede
ejecutar el flujo de consentimiento OAuth por ti.

📁 Directorio: `06-agente-AgentCore-deploy/` (raíz del proyecto, donde vive tu `token.json` local)

```bash
cd ..                    # volver a la raíz del proyecto si venías de infra/
aws secretsmanager put-secret-value \
  --secret-id <GoogleTokenSecretArn-o-Name-del-output-anterior> \
  --secret-string file://token.json \
  --region us-east-1
```

### Paso 5: Configurar el target de despliegue (cuenta/región) y las variables de entorno

El AgentCore CLI **no tiene un comando `configure`** — la cuenta y región
de destino se definen editando directamente `agentcore/aws-targets.json`
(un arreglo de targets con `name`, `account`, `region`):

📁 Archivo: `06-agente-AgentCore-deploy/agentcore/aws-targets.json`

```json
[
  {
    "name": "default",
    "account": "<tu-account-id-de-12-dígitos>",
    "region": "us-east-1"
  }
]
```

Obtén tu account ID con `aws sts get-caller-identity`.

Después, edita `agentcore/agentcore.json` y agrega `envVars` al runtime
`personal_assistant_agent` con los valores obtenidos en el Paso 3:

📁 Archivo: `06-agente-AgentCore-deploy/agentcore/agentcore.json`

```json
{
  "runtimes": [
    {
      "name": "personal_assistant_agent",
      "build": "CodeZip",
      "entrypoint": "main.py",
      "codeLocation": "app/personal_assistant_agent/",
      "runtimeVersion": "PYTHON_3_14",
      "networkMode": "PUBLIC",
      "protocol": "HTTP",
      "envVars": [
        { "name": "AGENT_SESSIONS_BUCKET", "value": "<nombre-del-bucket-del-Paso-3>" },
        { "name": "GOOGLE_TOKEN_SECRET_ID", "value": "<ARN-o-nombre-del-secreto-del-Paso-3>" }
      ]
    }
  ]
}
```

Valida ambos archivos:

📁 Directorio: `06-agente-AgentCore-deploy/` (raíz del proyecto)

```bash
./agentcore-cli-tools/node_modules/.bin/agentcore validate
```

### Paso 6: Desplegar

📁 Directorio: `06-agente-AgentCore-deploy/` (raíz del proyecto — el CLI opera sobre `agentcore/` relativo al directorio actual)

```bash
./agentcore-cli-tools/node_modules/.bin/agentcore deploy --target default --yes
```

Esto sintetiza y aplica el CDK generado en `agentcore/cdk/`, empaqueta el
código (`CodeZip`, sin necesidad de Docker), crea el rol de IAM necesario, y
crea el recurso de AgentCore Runtime.

Para revisar los cambios antes de aplicarlos:
```bash
./agentcore-cli-tools/node_modules/.bin/agentcore deploy --target default --dry-run
# o, para ver el diff de CloudFormation:
./agentcore-cli-tools/node_modules/.bin/agentcore deploy --target default --diff
```

### Paso 7: Verificar el estado del despliegue

📁 Directorio: `06-agente-AgentCore-deploy/` (raíz del proyecto)

```bash
./agentcore-cli-tools/node_modules/.bin/agentcore status
```

### Paso 8: Probar el agente desplegado

📁 Directorio: `06-agente-AgentCore-deploy/` (raíz del proyecto)

```bash
./agentcore-cli-tools/node_modules/.bin/agentcore invoke "Hola"
```

Para probar el flujo de confirmación de `delete_email` sobre el agente ya
desplegado, primero invoca con un prompt que dispare `delete_email` (la
respuesta contendrá `"status": "interrupt"` con un `id`), y luego invoca de
nuevo pasando el JSON de `interrupt_responses` como prompt:
```bash
./agentcore-cli-tools/node_modules/.bin/agentcore invoke '{"interrupt_responses": [{"interrupt_id": "<el id recibido>", "response": "y"}]}'
```

### Paso 9: Revisar logs y trazas

📁 Directorio: `06-agente-AgentCore-deploy/` (raíz del proyecto)

```bash
./agentcore-cli-tools/node_modules/.bin/agentcore logs
./agentcore-cli-tools/node_modules/.bin/agentcore traces
```

O directamente en CloudWatch: **Log groups → `/aws/bedrock-agentcore/runtimes/{agent-id}-DEFAULT`**.

### Paso 10 (limpieza): eliminar los recursos desplegados

📁 Directorio: `06-agente-AgentCore-deploy/` (raíz del proyecto)

```bash
./agentcore-cli-tools/node_modules/.bin/agentcore remove agent --name personal_assistant_agent --yes
./agentcore-cli-tools/node_modules/.bin/agentcore deploy --target default --yes   # aplica la eliminación del recurso
```

Esto elimina el AgentCore Runtime y los recursos asociados. El bucket S3 de
sesiones y el secreto de Secrets Manager (creados por CDK en el Paso 3)
**no** se eliminan con esto.

### Paso 11 (limpieza): eliminar los prerrequisitos de CDK (reversible)

📁 Directorio: `06-agente-AgentCore-deploy/infra/`

```bash
cd infra                # si venías de la raíz del proyecto
npx cdk destroy
```

El bucket se creó con `removal_policy=DESTROY` y `auto_delete_objects=True`,
y el secreto con `removal_policy=DESTROY`, por lo que `cdk destroy` elimina
ambos recursos por completo — no quedan huérfanos que limpiar manualmente.
