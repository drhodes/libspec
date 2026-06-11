# Model Context Protocol (MCP) Reference

The `libspec` MCP server hosts tools that allow LLM agents to query the specification ledger, view diffs, search components, and manage logical dependencies. The server implements the standard Model Context Protocol.

---

## Tool Catalog

All tools registered under the server are prefixed with the server's name: `mcp_libspec_`.

### `mcp_libspec_search`
Performs a workspace-wide semantic search for components (classes, methods, variables). It merges results from native specification analysis with LSP symbol discovery.
*   **Arguments**:
    *   `query` (string, Required): The search query pattern or keyword.

---

### `mcp_libspec_diff`
Diffs specification snapshots natively.
*   **Arguments**:
    *   `snapshot_a` (string, Optional): The older snapshot ID. Defaults to `#0`.
    *   `snapshot_b` (string, Optional): The newer snapshot ID. Defaults to `PENDING` (live files).

---

### `mcp_libspec_list_snapshots`
Lists all recorded specification snapshots in the ledger chronologically.
*   **Arguments**: None

---

### `mcp_libspec_list_components`
Lists all specification components present in a given snapshot.
*   **Arguments**:
    *   `snapshot_id` (string, Optional): The explicit 16-character snapshot hash/ID prefix. Defaults to latest.

---

### `mcp_libspec_show_component`
Shows comprehensive details of a specific component, including docstrings, parent inheritance, and verification claims.
*   **Arguments**:
    *   `component_ref` (string, Required): Fully qualified name of the class (e.g. `spec.app.App`).
    *   `snapshot_id` (string, Optional): The explicit snapshot ID or prefix. Defaults to latest.

---

### `mcp_libspec_get_log`
Retrieves the chronological append-only event log of the spec database.
*   **Arguments**: None

---

### `mcp_libspec_link_snapshot`
Links a spec snapshot to a Version Control System (VCS) revision.
*   **Arguments**:
    *   `snapshot_id` (string, Required): The target snapshot hash.
    *   `vcs` (string, Required): The VCS type, e.g. `"git"`.
    *   `revision` (string, Required): The commit hash or revision code.
    *   `metadata` (object, Optional): Key-value pairs of metadata context.

---

### `mcp_libspec_compact_store`
Compacts the SpecStore database log, pruning intermediate drafts and optimizing storage.
*   **Arguments**:
    *   `dry_run` (boolean, Optional): Whether to dry-run the compaction. Defaults to `false`.

---

### `mcp_libspec_delete_snapshot`
Permanently deletes (tombstones) a historical snapshot from the active list.
*   **Arguments**:
    *   `snapshot_id` (string, Required): The target snapshot hash.

---

### `mcp_libspec_restore_snapshot`
Restores a previously deleted/tombstoned historical snapshot.
*   **Arguments**:
    *   `snapshot_id` (string, Required): The target snapshot hash.

---

### `mcp_libspec_declare_dependency`
Declares a logical dependency between two specification components.
*   **Arguments**:
    *   `ref` (string, Required): The FQN of the dependent component.
    *   `depends_on` (string, Required): The FQN of the component it depends on.
    *   `snapshot_id` (string, Optional): Target snapshot ID. Defaults to `"PENDING"`.

---

### `mcp_libspec_list_dependencies`
List component dependencies recorded for a snapshot.
*   **Arguments**:
    *   `snapshot_id` (string, Optional): Snapshot ID or prefix. Defaults to `"PENDING"`.

---

### `mcp_libspec_start_lsp`
Starts the background Python LSP (`pylsp`) server for the workspace.
*   **Arguments**:
    *   `root_dir` (string, Optional): Root directory of workspace specs. Defaults to CWD.

---

### `mcp_libspec_peek`
Combined hover, type, and definition lookup for a python component at a specific position.
*   **Arguments**:
    *   `file_path` (string, Required): File containing the symbol.
    *   `line` (integer, Required): 1-indexed line number.
    *   `character` (integer, Required): 1-indexed character position.

---

### `mcp_libspec_usage`
Finds all semantic references and usages of a python component.
*   **Arguments**:
    *   `file_path` (string, Required): File containing the target symbol.
    *   `line` (integer, Required): 1-indexed line number.
    *   `character` (integer, Required): 1-indexed character position.

---

### `mcp_libspec_symbols`
Lists all structural components (classes and methods) defined inside a specific file.
*   **Arguments**:
    *   `file_path` (string, Required): Path to target file.

---

### `mcp_libspec_pylsp_plugin`
Controls any active pylsp server plugins.
*   **Arguments**:
    *   `plugin_name` (string, Required): Name of plugin (e.g. `hello_ast`).
    *   `action` (string, Optional): Status, enable, or disable. Defaults to `"status"`.

---

### `mcp_libspec_set_pylsp_plugin_setting`
Sets an configuration parameter dynamically for a pylsp plugin.
*   **Arguments**:
    *   `plugin_name` (string, Required): Target plugin name.
    *   `setting_name` (string, Required): Setting key name.
    *   `value` (string, Required): Setting value to apply.
