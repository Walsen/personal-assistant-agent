"""CDK stack provisioning the AWS prerequisites for deploying the personal
assistant agent to Amazon Bedrock AgentCore Runtime.

This stack intentionally does NOT create the AgentCore Runtime, its
execution IAM role, or the deployment staging bucket - those remain part of
the manual `agentcore configure` / `agentcore deploy` workflow (see
DEPLOY_AGENTCORE.md), by design, so the agent deployment steps stay manual.

What this stack DOES create, since these are pure infrastructure
dependencies with no meaningful "configuration choices" during deploy:

- An S3 bucket for Strands' S3SessionManager (conversation history and
  pending interrupts), referenced by the agent via AGENT_SESSIONS_BUCKET.
- A Secrets Manager secret placeholder for the Google OAuth token,
  referenced via GOOGLE_TOKEN_SECRET_ID. The secret is created empty; the
  actual token value must still be uploaded manually (see README/DEPLOY_AGENTCORE.md)
  since it requires running the OAuth consent flow locally first - CDK
  cannot do this for you.

Both resources use RemovalPolicy.DESTROY with auto_delete_objects (bucket)
so `cdk destroy` fully tears down everything this stack created, keeping
the whole prerequisite lifecycle reversible.

Ordering note: the AgentCore Runtime's execution IAM role (created by
`agentcore deploy`, not by this stack) needs read/write access to the
sessions bucket, but that role doesn't exist yet the first time this stack
is deployed. Pass its ARN via the `execution_role_arn` parameter (typically
sourced from a CDK context value, see app.py) on a second `cdk deploy` run,
after the agent has been deployed once and its execution role ARN is known
(see `agentcore status` output, or DEPLOY_AGENTCORE.md).
"""

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class AgentPrerequisitesStack(Stack):
    """Provisions the S3 sessions bucket and Secrets Manager secret that the
    personal assistant agent needs when deployed to AgentCore Runtime.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        execution_role_arn: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The AgentCore Runtime execution role is created by `agentcore deploy`
        # (a separate, CLI-managed CDK stack), not by this stack, so it's
        # referenced here by ARN via ArnPrincipal rather than imported as a
        # full Role construct.
        execution_role_principal = (
            iam.ArnPrincipal(execution_role_arn) if execution_role_arn else None
        )

        self.sessions_bucket = s3.Bucket(
            self,
            "AgentSessionsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
        )

        if execution_role_principal:
            self.sessions_bucket.grant_read_write(execution_role_principal)

        self.google_token_secret = secretsmanager.Secret(
            self,
            "GoogleTokenSecret",
            description=(
                "Google OAuth token for the personal assistant agent's Gmail/Calendar/Docs "
                "access. Created empty by CDK - upload the real token.json contents manually "
                "after running the OAuth consent flow locally (see DEPLOY_AGENTCORE.md)."
            ),
            removal_policy=RemovalPolicy.DESTROY,
            secret_string_value=None,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                # Placeholder JSON; overwritten by the manual token upload step.
                # A generated value is required at creation time since Secret
                # cannot be created with a fixed empty/placeholder string via
                # secret_string_beta1/secret_string_value in this CDK version
                # without triggering a lint warning about literal secrets in code.
                secret_string_template='{"placeholder": true}',
                generate_string_key="_unused",
            ),
        )

        if execution_role_principal:
            # Grant read/write access to the token secret via a resource
            # policy statement (rather than grant_read()/grant_write(),
            # which fail with "KeyProvidedCrossAccountAccess" for a bare
            # ArnPrincipal - CDK can't confirm it's same-account without an
            # explicit account on the principal, even though it is here).
            self.google_token_secret.add_to_resource_policy(
                iam.PolicyStatement(
                    actions=["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"],
                    principals=[execution_role_principal],
                    resources=["*"],
                )
            )

        CfnOutput(
            self,
            "AgentSessionsBucketName",
            value=self.sessions_bucket.bucket_name,
            description="Set this as AGENT_SESSIONS_BUCKET in the AgentCore Runtime deployment.",
        )
        CfnOutput(
            self,
            "GoogleTokenSecretArn",
            value=self.google_token_secret.secret_arn,
            description=(
                "Set this as GOOGLE_TOKEN_SECRET_ID in the AgentCore Runtime deployment. "
                "Remember to upload the real token.json contents to this secret before "
                "invoking the deployed agent - see DEPLOY_AGENTCORE.md."
            ),
        )
        CfnOutput(
            self,
            "GoogleTokenSecretName",
            value=self.google_token_secret.secret_name,
            description="Secret name, usable instead of the ARN for GOOGLE_TOKEN_SECRET_ID.",
        )
