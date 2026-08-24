# Model Context Protocol (MCP) Reference

The `libspec` MCP server hosts tools that allow LLM agents to query specifications, view diffs, search components, inspect code structures, and manage development workflows. The server implements the standard Model Context Protocol.

---

## Tool Catalog

All tools registered under the server are prefixed with the server's name: `mcp_libspec_` (or `libspec_` / unprefixed depending on client configuration).

### `diff`
Diffs specification trees natively between Git commits or against live files.
*   **Arguments**:
    *   `commit_a` (string, Optional): Older Git commit / ref (e.g. `HEAD~1`, `main`, `@1`). Defaults to `HEAD`.
    *   `commit_b` (string, Optional): Newer Git commit / ref. Defaults to live files (`PENDING`).

---

### `search`
Performs a workspace-wide search for specification components and code symbols using AST analysis.
*   **Arguments**:
    *   `query` (string, Required): The search query pattern or keyword.

---

### `list_dependencies`
Lists component dependencies for the live specification or a target Git revision.
*   **Arguments**:
    *   `commit` (string, Optional): Git commit/ref. Defaults to live spec (`PENDING`).

---

### `list_components`
Lists all specification components present in the live spec or a Git revision.
*   **Arguments**:
    *   `commit` (string, Optional): Git commit/ref. Defaults to live spec (`PENDING`).

---

### `show_component`
Shows comprehensive details of a specific component, including docstrings, parent inheritance, and implementation claims.
*   **Arguments**:
    *   `component_ref` (string, Required): Fully qualified name of the class (e.g. `spec.app.App`).
    *   `commit` (string, Optional): Git commit/ref. Defaults to live spec (`PENDING`).

---

### `peek`
Combined hover, type, and definition lookup for a python component at a specific position.
*   **Arguments**:
    *   `file_path` (string, Required): File containing the symbol.
    *   `line` (integer, Required): 1-indexed line number.
    *   `character` (integer, Required): 1-indexed character position.

---

### `usage`
Finds all semantic references and usages of a python component across the project.
*   **Arguments**:
    *   `file_path` (string, Required): File containing the target symbol.
    *   `line` (integer, Required): 1-indexed line number.
    *   `character` (integer, Required): 1-indexed character position.

---

### `symbols`
Lists all structural components (classes and methods) defined inside a specific file.
*   **Arguments**:
    *   `file_path` (string, Required): Path to target file.

---

### `start_lsp`
Starts the background Python LSP (`pylsp`) server for the workspace.
*   **Arguments**:
    *   `root_dir` (string, Optional): Root directory of workspace specs. Defaults to CWD.

---

### `pylsp_plugin`
Controls active pylsp server plugins.
*   **Arguments**:
    *   `plugin_name` (string, Required): Name of plugin (e.g. `hello_ast`).
    *   `action` (string, Optional): Status, enable, or disable. Defaults to `"status"`.

---

### `agent_workflow`
Recites the standardized 9-step developer agent workflow with client-specific prefixes.
*   **Arguments**:
    *   `agent` (string, Optional): Target agent (e.g. `antigravity`, `gemini`, `claude`).
    *   `prefix` (string, Optional): Explicit tool prefix.

