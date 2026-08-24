#!/usr/bin/env python3
"""CDK app entry point.

Provisions AWS prerequisites for deploying the personal assistant agent to
Amazon Bedrock AgentCore Runtime: an S3 bucket for session persistence and
a Secrets Manager secret placeholder for the Google OAuth token.

Usage (from this infra/ directory):
    uv run cdk synth
    uv run cdk deploy
    uv run cdk destroy

To grant the AgentCore Runtime execution role access to the sessions
bucket (needed after the agent has been deployed at least once and its
execution role ARN is known - see DEPLOY_AGENTCORE.md):
    uv run cdk deploy -c executionRoleArn=arn:aws:iam::<account>:role/<execution-role-name>

The actual agent deployment (agentcore configure / agentcore deploy)
remains a separate, manual step - see ../DEPLOY_AGENTCORE.md.
"""

import os

import aws_cdk as cdk

from stacks.prerequisites_stack import AgentPrerequisitesStack

app = cdk.App()

execution_role_arn = app.node.try_get_context("executionRoleArn")

AgentPrerequisitesStack(
    app,
    "PersonalAssistantAgentPrerequisites",
    execution_role_arn=execution_role_arn,
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
