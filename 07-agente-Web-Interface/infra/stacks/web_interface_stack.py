"""CDK stack for the personal assistant web chat interface.

Provisions everything needed to expose a browser-based chat client for the
agent already deployed in 06-agente-AgentCore-deploy, without touching that
agent or its runtime:

- AgentChatFunction: a Lambda (backend/handler.py) that proxies chat
  requests to the deployed AgentCore Runtime via boto3's
  invoke_agent_runtime, exposed through a public Function URL that is
  nonetheless only usable through CloudFront in practice: every request
  must carry a random shared-secret header (ORIGIN_VERIFY_HEADER) that
  only this stack's CloudFront distribution knows and injects - the
  handler rejects any request missing or mismatching it.
- FrontendBucket: a private S3 bucket holding the static frontend
  (frontend/index.html, app.js, styles.css, config.js), readable only by
  CloudFront via Origin Access Control - never public.
- A single CloudFront distribution fronting both: "/chat" routes to the
  Lambda Function URL (POST, no caching), everything else routes to the S3
  bucket (GET/HEAD, cached). This gives the browser one HTTPS origin with
  no CORS concerns for same-origin requests.

Everything here uses RemovalPolicy.DESTROY (S3 auto_delete_objects, no
retained CloudFront distributions) so `cdk destroy` fully tears the web
interface down, independent of the agent runtime/prerequisites stacks from
step 06.

Access control: the whole distribution (static frontend and /chat alike)
is gated by HTTP Basic Auth, enforced at the edge by a CloudFront Function
(see _build_basic_auth_function below) - requests without valid
credentials get a 401 before ever reaching S3 or the Lambda. This is a
lightweight, single-shared-credential control appropriate for a personal
demo, not a substitute for real per-user authentication (Cognito, an
identity provider, etc.) if this is ever shared beyond its owner.
"""

import base64
import secrets

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3_deployment
from constructs import Construct

# HTTP header CloudFront injects on every request it forwards to the chat
# Lambda's Function URL, and that the Lambda handler checks before doing
# any work (see backend/handler.py). This is the standard "restrict access
# to a custom origin" pattern AWS documents for ALBs/API Gateway/etc:
# https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/restrict-access-to-load-balancer.html
#
# It replaces CloudFront's built-in Origin Access Control (OAC) for this
# origin. OAC support for POST bodies against AWS_IAM-authenticated Lambda
# Function URLs turned out to be unreliable in practice (CloudFront's SigV4
# request signing for POST never reached the Lambda handler at all in
# testing, even after following AWS's documented x-amz-content-sha256
# workaround) - this is a known rough edge, not specific to this stack. A
# shared secret header sidesteps the whole SigV4/payload-hash problem.
ORIGIN_VERIFY_HEADER = "x-origin-verify"


class WebInterfaceStack(Stack):
    """Provisions the Lambda chat proxy, static frontend bucket, and the
    CloudFront distribution that fronts both.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agent_runtime_arn: str,
        basic_auth_username: str | None = None,
        basic_auth_password: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # HTTP Basic Auth credentials for the whole distribution (see
        # _build_basic_auth_function below). Pass both via CDK context
        # (-c basicAuthUsername=... -c basicAuthPassword=...) to pick your
        # own; otherwise a random password is generated and printed as a
        # stack output on deploy - copy it down, since it isn't stored
        # anywhere else and cdk deploy won't print it again on unrelated
        # future deploys unless this value changes.
        self.basic_auth_username = basic_auth_username or "admin"
        self.basic_auth_password = basic_auth_password or secrets.token_urlsafe(12)
        self._password_was_generated = basic_auth_password is None

        # Random per-deployment secret shared between CloudFront (as a
        # custom origin header, see the distribution below) and the Lambda
        # (which validates it - see backend/handler.py). Generated fresh on
        # every `cdk deploy` of a new stack instance; anyone without it
        # gets rejected before the handler does any work.
        origin_verify_secret = secrets.token_urlsafe(32)

        # --- Backend: Lambda proxy to the deployed AgentCore Runtime agent ---

        self.chat_function = lambda_.Function(
            self,
            "AgentChatFunction",
            runtime=lambda_.Runtime.PYTHON_3_14,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "AGENT_RUNTIME_ARN": agent_runtime_arn,
                "ORIGIN_VERIFY_SECRET": origin_verify_secret,
                # AWS_REGION is not set explicitly - it's a reserved Lambda
                # runtime environment variable, automatically provided by
                # Lambda itself (handler.py/agent_client.py already fall
                # back to it via os.environ.get("AWS_REGION", ...)).
                "ALLOWED_ORIGINS": "*",
            },
        )

        # bedrock-agentcore:InvokeAgentRuntime on the specific agent runtime
        # this stack was told about - not a wildcard resource, so this
        # function cannot invoke any other agent in the account.
        self.chat_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[agent_runtime_arn, f"{agent_runtime_arn}/*"],
            )
        )

        # NONE auth type (no SigV4/OAC) - access is instead restricted by
        # the shared-secret header CloudFront injects below, which the
        # handler validates on every request. See the ORIGIN_VERIFY_HEADER
        # comment above for why OAC was dropped for this origin.
        function_url = self.chat_function.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
        )

        # --- Frontend: private S3 bucket holding the static chat UI ---

        self.frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
        )

        # --- CloudFront: single distribution fronting both origins ---

        basic_auth_function = self._build_basic_auth_function()

        s3_origin = origins.S3BucketOrigin.with_origin_access_control(self.frontend_bucket)
        lambda_origin = origins.FunctionUrlOrigin(
            function_url,
            custom_headers={ORIGIN_VERIFY_HEADER: origin_verify_secret},
        )

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment="Personal assistant agent - web chat interface",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=basic_auth_function,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                    )
                ],
            ),
            additional_behaviors={
                "/chat": cloudfront.BehaviorOptions(
                    origin=lambda_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    function_associations=[
                        cloudfront.FunctionAssociation(
                            function=basic_auth_function,
                            event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                        )
                    ],
                )
            },
        )

        # --- Deploy the static frontend files to the bucket, invalidating
        # the CloudFront cache on every deploy so updates go live immediately ---

        s3_deployment.BucketDeployment(
            self,
            "FrontendDeployment",
            sources=[s3_deployment.Source.asset("../frontend")],
            destination_bucket=self.frontend_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )

        CfnOutput(
            self,
            "DistributionDomainName",
            value=f"https://{self.distribution.distribution_domain_name}",
            description="Open this URL in a browser to use the chat interface.",
        )
        CfnOutput(
            self,
            "ChatFunctionName",
            value=self.chat_function.function_name,
            description="Lambda function name, useful for tailing logs (aws logs tail).",
        )
        CfnOutput(
            self,
            "BasicAuthUsername",
            value=self.basic_auth_username,
            description="HTTP Basic Auth username required to access the site.",
        )
        if self._password_was_generated:
            CfnOutput(
                self,
                "BasicAuthPassword",
                value=self.basic_auth_password,
                description=(
                    "Auto-generated HTTP Basic Auth password required to access the site. "
                    "Not stored anywhere else - copy it now. To set your own instead, redeploy "
                    "with -c basicAuthPassword=<your-password>."
                ),
            )

    def _build_basic_auth_function(self) -> cloudfront.Function:
        """CloudFront Function (runs at the edge, before origin or cache
        lookup) that enforces HTTP Basic Auth on every request to this
        distribution. Requests without a matching Authorization header get
        an immediate 401 with a WWW-Authenticate challenge, which browsers
        turn into their native login prompt - no frontend code changes
        needed.
        """
        expected_auth_header = "Basic " + base64.b64encode(
            f"{self.basic_auth_username}:{self.basic_auth_password}".encode()
        ).decode()

        function_code = f"""
function handler(event) {{
    var request = event.request;
    var headers = request.headers;
    var expected = "{expected_auth_header}";

    if (!headers.authorization || headers.authorization.value !== expected) {{
        return {{
            statusCode: 401,
            statusDescription: "Unauthorized",
            headers: {{
                "www-authenticate": {{ value: 'Basic realm="Personal Assistant Agent"' }}
            }}
        }};
    }}

    return request;
}}
"""

        return cloudfront.Function(
            self,
            "BasicAuthFunction",
            code=cloudfront.FunctionCode.from_inline(function_code),
            runtime=cloudfront.FunctionRuntime.JS_2_0,
        )
