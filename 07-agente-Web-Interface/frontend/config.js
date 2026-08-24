// Backend URL the frontend calls for /chat requests.
//
// Default: a relative path. Once deployed, the frontend is served by the
// same CloudFront distribution that also routes "/chat" to the backend
// Lambda (see infra/stacks/web_interface_stack.py), so a relative path
// always resolves to the right place with no CORS hop.
//
// Local development against local_server.py: temporarily change this to
// "http://127.0.0.1:8000/chat" (see README.md "Desarrollo local") - just
// remember to revert it before deploying, since this file is uploaded to
// S3 as-is.
window.AGENT_CHAT_API_URL = "/chat";
