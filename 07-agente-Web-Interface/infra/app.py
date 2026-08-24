#!/usr/bin/env python3
"""CDK app entry point for the personal assistant web interface.

Provisions:
- A Lambda function (backend/handler.py) that proxies chat requests to the
  already-deployed AgentCore Runtime agent (from 06-agente-AgentCore-deploy),
  exposed via a Function URL.
- An S3 bucket holding the static frontend (frontend/), served through
  CloudFront.
- A single CloudFront distribution in front of both: "/chat" routes to the
  Lambda Function URL, everything else routes to the S3 bucket. This means
  the browser only ever talks to one HTTPS origin (the CloudFront domain),
  with no CORS hop and no public S3 bucket or public Lambda URL - both
  origins are locked down to CloudFront via Origin Access Control.
- An HTTP Basic Auth check (CloudFront Function) in front of the entire
  distribution, so the deployed URL isn't open to the public internet -
  see the docstring on WebInterfaceStack for details and its limitations.

Requires the AgentCore Runtime agent from 06-agente-AgentCore-deploy to
already be deployed - this stack does not create the agent itself, only
the web client in front of it.

Usage (from this infra/ directory):
    uv run cdk deploy -c agentRuntimeArn=arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/<id>

    # optionally pick your own Basic Auth credentials (otherwise a random
    # password is generated and printed as a stack output):
    uv run cdk deploy -c agentRuntimeArn=<arn> -c basicAuthUsername=<user> -c basicAuthPassword=<pass>

    uv run cdk destroy
"""

import os

import aws_cdk as cdk

from stacks.web_interface_stack import WebInterfaceStack

app = cdk.App()

agent_runtime_arn = app.node.try_get_context("agentRuntimeArn")
if not agent_runtime_arn:
    raise SystemExit(
        "Missing required context value 'agentRuntimeArn'. Pass it with:\n"
        "  uv run cdk deploy -c agentRuntimeArn=<runtime-arn>\n"
        "(the ARN of the already-deployed agent from 06-agente-AgentCore-deploy - "
        "see `agentcore status` in that step)."
    )

WebInterfaceStack(
    app,
    "PersonalAssistantWebInterface",
    agent_runtime_arn=agent_runtime_arn,
    basic_auth_username=app.node.try_get_context("basicAuthUsername"),
    basic_auth_password=app.node.try_get_context("basicAuthPassword"),
    description=(
        "Web chat client (Lambda proxy + S3/CloudFront static frontend) for the "
        "personal-assistant-agent AgentCore Runtime deployment."
    ),
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)

app.synth()
