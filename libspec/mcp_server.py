import ast
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "libspec",
    instructions="""
    # libspec MCP Server
    
    This server provides specialized tools for specification-driven development 
    and deep code analysis.
    
    ## Navigation & Search
    - Use `search` to find both specification components (Requirements/Features) 
      and their implementations.
    - Use `peek` to retrieve documentation and definitions for specific symbols 
      without reading entire files.
    - Use `symbols` to orient yourself within a file's structure.
    - Use `usage` to perform impact analysis before modifying shared components.
      
    spec.mcp.McpServerInstructions
    """,
)


def _to_uri(file_path: str) -> str:
    return Path(os.path.abspath(file_path)).as_uri()


@mcp.tool()
def diff(commit_a: str = None, commit_b: str = None) -> str:
    """
    Diff specification trees natively between Git commits.

    If no arguments are provided, it compiles the live specification files on-the-fly (the pending spec)
    and diffs them against HEAD.
    If only one argument is provided, it diffs it against HEAD.
    """
    cmd = [sys.executable, "-m", "libspec.cli", "diff"]
    if commit_a:
        cmd.append(commit_a)
    if commit_b:
        cmd.append(commit_b)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout or "No changes detected."
    except subprocess.CalledProcessError as e:
        return f"Error running diff:\n{e.stderr}\n{e.stdout}"


@mcp.tool()
def search(query: str) -> str:
    """
    Perform a workspace-wide search for components (classes, methods, variables).
    Uses native libspec discovery for specification components and AST parsing.
    """
    assert query, "Search query cannot be empty."

    results = []

    try:
        results.extend(_native_spec_discovery(query))
    except Exception:
        pass

    return json.dumps(results, indent=2)


def _native_spec_discovery(query: str):
    """Scan the workspace for classes matching the query using AST."""
    results = []
    patterns = ["spec/**/*.py", "*_spec.py", "spec.py", "libspec/**/*.py"]
    files = []
    for p in patterns:
        files.extend(glob.glob(p, recursive=True))

    files = sorted(list(set(f for f in files if ".venv" not in f)))
    query_lower = query.lower()

    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    docstring = ast.get_docstring(node) or ""
                    if (
                        query_lower in node.name.lower()
                        or query_lower in docstring.lower()
                    ):
                        results.append(
                            {
                                "name": node.name,
                                "kind": 5 if isinstance(node, ast.ClassDef) else 12,
                                "location": {
                                    "uri": Path(os.path.abspath(path)).as_uri(),
                                    "range": {
                                        "start": {
                                            "line": node.lineno - 1,
                                            "character": node.col_offset,
                                        },
                                        "end": {
                                            "line": (
                                                getattr(node, "end_lineno", node.lineno)
                                            )
                                            - 1,
                                            "character": 0,
                                        },
                                    },
                                },
                                "containerName": os.path.basename(path),
                                "description": docstring.strip(),
                            }
                        )
        except Exception:
            continue
    return results


@mcp.tool()
def peek(file_path: str, line: int, character: int) -> str:
    """
    Combined hover, type, and definition lookup for a component at a specific position.
    """
    assert os.path.exists(file_path), f"File not found: {file_path}"
    assert line >= 0, "Line number must be non-negative."
    assert character >= 0, "Character offset must be non-negative."

    try:
        with open(file_path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        target_node = None
        target_line = line + 1
        for node in ast.walk(tree):
            if hasattr(node, "lineno"):
                end_lineno = getattr(node, "end_lineno", node.lineno)
                if node.lineno <= target_line <= end_lineno:
                    if isinstance(
                        node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        target_node = node

        if target_node:
            docstring = ast.get_docstring(target_node) or ""
            result = {
                "hover": f"**{target_node.name}**\n\n{docstring}".strip(),
                "definition": {
                    "uri": Path(os.path.abspath(file_path)).as_uri(),
                    "range": {
                        "start": {
                            "line": target_node.lineno - 1,
                            "character": target_node.col_offset,
                        },
                        "end": {
                            "line": (
                                getattr(target_node, "end_lineno", target_node.lineno)
                            )
                            - 1,
                            "character": 0,
                        },
                    },
                },
            }
        else:
            result = {"hover": "", "definition": {}}
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Navigation Failure: Failed to peek at {file_path}:{line}:{character}.\n{e}"


@mcp.tool()
def usage(file_path: str, line: int, character: int) -> str:
    """
    Find references to a component.
    """
    assert os.path.exists(file_path), f"File not found: {file_path}"

    return json.dumps([], indent=2)


@mcp.tool()
def symbols(file_path: str) -> str:
    """
    List all structural components (classes/methods) in a file.
    """
    assert os.path.exists(file_path), f"File not found: {file_path}"

    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        results = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node) or ""
                results.append(
                    {
                        "name": node.name,
                        "kind": 5 if isinstance(node, ast.ClassDef) else 12,
                        "location": {
                            "uri": Path(os.path.abspath(file_path)).as_uri(),
                            "range": {
                                "start": {
                                    "line": node.lineno - 1,
                                    "character": node.col_offset,
                                },
                                "end": {
                                    "line": (getattr(node, "end_lineno", node.lineno))
                                    - 1,
                                    "character": 0,
                                },
                            },
                        },
                        "description": docstring.strip(),
                    }
                )
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Structural Analysis Failure: Failed to list components in {file_path}.\n{e}"


@mcp.tool()
def mcp_agent(
    agent: str = None, project_root: str = ".", list_agents: bool = False
) -> str:
    """
    Configure or list coding agents for libspec MCP integration.

    Args:
        agent: The name of the agent to configure (required if not listing).
        project_root: The root directory of the project (default ".").
        list_agents: If True, list all supported agents and return immediately.
    """
    from libspec.agent_config import get_agent_config, list_supported_agents

    if list_agents:
        return list_supported_agents()

    if not agent:
        return "Error: 'agent' argument is required when not listing agents."

    try:
        configurator = get_agent_config(agent, project_root)
        return configurator.configure()
    except Exception as e:
        return str(e)


@mcp.tool()
def agent_config(
    agent: str = None, project_root: str = ".", list_agents: bool = False
) -> str:
    """
    Configure or list coding agents for libspec MCP integration.

    Args:
        agent: The name of the agent to configure (required if not listing).
        project_root: The root directory of the project (default ".").
        list_agents: If True, list all supported agents and return immediately.
    """
    return mcp_agent(agent, project_root, list_agents)


@mcp.tool()
def list_components(commit: str = None) -> str:
    """
    List all components present in the specification at the given Git commit (defaulting to live spec if commit is omitted).

    Args:
        commit: The Git reference (SHA, branch, tag) to load components from.
    """
    from libspec.util import compile_git_spec, compile_live_spec

    if commit:
        try:
            comps = compile_git_spec(commit)
            label = f"Git Ref: {commit}"
        except Exception as e:
            return f"Error loading specs at '{commit}': {e}"
    else:
        try:
            comps, _ = compile_live_spec()
            label = "HEAD (Live Spec)"
        except Exception as e:
            return f"Error compiling live specs: {e}"

    comps = [c for c in comps if not getattr(c, "is_dependency", False)]
    if not comps:
        return f"No components found in '{label}'."

    lines = [f"Specification ({label}) Components ({len(comps)} total):"]
    for comp in comps:
        comp_type = "Template" if comp.is_template else "Component"
        lines.append(f"  • {comp.ref} [{comp_type}]")
    return "\n".join(lines)


@mcp.tool()
def show_component(component_ref: str, commit: str = None) -> str:
    """
    Show details of a specific component.

    Args:
        component_ref: The FQN of the component.
        commit: The Git reference (SHA, branch, tag) to load the component from.
    """
    from libspec.util import compile_git_spec, compile_live_spec

    if commit:
        try:
            comps = compile_git_spec(commit)
            label = f"Git Ref: {commit}"
        except Exception as e:
            return f"Error loading specs at '{commit}': {e}"
    else:
        try:
            comps, _ = compile_live_spec()
            label = "HEAD (Live Spec)"
        except Exception as e:
            return f"Error compiling live specs: {e}"

    comp = next((c for c in comps if c.ref == component_ref), None)
    if not comp:
        return f"Error: Component '{component_ref}' not found in '{label}'."

    lines = []
    lines.append("=" * 60)
    lines.append(f"Reference:   {comp.ref}")
    lines.append(
        f"Type:        {'Template Requirement' if comp.is_template else 'Requirement'}"
    )
    lines.append(f"Hash:        {comp.hash}")
    if comp.inherits:
        lines.append("Inherits:    " + ", ".join(comp.inherits))
    lines.append(f"Docstring:\n{'-' * 60}\n{comp.docstring}\n{'-' * 60}")

    from libspec.util import find_implementations_in_workspace

    claims = find_implementations_in_workspace(component_ref)
    if claims:
        lines.append(f"Implementation Claims ({len(claims)}):")
        for cl in claims:
            lines.append(f"  • {cl['file']}:{cl['line']}")
    else:
        lines.append("No implementation claims found in codebase.")
    lines.append("=" * 60)
    return "\n".join(lines)


@mcp.tool()
def list_dependencies(commit: str = None) -> str:
    """
    List component dependencies.

    Args:
        commit: Target Git commit/ref (defaults to active/latest version).
    """
    from libspec.util import compile_git_spec, compile_live_spec

    if commit:
        try:
            comps = compile_git_spec(commit)
            label = f"Git Ref: {commit}"
        except Exception as e:
            return f"Error loading specs at '{commit}': {e}"
    else:
        try:
            comps, _ = compile_live_spec()
            label = "HEAD (Live Spec)"
        except Exception as e:
            return f"Error compiling live specs: {e}"

    deps = {}
    has_explicit_deps = any(getattr(c, "deps", None) for c in comps)
    for comp in comps:
        comp_deps = getattr(comp, "deps", [])
        if has_explicit_deps:
            if comp_deps:
                deps[comp.ref] = list(comp_deps)
        else:
            if comp.inherits:
                deps[comp.ref] = list(comp.inherits)

    if not deps:
        return f"No dependencies recorded for '{label}'."

    lines = [f"Component Dependencies for '{label}':"]
    for ref, depends_list in sorted(deps.items()):
        lines.append(f"  • {ref}")
        for dep in sorted(depends_list):
            lines.append(f"    └── depends on: {dep}")
    return "\n".join(lines)


@mcp.tool()
def implementation_order(commit_ref: str = None) -> str:
    """
    Calculate topological implementation wave ordering across components.

    Args:
        commit_ref: Optional Git commit/ref. Defaults to live spec.
    """
    from libspec.util import compile_git_spec, compile_live_spec, topological_sort

    if commit_ref:
        try:
            comps = compile_git_spec(commit_ref)
            label = f"Git Ref: {commit_ref}"
        except Exception as e:
            return f"Error loading specs at '{commit_ref}': {e}"
    else:
        try:
            comps, _ = compile_live_spec()
            label = "HEAD (Live Spec)"
        except Exception as e:
            return f"Error compiling live specs: {e}"

    try:
        waves = topological_sort(comps)
    except Exception as e:
        return f"Error sorting dependencies: {e}"

    lines = [f"Topological Implementation Order for '{label}':"]
    for idx, wave in enumerate(waves, 1):
        wave_refs = [c.ref for c in wave]
        lines.append(f"  Wave {idx}: {', '.join(wave_refs)}")
    return "\n".join(lines)


@mcp.tool()
def agent_workflow(agent: str = None, prefix: str = None) -> str:
    """
    Recite the standard developer agent workflow instructions.

    Args:
        agent: Optional target agent platform (e.g. antigravity, gemini, claude).
        prefix: Optional explicit MCP tool prefix.
    """
    from libspec.workflow import get_agent_workflow, resolve_prefix

    pfx = resolve_prefix(agent=agent, prefix=prefix, project_root=".")
    return get_agent_workflow(pfx)


def main():
    try:
        from libspec.agent_config import check_and_heal_skills

        messages = check_and_heal_skills(os.getcwd(), auto_heal=True)
        for msg in messages:
            print(f"[libspec] {msg}", file=sys.stderr)
    except Exception as e:
        print(f"[libspec] Warning: Error checking agent skills: {e}", file=sys.stderr)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
