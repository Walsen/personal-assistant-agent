---
name: cdk-iterate-and-verify
description: Use when developing, deploying, or debugging the CDK stack for the web chat interface (Lambda + S3 + CloudFront) in this personal assistant agent step. Covers the diff/deploy/destroy loop, retrieving Basic Auth credentials, and local backend testing before deploying.
---

# CDK iterate-and-verify loop (web interface)

## Goal

Make a change to the Lambda proxy backend or CloudFront/S3 infra and verify
it end-to-end, without unnecessary full deploys or losing track of the
Basic Auth credentials.

## Local-first: test the backend before touching CDK

Before deploying, run the backend locally against the real deployed
AgentCore agent - most bugs in `backend/handler.py`/`agent_client.py` are
catchable this way without a CDK deploy cycle at all:

```bash
uv sync   # from 07-agente-Web-Interface/
export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/<id>
cd backend && uv run python local_server.py
```

Then point `frontend/config.js` at `http://127.0.0.1:8000/chat`
temporarily (revert before deploying - it defaults to the relative `/chat`
path used once behind CloudFront) and open `frontend/index.html` directly
in a browser.

Also run `devbox run -- uv run pytest -v` from the step root - the backend
has a full mocked test suite (`tests/test_agent_client.py`,
`tests/test_handler.py`) that catches most regressions without any AWS
call.

## CDK loop

📁 All commands from `07-agente-Web-Interface/infra/`:

```bash
uv sync && npm install   # once, or after infra dependency changes

# Preview - always do this before deploy on a non-trivial change
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk diff \
  -c agentRuntimeArn=<arn>

# Apply
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk deploy \
  -c agentRuntimeArn=<arn> --require-approval never
```

Or via this step's `Justfile`: `just infra-diff <arn>` / `just infra-deploy <arn>`.

Frontend-only changes (edited `frontend/*.js`/`.html`/`.css`) still need a
`cdk deploy` - the `BucketDeployment` construct re-syncs S3 and invalidates
CloudFront automatically on every deploy, there's no separate "just upload
static files" path.

## Retrieving Basic Auth credentials

The password is generated once and only printed as a `cdk deploy` output -
if you didn't copy it then, retrieve it later with:
```bash
aws cloudformation describe-stacks --stack-name PersonalAssistantWebInterface \
  --query "Stacks[0].Outputs" --region us-east-1
```
Or `just outputs`. To set your own instead of the generated one, add
`-c basicAuthUsername=<user> -c basicAuthPassword=<pass>` to the deploy
command - this only takes effect on a fresh deploy of that context value,
changing it later requires another `cdk deploy` with the new values.

## Debugging a deployed request that isn't working

1. Confirm the request even reached the Lambda:
   ```bash
   aws logs tail /aws/lambda/<ChatFunctionName> --follow --region us-east-1
   ```
   (get `<ChatFunctionName>` from `cdk deploy`'s output or `just outputs`)
2. If nothing shows up in logs at all, the request likely never got past
   CloudFront - check the `x-origin-verify` shared-secret header logic in
   `handler.py`/the CloudFront Function, and confirm Basic Auth
   credentials are correct (a 401 from the Basic Auth CloudFront Function
   never reaches the Lambda or S3 origin, so it won't appear in Lambda
   logs at all).

## Cleanup

```bash
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk destroy -c agentRuntimeArn=<arn>
```
Everything in this stack uses `RemovalPolicy.DESTROY` (including
`auto_delete_objects` on the S3 bucket), so destroy is clean - no manual
S3 emptying needed first.
