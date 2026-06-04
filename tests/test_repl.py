import datetime
from unittest.mock import MagicMock, patch
from libspec.repl import LibspecRepl
from libspec.store import JsonLinesSpecStore, Component, Snapshot, SpecStoreNotFoundError

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
    mock_store = MagicMock(spec=JsonLinesSpecStore)
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
    mock_store = MagicMock(spec=JsonLinesSpecStore)
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


@patch("libspec.repl.get_store")
@patch("libspec.spec_diff.generate_native_patch")
def test_repl_diff_vv(mock_generate_native_patch, mock_get_store, capsys):
    mock_store = MagicMock(spec=JsonLinesSpecStore)
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
    
    # Run with -vv
    repl.cmd_diff("-vv")
    
    # Assert generate_native_patch was called with build1 and build2
    mock_generate_native_patch.assert_called_once_with(old_snap=build1, new_snap=build2)


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
    mock_store = MagicMock(spec=JsonLinesSpecStore)
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
    
    # Test empty argument tab completion guides user with recent 10 builds and dynamic indices
    doc = Document("enter ", cursor_position=6)
    completions = list(completer.get_completions(doc, None))
    completion_texts = {c.text for c in completions}
    assert builds[-1].id[:10] in completion_texts
    assert builds[2].id[:10] in completion_texts
    assert builds[0].id[:10] not in completion_texts
    assert builds[1].id[:10] not in completion_texts
    assert "#0" in completion_texts
    assert "#9" in completion_texts

    # Test tab completion with a prefixed dynamic index works perfectly
    doc = Document("enter #6", cursor_position=8)
    completions = list(completer.get_completions(doc, None))
    completion_texts = {c.text for c in completions}
    assert "#6" in completion_texts
    assert len(completion_texts) == 1

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

@patch("libspec.repl.get_store")
@patch("builtins.input", side_effect=["y"])
def test_repl_rm_snapshot(mock_input, mock_get_store, capsys):
    mock_store = MagicMock(spec=JsonLinesSpecStore)
    mock_get_store.return_value = mock_store
    
    build1 = Snapshot(id="hash1", created_at=datetime.datetime.now(), master_hash="1"*64, git_commit=None)
    build2 = Snapshot(id="hash2", created_at=datetime.datetime.now(), master_hash="2"*64, git_commit=None)
    
    mock_store.current_snapshot.return_value = build2
    mock_store.get_snapshot.return_value = build1
    mock_store.list_snapshots.return_value = [build1, build2]
    mock_store.get_components_for_snapshot.return_value = []
    mock_store.list_components.return_value = []
    
    repl = LibspecRepl()
    
    # 1. Try to delete the LATEST snapshot (build2)
    mock_store.get_snapshot.return_value = build2
    repl.commander.run("rm-snapshot hash2", repl)
    out = capsys.readouterr().out
    assert "Error: Cannot delete snapshot 'hash2' because it is the latest" in out
    
    # 2. Try to delete the ACTIVE snapshot (if we entered it)
    mock_store.get_snapshot.return_value = build1
    repl.cmd_enter("hash1")
    repl.commander.run("rm-snapshot hash1", repl)
    out = capsys.readouterr().out
    assert "Error: Cannot delete snapshot 'hash1' because it is the currently active/entered context" in out
    
    # 3. Successful deletion (after leave)
    repl.cmd_leave()
    repl.commander.run("rm-snapshot hash1", repl)
    out = capsys.readouterr().out
    assert "WARNING: You are about to permanently delete the following snapshot" in out
    assert "Target Reference" in out
    assert "hash1" in out
    assert "Resolved Hash ID" in out
    assert "Snapshot 'hash1' successfully deleted" in out
    mock_store.delete_snapshot.assert_called_once_with(build1)


@patch("libspec.repl.get_store")
def test_repl_snapshot_enumeration_and_index_resolution(mock_get_store, capsys):
    mock_store = MagicMock(spec=JsonLinesSpecStore)
    mock_get_store.return_value = mock_store

    build1 = Snapshot(id="oldest_id", created_at=datetime.datetime.now(), master_hash="1"*64, git_commit=None)
    build2 = Snapshot(id="newest_id", created_at=datetime.datetime.now(), master_hash="2"*64, git_commit=None)

    mock_store.current_snapshot.return_value = build2
    mock_store.list_snapshots.return_value = [build1, build2]
    mock_store.get_components_for_snapshot.return_value = []

    repl = LibspecRepl()

    # Verify listing displays enumeration indices correctly
    repl.cmd_list_snapshots()
    out = capsys.readouterr().out
    assert "#0 •" in out
    assert "newest_id" in out
    assert "#1 •" in out
    assert "oldest_id" in out

    # Verify resolving by index works (strictly prefixed with '#')
    # Index #0 is the most recent (build2)
    resolved_0 = repl.find_build_by_id("#0")
    assert resolved_0 == build2

    # Index #1 is the oldest (build1)
    resolved_1 = repl.find_build_by_id("#1")
    assert resolved_1 == build1

    # Raw digits do NOT resolve as indices (they fallback to DB lookup by hash prefix)
    mock_store.get_snapshot.return_value = build1
    resolved_raw = repl.find_build_by_id("1")
    assert resolved_raw == build1
    mock_store.get_snapshot.assert_called_with("1")


@patch("libspec.repl.get_store")
def test_repl_active_snapshot_isolation(mock_get_store, capsys):
    mock_store = MagicMock(spec=JsonLinesSpecStore)
    mock_get_store.return_value = mock_store

    # Two snapshots with the same master_hash/ID but different created_at
    build1 = Snapshot(
        id="87e4dbbe8f8d1090",
        created_at=datetime.datetime(2026, 5, 25, 21, 14, 10),
        master_hash="8" * 64,
        git_commit="f0541cd"
    )
    build2 = Snapshot(
        id="0de81c7a04f14080",
        created_at=datetime.datetime(2026, 5, 26, 21, 19, 37),
        master_hash="0" * 64,
        git_commit="cb803c9"
    )
    build3 = Snapshot(
        id="87e4dbbe8f8d1090",
        created_at=datetime.datetime(2026, 5, 26, 21, 19, 57),
        master_hash="8" * 64,
        git_commit="cb803c9"
    )

    mock_store.current_snapshot.return_value = build3
    mock_store.list_snapshots.return_value = [build1, build2, build3]
    mock_store.get_components_for_snapshot.return_value = []

    repl = LibspecRepl()

    repl.cmd_list_snapshots()
    out = capsys.readouterr().out

    # Split lines to inspect markers for each row
    lines = [line.strip() for line in out.splitlines() if "ID:" in line]
    assert len(lines) == 3

    # #0 is the newest (build3) -> should be active (displayed at lines[2])
    assert "#0" in lines[2]
    assert "(ACTIVE)" in lines[2]

    # #1 is the middle (build2) -> should NOT be active
    assert "#1" in lines[1]
    assert "(ACTIVE)" not in lines[1]

    # #2 is the oldest (build1) -> should NOT be active (displayed at lines[0], despite identical ID/master_hash to build3)
    assert "#2" in lines[0]
    assert "(ACTIVE)" not in lines[0]


def test_repl_command_help(capsys):
    repl = LibspecRepl()
    
    # 1. Test diff --help
    repl.commander.run("diff --help", repl)
    out = capsys.readouterr().out
    assert "diff" in out
    assert "Flags:" in out
    assert "Example:" in out
    
    # 2. Test show -h
    repl.commander.run("show -h", repl)
    out = capsys.readouterr().out
    assert "show" in out
    assert "Usage:" in out
    
    # 3. Test a command that doesn't override usage (default usage)
    repl.commander.run("list --help", repl)
    out = capsys.readouterr().out
    assert "list" in out
    assert "Description:" in out


def test_repl_shortcuts_and_completer_and_help_padding(capsys):
    from prompt_toolkit.document import Document
    from libspec.repl import LibspecCompleter
    
    repl = LibspecRepl()
    
    # 1. Test shortcuts delegation
    with patch.object(repl.commander.commands["list-snapshots"], "run") as mock_sn_run, \
         patch.object(repl.commander.commands["list"], "run") as mock_list_run:
        
        repl.commander.run("sn", repl)
        mock_sn_run.assert_called_once_with(repl, "")
        mock_sn_run.reset_mock()
        
        repl.commander.run("ls", repl)
        mock_sn_run.assert_called_once_with(repl, "")
        
        repl.commander.run("components", repl)
        mock_list_run.assert_called_once_with(repl, "")

    # 2. Test completer does not suggest shortcuts/aliases
    completer = LibspecCompleter(repl)
    doc = Document("s", cursor_position=1)
    completions = [c.text for c in completer.get_completions(doc, None)]
    assert "search" in completions
    assert "show" in completions
    assert "list-snapshots" not in completions
    assert "sn" not in completions
    
    doc2 = Document("l", cursor_position=1)
    completions2 = [c.text for c in completer.get_completions(doc2, None)]
    assert "list" in completions2
    assert "leave" in completions2
    assert "list-snapshots" in completions2
    assert "ls" not in completions2

    # 3. Test help padding dynamic calculation
    repl.commander.run("help", repl)
    out = capsys.readouterr().out
    # Longest command is 'restore-snapshot' (16 chars).
    # 'list' (4 chars) will be padded with 12 spaces plus the 2 separator spaces.
    assert "list" in out
    # Strip ANSI colors to check raw layout
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    plain_out = ansi_escape.sub('', out)
    assert "  list              List all specification components." in plain_out


def test_repl_auto_suggest():
    from prompt_toolkit.document import Document
    from prompt_toolkit.history import InMemoryHistory
    from libspec.repl import HybridAutoSuggest
    
    repl = LibspecRepl()
    auto_suggest = HybridAutoSuggest(repl)
    
    # 1. Test Command Guessing (when typing prefix of a primary command)
    doc = Document("sh")
    suggestion = auto_suggest.get_suggestion(None, doc)
    assert suggestion is not None
    assert suggestion.text == "ow"
    
    doc2 = Document("rest")
    suggestion2 = auto_suggest.get_suggestion(None, doc2)
    assert suggestion2 is not None
    assert suggestion2.text == "ore-snapshot"

    doc3 = Document("show")
    suggestion3 = auto_suggest.get_suggestion(None, doc3)
    assert suggestion3 is None or suggestion3.text == ""

    # 2. Test History Fallback and Space Blocks
    mock_history = InMemoryHistory()
    mock_history.append_string("snapshots")
    mock_history.append_string("show spec.app.App")
    mock_history.append_string("diff -v")
    
    class MockBuffer:
        def __init__(self, history):
            self.history = history

    buffer = MockBuffer(mock_history)
    
    # "show sp" -> allowed because suffix "ec.app.App" does not contain spaces
    doc_hist = Document("show sp")
    suggestion_hist = auto_suggest.get_suggestion(buffer, doc_hist)
    assert suggestion_hist is not None
    assert suggestion_hist.text == "ec.app.App"

    # "diff" -> blocked because suffix " -v" starts with a space
    doc_diff = Document("diff")
    suggestion_diff = auto_suggest.get_suggestion(buffer, doc_diff)
    assert suggestion_diff is None

    # "diff " -> blocked because the input ends with a space
    doc_space = Document("diff ")
    suggestion_space = auto_suggest.get_suggestion(buffer, doc_space)
    assert suggestion_space is None


    
    # 3. Test PromptSession styling and auto suggest configuration
    with patch("libspec.repl.PromptSession") as mock_session_cls:
        mock_session_inst = MagicMock()
        mock_session_inst.prompt.side_effect = EOFError
        mock_session_cls.return_value = mock_session_inst
        
        with patch.object(repl, "_print_welcome"):
            repl.last_mtime = 1234.5
            with patch.object(repl, "_store_path", return_value=None):
                repl.start()
                
                mock_session_cls.assert_called_once()
                args, kwargs = mock_session_cls.call_args
                
                assert "style" in kwargs
                style = kwargs["style"]
                assert ("auto-suggest", "#666666") in style.style_rules
                
                assert "auto_suggest" in kwargs
                assert isinstance(kwargs["auto_suggest"], HybridAutoSuggest)
                
                # Verify key_bindings is set with standard keys
                from prompt_toolkit.keys import Keys
                assert "key_bindings" in kwargs
                kb = kwargs["key_bindings"]
                bound_keys = [b.keys[0] for b in kb.bindings]
                assert Keys.Right in bound_keys
                assert Keys.End in bound_keys
                assert Keys.ControlF in bound_keys
                assert Keys.ControlE in bound_keys
                assert Keys.ControlM in bound_keys


def test_repl_file_change_corruption(capsys):
    repl = LibspecRepl()
    
    # Mock self.last_mtime to some old timestamp, and mock _store_path existence
    repl.last_mtime = 1000.0
    
    # Mock os.path.exists to return True and os.path.getmtime to return a new timestamp (e.g. 2000.0)
    with patch("os.path.exists", return_value=True), \
         patch("os.path.getmtime", return_value=2000.0), \
         patch.object(repl, "_store_path", return_value="/mock/store.jsonl"), \
         patch.object(repl.store, "_replay") as mock_replay, \
         patch.object(repl, "load_components") as mock_load, \
         patch("libspec.repl.PromptSession") as mock_session_cls:
         
        mock_session_inst = MagicMock()
        mock_session_inst.prompt.side_effect = EOFError
        mock_session_cls.return_value = mock_session_inst
        
        # Run start() to trigger capture, corruption, and reprint on change detection
        repl.start()
        
        # Verify reload functions were called
        mock_replay.assert_called_once()
        mock_load.assert_called_once()
        
        # Verify the printed terminal corruption output contains dots instead of spaces in the welcome banner
        out = capsys.readouterr().out
        assert "_·_·_" in out
        
        # Verify the fresh reload notification messages are printed normally with spaces
        assert "[libspec] Detected change in storage file. Reloading..." in out
        assert "  Successfully reloaded active context. Current Snapshot:" in out


@patch("libspec.repl.get_store")
def test_snapshots_command_shows_pending(mock_get_store, capsys):
    mock_store = MagicMock(spec=JsonLinesSpecStore)
    mock_get_store.return_value = mock_store
    
    build = Snapshot(
        id="87bb22270f9fafe7",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        master_hash="8" * 64,
        git_commit=None  # unlinked/pending
    )
    
    mock_store.current_snapshot.return_value = build
    mock_store.list_snapshots.return_value = [build]
    mock_store.get_components_for_snapshot.return_value = []
    
    repl = LibspecRepl()
    # Run the list-snapshots command
    repl.commander.run("list-snapshots", repl)
    
    out = capsys.readouterr().out
    assert "PENDING" in out


def test_log_command(capsys):
    repl = LibspecRepl()
    # Mock get_raw_events on the store
    sample_events = [
        {
            "type": "snapshot",
            "id": "12345678abcdef01",
            "created_at": "2026-05-28T22:24:19.000000",
            "master_hash": "12345678abcdef012345678901234567",
            "git_commit": "42cd025"
        },
        {
            "type": "component",
            "snapshot_id": "12345678abcdef01",
            "ref": "spec.store.JsonLinesStore",
            "hash": "a1f8b2c4d5e6f7"
        },
        {
            "type": "implemented",
            "snapshot_id": "12345678abcdef01",
            "ref": "spec.store.JsonLinesStore",
            "file": "libspec/store.py",
            "line": 12
        },
        {
            "type": "vcs_link",
            "snapshot_id": "12345678abcdef01",
            "vcs": "git",
            "revision": "42cd025"
        },
        {
            "type": "tombstone",
            "snapshot_id": "12345678abcdef01"
        },
        {
            "type": "restore",
            "snapshot_id": "12345678abcdef01"
        }
    ]
    repl.store.get_raw_events = MagicMock(return_value=sample_events)
    
    # Run command
    res = repl.commander.run("log", repl)
    assert res is True
    
    out = capsys.readouterr().out
    assert "Chronological SpecStore Event Log (6 events):" in out
    assert "[SNAPSHOT]" in out
    assert "[COMPONENT]" in out
    assert "[IMPLEMENTED]" in out
    assert "[VCS_LINK]" in out
    assert "[TOMBSTONE]" in out
    assert "[RESTORE]" in out
    assert "spec.store.JsonLinesStore" in out
    assert "libspec/store.py:12" in out
    assert "git:42cd025" in out
    assert "#0" in out
    assert "#5" in out


@patch("libspec.repl.get_store")
def test_repl_diff_provenance(mock_get_store, capsys):
    mock_store = MagicMock(spec=JsonLinesSpecStore)
    mock_get_store.return_value = mock_store

    snap1 = Snapshot(
        id="1111111111111111",
        created_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=20),
        master_hash="1" * 64,
        git_commit="git_12345"
    )
    snap2 = Snapshot(
        id="2222222222222222",
        created_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10),
        master_hash="2" * 64,
        git_commit="PENDING"
    )
    snap3 = Snapshot(
        id="3333333333333333",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        master_hash="3" * 64,
        git_commit="git_67890"
    )

    mock_store.current_snapshot.return_value = snap3
    mock_store.list_snapshots.return_value = [snap1, snap2, snap3]
    mock_store.get_components_for_snapshot.return_value = []

    repl = LibspecRepl()

    # Define components per snapshot:
    # snap1 has X
    comp_x_v1 = Component(ref="spec.X", docstring="Doc X", is_template=False, inherits=[], hash="1" * 64)
    
    # snap2 adds A and keeps X
    comp_a = Component(ref="spec.A", docstring="Doc A", is_template=False, inherits=[], hash="a" * 64)
    
    # snap3 changes X (to v2) and keeps A
    comp_x_v2 = Component(ref="spec.X", docstring="Doc X New", is_template=False, inherits=[], hash="2" * 64)

    def mock_get_comps(build):
        if build.id == snap1.id:
            return [comp_x_v1]
        elif build.id == snap2.id:
            return [comp_x_v1, comp_a]
        elif build.id == snap3.id:
            return [comp_x_v2, comp_a]
        return []

    repl.get_components_for_build = MagicMock(side_effect=mock_get_comps)
    repl.components = [comp_x_v2, comp_a]

    # 1. Initialize snapshot registry index mappings in REPL
    repl._snapshot_registry = {
        "2": snap1,
        "#2": snap1,
        "1": snap2,
        "#1": snap2,
        "0": snap3,
        "#0": snap3,
    }

    # 2. Run diff range comparing snap1 (#2) to snap3 (#0)
    capsys.readouterr() # Clear any previous output
    res = repl.commander.run("diff #2 #0", repl)
    assert res is True

    out = capsys.readouterr().out

    # Assert correct diff provenance tracking:
    # REQUIREMENT-ID: spec.repl.DiffProvenanceFormatting
    # Component A was introduced in snap2 (#1 | PENDING)
    assert "spec.A [Component]" in out
    assert "(introduced in #1 | Git: PENDING)" in out

    # Component X was changed in snap3 (#0 | git_67890)
    assert "spec.X [Component]" in out
    assert "(changed in #0 | Git: git_678)" in out


@patch("libspec.repl.get_store")
def test_repl_compact(mock_get_store, capsys):
    mock_store = MagicMock(spec=JsonLinesSpecStore)
    mock_get_store.return_value = mock_store
    mock_store.current_snapshot.return_value = None
    mock_store.list_components.return_value = []

    mock_store.compact.return_value = {
        "original_size": 2048,
        "compacted_size": 1024,
        "reclaimed_bytes": 1024,
        "pruned_snapshots_count": 2,
        "upgraded_legacy_format": True
    }
    mock_store.filepath = "/dummy/libspec.jsonl"

    repl = LibspecRepl()
    repl.load_components = MagicMock()

    # Run compact command
    res = repl.commander.run("compact", repl)
    assert res is True

    out = capsys.readouterr().out
    assert "LIBSPEC COMPACTION REPORT" in out
    assert "MODE             : EXECUTION (Database compacted)" in out
    assert "Snapshots Pruned : 2" in out
    assert "Original Size    : 2.00 KB" in out
    assert "Compacted Size   : 1.00 KB" in out
    assert "Space Reclaimed  : 1.00 KB (50.0%)" in out
    assert "Format Upgrade   : COMPLETED (Legacy format migrated)" in out


@patch("libspec.repl.get_store")
def test_repl_compact_dry_run(mock_get_store, capsys):
    mock_store = MagicMock(spec=JsonLinesSpecStore)
    mock_get_store.return_value = mock_store
    mock_store.current_snapshot.return_value = None
    mock_store.list_components.return_value = []

    mock_store.compact.return_value = {
        "original_size": 2048,
        "compacted_size": 1024,
        "reclaimed_bytes": 1024,
        "pruned_snapshots_count": 2,
        "upgraded_legacy_format": True
    }

    repl = LibspecRepl()
    repl.load_components = MagicMock()

    # Run compact command with dry run
    res = repl.commander.run("compact --dry-run", repl)
    assert res is True

    out = capsys.readouterr().out
    assert "LIBSPEC COMPACTION REPORT" in out
    assert "MODE             : DRY RUN (No changes written)" in out
    assert "Format Upgrade   : PENDING (Legacy format detected)" in out


def test_repl_sidecar_file_change_reload(capsys):
    repl = LibspecRepl()
    repl.store.filepath = "/mock/store.jsonl"
    repl.store.vcs_links_filepath = "/mock/vcs_links.jsonl"

    repl.last_mtime = 1000.0

    def mock_getmtime(path):
        if path == "/mock/store.jsonl":
            return 1000.0
        if path == "/mock/vcs_links.jsonl":
            return mock_getmtime.vcs_mtime
        return 0.0
    mock_getmtime.vcs_mtime = 2000.0

    with patch("os.path.exists", return_value=True), \
         patch("os.path.getmtime", side_effect=mock_getmtime), \
         patch.object(repl, "_store_path", return_value="/mock/store.jsonl"), \
         patch.object(repl.store, "_replay") as mock_replay, \
         patch.object(repl, "load_components") as mock_load, \
         patch("libspec.repl.PromptSession") as mock_session_cls:

        mock_session_inst = MagicMock()

        def prompt_side_effect(*args, **kwargs):
            if mock_getmtime.vcs_mtime == 2000.0:
                mock_getmtime.vcs_mtime = 2005.0
                return ""
            else:
                raise EOFError

        mock_session_inst.prompt.side_effect = prompt_side_effect
        mock_session_cls.return_value = mock_session_inst

        repl.start()

        mock_replay.assert_called_once()
        mock_load.assert_called_once()

        out = capsys.readouterr().out
        assert "[libspec] Detected change in storage file. Reloading..." in out


@patch("libspec.repl.get_store")
def test_repl_diff_successor_shortcut(mock_get_store):
    import pytest
    mock_store = MagicMock(spec=JsonLinesSpecStore)
    mock_get_store.return_value = mock_store

    snap1 = Snapshot(id="1111111111111111", created_at=datetime.datetime.now(datetime.timezone.utc), master_hash="1"*64, git_commit=None)
    snap2 = Snapshot(id="2222222222222222", created_at=datetime.datetime.now(datetime.timezone.utc), master_hash="2"*64, git_commit=None)
    snap3 = Snapshot(id="3333333333333333", created_at=datetime.datetime.now(datetime.timezone.utc), master_hash="3"*64, git_commit=None)

    mock_store.current_snapshot.return_value = snap3
    mock_store.list_snapshots.return_value = [snap1, snap2, snap3]
    mock_store.get_components_for_snapshot.return_value = []

    repl = LibspecRepl()
    
    # Initialize snapshot registry index mappings in REPL
    repl._snapshot_registry = {
        "2": snap1,
        "#2": snap1,
        "1": snap2,
        "#1": snap2,
        "0": snap3,
        "#0": snap3,
    }

    # Resolve @1 should mean diff #1 #2 (so old = snap2, new = snap1)
    old_snap, new_snap = repl._resolve_diff_snapshots(["@1"])
    assert old_snap == snap2
    assert new_snap == snap1

    # Resolve @0 should mean diff #0 #1 (so old = snap3, new = snap2)
    old_snap, new_snap = repl._resolve_diff_snapshots(["@0"])
    assert old_snap == snap3
    assert new_snap == snap2

    # Verify invalid integer raises ValueError
    with pytest.raises(ValueError, match="Invalid successor diff syntax"):
        repl._resolve_diff_snapshots(["@invalid"])

    # Verify out of range index raises ValueError (e.g. @2 -> #2 and #3, but #3 does not exist)
    with pytest.raises(ValueError, match="Could not resolve snapshots for successor diff target"):
        repl._resolve_diff_snapshots(["@2"])











