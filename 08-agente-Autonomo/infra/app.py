#!/usr/bin/env python3
"""CDK app entry point for the autonomous weekly digest.

Provisions a schedule + Lambda that invokes the already-deployed AgentCore
Runtime agent from 06-agente-AgentCore-deploy on its own, with no human
prompting it. See stacks/autonomous_stack.py for what's provisioned and why
it's safe to run unattended.

Requires the AgentCore Runtime agent from 06-agente-AgentCore-deploy to
already be deployed - this stack does not create the agent itself, only
the trigger + checkpoint around it.

Usage (from this infra/ directory):
    uv run cdk deploy -c agentRuntimeArn=arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/<id>
    uv run cdk destroy

Optional push notifications on run completion/failure (see
backend/notifications.py and DEPLOY_AGENTCORE.md-style docs in this step's
README for how to obtain these credentials) - add whichever of these you
have to the deploy command above:
    -c telegramBotToken=<token> -c telegramChatId=<chat-id>
    -c discordWebhookUrl=<webhook-url>

Note: these are real credentials passed as plaintext CDK context on the
command line, which most shells record in ~/.bash_history (or equivalent).
Prefer setting them via environment variables and referencing those in the
command, or clear your shell history afterwards, if that's a concern on
this machine.
"""

import os

import aws_cdk as cdk

from stacks.autonomous_stack import AutonomousStack

app = cdk.App()

agent_runtime_arn = app.node.try_get_context("agentRuntimeArn")
if not agent_runtime_arn:
    raise SystemExit(
        "Missing required context value 'agentRuntimeArn'. Pass it with:\n"
        "  uv run cdk deploy -c agentRuntimeArn=<runtime-arn>\n"
        "(the ARN of the already-deployed agent from 06-agente-AgentCore-deploy - "
        "see `agentcore status` in that step)."
    )

schedule_expression = app.node.try_get_context("scheduleExpression") or "rate(7 days)"
telegram_bot_token = app.node.try_get_context("telegramBotToken")
telegram_chat_id = app.node.try_get_context("telegramChatId")
discord_webhook_url = app.node.try_get_context("discordWebhookUrl")

AutonomousStack(
    app,
    "PersonalAssistantAutonomous",
    agent_runtime_arn=agent_runtime_arn,
    schedule_expression=schedule_expression,
    telegram_bot_token=telegram_bot_token,
    telegram_chat_id=telegram_chat_id,
    discord_webhook_url=discord_webhook_url,
    description=(
        "Scheduled autonomous run (Lambda + EventBridge Schedule + DynamoDB checkpoint) "
        "of the personal-assistant-agent's weekly billing-summary digest."
    ),
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)

app.synth()
