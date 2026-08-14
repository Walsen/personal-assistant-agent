# 🤖 Personal Assistant AI Agent

A personal assistant AI agent built with [Strands Agents SDK](https://strandsagents.com/) that can read Gmail, manage Google Calendar, and create/edit Google Docs. Designed for deployment on [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html).

## 🎓 Workshop

This project is the companion code for the **"Building a Personal Assistant AI Agent with Strands Agents & AgentCore"** workshop. See the [`docs/`](docs/) directory for the full workshop materials organized by module.

## ✨ Features

- 📧 **Gmail** — Read and send emails
- 📅 **Google Calendar** — List upcoming events and create new ones
- 📄 **Google Docs** — Create, read, and update documents
- 🚀 **AgentCore Ready** — Deploy to serverless AWS infrastructure

## 🛠️ Tools

| Tool | Description |
|------|-------------|
| `read_emails` | Search and read Gmail messages |
| `send_email` | Send emails via Gmail |
| `list_events` | List upcoming calendar events |
| `create_event` | Create new calendar events |
| `create_document` | Create new Google Docs |
| `get_document` | Read Google Doc content |
| `update_document` | Append text to existing docs |

## 📋 Prerequisites

- Python 3.10+
- AWS account with Bedrock access (Claude Sonnet model enabled)
- Google account with Gmail
- Google Cloud project with APIs enabled

## 🚀 Quick Start

```bash
# Clone the repo
git clone git@github.com:Walsen/personal-assistant-agent.git
cd personal-assistant-agent

# Install dependencies
pip install -r requirements.txt

# Set up Google OAuth (see docs/module-02-google-oauth-setup.md)
# Place your credentials.json in the project root

# Run the agent
python agent.py
```

## 📁 Project Structure

```
personal-assistant-agent/
├── tools/
│   ├── __init__.py
│   ├── auth.py              # Shared OAuth2 credential helper
│   ├── gmail_tools.py       # read_emails, send_email
│   ├── calendar_tools.py    # list_events, create_event
│   └── docs_tools.py        # create_document, get_document, update_document
├── docs/                     # Workshop documentation (by module)
├── agent.py                  # Main agent (local interactive mode)
├── agent_agentcore.py        # AgentCore deployment entrypoint
├── Dockerfile                # ARM64 container for AgentCore
├── requirements.txt
└── README.md
```

## 📚 Workshop Documentation

| Module | Topic | Duration |
|--------|-------|----------|
| [Module 1](docs/module-01-intro-agents-strands.md) | Intro to AI Agents & Strands SDK | 30 min |
| [Module 2](docs/module-02-google-oauth-setup.md) | Google Cloud & OAuth2 Setup | 30 min |
| [Module 3](docs/module-03-building-custom-tools.md) | Building Custom Tools | 60 min |
| [Module 4](docs/module-04-assembling-the-agent.md) | Assembling the Personal Assistant | 30 min |
| [Module 5](docs/module-05-testing-iterating.md) | Testing & Iterating | 20 min |
| [Module 6](docs/module-06-deploying-agentcore.md) | Deploying to AgentCore | 30 min |
| [Module 7](docs/module-07-advanced-memory-harness.md) | **Advanced:** Memory, Storage & Harness | 45 min |
| [Module 8](docs/module-08-multi-agent-systems.md) | **Advanced:** Multi-Agent Systems | 45 min |

## 📄 License

MIT
