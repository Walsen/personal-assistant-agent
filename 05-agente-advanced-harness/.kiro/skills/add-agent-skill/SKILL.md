---
name: add-agent-skill
description: Use when authoring a new AgentSkills.io skill (a skills/<name>/SKILL.md directory the personal assistant agent itself can activate at runtime via the `skills` tool) - not to be confused with Kiro's own IDE skills. Covers the frontmatter, instructions format, and registration used by weekly-billing-summary and inbox-cleanup-scan.
---

# Add an AgentSkills.io skill to the personal assistant agent

## Goal

Author a new runtime skill the deployed personal assistant agent (not
Kiro/the IDE agent) can activate on demand via the `skills` tool, following
the same shape as the two existing skills in `skills/`.

## Important distinction

This is NOT about Kiro's own `.kiro/skills/` (IDE dev-workflow skills, like
this one). This is the AgentSkills.io mechanism wired in via
`AgentSkills(skills=str(SKILLS_DIR))` in `agent.py` (`strands.vended_plugins.skills`),
which lets the *personal assistant agent itself* progressively disclose
extra instructions for recurring user-facing tasks (e.g. "summarize my
weekly bills") without bloating the base system prompt for every
conversation.

## Steps

1. Create `skills/<skill-name>/SKILL.md` (kebab-case name, matches the
   directory).

2. Frontmatter:
   ```yaml
   ---
   name: <skill-name>
   description: Use when <specific trigger phrase/intent the user would say>. <What it produces.>
   allowed-tools:
     - list_recent_emails
     - get_email
   ---
   ```
   `description` is what the model matches against user requests to decide
   whether to activate the skill - be specific about trigger phrasing, not
   vague ("summarize weekly bills" not "helps with emails").
   `allowed-tools` should list only the tools this skill's instructions
   actually need - keep it as narrow as the task allows, especially if the
   skill should never be able to trigger a write/irreversible action (see
   `inbox-cleanup-scan`, which lists `archive_email`/`delete_email` for its
   cleanup step but its own instructions gate their use on explicit user
   selection - the `allowed-tools` list is not itself a confirmation
   mechanism, the tool's own steering/Interrupt still applies).

3. Body: a `## Goal` (what this produces), numbered `## Steps` (the exact
   procedure - which tool calls in what order, what query strings to use,
   how to format output), and a `## Notes` section for scope boundaries
   (e.g. "read-only, no action taken" or "only look at last N days unless
   asked otherwise").

4. If the skill can lead to an irreversible action (like
   `inbox-cleanup-scan`'s archive/delete step), the instructions must
   explicitly require presenting a reviewable list and getting the user's
   selection BEFORE calling any gated tool - do not rely on the
   skill mechanism itself to enforce this, since it doesn't; the
   underlying tool's own steering/Interrupt (see `add-confirmation-gate`
   skill) is what actually blocks the action, the skill instructions are
   just guidance for the model's behavior leading up to that point.

5. No separate registration step is needed - `AgentSkills(skills=str(SKILLS_DIR))`
   in `agent.py` loads every subdirectory under `skills/` automatically at
   agent construction time.

6. Test by running the local chatbot (`uv run python -c "from personal_assistant_agent.agent import run; run()"`
   or the step's normal entry point) and phrasing a request that should
   match your skill's `description` - confirm the model activates it (it
   will mention using the skill or its behavior will visibly follow your
   `## Steps`) rather than answering ad hoc.
