---
name: google-oauth-setup
description: Use when setting up, debugging, or documenting Google OAuth (Gmail/Calendar/Docs/Drive API access) for any step in this personal-assistant-agent repo. Covers Google Cloud project setup, OAuth consent screen, credentials.json/token.json, and the get_credentials()/AuthenticationError flow used identically across steps 02-06.
---

# Google OAuth setup for Google Workspace tools

## Goal

Get a working `credentials.json` + `token.json` pair so `tools/auth.py`'s
`get_credentials()` can authenticate Gmail/Calendar/Docs/Drive API calls,
and know how to debug it when it breaks. This exact flow is duplicated
verbatim across steps 02, 03, 04, 05, and 06's READMEs - use this skill
instead of re-deriving or re-copying it, and update all five READMEs
together if the flow ever changes.

## One-time Google Cloud setup

1. Create or select a project at console.cloud.google.com.
2. Enable APIs (APIs & Services -> Library): Gmail API, Google Calendar
   API, Google Docs API, and (from step 04 onward) Google Drive API - the
   scopes required scale up per step, see "Scopes per step" below.
3. OAuth consent screen (APIs & Services -> OAuth consent screen): choose
   External (or Internal for a Workspace org), fill in app name/support
   email, then under Audience -> Test users, add your own Google account
   (required while the app is in "Testing" status).
4. Create credentials (Google Auth Platform -> Clients -> Create OAuth
   client): Application type = Desktop app. Download the JSON.

## Per-step local setup

1. Rename the downloaded file to `credentials.json` and place it at the
   step's project root (e.g. `03-agente-impl-tools/credentials.json`).
   Never commit this file - it's already gitignored.
2. Run the bootstrap one-liner from that step's root:
   ```bash
   uv run python -c "
   from personal_assistant_agent.tools import auth
   creds = auth.get_credentials()
   print('Authenticated. Token valid:', creds.valid)
   "
   ```
3. This opens a browser for consent. On approval, `token.json` is written
   to the project root automatically and reused/refreshed on later runs.
   Also gitignored, never commit it.

## Scopes per step (tools/auth.py SCOPES list)

- Steps 02-03: `gmail.modify`, `gmail.send`, `calendar`, `documents`.
- Steps 04+: adds `drive.readonly` (needed for `search_docs`/Drive-backed
  document search).
- Step 06 (deployed): same scopes, but the token itself is stored/read via
  AWS Secrets Manager (`GOOGLE_TOKEN_SECRET_ID` env var) instead of a local
  `token.json`, since the deployed container has no browser - see
  `06-agente-AgentCore-deploy/DEPLOY_AGENTCORE.md` Part 1 section 5.

If you widen the scopes list, existing users must delete their
`token.json` and redo the consent flow - a token authorized under the old
scope set won't silently gain the new scope.

## Debugging (AuthenticationError, from steps 05+)

`get_credentials()` raises `AuthenticationError` (not a raw exception) in
these cases - the message itself tells you which:
- `credentials.json` missing entirely.
- A stored token's refresh failed (`RefreshError` - usually a revoked
  grant or a scope mismatch). Fix: delete `token.json`, redo the consent
  flow.
- (Step 06 only) No valid token found in the configured Secrets Manager
  secret - a deployed container can't run the interactive flow, so you
  must re-provision `token.json` locally and re-upload it (see
  `DEPLOY_AGENTCORE.md` Part 2, "Preparar el token para despliegue").

Steps 02/03 don't yet have `AuthenticationError`/logging - if working in
those, first check whether `tools/auth.py` there has been backported to
match steps 05+'s pattern (it should have been, see the engineering
practices steering doc); if not, treat that as tech debt, not expected
behavior, before debugging further.
