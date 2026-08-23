"""Personal assistant agent definition."""

from strands import Agent

SYSTEM_PROMPT = "You are a helpful personal assistant."

agent = Agent(system_prompt=SYSTEM_PROMPT)


def run() -> None:
    """Entry point used by the CLI to start an interactive agent session."""
    agent("Hello! How can you help me today?")


if __name__ == "__main__":
    run()
