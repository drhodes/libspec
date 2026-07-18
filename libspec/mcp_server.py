"""
MCP Server entry point for libspec.
"""

import ast
import glob
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from libspec.lsp_client import LspClient, LspError

mcp = FastMCP(
    "libspec",
    instructions="""
    # libspec MCP Server
    
    This server provides specialized tools for specification-driven development 
    and deep code analysis.
    
    ## Navigation & Search (Prefer LSP over Grep)
    - Always prefer LSP-based tools (`search`, `peek`, `symbols`, `usage`) 
      over generic `grep` when you need semantic understanding of the code.
    - Use `search` to find both specification components (Requirements/Features) 
      and their implementations.
    - Use `peek` to retrieve documentation and definitions for specific symbols 
      without reading entire files.
    - Use `symbols` to orient yourself within a new file's structure.
    - Use `usage` to perform impact analysis before modifying shared components.
    
    ## Lifecycle
    - The background LSP server (`pylsp`) auto-initializes on the first call to 
      any LSP-dependent tool. No manual setup is required.
      
    spec.mcp.McpServerInstructions
    """,
)

# Global LSP client instance
lsp = LspClient()
lsp_lock = threading.Lock()


def _ensure_lsp_started(requested_root: str = None):
    """
    Internal helper to ensure the LSP process is running.
    Auto-starts with sensible defaults if not already initialized.
    """
    if lsp.process:
        return

    with lsp_lock:
        if lsp.process:
            return

        # Default root discovery logic
        if requested_root:
            root_dir = requested_root
        else:
            root_candidates = ["spec", "."]
            root_dir = next((d for d in root_candidates if os.path.isdir(d)), ".")

        # Call start_lsp logic directly to ensure initialization
        root_uri = _to_uri(root_dir)
        try:
            lsp.start(root_uri)
        except Exception as e:
            # spec.lsp_auto_init.DiagnosticInitialization
            raise LspError(
                f"Failed to auto-initialize LSP for workspace '{root_dir}'.",
                step="auto-start",
                details=f"Original Error: {e}\nEnsure 'python-lsp-server' is installed (e.g., `uv add --dev python-lsp-server`).",
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
def start_lsp(root_dir: str = "spec") -> str:
    """
    Start the background pylsp server for the given workspace.
    """
    try:
        _ensure_lsp_started(root_dir)  # Ensure idempotency and state safety
        return f"LSP Server (pylsp) started for {root_dir}"
    except Exception as e:
        return f"Error starting LSP: {e}"


@mcp.tool()
def search(query: str) -> str:
    """
    Perform a workspace-wide semantic search for components (classes, methods, variables).
    This tool combines native libspec discovery for specification components with
    LSP symbol search for general code discovery.
    """
    assert query, "Search query cannot be empty."

    results = []

    # 1. Native Spec Discovery (high precision for Features/Requirements)
    try:
        results.extend(_native_spec_discovery(query))
    except Exception:
        pass

    # 2. LSP Symbol Search (broader coverage for implementations)
    try:
        _ensure_lsp_started()
        res = lsp.send_request("workspace/symbol", {"query": query})
        lsp_results = res.get("result", [])
        if lsp_results:
            seen_locs = {
                (
                    r.get("location", {}).get("uri"),
                    r.get("location", {}).get("range", {}).get("start", {}).get("line"),
                )
                for r in results
                if "location" in r
            }

            for sym in lsp_results:
                loc = sym.get("location", {})
                uri = loc.get("uri")
                start_line = loc.get("range", {}).get("start", {}).get("line")
                if (uri, start_line) not in seen_locs:
                    results.append(sym)
    except Exception:
        pass

    return json.dumps(results, indent=2)


def _native_spec_discovery(query: str):
    """Scan the workspace for classes matching the query using AST."""
    results = []
    patterns = ["spec/**/*.py", "*_spec.py", "spec.py"]
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
                if isinstance(node, ast.ClassDef):
                    docstring = ast.get_docstring(node) or ""
                    if (
                        query_lower in node.name.lower()
                        or query_lower in docstring.lower()
                    ):
                        results.append(
                            {
                                "name": node.name,
                                "kind": 5,  # Class
                                "location": {
                                    "uri": Path(os.path.abspath(path)).as_uri(),
                                    "range": {
                                        "start": {
                                            "line": node.lineno - 1,
                                            "character": 0,
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
        _ensure_lsp_started()
        uri = _to_uri(file_path)
        pos = {"line": line, "character": character}

        hover = lsp.send_request(
            "textDocument/hover", {"textDocument": {"uri": uri}, "position": pos}
        )
        definition = lsp.send_request(
            "textDocument/definition", {"textDocument": {"uri": uri}, "position": pos}
        )

        result = {"hover": hover.get("result"), "definition": definition.get("result")}
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Navigation Failure: Failed to peek at {file_path}:{line}:{character}.\n{e}"


@mcp.tool()
def usage(file_path: str, line: int, character: int) -> str:
    """
    Find all semantic references to a component.
    """
    assert os.path.exists(file_path), f"File not found: {file_path}"

    try:
        _ensure_lsp_started()
        uri = _to_uri(file_path)
        res = lsp.send_request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
                "context": {"includeDeclaration": True},
            },
        )
        return json.dumps(res.get("result", []), indent=2)
    except Exception as e:
        return f"Impact Analysis Failure: Could not find references for component at {file_path}:{line}.\n{e}"


@mcp.tool()
def symbols(file_path: str) -> str:
    """
    List all structural components (classes/methods) in a file.
    """
    assert os.path.exists(file_path), f"File not found: {file_path}"

    try:
        _ensure_lsp_started()
        uri = _to_uri(file_path)
        res = lsp.send_request(
            "textDocument/documentSymbol", {"textDocument": {"uri": uri}}
        )
        return json.dumps(res.get("result", []), indent=2)
    except Exception as e:
        return f"Structural Analysis Failure: Failed to list components in {file_path}.\n{e}"


@mcp.tool()
def pylsp_plugin(plugin_name: str, action: str = "status") -> str:
    """
    Control any pylsp plugin (e.g., "hello", "pyflakes").

    Args:
        plugin_name: The name of the plugin to control.
        action: "status", "enable", or "disable". Defaults to "status".
    """
    # spec.hello_plugin.PluginMcpControl
    # spec.mcp.McpPylspPluginTool
    try:
        _ensure_lsp_started()

        if action == "status":
            return f"Plugin '{plugin_name}' is currently managed via LSP workspace configuration."

        enabled = action == "enable"

        # Update workspace configuration dynamically
        lsp.send_notification(
            "workspace/didChangeConfiguration",
            {"settings": {"plugins": {plugin_name: {"enabled": enabled}}}},
        )

        return (
            f"Plugin '{plugin_name}' has been {'enabled' if enabled else 'disabled'}."
        )
    except Exception as e:
        return f"Error controlling plugin '{plugin_name}': {e}"


@mcp.tool()
def set_pylsp_plugin_setting(plugin_name: str, setting_name: str, value: str) -> str:
    """
    Set an arbitrary configuration value for a pylsp plugin dynamically.

    Args:
        plugin_name: The name of the plugin (e.g., "hello_ast").
        setting_name: The specific setting key to update (e.g., "pattern").
        value: The value to apply (will be parsed as JSON if possible, otherwise treated as a string).
    """
    try:
        _ensure_lsp_started()

        try:
            parsed_value = json.loads(value)
        except Exception:
            parsed_value = value

        lsp.send_notification(
            "workspace/didChangeConfiguration",
            {"settings": {"plugins": {plugin_name: {setting_name: parsed_value}}}},
        )

        return f"Successfully updated '{plugin_name}.{setting_name}' to {repr(parsed_value)}."
    except Exception as e:
        return f"Error updating setting for plugin '{plugin_name}': {e}"


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
    for comp in comps:
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


try:
    import libspec_scheduler.mcp
except ImportError:
    pass


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
