# 07 - Interfaz web (chat en el navegador)

Este paso agrega un cliente web de chat para el agente ya desplegado en
**06-agente-AgentCore-deploy**. No reimplementa el agente ni lo vuelve a
desplegar - solo agrega una capa delgada encima del runtime de AgentCore ya
existente:

- **`backend/`** - una función Lambda que reenvía cada mensaje del navegador
  al AgentCore Runtime desplegado, usando `boto3.invoke_agent_runtime`
  (mismo mecanismo que usa `agentcore invoke` en el paso 06, pero accesible
  desde un navegador en lugar de la terminal).
- **`frontend/`** - una página HTML/JS estática con una interfaz de chat,
  incluyendo confirmación en pantalla (botones Sí/Cancelar) para
  interrupciones como `delete_email`.
- **`infra/`** - un stack de CDK (Python) que despliega ambas piezas: la
  Lambda detrás de una Function URL, el frontend en un bucket S3 privado, y
  una única distribución de **CloudFront** que sirve ambos desde un solo
  dominio HTTPS (`/chat` va a la Lambda, todo lo demás va al bucket S3).
  Ni el bucket ni la Function URL son públicos - ambos están restringidos a
  CloudFront mediante Origin Access Control (OAC).

## Por qué esta arquitectura

- **Un solo dominio HTTPS.** El navegador solo habla con la URL de
  CloudFront, tanto para los archivos estáticos como para `/chat`. Esto
  evita problemas de CORS y significa que el navegador nunca necesita
  credenciales de AWS - toda llamada a `bedrock-agentcore:InvokeAgentRuntime`
  la hace la Lambda, con su propio rol de IAM.
- **Nada accesible sin pasar por CloudFront.** El bucket S3 del frontend
  tiene `BLOCK_ALL` en accesos públicos y solo CloudFront (vía Origin
  Access Control) puede leerlo. La Function URL de la Lambda sí es técnicamente
  pública a nivel de red, pero cada request debe llevar un header secreto
  (`x-origin-verify`) generado aleatoriamente por CDK en cada despliegue,
  que solo la distribución de CloudFront conoce e inyecta - la función
  rechaza cualquier request sin ese header antes de invocar al agente. Se
  optó por este mecanismo (en lugar de OAC + `AWS_IAM`, el enfoque
  "recomendado" para Function URLs) porque en la práctica el flujo de
  firma SigV4 de CloudFront para peticiones POST con OAC resultó
  poco confiable (las peticiones nunca llegaban a ejecutar el handler,
  incluso siguiendo el workaround documentado por AWS con
  `x-amz-content-sha256`) - ver comentarios en
  `infra/stacks/web_interface_stack.py`.
- **Permisos mínimos.** La Lambda solo tiene permiso
  `bedrock-agentcore:InvokeAgentRuntime` sobre el ARN exacto del runtime que
  le pasas por contexto de CDK - no puede invocar ningún otro agente de la
  cuenta.
- **Reversible.** Igual que el stack de prerrequisitos del paso 06, este
  stack usa `RemovalPolicy.DESTROY` en todo lo que crea (bucket con
  `auto_delete_objects`, sin distribución "retenida"), así que
  `cdk destroy` elimina todo sin dejar residuos.

### Autenticación

Toda la distribución (frontend y `/chat` por igual) está protegida con
**HTTP Basic Auth**, aplicado en el borde por una CloudFront Function antes
de que la petición llegue a S3 o a la Lambda (ver `_build_basic_auth_function`
en `infra/stacks/web_interface_stack.py`). Sin credenciales válidas, la
respuesta es un 401 inmediato - el navegador muestra su prompt de login
nativo, sin necesidad de cambios en el frontend.

> ⚠️ **Limitación conocida:** esto es un control ligero con una sola
> credencial compartida, apropiado para un demo/uso personal - no es un
> sustituto de autenticación real por usuario (Cognito, un proveedor de
> identidad, etc.) si esta URL se comparte con más personas. El agente
> detrás de esta interfaz tiene acceso a tu Gmail, Calendar y Docs reales,
> así que cualquiera con estas credenciales tiene ese mismo acceso.

Las credenciales se generan automáticamente en el primer despliegue (usuario
`admin`, contraseña aleatoria) y se imprimen como outputs de `cdk deploy`
(`BasicAuthUsername` / `BasicAuthPassword`) - la contraseña no se guarda en
ningún otro lugar, cópiala en ese momento. Para volver a verla:

```bash
aws cloudformation describe-stacks --stack-name PersonalAssistantWebInterface \
  --query "Stacks[0].Outputs" --region us-east-1
```

Para usar tus propias credenciales en lugar de la generada automáticamente,
agrega `-c basicAuthUsername=<usuario> -c basicAuthPassword=<contraseña>` al
comando `cdk deploy` del Paso 3 más abajo.

## Estructura

```
07-agente-Web-Interface/
├── backend/
│   ├── agent_client.py    # Lógica compartida: invoke_agent_runtime
│   ├── handler.py         # Entrypoint de la Lambda (Function URL)
│   └── local_server.py    # Servidor de desarrollo local (mismo código, sin AWS Lambda)
├── frontend/
│   ├── index.html
│   ├── app.js             # Lógica de chat + manejo de interrupciones
│   ├── styles.css
│   └── config.js          # URL del backend (se ajusta según el entorno)
├── infra/
│   ├── app.py
│   ├── stacks/web_interface_stack.py
│   └── ...                # cdk.json, package.json, etc.
└── pyproject.toml         # boto3, para backend/ (workspace con infra/)
```

## Desarrollo local

Antes de desplegar nada, puedes probar el frontend contra el agente ya
desplegado en el paso 06, corriendo el backend localmente:

📁 Directorio: `07-agente-Web-Interface/`

```bash
uv sync   # instala boto3

export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:<cuenta>:runtime/<id>
# (el mismo ARN que ves en `agentcore status` dentro de 06-agente-AgentCore-deploy)

cd backend
uv run python local_server.py
```

Esto levanta un servidor en `http://127.0.0.1:8000`. Antes de abrir
`frontend/index.html` en tu navegador, cambia temporalmente
`frontend/config.js` para que apunte ahí:

```js
window.AGENT_CHAT_API_URL = "http://127.0.0.1:8000/chat";
```

(el valor por defecto, `/chat`, es una ruta relativa pensada para cuando el
frontend ya está desplegado detrás de CloudFront - ver la sección de
despliegue más abajo). Recuerda revertir este cambio antes de desplegar,
ya que `config.js` se sube a S3 tal como está.

Usa tus credenciales locales de AWS (perfil `walsen`, igual que el resto del
repo) - el servidor local llama a `invoke_agent_runtime` directamente, sin
pasar por Lambda.

## Despliegue en AWS (Lambda + S3 + CloudFront vía CDK)

> ⚠️ Estos pasos crean recursos reales y facturables en tu cuenta de AWS
> (función Lambda, bucket S3, distribución de CloudFront). Revisa cada paso
> antes de ejecutarlo. Requiere que el agente del paso 06 ya esté
> desplegado.

### Paso 1: Obtener el ARN del runtime ya desplegado

📁 Directorio: `06-agente-AgentCore-deploy/`

```bash
./agentcore-cli-tools/node_modules/.bin/agentcore status --json | jq -r '.resources[0].identifier'
```

### Paso 2: Instalar dependencias del stack de CDK

📁 Directorio: `07-agente-Web-Interface/infra/`

```bash
cd infra
uv sync      # instala aws-cdk-lib y constructs
npm install  # instala el CLI de cdk (a nivel de proyecto, no global)
```

### Paso 3: Vista previa y despliegue

📁 Directorio: `07-agente-Web-Interface/infra/`

```bash
# Vista previa de los recursos a crear (no crea nada)
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk diff \
  -c agentRuntimeArn=<ARN-del-Paso-1>

# Crear los recursos reales en AWS
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk deploy \
  -c agentRuntimeArn=<ARN-del-Paso-1> --require-approval never

# O, para elegir tus propias credenciales de Basic Auth en vez de la
# contraseña generada automáticamente:
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk deploy \
  -c agentRuntimeArn=<ARN-del-Paso-1> \
  -c basicAuthUsername=<usuario> -c basicAuthPassword=<contraseña> \
  --require-approval never
```

Al finalizar, `cdk deploy` imprime:
- `DistributionDomainName` - la URL de CloudFront donde abrir el chat.
- `ChatFunctionName` - el nombre de la Lambda, útil para ver logs
  (`aws logs tail /aws/lambda/<ChatFunctionName> --follow`).
- `BasicAuthUsername` / `BasicAuthPassword` - las credenciales de acceso
  (ver sección "Autenticación" más arriba).

Abre la URL de `DistributionDomainName` en tu navegador - el navegador
pedirá las credenciales de Basic Auth, y luego la interfaz de chat ya está
lista para usarse contra el agente real.

### Actualizar el frontend después de un cambio

Cada `cdk deploy` vuelve a subir los archivos de `frontend/` al bucket S3 e
invalida la caché de CloudFront automáticamente (ver `BucketDeployment` en
`web_interface_stack.py`), así que basta con repetir el comando `cdk deploy`
del Paso 3 tras editar cualquier archivo en `frontend/`.

## Limpieza

Para eliminar todos los recursos creados por este paso (Lambda, bucket S3,
distribución de CloudFront):

📁 Directorio: `07-agente-Web-Interface/infra/`

```bash
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk destroy \
  -c agentRuntimeArn=<ARN-del-Paso-1>
```

Esto no afecta al agente ni a los recursos del paso 06 (bucket de sesiones,
secreto de Secrets Manager, AgentCore Runtime) - son stacks independientes.
