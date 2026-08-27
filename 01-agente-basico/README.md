# 01 - Agente básico

Este paso conecta el agente a un modelo de lenguaje real usando **Amazon Bedrock**.
A diferencia del [paso 00](../00-proyecto-base/), donde el agente se creaba con la
configuración por defecto, aquí se define explícitamente el modelo (Claude Sonnet)
y un *system prompt* orientado al asistente personal.

## Qué hay de nuevo respecto al paso 00

- Se usa `BedrockModel` de Strands para invocar **Claude Sonnet** vía Amazon Bedrock.
- El `system_prompt` describe el rol del asistente (Gmail, Calendar y Docs) y sus reglas de comportamiento.
- Se requiere **acceso a AWS Bedrock** (credenciales + modelo habilitado).

```python
bedrock_model = BedrockModel(
    model_id="global.anthropic.claude-sonnet-4-6",
    region_name="us-east-1",
    temperature=0.3,
)
agent = Agent(model=bedrock_model, system_prompt=SYSTEM_PROMPT)
```

## Requisitos previos

El entorno de desarrollo (devbox, direnv, uv, Python 3.14) es el mismo del
[paso 00](../00-proyecto-base/README.md). Si aún no lo configuraste, sigue esa
guía primero. En resumen:

```bash
cd 01-agente-basico
direnv allow      # o: devbox shell
uv sync
```

## Configurar el acceso a Amazon Bedrock

Este agente llama a Claude a través de Bedrock, así que necesitas credenciales de
AWS y el modelo habilitado en tu cuenta.

### 1. Habilitar el modelo en Bedrock

En la [consola de Amazon Bedrock](https://console.aws.amazon.com/bedrock/),
dentro de la región **us-east-1** (la misma que usa `region_name` en el código):

- Ve a **Model access**
- Solicita/activa el acceso a los modelos de **Anthropic Claude** (Claude Sonnet).
- Espera a que el estado quede en **Access granted**.

### 2. Configurar las credenciales de AWS

`awscli2` ya está incluido en `devbox.json`, así que `aws` está disponible dentro
del entorno. Configura tus credenciales con:

```bash
aws configure
```

Introduce tu *Access Key*, *Secret Key* y define la región `us-east-1`.

Alternativamente, puedes exportar las variables de entorno:

```bash
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
```

> Si usas un perfil con nombre o SSO, asegúrate de que la sesión esté activa
> (`aws sso login`) antes de ejecutar el agente.

### 3. Verificar el acceso

```bash
aws sts get-caller-identity        # confirma que las credenciales funcionan
aws bedrock list-foundation-models --region us-east-1 >/dev/null && echo "Bedrock OK"
```

## Ejecutar el agente

```bash
uv run personal-assistant-agent
```

El agente enviará un saludo inicial al modelo y mostrará la respuesta de Claude.

## Estructura

```
01-agente-basico/
├── .envrc                                  # Integración direnv → devbox
├── devbox.json                             # Herramientas del entorno
├── pyproject.toml                          # Dependencias (uv)
└── src/personal_assistant_agent/
    ├── __init__.py                         # main() → run()
    └── agent.py                            # BedrockModel + Agent + system prompt
```

## Problemas frecuentes

- **`AccessDeniedException` / `You don't have access to the model`** → falta habilitar el modelo en **Bedrock → Model access** (paso 1).
- **`Unable to locate credentials`** → ejecuta `aws configure` o exporta las variables `AWS_*` (paso 2).
- **`ExpiredTokenException`** → renueva la sesión (`aws sso login` o nuevas claves temporales).
- **Errores de región** → verifica que tus credenciales y el modelo estén en `us-east-1`.
