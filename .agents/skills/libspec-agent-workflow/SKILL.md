---
name: libspec-agent-workflow
description: >-
  Executes, prototypes, and manages agent workflows using `uv run libspec agent-workflow`.
  Use this skill whenever prototyping agent workflows, testing libspec steps, or orchestrating
  declarative specifications and imperative coding prompts within libspec.
---

# Libspec Agent Workflow Skill

## Overview
This skill standardizes instructions for prototyping, running, and debugging agent workflows within the `libspec` repository. It formalizes the distinction between **Declarative Specifications** (in `./spec`) and **Imperative Prompts** (derived via `libspec diff`), along with phase-typed orchestration across the 9-step development loop.

## Core Architectural Concepts

### 1. Declarative Specifications (`./spec`)
- **Nature**: Declarative specs in `./spec/*.py` define WHAT the system is (architecture, interface contracts, data schemas, invariants, and constraints).
- **Long-Lived Blueprint**: Specs represent the enduring source of architectural truth versioned in Git.
- **Strict Exclusion**: One-off procedural instructions, bugfix tasks, or temporary implementation steps MUST NOT be placed in `./spec`.

### 2. Imperative Prompts & Instructions
- **Nature**: Imperative prompts represent transient, procedural, and disposable directives (e.g. "Create module X", "Add method Y", "Fix test Z").
- **Diff-Generated Bridge**: The `libspec diff` command computes the delta between declarative specs and the codebase, compiling component deltas into structured imperative prompts.
- **Disposable Lifecycle**: Once executed and verified by tests, the codebase satisfies the declarative contract and the imperative prompt is retired.

### 3. Dispatching (Orchestrator) vs. Generating (Worker) Roles
- **Dispatching Agent (Orchestrator)**: Must understand both the active Workflow Phase and Execution Paradigm (Declarative vs. Imperative). Ingests declarative specs, computes topological waves via `libspec dependencies --topo`, and dispatches targeted imperative prompt envelopes to workers.
- **Generating Agent (Worker)**: Receives focused prompt envelopes, executes localized TDD and implementation steps, and satisfies verification gates without needing global project state.

## The 9-Step Phase-Typed Workflow

```bash
uv run libspec agent-workflow
```

1. **Phase 1: Edit Spec [DECLARATIVE]**: Decompose broad requirements into granular, single-responsibility specification classes in `spec/`. Specs DECLARE the system; do not put imperative task steps here.
2. **Phase 2: Diff Spec (MANDATORY BEFORE CODING) [DECLARATIVE -> IMPERATIVE]**: Run `uv run libspec diff` to compile specification drift into structured imperative component action diffs.
3. **Phase 3: Sort Implementation Ordering [IMPERATIVE]**: Inspect component dependencies via `uv run libspec dependencies --topo` to sort components into topological implementation order.
4. **Phase 4: Test Driven Development [IMPERATIVE - Contract Driven]**: Write unit and integration tests in topological dependency order, formalizing declarative acceptance criteria.
5. **Phase 5: Implement [IMPERATIVE - Goal Directed]**: Implement production code to pass tests and satisfy specification contracts.
6. **Phase 6: Code Quality & Verification [IMPERATIVE]**: Run static analysis (`mypy`), linting (`ruff check`), formatting (`ruff format`), and dead code detection (`vulture`).
7. **Phase 7: Verify Specification Sync [DECLARATIVE]**: Run `uv run libspec diff` to ensure live specs match implementation claims and zero drift remains.
8. **Phase 8: Version Bump [IMPERATIVE]**: Bump project version in `pyproject.toml` according to Semantic Versioning (`MAJOR.MINOR.PATCH`).
9. **Phase 9: Commit & Present [IMPERATIVE]**: Author a clean Git commit message linking spec references and diff footprints, then present to the user.

## Execution Rules
- Always run agent workflow prototyping commands via `uv run`:
  ```bash
  uv run libspec agent-workflow [subcommand / options]
  ```
- Use standard `uv` commands (`uv run`, `uv sync`) without invoking raw `python` interpreters directly.
- Inspect logs, file outputs, or CLI output produced by the workflow runs to verify results.

