#!/usr/bin/env python3
"""
server.py - memento-context MCP server
Implements MCP server for persistent global and repository-scoped mementos.

See licence: https://github.com/FranBarInstance/memento-context
"""
import datetime
import hashlib
import json
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


# pylint: disable=too-many-public-methods
class MementoServer:
    """Stateful MCP stdio server for memento storage and retrieval."""

    def __init__(self) -> None:
        self.mementos_loaded = False
        self.handlers = {
            "init_memento": self.handle_init_memento,
            "get_mementos": self.handle_get_mementos,
            "save_memento": self.handle_save_memento,
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

    def current_repo_path(self) -> str:
        """Return the canonical workspace path used as repository scope."""
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
        resolved_path = repo_path or self.current_repo_path()
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

    def validate_scope(self, scope: Any) -> str:
        """Validate global vs repository scope."""
        if not isinstance(scope, str) or scope not in VALID_SCOPES:
            raise ValueError("Invalid scope: expected 'global' or 'repo'")
        return scope

    def is_active(self, memento: Dict[str, Any], today: str) -> bool:
        """Return whether a memento should be injected into active context."""
        expires = memento.get("expires")
        if not expires or expires == "never":
            return True
        # Only treat as date if it looks like YYYY-MM-DD; otherwise treat as expired
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
        return [
            memento for memento in self.load_global_mementos()
            if self.is_active(memento, today)
        ]

    def get_active_repo_mementos(self, repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return non-expired repo mementos."""
        today = datetime.date.today().isoformat()
        return [
            memento for memento in self.load_repo_mementos(repo_path)
            if self.is_active(memento, today)
        ]

    def format_memento_list(self, title: str, mementos: List[Dict[str, Any]]) -> str:
        """Render a titled memento section for the model."""
        if not mementos:
            return f"## {title}\nNo active mementos."

        lines = [
            f"- [{memento.get('id', '?')}] "
            f"{memento.get('text', '')} "
            f"(expires: {memento.get('expires', 'never')})"
            for memento in mementos
        ]
        return "\n".join([f"## {title}", *lines])

    def format_active_context(self) -> str:
        """Render both global and repository mementos for session bootstrap."""
        repo_path = self.current_repo_path()
        repo_name = Path(repo_path).name
        return "\n\n".join(
            [
                self.format_memento_list(
                    "Global Mementos",
                    self.get_active_global_mementos(),
                ),
                self.format_memento_list(
                    f"Repository Mementos ({repo_name})",
                    self.get_active_repo_mementos(repo_path),
                ),
            ]
        )

    def mark_context_loaded(self, source: str) -> None:
        """Mark session context as available and emit a debug log."""
        self.mementos_loaded = True
        print(f"[memento-context] {source} executed. Context loaded.", file=sys.stderr)

    def require_mementos_loaded(self) -> None:
        """Ensure session context was previously loaded in this session."""
        if not self.mementos_loaded:
            raise RuntimeError(
                "Session constraint: call init_memento or get_mementos before mutating mementos."
            )

    def find_memento(self, memento_id: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """Locate a memento in global or repository storage."""
        global_mementos = self.load_global_mementos()
        for memento in global_mementos:
            if memento["id"] == memento_id:
                return "global", global_mementos, memento

        repo_mementos = self.load_repo_mementos()
        for memento in repo_mementos:
            if memento["id"] == memento_id:
                return "repo", repo_mementos, memento

        raise ValueError(f"Memento not found: {memento_id}")

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

    def build_memento(self, args: Dict[str, Any], scope: str) -> Dict[str, Any]:
        """Build a stored memento payload."""
        memento = {
            "id": f"memento_{datetime.date.today()}_{uuid.uuid4().hex[:8]}",
            "scope": scope,
            "text": args["text"],
            "tags": args.get("tags", []),
            "expires": self.validate_expires(args.get("expires")),
            "created": datetime.date.today().isoformat(),
        }
        if scope == "repo":
            repo_path = self.current_repo_path()
            memento["repo_path"] = repo_path
            memento["repo_name"] = Path(repo_path).name
        return memento

    def persist_memento(self, memento: Dict[str, Any]) -> None:
        """Save a memento into the appropriate storage scope."""
        scope = self.validate_scope(memento["scope"])
        if scope == "global":
            mementos = self.load_global_mementos()
            mementos.append(memento)
            self.save_global_mementos(mementos)
            return

        repo_path = str(memento["repo_path"])
        mementos = self.load_repo_mementos(repo_path)
        mementos.append(memento)
        self.save_repo_mementos(mementos, repo_path)

    def remove_memento(self, memento_id: str) -> Tuple[str, Dict[str, Any]]:
        """Delete a memento from its current store and return its original payload."""
        scope, mementos, target = self.find_memento(memento_id)
        filtered = [memento for memento in mementos if memento["id"] != memento_id]
        if scope == "global":
            self.save_global_mementos(filtered)
        else:
            # Use the repo_path stored in the memento itself to avoid CWD drift
            repo_path = target.get("repo_path") or self.current_repo_path()
            self.save_repo_mementos(filtered, repo_path)
        return scope, target

    def handle_init_memento(self, _: Dict[str, Any]) -> str:
        """Handler for init_memento tool: returns behavior plus active mementos."""
        behavior = self.load_behavior().strip()
        active_context = self.format_active_context()
        self.mark_context_loaded("init_memento")
        return "\n\n".join(
            [
                "## Behavior",
                behavior,
                active_context,
            ]
        )

    def handle_get_mementos(self, args: Dict[str, Any]) -> str:
        """Handler for get_mementos tool: returns active mementos by scope."""
        scope = args.get("scope", "all")
        if scope not in {"all", "global", "repo"}:
            raise ValueError("Invalid scope: expected 'all', 'global', or 'repo'")

        sections: List[str] = []
        if scope in {"all", "global"}:
            sections.append(
                self.format_memento_list(
                    "Global Mementos",
                    self.get_active_global_mementos(),
                )
            )
        if scope in {"all", "repo"}:
            repo_name = Path(self.current_repo_path()).name
            sections.append(
                self.format_memento_list(
                    f"Repository Mementos ({repo_name})",
                    self.get_active_repo_mementos(),
                )
            )

        self.mark_context_loaded("get_mementos")
        return "\n\n".join(sections)

    def handle_save_memento(self, args: Dict[str, Any]) -> str:
        """Handler for save_memento tool: stores a new scoped memento entry."""
        self.require_mementos_loaded()
        scope = self.validate_scope(args.get("scope"))
        memento = self.build_memento(args, scope)
        self.persist_memento(memento)
        return f"Memento saved: {memento['id']} ({scope})"

    def handle_delete_memento(self, args: Dict[str, Any]) -> str:
        """Handler for delete_memento tool: removes a memento by given id."""
        self.require_mementos_loaded()
        original_scope, _ = self.remove_memento(args["id"])
        return f"Memento deleted: {args['id']} ({original_scope})"

    def handle_move_memento(self, args: Dict[str, Any]) -> str:
        """Handler for move_memento tool: changes a memento scope."""
        self.require_mementos_loaded()
        target_scope = self.validate_scope(args.get("target_scope"))

        # Single lookup: reuse the full payload returned by find_memento
        original_scope, _, memento = self.find_memento(args["id"])

        if original_scope == target_scope:
            return f"Memento unchanged: {args['id']} already in {target_scope}"

        # Remove from current store using stored repo_path to avoid CWD drift
        _, _ = self.remove_memento(args["id"])

        moved = dict(memento)
        moved["scope"] = target_scope
        if target_scope == "global":
            moved.pop("repo_path", None)
            moved.pop("repo_name", None)
        else:
            repo_path = self.current_repo_path()
            moved["repo_path"] = repo_path
            moved["repo_name"] = Path(repo_path).name

        self.persist_memento(moved)
        return f"Memento moved: {args['id']} ({original_scope} -> {target_scope})"

    def respond(self, obj: Dict[str, Any]) -> None:
        """Send JSON response over stdout following MCP protocol."""
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()

    def handle_initialize(self, req_id: Optional[str]) -> None:
        """Handle MCP initialize request."""
        self.mementos_loaded = False
        self.respond(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "memento-context", "version": "0.1.0"},
                },
            }
        )

    def handle_tools_list(self, req_id: Optional[str]) -> None:
        """Handle MCP tools/list request."""
        try:
            tools = self.load_tools()
            self.respond(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": tools},
                }
            )
        except Exception as error:  # pylint: disable=broad-exception-caught
            error_msg = f"{type(error).__name__}: {error}"
            self.respond(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": error_msg,
                    },
                }
            )

    def handle_tools_call(self, req: Dict[str, Any], req_id: Optional[str]) -> None:
        """Handle MCP tools/call request."""
        try:
            params = req.get("params")
            if not isinstance(params, dict):
                raise ValueError("Invalid tools/call request: missing params object")

            tool = params.get("name")
            if not isinstance(tool, str) or not tool:
                raise ValueError("Invalid tools/call request: missing tool name")

            args = params.get("arguments", {})
            if not isinstance(args, dict):
                raise ValueError(
                    "Invalid tools/call request: arguments must be an object"
                )

            if tool not in self.handlers:
                raise ValueError(f"Unimplemented tool: {tool}")
            result = self.handlers[tool](args)
            self.respond(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": result}],
                    },
                }
            )
        except Exception as error:  # pylint: disable=broad-exception-caught
            error_msg = f"{type(error).__name__}: {error}"
            self.respond(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": error_msg,
                    },
                }
            )

    def handle_unknown_method(self, method: Optional[str], req_id: Optional[str]) -> None:
        """Return JSON-RPC -32601 Method Not Found for unrecognised MCP methods."""
        # Suppress notification messages (id is None) — they don't expect a response
        if req_id is None:
            return
        self.respond(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }
        )

    def run(self) -> None:
        """Main stdio server loop for MCP protocol."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue

            method: Optional[str] = req.get("method")
            req_id: Optional[str] = req.get("id")

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
