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

def test_jsonlines_store_errors(tmp_path):
    log_file = tmp_path / "spec_log_errors.jsonl"
    
    # Write corrupt JSON
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("{invalid_json}\n")
        
    with pytest.raises(SpecStoreCorruptedDataError):
        JsonLinesSpecStore(str(log_file))
