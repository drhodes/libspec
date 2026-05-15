"""
MCP Server entry point for libspec.
"""

import os
import sys
import subprocess
import json
import threading
import ast
import glob
import inspect
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
    """
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
                details=f"Original Error: {e}\nEnsure 'python-lsp-server' is installed (e.g., `uv add --dev python-lsp-server`)."
            )

def _to_uri(file_path: str) -> str:
    return Path(os.path.abspath(file_path)).as_uri()

@mcp.tool()
def build(spec_file: str = None, output_dir: str = "spec-build") -> str:
    """
    Build the XML spec from a Python spec file.
    
    Args:
        spec_file: Path to the main python spec file. If omitted, attempts to auto-discover in the current directory.
        output_dir: Output directory (default is 'spec-build')
    """
    if not spec_file:
        candidates = glob.glob(os.path.join(os.getcwd(), "*_spec.py")) + glob.glob(os.path.join(os.getcwd(), "spec.py")) + glob.glob(os.path.join(os.getcwd(), "spec", "*_spec.py"))
        if not candidates:
            return "Error: Could not auto-discover a spec_file. Please provide one."
        spec_file = candidates[0]
        
    cmd = [sys.executable, "-m", "libspec.cli", "build", spec_file, "-o", output_dir]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"Successfully built {spec_file} to {output_dir}.\n{res.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Error building spec:\n{e.stderr}\n{e.stdout}"


@mcp.tool()
def diff(build_dir: str = "spec-build") -> str:
    """
    Diff the two latest XML specs in a build directory.
    
    Args:
        build_dir: Directory containing XML spec files (default is 'spec-build')
    """
    cmd = [sys.executable, "-m", "libspec.cli", "diff", build_dir]
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
        _ensure_lsp_started(root_dir) # Ensure idempotency and state safety
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
            seen_locs = { (r.get("location", {}).get("uri"), 
                           r.get("location", {}).get("range", {}).get("start", {}).get("line")) 
                          for r in results if "location" in r }
            
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
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    docstring = ast.get_docstring(node) or ""
                    if query_lower in node.name.lower() or query_lower in docstring.lower():
                        results.append({
                            "name": node.name,
                            "kind": 5, # Class
                            "location": {
                                "uri": Path(os.path.abspath(path)).as_uri(),
                                "range": {
                                    "start": {"line": node.lineno - 1, "character": 0},
                                    "end": {"line": (getattr(node, "end_lineno", node.lineno)) - 1, "character": 0}
                                }
                            },
                            "containerName": os.path.basename(path),
                            "description": docstring.strip()
                        })
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

        hover = lsp.send_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": pos
        })
        definition = lsp.send_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": pos
        })
        
        result = {
            "hover": hover.get("result"),
            "definition": definition.get("result")
        }
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
        res = lsp.send_request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": True}
        })
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
        res = lsp.send_request("textDocument/documentSymbol", {
            "textDocument": {"uri": uri}
        })
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
    try:
        _ensure_lsp_started()
        
        if action == "status":
            return f"Plugin '{plugin_name}' is currently managed via LSP workspace configuration."
        
        enabled = (action == "enable")
        
        # Update workspace configuration dynamically
        lsp.send_notification("workspace/didChangeConfiguration", {
            "settings": {
                "plugins": {
                    plugin_name: {
                        "enabled": enabled
                    }
                }
            }
        })
        
        return f"Plugin '{plugin_name}' has been {'enabled' if enabled else 'disabled'}."
    except Exception as e:
        return f"Error controlling plugin '{plugin_name}': {e}"


@mcp.tool()
def mcp_agent(agent: str = None, project_root: str = ".", list_agents: bool = False) -> str:
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


def main():
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
