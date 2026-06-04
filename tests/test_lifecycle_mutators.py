import pytest
import os
import datetime
from click.testing import CliRunner
from libspec.cli import main
from libspec.store import get_store, Component
from libspec.repl import LibspecRepl
from libspec.mcp_server import link_snapshot, compact_store, delete_snapshot, restore_snapshot


def test_cli_rm_and_restore_snapshot():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Initialize
        runner.invoke(main, ["init"])
        
        # Populate store with two distinct snapshots programmatically
        store = get_store()
        comp1 = Component(ref="spec.test1", docstring="Test req 1", is_template=False, inherits=[], hash="1"*64)
        comp2 = Component(ref="spec.test2", docstring="Test req 2", is_template=False, inherits=[], hash="2"*64)
        
        snap1 = store.store_snapshot([comp1])
        snap2 = store.store_snapshot([comp1, comp2]) # second snapshot, so snap2 is the latest
        
        # 1. Try to delete snap2 (latest) - should fail/prevent
        result = runner.invoke(main, ["rm-snapshot", snap2.id], input="y\n")
        assert "Error: Cannot delete snapshot" in result.output or result.exit_code != 0
        
        # 2. Delete snap1 (historical)
        result = runner.invoke(main, ["rm-snapshot", snap1.id], input="y\n")
        assert result.exit_code == 0
        assert "successfully deleted" in result.output
        
        # Verify snap1 is deleted from active list (by reloading store cache)
        store._replay()
        active_snaps = [s.id for s in store.list_snapshots()]
        assert snap1.id not in active_snaps
        
        # 3. Restore snap1
        result = runner.invoke(main, ["restore-snapshot", snap1.id])
        assert result.exit_code == 0
        assert "successfully restored" in result.output
        
        # Verify snap1 is back in active list
        store._replay()
        active_snaps = [s.id for s in store.list_snapshots()]
        assert snap1.id in active_snaps


def test_repl_link_command():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        store = get_store()
        comp = Component(ref="spec.test", docstring="Test req", is_template=False, inherits=[], hash="x"*64)
        snap = store.store_snapshot([comp])
        
        repl = LibspecRepl()
        
        # Run repl link command
        res = repl.commander.run(f"link --snapshot {snap.id} --vcs git --revision abcdef123 --metadata author=derek", repl)
        assert res is True
        
        # Verify VCS link using repl.store (the active store instance that made the mutation)
        snapshots = repl.store.list_snapshots()
        target_snap = next(s for s in snapshots if s.id == snap.id)
        assert target_snap.git_commit == "abcdef123"


def test_mcp_lifecycle_tools():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        store = get_store()
        comp1 = Component(ref="spec.test1", docstring="Test req 1", is_template=False, inherits=[], hash="1"*64)
        comp2 = Component(ref="spec.test2", docstring="Test req 2", is_template=False, inherits=[], hash="2"*64)
        snap1 = store.store_snapshot([comp1])
        snap2 = store.store_snapshot([comp1, comp2])
        
        # 1. Test link_snapshot
        link_res = link_snapshot(snapshot_id=snap1.id, vcs="git", revision="abc12345", metadata={"author": "derek"})
        assert "Successfully linked" in link_res
        
        # 2. Test compact_store
        compact_res = compact_store(dry_run=True)
        assert "LIBSPEC COMPACTION REPORT" in compact_res
        
        # 3. Test delete_snapshot
        del_res = delete_snapshot(snapshot_id=snap1.id)
        assert "successfully deleted" in del_res
        
        # 4. Test restore_snapshot
        rest_res = restore_snapshot(snapshot_id=snap1.id)
        assert "successfully restored" in rest_res
