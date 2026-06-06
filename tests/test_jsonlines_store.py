import os
import pytest
import datetime
import json
from libspec.store import (
    JsonLinesSpecStore,
    Component,
    Implemented,
    SpecStoreNotFoundError,
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
        
    snaps = [json.loads(line_str) for line_str in lines if json.loads(line_str)["type"] == "snapshot"]
    comps = [json.loads(line_str) for line_str in lines if json.loads(line_str)["type"] == "component"]
    
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
        
    snaps = [json.loads(line_str) for line_str in lines if json.loads(line_str)["type"] == "snapshot"]
    # There should only be ONE snapshot record in the log file because they were consecutive duplicate builds!
    assert len(snaps) == 1

def test_jsonlines_store_vcs_linking(tmp_path):
    log_file = tmp_path / "spec_log_vcs.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    comp = Component(
        ref="spec.store.SQLiteStore",
        docstring="SQLite database",
        is_template=False,
        inherits=[],
        hash="a" * 64
    )
    snap = store.store_snapshot([comp], git_commit="legacy_commit")
    assert snap.git_commit == "legacy_commit"
    
    # Store a late-bound VCS link
    store.store_vcs_link(snap.id, vcs="git", revision="new_resolved_commit", metadata={"branch": "main"})
    
    # Re-read/replay state using a fresh store instance on the same file
    store2 = JsonLinesSpecStore(str(log_file))
    current = store2.current_snapshot()
    assert current is not None
    assert current.id == snap.id
    # Ensure late-bound vcs_link has successfully overridden the legacy/parent commit hash!
    assert current.git_commit == "new_resolved_commit"


def test_jsonlines_store_get_raw_events(tmp_path):
    log_file = tmp_path / "spec_log_raw_events.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    comp = Component(ref="A", docstring="Doc A", is_template=False, inherits=[], hash="a"*64)
    _snap = store.store_snapshot([comp])
    
    events = store.get_raw_events()
    assert len(events) >= 2
    assert events[0]["type"] == "snapshot"
    assert events[1]["type"] == "component"


def test_jsonlines_compaction_squashing(tmp_path):
    log_file = tmp_path / "spec_log_compaction.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    # 1. Create multiple intermediate snapshots for commit 'commit_1'
    comp_a = Component(ref="A", docstring="Doc A", is_template=False, inherits=[], hash="a"*64)
    comp_b = Component(ref="B", docstring="Doc B", is_template=False, inherits=[], hash="b"*64)
    
    _snap1 = store.store_snapshot([comp_a], git_commit="commit_1")
    # Add a slight delay or force different created_at
    import time
    time.sleep(0.01)
    snap2 = store.store_snapshot([comp_a, comp_b], git_commit="commit_1")
    
    assert len(store.list_snapshots()) == 2
    
    # 2. Run compaction in dry-run mode
    dry_res = store.compact(dry_run=True)
    assert dry_res["pruned_snapshots_count"] == 1
    assert dry_res["reclaimed_bytes"] > 0
    # Filesystem remains unchanged in dry-run
    assert len(store.list_snapshots()) == 2
    
    # 3. Run actual compaction
    res = store.compact(dry_run=False)
    assert res["pruned_snapshots_count"] == 1
    assert res["reclaimed_bytes"] > 0
    
    # 4. Assert survivors and cleanup
    snaps = store.list_snapshots()
    assert len(snaps) == 1
    assert snaps[0].id == snap2.id  # Chronological latest is survivor
    assert len(store.get_components_for_snapshot(snaps[0])) == 2


def test_jsonlines_cas_deduplication(tmp_path):
    log_file = tmp_path / "spec_log_cas.jsonl"
    store = JsonLinesSpecStore(str(log_file))
    
    comp_a = Component(ref="A", docstring="Doc A", is_template=False, inherits=[], hash="a"*64)
    comp_b = Component(ref="B", docstring="Doc B", is_template=False, inherits=[], hash="b"*64)
    
    # First snapshot: has A
    store.store_snapshot([comp_a], git_commit="c1")
    # Second snapshot: has A and B
    store.store_snapshot([comp_a, comp_b], git_commit="c2")
    
    # Read raw lines to count components
    with open(log_file, "r", encoding="utf-8") as f:
        events = [json.loads(line_str) for line_str in f]
        
    component_events = [e for e in events if e.get("type") == "component"]
    # Even though A is in both snapshots, it should only be written once due to CAS!
    assert len(component_events) == 2  # one for A, one for B


def test_jsonlines_legacy_migration(tmp_path):
    log_file = tmp_path / "spec_log_legacy.jsonl"
    
    mock_hash = "a" * 64
    mock_hash = "a" * 64
    comp_hash = "b" * 64
    # Write a simulated legacy log with legacy format snapshot (no 'components' manifest, component has snapshot_id)
    legacy_lines = [
        f'{{"type":"snapshot","id":"legacy_snap_1","created_at":"2026-06-01T00:00:00Z","master_hash":"{mock_hash}","git_commit":"c1"}}',
        f'{{"type":"component","snapshot_id":"legacy_snap_1","ref":"A","docstring":"Doc A","is_template":false,"inherits":[],"hash":"{comp_hash}"}}',
        f'{{"type":"implemented","snapshot_id":"legacy_snap_1","ref":"A","spec_hash":"{comp_hash}","file":"impl.py","line":10}}'
    ]
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("\n".join(legacy_lines) + "\n")
        
    # Replay under legacy-compatible engine
    store = JsonLinesSpecStore(str(log_file), auto_upgrade=False)
    
    snaps = store.list_snapshots()
    assert len(snaps) == 1
    assert snaps[0].id == "legacy_snap_1"
    
    comps = store.get_components_for_snapshot(snaps[0])
    assert len(comps) == 1
    assert comps[0].ref == "A"
    
    # Perform compact to migrate/upgrade the file automatically
    res = store.compact(dry_run=False)
    assert res["upgraded_legacy_format"] is True
    
    # Assert backup was created
    backup_file = tmp_path / "spec_log_legacy.jsonl.bak"
    assert backup_file.exists()
    
    # Verify new migrated format has components manifest and CAS structure
    with open(log_file, "r", encoding="utf-8") as f:
        migrated_events = [json.loads(line_str) for line_str in f]
        
    snap_event = next(e for e in migrated_events if e.get("type") == "snapshot")
    assert "components" in snap_event
    assert snap_event["components"]["A"] == comp_hash
    
    comp_event = next(e for e in migrated_events if e.get("type") == "component")
    assert "snapshot_id" not in comp_event  # Upgraded to pure CAS


def test_jsonlines_vcs_link_sidecar_isolation(tmp_path):
    # 1. Initialize store in a temp directory
    store_dir = tmp_path / ".libspec"
    log_file = store_dir / "libspec.jsonl"
    
    store = JsonLinesSpecStore(str(log_file))
    
    # Verify .gitignore was automatically created inside the store directory
    # REQUIREMENT-ID: spec.store_compaction.AutomatedIgnoreConfiguration
    gitignore = store_dir / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text(encoding="utf-8")
    assert "vcs_links.jsonl" in content
    assert "*.bak" in content

    # 2. Store a snapshot to the main tracked database log file
    comp_a = Component(ref="A", docstring="Doc A", is_template=False, inherits=[], hash="a"*64)
    snap = store.store_snapshot([comp_a], git_commit="PENDING")
    
    # Main log file should now contain snapshot and component events
    assert log_file.exists()
    assert os.path.getsize(log_file) > 0
    
    # 3. Store a late-bound VCS link
    # REQUIREMENT-ID: spec.store_compaction.UntrackedSidecarStore
    store.store_vcs_link(snap.id, vcs="git", revision="my_revision_123")
    
    # Verify the vcs_link event was written strictly to the sidecar vcs_links.jsonl file
    sidecar_file = store_dir / "vcs_links.jsonl"
    assert sidecar_file.exists()
    assert os.path.getsize(sidecar_file) > 0
    
    # Verify that the main tracked file remained unchanged by the link operation
    with open(log_file, "r", encoding="utf-8") as f:
        main_events = [json.loads(line) for line in f if line.strip()]
    assert not any(e.get("type") == "vcs_link" for e in main_events)
    
    # Verify that the sidecar file contains the vcs_link event
    with open(sidecar_file, "r", encoding="utf-8") as f:
        sidecar_events = [json.loads(line) for line in f if line.strip()]
    assert len(sidecar_events) == 1
    assert sidecar_events[0]["type"] == "vcs_link"
    assert sidecar_events[0]["revision"] == "my_revision_123"

    # 4. Initialize a new store instance to test replay merging both files
    # REQUIREMENT-ID: spec.store_compaction.UnifiedSidecarReplay
    new_store = JsonLinesSpecStore(str(log_file))
    replayed_snaps = new_store.list_snapshots()
    assert len(replayed_snaps) == 1
    assert replayed_snaps[0].git_commit == "my_revision_123"  # Merged successfully!

    # 5. Run compaction and assert consolidation
    store.compact(dry_run=False)
    
    # Verify sidecar file has been truncated/emptied after consolidation
    assert os.path.getsize(sidecar_file) == 0
    
    # Verify the vcs_link event was successfully consolidated into the main log file
    with open(log_file, "r", encoding="utf-8") as f:
        consolidated_events = [json.loads(line) for line in f if line.strip()]
    
    link_event = next(e for e in consolidated_events if e.get("type") == "vcs_link")
    assert link_event["revision"] == "my_revision_123"


def test_jsonlines_self_healing_auto_migration(tmp_path):
    log_file = tmp_path / "spec_log_self_heal.jsonl"
    
    mock_hash = "a" * 64
    comp_hash = "b" * 64
    
    # Legacy lines with old-style snapshot (no components dictionary)
    legacy_lines = [
        f'{{"type":"snapshot","id":"heal_snap_1","created_at":"2026-06-01T00:00:00Z","master_hash":"{mock_hash}","git_commit":"c1"}}',
        f'{{"type":"component","snapshot_id":"heal_snap_1","ref":"A","docstring":"Doc A","is_template":false,"inherits":[],"hash":"{comp_hash}"}}'
    ]
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("\n".join(legacy_lines) + "\n")
        
    # Initialize with default auto_upgrade=True
    # REQUIREMENT-ID: spec.store_compaction.SelfHealingAutoMigration
    store = JsonLinesSpecStore(str(log_file), auto_upgrade=True)
    
    # 1. Assert backup copy was created
    backup_file = tmp_path / "spec_log_self_heal.jsonl.bak"
    assert backup_file.exists()
    
    # 2. Assert log file was silently and atomically upgraded
    with open(log_file, "r", encoding="utf-8") as f:
        migrated_events = [json.loads(line) for line in f if line.strip()]
        
    # Check that snapshot now has components manifest dictionary
    snap_event = next(e for e in migrated_events if e.get("type") == "snapshot")
    assert "components" in snap_event
    assert snap_event["components"] == {"A": comp_hash}
    
    # Check that component was safely written content-addressably (CAS)
    comp_event = next(e for e in migrated_events if e.get("type") == "component")
    assert "snapshot_id" not in comp_event
    assert comp_event["hash"] == comp_hash
    
    # 3. Assert store state holds the upgraded components correctly
    snaps = store.list_snapshots()
    assert len(snaps) == 1
    assert snaps[0].id == "heal_snap_1"
    
    comps = store.get_components_for_snapshot(snaps[0])
    assert len(comps) == 1
    assert comps[0].ref == "A"


def test_jsonlines_store_cas_renamed_components(tmp_path):
    log_file = tmp_path / "spec_log_rename.jsonl"
    store = JsonLinesSpecStore(str(log_file))

    # 1. Create a component with original ref and docstring
    comp_old = Component(
        ref="spec.store.OldComponent",
        docstring="Shared docstring text",
        is_template=False,
        inherits=[],
        hash="a" * 64
    )
    snap_old = store.store_snapshot([comp_old], git_commit="commit_1")

    # 2. Rename it, keeping the docstring and hash identical
    comp_new = Component(
        ref="spec.store.NewComponent",
        docstring="Shared docstring text",
        is_template=False,
        inherits=[],
        hash="a" * 64
    )
    snap_new = store.store_snapshot([comp_new], git_commit="commit_2")

    # Replay in a new store instance to ensure it gets correctly reconstructed from the JSONL log
    store2 = JsonLinesSpecStore(str(log_file))

    # 3. Retrieve components from the first snapshot
    comps_old = store2.get_components_for_snapshot(snap_old)
    assert len(comps_old) == 1
    assert comps_old[0].ref == "spec.store.OldComponent"

    # 4. Retrieve components from the second snapshot
    comps_new = store2.get_components_for_snapshot(snap_new)
    assert len(comps_new) == 1
    assert comps_new[0].ref == "spec.store.NewComponent"






