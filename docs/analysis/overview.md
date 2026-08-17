# libspec — Architectural Overview

> **Version**: 10.3.2  
> **Language**: Python 3.12+  
> **License**: GPL-3.0-or-later

---

## 1. What is libspec?

`libspec` is a **spec-driven development library** designed to help software teams (and LLM coding agents) work with structured, versioned software specifications. Specifications are written as ordinary Python class hierarchies, compiled into structured data (`Component` objects) and optionally into XML, and then used to drive the implementation lifecycle.

The core insight is: **specifications are code**. They live alongside source code in version control, are diffable at the requirement level, and can be consumed by AI coding agents through a standard MCP (Model Context Protocol) interface.

---

## 2. Repository Structure

```
libspec/
├── libspec/          # Main Python package (the library)
│   ├── spec.py       # Core engine: Spec (orchestrator) + Ctx (spec base class)
│   ├── spec_types.py # Built-in vocabulary: Feature, Requirement, API, DataSchema, …
│   ├── common.py     # Frozen dataclasses: Component, Snapshot, Implemented
│   ├── store.py      # Store error types (SpecStore has been removed — Git-native only)
│   ├── util.py       # compile_live_spec, compile_git_spec, find_implementations_in_workspace
│   ├── spec_diff.py  # Native specification diff engine (Component-level)
│   ├── cli.py        # click-based CLI (init, diff, list, show, search, mcp, repl, …)
│   ├── repl.py       # Interactive specification inspector REPL (prompt_toolkit)
│   ├── mcp_server.py # FastMCP server exposing spec tools to AI agents
│   ├── agent_config.py # Configures AI agent integrations (Claude, Gemini, Copilot, etc.)
│   ├── workflow.py   # Returns the standardised 8-step developer agent workflow
│   ├── watcher.py    # Linux inotify-based file-change watcher (used by REPL)
│   ├── colors.py     # Terminal color/theme constants
│   └── err.py        # UnimplementedMethodError
├── spec/             # libspec's own self-specification (dogfooding)
│   ├── main_spec.py  # Root MainSpec(Spec) listing all spec modules
│   ├── app.py        # Top-level requirements
│   ├── core.py       # Specs for Ctx / Spec engine
│   ├── types.py      # Specs for built-in vocabulary
│   ├── err.py        # Error-handling specs (Req / Feat base classes)
│   └── …
└── tests/            # pytest test suite
```

---

## 3. Core Concepts

### 3.1 Specifications as Python Classes

A *specification* is a Python class that:

1. Inherits (directly or transitively) from `Ctx`.
2. Has a **docstring** — either plain text or a **Jinja2 template**.
3. May define **methods** that supply values for template variables.
4. May inherit from other `Ctx` subclasses to form a requirement hierarchy.

```python
# Example project specification (lives in spec/app.py)
from libspec import Requirement, Feature

class MustBeFast(Requirement):
    """
    TITLE: Performance Requirement
    REQUIREMENT-ID: spec.app.MustBeFast
    The system MUST respond to any user request within {{max_ms}} ms.
    """
    def max_ms(self):
        return 200

class UserDashboard(Feature, MustBeFast):
    """The user dashboard must display a real-time feed."""
```

### 3.2 Spec (Orchestrator)

`Spec` is the top-level orchestrator. Users subclass it and implement `modules()`:

```python
class MainSpec(Spec):
    def modules(self):
        return [app, core, types]
```

`Spec` walks all modules, instantiates every `Ctx` subclass, and either:
- **`get_components()`** — returns a flat list of `Component` frozen dataclasses.
- **`generate_xml()`** / **`write_xml()`** — serialises to a structured XML document.

### 3.3 Component (Data Artefact)

Each compiled spec class produces a `Component`:

| Field | Description |
|-------|-------------|
| `ref` | Fully-qualified class name (`spec.app.MustBeFast`) |
| `docstring` | Rendered (Jinja2) specification text |
| `is_template` | True if the docstring contained `{{ }}` or `{% %}` |
| `inherits` | List of FQNs of parent Ctx classes with docstrings |
| `hash` | SHA-256 of the rendered docstring (content fingerprint) |
| `is_dependency` | True for inherited classes not defined in the project's own modules |

### 3.4 Git-Native Versioning

libspec has **no database**. Versioning relies entirely on Git:

- `compile_live_spec()` — imports the `spec/` directory on disk.
- `compile_git_spec(ref)` — extracts `spec/` from a Git archive at `ref` into a tempdir and compiles it.
- Results are cached in `.libspec/cache/` using a SHA-256 fingerprint to avoid redundant recompilation.

### 3.5 Native Spec Diff

`spec_diff.generate_native_patch()` compares two sets of `Component` lists:

- **NEW**: component present in new but not old.
- **REMOVED**: component present in old but not new.
- **CHANGED**: hash differs; performs recursive inheritance diff.

Changes are printed as a human-readable unified-diff-style patch at the requirement level.

---

## 4. Entry Points

### 4.1 CLI (`libspec`)

Implemented with `click`. Key commands:

| Command | Purpose |
|---------|---------|
| `libspec init` | Scaffold a new `spec/` directory with boilerplate |
| `libspec diff [A] [B]` | Native spec diff (defaults to HEAD vs live) |
| `libspec list [-c ref]` | List all components (live or at a Git ref) |
| `libspec show <ref>` | Inspect a single component and its implementation claims |
| `libspec search <query>` | Full-text search across refs and docstrings |
| `libspec log` | Git commit history of the `spec/` directory |
| `libspec dependencies` | Show component inheritance graph |
| `libspec repl` | Launch the interactive specification REPL |
| `libspec mcp` | Start the MCP server (stdio transport) |
| `libspec agent-config <agent>` | Install MCP + skill for an AI agent |
| `libspec agent-workflow` | Print the standardised 8-step workflow |
| `libspec completion <shell>` | Generate shell auto-completion script |

### 4.2 MCP Server (`libspec-mcp`)

The MCP server exposes libspec tools to AI coding agents:

| Tool | Purpose |
|------|---------|
| `diff` | Spec diff between two Git refs |
| `search` | AST-based workspace search |
| `peek` | Hover / definition lookup at file position |
| `usage` | Find references to a component |
| `symbols` | List classes/methods in a file |
| `list_components` | List all spec components |
| `show_component` | Inspect a single component |
| `list_dependencies` | Show component dependency graph |
| `agent_workflow` | Return the 8-step workflow instructions |
| `agent_config` / `mcp_agent` | Configure coding agents |

### 4.3 REPL

An interactive `prompt_toolkit`-based REPL for browsing specifications:

- **Commands**: `list`, `show`, `search`, `diff`, `log`, `dependencies`, `help`, `quit`
- Auto-completion of component refs
- Linux inotify watcher auto-reloads specs on file change
- Snapshot navigation (browse specs at historical Git commits)

---

## 5. Agent Integration

`AgentConfig` is an ABC with concrete subclasses for each supported coding agent:

| Agent ID | Tool | Config Location |
|----------|------|----------------|
| `claude` | Claude Code | `.claude/` |
| `gemini` | Gemini CLI | `.gemini/settings.json` |
| `antigravity` | Antigravity IDE | `.gemini/antigravity/mcp_config.json` |
| `copilot` | GitHub Copilot | `.github/mcp.json` |
| `codex` | OpenAI Codex | `.codex/config.toml` |
| `opencode` | OpenCode | `.opencode/opencode.json` |

Each configurator:
1. Writes the agent's MCP server config pointing to `uv run libspec mcp`.
2. Renders and installs a `SKILL.md` (validated via `skillkit`) containing the 8-step developer workflow.
3. Auto-heals outdated skills on `libspec init`, `libspec mcp`, and `libspec agent-config`.

---

## 6. Developer Agent Workflow

The canonical 8-step workflow (surfaced via `agent_workflow`):

1. **Edit Spec** — Decompose requirements into granular, single-responsibility `Ctx` subclasses.
2. **Diff Spec** *(mandatory before coding)* — Run `libspec diff` to detect specification drift.
3. **Sort Implementation Order** — Use `libspec dependencies` to build a topological ordering.
4. **TDD** — Write tests first for each component in dependency order.
5. **Implement** — Write code to make the tests pass.
6. **Code Quality** — Lint, format, and static analysis.
7. **Verify Spec Sync** — Run `libspec diff` again to confirm everything is accounted for.
8. **Author a git commit message** — Present to the user.

---

## 7. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Specs are Python classes | Native IDE support, import system, inheritance, type checking |
| Jinja2 docstring templates | Allows reusable parameterised requirement patterns |
| Git-native versioning (no DB) | Zero infrastructure, works anywhere Git works |
| SHA-256 content hashing | Deterministic change detection without timestamps |
| Component-level diff (not XML diff) | Understands inheritance; produces requirement-level patches |
| MCP for AI integration | Standard protocol; works with Claude, Gemini, Copilot, etc. |
| `SKILL.md` skill injection | Ensures AI agents know the workflow without manual setup |
| inotify watcher in REPL | Live spec reload without polling |
| `.libspec/` marker dir | Simple project detection, consistent with `.git/` convention |
