"""
Dependency evaluation, validation, DAG integrity enforcement, and exotic error formatting.
"""

from __future__ import annotations

import inspect
import json
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


def _sanitize_mermaid_id(name: str) -> str:
    """Sanitize a component ref into a valid Mermaid node identifier."""
    sanitized = "".join(c if c.isalnum() else "_" for c in name)
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized or "node"


def _normalize_component_graph(
    components_or_map: Any,
) -> tuple[
    dict[str, Any],
    dict[str, list[str]],
    dict[str, str],
    dict[str, bool],
    dict[str, str],
]:
    """
    Normalize various component inputs into consistent mapping dictionaries.

    Returns:
        nodes: dict of ref -> component object or class
        adj: dict of ref -> list of direct prerequisite refs
        docstrings: dict of ref -> docstring
        is_template: dict of ref -> bool
        locs: dict of ref -> source location string
    """
    nodes: dict[str, Any] = {}
    adj: dict[str, list[str]] = {}
    docstrings: dict[str, str] = {}
    is_template: dict[str, bool] = {}
    locs: dict[str, str] = {}

    if isinstance(components_or_map, dict):
        for k, v in components_or_map.items():
            k_ref = fqn(k) if isinstance(k, type) else str(k)
            nodes[k_ref] = k
            adj[k_ref] = [fqn(x) if isinstance(x, type) else str(x) for x in v]
            docstrings[k_ref] = (inspect.getdoc(k) or "") if isinstance(k, type) else ""
            is_template[k_ref] = getattr(k, "is_template", False)
            locs[k_ref] = (
                _get_class_source_loc(k)
                if isinstance(k, type)
                else getattr(k, "source", "unknown")
            )
    elif isinstance(components_or_map, (list, tuple)):
        for item in components_or_map:
            if isinstance(item, type):
                ref = fqn(item)
                nodes[ref] = item
                deps = evaluate_component_dependencies(item)
                adj[ref] = [fqn(d) for d in deps]
                docstrings[ref] = inspect.getdoc(item) or ""
                is_template[ref] = getattr(item, "is_template", False)
                locs[ref] = _get_class_source_loc(item)
            elif hasattr(item, "ref"):
                ref = item.ref
                nodes[ref] = item
                adj[ref] = list(getattr(item, "deps", []))
                docstrings[ref] = getattr(item, "docstring", "") or ""
                is_template[ref] = getattr(item, "is_template", False)
                locs[ref] = getattr(item, "file", "unknown")
            else:
                ref = str(item)
                nodes[ref] = item
                adj[ref] = []
                docstrings[ref] = ""
                is_template[ref] = False
                locs[ref] = "unknown"

    return nodes, adj, docstrings, is_template, locs


# REQUIREMENT-ID: spec.dependencies.ReverseDependencyAnalysisFeat
def compute_reverse_dependencies(
    components_or_map: Any,
    target_ref: str | None = None,
    transitive: bool = False,
) -> dict[str, list[str]]:
    """
    Compute reverse dependencies (dependents / downstream blast radius) for components.

    Inverts directed dependency edges (u <- v where v in deps(u)).
    If target_ref is provided, returns only the entry for that component.
    If transitive is True, returns the full transitive closure of downstream components.
    """
    nodes, adj, _, _, _ = _normalize_component_graph(components_or_map)

    # Invert adjacency
    radj: dict[str, list[str]] = {k: [] for k in nodes}
    for comp_ref, prereqs in adj.items():
        for prereq in prereqs:
            if prereq not in radj:
                radj[prereq] = []
            if comp_ref not in radj[prereq]:
                radj[prereq].append(comp_ref)

    if transitive:
        transitive_radj: dict[str, list[str]] = {}
        targets = [target_ref] if target_ref is not None else list(radj.keys())
        for start_node in targets:
            visited: set[str] = set()
            queue = list(radj.get(start_node, []))
            while queue:
                curr = queue.pop(0)
                if curr not in visited:
                    visited.add(curr)
                    queue.extend(radj.get(curr, []))
            transitive_radj[start_node] = sorted(visited)
        radj = transitive_radj

    if target_ref is not None:
        return {target_ref: sorted(radj.get(target_ref, []))}

    return {k: sorted(v) for k, v in sorted(radj.items())}


def filter_subgraph(
    components_or_map: Any,
    target_ref: str,
    rdeps: bool = False,
) -> tuple[set[str], dict[str, list[str]]]:
    """
    Extract a scoped subgraph centered on target_ref.

    If rdeps is False (default): Traverses upstream prerequisites.
    If rdeps is True: Traverses downstream dependents (blast radius).

    Returns:
        (reachable_nodes, filtered_edges)
    """
    nodes, adj, _, _, _ = _normalize_component_graph(components_or_map)
    radj = compute_reverse_dependencies(components_or_map)

    traversal_edges = radj if rdeps else adj
    reachable: set[str] = {target_ref} if target_ref in nodes else set()
    queue = [target_ref] if target_ref in nodes else []

    while queue:
        curr = queue.pop(0)
        for nxt in traversal_edges.get(curr, []):
            if nxt not in reachable:
                reachable.add(nxt)
                queue.append(nxt)

    active_edges = radj if rdeps else adj
    filtered_edges = {
        k: [d for d in active_edges.get(k, []) if d in reachable] for k in reachable
    }

    return reachable, filtered_edges


# REQUIREMENT-ID: spec.dependencies.DependencyGraphVisualizationFeat
def render_mermaid(
    components_or_map: Any,
    target_ref: str | None = None,
    rdeps: bool = False,
    waves: list[list[Any]] | None = None,
) -> str:
    """
    Render component dependency graph as GitHub-compatible Mermaid markdown.
    """
    from libspec.util import topological_sort

    nodes, adj, _, _, _ = _normalize_component_graph(components_or_map)
    radj = compute_reverse_dependencies(components_or_map)

    if target_ref:
        reachable, filtered_edges = filter_subgraph(
            components_or_map, target_ref, rdeps=rdeps
        )
    else:
        reachable = set(nodes.keys())
        filtered_edges = radj if rdeps else adj

    if waves is None:
        try:
            computed_waves = topological_sort(components_or_map)
        except Exception:
            computed_waves = [[n] for n in nodes.values()]
    else:
        computed_waves = waves

    lines = ["flowchart TD"]

    # Wave subgraphs
    for idx, wave in enumerate(computed_waves, 1):
        wave_members: list[str] = []
        for item in wave:
            r = (
                item.ref
                if hasattr(item, "ref")
                else fqn(item)
                if isinstance(item, type)
                else str(item)
            )
            if r in reachable:
                wave_members.append(r)

        if not wave_members:
            continue

        lines.append(f'  subgraph Wave_{idx} ["Wave {idx}"]')
        for r in sorted(wave_members):
            node_id = _sanitize_mermaid_id(r)
            lines.append(f'    {node_id}["{r}"]')
        lines.append("  end")

    # Directed edges
    edge_lines = []
    for src, targets in sorted(filtered_edges.items()):
        src_id = _sanitize_mermaid_id(src)
        for tgt in sorted(targets):
            tgt_id = _sanitize_mermaid_id(tgt)
            if rdeps:
                edge_lines.append(f"  {src_id} -->|required by| {tgt_id}")
            else:
                edge_lines.append(f"  {src_id} --> {tgt_id}")

    if edge_lines:
        lines.append("")
        lines.extend(edge_lines)

    return "\n".join(lines)


def render_dot(
    components_or_map: Any,
    target_ref: str | None = None,
    rdeps: bool = False,
    waves: list[list[Any]] | None = None,
) -> str:
    """
    Render component dependency graph as Graphviz DOT digraph definition.
    """
    from libspec.util import topological_sort

    nodes, adj, _, _, _ = _normalize_component_graph(components_or_map)
    radj = compute_reverse_dependencies(components_or_map)

    if target_ref:
        reachable, filtered_edges = filter_subgraph(
            components_or_map, target_ref, rdeps=rdeps
        )
    else:
        reachable = set(nodes.keys())
        filtered_edges = radj if rdeps else adj

    if waves is None:
        try:
            computed_waves = topological_sort(components_or_map)
        except Exception:
            computed_waves = [[n] for n in nodes.values()]
    else:
        computed_waves = waves

    lines = [
        "digraph DependencyGraph {",
        '  rankdir="TB";',
        '  graph [fontname="Helvetica,Arial,sans-serif", bgcolor="#ffffff", pad="0.5", nodesep="0.4", ranksep="0.6"];',
        '  node [shape="box", style="rounded,filled", fillcolor="#f8fafc", color="#64748b", fontname="Helvetica,Arial,sans-serif", fontsize=10, margin="0.15,0.08"];',
        '  edge [color="#94a3b8", fontname="Helvetica,Arial,sans-serif", fontsize=8];',
        "",
    ]

    # Cluster subgraphs for waves
    for idx, wave in enumerate(computed_waves, 1):
        wave_members = []
        for item in wave:
            r = (
                item.ref
                if hasattr(item, "ref")
                else fqn(item)
                if isinstance(item, type)
                else str(item)
            )
            if r in reachable:
                wave_members.append(r)

        if not wave_members:
            continue

        lines.append(f"  subgraph cluster_wave_{idx} {{")
        lines.append(f'    label="Wave {idx}";')
        lines.append('    style="rounded,dashed";')
        lines.append('    color="#cbd5e1";')
        lines.append('    fontcolor="#475569";')
        lines.append("    fontsize=11;")
        for r in sorted(wave_members):
            lines.append(f'    "{r}";')
        lines.append("  }")

    lines.append("")
    for src, targets in sorted(filtered_edges.items()):
        for tgt in sorted(targets):
            lbl = ' [label="required by"]' if rdeps else ""
            lines.append(f'  "{src}" -> "{tgt}"{lbl};')

    lines.append("}")
    return "\n".join(lines)


def render_html_dag(
    components_or_map: Any,
    target_ref: str | None = None,
    rdeps: bool = False,
    waves: list[list[Any]] | None = None,
    output_path: str | None = None,
) -> str:
    """
    Generate a zero-dependency, self-contained, interactive HTML/SVG DAG visualization.
    """
    from libspec.util import topological_sort

    nodes, adj, docstrings, is_template, locs = _normalize_component_graph(
        components_or_map
    )
    radj = compute_reverse_dependencies(components_or_map)

    if waves is None:
        try:
            computed_waves = topological_sort(components_or_map)
        except Exception:
            computed_waves = [[n] for n in nodes.values()]
    else:
        computed_waves = waves

    # Map each component to its wave index (1-indexed)
    comp_wave: dict[str, int] = {}
    for idx, wave in enumerate(computed_waves, 1):
        for item in wave:
            r = (
                item.ref
                if hasattr(item, "ref")
                else fqn(item)
                if isinstance(item, type)
                else str(item)
            )
            comp_wave[r] = idx

    # Build structured JSON payload for standalone embedded interactivity
    component_data = []
    for ref, node in sorted(nodes.items()):
        component_data.append(
            {
                "ref": ref,
                "name": ref.split(".")[-1],
                "module": ".".join(ref.split(".")[:-1]),
                "wave": comp_wave.get(ref, 1),
                "is_template": is_template.get(ref, False),
                "docstring": docstrings.get(ref, ""),
                "deps": adj.get(ref, []),
                "rdeps": radj.get(ref, []),
                "loc": locs.get(ref, "unknown"),
            }
        )

    edges_data = []
    for src, targets in sorted(adj.items()):
        for tgt in targets:
            edges_data.append({"from": src, "to": tgt})

    total_waves = len(computed_waves)
    total_comps = len(nodes)
    total_edges = sum(len(v) for v in adj.values())

    payload = {
        "components": component_data,
        "edges": edges_data,
        "total_waves": total_waves,
        "initial_target": target_ref or "",
        "initial_rdeps": rdeps,
    }
    payload_json = json.dumps(payload)

    # Embedded self-contained HTML/CSS/JS template
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>libspec - Component Dependency Graph</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --prereq-color: #38bdf8;
      --rdep-color: #f59e0b;
      --wave-bg: rgba(30, 41, 59, 0.5);
      --wave-border: #334155;
      --edge-color: #475569;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: var(--font);
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      user-select: none;
    }}
    header {{
      background: #1e293b;
      border-bottom: 1px solid #334155;
      padding: 10px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      z-index: 10;
    }}
    .title-group {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .title-group h1 {{
      font-size: 1.1rem;
      font-weight: 700;
      color: var(--text);
      letter-spacing: -0.02em;
    }}
    .stats-badge {{
      background: #0f172a;
      border: 1px solid #334155;
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 0.75rem;
      color: var(--text-muted);
    }}
    .stats-badge span {{
      color: var(--accent);
      font-weight: 600;
    }}
    .controls {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    input[type="search"] {{
      background: #0f172a;
      border: 1px solid #334155;
      color: var(--text);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.85rem;
      width: 220px;
      outline: none;
      transition: border-color 0.15s;
    }}
    input[type="search"]:focus {{
      border-color: var(--accent);
    }}
    button {{
      background: #334155;
      color: var(--text);
      border: none;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.8rem;
      cursor: pointer;
      font-weight: 500;
      transition: background 0.15s;
    }}
    button:hover {{
      background: #475569;
    }}
    button.primary {{
      background: var(--accent);
      color: #0f172a;
      font-weight: 600;
    }}
    button.primary:hover {{
      background: var(--accent-hover);
    }}
    main {{
      flex: 1;
      position: relative;
      overflow: hidden;
      display: flex;
    }}
    #viewport {{
      flex: 1;
      height: 100%;
      cursor: grab;
    }}
    #viewport:active {{
      cursor: grabbing;
    }}
    #dag-svg {{
      width: 100%;
      height: 100%;
    }}
    /* Side Inspector Drawer */
    #inspector {{
      width: 380px;
      background: #1e293b;
      border-left: 1px solid #334155;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      transition: transform 0.2s ease;
      z-index: 20;
    }}
    #inspector.hidden {{
      display: none;
    }}
    .inspector-header {{
      padding: 16px;
      border-bottom: 1px solid #334155;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .inspector-header h2 {{
      font-size: 1rem;
      font-weight: 600;
      color: var(--accent);
      word-break: break-all;
    }}
    .inspector-body {{
      padding: 16px;
      overflow-y: auto;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 14px;
      user-select: text;
    }}
    .prop-group {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .prop-label {{
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      font-weight: 600;
    }}
    .prop-val {{
      font-size: 0.85rem;
      color: var(--text);
    }}
    .doc-box {{
      background: #0f172a;
      padding: 10px;
      border-radius: 6px;
      font-family: monospace;
      font-size: 0.78rem;
      line-height: 1.4;
      white-space: pre-wrap;
      max-height: 200px;
      overflow-y: auto;
      border: 1px solid #334155;
    }}
    .link-list {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .link-item {{
      background: #0f172a;
      padding: 6px 10px;
      border-radius: 4px;
      font-size: 0.8rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border: 1px solid #334155;
      transition: border-color 0.15s, background 0.15s;
    }}
    .link-item:hover {{
      border-color: var(--accent);
      background: #1e293b;
    }}
    /* SVG Styling */
    .wave-column {{
      fill: var(--wave-bg);
      stroke: var(--wave-border);
      stroke-dasharray: 4,4;
      rx: 8;
    }}
    .wave-label {{
      fill: var(--text-muted);
      font-size: 13px;
      font-weight: 700;
      text-anchor: middle;
      letter-spacing: 0.05em;
    }}
    .comp-node {{
      cursor: pointer;
      transition: opacity 0.15s, transform 0.15s;
    }}
    .comp-node rect {{
      fill: var(--card-bg);
      stroke: var(--card-border);
      stroke-width: 1.5;
      rx: 6;
      transition: stroke 0.15s, fill 0.15s;
    }}
    .comp-node:hover rect {{
      stroke: var(--accent);
      fill: #26354a;
    }}
    .comp-node.selected rect {{
      stroke: #ffffff;
      stroke-width: 2.5;
      fill: #1e3a8a;
    }}
    .comp-node.is-prereq rect {{
      stroke: var(--prereq-color);
      stroke-width: 2;
      fill: #0c4a6e;
    }}
    .comp-node.is-rdep rect {{
      stroke: var(--rdep-color);
      stroke-width: 2;
      fill: #78350f;
    }}
    .comp-node.dimmed {{
      opacity: 0.2;
    }}
    .node-title {{
      fill: var(--text);
      font-size: 12px;
      font-weight: 600;
    }}
    .node-sub {{
      fill: var(--text-muted);
      font-size: 10px;
    }}
    .edge-line {{
      fill: none;
      stroke: var(--edge-color);
      stroke-width: 1.5;
      transition: stroke 0.15s, stroke-width 0.15s, opacity 0.15s;
    }}
    .edge-line.active-prereq {{
      stroke: var(--prereq-color);
      stroke-width: 2.5;
      opacity: 1;
    }}
    .edge-line.active-rdep {{
      stroke: var(--rdep-color);
      stroke-width: 2.5;
      opacity: 1;
    }}
    .edge-line.dimmed {{
      opacity: 0.1;
    }}
  </style>
</head>
<body>
  <header>
    <div class="title-group">
      <h1>libspec graph</h1>
      <div class="stats-badge">Components: <span>{total_comps}</span></div>
      <div class="stats-badge">Waves: <span>{total_waves}</span></div>
      <div class="stats-badge">Edges: <span>{total_edges}</span></div>
    </div>
    <div class="controls">
      <input type="search" id="search-input" placeholder="Filter component..." />
      <button id="btn-reset">Reset View</button>
      <button id="btn-clear-selection">Clear Selection</button>
    </div>
  </header>
  <main>
    <div id="viewport">
      <svg id="dag-svg">
        <defs>
          <marker id="arrow-default" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <polygon points="0 0, 8 4, 0 8" fill="#475569" />
          </marker>
          <marker id="arrow-prereq" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <polygon points="0 0, 8 4, 0 8" fill="#38bdf8" />
          </marker>
          <marker id="arrow-rdep" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <polygon points="0 0, 8 4, 0 8" fill="#f59e0b" />
          </marker>
        </defs>
        <g id="canvas-content"></g>
      </svg>
    </div>
    <aside id="inspector" class="hidden">
      <div class="inspector-header">
        <h2 id="insp-name">Component Details</h2>
        <button id="btn-close-insp">&times;</button>
      </div>
      <div class="inspector-body">
        <div class="prop-group">
          <span class="prop-label">Full Reference</span>
          <span class="prop-val" id="insp-ref"></span>
        </div>
        <div class="prop-group">
          <span class="prop-label">Topological Wave</span>
          <span class="prop-val" id="insp-wave"></span>
        </div>
        <div class="prop-group">
          <span class="prop-label">Source Location</span>
          <span class="prop-val" id="insp-loc"></span>
        </div>
        <div class="prop-group">
          <span class="prop-label">Docstring</span>
          <pre class="doc-box" id="insp-doc"></pre>
        </div>
        <div class="prop-group">
          <span class="prop-label">Direct Prerequisites (<span id="insp-deps-count">0</span>)</span>
          <div class="link-list" id="insp-deps-list"></div>
        </div>
        <div class="prop-group">
          <span class="prop-label">Downstream Dependents / Blast Radius (<span id="insp-rdeps-count">0</span>)</span>
          <div class="link-list" id="insp-rdeps-list"></div>
        </div>
      </div>
    </aside>
  </main>

  <script id="dag-data" type="application/json">
    {payload_json}
  </script>

  <script>
    const data = JSON.parse(document.getElementById('dag-data').textContent);
    const svg = document.getElementById('dag-svg');
    const content = document.getElementById('canvas-content');
    const inspector = document.getElementById('inspector');
    const searchInput = document.getElementById('search-input');

    // Canvas pan/zoom state
    let transform = {{ x: 40, y: 40, scale: 1 }};
    let isPanning = false;
    let startPoint = {{ x: 0, y: 0 }};
    let selectedRef = null;

    const compMap = new Map();
    data.components.forEach(c => compMap.set(c.ref, c));

    // Layout calculations
    const waveWidth = 280;
    const waveGap = 80;
    const nodeWidth = 240;
    const nodeHeight = 54;
    const nodeGap = 20;
    const headerHeight = 40;

    // Group components by wave
    const waveGroups = new Map();
    for (let i = 1; i <= data.total_waves; i++) waveGroups.set(i, []);
    data.components.forEach(c => {{
      const list = waveGroups.get(c.wave) || [];
      list.push(c);
      waveGroups.set(c.wave, list);
    }});

    // Calculate node coordinates
    const nodeCoords = new Map();
    let maxWaveY = 0;

    waveGroups.forEach((comps, waveIdx) => {{
      const x = (waveIdx - 1) * (waveWidth + waveGap) + 40;
      comps.forEach((c, idx) => {{
        const y = 60 + idx * (nodeHeight + nodeGap);
        nodeCoords.set(c.ref, {{ x: x + 20, y: y, w: nodeWidth, h: nodeHeight, cx: x + 20 + nodeWidth/2, cy: y + nodeHeight/2 }});
        if (y + nodeHeight > maxWaveY) maxWaveY = y + nodeHeight;
      }});
    }});

    function updateTransform() {{
      content.setAttribute('transform', `translate(${{transform.x}}, ${{transform.y}}) scale(${{transform.scale}})`);
    }}

    function renderDAG() {{
      content.innerHTML = '';

      // Draw Wave Swimlanes
      waveGroups.forEach((comps, waveIdx) => {{
        const x = (waveIdx - 1) * (waveWidth + waveGap) + 40;
        const colHeight = Math.max(maxWaveY + 40, 600);

        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('class', 'wave-column');
        rect.setAttribute('x', x);
        rect.setAttribute('y', 20);
        rect.setAttribute('width', waveWidth);
        rect.setAttribute('height', colHeight);
        content.appendChild(rect);

        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('class', 'wave-label');
        label.setAttribute('x', x + waveWidth / 2);
        label.setAttribute('y', 45);
        label.textContent = `WAVE ${{waveIdx}} (${{comps.length}})`;
        content.appendChild(label);
      }});

      // Draw Edges (Path connecting dependent to prerequisite)
      const edgesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      edgesGroup.setAttribute('id', 'edges-layer');

      data.edges.forEach(edge => {{
        const src = nodeCoords.get(edge.from);
        const tgt = nodeCoords.get(edge.to);
        if (!src || !tgt) return;

        // Draw bezier curve from right/left of node
        const x1 = src.x;
        const y1 = src.cy;
        const x2 = tgt.x + tgt.w;
        const y2 = tgt.cy;
        const dx = Math.abs(x1 - x2) * 0.5;

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('class', 'edge-line');
        path.setAttribute('d', `M ${{x1}} ${{y1}} C ${{x1 - dx}} ${{y1}}, ${{x2 + dx}} ${{y2}}, ${{x2}} ${{y2}}`);
        path.setAttribute('data-from', edge.from);
        path.setAttribute('data-to', edge.to);
        path.setAttribute('marker-end', 'url(#arrow-default)');
        edgesGroup.appendChild(path);
      }});
      content.appendChild(edgesGroup);

      // Draw Nodes
      const nodesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      nodesGroup.setAttribute('id', 'nodes-layer');

      data.components.forEach(c => {{
        const pos = nodeCoords.get(c.ref);
        if (!pos) return;

        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'comp-node');
        g.setAttribute('data-ref', c.ref);
        g.setAttribute('transform', `translate(${{pos.x}}, ${{pos.y}})`);

        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', pos.w);
        rect.setAttribute('height', pos.h);
        g.appendChild(rect);

        const title = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        title.setAttribute('class', 'node-title');
        title.setAttribute('x', 12);
        title.setAttribute('y', 22);
        title.textContent = c.name;
        g.appendChild(title);

        const sub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        sub.setAttribute('class', 'node-sub');
        sub.setAttribute('x', 12);
        sub.setAttribute('y', 40);
        sub.textContent = `${{c.module}} • deps:${{c.deps.length}} | rdeps:${{c.rdeps.length}}`;
        g.appendChild(sub);

        g.addEventListener('click', (e) => {{
          e.stopPropagation();
          selectComponent(c.ref);
        }});

        nodesGroup.appendChild(g);
      }});
      content.appendChild(nodesGroup);

      updateTransform();
    }}

    function selectComponent(ref) {{
      selectedRef = ref;
      const comp = compMap.get(ref);
      if (!comp) return;

      // Update node styles
      const prereqs = new Set(comp.deps);
      const rdeps = new Set(comp.rdeps);

      document.querySelectorAll('.comp-node').forEach(node => {{
        const r = node.getAttribute('data-ref');
        node.classList.remove('selected', 'is-prereq', 'is-rdep', 'dimmed');
        if (r === ref) {{
          node.classList.add('selected');
        }} else if (prereqs.has(r)) {{
          node.classList.add('is-prereq');
        }} else if (rdeps.has(r)) {{
          node.classList.add('is-rdep');
        }} else {{
          node.classList.add('dimmed');
        }}
      }});

      // Update edge styles
      document.querySelectorAll('.edge-line').forEach(edge => {{
        const from = edge.getAttribute('data-from');
        const to = edge.getAttribute('data-to');
        edge.classList.remove('active-prereq', 'active-rdep', 'dimmed');

        if (from === ref) {{
          edge.classList.add('active-prereq');
          edge.setAttribute('marker-end', 'url(#arrow-prereq)');
        }} else if (to === ref) {{
          edge.classList.add('active-rdep');
          edge.setAttribute('marker-end', 'url(#arrow-rdep)');
        }} else {{
          edge.classList.add('dimmed');
          edge.setAttribute('marker-end', 'url(#arrow-default)');
        }}
      }});

      // Populate Inspector
      document.getElementById('insp-name').textContent = comp.name;
      document.getElementById('insp-ref').textContent = comp.ref;
      document.getElementById('insp-wave').textContent = `Wave ${{comp.wave}}`;
      document.getElementById('insp-loc').textContent = comp.loc;
      document.getElementById('insp-doc').textContent = comp.docstring || '(No docstring recorded)';

      const depsList = document.getElementById('insp-deps-list');
      depsList.innerHTML = '';
      document.getElementById('insp-deps-count').textContent = comp.deps.length;
      comp.deps.forEach(d => {{
        const item = document.createElement('div');
        item.className = 'link-item';
        item.textContent = d;
        item.onclick = () => selectComponent(d);
        depsList.appendChild(item);
      }});

      const rdepsList = document.getElementById('insp-rdeps-list');
      rdepsList.innerHTML = '';
      document.getElementById('insp-rdeps-count').textContent = comp.rdeps.length;
      comp.rdeps.forEach(d => {{
        const item = document.createElement('div');
        item.className = 'link-item';
        item.textContent = d;
        item.onclick = () => selectComponent(d);
        rdepsList.appendChild(item);
      }});

      inspector.classList.remove('hidden');
    }}

    function clearSelection() {{
      selectedRef = null;
      document.querySelectorAll('.comp-node').forEach(n => n.classList.remove('selected', 'is-prereq', 'is-rdep', 'dimmed'));
      document.querySelectorAll('.edge-line').forEach(e => {{
        e.classList.remove('active-prereq', 'active-rdep', 'dimmed');
        e.setAttribute('marker-end', 'url(#arrow-default)');
      }});
      inspector.classList.add('hidden');
    }}

    // Pan and Zoom
    svg.addEventListener('mousedown', (e) => {{
      isPanning = true;
      startPoint = {{ x: e.clientX - transform.x, y: e.clientY - transform.y }};
    }});
    window.addEventListener('mousemove', (e) => {{
      if (!isPanning) return;
      transform.x = e.clientX - startPoint.x;
      transform.y = e.clientY - startPoint.y;
      updateTransform();
    }});
    window.addEventListener('mouseup', () => isPanning = false);
    svg.addEventListener('wheel', (e) => {{
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      transform.scale = Math.min(Math.max(transform.scale * zoomFactor, 0.2), 3);
      updateTransform();
    }});

    // Controls
    document.getElementById('btn-reset').addEventListener('click', () => {{
      transform = {{ x: 40, y: 40, scale: 1 }};
      updateTransform();
    }});
    document.getElementById('btn-clear-selection').addEventListener('click', clearSelection);
    document.getElementById('btn-close-insp').addEventListener('click', () => inspector.classList.add('hidden'));
    svg.addEventListener('click', clearSelection);

    // Search filter
    searchInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase().trim();
      if (!q) {{
        clearSelection();
        return;
      }}
      document.querySelectorAll('.comp-node').forEach(node => {{
        const ref = node.getAttribute('data-ref').toLowerCase();
        if (ref.includes(q)) {{
          node.classList.remove('dimmed');
        }} else {{
          node.classList.add('dimmed');
        }}
      }});
    }});

    renderDAG();
    if (data.initial_target) {{
      selectComponent(data.initial_target);
    }}
  </script>
</body>
</html>
"""
    if output_path:
        import os

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    return html
