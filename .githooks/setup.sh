#!/usr/bin/env bash
# One-time setup: point this clone's git hooks at the versioned hooks in
# .githooks/ instead of the untracked, per-clone .git/hooks/ directory, and
# make sure gitleaks is available on PATH for real secret-detection
# coverage (falls back to a smaller hand-written pattern set otherwise).
#
# This repo deliberately has NO root-level devbox.json/.envrc - every
# NN-step/ directory is meant to be independently copyable as its own
# standalone project, and a root devbox project would undermine that. So
# gitleaks is installed per-machine via `devbox global` (devbox's built-in
# feature for exactly this - user-wide tools, no project file involved),
# not as a repo dependency.
#
# Run once after cloning:  bash .githooks/setup.sh
set -euo pipefail
REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"

chmod +x "$REPO_ROOT/.githooks/pre-commit" "$REPO_ROOT/.githooks/pre-push"
git -C "$REPO_ROOT" config core.hooksPath .githooks

if command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks already on PATH - nothing more to install."
elif command -v devbox >/dev/null 2>&1; then
  echo "Installing gitleaks via 'devbox global' (per-machine, not a repo dependency)..."
  devbox global add gitleaks@latest
  echo ""
  echo "If 'gitleaks' isn't found in new shells after this, add the following to"
  echo "your shell rcfile (~/.bashrc or ~/.zshrc) once, per devbox's own instructions:"
  echo '  eval "$(devbox global shellenv)"'
else
  echo "NOTE: devbox not found on PATH - the hooks will still run, but will fall"
  echo "back to a much smaller hand-written secret pattern set instead of gitleaks."
  echo "Install devbox (https://www.jetify.com/devbox/docs/installing_devbox/), or"
  echo "gitleaks directly (https://github.com/gitleaks/gitleaks/releases), for full"
  echo "coverage."
fi

echo ""
echo "Done. core.hooksPath set to .githooks for this clone."
echo "  - pre-commit: blocks credential filenames, scans for secrets (gitleaks if"
echo "                on PATH), quick Python static check"
echo "  - pre-push:   re-scans for secrets, runs pytest for any touched step directory"
echo ""
echo "Bypass a single commit/push if you're sure it's a false positive:"
echo "  git commit --no-verify"
echo "  git push --no-verify"
