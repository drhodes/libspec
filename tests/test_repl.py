import pytest
from unittest.mock import MagicMock, patch
from libspec.repl import LibspecRepl
from libspec.store import SQLiteSpecStore, DBBuild, Component

def test_repl_init():
    repl = LibspecRepl()
    assert repl.store is not None
    assert isinstance(repl.components, list)
    assert isinstance(repl.fqns, set)

@patch("libspec.repl.get_store")
@patch("libspec.repl.DBSpec")
@patch("libspec.repl.DBEdge")
@patch("libspec.repl.DBBuild")
def test_repl_enter_leave(mock_db_build, mock_db_edge, mock_db_spec, mock_get_store):
    mock_store = MagicMock(spec=SQLiteSpecStore)
    mock_get_store.return_value = mock_store
    
    build1 = MagicMock(spec=DBBuild)
    build1.session_id = "87bb22270f9fafe7"
    
    build2 = MagicMock(spec=DBBuild)
    build2.session_id = "0fbc00baabcc96d7"
    
    mock_store._get_latest_build.return_value = build2
    
    # Mock DBBuild get/select calls
    mock_db_build.get_or_none.return_value = build1
    
    mock_spec_record = MagicMock()
    mock_spec_record.ref = "spec.b"
    mock_spec_record.docstring = "B req"
    mock_spec_record.is_template = False
    mock_spec_record.hash = "b"*64
    
    mock_db_spec.select.return_value.where.return_value = [mock_spec_record]
    mock_db_edge.select.return_value.where.return_value.order_by.return_value = []
    
    repl = LibspecRepl()
    assert repl.active_build is None
    # Latest build is loaded on init
    assert repl.active_session_id == "0fbc00baabcc96d7"
    assert len(repl.components) == 1
    assert "spec.b" in repl.fqns
    
    # Mock DBBuild lookup for enter command
    mock_db_build.get_or_none.return_value = build1
    
    # Enter snapshot 1
    repl.cmd_enter("87bb22270f")
    
    assert repl.active_build == build1
    assert repl.active_session_id == "87bb22270f9fafe7"
    
    # Leave snapshot context
    repl.cmd_leave()
    assert repl.active_build is None
    assert repl.active_session_id == "0fbc00baabcc96d7"


@patch("libspec.repl.get_store")
@patch("libspec.repl.DBSpec")
@patch("libspec.repl.DBEdge")
@patch("libspec.repl.DBBuild")
def test_repl_diff(mock_db_build, mock_db_edge, mock_db_spec, mock_get_store):
    mock_store = MagicMock(spec=SQLiteSpecStore)
    mock_get_store.return_value = mock_store
    
    build1 = MagicMock(spec=DBBuild)
    build1.session_id = "87bb22270f9fafe7"
    
    build2 = MagicMock(spec=DBBuild)
    build2.session_id = "0fbc00baabcc96d7"
    
    mock_store._get_latest_build.return_value = build2
    
    # Mock builds order for default diffing
    mock_db_build.select.return_value.order_by.return_value = [build1, build2]
    
    mock_spec_record = MagicMock()
    mock_spec_record.ref = "spec.b"
    mock_spec_record.docstring = "B req"
    mock_spec_record.is_template = False
    mock_spec_record.hash = "b"*64
    
    mock_db_spec.select.return_value.where.return_value = [mock_spec_record]
    mock_db_edge.select.return_value.where.return_value.order_by.return_value = []
    
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


