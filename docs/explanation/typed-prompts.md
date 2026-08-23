# Phase-Typed Prompts & Paradigms

A core design principle in `libspec` is the separation of **Declarative Architecture** from **Imperative Construction Logistics**, coupled with **Phase-Typed Prompt Orchestration** for autonomous AI coding agents.

---

## 1. The Declarative vs. Imperative Dichotomy

In software engineering and AI agent delegation, there is a fundamental distinction between:

1. **What the system IS (Declarative Specification)**:
   - Resides in `spec/*.py`.
   - Represents the enduring, version-controlled architecture, contracts, schemas, invariants, and behavioral requirements.
   - Serves as the target blueprint that the codebase must satisfy.
2. **What to DO now (Imperative Directives)**:
   - Ephemeral, procedural tasks (e.g. "Create file `x.py`", "Add method `foo()`", "Fix failing test `test_bar`").
   - Dispatched dynamically to coding agents to perform immediate codebase mutations.

```mermaid
flowchart TD
    classDef decl fill:#e0e7ff,stroke:#4338ca,stroke-width:2px,color:#1e1b4b;
    classDef diff fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f;
    classDef imp fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#082f49;
    classDef code fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d;

    subgraph Declarative ["Declarative Architecture"]
        SpecDoc["Requirement and Feature Classes"]:::decl
    end

    subgraph Compiler ["The libspec diff Bridge"]
        DiffOp["libspec diff and dependencies"]:::diff
        ActionDelta["Structured Component Action Diffs"]:::diff
    end

    subgraph Imperative ["Imperative Execution"]
        TaskPrompt["Phase-Typed Prompt Envelope"]:::imp
    end

    subgraph Production ["Target Codebase"]
        Src["Source Implementation"]:::code
        Tests["Test Suite"]:::code
    end

    SpecDoc --> DiffOp
    Src --> DiffOp
    DiffOp --> ActionDelta
    ActionDelta --> TaskPrompt
    TaskPrompt --> Tests
    TaskPrompt --> Src
```

---

## 2. The Non-Colocation Tenet

> **Imperative task instructions must NEVER live inside `./spec`.**

Specifications in `./spec` are architectural design documents. Storing one-off tasks, procedural migration scripts, or temporary checklists inside `./spec` pollutes the enduring design blueprint with transient construction residue.

Instead:
- `./spec` defines the declarative destination.
- `libspec diff` compiles the difference between the codebase and `./spec` into actionable imperative instructions.

$$\text{Imperative Instructions} = \text{Declarative Spec} \ominus \text{Current Codebase State}$$

---

## 3. Cognitive Roles: Dispatcher vs. Generator

Effective agent orchestration divides responsibilities between two distinct cognitive roles:

```mermaid
classDiagram
    class DispatchingAgent {
        +active_phase
        +dependency_dag
        +baseline_spec
        +ingest_declarative_specs()
        +compile_diff_to_imperative_tasks()
        +schedule_topological_waves()
        +dispatch_typed_prompt()
        +reconcile_and_verify_sync()
    }

    class GeneratingAgent {
        +active_task
        +execute_imperative_step()
        +satisfy_declarative_contract()
        +run_local_test_loop()
        +report_resolution_status()
    }

    DispatchingAgent --> GeneratingAgent : Dispatches Typed Prompt Envelope
```

- **The Dispatching Agent (Orchestrator)**: Must understand the active workflow phase, topological dependencies (`depends_on`), and declarative architecture. It converts spec diffs into topological execution waves and dispatches targeted prompt envelopes to workers.
- **The Generating Agent (Worker)**: Receives a single typed prompt envelope with concrete file targets, prerequisite contracts, and test gates. It focuses purely on satisfying the local contract without needing global project state.

---

## 4. The Two-Axis Prompt Typing Taxonomy

Every prompt exchanged in `libspec` is classified along two axes:

1. **Paradigm Type**: `DECLARATIVE` vs. `IMPERATIVE`.
2. **Workflow Phase**: The active phase in the 9-step lifecycle.

```mermaid
flowchart LR
    classDef decl fill:#e0e7ff,stroke:#4338ca,stroke-width:2px,color:#1e1b4b;
    classDef imp fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#082f49;
    classDef bridge fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f;
    classDef done fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d;

    P1["Phase 1: Spec Declaration"]:::decl --> P2["Phase 2: Diff Compilation"]:::bridge
    P2 --> P3["Phase 3: Topo Scheduling"]:::imp
    P3 --> P4["Phase 4: TDD Formulation"]:::imp
    P4 --> P5["Phase 5: Implementation"]:::imp
    P5 --> P6["Phase 6: Quality Verification"]:::imp
    P6 --> P7["Phase 7: Spec Reconciliation"]:::decl
    P7 --> P8["Phase 8: Version Release"]:::imp
    P8 --> P9["Phase 9: VCS Commit"]:::done
```


| Phase | Paradigm | Focus |
|---|---|---|
| **Phase 1: Edit Spec** | `DECLARATIVE` | Granular specification authoring and contract formulation. |
| **Phase 2: Diff Spec** | `DECLARATIVE → IMPERATIVE` | Synthesizing component deltas from live specs and Git revisions. |
| **Phase 3: Topo Scheduling** | `IMPERATIVE` | Ordering tasks into topological waves based on `depends_on`. |
| **Phase 4: TDD Formulation** | `IMPERATIVE (Contract Driven)` | Writing failing unit tests that formalize declarative contracts. |
| **Phase 5: Implement** | `IMPERATIVE (Goal Directed)` | Implementing code to make tests pass and satisfy contracts. |
| **Phase 6: Quality Verification** | `IMPERATIVE` | Static analysis (`mypy`), linting (`ruff`), and dead code detection. |
| **Phase 7: Verify Spec Sync** | `DECLARATIVE` | Verifying that live specs match code claims with zero drift. |
| **Phase 8: Version Bump** | `IMPERATIVE` | Bumping SemVer in `pyproject.toml`. |
| **Phase 9: Commit & Present** | `IMPERATIVE` | Synthesizing git commit messages linking spec references. |
