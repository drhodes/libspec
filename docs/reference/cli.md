# Command-Line Interface (CLI) Reference

The `libspec` package installs a unified global command-line entry point: `libspec`. In project workspaces, always run using the `uv run` command runner to ensure the correct environment bindings are loaded.

---

## Global Commands

### `init`
Initializes a new `libspec` workspace context in the current working directory.
```bash
uv run libspec init
```
*   **Creates**: `spec/` blueprint folder, `.libspec/` metadata marker.
*   **Installs**: Automated Git post-commit hooks for VCS snapshot linking.

---

### `diff`
Diffs specification snapshots natively.
```bash
uv run libspec diff [snapshot_a] [snapshot_b]
```
*   **No arguments**: Compiles live spec files on-the-fly (`PENDING`) and diffs them against the latest recorded snapshot in the database (`#0`).
*   **One argument**: Diffs the specified snapshot against `#0`.
*   **Two arguments**: Diffs `snapshot_a` against `snapshot_b`.

---

### `link`
Links a specification snapshot to a specific Version Control System (VCS) revision.
```bash
uv run libspec link --revision <rev_hash> [options]
```
*   `--revision <text>`: **(Required)** The unique revision identifier (e.g. Git commit SHA).
*   `--snapshot <text>`: The 16-character hexadecimal target snapshot identifier. If omitted, links all unlinked snapshots in the store.
*   `--vcs <text>`: The VCS type (defaults to `git`).
*   `--metadata <key=value>`: Scoped context metadata. Can be provided multiple times.
*   `--only-on-changes`: Only perform compilation and linking if the revision changed files within the `spec/` path or implementation code.

---

### `list`
List all specification components present in a target snapshot.
```bash
uv run libspec list [-s <snapshot_id>]
```
*   `-s, --snapshot <text>`: Target snapshot ID or relative index prefix. Defaults to latest.

---

### `show`
Displays full structured details of a target component.
```bash
uv run libspec show <component_ref> [-s <snapshot_id>]
```
*   `<component_ref>`: **(Required)** The fully qualified name (FQN) of the component class (e.g. `spec.app.App`).
*   `-s, --snapshot <text>`: Target snapshot ID. Defaults to latest.

---

### `search`
Searches spec component names and class docstrings.
```bash
uv run libspec search <query> [-s <snapshot_id>]
```
*   `<query>`: **(Required)** The text search keyword.
*   `-s, --snapshot <text>`: Target snapshot ID. Defaults to latest.

---

### `list-snapshots`
Lists chronological snapshot build history recorded in the transaction store.
```bash
uv run libspec list-snapshots
```

---

### `log`
Displays the chronological `SpecStore` append-only event ledger.
```bash
uv run libspec log
```

---

### `compact`
Compacts the specification database, squashing intermediate unlinked drafts and merging VCS links to reclaim storage space.
```bash
uv run libspec compact [--dry-run]
```
*   `--dry-run`: Runs calculation of space savings without modifying files on disk.

---

### `declare-dependency`
Declares a logical dependency between components.
```bash
uv run libspec declare-dependency <dependent_ref> <depends_on_ref> [-s <snapshot_id>]
```
*   `-s, --snapshot <text>`: Scopes the link to a target snapshot or `PENDING` (default).

---

### `dependencies`
Lists component dependencies recorded for the target snapshot.
```bash
uv run libspec dependencies [-s <snapshot_id>]
```
*   `-s, --snapshot <text>`: Defaults to `PENDING`.

---

### `agent-config` (alias: `mcp_agent`)
Configures an LLM coding assistant agent for the local project.
```bash
uv run libspec agent-config <agent_name> [project_root] [--list]
```
*   `--list`: Lists all supported agents.
*   `<agent_name>`: Name of target agent (e.g. `antigravity`, `claude`).
*   `[project_root]`: Path to local project directory. Defaults to CWD.

---

### `mcp`
Launches the Model Context Protocol (MCP) server over standard input/output (stdio).
```bash
uv run libspec mcp
```
*   *Note: This command is usually invoked in the background by IDEs or agent runtimes rather than executed manually by human developers.*

---

### `repl`
Launches the interactive prompt REPL console.
```bash
uv run libspec repl
```

---

### `rm-snapshot`
Permanently deletes (tombstones) a historical snapshot from the active list.
```bash
uv run libspec rm-snapshot <snapshot_id>
```

---

### `restore-snapshot`
Restores a previously deleted/tombstoned historical snapshot back to the active log.
```bash
uv run libspec restore-snapshot <snapshot_id>
```
