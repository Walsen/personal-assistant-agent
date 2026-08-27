"""CDK stack for the autonomous weekly digest run.

Provisions the minimum needed to make the already-deployed AgentCore
Runtime agent (from 06-agente-AgentCore-deploy) run on its own on a
schedule, without touching that agent or its runtime:

- ChecklistTable: a DynamoDB table used purely as an idempotency checkpoint
  (see backend/handler.py) - one item per ISO week, conditionally written
  so retries/duplicate schedule firings are no-ops instead of duplicate
  runs.
- DigestFunction: a Lambda (backend/handler.py) that invokes the deployed
  agent with a fixed, read-mostly prompt and reports the outcome via its
  return value / raised exceptions (visible in CloudWatch Logs + the
  Lambda's built-in Errors metric).
- A weekly EventBridge Schedule that invokes DigestFunction - the only
  "trigger" this stack adds. No new destructive permissions are granted:
  the Lambda's only two IAM grants are bedrock-agentcore:InvokeAgentRuntime
  on the specific runtime ARN, and read/write on its own checkpoint table.

This stack does not change what the agent is allowed to do - the same
send_email/create_event steering gate and delete_email interrupt from
step 06 still apply. It only supplies a prompt (see DEFAULT_PROMPT in
handler.py) that sticks to tools with no such gate, so the scheduled run
can complete unattended instead of stalling on a confirmation nobody is
there to give.

Notifications: optionally, the digest Lambda pushes a short message to
Telegram and/or Discord on every run outcome (completed/failed/stalled) -
see backend/notifications.py. Both channels are entirely optional and
independent of each other; pass whichever credentials you have via CDK
context (telegramBotToken/telegramChatId and/or discordWebhookUrl - see
app.py) and leave the others unset to skip that channel. No IAM
permissions are needed for this - both are plain outbound HTTPS calls to
public APIs, not AWS services.

Uses RemovalPolicy.DESTROY on the table (no retained data) so `cdk destroy`
fully tears this down, independent of steps 06/07.
"""

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_scheduler_targets as scheduler_targets
from constructs import Construct


class AutonomousStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agent_runtime_arn: str,
        schedule_expression: str = "rate(7 days)",
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
        discord_webhook_url: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Idempotency checkpoint ---

        self.checkpoint_table = dynamodb.Table(
            self,
            "CheckpointTable",
            partition_key=dynamodb.Attribute(name="run_key", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # --- The scheduled digest Lambda ---

        environment = {
            "AGENT_RUNTIME_ARN": agent_runtime_arn,
            "CHECKPOINT_TABLE_NAME": self.checkpoint_table.table_name,
        }
        # Only set notification env vars that were actually provided, so an
        # unset channel is genuinely absent from the Lambda's environment
        # (notifications.py checks for that with os.environ.get(...)) rather
        # than present with a Python "None" string, which would be truthy
        # and break that channel's request instead of skipping it.
        if telegram_bot_token and telegram_chat_id:
            environment["TELEGRAM_BOT_TOKEN"] = telegram_bot_token
            environment["TELEGRAM_CHAT_ID"] = telegram_chat_id
        if discord_webhook_url:
            environment["DISCORD_WEBHOOK_URL"] = discord_webhook_url

        self.digest_function = lambda_.Function(
            self,
            "DigestFunction",
            runtime=lambda_.Runtime.PYTHON_3_14,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.minutes(5),
            memory_size=256,
            environment=environment,
        )

        # bedrock-agentcore:InvokeAgentRuntime on the specific agent runtime
        # this stack was told about - not a wildcard resource. No other
        # AWS permissions beyond this and the table access below: this
        # Lambda cannot call any other agent, and has no Gmail/Calendar/
        # Docs credentials of its own (those live inside the agent
        # runtime's own execution role from step 06, unaffected by this
        # stack).
        self.digest_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[agent_runtime_arn, f"{agent_runtime_arn}/*"],
            )
        )
        self.checkpoint_table.grant_read_write_data(self.digest_function)

        # --- The schedule itself ---

        self.schedule = scheduler.Schedule(
            self,
            "WeeklyDigestSchedule",
            schedule=scheduler.ScheduleExpression.expression(schedule_expression),
            target=scheduler_targets.LambdaInvoke(self.digest_function),
            description="Weekly autonomous run of the personal assistant agent's billing-summary digest.",
        )

        CfnOutput(
            self,
            "DigestFunctionName",
            value=self.digest_function.function_name,
            description="Lambda function name, useful for tailing logs (aws logs tail) or manual invokes.",
        )
        CfnOutput(
            self,
            "CheckpointTableName",
            value=self.checkpoint_table.table_name,
            description="DynamoDB table tracking which weekly runs have been claimed/completed.",
        )
