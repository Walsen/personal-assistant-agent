---
name: rotate-google-token-secret
description: Use when the deployed AgentCore agent's Google authentication has expired, been revoked, or needs its OAuth token rotated in AWS Secrets Manager. Covers uploading/refreshing the token.json contents that back GOOGLE_TOKEN_SECRET_ID.
---

# Rotate the deployed agent's Google OAuth token secret

## Goal

Refresh or replace the Google OAuth token the deployed agent reads from
AWS Secrets Manager, without needing to redeploy the agent itself (the
secret is read at invocation time, not baked into the deployment).

## When you need this

- `agentcore invoke` starts returning an authentication error mentioning
  expired/revoked credentials.
- You widened `SCOPES` in `tools/auth.py` and need every existing user's
  token reissued under the new scope set.
- The token simply expired and refresh failed (e.g. grant revoked from the
  Google account side).

## Steps

1. Locally, re-run the OAuth bootstrap flow to get a fresh `token.json`
   (see the `google-oauth-setup` skill) - this MUST be done locally since
   the deployed container has no browser to complete a consent flow:
   ```bash
   uv run python -c "
   from personal_assistant_agent.tools import auth
   creds = auth.get_credentials()
   print('Authenticated. Token valid:', creds.valid)
   "
   ```
   This writes a fresh `token.json` to this step's project root.

2. Find the secret's ARN/name if you don't already have it (printed as a
   `cdk deploy` output when the prerequisites stack was created):
   ```bash
   cd infra && uv run cdk deploy  # outputs GoogleTokenSecretArn if not already known
   ```
   Or check the AWS console / `aws secretsmanager list-secrets`.

3. Upload the new token:
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id <GoogleTokenSecretArn-or-Name> \
     --secret-string file://token.json \
     --region us-east-1
   ```

4. No redeploy of the AgentCore runtime is needed - `tools/auth.py` reads
   the secret fresh on each cold start / token refresh check. If you want
   to force an immediate pickup rather than waiting for the next
   invocation's natural refresh check, the safest option is simply
   invoking the agent once (`agentcore invoke "Hola"`) and confirming no
   auth error comes back.

5. If the upload itself fails with "secret does not exist", the
   prerequisites stack (`infra/`) hasn't been deployed yet, or you have
   the wrong secret ID - re-check step 2's output rather than assuming the
   upload command itself is wrong.

## After rotation

Delete the local `token.json` if you're on a shared/ephemeral machine -
it's gitignored already, but it's still a live credential once written to
disk locally.
