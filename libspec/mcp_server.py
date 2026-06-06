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
def diff(snapshot_a: str = None, snapshot_b: str = None) -> str:
    """
    Diff specification snapshots natively.

    If no arguments are provided, it compiles the live specification files on-the-fly (the pending spec)
    and diffs them against the latest recorded snapshot #0 in the SpecStore without writing to the database.
    If only one argument is provided, it diffs it against #0.
    """
    cmd = [sys.executable, "-m", "libspec.cli", "diff"]
    if snapshot_a:
        cmd.append(snapshot_a)
    if snapshot_b:
        cmd.append(snapshot_b)
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
    # spec.mcp.McpPylspPluginTool
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
            
        lsp.send_notification("workspace/didChangeConfiguration", {
            "settings": {
                "plugins": {
                    plugin_name: {
                        setting_name: parsed_value
                    }
                }
            }
        })
        
        return f"Successfully updated '{plugin_name}.{setting_name}' to {repr(parsed_value)}."
    except Exception as e:
        return f"Error updating setting for plugin '{plugin_name}': {e}"


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


@mcp.tool()
def agent_config(agent: str = None, project_root: str = ".", list_agents: bool = False) -> str:
    """
    Configure or list coding agents for libspec MCP integration.
    
    Args:
        agent: The name of the agent to configure (required if not listing).
        project_root: The root directory of the project (default ".").
        list_agents: If True, list all supported agents and return immediately.
    """
    return mcp_agent(agent, project_root, list_agents)


@mcp.tool()
def list_snapshots() -> str:
    """
    List all recorded specification snapshots chronologically.
    """
    from libspec.store import get_store
    store = get_store()
    snapshots = store.list_snapshots()
    if not snapshots:
        return "No snapshots recorded yet."
        
    n = len(snapshots)
    w = len(str(n - 1))
    
    snapshot_comps = []
    new_counts = []
    size_bytes_list = []
    for i, s in enumerate(snapshots):
        try:
            comps = store.get_components_for_snapshot(s)
        except Exception:
            comps = []
        snapshot_comps.append(comps)
        
        sb = sum(
            len(c.ref.encode("utf-8")) +
            len(c.docstring.encode("utf-8")) +
            sum(len(x.encode("utf-8")) for x in c.inherits) +
            64
            for c in comps
        )
        size_bytes_list.append(sb)
        
        if i == 0:
            nc = len(comps)
        else:
            prev_refs = {c.ref for c in snapshot_comps[i-1]}
            current_refs = {c.ref for c in comps}
            nc = len(current_refs - prev_refs)
        new_counts.append(nc)
        
    max_new_w = max((len(str(x)) for x in new_counts), default=1)
    max_bytes_w = max((len(str(x)) for x in size_bytes_list), default=1)
    has_any_git = any(s.git_commit for s in snapshots) or os.path.exists(".git")
    
    lines = []
    lines.append("Chronological Snapshot History:")
    lines.append("-" * 80)
    for i, s in enumerate(snapshots):
        idx = n - 1 - i
        timestamp_str = s.created_at.strftime('%Y-%m-%d %H:%M:%S')
        
        git_info = ""
        if has_any_git:
            if s.git_commit and s.git_commit != "PENDING":
                git_str = f"(Git: {s.git_commit[:7]})"
            else:
                git_str = "(Git: PENDING)"
            git_info = f" | {git_str:<14}"
            
        lines.append(
            f"  #{idx:>{w}} • {timestamp_str}"
            f" | ID: {s.id}"
            f" | {new_counts[i]:>{max_new_w}} new"
            f" | {size_bytes_list[i]:>{max_bytes_w}} bytes"
            f"{git_info}"
        )
    lines.append("-" * 80)
    return "\n".join(lines)


@mcp.tool()
def list_components(snapshot_id: str = None) -> str:
    """
    List all components present in the given snapshot (defaulting to the latest snapshot if snapshot_id is omitted).
    
    Args:
        snapshot_id: The explicit snapshot hash/ID prefix (relative index is NOT supported).
    """
    from libspec.store import get_store
    store = get_store()
    if snapshot_id:
        try:
            snap = store.get_snapshot(snapshot_id)
        except Exception:
            return f"Error: Snapshot '{snapshot_id}' not found."
    else:
        snap = store.current_snapshot()
        
    if not snap:
        return "No snapshots found in active SpecStore."
        
    try:
        comps = store.get_components_for_snapshot(snap)
    except Exception as e:
        return f"Error loading components: {e}"
        
    if not comps:
        return "No components found."
        
    lines = [f"Snapshot ({snap.id}) Components ({len(comps)} total):"]
    for comp in comps:
        comp_type = "Template" if comp.is_template else "Component"
        lines.append(f"  • {comp.ref} [{comp_type}]")
    return "\n".join(lines)


@mcp.tool()
def show_component(component_ref: str, snapshot_id: str = None) -> str:
    """
    Show details of a specific component.
    
    Args:
        component_ref: The FQN of the component.
        snapshot_id: The explicit snapshot hash/ID prefix (relative index is NOT supported).
    """
    from libspec.store import get_store
    store = get_store()
    if snapshot_id:
        try:
            snap = store.get_snapshot(snapshot_id)
        except Exception:
            return f"Error: Snapshot '{snapshot_id}' not found."
    else:
        snap = store.current_snapshot()
        
    if not snap:
        return "No snapshots found in active SpecStore."
        
    try:
        comps = store.get_components_for_snapshot(snap)
    except Exception as e:
        return f"Error loading components: {e}"
        
    comp = next((c for c in comps if c.ref == component_ref), None)
    if not comp:
        return f"Error: Component '{component_ref}' not found in snapshot '{snap.id}'."
        
    lines = []
    lines.append("=" * 60)
    lines.append(f"Reference:   {comp.ref}")
    lines.append(f"Type:        {'Template Requirement' if comp.is_template else 'Requirement'}")
    lines.append(f"Hash:        {comp.hash}")
    if comp.inherits:
        lines.append("Inherits:    " + ", ".join(comp.inherits))
    lines.append(f"Docstring:\n{'-' * 60}\n{comp.docstring}\n{'-' * 60}")
    
    claims = [c for c in store.list_implemented(snap) if c.ref == component_ref]
    if claims:
        lines.append("Implementation Claims:")
        for c in claims:
            lines.append(f"  • {c.file}:{c.line} (Hash: {c.spec_hash[:8]})")
    lines.append("=" * 60)
    return "\n".join(lines)


@mcp.tool()
def get_log() -> str:
    """
    Retrieve the chronological append-only event log.
    """
    from libspec.store import get_store
    import datetime
    store = get_store()
    try:
        raw_events = store.get_raw_events()
    except Exception as e:
        return f"Failed to read events from store: {e}"
        
    if not raw_events:
        return "No events recorded in append-only SpecStore log."
        
    lines = []
    lines.append(f"Chronological SpecStore Event Log ({len(raw_events)} events):")
    lines.append("-" * 80)
    
    def get_safe_slice(e: dict, key: str, length: int) -> str:
        val = e.get(key)
        if val is None:
            return ""
        return str(val)[:length]
        
    w = len(str(len(raw_events) - 1))
    for index, event in enumerate(raw_events):
        rec_type = event.get("type", "unknown").upper()
        if rec_type in ("TOMBSTONE", "DELETE_SNAPSHOT"):
            rec_type = "TOMBSTONE"
        elif rec_type in ("RESTORE", "RESTORE_SNAPSHOT"):
            rec_type = "RESTORE"
            
        action_str = f"[{rec_type}]"
        
        created_at_str = event.get("created_at")
        if not created_at_str:
            target_id = event.get("snapshot_id")
            if target_id:
                for e in raw_events:
                    if e.get("type") == "snapshot" and e.get("id") == target_id:
                        created_at_str = e.get("created_at")
                        break
                        
        if created_at_str:
            try:
                dt = datetime.datetime.fromisoformat(created_at_str)
                timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                timestamp_str = str(created_at_str)[:19].replace("T", " ")
        else:
            timestamp_str = " " * 19
            
        details = ""
        if rec_type == "SNAPSHOT":
            git_str = f" (Git: {event.get('git_commit')})" if event.get('git_commit') else ""
            master_short = get_safe_slice(event, "master_hash", 16)
            details = f"ID: {event.get('id')} | Master: {master_short}...{git_str}"
        elif rec_type == "COMPONENT":
            snap_short = get_safe_slice(event, "snapshot_id", 8)
            hash_short = get_safe_slice(event, "hash", 8)
            details = f"Ref: {event.get('ref')} | Snap: {snap_short} | Hash: {hash_short}"
        elif rec_type == "IMPLEMENTED":
            details = f"Ref: {event.get('ref')} | Location: {event.get('file')}:{event.get('line')}"
        elif rec_type == "VCS_LINK":
            snap_short = get_safe_slice(event, "snapshot_id", 8)
            details = f"Target: {snap_short} -> {event.get('vcs')}:{event.get('revision')}"
        elif rec_type in ("TOMBSTONE", "RESTORE"):
            snap_short = get_safe_slice(event, "snapshot_id", 8)
            details = f"Target Snapshot: {snap_short}"
            
        lines.append(f"  #{index:<{w}} | {timestamp_str} | {action_str:<13} | {details}")
    lines.append("-" * 80)
    return "\n".join(lines)


@mcp.tool()
def link_snapshot(snapshot_id: str, vcs: str, revision: str, metadata: dict = None) -> str:
    """
    Link a spec snapshot to a VCS revision.
    
    Args:
        snapshot_id: The explicit snapshot hash/ID prefix (relative index is NOT supported).
        vcs: The VCS type (e.g. "git").
        revision: The VCS revision/commit hash.
        metadata: Optional key-value metadata pairs.
    """
    from libspec.store import get_store
    store = get_store()
    try:
        snap = store.get_snapshot(snapshot_id)
    except Exception:
        return f"Error: Snapshot '{snapshot_id}' not found."
        
    try:
        store.store_vcs_link(snap.id, vcs=vcs, revision=revision, metadata=metadata)
        return f"Successfully linked snapshot {snap.id} to {vcs} revision {revision}."
    except Exception as e:
        return f"Error: Failed to link snapshot '{snap.id}': {e}"


@mcp.tool()
def compact_store(dry_run: bool = False) -> str:
    """
    Compact the SpecStore database log.
    
    Args:
        dry_run: Whether to dry-run the compaction (default False).
    """
    from libspec.store import get_store
    store = get_store()
    if not hasattr(store, "compact"):
        return "Error: Active store backend does not support compaction."
        
    try:
        res = store.compact(dry_run=dry_run)
        orig_kb = res["original_size"] / 1024.0
        comp_kb = res["compacted_size"] / 1024.0
        reclaimed_kb = res["reclaimed_bytes"] / 1024.0
        
        lines = []
        lines.append("============================================================")
        lines.append("                 LIBSPEC COMPACTION REPORT                  ")
        lines.append("============================================================")
        if dry_run:
            lines.append("MODE             : DRY RUN (No changes written)")
        else:
            lines.append("MODE             : EXECUTION (Database compacted)")
            
        lines.append(f"Snapshots Pruned : {res['pruned_snapshots_count']}")
        lines.append(f"Original Size    : {orig_kb:.2f} KB")
        lines.append(f"Compacted Size   : {comp_kb:.2f} KB")
        
        if res["reclaimed_bytes"] > 0 and orig_kb > 0:
            lines.append(f"Space Reclaimed  : {reclaimed_kb:.2f} KB ({reclaimed_kb/orig_kb*100.0:.1f}%)")
        else:
            lines.append("Space Reclaimed  : 0.00 KB (Database already fully optimized)")
            
        if res["upgraded_legacy_format"]:
            if dry_run:
                lines.append("Format Upgrade   : PENDING (Legacy format detected)")
            else:
                lines.append("Format Upgrade   : COMPLETED (Legacy format migrated)")
                
        lines.append("============================================================")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: Compaction failed: {e}"


@mcp.tool()
def delete_snapshot(snapshot_id: str) -> str:
    """
    Permanently delete a historical snapshot.
    
    Args:
        snapshot_id: The explicit snapshot hash/ID prefix.
    """
    from libspec.store import get_store
    store = get_store()
    try:
        snap = store.get_snapshot(snapshot_id)
    except Exception:
        return f"Error: Snapshot '{snapshot_id}' not found."
        
    latest = store.current_snapshot()
    if latest and latest.id == snap.id:
        return f"Error: Cannot delete snapshot '{snap.id}' because it is the latest snapshot."
        
    try:
        store.delete_snapshot(snap)
        return f"Snapshot '{snap.id}' successfully deleted."
    except Exception as e:
        return f"Error: Failed to delete snapshot: {e}"


@mcp.tool()
def restore_snapshot(snapshot_id: str) -> str:
    """
    Restore a previously deleted/tombstoned snapshot back to active list.
    
    Args:
        snapshot_id: The explicit snapshot hash/ID prefix.
    """
    from libspec.store import get_store
    store = get_store()
    try:
        snap = store.get_snapshot(snapshot_id)
    except Exception:
        return f"Error: Snapshot '{snapshot_id}' not found."
        
    active_snapshots = store.list_snapshots()
    if any(s.id == snap.id for s in active_snapshots):
        return f"Snapshot '{snap.id}' is already active."
        
    try:
        store.restore_snapshot(snap)
        return f"Snapshot '{snap.id}' successfully restored."
    except Exception as e:
        return f"Error: Failed to restore snapshot: {e}"


def main():
    try:
        from libspec.agent_config import check_and_heal_skills
        messages = check_and_heal_skills(os.getcwd(), auto_heal=True)
        for msg in messages:
            print(f"[libspec] {msg}", file=sys.stderr)
    except Exception as e:
        print(f"[libspec] Warning: Error checking agent skills: {e}", file=sys.stderr)

    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
