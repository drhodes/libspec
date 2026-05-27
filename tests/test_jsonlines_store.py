import os
import pytest
import datetime
import json
from libspec.store import (
    JsonLinesSpecStore,
    Component,
    Snapshot,
    Implemented,
    SpecStoreNotFoundError,
    SpecStoreIOError,
    SpecStoreCorruptedDataError
)

def test_jsonlines_store_basic_flow(tmp_path):
    log_file = tmp_path / "spec_log.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    assert store.current_snapshot() is None
    
    comp1 = Component(
        ref="spec.store.SQLiteStore",
        docstring="SQLite storage engine",
        is_template=False,
        inherits=["spec.store.SpecStore"],
        hash="a" * 64
    )
    comp2 = Component(
        ref="spec.store.PostgreSQLStore",
        docstring="Postgres storage engine",
        is_template=False,
        inherits=["spec.store.SpecStore"],
        hash="b" * 64
    )
    
    # Store snapshot
    created_at = datetime.datetime.now(datetime.timezone.utc)
    snap = store.store_snapshot([comp1, comp2], git_commit="c" * 40, created_at=created_at)
    
    assert snap.id is not None
    assert len(snap.id) == 16
    assert snap.git_commit == "c" * 40
    
    # Check current snapshot
    current = store.current_snapshot()
    assert current is not None
    assert current.id == snap.id
    
    # Get components
    comps = store.list_components()
    assert len(comps) == 2
    refs = [c.ref for c in comps]
    assert "spec.store.SQLiteStore" in refs
    assert "spec.store.PostgreSQLStore" in refs
    
    # Get specific component
    c = store.get_component("spec.store.SQLiteStore")
    assert c.docstring == "SQLite storage engine"
    
    with pytest.raises(SpecStoreNotFoundError):
        store.get_component("spec.nonexistent")

def test_jsonlines_store_replay_reconstruction(tmp_path):
    log_file = tmp_path / "spec_log_replay.jsonl"
    store1 = JsonLinesSpecStore(str(log_file))
    
    comp = Component(
        ref="spec.store.JsonLinesStore",
        docstring="NDJSON storage",
        is_template=False,
        inherits=[],
        hash="d" * 64
    )
    
    snap = store1.store_snapshot([comp], git_commit="e" * 40)
    
    claim = Implemented(
        ref="spec.store.JsonLinesStore",
        spec_hash="d" * 64,
        file="libspec/store.py",
        line=100,
        session_id="session-123"
    )
    store1.store_implemented(claim)
    
    # Instantiate a second store on the same file to trigger replay
    store2 = JsonLinesSpecStore(str(log_file))
    
    assert store2.current_snapshot() is not None
    assert store2.current_snapshot().id == snap.id
    
    comps = store2.list_components()
    assert len(comps) == 1
    assert comps[0].ref == "spec.store.JsonLinesStore"
    
    claims = store2.list_implemented(snap)
    assert len(claims) == 1
    assert claims[0].ref == "spec.store.JsonLinesStore"
    assert claims[0].session_id == "session-123"

def test_jsonlines_canonical_serialization(tmp_path):
    log_file = tmp_path / "spec_log_canonical.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    comp = Component(
        ref="spec.store.SQLiteStore",
        docstring="SQLite database",
        is_template=False,
        inherits=[],
        hash="a" * 64
    )
    store.store_snapshot([comp])
    
    # Read raw lines to verify canonical JSON formatting (sorted keys, compact separators, no extra spaces)
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    assert len(lines) == 2  # One snapshot record, one component record
    
    # Check that snapshot record has keys sorted alphabetically
    snap_data = json.loads(lines[0])
    keys = list(snap_data.keys())
    assert keys == sorted(keys)
    
    # Check compact serialization (no whitespace around colons/commas in raw line)
    raw_snap_line = lines[0].strip()
    assert " " not in raw_snap_line  # Except within docstring / string values, but there are no spaces in keys/values of snapshot record

def test_jsonlines_claim_deduplication(tmp_path):
    log_file = tmp_path / "spec_log_dedup.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    comp = Component(
        ref="spec.store.SQLiteStore",
        docstring="SQLite database",
        is_template=False,
        inherits=[],
        hash="a" * 64
    )
    snap = store.store_snapshot([comp])
    
    claim1 = Implemented(ref="spec.store.SQLiteStore", spec_hash="a" * 64, file="file.py", line=10)
    claim2 = Implemented(ref="spec.store.SQLiteStore", spec_hash="a" * 64, file="file.py", line=20)
    
    store.store_implemented(claim1)
    store.store_implemented(claim2)
    
    claims = store.list_implemented(snap)
    assert len(claims) == 1
    assert claims[0].line == 20  # The last recorded claim overrides prior claims

def test_jsonlines_store_idempotency_updates_current(tmp_path):
    log_file = tmp_path / "spec_log_idempotency.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    comp_a = Component(ref="A", docstring="A", is_template=False, inherits=[], hash="a"*64)
    comp_b = Component(ref="B", docstring="B", is_template=False, inherits=[], hash="b"*64)
    
    snap_a = store.store_snapshot([comp_a])
    snap_b = store.store_snapshot([comp_b])
    
    assert store.current_snapshot().id == snap_b.id
    
    # Rebuilding A should make it current again
    snap_a_v2 = store.store_snapshot([comp_a])
    
    assert snap_a_v2.id == snap_a.id
    assert store.current_snapshot().id == snap_a.id
    
    # Verify log has 3 snapshot records (A, B, A) but only 2 component records (A, B)
    with open(log_file, "r") as f:
        lines = f.readlines()
        
    snaps = [json.loads(l) for l in lines if json.loads(l)["type"] == "snapshot"]
    comps = [json.loads(l) for l in lines if json.loads(l)["type"] == "component"]
    
    assert len(snaps) == 3
    assert snaps[0]["id"] == snap_a.id
    assert snaps[1]["id"] == snap_b.id
    assert snaps[2]["id"] == snap_a.id
    
    assert len(comps) == 2
    assert comps[0]["ref"] == "A"
    assert comps[1]["ref"] == "B"

def test_jsonlines_store_errors(tmp_path):
    log_file = tmp_path / "spec_log_errors.jsonl"
    
    # Write corrupt JSON
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("{invalid_json}\n")
        
    with pytest.raises(SpecStoreCorruptedDataError):
        JsonLinesSpecStore(str(log_file))

def test_jsonlines_store_delete_snapshot(tmp_path):
    log_file = tmp_path / "spec_log_delete.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    comp_a = Component(ref="A", docstring="Doc A", is_template=False, inherits=[], hash="a"*64)
    comp_b = Component(ref="B", docstring="Doc B", is_template=False, inherits=[], hash="b"*64)
    
    snap_a = store.store_snapshot([comp_a])
    snap_b = store.store_snapshot([comp_b])
    
    assert len(store.list_snapshots()) == 2
    assert len(store.get_components_for_snapshot(snap_a)) == 1
    
    # Delete A
    store.delete_snapshot(snap_a)
    
    assert len(store.list_snapshots()) == 1
    assert store.list_snapshots()[0].id == snap_b.id
    
    # Components for A should be gone
    with pytest.raises(SpecStoreNotFoundError):
        store.get_components_for_snapshot(snap_a)
        
    # B should still be there
    assert len(store.get_components_for_snapshot(snap_b)) == 1
    assert store.get_components_for_snapshot(snap_b)[0].ref == "B"
    
    # Verify file content: it must contain the tombstone record at the end instead of removing lines
    with open(log_file, "r") as f:
        lines = f.readlines()
    tombstone_data = json.loads(lines[-1])
    assert tombstone_data.get("type") == "tombstone"
    assert tombstone_data.get("snapshot_id") == snap_a.id

def test_most_recent_hash_and_consecutive_duplicate_prevention(tmp_path):
    log_file = tmp_path / "spec_log_consecutive.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    comp_a = Component(ref="A", docstring="A", is_template=False, inherits=[], hash="a"*64)
    
    snap_1 = store.store_snapshot([comp_a], git_commit="c1")
    assert store.most_recent_hash() == snap_1.master_hash
    
    # Rebuilding identical spec immediately, even with a different git commit
    snap_2 = store.store_snapshot([comp_a], git_commit="c2")
    
    # They should be the exact same snapshot object, and NO new record should be written
    assert snap_2 == snap_1
    
    with open(log_file, "r") as f:
        lines = f.readlines()
        
    snaps = [json.loads(l) for l in lines if json.loads(l)["type"] == "snapshot"]
    # There should only be ONE snapshot record in the log file because they were consecutive duplicate builds!
    assert len(snaps) == 1
