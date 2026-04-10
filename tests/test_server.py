"""
Tests for the memento_context MCP server.

See licence: https://github.com/FranBarInstance/memento-context
"""
# pylint: disable=redefined-outer-name

import json
import pytest
from memento_context.server import MementoServer


@pytest.fixture
def mock_server(monkeypatch, tmp_path):
    """Fixture that isolates the server to use a temporary directory."""
    memory_home = tmp_path / ".memento-context"

    # Patch module constants
    monkeypatch.setattr("memento_context.server.MEMORY_HOME", memory_home)
    global_file = memory_home / "global" / "mementos.json"
    monkeypatch.setattr("memento_context.server.GLOBAL_MEMENTOS_FILE", global_file)
    monkeypatch.setattr("memento_context.server.REPOS_DIR", memory_home / "repos")

    server = MementoServer()

    # Mock behavior and tools files to avoid dependency on real files
    monkeypatch.setattr("memento_context.server.TOOLS_FILE", tmp_path / "tools.json")
    monkeypatch.setattr("memento_context.server.BEHAVIOR_FILE", tmp_path / "behavior.md")
    (tmp_path / "tools.json").write_text(json.dumps([{"name": "test_tool"}]))
    (tmp_path / "behavior.md").write_text("Test behavior instructions")

    # Mock current_repo_path to be stable
    mock_repo = str(tmp_path / "mock-repo")
    monkeypatch.setattr(server, "current_repo_path", lambda: mock_repo)

    return server


def test_server_identity(mock_server):
    """Verify the server identifies itself correctly as memento-context."""
    # Capture output to avoid printing to test stdout
    responses = []
    mock_server.respond = responses.append
    mock_server.handle_initialize("1")
    assert responses[0]["result"]["serverInfo"]["name"] == "memento-context"


def test_init_memento_flow(mock_server):
    """Test that init_memento returns behavior and active mementos."""
    response = mock_server.handle_init_memento({})
    assert "Test behavior instructions" in response
    assert "Global Mementos" in response
    assert mock_server.mementos_loaded is True


def test_mutation_restriction(mock_server):
    """Ensure mutations are blocked if context hasn't been loaded."""
    mock_server.mementos_loaded = False
    with pytest.raises(RuntimeError, match="Session constraint"):
        mock_server.handle_save_memento({"text": "fail", "scope": "global"})


def test_repo_key(mock_server):
    """Ensure the repo key uses the hashing formula correctly."""
    key = mock_server.repo_key("/home/user/my_cool_project")
    assert key.startswith("my-cool-project__")
    assert len(key) == len("my-cool-project__") + 10  # 10 chars hash


def test_memento_lifecycle_global_to_repo(mock_server):
    """Test full create -> read -> move -> read -> delete lifecycle."""
    mock_server.mementos_loaded = True
    # 1. Create (Save)
    save_args = {
        "scope": "global",
        "text": "this is a test memory",
        "tags": ["testing"],
        "expires": "never"
    }

    response = mock_server.handle_save_memento(save_args)
    assert "Memento saved" in response
    assert "global" in response

    # Extract ID
    mementos = mock_server.load_global_mementos()
    assert len(mementos) == 1
    memento_id = mementos[0]["id"]

    # 2. Get
    get_response = mock_server.handle_get_mementos({"scope": "all"})
    assert memento_id in get_response
    assert "this is a test memory" in get_response
    assert "Global Mementos" in get_response

    # 3. Move (Global -> Repo)
    move_args = {
        "id": memento_id,
        "target_scope": "repo"
    }
    move_response = mock_server.handle_move_memento(move_args)
    assert "Memento moved" in move_response
    assert "global -> repo" in move_response

    # Evaluate move resolution
    assert len(mock_server.load_global_mementos()) == 0
    assert len(mock_server.load_repo_mementos()) == 1

    # 4. Delete
    delete_response = mock_server.handle_delete_memento({"id": memento_id})
    assert "Memento deleted" in delete_response

    # Ensure it's empty everywhere
    assert len(mock_server.load_repo_mementos()) == 0


def test_is_active(mock_server):
    """Ensure date comparisons for expiry work robustly."""
    # Never expires
    assert mock_server.is_active({"expires": "never"}, "2026-04-09") is True
    # Missing explicit 'expires' falls back to True safely
    assert mock_server.is_active({"text": "test"}, "2026-04-09") is True
    # Valid explicit future date
    assert mock_server.is_active({"expires": "2026-04-10"}, "2026-04-09") is True
    # Expired explicit past date
    assert mock_server.is_active({"expires": "2026-04-08"}, "2026-04-09") is False


def test_load_json_flat_array_migration(mock_server, tmp_path):
    """Ensure backward compatibility of plain JSON lists and their upgrade path."""
    fpath = tmp_path / "test_migration.json"

    # Simulate an ancient mementos.json (just a list)
    fpath.write_text(json.dumps([{"id": "old_1", "text": "legacy text"}]))

    # Test reading transparently
    data = mock_server.load_json_file(fpath, "migration_test")
    assert len(data) == 1
    assert data[0]["text"] == "legacy text"

    # Test writing transforms it into wrapped format
    mock_server.save_json_file(fpath, data)

    # Read raw to assert envelope insertion
    raw = json.loads(fpath.read_text())
    assert isinstance(raw, dict)
    assert raw["version"] == "1.0"
    assert "updated_at" in raw
    assert isinstance(raw["mementos"], list)
    assert raw["mementos"][0]["id"] == "old_1"
