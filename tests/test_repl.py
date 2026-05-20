import pytest
import datetime
from unittest.mock import MagicMock, patch
from libspec.repl import LibspecRepl
from libspec.store import SQLiteSpecStore, JsonLinesSpecStore, Component, Snapshot, SpecStoreNotFoundError

def test_repl_init():
    repl = LibspecRepl()
    assert repl.store is not None
    assert isinstance(repl.components, list)
    assert isinstance(repl.fqns, set)


@patch("libspec.repl.get_store")
def test_repl_header_shows_backend(mock_get_store, tmp_path, capsys):
    mock_get_store.return_value = JsonLinesSpecStore(str(tmp_path / "spec.jsonl"))
    repl = LibspecRepl()

    repl._print_welcome()

    out = capsys.readouterr().out
    assert "Backend :" in out
    assert "JsonLinesSpecStore" in out
    assert "spec.jsonl" in out

@patch("libspec.repl.get_store")
def test_repl_enter_leave(mock_get_store):
    mock_store = MagicMock(spec=SQLiteSpecStore)
    mock_get_store.return_value = mock_store
    
    build1 = Snapshot(
        id="87bb22270f9fafe7",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        master_hash="8" * 64,
        git_commit=None
    )
    
    build2 = Snapshot(
        id="0fbc00baabcc96d7",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        master_hash="0" * 64,
        git_commit=None
    )
    
    mock_store.current_snapshot.return_value = build2
    mock_store.get_snapshot.return_value = build1
    
    comp = Component(
        ref="spec.b",
        docstring="B req",
        is_template=False,
        inherits=[],
        hash="b"*64
    )
    mock_store.get_components_for_snapshot.return_value = [comp]
    
    repl = LibspecRepl()
    assert repl.active_build is None
    # Latest build is loaded on init
    assert repl.active_session_id == "0fbc00baabcc96d7"
    assert len(repl.components) == 1
    assert "spec.b" in repl.fqns
    
    # Enter snapshot 1
    repl.cmd_enter("87bb22270f")
    
    assert repl.active_build == build1
    assert repl.active_session_id == "87bb22270f9fafe7"
    
    # Leave snapshot context
    repl.cmd_leave()
    assert repl.active_build is None
    assert repl.active_session_id == "0fbc00baabcc96d7"


@patch("libspec.repl.get_store")
def test_repl_diff(mock_get_store):
    mock_store = MagicMock(spec=SQLiteSpecStore)
    mock_get_store.return_value = mock_store
    
    build1 = Snapshot(
        id="87bb22270f9fafe7",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        master_hash="8" * 64,
        git_commit=None
    )
    
    build2 = Snapshot(
        id="0fbc00baabcc96d7",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        master_hash="0" * 64,
        git_commit=None
    )
    
    mock_store.current_snapshot.return_value = build2
    mock_store.list_snapshots.return_value = [build1, build2]
    mock_store.get_components_for_snapshot.return_value = []
    
    repl = LibspecRepl()
    
    # Set active context components
    c_added = Component(ref="spec.added", docstring="Added req", is_template=False, inherits=[], hash="x"*64)
    c_changed = Component(ref="spec.b", docstring="Changed B", is_template=False, inherits=[], hash="y"*64)
    repl.components = [c_added, c_changed]
    
    # Mock get_components_for_build return value
    with patch.object(repl, "get_components_for_build") as mock_get_comp:
        mock_get_comp.return_value = [
            Component(ref="spec.b", docstring="B req", is_template=False, inherits=[], hash="b"*64),
            Component(ref="spec.removed", docstring="Removed req", is_template=False, inherits=[], hash="z"*64)
        ]
        
        # Capture standard stdout to avoid terminal noise and assert correctness
        repl.cmd_diff("")
        
        # Verify that it fetched the predecessor build (build1)
        mock_get_comp.assert_called_once_with(build1)
        
        # Now test with -v flag
        mock_get_comp.reset_mock()
        repl.cmd_diff("-v")
        mock_get_comp.assert_called_once_with(build1)


def test_repl_completer():
    from prompt_toolkit.document import Document
    from libspec.repl import LibspecCompleter
    repl = LibspecRepl()
    repl.fqns = {"spec.a", "spec.b"}
    
    completer = LibspecCompleter(repl)
    
    # 1. Test command mode completion (first word)
    doc = Document("he", cursor_position=2)
    completions = list(completer.get_completions(doc, None))
    assert any(c.text == "help" for c in completions)
    
    # 2. Test show mode FQN completion
    doc = Document("show sp", cursor_position=7)
    completions = list(completer.get_completions(doc, None))
    assert any(c.text == "spec.a" for c in completions)
    assert any(c.text == "spec.b" for c in completions)
    
    # 3. Test enter mode completion (should NOT suggest FQNs!)
    doc = Document("enter sp", cursor_position=8)
    completions = list(completer.get_completions(doc, None))
    assert not any(c.text == "spec.a" for c in completions)


@patch("libspec.repl.get_store")
def test_date_and_hash_resolution(mock_get_store):
    from datetime import datetime
    mock_store = MagicMock(spec=SQLiteSpecStore)
    mock_get_store.return_value = mock_store
    
    builds = []
    for i in range(12):
        b = Snapshot(
            id=f"hash{i:02d}abcde12345",
            created_at=datetime(2026, 5, 19, 13, i),
            master_hash=f"{i:02d}" + "a" * 62,
            git_commit=None
        )
        builds.append(b)
        
    mock_store.list_snapshots.return_value = builds
    mock_store.current_snapshot.return_value = builds[-1]
    mock_store.get_components_for_snapshot.return_value = []
    
    def mock_get_snapshot(id_or_hash):
        for b in builds:
            if id_or_hash in b.id or id_or_hash in b.master_hash or b.id.startswith(id_or_hash):
                return b
        raise SpecStoreNotFoundError()
    mock_store.get_snapshot.side_effect = mock_get_snapshot
    
    repl = LibspecRepl()
    
    # Resolve by partial ISO date string / partial hash
    resolved = repl.find_build_by_id("hash08")
    assert resolved == builds[8]
    
    # Test completer suggestions are limited to 10 most recent builds (index 2 to 11)
    from prompt_toolkit.document import Document
    from libspec.repl import LibspecCompleter
    completer = LibspecCompleter(repl)
    
    # Test empty argument tab completion guides user with recent 10 builds
    doc = Document("enter ", cursor_position=6)
    completions = list(completer.get_completions(doc, None))
    completion_texts = {c.text for c in completions}
    assert builds[-1].id[:10] in completion_texts
    assert builds[2].id[:10] in completion_texts
    assert builds[0].id[:10] not in completion_texts
    assert builds[1].id[:10] not in completion_texts

    # Test tab completion with a prefix filters ALL historical builds!
    doc = Document("enter hash01", cursor_position=12)
    completions = list(completer.get_completions(doc, None))
    completion_texts = {c.text for c in completions}
    assert "hash01abcd" in completion_texts
    assert len(completion_texts) == 1
    
    # Test tab completion with a completely unmatched prefix emits an error
    doc = Document("enter unmatched_prefix", cursor_position=22)
    completions = list(completer.get_completions(doc, None))
    assert len(completions) == 0
