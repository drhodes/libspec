"""
Dependency evaluation, validation, DAG integrity enforcement, and exotic error formatting.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from libspec.err import (
    CyclicDependencyError,
    DependencyDeclarationError,
    DependencyTypeError,
    NonComponentDependencyError,
    SelfDependencyError,
)
from libspec.util import fqn

if TYPE_CHECKING:
    from libspec.spec_types import Component


def _get_class_source_loc(cls: Any) -> str:
    """Safely extract source file and line for a class or object."""
    target = cls if isinstance(cls, type) else type(cls)
    try:
        source_file = inspect.getsourcefile(target)
        if source_file:
            _, start_line = inspect.getsourcelines(target)
            return f"{source_file}:{start_line}"
    except (OSError, TypeError):
        pass
    return "unknown location"


def _format_mro_tree(cls: type) -> str:
    """Render an ASCII tree of the class's Method Resolution Order (MRO)."""
    lines = ["Actual Inheritance Hierarchy:"]
    indent = 2
    for base in cls.__mro__:
        lines.append(f"{' ' * indent}└── {base.__name__}")
        indent += 4
    return "\n".join(lines)


def evaluate_component_dependencies(cls: type) -> list[type[Component]]:
    """
    Evaluate and validate logical dependencies declared on a Component class.

    Prerequisites are declared via `deps = [Dep1, Dep2, ...]` (or `depends_on`).
    Enforces that all dependencies inherit from `Component` and raises exotic storytelling
    domain exceptions on any violation.
    """
    if "deps" in cls.__dict__:
        raw_deps = cls.__dict__["deps"]
    elif "depends_on" in cls.__dict__:
        raw_deps = cls.__dict__["depends_on"]
    else:
        return []

    from libspec.spec_types import Component

    comp_loc = _get_class_source_loc(cls)
    comp_fqn = fqn(cls)

    # Validate container type
    if not isinstance(raw_deps, (list, tuple)):
        hint = ""
        if isinstance(raw_deps, type):
            hint = f"\n\nDid you mean:\n  deps = [{raw_deps.__name__}]"
        msg = (
            f"\n================================================================================\n"
            f"LIBSPEC DEPENDENCY DECLARATION ERROR: Invalid `deps` Attribute\n"
            f"================================================================================\n"
            f"Component:\n"
            f"  {comp_fqn}\n"
            f"  Location: {comp_loc}\n\n"
            f"Found:\n"
            f"  deps = {repr(raw_deps)} (type: {type(raw_deps).__name__})\n\n"
            f"Violation:\n"
            f"  The `deps` attribute must be a list or tuple of Component classes.{hint}\n\n"
            f"FIX:\n"
            f"  Wrap dependencies in a list: `deps = [...]`\n"
            f"================================================================================"
        )
        raise DependencyDeclarationError(msg)

    evaluated_deps: list[type[Component]] = []
    seen = set()

    for idx, dep in enumerate(raw_deps):
        # Validate that dep is a class
        if not isinstance(dep, type):
            hint = ""
            if hasattr(dep, "__class__") and issubclass(dep.__class__, Component):
                hint = (
                    f"\n\nDid you mean:\n"
                    f"  deps = [{dep.__class__.__name__}]   # <-- Pass the class, not an instantiated object: {dep.__class__.__name__}()\n\n"
                    f"FIX:\n"
                    f"  Remove parentheses from the instantiated dependency in 'deps'."
                )
            else:
                hint = "\n\nFIX:\n  Ensure every item in 'deps' is a class inheriting from 'Component'."

            msg = (
                f"\n================================================================================\n"
                f"LIBSPEC DEPENDENCY TYPE ERROR: Instance Passed Instead of Class\n"
                f"================================================================================\n"
                f"Component:\n"
                f"  {comp_fqn}\n"
                f"  Location: {comp_loc}\n\n"
                f"Offending Value:\n"
                f"  [Index {idx}] {repr(dep)} (type: {type(dep).__name__})\n\n"
                f"Violation:\n"
                f"  Elements in `deps` must be Component classes (types), not instances.{hint}\n"
                f"================================================================================"
            )
            raise DependencyTypeError(msg)

        # Validate self-dependency
        if dep is cls:
            msg = (
                f"\n================================================================================\n"
                f"LIBSPEC DEPENDENCY INTEGRITY ERROR: Self-Dependency Detected\n"
                f"================================================================================\n"
                f"Component:\n"
                f"  {comp_fqn}\n"
                f"  Location: {comp_loc}\n\n"
                f"Violation:\n"
                f"  Component '{cls.__name__}' cannot depend on itself.\n"
                f"  A component's prerequisite must be an external component that can be built\n"
                f"  and satisfied prior to this component.\n\n"
                f"FIX:\n"
                f"  Remove '{cls.__name__}' from its own `deps` list in {comp_loc}.\n"
                f"================================================================================"
            )
            raise SelfDependencyError(msg)

        # Validate Component inheritance
        if not issubclass(dep, Component):
            dep_loc = _get_class_source_loc(dep)
            mro_tree = _format_mro_tree(dep)
            msg = (
                f"\n================================================================================\n"
                f"LIBSPEC DEPENDENCY COMPLIANCE ERROR: Non-Component Dependency Declared\n"
                f"================================================================================\n"
                f"Component:\n"
                f"  {comp_fqn}\n"
                f"  Location: {comp_loc}\n\n"
                f"Offending Dependency:\n"
                f"  [Index {idx}] {dep.__name__} ({dep})\n"
                f"  Location: {dep_loc}\n\n"
                f"Violation:\n"
                f"  All elements in `deps` must inherit from `libspec.Component`.\n"
                f"  Class '{dep.__name__}' does NOT inherit from 'Component'.\n\n"
                f"  {mro_tree}\n\n"
                f"Architectural Explanation:\n"
                f"  libspec enforces that dependency graphs represent logical relationships\n"
                f"  between formal specification components. Plain Python classes, utilities,\n"
                f"  or third-party objects cannot be scheduled or verified in the agent workflow.\n\n"
                f"FIX:\n"
                f"  1. If '{dep.__name__}' is a specification component, inherit from Component:\n"
                f"       class {dep.__name__}(Component):\n"
                f"           ...\n"
                f"  2. Or if '{cls.__name__}' does not depend on a spec component, remove it from 'deps'.\n"
                f"================================================================================"
            )
            raise NonComponentDependencyError(msg)

        if dep not in seen:
            seen.add(dep)
            evaluated_deps.append(dep)

    return evaluated_deps


def validate_dependency_dag(components_or_map: Any) -> None:
    """
    Validate that the dependency graph forms a strict Directed Acyclic Graph (DAG).
    Raises CyclicDependencyError with full ASCII tracepath on cycle detection.
    """
    adj: dict[str, list[str]] = {}
    loc_map: dict[str, str] = {}

    if isinstance(components_or_map, dict):
        for k, v in components_or_map.items():
            k_ref = fqn(k) if isinstance(k, type) else str(k)
            adj[k_ref] = [fqn(x) if isinstance(x, type) else str(x) for x in v]
            loc_map[k_ref] = (
                _get_class_source_loc(k)
                if isinstance(k, type)
                else getattr(k, "source", "unknown")
            )
    elif isinstance(components_or_map, (list, tuple)):
        for item in components_or_map:
            if isinstance(item, type):
                ref = fqn(item)
                deps = evaluate_component_dependencies(item)
                adj[ref] = [fqn(d) for d in deps]
                loc_map[ref] = _get_class_source_loc(item)
            elif hasattr(item, "ref") and hasattr(item, "deps"):
                adj[item.ref] = list(item.deps)
                loc_map[item.ref] = getattr(item, "file", "unknown")
            else:
                ref = str(item)
                adj[ref] = []
                loc_map[ref] = "unknown"

    # DFS cycle detection
    visited: set[str] = set()
    rec_stack: list[str] = []

    def dfs(node: str):
        visited.add(node)
        rec_stack.append(node)

        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_stack:
                # Cycle found!
                cycle_start_idx = rec_stack.index(neighbor)
                cycle_path = rec_stack[cycle_start_idx:] + [neighbor]
                _raise_cyclic_error(cycle_path, loc_map)

        rec_stack.pop()

    for node in list(adj.keys()):
        if node not in visited:
            dfs(node)


def _raise_cyclic_error(cycle_path: list[str], loc_map: dict[str, str]) -> None:
    """Format and raise an exotic CyclicDependencyError."""
    trace_lines = ["  Cycle Trace:"]
    indent = 4
    for i, ref in enumerate(cycle_path):
        loc = loc_map.get(ref, "")
        loc_str = f" ({loc})" if loc and loc != "unknown location" else ""
        if i == 0:
            trace_lines.append(f"{' ' * indent}{ref}{loc_str}")
        elif i == len(cycle_path) - 1:
            trace_lines.append(
                f"{' ' * indent}└── depends on: {ref} [CYCLE CLOSES HERE]"
            )
        else:
            trace_lines.append(f"{' ' * indent}└── depends on: {ref}{loc_str}")
        indent += 2

    involved_lines = []
    unique_nodes = []
    for n in cycle_path[:-1]:
        if n not in unique_nodes:
            unique_nodes.append(n)
            loc = loc_map.get(n, "")
            loc_str = f" ({loc})" if loc and loc != "unknown location" else ""
            involved_lines.append(f"  • {n}{loc_str}")

    msg = (
        "\n================================================================================\n"
        "LIBSPEC DEPENDENCY GRAPH ERROR: Cyclic Dependency Detected (Cycle in DAG)\n"
        "================================================================================\n"
        "A cycle was detected in the component dependency graph:\n\n"
        + "\n".join(trace_lines)
        + "\n\nViolation:\n"
        "  The component dependency graph must be a strict Directed Acyclic Graph (DAG)\n"
        "  so that orchestrator agents can schedule implementation in topological waves.\n"
        "  Components involved in a cycle cannot be topologically sorted.\n\n"
        "Involved Components:\n"
        + "\n".join(involved_lines)
        + "\n\nResolution Strategies:\n"
        "  1. Extract a shared prerequisite: Extract the common interface or contract\n"
        "     into a separate foundational component, and have both depend on it.\n"
        "  2. Invert edge: Re-examine if the dependency truly runs in both directions.\n"
        "================================================================================"
    )
    raise CyclicDependencyError(msg)
