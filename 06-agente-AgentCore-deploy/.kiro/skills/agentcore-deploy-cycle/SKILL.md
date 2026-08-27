---
name: agentcore-deploy-cycle
description: Use when deploying, redeploying, checking status, invoking, or viewing logs for the personal assistant agent on Amazon Bedrock AgentCore Runtime. Covers the validate/deploy/status/invoke/logs loop and the critical two-copy gotcha in this step's directory layout.
---

# AgentCore deploy/status/invoke/logs cycle

## Goal

Iterate on the deployed agent (`06-agente-AgentCore-deploy/`) safely and
efficiently, without editing the wrong copy of the code or forgetting a
step in the deploy loop.

## Critical gotcha: two copies of the agent package exist

This directory contains BOTH:
- `src/personal_assistant_agent/` - a legacy copy from the CLI-based
  chatbot steps. **Dead code as of the AgentCore CLI migration - editing
  this does nothing to the deployed agent.**
- `app/personal_assistant_agent/personal_assistant_agent/` - the REAL
  deployed copy, referenced by `agentcore.json`'s
  `"codeLocation": "app/personal_assistant_agent/"`.

Always confirm you're editing under `app/personal_assistant_agent/` before
making a change intended to affect the deployed agent. A previous session
task nearly wrote new tests against the dead `src/` copy - check
`agentcore.json`'s `codeLocation` if ever unsure which copy is live.

## The cycle (all commands run from `06-agente-AgentCore-deploy/`, the repo root for this step - the CLI resolves `agentcore/` relative to cwd)

1. **Alias the CLI** (once per shell): the binary is a project-local
   dependency, not global:
   ```bash
   alias agentcore="$(pwd)/agentcore-cli-tools/node_modules/.bin/agentcore"
   ```
   Or use the `Justfile` recipes in this step (`just deploy`, `just status`,
   etc.) which already reference the right path.

2. **Validate** after any edit to `agentcore/agentcore.json` or
   `agentcore/aws-targets.json`:
   ```bash
   agentcore validate
   ```

3. **Deploy**:
   ```bash
   agentcore deploy --target default --yes
   ```
   Add `--dry-run` or `--diff` first if you want to preview before
   applying. This uses AWS CodeBuild - no local Docker needed for
   `CodeZip` build type.

4. **Check status**:
   ```bash
   agentcore status               # human-readable
   agentcore status --json | jq . # for scripting, e.g. extracting the runtime ARN
   ```
   The runtime ARN from `status --json`'s `.resources[0].identifier` is
   what steps 07/08 need as their `agentRuntimeArn` CDK context value.

5. **Invoke** to smoke-test:
   ```bash
   agentcore invoke "Hola"
   ```
   To test a pending interrupt (e.g. `delete_email`), invoke once to get
   an `"id"` back in the interrupt response, then resume:
   ```bash
   agentcore invoke '{"interrupt_responses": [{"interrupt_id": "<id>", "response": "y"}]}'
   ```

6. **Logs/traces** when something looks wrong:
   ```bash
   agentcore logs
   agentcore traces
   ```
   Or CloudWatch directly: log group
   `/aws/bedrock-agentcore/runtimes/{agent-id}-DEFAULT`.

## Before any deploy involving a code change

- If you touched `app/personal_assistant_agent/personal_assistant_agent/tools/*`,
  run that copy's own test suite first (it has its own venv):
  ```bash
  cd app/personal_assistant_agent && uv run pytest -v
  ```
- If you changed env vars (`AGENT_SESSIONS_BUCKET`, `GOOGLE_TOKEN_SECRET_ID`),
  update them in `agentcore/agentcore.json`'s `envVars` array, not just
  locally - `agentcore deploy` only applies what's declared there.

## Cleanup

```bash
agentcore remove agent --name personal_assistant_agent --yes
agentcore deploy --target default --yes   # applies the removal
```
This does not remove the prerequisites stack (S3 bucket, Secrets Manager
secret) - see the separate `infra/` CDK stack for that (`cdk destroy` from
`infra/`).
