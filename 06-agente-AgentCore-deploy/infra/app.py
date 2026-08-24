#!/usr/bin/env python3
"""CDK app entry point.

Provisions AWS prerequisites for deploying the personal assistant agent to
Amazon Bedrock AgentCore Runtime: an S3 bucket for session persistence and
a Secrets Manager secret placeholder for the Google OAuth token.

Usage (from this infra/ directory):
    uv run cdk synth
    uv run cdk deploy
    uv run cdk destroy

The actual agent deployment (agentcore configure / agentcore deploy)
remains a separate, manual step - see ../DEPLOY_AGENTCORE.md.
"""

import os

import aws_cdk as cdk

from stacks.prerequisites_stack import AgentPrerequisitesStack

app = cdk.App()

AgentPrerequisitesStack(
    app,
    "PersonalAssistantAgentPrerequisites",
    description=(
        "S3 sessions bucket and Secrets Manager secret placeholder for the "
        "personal-assistant-agent AgentCore Runtime deployment."
    ),
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)

app.synth()
