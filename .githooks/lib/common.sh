#!/usr/bin/env bash
# Shared helpers for .githooks/pre-commit and .githooks/pre-push.
# Not directly executable - sourced by the actual hooks.
#
# Scope and limitations (read this before trusting these checks blindly):
#   - This is a client-side safety net, not a security boundary. Any of it
#     can be skipped with `git commit/push --no-verify`, and it only ever
#     sees what's in *this* clone's git history/diff.
#   - Secret detection: gitleaks is used as the primary scanner whenever
#     it's on PATH (its built-in ruleset covers far more credential types -
#     AWS, GCP, Slack, Stripe, generic high-entropy strings, etc. - than
#     the handful of hand-written patterns below). This repo has NO
#     root-level devbox project on purpose - every NN-step/ directory is
#     meant to be independently copyable as its own standalone project, so
#     _resolve_gitleaks() below never invents a root project or does a
#     cwd-based directory search for one (git also always runs hooks with
#     cwd = repo root regardless of which directory you ran `git commit`
#     from, so a cwd-based lookup wouldn't find a step's devbox.json
#     anyway). It relies purely on PATH, which covers:
#       - A global install via `devbox global add gitleaks@latest` (once
#         per machine - see README.md "Toolchain" section). This is
#         devbox's per-machine global package feature, not a per-repo
#         project, so it doesn't add scaffolding here either.
#       - Being inside an activated devbox+direnv shell for any NN-step/
#         directory (every step's own devbox.json declares
#         "gitleaks@latest") - direnv exports that shell's PATH, and PATH
#         is inherited by the hook's child process regardless of what cwd
#         the hook itself runs with.
#       - Any other install method that puts gitleaks on PATH.
#     If gitleaks truly isn't on PATH by any of those means,
#     scan_diff_for_secrets() falls back to a small built-in set of
#     high-confidence patterns (AWS keys, PEM private keys, Discord
#     webhooks, Telegram bot tokens, Google OAuth client secrets) so the
#     hooks still do something useful either way.
#   - Neither gitleaks nor the fallback patterns are general PII detection
#     (names, emails, phone numbers, SSNs) - that's a different problem
#     with a much higher false-positive rate, not something either of these
#     tools claim to solve.
#   - gitleaks' `protect` mode (used below) only scans the diff being
#     committed/pushed right now, same limitation as the fallback. Run
#     `gitleaks git --no-banner` (no `--staged`, full history) periodically
#     to check for secrets already sitting further back in history that
#     predate these hooks.

RED=$'\033[0;31m'
YELLOW=$'\033[0;33m'
GREEN=$'\033[0;32m'
NC=$'\033[0m'

# Filenames that must never be committed, regardless of content - these are
# exactly the files this repo's per-step .gitignore already excludes
# (Google OAuth credentials/token, AWS/SSH private keys, .env files). This
# is the backstop for when someone bypasses .gitignore with `git add -f`.
BLOCKED_FILENAME_REGEX='(^|/)(credentials\.json|token\.json|\.env(\..+)?|id_rsa|id_ed25519|.*\.pem|.*\.p12|.*\.pfx)$'
ALLOWED_ENV_SUFFIX_REGEX='\.(example|sample|template)$'

# Lines containing one of these markers are treated as known-fake
# placeholders (README examples, test fixtures) and are not blocked -
# without this, this repo's own documented examples (e.g. the fake Telegram
# token in 08-agente-Autonomo/README.md, or AWS's own "AKIAIOSFODNN7EXAMPLE"
# convention) would trip the scanner every time that line re-enters a diff.
PLACEHOLDER_MARKER_REGEX_ERE='(EXAMPLE|NOTREAL|NOT_REAL|CHANGEME|CHANGE_ME|DUMMY|PLACEHOLDER|REDACTED|FAKE[-_]?TOKEN|SAMPLE|XXXXXXXX)'

# check_blocked_filenames: reads a list of filenames (one per line) on
# stdin, prints a BLOCKED line for each credential-shaped filename found,
# and returns non-zero if any were found.
check_blocked_filenames() {
  local file hit=0
  while IFS= read -r file; do
    [ -z "$file" ] && continue
    echo "$file" | grep -Eq "$BLOCKED_FILENAME_REGEX" || continue
    echo "$file" | grep -Eiq "$ALLOWED_ENV_SUFFIX_REGEX" && continue
    echo "${RED}BLOCKED:${NC} '$file' looks like a credential/secret file and must not be committed."
    hit=1
  done
  return $hit
}

# GITLEAKS_INVOCATION: populated by _resolve_gitleaks() below with the
# command (as an array, so no quoting/splitting issues) needed to run
# gitleaks - either the bare binary, or wrapped in `devbox run --`. Empty
# if gitleaks can't be resolved at all.
GITLEAKS_INVOCATION=()

# _resolve_gitleaks: sets the GITLEAKS_INVOCATION array if `gitleaks` is on
# PATH (see the header comment above for how it gets there - global devbox
# install, an activated step devbox shell, or any other install method).
# Deliberately PATH-only: no cwd-based directory search and no root-level
# devbox.json, since this repo intentionally has neither (see header
# comment). Returns non-zero if gitleaks isn't on PATH, so the caller can
# fall back to the hand-written pattern set.
_resolve_gitleaks() {
  if command -v gitleaks >/dev/null 2>&1; then
    GITLEAKS_INVOCATION=(gitleaks)
    return 0
  fi
  GITLEAKS_INVOCATION=()
  return 1
}

# scan_diff_for_secrets: reads a unified diff (as produced by `git diff`,
# with default context lines - added lines start with a single '+') on
# stdin. Uses gitleaks if it can be resolved (directly or via devbox - see
# _resolve_gitleaks, far broader ruleset than hand-written patterns);
# otherwise falls back to a small set of high-confidence patterns. Returns
# non-zero if any non-placeholder secret is found.
scan_diff_for_secrets() {
  if _resolve_gitleaks; then
    _scan_diff_with_gitleaks
    return $?
  fi
  _scan_diff_with_fallback_patterns
}

# _scan_diff_with_gitleaks: pipes the diff on stdin into `gitleaks stdin`
# (scans arbitrary text, not just git history) using this repo's
# .gitleaks.toml if present. Prints gitleaks' own findings, filtering out
# hits whose matched secret text carries an obvious placeholder marker.
# Requires GITLEAKS_INVOCATION to already be set (see _resolve_gitleaks).
_scan_diff_with_gitleaks() {
  local diff_input report gitleaks_args
  diff_input=$(cat)
  [ -z "$diff_input" ] && return 0

  report=$(mktemp)
  gitleaks_args=(stdin --no-banner --exit-code 0 --report-format json --report-path "$report")
  [ -f "$REPO_ROOT/.gitleaks.toml" ] && gitleaks_args+=(--config "$REPO_ROOT/.gitleaks.toml")

  printf '%s\n' "$diff_input" | "${GITLEAKS_INVOCATION[@]}" "${gitleaks_args[@]}" >/dev/null 2>&1

  local hit=0
  if [ -s "$report" ] && [ "$(cat "$report")" != "[]" ] && [ "$(cat "$report")" != "null" ]; then
    local filtered
    if command -v python3 >/dev/null 2>&1; then
      filtered=$(python3 - "$report" "$PLACEHOLDER_MARKER_REGEX_ERE" <<'PYEOF'
import json, re, sys
path, marker_re = sys.argv[1], sys.argv[2]
with open(path) as f:
    findings = json.load(f) or []
pattern = re.compile(marker_re, re.IGNORECASE)
kept = [f for f in findings if not pattern.search(f.get("Secret", "") or f.get("Match", "") or "")]
print(json.dumps(kept))
PYEOF
      )
    else
      filtered=$(cat "$report")
    fi

    if [ -n "$filtered" ] && [ "$filtered" != "[]" ]; then
      echo "${RED}BLOCKED:${NC} gitleaks found possible secret(s):"
      if command -v python3 >/dev/null 2>&1; then
        printf '%s' "$filtered" | python3 -c '
import json, sys
for f in json.load(sys.stdin):
    rule = f.get("RuleID")
    match = (f.get("Match") or "")[:120]
    print("    rule=%r match=%r" % (rule, match))
'
      else
        printf '%s\n' "$filtered" | sed 's/^/    /'
      fi
      hit=1
    fi
  fi

  rm -f "$report"
  return $hit
}

# _scan_diff_with_fallback_patterns: original hand-written pattern set,
# used only when gitleaks is not installed. Reads the diff on stdin.
_scan_diff_with_fallback_patterns() {
  local added
  added=$(grep -E '^\+' | grep -Ev '^\+\+\+' || true)
  [ -z "$added" ] && return 0

  local hit=0
  local labels=(
    "AWS access key ID"
    "AWS secret access key"
    "private key material"
    "Discord webhook URL"
    "Telegram bot token"
    "Google OAuth client secret"
  )
  local patterns=(
    'AKIA[0-9A-Z]{16}'
    'aws_secret_access_key.{0,5}[:=].{0,5}[A-Za-z0-9/+=]{40}'
    '-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----'
    'discord(app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+'
    '[0-9]{8,10}:[A-Za-z0-9_-]{34,36}'
    '"client_secret"[[:space:]]*:[[:space:]]*"[A-Za-z0-9_-]{10,}"'
  )
  local case_insensitive=(0 1 0 0 0 1)

  local i label pattern ci lines real
  for i in "${!patterns[@]}"; do
    label="${labels[$i]}"
    pattern="${patterns[$i]}"
    ci="${case_insensitive[$i]}"
    if [ "$ci" = "1" ]; then
      lines=$(printf '%s\n' "$added" | grep -Ei -- "$pattern" || true)
    else
      lines=$(printf '%s\n' "$added" | grep -E -- "$pattern" || true)
    fi
    [ -z "$lines" ] && continue
    real=$(printf '%s\n' "$lines" | grep -Eiv -- "$PLACEHOLDER_MARKER_REGEX_ERE" || true)
    [ -z "$real" ] && continue
    echo "${RED}BLOCKED:${NC} possible $label found:"
    printf '%s\n' "$real" | sed 's/^/    /'
    hit=1
  done

  return $hit
}

# quick_static_check: reads a list of *.py filenames (one per line) on
# stdin, compiles each (catches syntax errors, zero setup required) and
# runs `ruff check` on them if ruff is available on PATH. Returns non-zero
# if any syntax error or ruff finding is present.
quick_static_check() {
  local files hit=0
  files=$(cat)
  [ -z "$files" ] && return 0

  if command -v python3 >/dev/null 2>&1; then
    local f err_file
    err_file=$(mktemp)
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      [ -f "$f" ] || continue
      if ! python3 -m py_compile "$f" 2>"$err_file"; then
        echo "${RED}SYNTAX ERROR:${NC} $f"
        sed 's/^/    /' "$err_file"
        hit=1
      fi
    done <<< "$files"
    rm -f "$err_file"
  else
    echo "${YELLOW}NOTE:${NC} python3 not found - skipping syntax check."
  fi

  if command -v ruff >/dev/null 2>&1; then
    echo "Running ruff on changed Python files..."
    if ! printf '%s\n' "$files" | xargs -r ruff check; then
      hit=1
    fi
  else
    echo "${YELLOW}NOTE:${NC} ruff not installed - skipping lint (not a dependency of any" \
         "step yet; install it or add it as a dev dependency for stricter checks)."
  fi

  return $hit
}
