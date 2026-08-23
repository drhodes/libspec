# libspec

> **"An ounce of spec is worth a pound of tokens."**

`libspec` is a **Specification Management System** in Python. Similar in spirit to Object-Relational Mapping (ORM) tools, `libspec` implements **Object Specification Mapping (OSM)** to compile declarative requirements declared in Python classes into structured component models. Instead of generating SQL schemas or relying on an external database, it is completely **stateless and Git-native**, tracking how requirement definitions evolve across Git revisions.

By diff'ing specifications and providing a native **Model Context Protocol (MCP)** server, `libspec` acts as a centralized, programmatic context layer for LLM coding agents. The developer workflow is incremental and exploratory, turning code generation from a gamble into disciplined delegation.

---

## The big idea: generic specifications

The deepest capability in `libspec` is **generic specifications** — base classes
that encode *how features should be specified*, not what any particular feature
does.

```python
from libspec import Feature
from libspec.diataxis import Diataxis        # pip install libspec-diataxis
from libspec.conventional_commits import Commit # pip install libspec-conventional-commits

# Inherit once. Every feature in your project automatically
# carries both contracts — enforced at spec-generation time.
class MyFeature(Feature, Diataxis, Commit): pass

class AwesomeNavBar(MyFeature):
    def tutorial(self):    return "In this tutorial we will build..."
    def how_to(self):      return "To highlight the active route..."
    def reference(self):   return "AwesomeNavBar(items, active_index, ...)"
    def explanation(self): return "The nav bar uses a slot-based model because..."
```

Generic specs turn documentation standards from advisory suggestions into
**structural guarantees**. Miss a quadrant and `UnimplementedMethodError` tells
you exactly where, at spec-generation time. The contract travels through
inheritance automatically — define it once at your base class, and every
downstream feature complies.

[Read the full explanation →](explanation/generic-specs.md)

---

## The Workflow

```mermaid
graph TD
    classDef default fill:#f8fafc,stroke:#475569,stroke-width:1.5px,color:#0f172a;
    classDef spec fill:#e0e7ff,stroke:#4338ca,stroke-width:2px,color:#1e1b4b;
    classDef agent fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#082f49;
    classDef verify fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d;

    A[Define Spec in Python (spec/*.py)]:::spec --> B[Compile In-Memory / Git Snapshot]:::default
    B --> C[Inspect via REPL or libspec diff]:::default
    C --> D[Connect LLM Agent via MCP]:::agent
    D --> E[Agent Reads Spec & Implements Code]:::agent
    E --> F[Test & Reconcile Sync]:::verify
```

---

## Core Philosophy

1. **Specifications as Code**: Define requirements as declarative Python classes in `spec/*.py`. Use inheritance to express constraint qualities and `depends_on` to model logical implementation dependencies.
2. **Git-Native Architecture**: Specifications live in version control alongside your codebase. Historical specs are extracted directly from Git revisions without external database files.
3. **Seamless Agent Guidance**: Feed rich, dependency-sorted context directly to coding agents via LSP or MCP, ensuring they implement requirements correctly in topological order.
4. **Declarative Architecture, Imperative Directives**: Keep `./spec` purely declarative; use `libspec diff` to generate actionable imperative instructions on the fly.

---

## Visualizing the Architecture

`libspec` bridges the gap between design-time specifications and run-time implementations. It provides tools for both human developers and LLM subagents:

*   **Developers** write and refine specifications using familiar Python OOP syntax in `spec/`.
*   **The Compiler** builds these specs into deterministic, content-addressed component models in memory.
*   **The REPL & CLI** allow you to inspect, search, and diff specifications against any Git revision.
*   **The MCP Server** exposes these tools directly to coding assistants in IDEs.

