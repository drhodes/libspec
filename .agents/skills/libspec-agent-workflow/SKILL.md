---
name: libspec-agents
description: Navigation and specification tools for workspace .agents
license: MIT
---

# Agents + Libspec

Your environment is configured to use the **Libspec** MCP server, providing advanced navigation and specification-driven development tools.

## Available Tools

### 🔍 libspec_search
- **Purpose**: Semantic search for specification components (Requirements, Features, Scenarios).
- **Usage**: When you need to understand the "why" behind a piece of code or find where a requirement is implemented.
- **Example**: `libspec_search(query="user authentication")`

### 👁️ libspec_peek
- **Purpose**: Retrieve definitions, docstrings, and type hints for a symbol without reading the entire file.
- **Usage**: Use this for quick orientation before diving into the implementation.
- **Example**: `libspec_peek(file_path="auth.py", line=42, character=10)`

### 🏗️ libspec_symbols
- **Purpose**: List all structural components (classes and methods) in a specific file.
- **Usage**: Orientation in large or unfamiliar source files.
- **Example**: `libspec_symbols(file_path="models.py")`

### 🔗 libspec_usage
- **Purpose**: Find all semantic references to a component across the entire project.
- **Usage**: **Mandatory** before refactoring or deleting shared code to perform impact analysis.
- **Example**: `libspec_usage(file_path="utils.py", line=12, character=5)`

## Dev Workflow (Phase-Typed & Paradigm-Aware)
1. **Phase 1: Edit Spec [DECLARATIVE]**: Edit/define the requirements/features in the specification files. **Always decompose broad requirements into granular, single-responsibility requirement classes (e.g. `HelpCommandReq`, `SnapshotsCommandReq`) rather than using monolithic requirement blocks to ensure first-class specification footprinting.** Specs DECLARE the system architecture; do not put one-off imperative task steps here.
2. **Phase 2: Diff Spec (MANDATORY BEFORE CODING) [DECLARATIVE -> IMPERATIVE]**: You **must absolutely** run a spec diff using either the `libspec_diff` MCP tool or the `uv run libspec diff` command to identify specification drift, review mutations, and compile component deltas into structured imperative action prompts before coding begins.
3. **Phase 3: Sort Implementation Ordering [IMPERATIVE]**: Inspect component dependencies via the `libspec_dependencies` tool or `uv run libspec dependencies` command to sort components into topological implementation order, ensuring foundational requirements are built before dependent features.
4. **Phase 4: Test Driven Development [IMPERATIVE - Contract Driven]**: Follow best practices in test driven development to write unit and integration tests for the components in topological dependency order, formalizing the declarative acceptance criteria before writing production code.
5. **Phase 5: Implement [IMPERATIVE - Goal Directed]**: Implement the components to ensure the tests pass and satisfy the declared specification contracts.
   * Run pytest suite: `make test`
   * Run formatting check: `uv run ruff format --check`
   * Run linting check: `uv run ruff check`
   * Run deadcode check: `make deadcode`
6. **Phase 6: Code Quality & Verification [IMPERATIVE]**: Run static analysis, linting, formatting, and dead code checks according to the project's guidelines.
7. **Phase 7: Verify Specification Sync [DECLARATIVE]**: Run a spec diff using the `libspec_diff` MCP tool or the `uv run libspec diff` command to ensure that the live specifications are fully synchronized with the final implementation and that all changes are accounted for.
8. **Phase 8: Version Bump [IMPERATIVE]**: Bump the project version in `pyproject.toml` according to Semantic Versioning (SemVer: `MAJOR.MINOR.PATCH`). Use helper commands (`make bump-patch`, `make bump-minor`, or `make bump-major`) as appropriate for the change.
9. **Phase 9: Author a git message and present to user [IMPERATIVE]**


