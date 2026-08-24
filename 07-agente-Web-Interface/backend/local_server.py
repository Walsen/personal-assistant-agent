"""Local dev server for the web chat backend.

Runs the same proxy logic as the deployed Lambda (agent_client.py) behind a
plain http.server, so the frontend can be developed and tested against the
real deployed AgentCore agent without deploying anything to AWS. Uses your
local AWS credentials (the `walsen` profile, same as the rest of this repo)
to call InvokeAgentRuntime directly.

Usage:
    export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:...:runtime/...
    uv run python local_server.py

Then open frontend/index.html in a browser (it defaults to
http://localhost:8000 as the backend URL - see frontend/config.js).
"""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

import boto3

from agent_client import invoke_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
PORT = int(os.environ.get("PORT", "8000"))

_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)


class ChatHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json(204, {})

    def do_POST(self) -> None:
        if self.path != "/chat":
            self._send_json(404, {"status": "error", "error": "Not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError as e:
            self._send_json(400, {"status": "error", "error": f"Invalid JSON: {e}"})
            return

        try:
            result = invoke_agent(AGENT_RUNTIME_ARN, body, client=_client)
        except Exception:
            logger.exception("Agent invocation failed")
            self._send_json(500, {"status": "error", "error": "Agent invocation failed. Check server logs."})
            return

        self._send_json(200, result)

    def log_message(self, format, *args):  # noqa: A002 - matches BaseHTTPRequestHandler signature
        logger.info(format, *args)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), ChatHandler)
    logger.info("Local chat backend listening on http://127.0.0.1:%s (agent=%s)", PORT, AGENT_RUNTIME_ARN)
    server.serve_forever()
