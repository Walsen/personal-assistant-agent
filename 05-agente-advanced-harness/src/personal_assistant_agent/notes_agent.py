"""Specialized note-taking sub-agent, exposed as a tool (agents-as-tools).

Rather than teaching the main assistant a note-structuring format inline in
its own system prompt (which would apply that formatting bias to every
response, not just note-taking requests), this sub-agent has its own
narrow, tailored system prompt and is exposed to the main agent as a single
callable tool. The main agent decides when a request is "take notes on X"
and delegates the actual extraction/structuring to this specialist.
"""

from strands import Agent
from strands.models.bedrock import BedrockModel

NOTES_SYSTEM_PROMPT = """You are a note-taking specialist. You receive raw text
(from an email, a document, or a conversation) and turn it into structured
notes. Always extract, when present in the source text:

- **Summary**: 1-3 sentence overview
- **Key points**: bullet list of the most important facts or decisions
- **Action items**: bullet list of anything someone needs to do, with the
  responsible person and due date if mentioned
- **People mentioned**: names/roles referenced in the text
- **Dates/deadlines**: any specific dates or deadlines mentioned

If a section has nothing relevant in the source text, omit that section
rather than inventing content. Never fabricate action items, dates, or
people that are not actually present in the source text you were given.
Output only the structured notes, in Markdown, with no extra commentary."""

_notes_model = BedrockModel(
    model_id="global.anthropic.claude-sonnet-4-6",
    region_name="us-east-1",
    temperature=0.1,
)

notes_agent = Agent(
    name="notes_agent",
    description=(
        "Takes raw text (email body, document content, or conversation excerpt) and "
        "structures it into notes with a summary, key points, action items, people "
        "mentioned, and dates/deadlines. Use this whenever the user asks to take notes "
        "on, summarize into notes, or extract action items from a piece of content."
    ),
    model=_notes_model,
    system_prompt=NOTES_SYSTEM_PROMPT,
)

notes_tool = notes_agent.as_tool()
