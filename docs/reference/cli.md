# Command-Line Interface (CLI) Reference

The `libspec` package installs a unified global command-line entry point: `libspec`. In project workspaces, always run using the `uv run` command runner to ensure the correct environment bindings are loaded.

---

## Global Commands

### `init`
Initializes a new `libspec` workspace context in the current working directory.
```bash
uv run libspec init
```
*   **Creates**: `spec/` blueprint folder, `.libspec/` configuration directory with `workflow.yaml`, and `.agents/` workspace agent skills.
*   **Installs**: Default agent skill at `.agents/skills/libspec/SKILL.md`.

---

### `diff`
Diffs specification trees natively between Git commits.
```bash
uv run libspec diff [commit_a] [commit_b]
```
*   **No arguments**: Compiles live spec files on-the-fly (`PENDING`) and diffs them against `HEAD`.
*   **One argument**: Diffs the specified Git commit or build index (e.g. `#1`) against `HEAD`.
*   **Two arguments**: Diffs `commit_a` against `commit_b`.

---

### `dependencies`
Lists component dependencies recorded in specifications.
```bash
uv run libspec dependencies [-c <commit_ref>]
```
*   `-c, --commit <text>`: Git commit/ref. Defaults to live spec.
*   Shows logical dependency hierarchies declared via `depends_on`.

---

### `list`
List all specification components present in the live spec or a Git revision.
```bash
uv run libspec list [-c <commit_ref>]
```
*   `-c, --commit <text>`: Git commit/ref. Defaults to live spec.

---

### `show`
Displays full structured details of a target component.
```bash
uv run libspec show <component_ref> [-c <commit_ref>]
```
*   `<component_ref>`: **(Required)** The fully qualified name (FQN) of the component class (e.g. `spec.app.App`).
*   `-c, --commit <text>`: Git commit/ref. Defaults to live spec.

---

### `search`
Searches spec component names and class docstrings.
```bash
uv run libspec search <query> [-c <commit_ref>]
```
*   `<query>`: **(Required)** The text search keyword.
*   `-c, --commit <text>`: Git commit/ref. Defaults to live spec.

---

### `log`
Displays the Git commit history of the specifications (`spec/` directory).
```bash
uv run libspec log
```

---

### `agent-workflow`
Recites the standardized 9-step developer agent workflow.
```bash
uv run libspec agent-workflow [--agent <agent_name>] [--prefix <prefix>]
```
*   `--agent <text>`: Target agent platform (e.g. `antigravity`, `gemini`, `claude`).
*   `--prefix <text>`: Explicit MCP tool prefix.

---

### `agent-config` (alias: `mcp_agent`)
Configures an LLM coding assistant agent for the local project.
```bash
uv run libspec agent-config <agent_name> [project_root] [--list]
```
*   `--list`: Lists all supported agents.
*   `<agent_name>`: Name of target agent (e.g. `antigravity`, `gemini`, `claude`, `opencode`, `copilot`, `codex`, `agents`).
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

### `completion`
Outputs shell completion scripts for Bash, Zsh, or Fish.
```bash
uv run libspec completion [bash|zsh|fish]
```

