---
name: scaffold-strands-step
description: Use when creating a new numbered step directory in this Strands Agents workshop repo (personal-assistant-agent), or fixing an existing step's Python package layout. Sets up the uv/pyproject.toml/src layout this repo expects and avoids the hyphenated-vs-underscore module name mismatch bug.
---

# Scaffold a Strands workshop step

## Goal

Create (or repair) a step directory with the exact `uv` + `pyproject.toml` +
`src/<module>/` layout this repo's other steps use, so `uv run`/`uv sync`
and the CLI entry point work on the first try.

## The bug this exists to prevent

`00-proyecto-base` originally had its source directory named
`src/personal-assistant-agent/` (hyphenated) while `pyproject.toml`
declared the importable module as `proyecto_base`. Hyphens are not valid in
Python module names, so `uv run python -c "import proyecto_base"` failed
with "Expected a Python module at: src/proyecto_base/__init__.py" and
nothing in the step could run. Always use underscores (or no separator) in
the actual `src/` directory name, and make sure `pyproject.toml`'s
`[project.scripts]` target matches it exactly.

## Steps

1. Pick the module name first (e.g. `personal_assistant_agent`), matching
   what other steps use unless there's a specific reason to diverge.

2. Directory layout:
   ```
   NN-step-name/
   ├── .envrc                 # eval "$(devbox generate direnv --print-envrc)"
   ├── devbox.json            # copy from an existing step, keep just@latest
   ├── pyproject.toml
   ├── src/
   │   └── <module_name>/     # underscore-separated, matches pyproject.toml
   │       ├── __init__.py
   │       └── agent.py
   └── README.md
   ```

3. `pyproject.toml` minimum shape (see any existing step for the exact
   `[build-system]` block — this repo currently uses `uv_build`):
   ```toml
   [project]
   name = "<kebab-or-underscore-name>"
   version = "0.1.0"
   requires-python = ">=3.14"
   dependencies = [
       "strands-agents>=1.53.0",
       "strands-agents-tools>=0.8.6",
   ]

   [project.scripts]
   <cli-name> = "<module_name>:main"

   [build-system]
   requires = ["uv_build>=0.12.3,<0.13.0"]
   build-backend = "uv_build"
   ```
   The `[project.scripts]` target (`<module_name>:main`) MUST point at a
   real importable package under `src/` with that exact name.

4. `src/<module_name>/__init__.py`:
   ```python
   from .agent import run


   def main() -> None:
       run()
   ```

5. Verify immediately, before writing any more code:
   ```bash
   cd NN-step-name && devbox run -- uv run python -c "import <module_name>; print('OK')"
   ```
   If this fails with "Expected a Python module at...", the `src/`
   directory name doesn't match `pyproject.toml` - fix the directory name,
   not the pyproject.toml declaration (unless the module name itself was
   wrong).

6. Copy `.kiro/steering/engineering-practices.md` from an adjacent step
   into the new step's own `.kiro/steering/` (steering files are per-step
   in this repo, not shared at the repo root - each step gets its own
   copy, adapted if the step's actual modules differ).

7. Add `pytest` as a dev dependency (`uv add --dev pytest`) and create a
   `tests/` directory with at least a smoke test for `run()`, per the
   TDD requirement in the steering doc - don't leave a new step without
   test coverage from the start.
