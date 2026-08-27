# Git hooks

Versioned git hooks for this repo, since `.git/hooks/` itself isn't tracked
and wouldn't survive a fresh clone.

## Enable (once per clone)

```bash
bash .githooks/setup.sh
```

This sets `core.hooksPath` to `.githooks` for your local clone only (a git
config setting, not committed - every clone must run this once), and
installs **gitleaks** per-machine via `devbox global` if it isn't already
on PATH - see "Toolchain" below for why it's per-machine and not a repo
dependency.

## What runs

**pre-commit** (fast, runs on every `git commit`):
- Blocks committing files that look like credentials by name
  (`credentials.json`, `token.json`, `.env*`, private key files) - this is
  the backstop for `git add -f` bypassing `.gitignore`.
- Scans the staged diff for secrets using **gitleaks** if it's on PATH -
  its ruleset covers AWS, GCP, Slack, Stripe, generic API keys/high-entropy
  strings, and much more than we'd hand-write. Falls back to a small
  built-in pattern set (AWS keys, PEM private key headers, Discord
  webhooks, Telegram bot tokens, Google OAuth `client_secret`) if gitleaks
  isn't on PATH at all, so the hook still does something useful either
  way. Lines/matches containing an obvious placeholder marker (`EXAMPLE`,
  `NOTREAL`, `CHANGEME`, etc.) are not blocked, so documented fake examples
  in READMEs don't trip it.
- Runs a quick static check on staged `*.py` files: `python3 -m py_compile`
  (catches syntax errors, always available) plus `ruff check` if `ruff` is
  on PATH (not currently a dependency of any step - install it yourself if
  you want this to actually run, e.g. `uv tool install ruff`).

**pre-push** (runs on every `git push`):
- Re-scans the full range of commits being pushed for secrets (same
  gitleaks-or-fallback logic as pre-commit) - catches something that
  slipped through commit-time, e.g. via `--no-verify`, an amend, or a
  merge.
- Runs `pytest` for each step directory (`00-08`) that has changed files in
  this push and has its own `tests/` directory - not the whole repo every
  time. Uses `devbox run -- uv run pytest` if `devbox` is available,
  otherwise falls back to plain `uv run pytest`.

## Toolchain

This repo deliberately has **no root-level `devbox.json`/`.envrc`** -
every `NN-step/` directory is meant to be independently copyable as its
own standalone project (each has its own `devbox.json`, `.envrc`,
`pyproject.toml`, etc.), and a root-level devbox project would make the
repo root itself "a project," undermining that. So `gitleaks` is not a
repo dependency - it's resolved purely via PATH (see `_resolve_gitleaks()`
in `.githooks/lib/common.sh`), which in practice means one of:

- **A one-time per-machine install** via `devbox global add gitleaks@latest`
  (what `setup.sh` does for you) - this is devbox's built-in feature for
  user-wide tools with no project file involved, so it adds nothing to
  this repo.
- **Being inside an activated devbox+direnv shell** for any `NN-step/`
  directory - every step's own `devbox.json` already declares
  `"gitleaks@latest"` alongside `python`, `uv`, `just`, etc., so it's on
  PATH automatically whenever you `cd` into a step with direnv active.
- Any other install method (`brew install gitleaks`, a manual binary
  download, etc.) that puts it on PATH.

If none of those apply, the hooks fall back to a small hand-written
pattern set automatically - see the header comment in `common.sh`.

Note: git always runs hooks with the *repo root* as the working directory,
regardless of which subdirectory you ran `git commit`/`git push` from - so
there's no cwd-based lookup for a step's `devbox.json` here; it really is
PATH-only.

Optionally add a `.gitleaks.toml` at the repo root to customize
rules/allowlist - it's picked up automatically by both hooks if present.

To check the full commit history (not just the current diff - gitleaks in
these hooks only ever sees what's being committed/pushed *right now*), run
periodically from anywhere gitleaks is on PATH:
```bash
gitleaks git --no-banner
```

## Bypassing

```bash
git commit --no-verify   # skip pre-commit
git push --no-verify      # skip pre-push
SKIP_TESTS=1 git push     # keep the secret scan, skip the test run
```

Use `--no-verify` deliberately and only for confirmed false positives - it
disables the safety net entirely for that commit/push.

## What this does NOT do

- **Not a security boundary.** This is a client-side convenience check.
  Anyone can bypass it with `--no-verify`, and it has no effect on pushes
  made by anyone who hasn't run `setup.sh`, or from any other clone/CI
  system. If you need enforcement that can't be bypassed locally, that
  has to live server-side (e.g. a GitHub branch protection rule + required
  status check, or a pre-receive hook on a self-hosted remote).
- **Not general PII detection.** Even with gitleaks installed, this only
  covers known credential *shapes* (API keys, tokens, private keys, etc.).
  It will not catch a real person's name, email address, phone number, or
  similar PII pasted into a file - that's a different problem with a much
  higher false-positive/false-negative rate for regex/entropy-based tools,
  and neither gitleaks nor
  [detect-secrets](https://github.com/Yelp/detect-secrets) claim to solve
  it. If PII scanning is a real requirement, that needs a purpose-built
  tool, not a secret scanner repurposed for it.
- **Only sees the diff being committed/pushed right now.** A secret already
  sitting further back in this repo's history won't be flagged
  retroactively - run a history-wide scanner (e.g. `gitleaks detect`)
  separately if you're worried about that.

## Extending

- **If gitleaks is installed:** add rules/allowlist entries via a
  `.gitleaks.toml` at the repo root - it's picked up automatically by both
  hooks, no shell script changes needed.
- **Fallback pattern set** (used only when gitleaks isn't installed): add
  an entry to the `labels`/`patterns`/`case_insensitive` parallel arrays in
  `.githooks/lib/common.sh`'s `_scan_diff_with_fallback_patterns()`.
- Add a new blocked filename by extending `BLOCKED_FILENAME_REGEX` in the
  same file.
