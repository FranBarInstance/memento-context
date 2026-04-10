# memento-context

Memento Context is a Model Context Protocol (MCP) server that provides persistent memory capabilities for AI assistants. It allows AI models to save, retrieve, and manage scoped context across different sessions and projects safely on your local machine.

## What is Memento Context?

**Memento Context** is not a traditional knowledge base or a long-term file storage system. Instead, it is designed as a **"living context"** layer for AI assistants.

### The Concept
A "memento" is a short, high-impact note—usually no more than a few lines—that captures preferences, rules, or specific project context. These notes are automatically injected into the AI's instructions at the start of every session.

*   **It IS**: A place for "Always use TypeScript strict mode", "I prefer concise Spanish responses", or "This project uses FastAPI".
*   **It IS NOT**: A heavy knowledge base designed for complex semantic search or RAG. While future versions may include conversation logging, the focus remains on direct, deterministic context injection rather than large-scale document retrieval.

By keeping memories small and scoped, they remain relevant and don't overwhelm the AI's reasoning capacity.

## Features

- Global Memory: Store preferences, rules, and facts about the user that persist across all interactions.
- Repository Memory: Store project-specific context, conventions, and architectural decisions automatically scoped to the current working directory.
- Intelligent Hashing: Avoids path collisions natively by generating safe repository folder IDs.
- Deterministic Storage: Saves everything locally using a scalable JSON Envelope format.

## Installation

You can install `memento-context` seamlessly from this repository code using `pip` or preferably `pipx` (to keep dependencies strictly isolated while exposing the executable globally).

```bash
# Recommended approach for CLI tools
pipx install .

# Or using standard pip
pip install .
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
- `delete_memento`: Completely removes a recognized memory.
- `move_memento`: Recategorizes a memory, transferring it seamlessly between repository scope and global scope.

## Storage Architecture

All AI memories are saved inside the user home directory (`~/.memento-context/`).
- Global records: `~/.memento-context/global/mementos.json`
- Repository records: `~/.memento-context/repos/<slug>__<hash>/mementos.json`

## License

This project is licensed under the MIT License.
See: https://github.com/FranBarInstance/memento-context
