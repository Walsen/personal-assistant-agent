/**
 * Chat UI for the personal assistant agent.
 *
 * Talks only to the backend proxy configured in config.js
 * (window.AGENT_CHAT_API_URL) - never directly to AWS. The backend forwards
 * every request to the already-deployed AgentCore Runtime agent (see
 * backend/agent_client.py) and returns its response verbatim, plus a
 * session_id this script must echo back on every subsequent turn so the
 * agent keeps conversation history and can resolve pending confirmations
 * (e.g. delete_email) tied to that session.
 */

const messagesEl = document.getElementById("messages");
const interruptBanner = document.getElementById("interrupt-banner");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const newSessionBtn = document.getElementById("new-session-btn");

let sessionId = null;
let pendingInterrupts = null; // array from the last "interrupt" response, or null

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `message ${role}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

function addTypingIndicator() {
  const el = document.createElement("div");
  el.className = "typing-indicator";
  el.textContent = "Thinking...";
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

function extractText(message) {
  if (!message || !Array.isArray(message.content)) return "";
  return message.content
    .map((block) => block.text || "")
    .filter(Boolean)
    .join("\n");
}

function describeInterrupt(interrupt) {
  if (interrupt.name === "gmail-delete-approval") {
    const reason = interrupt.reason || {};
    return {
      title: "Confirm email deletion",
      detail: `From: ${reason.sender || "(unknown)"}\nSubject: ${reason.subject || "(no subject)"}`,
    };
  }
  return {
    title: interrupt.name || "Confirmation required",
    detail: JSON.stringify(interrupt.reason || {}, null, 2),
  };
}

function renderInterrupts(interrupts) {
  pendingInterrupts = interrupts;
  interruptBanner.innerHTML = "";
  interruptBanner.hidden = false;

  interrupts.forEach((interrupt) => {
    const { title, detail } = describeInterrupt(interrupt);

    const card = document.createElement("div");

    const titleEl = document.createElement("div");
    titleEl.className = "interrupt-title";
    titleEl.textContent = title;

    const detailEl = document.createElement("div");
    detailEl.className = "interrupt-detail";
    detailEl.textContent = detail;

    const actions = document.createElement("div");
    actions.className = "interrupt-actions";

    const confirmBtn = document.createElement("button");
    confirmBtn.className = "confirm-btn";
    confirmBtn.textContent = "Yes, proceed";
    confirmBtn.onclick = () => resolveInterrupt(interrupt.id, "y");

    const cancelBtn = document.createElement("button");
    cancelBtn.className = "cancel-btn";
    cancelBtn.textContent = "Cancel";
    cancelBtn.onclick = () => resolveInterrupt(interrupt.id, "n");

    actions.append(confirmBtn, cancelBtn);
    card.append(titleEl, detailEl, actions);
    interruptBanner.appendChild(card);
  });
}

function clearInterrupts() {
  pendingInterrupts = null;
  interruptBanner.hidden = true;
  interruptBanner.innerHTML = "";
}

async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function callBackend(body) {
  const requestBody = JSON.stringify({ ...body, session_id: sessionId });

  // CloudFront's Origin Access Control signs every request it forwards to
  // the Lambda Function URL origin (see infra/stacks/web_interface_stack.py)
  // using SigV4, which for POST requests requires the client to supply the
  // SHA256 hash of the body up front in x-amz-content-sha256. Without it,
  // CloudFront falls back to an unsigned payload, which Lambda's SigV4
  // validation rejects with a signature mismatch. See:
  // https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html
  const contentHash = await sha256Hex(requestBody);

  const response = await fetch(window.AGENT_CHAT_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-amz-content-sha256": contentHash,
    },
    body: requestBody,
  });

  const data = await response.json();
  if (!response.ok || data.status === "error") {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}

function handleAgentResponse(data) {
  sessionId = data.session_id || sessionId;

  if (data.status === "interrupt") {
    renderInterrupts(data.interrupts || []);
    return;
  }

  clearInterrupts();
  const text = extractText(data.message) || "(empty response)";
  addMessage("assistant", text);
}

async function sendPrompt(prompt) {
  addMessage("user", prompt);
  const typingEl = addTypingIndicator();
  sendBtn.disabled = true;

  try {
    const data = await callBackend({ prompt });
    handleAgentResponse(data);
  } catch (err) {
    addMessage("error", `Error: ${err.message}`);
  } finally {
    typingEl.remove();
    sendBtn.disabled = false;
  }
}

async function resolveInterrupt(interruptId, response) {
  const interrupt = (pendingInterrupts || []).find((i) => i.id === interruptId);
  clearInterrupts();
  addMessage("system", response === "y" ? "Confirmed." : "Cancelled.");

  const typingEl = addTypingIndicator();
  sendBtn.disabled = true;

  try {
    const data = await callBackend({
      interrupt_responses: [{ interrupt_id: interruptId, response }],
    });
    handleAgentResponse(data);
  } catch (err) {
    addMessage("error", `Error: ${err.message}`);
  } finally {
    typingEl.remove();
    sendBtn.disabled = false;
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const prompt = input.value.trim();
  if (!prompt) return;
  input.value = "";
  input.style.height = "auto";
  sendPrompt(prompt);
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

newSessionBtn.addEventListener("click", () => {
  sessionId = null;
  clearInterrupts();
  messagesEl.innerHTML = "";
  addMessage("system", "Started a new session.");
});

addMessage("system", "Ask about your email, calendar, or documents to get started.");
