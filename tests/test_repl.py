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
