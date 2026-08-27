# 08 - Agente autónomo (ejecución programada, sin disparador humano)

Este paso agrega una capa de **autonomía** encima del agente ya desplegado
en **06-agente-AgentCore-deploy**. No reimplementa el agente ni crea uno
nuevo - agrega un disparador (EventBridge Scheduler) y una capa mínima de
checkpoint/idempotencia (DynamoDB) alrededor del mismo agente, para que se
ejecute solo, en un horario, sin que nadie escriba un prompt.

## Qué hace

Una vez por semana, una Lambda (`backend/handler.py`) invoca al agente
desplegado con una instrucción fija: ejecutar su skill
`weekly-billing-summary` (definida en el paso 06) y guardar el resultado
como una nueva sección fechada en un Google Doc llamado
"Weekly Assistant Digest" (creándolo si no existe todavía).

## Por qué es seguro ejecutarlo sin supervisión

El agente ya tiene dos mecanismos de seguridad que no se tocan en este
paso:

- **Steering** (`steering.py`, paso 05/06): `send_email` y `create_event`
  quedan bloqueados hasta que el usuario confirma explícitamente en un
  mensaje posterior.
- **Interrupt** (`delete_email`, paso 05/06): requiere una respuesta
  síncrona humana antes de ejecutarse.

Una invocación programada no tiene un humano que responda. Si el modelo
alguna vez intentara una de esas herramientas, simplemente quedaría
bloqueado o pendiente de interrupción - nunca podría completar una acción
irreversible por sí solo. Además, el prompt fijo (`DEFAULT_PROMPT` en
`handler.py`) le indica explícitamente no enviar correos, no crear eventos
de calendario y no borrar/archivar nada como parte de esta tarea - solo usa
herramientas de lectura (`list_recent_emails`, `get_email`) y de Google
Docs sin steering (`search_docs`, `create_doc`, `append_to_doc`).

Si el agente igual llegara a generar una interrupción (por ejemplo, si mal
interpreta la instrucción), el handler lo detecta, lo registra como
`blocked_on_interrupt` en la tabla de checkpoint, y hace fallar la
invocación de Lambda a propósito - eso queda visible en las métricas
`Errors` de CloudWatch, en vez de quedar silenciosamente colgado.

## Idempotencia

EventBridge Scheduler y Lambda pueden reintentar una invocación. Antes de
invocar al agente, la Lambda hace un `put_item` condicional en
`CheckpointTable` usando la semana ISO actual (`2026-W35`, por ejemplo)
como clave. Si ese `run_key` ya fue reclamado, la invocación se aborta sin
volver a invocar al agente ni duplicar la entrada en el digest.

## Notificaciones (Telegram / Discord)

Ya que nadie está mirando cuando corre una ejecución programada, la Lambda
puede enviar un mensaje corto a Telegram y/o Discord cada vez que una
ejecución termina (completada ✅, fallida ❌, o bloqueada en una
interrupción ⚠️) en vez de tener que revisar CloudWatch Logs para saber
qué pasó.

Ambos canales son **opcionales e independientes** entre sí - configura el
que prefieras (o ambos), o ninguno si preferís seguir revisando los logs
manualmente. Sin configuración, `notify()` (`backend/notifications.py`) no
hace nada - el digest funciona exactamente igual que antes.

| | Telegram | Discord |
|---|---|---|
| Qué necesitás | Bot token + chat ID | Solo una URL de webhook |
| Dónde llega el mensaje | Chat privado con tu bot | Un canal de un servidor de Discord |
| Límite de longitud del mensaje | 4096 caracteres | 2000 caracteres |
| Pasos para configurar | 3 (Sección A) | 1 (Sección B) |

### A. Configurar Telegram

#### A1. Crear el bot con BotFather

Abre una conversación con [@BotFather](https://t.me/BotFather) en Telegram
(el bot oficial para crear bots) y envía:

```
/newbot
```

BotFather te va a pedir un **nombre** para el bot (puede ser cualquier
cosa, ej. "Mi Asistente Personal") y luego un **username**, que debe
terminar obligatoriamente en `bot` (ej. `mi_asistente_personal_bot`).

Al terminar, BotFather responde con un mensaje que incluye un **token de
acceso HTTP API**, algo como:

```
123456789:AAHn2xK7vQZ_exampleTokenNotReal12345
```

Copia ese valor completo - es tu `TELEGRAM_BOT_TOKEN`. Trátalo como una
contraseña: quien lo tenga puede enviar mensajes en nombre de tu bot.

#### A2. Iniciar una conversación con tu bot

Busca tu bot por su username (el que elegiste en A1) dentro de Telegram y
presiona **Start** (o envíale cualquier mensaje, como "hola"). Este paso es
obligatorio - Telegram no entrega el chat ID de una conversación hasta que
esa conversación existe.

#### A3. Obtener tu chat ID

Con el token de A1, abre esta URL en el navegador (reemplaza `<TU_TOKEN>`):

```
https://api.telegram.org/bot<TU_TOKEN>/getUpdates
```

La respuesta es un JSON. Busca la sección `"chat"` dentro de `"message"`,
que se ve así:

```json
{
  "ok": true,
  "result": [
    {
      "message": {
        "chat": {
          "id": 987654321,
          "first_name": "Tu Nombre",
          "type": "private"
        }
      }
    }
  ]
}
```

El número en `"chat": {"id": ...}` es tu `TELEGRAM_CHAT_ID`.

> Si `"result"` aparece vacío (`[]`), significa que el paso A2 no se
> completó (o pasó demasiado tiempo). Envía otro mensaje al bot y recarga
> la URL de `getUpdates`.

### B. Configurar Discord

#### B1. Crear el webhook

En el servidor de Discord donde quieras recibir las notificaciones:

1. Click derecho sobre el canal (o **Configuración del canal** ⚙️) →
   **Integraciones**.
2. **Webhooks** → **Nuevo webhook**.
3. Opcionalmente, renómbralo (ej. "Asistente Personal") y elige un canal.
4. Click en **Copiar URL del webhook**.

Esa URL completa es tu `DISCORD_WEBHOOK_URL` (tiene esta forma:
`https://discord.com/api/webhooks/<id>/<token>`). No necesitas separarla en
partes - se usa tal cual.

### C. Verificar las credenciales antes de desplegar

Antes de tocar CDK, confirma que cada canal funciona con un `curl` directo
- así, si algo falla, sabes que es un problema de la credencial y no del
despliegue.

📁 Directorio: cualquiera

**Telegram:**

```bash
curl -s -X POST "https://api.telegram.org/bot<TU_TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "<TU_CHAT_ID>", "text": "Prueba desde el paso 08"}'
```

Una respuesta con `"ok":true` confirma que llegó el mensaje a tu chat de
Telegram. Si ves `"ok":false`, el `description` del error suele indicar
directamente el problema (token inválido, chat no encontrado, etc.).

**Discord:**

```bash
curl -s -X POST "<TU_WEBHOOK_URL>" \
  -H "Content-Type: application/json" \
  -d '{"content": "Prueba desde el paso 08"}'
```

Una respuesta vacía (sin salida) con código `204` es éxito - revisa el
canal de Discord para confirmar que llegó el mensaje. Podés ver el código
HTTP agregando `-w "\nHTTP %{http_code}\n"` al comando.

### D. Habilitar al desplegar

Con las credenciales ya verificadas, agrégalas al comando `cdk deploy` del
Paso 3 más abajo:

```bash
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk deploy \
  -c agentRuntimeArn=<ARN-del-Paso-1> \
  -c telegramBotToken=<tu-token> -c telegramChatId=<tu-chat-id> \
  -c discordWebhookUrl=<tu-webhook-url> \
  --require-approval never
```

Podés pasar solo las variables de un canal (Telegram o Discord), ambas, o
ninguna - cada una es independiente. Ver la sección "Probar manualmente"
más abajo para confirmar que las notificaciones también funcionan de
punta a punta, ya desplegadas en Lambda.

> ⚠️ Estas son credenciales reales pasadas como texto plano en la línea de
> comandos, lo que la mayoría de las shells guardan en el historial
> (`~/.bash_history` o equivalente). Si eso te preocupa en esta máquina,
> pasa los valores como variables de entorno y referéncialas en el comando
> (`-c telegramBotToken=$MY_TELEGRAM_TOKEN`), o limpia el historial de la
> shell después.

### E. Rotar o revocar credenciales

- **Telegram:** enviale `/revoke` a [@BotFather](https://t.me/BotFather)
  para tu bot y genera un token nuevo. Actualiza `TELEGRAM_BOT_TOKEN` con
  un nuevo `cdk deploy`.
- **Discord:** en la misma pantalla de **Integraciones → Webhooks**, borra
  el webhook (o regenéralo) - la URL anterior deja de funcionar
  inmediatamente. Actualiza `DISCORD_WEBHOOK_URL` con un nuevo
  `cdk deploy`.

### Solución de problemas

| Síntoma | Causa probable |
|---|---|
| `curl` a Telegram devuelve `"ok":false, "error_code":401` | Token inválido - revisa que copiaste el token completo de BotFather |
| `curl` a Telegram devuelve `"ok":false, "error_code":400, "description":"chat not found"` | Chat ID incorrecto, o nunca le escribiste al bot (paso A2) |
| `curl` a Discord devuelve `401` | La URL del webhook es incorrecta o el webhook fue borrado |
| `curl` a Discord devuelve `404` | El webhook fue eliminado - crea uno nuevo (Sección B) |
| Las credenciales funcionan con `curl` pero no llega nada tras invocar la Lambda | Revisa los logs (`aws logs tail /aws/lambda/<DigestFunctionName>`) - `notifications.py` registra cada intento fallido con el motivo exacto, sin hacer fallar la ejecución del digest |
| Mensaje llega cortado | El resumen supera el límite del canal (4096 Telegram / 2000 Discord) - se trunca automáticamente, no es un error |

## Atajos con `just`

Este paso incluye un `Justfile` que envuelve los comandos más largos de la
sección "Despliegue" y "Probar manualmente" de más abajo (`just` ya está
disponible vía `devbox`). Ejecuta `just --list` desde este directorio para
ver todos los atajos disponibles (`just infra-deploy <arn> ...`,
`just invoke <function-name>`, `just logs <function-name>`, etc.) — cada
uno llama exactamente al mismo comando documentado más abajo.

## Estructura

```
08-agente-Autonomo/
├── backend/
│   ├── handler.py         # Lambda: invoca al agente + checkpoint de idempotencia
│   └── notifications.py   # Notificaciones opcionales a Telegram/Discord
├── infra/
│   ├── app.py
│   ├── stacks/autonomous_stack.py   # Lambda + DynamoDB + EventBridge Schedule
│   └── ...                # cdk.json, package.json, etc.
└── pyproject.toml         # boto3, para backend/ (workspace con infra/)
```

## Despliegue

> ⚠️ Estos pasos crean recursos reales y facturables en tu cuenta de AWS
> (función Lambda, tabla DynamoDB, EventBridge Schedule). Requiere que el
> agente del paso 06 ya esté desplegado. No otorga ningún permiso nuevo de
> escritura sobre Gmail/Calendar/Docs - solo permiso para invocar el
> runtime del agente ya existente.

### Paso 1: Obtener el ARN del runtime ya desplegado

📁 Directorio: `06-agente-AgentCore-deploy/`

```bash
./agentcore-cli-tools/node_modules/.bin/agentcore status --json | jq -r '.resources[0].identifier'
```

### Paso 2: Instalar dependencias del stack de CDK

📁 Directorio: `08-agente-Autonomo/infra/`

```bash
cd infra
uv sync      # instala aws-cdk-lib y constructs
npm install  # instala el CLI de cdk (a nivel de proyecto, no global)
```

### Paso 3: Vista previa y despliegue

📁 Directorio: `08-agente-Autonomo/infra/`

```bash
# Vista previa de los recursos a crear (no crea nada)
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk diff \
  -c agentRuntimeArn=<ARN-del-Paso-1>

# Crear los recursos reales en AWS
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk deploy \
  -c agentRuntimeArn=<ARN-del-Paso-1> --require-approval never
```

Por defecto la ejecución ocurre cada 7 días (`rate(7 days)`). Para usar otro
horario (por ejemplo, todos los lunes a las 9am UTC), agrega
`-c scheduleExpression="cron(0 9 ? * MON *)"` al comando de arriba.

Para habilitar notificaciones por Telegram y/o Discord, agrega los flags
descritos en la sección "Notificaciones" más arriba al mismo comando de
`cdk deploy` - podés hacerlo ahora o en un `cdk deploy` posterior, ya que
volver a desplegar solo actualiza la configuración de la Lambda existente,
sin afectar el schedule ni la tabla de checkpoint.

Al finalizar, `cdk deploy` imprime:
- `DigestFunctionName` - el nombre de la Lambda.
- `CheckpointTableName` - el nombre de la tabla de idempotencia.

### Probar manualmente antes de esperar al horario

📁 Directorio: cualquiera (requiere AWS CLI configurado)

```bash
aws lambda invoke --function-name <DigestFunctionName-del-output> \
  --region us-east-1 --cli-binary-format raw-in-base64-out \
  /tmp/out.json && cat /tmp/out.json
```

Si configuraste notificaciones (sección anterior), este mismo comando
debería hacer llegar un mensaje ✅ a Telegram y/o Discord unos segundos
después de que termine la invocación - es la forma más simple de confirmar
que la integración funciona de punta a punta, sin esperar al horario
programado.

Revisa los logs con:

```bash
aws logs tail /aws/lambda/<DigestFunctionName> --follow --region us-east-1
```

## Limpieza

📁 Directorio: `08-agente-Autonomo/infra/`

```bash
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk destroy \
  -c agentRuntimeArn=<ARN-del-Paso-1>
```

Esto no afecta al agente ni a los recursos de los pasos 06/07 - son stacks
independientes.

## Próximos pasos posibles

- **Más disparadores:** un poller de Gmail (`history.list` desde un
  checkpoint guardado) en vez de solo un horario fijo, para reaccionar a
  correos nuevos en vez de solo generar un resumen semanal.
- **Políticas explícitas (Cedar):** usar `agentcore add policy-engine` /
  `agentcore add policy` para restringir a nivel de plataforma qué
  herramientas puede llamar una sesión autónoma, en vez de confiar solo en
  el prompt.
- **Memoria entre ejecuciones:** AgentCore Memory (estrategia
  `SUMMARIZATION` o `USER_PREFERENCE`) para que el resumen semanal recuerde
  preferencias o contexto de ejecuciones anteriores.
- **Notificaciones interactivas:** hoy Telegram/Discord son solo salida
  (push de resultados) - un bot de Telegram con webhook propio (o el
  frontend web del paso 07) podría permitir *responder* a una interrupción
  bloqueada directamente desde el chat, en vez de solo enterarte de que
  ocurrió.
