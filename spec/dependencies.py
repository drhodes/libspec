"""
Declarative specifications for class-member component dependencies and exotic error handling.
"""

from .core import SpecBase
from .err import Feat, Req


class ComponentBaseReq(Req):
    """
    The `Component` base class is the foundational unit for all architectural specifications.

    `Component` inherits from `BaseSpec` and establishes class-level dependency declarations
    via the `deps` class attribute (defaulting to an empty list). Standard vocabulary classes
    including `Feature` and `Requirement` inherit from `Component`, ensuring that all domain
    specifications (`Feat`, `Req`, or direct `Component` subclasses) participate in the
    dependency graph.

    Key responsibilities:
    - Serve as the root type for all spec components that can be depended upon.
    - Provide default `deps = []` on the base class.
    - Expose `__is_base_spec__ = True` so base components are excluded from concrete diff outputs.
    """

    deps = [SpecBase]


class ClassMemberDependenciesReq(Req):
    """
    Components declare their logical implementation prerequisites as class members using
    `deps = [Dep1, Dep2, ...]`.

    Prerequisites represent implementation sequencing: `MyComponent` depends on `Dep1` and `Dep2`
    such that `Dep1` and `Dep2` must be built, tested, and satisfied before `MyComponent` can be
    implemented.

    Key rules:
    - Declaration: Declared directly on the class body via `deps = [Dep1, Dep2, ...]`.
    - Aliasing: `depends_on` is recognized as a backwards-compatible alias for `deps`.
    - Non-Inheritance: Dependencies are read strictly from the concrete class's `__dict__`.
      Unlike cross-cutting behavioral constraints (`inherits`), logical dependencies are explicit
      per component and do not automatically bleed down class inheritance hierarchies.
    - Deduplication: Duplicate dependencies in `deps` are normalized deterministically while
      preserving declaration ordering.
    """

    deps = [ComponentBaseReq]


class ComponentInheritanceConstraintReq(Req):
    """
    All prerequisites declared within `deps` must be classes that inherit from `Component`.

    libspec enforces that dependency graphs represent logical relationships between formal
    specification components. Non-component classes (such as plain Python utilities, external
    libraries, or data models that do not inherit from `Component`) cannot be scheduled or
    verified in the agent workflow and must be rejected with descriptive errors.

    Validation invariant:
    - For each element `d` in `deps`: `isinstance(d, type) and issubclass(d, Component)`.
    """

    deps = [ComponentBaseReq, ClassMemberDependenciesReq]


class ExoticStorytellingErrorsReq(Req):
    """
    When dependency declaration or evaluation fails, libspec raises rich, storytelling domain
    exceptions that explain failure at extreme depth, following the guidelines of Err.

    Rather than raising generic TypeErrors or assertions, errors are encapsulated in a domain
    exception hierarchy rooted in `DependencyError`.

    Diagnostic requirements:
    - Frame and Source Introspection: Exceptions inspect caller stack frames and class definitions
      to identify exact file paths, line numbers, and code contexts.
    - Structural Narrative: Error messages tell a four-part story:
        1. Context: Component name, FQN, and source coordinates.
        2. Offending element: Value, type, index, and declaration location.
        3. Violation & Inheritance analysis: Exact broken invariant, including ASCII MRO trees.
        4. Actionable Remedy: Explicit "FIX:" copy-pasteable suggestions.
    - High-visibility ASCII formatting: Formatted banners and structured indentation that stand out
      in terminal and agent logs.
    """

    deps = [ComponentBaseReq]


class NonComponentDependencyErrorReq(Req):
    """
    When a class in `deps` does not inherit from `Component`, the compiler raises
    `NonComponentDependencyError`.

    The error report includes:
    - Component declaring the invalid dependency and its source location.
    - Offending dependency class name and its source location.
    - An ASCII visualization of the offending class's actual MRO hierarchy versus the required
      `Component` ancestor.
    - Architectural explanation detailing why plain classes cannot be dependencies.
    - Actionable fix instructing how to subclass `Component` or remove the invalid item.
    """

    deps = [ComponentInheritanceConstraintReq, ExoticStorytellingErrorsReq]


class DependencyTypeComplianceReq(Req):
    """
    Validates structural types for `deps` and its constituent elements.

    Structural invariants:
    - `deps` attribute type: Must be a sequence (`list` or `tuple`). Passing strings, ints,
      dictionaries, or single classes outside a sequence raises `DependencyDeclarationError`.
    - Element types: Every item in `deps` must be a class (an instance of `type`). Passing instantiated
      objects (e.g., `deps = [Dep1()]`), `None`, or primitives raises `DependencyTypeError`.
    - Remedial hints: When an instantiated object is passed, the error explicitly detects the instance
      and instructs: "Did you mean: deps = [Dep1] (remove parentheses)".
    """

    deps = [ClassMemberDependenciesReq, ExoticStorytellingErrorsReq]


class DependencyGraphDAGIntegrityReq(Req):
    """
    Enforces that the component dependency graph forms a strict Directed Acyclic Graph (DAG).

    Cycles and self-dependencies prevent topological sequencing and wave-based implementation.

    Integrity invariants:
    - Self-Dependency: A component cannot list itself in `deps`. Self-dependencies raise
      `SelfDependencyError` identifying the reflexive cycle.
    - Cycle Detection: Tarjan's or depth-first search cycle detection traverses all declared `deps`
      across the entire specification set.
    - Cycle Reporting: If a circular dependency is detected (e.g. A -> B -> C -> A), the compiler
      raises `CyclicDependencyError` rendering the full cycle loop path with source file coordinates
      for every step in the loop, along with architectural decoupling strategies.
    """

    deps = [ClassMemberDependenciesReq, ExoticStorytellingErrorsReq]


class TopologicalImplementationOrderingFeat(Feat):
    """
    Calculates implementation sequencing waves across components using Kahn's topological sort
    algorithm over `deps`.

    Wave scheduling logic:
    - Wave 1: In-degree 0 components with no prerequisites. These foundational components can be
      assigned to parallel worker agents concurrently.
    - Wave 2..N: Components whose prerequisites have been completed in earlier waves.
    - Determinism: Within each wave, ties are broken deterministically by sorting on FQN strings.

    Consumer integration:
    - CLI: `libspec dependencies` defaults to printing logical dependencies, and adds `--topo`
      to print implementation waves.
    - MCP & REPL: `list_dependencies` and `implementation_order` tools surface the logical DAG.
    """

    deps = [DependencyGraphDAGIntegrityReq]


class ReverseDependencyAnalysisFeat(Feat):
    r"""
    Analyzes reverse dependencies (dependents) and downstream impact blast radius across components.

    While standard dependencies query upstream prerequisites (what a component requires), reverse
    dependencies answer downstream blast radius questions (what depends on a component and what
    is impacted if that component changes).

    Key capabilities:
    - Reverse Adjacency Inversion: Inverts the directed dependency graph ($u \leftarrow v$ for each $v \in deps(u)$).
    - Direct vs Transitive Impact: Supports querying immediate dependents or the full transitive closure
      of downstream components affected by a change.
    - CLI & Interface Integration: Surfaced via the `--rdeps` flag across CLI, MCP tools, and REPL.
    """

    deps = [DependencyGraphDAGIntegrityReq]


class DependencyGraphVisualizationFeat(Feat):
    """
    Renders and exports the component dependency graph and topological wave schedule in multiple visual formats.

    Supported visual targets:
    - Mermaid Flowchart (`--mermaid`): Generates valid GitHub-compatible Mermaid `flowchart TD`
      diagrams with components grouped into topological wave subgraphs and sanitized node identifiers.
    - Graphviz DOT (`--dot`): Emits standards-compliant Graphviz `digraph` definitions featuring wave cluster
      subgraphs, rankdir formatting, and customizable node styling.
    - Standalone Interactive HTML (`--html`): Generates a zero-dependency, self-contained interactive HTML/SVG
      DAG visualizer with topological swimlanes, pan/zoom canvas, upstream/downstream dependency highlighting,
      and component detail inspection.
    - Scoped Subgraph Filtering: Supports scoping diagrams to a single component (`[COMPONENT_REF]`) to visualize
      its upstream prerequisite tree or downstream blast radius (combined with `--rdeps`).
    """

    deps = [TopologicalImplementationOrderingFeat, ReverseDependencyAnalysisFeat]
