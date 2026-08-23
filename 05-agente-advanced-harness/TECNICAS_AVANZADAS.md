# Técnicas avanzadas implementadas (05-agente-advanced-harness)

Este documento describe las técnicas de "harness" avanzado agregadas sobre el
agente base (autenticación de Google + herramientas de Gmail/Calendar/Docs),
por qué se eligieron para un asistente personal diario, y cómo cada una
contribuye a que el agente sea más seguro y controlable — en particular, a
evitar que elimine información importante y a que su memoria/contexto se
maneje de forma segura.

## Resumen

| Técnica | Módulo Strands | Propósito principal |
|---|---|---|
| Skills (habilidades) | `strands.vended_plugins.skills.AgentSkills` | Encapsular procedimientos específicos (resumen de gastos, limpieza de inbox) sin inflar el prompt base |
| Interrupts (interrupciones) | `strands.types.tools.ToolContext.interrupt` | Forzar una confirmación humana real antes de una acción destructiva (`delete_email`) |
| Steering (dirección/guía) | `strands.vended_plugins.steering.SteeringHandler` | Forzar, a nivel de código, que el modelo pida confirmación antes de acciones de riesgo moderado (`send_email`, `create_event`) |
| Agent-as-tool (agente como herramienta) | `Agent.as_tool()` | Delegar la estructuración de notas a un sub-agente especializado, separado del prompt principal |
| Diseño de herramientas por nivel de riesgo | `tools/gmail.py` (`archive_email` vs `delete_email`) | Preferir por diseño la acción reversible sobre la irreversible |
| Contexto de skill acotado (`allowed-tools`) | `SKILL.md` frontmatter | Limitar qué herramientas puede usar el agente mientras ejecuta una skill concreta |
| Session Manager (memoria persistente) | `strands.session.FileSessionManager` | Persistir historial de conversación y confirmaciones pendientes en disco, sobreviviendo reinicios del CLI |

A continuación se explica cada una en detalle.

---

## 1. Skills (habilidades) — `AgentSkills`

### Qué es

Strands provee un plugin de primera clase (`strands.vended_plugins.skills.AgentSkills`)
que implementa el estándar Agent Skills (`SKILL.md` con YAML frontmatter +
instrucciones en Markdown). En lugar de escribir todas las instrucciones de
cada tarea dentro del `system_prompt` principal, cada capacidad especializada
vive en su propio archivo `skills/<nombre>/SKILL.md`.

El plugin:
- Inyecta automáticamente un bloque `<available_skills>` en el contexto con
  solo el nombre y descripción de cada skill (metadata mínima).
- Expone una herramienta `skills(skill_name)` que el propio agente invoca
  cuando decide que una skill es relevante, cargando en ese momento las
  instrucciones completas.

Este proyecto define dos skills:
- `skills/weekly-billing-summary/SKILL.md` — resumen semanal de cargos/gastos
  a partir de correos de facturación.
- `skills/inbox-cleanup-scan/SKILL.md` — detección de correos promocionales
  candidatos a limpieza.

### Por qué es relevante para un asistente diario

Un asistente que administra correo, calendario y documentos tiende a
acumular procedimientos específicos con el tiempo ("cómo resumir gastos",
"cómo limpiar el inbox", futuras skills como "preparar notas de reunión").
Meter todo eso directamente en el `system_prompt` tiene dos problemas:

1. **Costo de tokens en cada turno.** Todas las instrucciones se cargan
   siempre, aunque el usuario esté pidiendo algo no relacionado.
2. **Prompt bloat.** Cuantas más reglas se acumulan en un solo prompt, más
   fácil es que el modelo ignore instrucciones enterradas en medio de un
   bloque de texto largo.

Con Skills, el costo de las instrucciones detalladas solo se paga cuando la
skill realmente se activa (progressive disclosure). El prompt base se
mantiene pequeño y enfocado, y cada skill puede evolucionar de forma
independiente sin tocar el resto del comportamiento del agente.

### Cómo mejora la seguridad y evita pérdida de información

Cada `SKILL.md` no es solo una guía de pasos: también documenta
explícitamente qué **no** debe hacer el agente. Por ejemplo,
`weekly-billing-summary` indica *"Do not take any action (no replying, no
deleting) as part of this skill — it is read-only reporting"*, e
`inbox-cleanup-scan` indica que la clasificación es solo orientativa y que
nunca se debe archivar/eliminar un correo que el usuario no haya visto y
aprobado explícitamente en la conversación.

Además, el campo `allowed-tools` en el frontmatter de cada skill acota qué
herramientas están pensadas para usarse durante esa skill (ver sección 6).
Esto reduce la superficie de error: mientras el agente ejecuta
`weekly-billing-summary`, la instrucción explícita es usar solo
`list_recent_emails` y `get_email` — herramientas de solo lectura — evitando
que una tarea de "solo dame un resumen" termine, por error de razonamiento
del modelo, ejecutando una acción destructiva no relacionada.

---

## 2. Interrupts (interrupciones) — confirmación humana real antes de eliminar

### Qué es

Strands soporta un mecanismo de **interrupts**: una herramienta puede pausar
la ejecución del agente y esperar una respuesta humana real antes de
continuar, usando `tool_context.interrupt(name, reason)`. Esto es distinto
de simplemente pedirle al modelo en el prompt que "confirme antes de
actuar" — es una pausa real a nivel de ejecución que el código de la
aplicación debe resolver explícitamente para que el flujo continúe.

Implementado en `tools/gmail.py`:

```python
@tool(context=True)
def delete_email(tool_context: ToolContext, message_id: str, subject: str = "", sender: str = "") -> str:
    approval = tool_context.interrupt(
        "gmail-delete-approval",
        reason={"message_id": message_id, "subject": subject, "sender": sender},
    )
    if str(approval).strip().lower() not in {"y", "yes"}:
        return f"Deletion of email {message_id} was NOT performed (user did not confirm)."

    service = get_gmail_service()
    service.users().messages().trash(userId="me", id=message_id).execute()
    return f"Email {message_id} moved to Trash."
```

En `agent.py`, el loop del chatbot detecta cuando el resultado del agente
tiene `stop_reason == "interrupt"`, y en `_resolve_interrupts()` muestra al
usuario el remitente, asunto y ID exactos del correo antes de pedir una
confirmación explícita en la terminal (`y`/`N`). Solo si la respuesta es
afirmativa se reanuda el agente y se ejecuta la llamada real a
`messages.trash()`.

### Por qué es relevante para un asistente diario

Un asistente con permisos de escritura sobre Gmail puede, en teoría, borrar
correos importantes por una mala interpretación de una instrucción ambigua
("limpia mi bandeja" podría interpretarse de formas muy distintas). Dado
que Gmail borra permanentemente los mensajes en Trash después de ~30 días,
una eliminación equivocada es un daño real, aunque no inmediato.

### Cómo mejora la seguridad y evita pérdida de información

La diferencia clave frente a solo poner "confirma antes de borrar" en el
`system_prompt` es que **la ejecución del tool se detiene de verdad**. El
modelo no puede "decidir saltarse" la confirmación, porque
`tool_context.interrupt(...)` bloquea el flujo de ejecución en el código
Python hasta que el proceso que llama al agente responda explícitamente.
Esto se verificó en pruebas reales:

- Al responder `N`, la herramienta retorna que la eliminación **no** se
  realizó, y una verificación directa contra la API de Gmail confirmó que
  el correo no había sido movido a Trash.
- Al responder `y`, se ejecuta `messages.trash()`, y se confirmó vía la API
  de Gmail que el mensaje quedó efectivamente con la etiqueta `TRASH`.

Esto convierte "pedir confirmación" de una sugerencia de prompt (que un
modelo podría ignorar bajo instrucciones ambiguas o adversariales) a una
garantía estructural del código.

---

## 3. Steering — confirmación forzada en código para acciones de riesgo moderado

### Qué es

Además del Interrupt "duro" usado para `delete_email` (que pausa la
ejecución de verdad esperando una respuesta humana), Strands ofrece
**Steering**: un mecanismo más liviano donde un handler puede interceptar
una llamada a herramienta *antes* de que se ejecute y decidir entre
`Proceed` (dejarla continuar) o `Guide` (cancelarla y devolver al modelo una
instrucción de por qué, para que reintente de otra forma). A diferencia de
un Interrupt, Steering no detiene el proceso esperando input humano
síncrono — actúa dentro del propio loop del agente, guiando su
comportamiento de forma determinística.

Implementado en `steering.py`:

```python
class ConfirmationSteeringHandler(SteeringHandler):
    name = "confirmation-steering"

    async def steer_before_tool(self, *, agent, tool_use, **kwargs):
        tool_name = tool_use.get("name")
        if tool_name not in CONFIRMATION_REQUIRED_TOOLS:  # send_email, create_event
            return Proceed(reason="Not a tool requiring confirmation")

        signature = _signature(tool_name, tool_use.get("input", {}))
        guided_signatures = agent.state.get(_STATE_KEY) or []

        if signature in guided_signatures:
            # Ya se avisó una vez sobre esta acción exacta; se asume que el
            # usuario confirmó en un mensaje posterior.
            agent.state.set(_STATE_KEY, [s for s in guided_signatures if s != signature])
            return Proceed(reason="User already confirmed this exact action")

        agent.state.set(_STATE_KEY, guided_signatures + [signature])
        return Guide(reason="Summarize the action and ask the user to confirm before retrying.")
```

El handler se registra como plugin del agente junto a `AgentSkills`:

```python
agent = Agent(
    ...,
    plugins=[AgentSkills(skills=str(SKILLS_DIR)), ConfirmationSteeringHandler()],
)
```

### Por qué es relevante para un asistente diario

`send_email` y `create_event` son acciones de riesgo moderado: no son tan
destructivas como borrar un correo (nada se pierde permanentemente), pero
sí tienen efectos reales hacia afuera — un correo enviado a la persona
equivocada, o un evento creado en la fecha incorrecta, no se pueden
"deshacer" limpiamente sin una segunda acción correctiva. Antes de agregar
Steering, la única protección para estas dos herramientas era una línea en
el `system_prompt` ("Always confirm before sending emails, creating
events..."), que el modelo podía en teoría ignorar bajo una instrucción
ambigua o una cadena de razonamiento apresurada.

### Cómo mejora la seguridad y evita pérdida de información

Este control se verificó en pruebas reales end-to-end:

- En el primer intento de `send_email`, el handler detectó que esa firma de
  llamada (herramienta + argumentos exactos) no había sido señalada antes,
  devolvió `Guide`, y **la llamada real a la API de Gmail nunca se
  ejecutó** — se confirmó buscando el correo por asunto inmediatamente
  después y no apareció ningún resultado.
- El modelo, siguiendo la guía recibida, resumió el correo (destinatario,
  asunto, cuerpo) y preguntó "¿Envío este correo?" en lugar de enviarlo.
- Al responder el usuario "Yes, please send it.", el modelo reintentó
  exactamente la misma llamada a `send_email`, el handler reconoció la
  firma ya señalada anteriormente y devolvió `Proceed`, y esta vez sí se
  envió realmente (confirmado con un `Message ID` real devuelto por la API
  de Gmail).

La diferencia con el prompt-only approach es que aquí la decisión de
"bloquear la primera llamada" no depende de que el modelo recuerde o
respete una instrucción en lenguaje natural: el propio código intercepta la
llamada antes de que llegue a ejecutarse, sin importar qué haya razonado el
modelo. Esto reduce, de forma medible (Strands reporta 100% de cumplimiento
en sus propios benchmarks internos de Steering contra 82.5% con solo
instrucciones de prompt), la probabilidad de que un correo se envíe o un
evento se cree sin que el usuario lo haya visto y aprobado primero.

---

## 4. Agent-as-tool — sub-agente especializado para notas

### Qué es

El patrón "Agents as Tools" envuelve un agente especializado, con su propio
`system_prompt` y modelo, como una herramienta invocable por el agente
principal. En lugar de que el asistente principal intente estructurar notas
directamente (lo que requeriría agregar instrucciones de formato de notas a
su propio `system_prompt`, aplicando ese sesgo de formato a *todas* sus
respuestas, no solo a las de toma de notas), se creó `notes_agent.py`:

```python
notes_agent = Agent(
    name="notes_agent",
    description="Takes raw text ... and structures it into notes with a "
                 "summary, key points, action items, people mentioned, and "
                 "dates/deadlines. Use this whenever the user asks to take "
                 "notes on ... a piece of content.",
    model=_notes_model,
    system_prompt=NOTES_SYSTEM_PROMPT,
)

notes_tool = notes_agent.as_tool()
```

Este `notes_tool` se agrega a la lista de herramientas del agente
principal (`tools=[*ALL_TOOLS, notes_tool]`). El agente principal decide
cuándo delegar (por ejemplo, tras leer un correo con `get_email` o un
documento con `read_doc`) y le pasa el texto crudo al `notes_agent`, que
responde solo con las notas estructuradas.

### Por qué es relevante para un asistente diario

"Tomar notas" a partir de correos, documentos o conversaciones es
transversal a las distintas fuentes de información del asistente — no es
una tarea de Gmail, ni de Docs, es una capacidad propia que debería
comportarse igual sin importar de dónde vino el texto. Encapsularla como un
especialista independiente evita reglas de formato repetidas o
inconsistentes cada vez que el asistente principal intenta resumir algo
"al vuelo".

### Cómo mejora la seguridad y evita pérdida de información

El `NOTES_SYSTEM_PROMPT` incluye una instrucción explícita de no inventar
contenido: *"Never fabricate action items, dates, or people that are not
actually present in the source text you were given."* Esto es relevante
para evitar un tipo distinto de "pérdida de información" — no borrar datos
reales, sino **inventar** datos que no existían (una fecha límite o una
persona responsable que el modelo alucina), lo cual podría llevar al
usuario a actuar sobre información falsa. En una prueba real, el
`notes_agent` extrajo correctamente responsables, fechas y elementos de
acción de un texto de ejemplo con dos tareas y una fecha reprogramada, sin
agregar ningún dato que no estuviera en el texto original.

Adicionalmente, al ser un `Agent` separado, el `notes_agent` no tiene acceso
a ninguna herramienta de Gmail/Calendar/Docs (no se le pasó ningún `tools=`
propio) — solo puede leer el texto que se le entrega y responder texto
estructurado. Esto acota su radio de acción: aunque el agente principal le
delegue contenido sensible para resumir, el `notes_agent` no puede, por
diseño, enviar correos, borrar nada ni modificar documentos.

---

## 5. Diseño de herramientas por nivel de riesgo — `archive_email` vs `delete_email`

### Qué es

En lugar de exponer una sola herramienta de "eliminar correo", se agregaron
dos herramientas con niveles de riesgo distintos:

- **`archive_email(message_id)`** — remueve la etiqueta `INBOX`. El correo
  sigue existiendo y es recuperable buscando en "Todos los correos"; no
  requiere ninguna confirmación especial porque el riesgo de daño
  irreversible es prácticamente nulo.
- **`delete_email(...)`** — mueve el correo a Trash (borrado permanente tras
  ~30 días). Requiere el interrupt descrito en la sección 2.

El `system_prompt` y el `SKILL.md` de limpieza de inbox instruyen
explícitamente al agente a **preferir `archive_email`** para limpieza de
rutina, y a usar `delete_email` únicamente cuando el usuario pidió borrar
(no solo "limpiar" u "organizar") un mensaje específico.

### Por qué es relevante para un asistente diario

Muchas de las tareas que el usuario probablemente pedirá ("limpia mi
inbox", "sácame estos correos de la vista") no requieren borrado permanente
— solo requieren que el correo deje de aparecer en la bandeja principal.
Ofrecer solo una herramienta de "eliminar" fuerza una acción de alto riesgo
incluso cuando el usuario solo quería una de bajo riesgo.

### Cómo mejora la seguridad y evita pérdida de información

Este es un control de **superficie de daño por diseño**: al separar la
acción reversible de la irreversible en dos herramientas distintas, y guiar
al modelo (vía prompt y vía `SKILL.md`) a preferir la reversible, se reduce
la probabilidad de que una ambigüedad en el lenguaje del usuario ("limpia",
"organiza", "bórrame esto") termine en una eliminación permanente
innecesaria. La acción de mayor riesgo (`delete_email`) queda además
protegida por el interrupt de la sección 2, de modo que hay dos capas de
protección: preferencia de diseño hacia la opción reversible, y
confirmación humana obligatoria para la irreversible.

---

## 6. `allowed-tools` en Skills — acotar el radio de acción por tarea

### Qué es

Cada `SKILL.md` declara en su frontmatter YAML una lista `allowed-tools` con
las herramientas que esa skill está diseñada para usar:

```yaml
allowed-tools:
  - list_recent_emails
  - get_email
  - archive_email
  - delete_email
```

### Por qué es relevante y cómo mejora la seguridad

Esto documenta, de forma legible tanto para el modelo como para cualquier
desarrollador que mantenga el proyecto, el "contrato" de cada skill: qué
herramientas son razonables usar durante esa tarea concreta. Por ejemplo,
`weekly-billing-summary` solo declara herramientas de lectura
(`list_recent_emails`, `get_email`) — es una señal explícita, tanto para el
modelo como para quien lea el código, de que esta skill nunca debería
modificar ni eliminar nada, reforzando en un segundo lugar (además del
texto de instrucciones) la intención de "solo lectura" de esa tarea.

---

## 7. Session Manager — memoria persistente y segura entre reinicios

### Qué es

Strands provee `strands.session.FileSessionManager`, que persiste en disco
(en lugar de solo en memoria del proceso Python) el historial de mensajes,
el estado del agente (`agent.state` — incluyendo las firmas de confirmación
que usa `ConfirmationSteeringHandler`), y cualquier **interrupt pendiente**
sin resolver. Se conecta al agente con un solo parámetro:

```python
session_manager = FileSessionManager(
    session_id="personal-assistant-cli",
    storage_dir=str(SESSIONS_DIR),  # <raíz-del-proyecto>/.sessions
)

agent = Agent(
    ...,
    session_manager=session_manager,
)
```

Cada sesión se guarda como una carpeta bajo `.sessions/session_<session_id>/`
con los mensajes y el estado en archivos JSON. Este directorio se agregó a
`.gitignore`, ya que contiene el historial real de la conversación
(incluyendo contenido de correos, documentos, etc. que el agente haya leído
o discutido) y nunca debe subirse al repositorio.

### Por qué es relevante para un asistente diario

Antes de esta pieza, cada ejecución del CLI (`personal_assistant_agent.agent`)
empezaba con el agente completamente en blanco — sin memoria de
conversaciones anteriores, y sin memoria de si el usuario ya había
confirmado o rechazado alguna acción pendiente. Para un asistente que se
usa día a día (no una sesión de chat de una sola vez), esto es una
limitación real: el usuario esperaría poder cerrar la terminal y volver más
tarde sin perder el contexto de lo que se venía conversando.

### Cómo mejora la seguridad y evita pérdida de información

Esto se verificó con dos pruebas reales, cada una lanzando **procesos de
Python completamente separados** (no solo llamadas dentro del mismo
proceso) para simular reinicios reales del CLI:

1. **Persistencia de memoria conversacional.** En un primer proceso, se le
   dijo al agente "mi color favorito es teal". Ese proceso terminó. En un
   segundo proceso (arrancando desde cero, sin ningún estado en memoria),
   al preguntar "¿cuál es mi color favorito?" el agente respondió
   correctamente "teal" — la respuesta solo pudo venir de los archivos de
   sesión en `.sessions/`, no de memoria del proceso anterior (que ya no
   existía).

2. **Persistencia de un interrupt pendiente sin resolver.** Se inició una
   solicitud de `delete_email` en un proceso, que generó el `Interrupt`
   habitual y el proceso terminó **sin responderlo** (simulando un cierre
   inesperado del CLI mientras esperaba confirmación). En un segundo
   proceso nuevo, al cargar el agente se recuperó el mismo `Interrupt`
   exacto (mismo `id`, mismo `reason` con el `message_id` y `subject`
   originales) desde disco. Al responder `y` en ese segundo proceso, la
   eliminación se ejecutó correctamente contra la API real de Gmail
   (verificado: el mensaje pasó a tener la etiqueta `TRASH`).

Este segundo punto es el más importante desde el ángulo de seguridad: sin
`session_manager`, un cierre inesperado del CLI mientras una acción
destructiva estaba pendiente de confirmación simplemente perdería ese
estado — la próxima vez que el usuario pidiera algo relacionado, el agente
no tendría memoria de que ya había una eliminación a medio confirmar,
pudiendo llevar a confusión o a que el usuario tenga que repetir la
solicitud desde cero. Con `FileSessionManager`, la confirmación pendiente
sobrevive intacta, y solo se resuelve cuando el usuario realmente responde
— nunca se ejecuta por default ni se pierde silenciosamente.
