# memento-context

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-2024--11--05-orange.svg)](https://modelcontextprotocol.io/)

Memento Context is a Model Context Protocol (MCP) server that provides persistent memory capabilities for AI assistants. It allows AI models to save, retrieve, and manage scoped context across different sessions and projects safely on your local machine.

## What is Memento Context?

**Memento Context** is not a traditional knowledge base or a long-term file storage system. Instead, it is designed as a **"living context"** layer for AI assistants.

### The Concept
A "memento" is a short, high-impact note—usually no more than a few lines—that captures preferences, rules, or specific project context. These notes are automatically injected into the AI's instructions at the start of every session.

*   **It IS**: A place for "Always use TypeScript strict mode", "I prefer concise Spanish responses", or "This project uses FastAPI".
*   **It IS NOT**: A heavy knowledge base designed for complex semantic search or RAG. Conversations can be saved as explicit attachments to a memento, but the core model remains direct, deterministic context injection rather than large-scale document retrieval.

By keeping memories small and scoped, they remain relevant and don't overwhelm the AI's reasoning capacity.

### The Zero-Dependency Advantage
Unlike most MCP servers, `memento-context` is built using **Zero External Dependencies**. It uses only the Python standard library to implement the JSON-RPC protocol. This ensures:
- **Instant Load Times**: No heavy package analysis at startup.
- **Maximum Portability**: Runs anywhere Python is available without `pip install` headaches.
- **High Security**: Zero risk of supply chain attacks from third-party libraries.

## How it Works

The interaction with Memento Context follows a simple, automated lifecycle:

1.  **Session Bootstrap**: At the start of every chat, the assistant calls `init_memento`. This automatically loads all relevant global and repository-scoped notes into its active context, so it "remembers" you and your project immediately.
2.  **Natural Learning**: As you talk, the assistant is trained to recognize important information—like a new coding preference or a project-specific rule—and will offer to save it using `save_memento`.
3.  **Explicit Instructions**: You have full control. You can explicitly say *"Remember that I prefer using Vitest for testing"* or *"Save a note about our deployment workflow"*, and the assistant will persist that information for all future sessions.
4.  **Conversation Attachments**: On explicit request only, the assistant can save a full conversation or summary with `save_conversation`, and later attach related files with `save_memento_attachments`. These attachments are stored alongside the memento and can be retrieved with `get_memento_attachments` when the extra detail is needed.


## Features

- Global Memory: Store preferences, rules, and facts about the user that persist across all interactions.
- Repository Memory: Store project-specific context, conventions, and architectural decisions automatically scoped to the current working directory.
- Conversation Attachments: Save full conversations, summaries, and related files as attachments linked to a memento, only when explicitly requested by the user.
- Intelligent Hashing: Avoids path collisions natively by generating safe repository folder IDs.
- Deterministic Storage: Saves everything locally using a scalable JSON Envelope format.

## Installation

> [!NOTE]
> `memento-context` is currently in early development. Standard installation via PyPI (`pip install memento-context`) will be available starting with the first stable release.

### Quick Install (Recommended)

You can install the server in a single command using our setup scripts. This clones the repository into a local hidden folder and installs the executable globally.

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/FranBarInstance/memento-context/main/scripts/install.sh | bash
```

**Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/FranBarInstance/memento-context/main/scripts/install.ps1" -OutFile install.ps1; .\install.ps1
```

### Manual Install from Source

If you prefer to install manually from the source code:

```bash
git clone https://github.com/FranBarInstance/memento-context.git
cd memento-context
pipx install .  # Recommended approach
# or: pip install .
```

For developmental purposes, use the editable mode:
```bash
pipx install -e .
```

## Running the Server

Because it is defined in the `pyproject.toml` scripts, the installation automatically creates a globally available executable. You can start the MCP stdio standard process anywhere by simply calling:

```bash
memento-context
```

## IDE / MCP Client Configuration

To use `memento-context` with an MCP-compatible client (like Claude Desktop or MCP VSCode plugins), configure the client's `mcp.json` settings file to connect to the executable:

```json
{
  "mcpServers": {
    "memento-context": {
      "command": "memento-context",
      "args": []
    }
  }
}
```

## Available MCP Tools

The server exposes the following tools to the AI capabilities out of the box:
- `init_memento`: Loads behavior instructions and bootstraps the context state.
- `get_mementos`: Fetches specific memory environments (global or repo).
- `save_memento`: Saves a new memory string into a target scope.
- `save_conversation`: Saves a conversation or summary as a memento with attachment files. Intended only for explicit user requests.
- `save_memento_attachments`: Copies one or more local files into the attachment directory of an existing memento.
- `get_memento_attachments`: Reads the attachment files associated with a specific memento.
- `delete_memento`: Completely removes a recognized memory.
- `move_memento`: Recategorizes a memory, transferring it seamlessly between repository scope and global scope.

## Storage Architecture

All AI memories are saved inside the user home directory (`~/.memento-context/`).
- Global records: `~/.memento-context/global/mementos.json`
- Repository records: `~/.memento-context/repos/<slug>__<hash>/mementos.json`

When a memento includes attachments, the server creates a sibling directory named `<memento_id>_attachments/` next to the corresponding `mementos.json` file. That directory may contain:
- `conversation.md` for a full saved conversation
- `summary.md` for a shorter narrative summary
- Any additional files copied with `save_memento_attachments`

Example layout:

```text
~/.memento-context/
├── global/
│   ├── mementos.json
│   └── memento_2026-04-10_abc12345_attachments/
│       ├── conversation.md
│       └── summary.md
└── repos/
    └── my-project__a1b2c3d4e5/
        ├── mementos.json
        └── memento_2026-04-10_def67890_attachments/
            ├── conversation.md
            └── architecture-notes.md
```

## License

This project is licensed under the MIT License.

See: https://github.com/FranBarInstance/memento-context
