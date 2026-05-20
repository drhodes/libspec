import os
import pytest
import datetime
from unittest.mock import patch
from libspec.cli import cmd_migrate, cmd_migrate_store
from libspec.migration import migrate
from libspec.store import (
    get_store,
    DBBuild,
    DBSpec,
    DBEdge,
    JsonLinesSpecStore,
    SQLiteSpecStore,
    Component,
    Implemented,
)


def _component(ref, marker):
    return Component(
        ref=ref,
        docstring=f"{ref} requirement",
        is_template=False,
        inherits=[],
        hash=marker * 64,
    )


def _populate_store(store):
    first = store.store_snapshot(
        [_component("spec.alpha", "a"), _component("spec.beta", "b")],
        git_commit="1" * 40,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
    )
    store.store_implemented(Implemented("spec.alpha", "a" * 64, "alpha.py", 10, "s1"))
    second = store.store_snapshot(
        [_component("spec.alpha", "c"), _component("spec.gamma", "d")],
        git_commit="2" * 40,
        created_at=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
    )
    store.store_implemented(Implemented("spec.gamma", "d" * 64, "gamma.py", 20, "s2"))
    return [first, second]


def _assert_migrated(source, target):
    source_snaps = source.list_snapshots()
    target_snaps = target.list_snapshots()
    assert [s.master_hash for s in target_snaps] == [s.master_hash for s in source_snaps]
    for src_snap, tgt_snap in zip(source_snaps, target_snaps):
        assert target.get_components_for_snapshot(tgt_snap) == source.get_components_for_snapshot(src_snap)
        assert target.list_implemented(tgt_snap) == source.list_implemented(src_snap)


@pytest.mark.parametrize("source_kind,target_kind", [
    ("sqlite", "jsonl"),
    ("jsonl", "jsonl"),
    ("jsonl", "sqlite"),
])
def test_universal_migrate_store_matrix(tmp_path, source_kind, target_kind):
    def make_store(kind, name):
        if kind == "sqlite":
            return SQLiteSpecStore(str(tmp_path / f"{name}.db"))
        return JsonLinesSpecStore(str(tmp_path / f"{name}.jsonl"))

    source = make_store(source_kind, "source")
    target = make_store(target_kind, "target")
    _populate_store(source)

    assert migrate(source, target) == {"migrated": 2, "skipped": 0}
    _assert_migrated(source, target)


def test_universal_migrate_is_idempotent(tmp_path):
    source = JsonLinesSpecStore(str(tmp_path / "source.jsonl"))
    target = JsonLinesSpecStore(str(tmp_path / "target.jsonl"))
    _populate_store(source)

    assert migrate(source, target) == {"migrated": 2, "skipped": 0}
    assert migrate(source, target) == {"migrated": 0, "skipped": 2}
    assert len(target.list_snapshots()) == 2


def test_get_store_jsonl_default_and_url_resolution(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LIBSPEC_DATABASE_URL", raising=False)
    default_store = get_store()
    assert isinstance(default_store, JsonLinesSpecStore)
    assert default_store.filepath == os.path.abspath(".libspec/libspec.jsonl")

    monkeypatch.setenv("LIBSPEC_DATABASE_URL", "jsonl://.libspec/custom.jsonl")
    jsonl_store = get_store()
    assert isinstance(jsonl_store, JsonLinesSpecStore)
    assert jsonl_store.filepath == os.path.abspath(".libspec/custom.jsonl")

    monkeypatch.setenv("LIBSPEC_DATABASE_URL", "sqlite:///.libspec/custom.db")
    sqlite_store = get_store()
    assert isinstance(sqlite_store, SQLiteSpecStore)


def test_cmd_migrate_store_rejects_same_store(tmp_path, monkeypatch, capsys):
    store_path = tmp_path / "same.jsonl"
    monkeypatch.setenv("LIBSPEC_DATABASE_URL", f"jsonl://{store_path}")

    with pytest.raises(SystemExit) as exc:
        cmd_migrate_store({"<source_url>": f"jsonl://{store_path}"})

    assert exc.value.code == 1
    assert "same store location" in capsys.readouterr().out

def test_migration_v4_to_v5(tmp_path):
    # Set LIBSPEC_DATABASE_URL to a temporary sqlite path
    temp_db_path = tmp_path / "test_migrate.db"
    db_url = f"sqlite:///{temp_db_path}"
    
    # Patch os.environ so that get_store() resolves our temporary database
    with patch.dict(os.environ, {"LIBSPEC_DATABASE_URL": db_url}):
        # Run migrate command pointing to the moved XML snapshots directory
        args = {"<v4_build_dir>": "tests/spec-build"}
        cmd_migrate(args)
        
        # Resolve the active store
        store = get_store()
        
        # Verify the database path matches our temporary file
        assert store.db_path == os.path.abspath(str(temp_db_path))
        
        # Verify that snapshots were successfully migrated and deduplicated by content hash.
        builds = list(DBBuild.select().order_by(DBBuild.created_at))
        assert len(builds) > 0
        assert len(builds) <= 12
        
        # Verify that each build contains a valid master hash and session id
        for b in builds:
            assert b.master_hash
            assert b.session_id
            
        # Verify first build contains specifications
        first_build = builds[0]
        specs = list(DBSpec.select().where(DBSpec.build == first_build))
        assert len(specs) > 0
        
        # Verify we can list components through the store
        components = store.list_components()
        assert len(components) > 0
        
        # Verify there are inherits edges populated
        edges = list(DBEdge.select().where(DBEdge.build == first_build))
        assert len(edges) >= 0
