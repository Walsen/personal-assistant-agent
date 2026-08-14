# AgentCore Runtime requires linux/arm64
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Copy dependency files
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY tools/ ./tools/
COPY agent_agentcore.py .

# AgentCore requires port 8080
EXPOSE 8080

# Run the AgentCore entrypoint
CMD ["python", "agent_agentcore.py"]
