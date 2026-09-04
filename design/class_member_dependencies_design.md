# Design: Class Member Dependencies (`deps`) with Exotic Error Handling

**Author:** Antigravity & Derek  
**Date:** 2026-09-04  
**Status:** Proposal / Review  
**Component:** `libspec.spec`, `libspec.spec_types`, `libspec.err`, `libspec.common`, `libspec.cli`  

---

## 1. Executive Summary

In `libspec`, specification components define the architectural blueprint of a software system. Today, `libspec dependencies` inspects `inherits` (the class MRO chain), which reflects cross-cutting quality constraints (such as `Err`, `BoilerPlate`, and `Robustness`) rather than logical prerequisites.

This design introduces **spec-native class-member dependency declarations**:
```python
from libspec import Component, Req, Feat

class DatabaseStorageReq(Req):
    """Underlying persistent database schema."""

class UserAuthComponent(Component):
    """Authentication and session management."""
    deps = [DatabaseStorageReq]
```

### Key Requirements & Semantics
1. **Class Member Declaration**: A specification component declares prerequisites via a class member: `deps = [Dep1, Dep2, ...]`. (With `depends_on` supported as a backwards-compatible alias).
2. **Inheritance Semantic**: Every dependency in `deps` **must inherit from `Component`** (`issubclass(dep, Component)`).
3. **Exotic Error Handling**: Guided by `design/err.md` ("Error reporting, handling, exceptions and all aspects of failure must be taken to extreme. It should be possible to understand the program by reading the error messages. When an error occurs there should be a story about the failure at each step of the way."), failures must produce rich, context-aware, storytelling diagnostic reports with source introspection, MRO tree visualization, and actionable remedies.
4. **DAG Invariant**: Component dependencies form a strict Directed Acyclic Graph (DAG). Cycles and self-dependencies are detected at compile-time with full cycle tracepaths.
5. **Phase-Typed Workflow**: Feature design, specification, test-driven development, and implementation follow the 9-step `libspec` agent workflow.

---

## 2. Type Hierarchy & Architecture

### 2.1 The `Component` Base Class
Currently, `libspec` exposes `Ctx`, `BaseSpec`, `Feature`, and `Requirement`. We introduce `Component` in `libspec.spec_types` (and export it via `libspec`):

```python
class Component(BaseSpec):
    """
    Base specification class for all architectural components.
    Declares logical component dependencies via the `deps` class attribute.
    """
    __is_base_spec__ = True
    deps: list[type["Component"]] = []
```

`Feature` and `Requirement` in `libspec.spec_types` inherit from `Component`:
```python
class Feature(Component):
    ...

class Requirement(Component):
    ...
```

Consequently, all existing user-defined specs (`Req`, `Feat`, `Requirement`, `Feature`, or direct `Component` subclasses) inherit from `Component`.

### 2.2 Dataclass Disambiguation (`libspec/common.py`)
In `libspec/common.py`, the immutable compiled data model is currently named `Component`. In the specification itself (`spec/common.py:8`), it is already specified as `SpecComponent`:
```python
class SpecComponent(Req):
    """Immutable data structure representing a compiled specification node."""
```
To avoid naming collisions between the spec base class `Component` and the compiled dataclass:
- `libspec/common.py` defines `SpecComponent` (with `Component = SpecComponent` alias for backwards compatibility).
- `libspec/__init__.py` exports `Component` from `libspec.spec_types` (the spec class) and `SpecComponent` from `libspec.common` (the compiled dataclass).
- The compiled record is extended with:
  ```python
  @dataclass(frozen=True)
  class SpecComponent:
      ref: str
      docstring: str
      is_template: bool
      inherits: list[str]
      hash: str
      is_dependency: bool = False
      deps: list[str] = field(default_factory=list)  # FQNs of direct dependencies
  ```

---

## 3. Dependency Declaration Semantics

### 3.1 Syntax Rules
- **Attribute**: `deps = [Dep1, Dep2, ...]` (or `tuple`).
- **Scope & Non-Inheritance**: `deps` is evaluated off the concrete class's `__dict__`. Unlike behavioral constraints, prerequisites are specific to the concrete component and are not implicitly inherited by subclasses.
- **Type Compliance**: Every element in `deps` must be a Python `type` (class), not an instance, string, or primitive.
- **Component Semantic**: Every element must satisfy `issubclass(dep, Component)`.
- **Identity**: Self-dependency (`Dep == MyComponent`) is forbidden.
- **Deduplication**: Duplicate entries are automatically normalized and deduplicated while preserving declaration order.

---

## 4. Exotic Error Handling Architecture

In accordance with `design/err.md`, error handling is treated as a first-class user experience. Each failure mode has a dedicated exception type, inspects AST/runtime frames for source locations, and formats a complete narrative story.

### 4.1 Exception Class Hierarchy (`libspec/err.py`)
```
LibspecError (Exception)
 └── DependencyError
      ├── DependencyDeclarationError       # Invalid `deps` attribute type (e.g. str, int, dict)
      ├── DependencyTypeError              # Item is not a class (e.g. instance, None, int)
      ├── NonComponentDependencyError      # Item does not inherit from `Component`
      ├── SelfDependencyError              # Component lists itself in `deps`
      ├── DuplicateDependencyError         # Duplicate dependencies declared
      └── CyclicDependencyError            # Cycle detected in component DAG
```

### 4.2 Storytelling Error Formats

#### Case 1: Dependency Does Not Inherit from `Component` (`NonComponentDependencyError`)
```
================================================================================
LIBSPEC DEPENDENCY COMPLIANCE ERROR: Non-Component Dependency Declared
================================================================================
Component:
  spec.services.PaymentGatewayReq
  Location: /workspace/spec/services.py:42

Offending Dependency:
  [Index 0] ExternalStripeClient (<class 'spec.services.ExternalStripeClient'>)
  Location: /workspace/spec/services.py:12

Violation:
  All elements in `deps` must inherit from `libspec.Component`.
  Class 'ExternalStripeClient' does NOT inherit from 'Component'.
  
  Actual Inheritance Hierarchy:
    └── ExternalStripeClient
        └── object

Architectural Explanation:
  libspec enforces that dependency graphs represent logical relationships
  between formal specification components. Plain Python classes, utilities,
  or third-party objects cannot be scheduled or verified in the agent workflow.

FIX:
  1. If 'ExternalStripeClient' is a specification component, inherit from Component:
       class ExternalStripeClient(Component):
           ...
  2. Or if 'PaymentGatewayReq' does not depend on a spec component, remove it:
       deps = [...]
================================================================================
```

#### Case 2: Instance Passed Instead of Class (`DependencyTypeError`)
```
================================================================================
LIBSPEC DEPENDENCY TYPE ERROR: Instance Passed Instead of Class
================================================================================
Component:
  spec.services.PaymentGatewayReq
  Location: /workspace/spec/services.py:42

Offending Value:
  [Index 1] <DatabaseStorageReq object at 0x7f88a10> (type: DatabaseStorageReq)

Violation:
  Elements in `deps` must be Component classes (types), not instances.

Did you mean:
  deps = [DatabaseStorageReq]   # <-- Pass the class, not an instantiated object: DatabaseStorageReq()

FIX:
  Remove parentheses from the instantiated dependency in 'deps'.
================================================================================
```

#### Case 3: Invalid `deps` Attribute Type (`DependencyDeclarationError`)
```
================================================================================
LIBSPEC DEPENDENCY DECLARATION ERROR: Invalid `deps` Attribute
================================================================================
Component:
  spec.services.PaymentGatewayReq
  Location: /workspace/spec/services.py:42

Found:
  deps = <class 'spec.storage.DatabaseStorageReq'> (type: type)

Violation:
  The `deps` attribute must be a list or tuple of Component classes.

Did you mean:
  deps = [DatabaseStorageReq]

FIX:
  Wrap the dependency in a list: `deps = [DatabaseStorageReq]`
================================================================================
```

#### Case 4: Self-Dependency (`SelfDependencyError`)
```
================================================================================
LIBSPEC DEPENDENCY INTEGRITY ERROR: Self-Dependency Detected
================================================================================
Component:
  spec.services.PaymentGatewayReq
  Location: /workspace/spec/services.py:42

Violation:
  Component 'PaymentGatewayReq' cannot depend on itself.
  A component's prerequisite must be an external component that can be built
  and verified prior to this component.

FIX:
  Remove 'PaymentGatewayReq' from its own `deps` list in /workspace/spec/services.py:42.
================================================================================
```

#### Case 5: Cyclic Dependency Detected (`CyclicDependencyError`)
```
================================================================================
LIBSPEC DEPENDENCY GRAPH ERROR: Cyclic Dependency Detected (Cycle in DAG)
================================================================================
A cycle was detected in the component dependency graph:

  Cycle Trace:
    spec.pipeline.IngestReq (/workspace/spec/pipeline.py:15)
      └── depends on: spec.pipeline.TransformReq (/workspace/spec/pipeline.py:32)
            └── depends on: spec.pipeline.ExportReq (/workspace/spec/pipeline.py:50)
                  └── depends on: spec.pipeline.IngestReq [CYCLE CLOSES HERE]

Violation:
  The component dependency graph must be a strict Directed Acyclic Graph (DAG)
  so that orchestrator agents can schedule implementation in topological waves.

Involved Components:
  • spec.pipeline.IngestReq (spec/pipeline.py:15)
  • spec.pipeline.TransformReq (spec/pipeline.py:32)
  • spec.pipeline.ExportReq (spec/pipeline.py:50)

Resolution Strategies:
  1. Extract a shared prerequisite: Extract the common interface or contract
     into a separate foundational component (e.g. DataSchemaReq), and have both
     IngestReq and ExportReq depend on it.
  2. Invert edge: Re-examine if ExportReq truly requires IngestReq.
================================================================================
```

---

## 5. Implementation Ordering & Downstream Tooling

### 5.1 Kahn's Algorithm Wave Scheduling (`--topo`)
With logical `deps`, `libspec` schedules implementation into **parallel waves**:
- **Wave 1 (Roots)**: Components with in-degree 0 (no prerequisites). Can be implemented immediately by parallel agents.
- **Wave 2**: Components whose prerequisites are fully satisfied by Wave 1.
- **Wave N**: Higher-order features.

```
$ uv run libspec dependencies --topo
Topological Implementation Order for 'HEAD (Live Spec)':
  Wave 1: spec.storage.DatabaseStorageReq, spec.auth.TokenCryptoReq
  Wave 2: spec.auth.UserAuthComponent
  Wave 3: spec.api.UserProfileAPI
```

### 5.2 Tooling Integration
- **CLI (`libspec dependencies`)**:
  - Default: Prints logical `deps` tree.
  - `--topo`: Prints implementation wave ordering.
  - `--inherits`: Prints MRO constraint hierarchy.
- **MCP Server (`mcp_server.py`)**: Updates `list_dependencies` and adds `implementation_order`.
- **REPL (`repl.py`)**: Updates `dependencies` and adds `topo` command.
- **Spec Diff (`spec_diff.py`)**: Emits `deps` change diffs when dependencies are added, modified, or removed.

---

## 6. The 9-Step Libspec Workflow Execution Plan

Once this design is reviewed and approved, we will execute the implementation strictly following the **Libspec 9-Step Workflow**:

1. **Phase 1: Edit Spec [DECLARATIVE]**:
   Add granular requirement and feature specifications in `spec/`:
   - `spec/dependencies.py`:
     - `ComponentBaseReq`: Spec for `Component` base class and `deps` class attribute.
     - `ComponentDependencyEvaluationReq`: Spec for validating `deps` elements inherit from `Component`.
     - `ExoticDependencyErrorsReq`: Spec for rich, storytelling exception hierarchy and formatting.
     - `DependencyGraphValidationReq`: Spec for DAG enforcement and cycle detection.
     - `TopologicalImplementationOrderFeat`: Spec for Kahn's wave scheduler.
   - Update `spec/common.py` to include `deps` in `SpecComponent`.
2. **Phase 2: Diff Spec [DECLARATIVE -> IMPERATIVE]**:
   Run `uv run libspec diff` to verify the declarative mutations and generate component action diffs.
3. **Phase 3: Sort Implementation Ordering [IMPERATIVE]**:
   Run `uv run libspec dependencies --topo` to order new components into implementation waves.
4. **Phase 4: Test-Driven Development [IMPERATIVE - Contract Driven]**:
   Write comprehensive pytest test cases in `tests/test_dependencies.py` covering all error scenarios, valid hierarchies, and wave scheduling.
5. **Phase 5: Implement [IMPERATIVE - Goal Directed]**:
   Implement the code in `libspec/err.py`, `libspec/spec_types.py`, `libspec/spec.py`, `libspec/common.py`, `libspec/cli.py`, etc.
6. **Phase 6: Code Quality & Verification [IMPERATIVE]**:
   Run `ruff check`, `ruff format --check`, `mypy`, and `pytest`.
7. **Phase 7: Verify Specification Sync [DECLARATIVE]**:
   Run `uv run libspec diff` to verify zero drift between specs and implementation.
8. **Phase 8: Version Bump [IMPERATIVE]**:
   Bump minor version in `pyproject.toml` (`libspec` feature addition).
9. **Phase 9: Commit & Present [IMPERATIVE]**:
   Author a clean git commit message referencing spec and diff footprints.
