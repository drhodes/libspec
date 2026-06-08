# Design Proposal: Agent-Driven Transactional Component Dependencies

## 1. Executive Summary

This proposal outlines the design for introducing logical dependencies between specification components in `libspec` using a **Transaction-Based Append-Only Log** model. 

In this paradigm:
1. **No Source Code Pollution**: Human programmers write clean, declarative specification classes without any dependency boilerplate.
2. **Dynamic Live Diff**: The coding agent diffs and interprets the pending abstract spec directly from the workspace on-the-fly, without needing a pre-implementation database snapshot.
3. **"PENDING" Transactional Binding**: The coding agent records dependencies and implementation claims during development using a placeholder `"PENDING"` snapshot ID.
4. **VCS Binding at Commit**: When the developer commits their changes, the Git `post-commit` hook compiles the new snapshot. The replay engine dynamically binds all preceding `"PENDING"` log events to this new Snapshot ID.
5. **Halt & Abort Protection**: If an implementation is aborted mid-way, pending dependency declarations and claims are safely removed from the log.

---

## 2. The Lifecycle Workflow & Git Integration

The specification lifecycle operates without a separate build step before implementation. Instead, dependencies and implementation claims are written dynamically as part of the live ("PENDING") session:

```
Step 1: Edit Specification
  └─ Human or agent edits python-native specs in `spec/*.py`.

Step 2: Diff Analysis
  └─ Agent runs `libspec diff`.
  └─ This compiles and interprets the pending abstract spec in-memory on-the-fly.

Step 3: Dependency Discovery & Log Recording (New)
  └─ Agent determines logical dependencies between components in the pending spec.
  └─ Agent appends `dependency` records referencing `"PENDING"` as the snapshot_id to the log.

Step 4: Code Generation / Implementation (Can be halted here)
  └─ Agent writes code matching the specs in sequence.
  └─ Agent appends `implemented` claims referencing `"PENDING"` as the snapshot_id to the log.
  └─ [If halted]: Reverts all pending entries (by discarding uncommitted Git changes).

Step 5: Git Commit & Post-Commit Hook Linking
  └─ Developer or agent runs `git commit`.
  └─ Git `post-commit` hook runs, compiles the live spec on-the-fly, and appends the following three record types to `libspec.jsonl`:
      1. `component` records: For any newly introduced spec components.
      2. `snapshot` record: Storing the compiled master hash and linking it to the Git commit hash.
      3. `vcs_link` record: Formalizing the relationship between the Snapshot ID and VCS revision.
  └─ The store automatically binds all preceding `"PENDING"` dependency and implemented events to this new Snapshot ID.
```

---

## 3. Transaction Log Event Schema

We introduce a new event type, `"dependency"`, to the append-only ledger. During the development cycle, the agent uses `"PENDING"` as the `snapshot_id`:

#### Pending Log Entry JSON Format
```json
{
  "type": "dependency",
  "snapshot_id": "PENDING",
  "ref": "spec.cli.DiffCommand",
  "depends_on": "spec.diff.DiffEngine",
  "created_at": "2026-06-08T14:26:43Z"
}
```

---

## 4. Replay State Machine & Binding Engine

Since the log is append-only, placeholder `"PENDING"` records are preserved literally on disk. The replay engine and compaction process resolve this dynamically.

### 4.1 Chronological Replay Binding (`libspec/stores/json_lines.py`)

During log replay, any event with `snapshot_id: "PENDING"` is collected into a temporary list. When the engine encounters the *next* `"type": "snapshot"` event, it automatically binds all collected pending events to that snapshot's ID:

```python
# Conceptual replay logic in JsonLinesSpecStore
def _replay(self):
    self._snapshots = []
    self._snapshot_dependencies = {}   # snapshot_id -> dict[ref -> list[str]]
    self._snapshot_implemented = {}    # snapshot_id -> dict[ref -> Implemented]
    
    pending_dependencies = []
    pending_implemented = []

    with open(self.filepath, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            rec_type = data.get("type")

            if rec_type == "dependency":
                snap_id = data["snapshot_id"]
                ref = data["ref"]
                dep = data["depends_on"]
                
                if snap_id == "PENDING":
                    pending_dependencies.append((ref, dep))
                else:
                    self._add_dependency(snap_id, ref, dep)

            elif rec_type == "implemented":
                snap_id = data["snapshot_id"]
                record = Implemented(**data)
                
                if snap_id == "PENDING":
                    pending_implemented.append(record)
                else:
                    self._add_implemented(snap_id, record)

            elif rec_type == "snapshot":
                snapshot = Snapshot(...)
                self._snapshots.append(snapshot)
                
                # Dynamic Binding: Bind all accumulated "PENDING" events to this new snapshot
                for ref, dep in pending_dependencies:
                    self._add_dependency(snapshot.id, ref, dep)
                for record in pending_implemented:
                    self._add_implemented(snapshot.id, record)
                    
                pending_dependencies.clear()
                pending_implemented.clear()
```

### 4.2 Compaction Resolution (`compact`)
When `libspec compact` executes:
- It processes the log events and resolves all `"PENDING"` records to their bound `snapshot_id` values in memory.
- It writes the clean, fully resolved `snapshot_id` to the compacted log file, eliminating all `"PENDING"` references for historical records.

---

## 5. Storage & Persistence Changes

### 5.1 SpecStore Protocol (`libspec/store.py`)

We expand the backend-agnostic storage protocol with two actions:
1. `store_dependency`: Appends a dependency declaration to the log.
2. `list_dependencies`: Retrieves all declared dependencies for a specific snapshot.

```python
class SpecStore(Protocol):
    # ... existing methods ...

    def store_dependency(self, ref: str, depends_on: str, snapshot_id: str = "PENDING") -> None:
        '''Appends a dependency record establishing that 'ref' depends on 'depends_on'.
        Defaults to "PENDING" for active implementation sessions.
        '''
        ...

    def list_dependencies(self, snapshot: Snapshot) -> Dict[str, List[str]]:
        '''Retrieves a mapping of component FQNs to their lists of dependencies
        for the given snapshot.
        '''
        ...
```

---

## 6. Handling Halted Implementations & Rollbacks

If an implementation task is aborted or halted mid-way, all pending declarations must be cleanly stripped to prevent log pollution.

### Strategy: Git-Native Discard
Because `libspec.jsonl` is tracked under Git, any uncommitted `"PENDING"` snapshot, dependency, or implementation records appended during a local session are automatically cleaned up if the developer discards local changes:
```bash
git checkout -- .libspec/libspec.jsonl
# or
git reset --hard
```
This instantly reverts the transaction log to the last committed snapshot state, removing all pending entries.

---

## 7. MCP Server Integration

We expose the new operations as MCP tools to make them easily accessible to the coding agent during planning:

### 7.1 Tool: `declare_dependency`
Allows the agent to declare a dependency before starting implementation.
```python
@mcp.tool()
def declare_dependency(component_ref: str, depends_on_ref: str, snapshot_id: str = "PENDING") -> str:
    """
    Declare that component_ref depends on depends_on_ref.
    Defaults to snapshot_id='PENDING' for the active development session.
    """
    try:
        store = get_store()
        store.store_dependency(component_ref, depends_on_ref, snapshot_id)
        return f"Successfully recorded dependency: {component_ref} depends on {depends_on_ref}"
    except Exception as e:
        return f"Error recording dependency: {e}"
```

### 7.2 Tool: `list_dependencies`
Allows the agent or human to query the dependencies for a given snapshot (defaults to active).
```python
@mcp.tool()
def list_dependencies(snapshot_id: str = None) -> str:
    """
    List all recorded component dependencies for a given snapshot.
    """
    # ... resolves snapshot and queries store.list_dependencies(snap) ...
```
