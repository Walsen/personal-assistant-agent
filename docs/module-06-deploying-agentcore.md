# Module 6: Deploying to Amazon Bedrock AgentCore

**Duration:** 30 minutes

---

## 6.1 AgentCore Concepts (10 min)

### What is Amazon Bedrock AgentCore Runtime?

A **serverless runtime** purpose-built for deploying and scaling AI agents.

| Feature | Description |
|---------|-------------|
| **Serverless** | No infrastructure to manage |
| **Session Isolation** | Dedicated microVM per user session |
| **Auto-scaling** | Scales to thousands of sessions in seconds |
| **Pay-per-use** | Only pay for actual compute time |
| **Identity Integration** | Cognito, Entra ID, Okta, Google, GitHub OAuth |
| **Session Persistence** | State preserved across interactions |
| **Observability** | Built-in CloudWatch + ADOT tracing |

### Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ Your Agent   │────→│ Docker (ARM64)  │────→│ ECR              │
│ (Python)     │     │ Port 8080       │     │ (container store)│
└──────────────┘     └─────────────────┘     └──────────────────┘
                                                      │
                                                      ▼
                                             ┌──────────────────┐
                                             │ AgentCore Runtime│
                                             │ (microVM per     │
                                             │  session)        │
                                             └──────────────────┘
                                                      │
                                                      ▼
                                             ┌──────────────────┐
                                             │ invoke_agent_    │
                                             │ runtime() API    │
                                             └──────────────────┘
```

### Required Contract

Your container MUST expose:
- **`POST /invocations`** — Receives agent requests
- **`GET /ping`** — Health check (return 200)
- **Port 8080** — Always
- **Platform** — `linux/arm64`

---

## 6.2 Adapting for AgentCore (10 min)

### Install the SDK

```bash
pip install bedrock-agentcore
```

### The AgentCore Entrypoint (`agent_agentcore.py`)

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models.bedrock import BedrockModel
from tools.gmail_tools import read_emails, send_email
from tools.calendar_tools import list_events, create_event
from tools.docs_tools import create_document, get_document, update_document

app = BedrockAgentCoreApp()

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

agent = Agent(
    model=model,
    system_prompt="You are a personal assistant...",
    tools=[read_emails, send_email, list_events, create_event,
           create_document, get_document, update_document]
)

@app.entrypoint
def invoke(payload):
    result = agent(payload.get("prompt", "Hello"))
    return {"result": result.message}

if __name__ == "__main__":
    app.run()
```

### Testing Locally

```bash
python agent_agentcore.py

# In another terminal:
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are my unread emails?"}'
```

### Handling Credentials in Production

For the workshop (local testing): `credentials.json` + `token.json` in the container.

For production, consider:
- **Google Service Account** with domain-wide delegation
- **AWS Secrets Manager** for storing OAuth tokens
- **AgentCore Identity** for end-user auth flow

---

## 6.3 Deploy & Invoke (10 min)

### Option A: AgentCore CLI (Recommended for Workshop)

```bash
# Install the CLI
npm install -g @aws/agentcore

# Create a new project (interactive wizard)
agentcore create
cd myproject

# Test locally
agentcore dev

# Deploy to AWS
agentcore deploy

# Test the deployed agent
agentcore invoke
```

### Option B: Manual Docker + boto3 Deployment

#### Build the Docker Image

```bash
# Build for ARM64
docker buildx build --platform linux/arm64 -t personal-assistant:arm64 --load .

# Test locally
docker run --platform linux/arm64 -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" \
  -e AWS_REGION="us-east-1" \
  personal-assistant:arm64
```

#### Push to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name personal-assistant --region us-east-1

# Login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag personal-assistant:arm64 <account-id>.dkr.ecr.us-east-1.amazonaws.com/personal-assistant:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/personal-assistant:latest
```

#### Deploy via boto3

```python
import boto3

client = boto3.client('bedrock-agentcore-control', region_name="us-east-1")

response = client.create_agent_runtime(
    agentRuntimeName='personal-assistant',
    agentRuntimeArtifact={
        'containerConfiguration': {
            'containerUri': '<account-id>.dkr.ecr.us-east-1.amazonaws.com/personal-assistant:latest'
        }
    },
    networkConfiguration={"networkMode": "PUBLIC"},
    roleArn='arn:aws:iam::<account-id>:role/AgentRuntimeRole'
)

print(f"Agent Runtime ARN: {response['agentRuntimeArn']}")
```

#### Invoke the Deployed Agent

```python
import boto3
import json

client = boto3.client('bedrock-agentcore', region_name='us-east-1')

response = client.invoke_agent_runtime(
    agentRuntimeArn='arn:aws:bedrock-agentcore:us-east-1:<account-id>:runtime/personal-assistant-xxx',
    runtimeSessionId='session-123456789012345678901234567890123',  # Must be 33+ chars
    payload=json.dumps({"prompt": "What are my unread emails?"})
)

result = json.loads(response['response'].read())
print("Agent:", result)
```

---

## Bonus: Observability

### Enable CloudWatch Tracing

```bash
pip install aws-opentelemetry-distro>=0.10.1

# Run with auto-instrumentation
opentelemetry-instrument python agent_agentcore.py
```

### View Metrics
1. Open CloudWatch Console
2. Navigate to GenAI Observability
3. Find your agent service
4. View traces, latency, token usage

---

## Resources

- [AgentCore Runtime Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [Strands: Deploy to AgentCore (Python)](https://strandsagents.com/docs/user-guide/deploy/deploy_to_bedrock_agentcore/python/)
- [AgentCore CLI](https://github.com/aws/agentcore-cli)
- [AgentCore Runtime Permissions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
- [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
