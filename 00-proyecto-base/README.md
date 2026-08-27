# 00 · Proyecto base

Punto de partida del **Personal Assistant Agent**. Antes de escribir código,
este paso te deja el entorno de desarrollo listo: gestión de herramientas con
**devbox**, activación automática con **direnv** y empaquetado de Python con
**uv**.

## Herramientas que usa el proyecto

| Herramienta | Para qué sirve aquí |
|-------------|---------------------|
| [devbox](https://www.jetify.com/devbox) | Instala y aísla todas las herramientas del proyecto (Python, uv, jq, awscli, etc.) sin ensuciar tu sistema. Declaradas en `devbox.json`. |
| [direnv](https://direnv.net/) | Activa el entorno de devbox automáticamente al entrar (`cd`) en la carpeta. Configurado en `.envrc`. |
| [uv](https://docs.astral.sh/uv/) | Gestor de paquetes y entornos virtuales de Python. Usa `pyproject.toml` + `uv.lock`. |
| Python 3.14 | Versión fijada en `.python-version`. |
| [Strands Agents](https://strandsagents.com/) | Framework sobre el que se construye el agente (`strands-agents`). |

## Requisitos previos (instalar una sola vez)

Solo necesitas instalar **devbox** y **direnv** en tu máquina; el resto de
herramientas las provee devbox.

### 1. Instalar devbox

```bash
curl -fsSL https://get.jetify.com/devbox | bash
```

### 2. Instalar direnv

```bash
# macOS
brew install direnv

# Debian / Ubuntu
sudo apt install direnv

# o con el instalador oficial
curl -sfL https://direnv.net/install.sh | bash
```

### 3. Enganchar direnv a tu shell

Añade la línea correspondiente al final del archivo de configuración de tu shell
y reinicia la terminal:

```bash
# bash  (~/.bashrc)
eval "$(direnv hook bash)"

# zsh   (~/.zshrc)
eval "$(direnv hook zsh)"

# fish  (~/.config/fish/config.fish)
direnv hook fish | source
```

> Sin este paso, direnv no puede activar el entorno automáticamente.

## Puesta en marcha del proyecto

```bash
# 1. Entra en la carpeta del paso
cd 00-proyecto-base

# 2. Autoriza el .envrc (solo la primera vez, o cuando cambie)
direnv allow
```

La primera vez, direnv ejecutará `devbox generate direnv` (ver `.envrc`) y
devbox descargará todas las herramientas declaradas en `devbox.json`. Puede
tardar un poco la primera vez; después es instantáneo.

Si prefieres no usar direnv, puedes entrar al entorno manualmente:

```bash
devbox shell
```

### Instalar dependencias de Python

Ya dentro del entorno (con uv disponible):

```bash
uv sync
```

Esto crea el `.venv` e instala las dependencias según `pyproject.toml` y
`uv.lock`.

## Ejecutar el agente

```bash
uv run proyecto-base
```

## Ejecutar los tests

```bash
uv run pytest
```

## Verificar que todo está configurado

```bash
devbox version   # devbox instalado
direnv version   # direnv instalado
python --version # debería mostrar Python 3.14.x
uv --version     # uv disponible dentro del entorno
```

## Estructura

```
00-proyecto-base/
├── .envrc              # Integración direnv → devbox
├── .python-version     # Python 3.14
├── devbox.json         # Herramientas del entorno
├── pyproject.toml      # Metadatos y dependencias (uv)
├── uv.lock             # Lockfile reproducible (versionado)
├── src/proyecto_base/  # Código del agente
└── tests/              # Tests con pytest
```

## Problemas frecuentes

- **`direnv: error .envrc is blocked`** → ejecuta `direnv allow` dentro de la carpeta.
- **No se activa nada al entrar en la carpeta** → falta el `direnv hook` en tu shell (paso 3).
- **`devbox: command not found`** → reinicia la terminal tras instalar devbox o revisa tu `PATH`.
- **Descarga lenta la primera vez** → es normal; devbox está bajando las herramientas y las cachea para siguientes usos.
