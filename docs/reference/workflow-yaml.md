# Workflow Configuration Reference (.libspec/workflow.yaml)

Technical specification for project-level developer agent workflow hooks configured in `.libspec/workflow.yaml`.

---

## Overview

The `.libspec/workflow.yaml` file defines project-specific commands and verification steps injected dynamically into the 9-phase developer agent workflow recited by:
- CLI: `libspec agent-workflow`
- MCP Tool: `libspec_agent_workflow` (or `mcp_libspec_agent_workflow`)

---

## Location

The file must be located directly inside the `.libspec/` directory at the project root:

```
<project-root>/
├── .libspec/
│   └── workflow.yaml
├── spec/
└── ...
```

---

## File Schema

`.libspec/workflow.yaml` is a standard YAML document with a top-level `hooks:` mapping.

```yaml
hooks:
  <hook-name>:
    - "<command or instruction>"
    - "<command or instruction>"
```

### Values

Values associated with a hook key can be either:
- A **string** representing a single command or instruction:
  ```yaml
  hooks:
    post-implement: "Run test suite: `uv run pytest`"
  ```
- A **list of strings** representing multiple commands or instructions executed in sequence:
  ```yaml
  hooks:
    pre-commit:
      - "Verify code formatting: `uv run ruff format --check`"
      - "Run linter: `uv run ruff check`"
      - "Run typechecker: `uv run mypy -p libspec`"
  ```

---

## Supported Hook Anchors

Hooks map directly to the 9 development phases:

| Hook Key | Phase | Placement | Description |
| :--- | :--- | :--- | :--- |
| `post-edit` | **Phase 1: Edit Spec** | After phase guidance | Instructions to execute immediately after editing specification classes. |
| `pre-diff` | **Phase 2: Diff Spec** | Before diff instruction | Pre-compilation or build steps required prior to diffing. |
| `post-diff` | **Phase 2: Diff Spec** | After diff instruction | Guidelines for inspecting or decomposing the generated diff output. |
| `post-dependencies` | **Phase 3: Sort Topo** | After topo sorting | Commands to visualize or inspect topological implementation waves. |
| `pre-test` | **Phase 4: TDD** | Before test authoring | Environment sync or fixture setup before writing tests. |
| `post-test` | **Phase 4: TDD** | After test authoring | Verification that tests fail prior to implementation (Red). |
| `pre-implement` | **Phase 5: Implement** | Before coding | Directives to follow before modifying production code. |
| `post-implement` | **Phase 5: Implement** | After coding | Local test runners and unit verification commands. |
| `pre-commit` | **Phase 6: Quality** | Main quality gate | Linters, formatters, typecheckers, and static analysis tools. |
| `post-quality` | **Phase 6: Quality** | Secondary quality gate | Security scans, complexity checks, or deadcode detection. |
| `post-sync` | **Phase 7: Spec Sync** | After spec diff | Validation commands to guarantee zero live specification drift. |
| `pre-bump` | **Phase 8: Version Bump** | Before version bump | Pre-release status checks (`git status -s`). |
| `post-bump` | **Phase 8: Version Bump** | After version bump | Lockfile re-generation or changelog synchronization. |
| `post-commit` | **Phase 9: Commit** | After commit advice | Git commit footprint presentation and release instructions. |

---

## Error Resilience & Fallback

The workflow engine handles anomalous file states defensively:
1. **Missing File**: If `.libspec/workflow.yaml` does not exist, `agent-workflow` recites the default canonical 9-step workflow without custom hooks.
2. **Empty File**: An empty file (0 bytes or comments only) is treated as an empty hook mapping.
3. **Malformed / Corrupt YAML**: If the file contains invalid syntax or a non-dictionary root, `libspec` absorbs the parsing error without crashing and falls back to default workflow instructions.
