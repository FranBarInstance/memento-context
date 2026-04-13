#!/usr/bin/env python3
"""
server.py - memento-context MCP server
Implements MCP server for persistent global and repository-scoped mementos.

See licence: https://github.com/FranBarInstance/memento-context
"""
import datetime
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --- paths ---
SCRIPT_DIR = Path(__file__).resolve().parent
TOOLS_FILE = SCRIPT_DIR / "tools.json"
BEHAVIOR_FILE = SCRIPT_DIR / "behavior.md"
MEMORY_HOME = Path.home() / ".memento-context"
GLOBAL_MEMENTOS_FILE = MEMORY_HOME / "global" / "mementos.json"
REPOS_DIR = MEMORY_HOME / "repos"

VALID_SCOPES = {"global", "repo"}


# ---------------------------------------------------------------------------
# Storage layer — paths, serialisation, repo metadata
# ---------------------------------------------------------------------------

class MementoStorage:
    """Handles all filesystem I/O for global and repository-scoped mementos."""

    def __init__(self, active_repo_path: Optional[str] = None) -> None:
        self.active_repo_path = active_repo_path

    def current_repo_path(self) -> str:
        """Return the canonical workspace path used as repository scope."""
        if self.active_repo_path:
            return str(Path(self.active_repo_path).resolve())
        return str(Path.cwd().resolve())

    def repo_key(self, repo_path: str) -> str:
        """Build a stable directory name for a repository-scoped memory store."""
        repo = Path(repo_path)
        slug = "".join(
            ch.lower() if ch.isalnum() else "-"
            for ch in repo.name.strip()
        ).strip("-") or "repo"
        digest = hashlib.sha1(repo_path.encode("utf-8")).hexdigest()[:10]
        return f"{slug}__{digest}"

    def repo_dir(self, repo_path: Optional[str] = None) -> Path:
        """Return the storage directory for the current or provided repository."""
        resolved_path = str(Path(repo_path or self.current_repo_path()).resolve())
        return REPOS_DIR / self.repo_key(resolved_path)

    def repo_mementos_file(self, repo_path: Optional[str] = None) -> Path:
        """Return the mementos file path for the current or provided repository."""
        return self.repo_dir(repo_path) / "mementos.json"

    def repo_meta_file(self, repo_path: Optional[str] = None) -> Path:
        """Return the metadata file path for the current or provided repository."""
        return self.repo_dir(repo_path) / "meta.json"

    def ensure_repo_metadata(self, repo_path: Optional[str] = None) -> None:
        """Persist repo metadata so scoped memory remains understandable on disk."""
        resolved_path = repo_path or self.current_repo_path()
        meta_file = self.repo_meta_file(resolved_path)
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "repo_path": resolved_path,
            "repo_name": Path(resolved_path).name,
            "repo_key": self.repo_key(resolved_path),
            "updated": datetime.date.today().isoformat(),
        }
        meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    def load_json_file(self, path: Path, label: str) -> List[Dict[str, Any]]:
        """Load JSON enveloped mementos from disk, wrapping older plain lists."""
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in {label}: {error}") from error

        # Backward compatibility for old flat array
        if isinstance(data, list):
            return data

        if not isinstance(data, dict) or "mementos" not in data:
            raise ValueError(f"Invalid JSON in {label}: expected enveloped mementos")

        return data.get("mementos", [])

    def save_json_file(self, path: Path, data: List[Dict[str, Any]]) -> None:
        """Persist mementos to disk wrapped in a versioned envelope."""
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "version": "1.0",
            "updated_at": datetime.datetime.now().astimezone().isoformat(),
            "mementos": data,
        }
        path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False))

    def load_global_mementos(self) -> List[Dict[str, Any]]:
        """Load all global mementos."""
        return self.load_json_file(GLOBAL_MEMENTOS_FILE, "global mementos")

    def save_global_mementos(self, mementos: List[Dict[str, Any]]) -> None:
        """Persist all global mementos."""
        self.save_json_file(GLOBAL_MEMENTOS_FILE, mementos)

    def load_repo_mementos(self, repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load all repository-scoped mementos."""
        resolved_path = repo_path or self.current_repo_path()
        self.ensure_repo_metadata(resolved_path)
        return self.load_json_file(
            self.repo_mementos_file(resolved_path),
            f"repo mementos for {resolved_path}",
        )

    def save_repo_mementos(
        self, mementos: List[Dict[str, Any]], repo_path: Optional[str] = None
    ) -> None:
        """Persist all repository-scoped mementos."""
        resolved_path = repo_path or self.current_repo_path()
        self.ensure_repo_metadata(resolved_path)
        self.save_json_file(self.repo_mementos_file(resolved_path), mementos)

    def persist_mementos(
        self,
        scope: str,
        mementos: List[Dict[str, Any]],
        repo_path: Optional[str] = None,
    ) -> None:
        """Persist a full memento collection for the provided scope."""
        if scope == "global":
            self.save_global_mementos(mementos)
        else:
            self.save_repo_mementos(mementos, repo_path)

    def get_attachments_dir(
        self,
        memento: Dict[str, Any],
        dir_name: str,
        create: bool = False,
    ) -> Path:
        """Resolve the attachment directory for a stored memento."""
        scope = memento["scope"]
        if scope == "global":
            attachments_dir = GLOBAL_MEMENTOS_FILE.parent / dir_name
        else:
            repo_path = memento.get("repo_path") or self.current_repo_path()
            attachments_dir = self.repo_mementos_file(repo_path).parent / dir_name
        if create:
            attachments_dir.mkdir(parents=True, exist_ok=True)
        return attachments_dir

    def write_attachments(
        self,
        attachments_dir: Path,
        conversation: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> List[str]:
        """Write standard conversation attachments and return created filenames."""
        attachments_dir.mkdir(parents=True, exist_ok=True)
        created: List[str] = []
        if conversation is not None:
            (attachments_dir / "conversation.md").write_text(conversation)
            created.append("conversation.md")
        if summary is not None:
            (attachments_dir / "summary.md").write_text(summary)
            created.append("summary.md")
        return created

    def copy_files_to_attachments(
        self, attachments_dir: Path, paths: List[str]
    ) -> List[str]:
        """Copy files into an attachments directory, returning result lines."""
        results = []
        for raw_path in paths:
            if not isinstance(raw_path, str):
                raise ValueError("each path must be a string")
            source = Path(raw_path)
            if not source.is_absolute():
                raise ValueError(f"path must be absolute: {raw_path}")
            if not source.exists() or not source.is_file():
                results.append(f"  ✗ {source.name} — file not found")
                continue
            destination = attachments_dir / source.name
            shutil.copy2(source, destination)
            results.append(f"  ✓ {source.name} (copied from {source})")
        return results

    def read_attachments(self, attachments_dir: Path, memento_id: str) -> str:
        """Read all files in an attachments directory and return formatted text."""
        if not attachments_dir.exists() or not attachments_dir.is_dir():
            raise ValueError(f"Attachments directory not found for memento: {memento_id}")
        files = sorted(path for path in attachments_dir.iterdir() if path.is_file())
        if not files:
            raise ValueError(f"No attachments found for memento: {memento_id}")
        sections = [
            f"## Attachments for {memento_id}",
            f"(folder: {attachments_dir.name}/)",
        ]
        for file_path in files:
            sections.append(f"\n### {file_path.name}")
            sections.append(file_path.read_text())
        return "\n".join(sections)


# ---------------------------------------------------------------------------
# Domain layer — business logic, validation, formatting
# ---------------------------------------------------------------------------

class MementoRepository:
    """Manages memento lifecycle: build, validate, find, format and mutate."""

    def __init__(self, storage: MementoStorage) -> None:
        self.storage = storage

    # --- validation ---------------------------------------------------------

    def validate_scope(self, scope: Any) -> str:
        """Validate global vs repository scope."""
        if not isinstance(scope, str) or scope not in VALID_SCOPES:
            raise ValueError("Invalid scope: expected 'global' or 'repo'")
        return scope

    def validate_expires(self, expires: Any) -> str:
        """Validate and normalize the expires field."""
        if expires is None or expires == "never":
            return "never"
        if not isinstance(expires, str):
            raise ValueError("expires must be a string (YYYY-MM-DD) or 'never'")
        try:
            datetime.date.fromisoformat(expires)
        except ValueError as error:
            raise ValueError(
                f"Invalid expires '{expires}':"
                " expected 'never' or a date in YYYY-MM-DD format"
            ) from error
        return expires

    # --- queries ------------------------------------------------------------

    def is_active(self, memento: Dict[str, Any], today: str) -> bool:
        """Return whether a memento should be injected into active context."""
        expires = memento.get("expires")
        if not expires or expires == "never":
            return True
        not_a_date = (
            not isinstance(expires, str)
            or len(expires) != 10
            or expires[4] != "-"
            or expires[7] != "-"
        )
        if not_a_date:
            return False
        return expires >= today

    def get_active_global_mementos(self) -> List[Dict[str, Any]]:
        """Return non-expired global mementos."""
        today = datetime.date.today().isoformat()
        return [m for m in self.storage.load_global_mementos() if self.is_active(m, today)]

    def get_active_repo_mementos(self, repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return non-expired repo mementos."""
        today = datetime.date.today().isoformat()
        return [m for m in self.storage.load_repo_mementos(repo_path) if self.is_active(m, today)]

    def find_memento(self, memento_id: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """Locate a memento in global or repository storage."""
        global_mementos = self.storage.load_global_mementos()
        for memento in global_mementos:
            if memento["id"] == memento_id:
                return "global", global_mementos, memento

        repo_mementos = self.storage.load_repo_mementos()
        for memento in repo_mementos:
            if memento["id"] == memento_id:
                return "repo", repo_mementos, memento

        raise ValueError(f"Memento not found: {memento_id}")

    # --- formatting ---------------------------------------------------------

    def format_memento_list(self, title: str, mementos: List[Dict[str, Any]]) -> str:
        """Render a titled memento section for the model."""
        if not mementos:
            return f"## {title}\nNo active mementos."
        lines = [
            f"- [{m.get('id', '?')}] {m.get('text', '')} (expires: {m.get('expires', 'never')})"
            for m in mementos
        ]
        return "\n".join([f"## {title}", *lines])

    def format_active_context(self) -> str:
        """Render both global and repository mementos for session bootstrap."""
        repo_path = self.storage.current_repo_path()
        repo_name = Path(repo_path).name
        return "\n\n".join([
            self.format_memento_list("Global Mementos", self.get_active_global_mementos()),
            self.format_memento_list(
                f"Repository Mementos ({repo_name})",
                self.get_active_repo_mementos(repo_path),
            ),
        ])

    # --- mutations ----------------------------------------------------------

    def attachments_dir_name(self, memento_id: str) -> str:
        """Return the standard folder name used for a memento attachments directory."""
        return f"{memento_id}_attachments"

    def build_memento(self, args: Dict[str, Any], scope: str) -> Dict[str, Any]:
        """Build a stored memento payload."""
        memento: Dict[str, Any] = {
            "id": f"memento_{datetime.date.today()}_{uuid.uuid4().hex[:8]}",
            "scope": scope,
            "text": args["text"],
            "tags": args.get("tags", []),
            "expires": self.validate_expires(args.get("expires")),
            "created": datetime.date.today().isoformat(),
        }
        if scope == "repo":
            repo_path = self.storage.current_repo_path()
            memento["repo_path"] = repo_path
            memento["repo_name"] = Path(repo_path).name
        if args.get("conversation") is not None or args.get("summary") is not None:
            memento["attachments"] = self.attachments_dir_name(memento["id"])
        return memento

    def persist_memento(self, memento: Dict[str, Any]) -> None:
        """Save a memento into the appropriate storage scope."""
        scope = self.validate_scope(memento["scope"])
        if scope == "global":
            mementos = self.storage.load_global_mementos()
            mementos.append(memento)
            self.storage.save_global_mementos(mementos)
            return
        repo_path = str(memento["repo_path"])
        mementos = self.storage.load_repo_mementos(repo_path)
        mementos.append(memento)
        self.storage.save_repo_mementos(mementos, repo_path)

    def remove_memento(self, memento_id: str) -> Tuple[str, Dict[str, Any]]:
        """Delete a memento from its current store and return its original payload."""
        scope, mementos, target = self.find_memento(memento_id)
        filtered = [m for m in mementos if m["id"] != memento_id]
        repo_path = target.get("repo_path") if scope == "repo" else None
        self.storage.persist_mementos(scope, filtered, repo_path)
        return scope, target


# ---------------------------------------------------------------------------
# Protocol layer — MCP stdio server, JSON-RPC dispatch, tool handlers
# ---------------------------------------------------------------------------

class MementoServer:
    """Stateful MCP stdio server. Delegates logic to MementoRepository."""

    def __init__(self) -> None:
        self.mementos_loaded = False
        self.storage = MementoStorage()
        self.repo = MementoRepository(self.storage)
        self.handlers = {
            "init_memento": self.handle_init_memento,
            "get_mementos": self.handle_get_mementos,
            "save_memento": self.handle_save_memento,
            "save_conversation": self.handle_save_conversation,
            "save_memento_attachments": self.handle_save_memento_attachments,
            "get_memento_attachments": self.handle_get_memento_attachments,
            "delete_memento": self.handle_delete_memento,
            "move_memento": self.handle_move_memento,
        }

    def load_tools(self) -> List[Dict[str, Any]]:
        """Load tool definitions from tools.json file."""
        if not TOOLS_FILE.exists():
            raise FileNotFoundError(f"tools.json not found at {TOOLS_FILE}")
        try:
            return json.loads(TOOLS_FILE.read_text())
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in tools.json: {error}") from error

    def load_behavior(self) -> str:
        """Load AI behavior instructions for session bootstrap."""
        if not BEHAVIOR_FILE.exists():
            raise FileNotFoundError(f"behavior.md not found at {BEHAVIOR_FILE}")
        return BEHAVIOR_FILE.read_text()

    def mark_context_loaded(self, source: str) -> None:
        """Mark session context as available and emit a debug log."""
        self.mementos_loaded = True
        print(f"[memento-context] {source} executed. Context loaded.", file=sys.stderr)

    def require_mementos_loaded(self) -> None:
        """Ensure session context was previously loaded in this session."""
        if not self.mementos_loaded:
            raise RuntimeError(
                "Memory not loaded. Call init_memento first, then retry."
            )

    # --- tool handlers ------------------------------------------------------

    def handle_init_memento(self, args: Dict[str, Any]) -> str:
        """Handler for init_memento tool: returns behavior plus active mementos."""
        repo_path = args.get("repo_path")
        if repo_path:
            self.storage.active_repo_path = repo_path

        behavior = self.load_behavior().strip()
        active_context = self.repo.format_active_context()
        self.mark_context_loaded("init_memento")
        return "\n\n".join(["## Behavior", behavior, active_context])

    def handle_get_mementos(self, args: Dict[str, Any]) -> str:
        """Handler for get_mementos tool: returns active mementos by scope."""
        scope = args.get("scope", "all")
        if scope not in {"all", "global", "repo"}:
            raise ValueError("Invalid scope: expected 'all', 'global', or 'repo'")

        sections: List[str] = []
        if scope in {"all", "global"}:
            sections.append(
                self.repo.format_memento_list(
                    "Global Mementos",
                    self.repo.get_active_global_mementos(),
                )
            )
        if scope in {"all", "repo"}:
            repo_name = Path(self.storage.current_repo_path()).name
            sections.append(
                self.repo.format_memento_list(
                    f"Repository Mementos ({repo_name})",
                    self.repo.get_active_repo_mementos(),
                )
            )

        self.mark_context_loaded("get_mementos")
        return "\n\n".join(sections)

    def handle_save_memento(self, args: Dict[str, Any]) -> str:
        """Handler for save_memento tool: stores a new scoped memento entry."""
        self.require_mementos_loaded()
        scope = self.repo.validate_scope(args.get("scope"))
        memento = self.repo.build_memento(args, scope)
        self.repo.persist_memento(memento)
        return f"Memento saved: {memento['id']} ({scope})"

    def handle_save_conversation(self, args: Dict[str, Any]) -> str:
        """Handler for save_conversation tool: stores a memento with attachments."""
        self.require_mementos_loaded()
        scope = self.repo.validate_scope(args.get("scope"))
        conversation = args.get("conversation")
        summary = args.get("summary")
        if conversation is None and summary is None:
            raise ValueError(
                "save_conversation requires at least one of 'conversation' or 'summary'"
            )
        if conversation is not None and not isinstance(conversation, str):
            raise ValueError("conversation must be a string")
        if summary is not None and not isinstance(summary, str):
            raise ValueError("summary must be a string")

        memento = self.repo.build_memento(args, scope)
        dir_name = self.repo.attachments_dir_name(memento["id"])
        attachments_dir = self.storage.get_attachments_dir(memento, dir_name, create=True)
        created = self.storage.write_attachments(
            attachments_dir, conversation=conversation, summary=summary
        )
        self.repo.persist_memento(memento)
        return (
            f"Conversation saved: {memento['id']} ({scope})"
            f" — {len(created)} attachment(s) in {attachments_dir.name}/"
        )

    def handle_save_memento_attachments(self, args: Dict[str, Any]) -> str:
        """Handler for save_memento_attachments tool: copies files into a memento."""
        self.require_mementos_loaded()
        paths = args.get("paths")
        if not isinstance(paths, list) or not paths:
            raise ValueError("paths must be a non-empty array of absolute file paths")

        scope, mementos, memento = self.repo.find_memento(args["id"])
        if "attachments" not in memento:
            memento["attachments"] = self.repo.attachments_dir_name(memento["id"])
            repo_path = memento.get("repo_path") if scope == "repo" else None
            self.storage.persist_mementos(scope, mementos, repo_path)

        dir_name = memento["attachments"]
        attachments_dir = self.storage.get_attachments_dir(memento, dir_name, create=True)
        results = [f"Attachments added to {memento['id']}:"]
        results += self.storage.copy_files_to_attachments(attachments_dir, paths)
        return "\n".join(results)

    def handle_get_memento_attachments(self, args: Dict[str, Any]) -> str:
        """Handler for get_memento_attachments tool: returns attachment contents."""
        self.require_mementos_loaded()
        _, _, memento = self.repo.find_memento(args["id"])
        if "attachments" not in memento:
            raise ValueError(f"Memento has no attachments: {args['id']}")

        dir_name = memento["attachments"]
        attachments_dir = self.storage.get_attachments_dir(memento, dir_name)
        return self.storage.read_attachments(attachments_dir, args["id"])

    def handle_delete_memento(self, args: Dict[str, Any]) -> str:
        """Handler for delete_memento tool: removes a memento by given id."""
        self.require_mementos_loaded()
        original_scope, _ = self.repo.remove_memento(args["id"])
        return f"Memento deleted: {args['id']} ({original_scope})"

    def handle_move_memento(self, args: Dict[str, Any]) -> str:
        """Handler for move_memento tool: changes a memento scope."""
        self.require_mementos_loaded()
        target_scope = self.repo.validate_scope(args.get("target_scope"))
        original_scope, _, memento = self.repo.find_memento(args["id"])

        if original_scope == target_scope:
            return f"Memento unchanged: {args['id']} already in {target_scope}"

        self.repo.remove_memento(args["id"])

        moved = dict(memento)
        moved["scope"] = target_scope
        if target_scope == "global":
            moved.pop("repo_path", None)
            moved.pop("repo_name", None)
        else:
            repo_path = self.storage.current_repo_path()
            moved["repo_path"] = repo_path
            moved["repo_name"] = Path(repo_path).name

        self.repo.persist_memento(moved)
        return f"Memento moved: {args['id']} ({original_scope} -> {target_scope})"

    # --- MCP protocol -------------------------------------------------------

    def respond(self, obj: Dict[str, Any]) -> None:
        """Send JSON response over stdout following MCP protocol."""
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()

    def respond_error(self, req_id: Any, code: int, message: str) -> None:
        """Send a JSON-RPC error response."""
        self.respond({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        })

    def handle_initialize(self, req_id: Any) -> None:
        """Handle MCP initialize request."""
        self.mementos_loaded = False
        if req_id is None:
            return
        self.respond({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "memento-context", "version": "0.1.0"},
            },
        })

    def handle_tools_list(self, req_id: Any) -> None:
        """Handle MCP tools/list request."""
        if req_id is None:
            return
        try:
            tools = self.load_tools()
            self.respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tools},
            })
        except Exception as error:  # pylint: disable=broad-exception-caught
            self.respond_error(req_id, -32000, f"{type(error).__name__}: {error}")

    def handle_tools_call(self, req: Dict[str, Any], req_id: Any) -> None:
        """Handle MCP tools/call request."""
        params = req.get("params")
        if not isinstance(params, dict):
            self.respond_error(req_id, -32602, "Invalid params: missing params object")
            return

        tool = params.get("name")
        if not isinstance(tool, str) or not tool:
            self.respond_error(req_id, -32602, "Invalid params: missing tool name")
            return

        args = params.get("arguments", {})
        if not isinstance(args, dict):
            self.respond_error(req_id, -32602, "Invalid params: arguments must be an object")
            return

        if tool not in self.handlers:
            self.respond_error(req_id, -32601, f"Method not found: tool '{tool}'")
            return

        try:
            result = self.handlers[tool](args)
            if req_id is None:
                return
            self.respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result}],
                    "isError": False,
                },
            })
        except Exception as error:  # pylint: disable=broad-exception-caught
            if req_id is None:
                return
            self.respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"{type(error).__name__}: {error}"}
                    ],
                    "isError": True,
                },
            })

    def handle_unknown_method(self, method: Optional[str], req_id: Any) -> None:
        """Return JSON-RPC -32601 Method Not Found for unrecognised MCP methods."""
        if req_id is None:
            return
        self.respond_error(req_id, -32601, f"Method not found: {method}")

    def run(self) -> None:
        """Main stdio server loop for MCP protocol."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                self.respond_error(None, -32700, "Parse error")
                continue

            if not isinstance(req, dict):
                self.respond_error(None, -32600, "Invalid Request")
                continue

            method: Optional[str] = req.get("method")
            req_id: Any = req.get("id")

            if method == "initialize":
                self.handle_initialize(req_id)
            elif method == "tools/list":
                self.handle_tools_list(req_id)
            elif method == "tools/call":
                self.handle_tools_call(req, req_id)
            else:
                self.handle_unknown_method(method, req_id)


def main() -> None:
    """Run the MCP server."""
    server = MementoServer()
    server.run()


if __name__ == "__main__":
    main()
