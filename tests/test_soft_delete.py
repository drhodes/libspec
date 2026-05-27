import pytest
import datetime
import os
import peewee
from unittest.mock import patch, MagicMock
from libspec.store import SQLiteSpecStore, JsonLinesSpecStore, Component, Snapshot, SpecStoreNotFoundError
from libspec.repl import LibspecRepl

def test_jsonlines_append_only_tombstone_and_restore(tmp_path):
    log_file = tmp_path / "spec.jsonl"
    store = JsonLinesSpecStore(str(log_file))

    # Store a snapshot
    comp = Component(
        ref="foo.bar",
        docstring="Some component doc",
        is_template=False,
        inherits=[],
        hash="a" * 64
    )
    snap = store.store_snapshot([comp], git_commit="c1")

    assert len(store.list_snapshots()) == 1
    assert store.get_snapshot(snap.id) == snap

    # Delete (tombstone) snapshot
    store.delete_snapshot(snap)

    # 1. Verify it's no longer listed in active snapshots
    assert len(store.list_snapshots()) == 0

    # 2. Verify we can still resolve/lookup the deleted snapshot
    resolved = store.get_snapshot(snap.id)
    assert resolved == snap

    # 3. Verify that the log is append-only (no lines removed)
    with open(log_file, "r") as f:
        lines = f.readlines()
    assert len(lines) >= 3  # snapshot event, component event, and tombstone event
    assert "tombstone" in lines[-1]

    # 4. Restore the snapshot
    store.restore_snapshot(snap)

    # Verify it is back in active snapshots list
    assert len(store.list_snapshots()) == 1
    assert store.list_snapshots()[0] == snap

    # Check append-only restore event added
    with open(log_file, "r") as f:
        lines_after = f.readlines()
    assert len(lines_after) == len(lines) + 1
    assert "restore" in lines_after[-1]


def test_sqlite_soft_delete_and_restore(tmp_path):
    db_file = tmp_path / "test.db"
    
    # 1. Initialize store and create tables
    store = SQLiteSpecStore(str(db_file))
    
    comp = Component(
        ref="foo.bar",
        docstring="Some component doc",
        is_template=False,
        inherits=[],
        hash="a" * 64
    )
    snap = store.store_snapshot([comp], git_commit="c1")

    # Check it shows up in list_snapshots
    assert len(store.list_snapshots()) == 1
    assert store.get_snapshot(snap.id) == snap

    # Delete snapshot (soft delete)
    store.delete_snapshot(snap)

    # Verify not showing in active list
    assert len(store.list_snapshots()) == 0

    # Verify we can still get it by ID
    assert store.get_snapshot(snap.id).id == snap.id

    # Restore snapshot
    store.restore_snapshot(snap)

    # Verify it is back in active list
    assert len(store.list_snapshots()) == 1
    assert store.list_snapshots()[0].id == snap.id


def test_sqlite_schema_migration_backward_compatibility(tmp_path):
    db_file = tmp_path / "legacy.db"
    
    # Define db proxy and tables without the is_deleted column to simulate legacy databases
    legacy_db = peewee.SqliteDatabase(str(db_file))
    
    class LegacyBuild(peewee.Model):
        created_at = peewee.DateTimeField(default=datetime.datetime.now)
        git_commit = peewee.CharField(null=True)
        master_hash = peewee.CharField()
        session_id = peewee.CharField(null=True)

        class Meta:
            database = legacy_db
            table_name = "dbbuild"

    legacy_db.create_tables([LegacyBuild])
    
    # Check that is_deleted column does NOT exist in the legacy dbbuild table
    columns = [c.name for c in legacy_db.get_columns("dbbuild")]
    assert "is_deleted" not in columns
    legacy_db.close()

    # Now load SQLiteSpecStore on this legacy file; should auto-migrate!
    store = SQLiteSpecStore(str(db_file))
    
    # Check that is_deleted has been successfully dynamically appended
    db_columns = [c.name for c in store.database.get_columns("dbbuild")]
    assert "is_deleted" in db_columns


@patch("libspec.repl.get_store")
def test_repl_commands_delete_and_restore(mock_get_store, tmp_path, capsys):
    log_file = tmp_path / "spec.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    mock_get_store.return_value = store

    comp1 = Component(
        ref="foo.bar",
        docstring="Some component doc",
        is_template=False,
        inherits=[],
        hash="a" * 64
    )
    comp2 = Component(
        ref="foo.baz",
        docstring="Another component doc",
        is_template=False,
        inherits=[],
        hash="b" * 64
    )
    # Store multiple snapshots so we can delete one without violating safety constraints
    snap1 = store.store_snapshot([comp1], git_commit="c1")
    snap2 = store.store_snapshot([comp1, comp2], git_commit="c2")

    repl = LibspecRepl()

    # Verify both snapshots are active initially
    assert len(store.list_snapshots()) == 2

    # Simulate rm-snapshot confirmation via mocking inputs
    with patch("builtins.input", return_value="y"):
        repl.commander.run(f"rm-snapshot {snap1.id}", repl)
        
    out = capsys.readouterr().out
    assert "successfully deleted" in out
    assert len(store.list_snapshots()) == 1

    # Try to restore snapshot
    repl.commander.run(f"restore-snapshot {snap1.id}", repl)
    out = capsys.readouterr().out
    assert "successfully restored" in out
    assert len(store.list_snapshots()) == 2


@patch("libspec.repl.get_store")
def test_repl_auto_reload_on_file_change(mock_get_store, tmp_path, capsys):
    log_file = tmp_path / "spec.jsonl"
    log_file.touch()
    
    store = JsonLinesSpecStore(str(log_file))
    mock_get_store.return_value = store

    repl = LibspecRepl()
    
    store_path = repl._store_path()
    assert store_path == str(log_file)
    
    initial_mtime = os.path.getmtime(store_path)
    
    comp = Component(
        ref="foo.bar",
        docstring="Some component doc",
        is_template=False,
        inherits=[],
        hash="a" * 64
    )
    store.store_snapshot([comp], git_commit="c1")
    
    # Guarantee change detection triggers by updating modification time
    os.utime(store_path, (initial_mtime + 10, initial_mtime + 10))
    
    with patch("prompt_toolkit.PromptSession.prompt", return_value="exit"):
        repl.start()
        
    out = capsys.readouterr().out
    assert "Detected change in storage file" in out
    assert "Successfully reloaded active context" in out
    assert len(repl.components) == 1
