"""
libspec - unified CLI for spec-driven development.
"""

import datetime
import inspect
import os
import sys
import click
from libspec.util import NotALibspecProjectError, require_libspec_project


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

INIT_MAIN_SPEC = """'''
main spec
'''

from libspec import Spec
from . import app

class MainSpec(Spec):
    def modules(self):
        return [app]
"""

INIT_APP = """'''
Features and requirements
'''

from .err import Feat, Req

class App(Req):
    '''This program should emit the
    string "Hello, world!" to the terminal.
    '''

class CmdLine(Feat):
    '''
    This program does not take any command line arguments.
    '''
"""




def cmd_init(args):
    spec_dir = os.path.abspath("spec")
    if os.path.exists(spec_dir):
        print(f"Error: Directory '{spec_dir}' already exists. Bailing.")
        sys.exit(1)
        
    os.makedirs(spec_dir)
    
    with open(os.path.join(spec_dir, "__init__.py"), "w") as f:
        pass
        
    with open(os.path.join(spec_dir, "main_spec.py"), "w") as f:
        f.write(INIT_MAIN_SPEC)

    with open(os.path.join(spec_dir, "app.py"), "w") as f:
        f.write(INIT_APP)

    # Read templates/err.py packaged inside libspec package
    template_err_path = os.path.join(os.path.dirname(__file__), "templates", "err.py")
    if not os.path.exists(template_err_path):
        print(f"Error: Internal template file '{template_err_path}' not found. Reinstall libspec.")
        sys.exit(1)

    with open(template_err_path, "r", encoding="utf-8") as f:
        err_content = f.read()

    with open(os.path.join(spec_dir, "err.py"), "w") as f:
        f.write(err_content)

    # Create the .libspec/ directory — this is the canonical project marker.
    # All store-dependent commands gate on its presence (spec.cli.CwdValidation).
    libspec_dir = os.path.abspath(".libspec")
    os.makedirs(libspec_dir, exist_ok=True)
        
    print(f"Initialized empty spec directory in {spec_dir}")

    # Git Hook Integration
    git_dir = os.path.abspath(".git")
    if os.path.exists(git_dir) and os.path.isdir(git_dir):
        hooks_dir = os.path.join(git_dir, "hooks")
        os.makedirs(hooks_dir, exist_ok=True)
        post_commit_path = os.path.join(hooks_dir, "post-commit")
        
        post_commit_content = """#!/bin/sh
# libspec automated VCS linking hook
# Attempts to link the latest unlinked build snapshot to the new commit hash

COMMIT_HASH=$(git rev-parse HEAD 2>/dev/null)
if [ -z "$COMMIT_HASH" ]; then
    exit 0
fi

LIBSPEC_CMD="libspec"
if [ -x "./.venv/bin/libspec" ]; then
    LIBSPEC_CMD="./.venv/bin/libspec"
elif [ -x "../.venv/bin/libspec" ]; then
    LIBSPEC_CMD="../.venv/bin/libspec"
fi

$LIBSPEC_CMD link --vcs git --revision "$COMMIT_HASH" --metadata "hook=post-commit" >/dev/null 2>&1 || true
"""
        try:
            with open(post_commit_path, "w", encoding="utf-8") as hf:
                hf.write(post_commit_content)
            # Make the hook script executable (chmod +x)
            import stat
            st = os.stat(post_commit_path)
            os.chmod(post_commit_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            print("Installed automated Git post-commit hook.")
        except Exception as e:
            print(f"Warning: Failed to install Git post-commit hook: {e}")



# ---------------------------------------------------------------------------
def _store_label(store) -> str:
    '''Return a short human-readable label for the active store backend.'''
    name = store.__class__.__name__
    if hasattr(store, "filepath"):
        return f"{name} ({store.filepath})"
    if hasattr(store, "db_path"):
        return f"{name} ({store.db_path})"
    if hasattr(store, "xml_path"):
        return f"{name} ({store.xml_path})"
    return name


# ---------------------------------------------------------------------------
def cmd_snapshot(args):
    from libspec.spec import Spec, module_specs
    from libspec.store import get_store

    store = get_store()
    print(f"Store: {_store_label(store)}")

    spec_file = os.path.abspath(args["<spec_file>"])
    if not os.path.exists(spec_file):
        print(f"Error: {spec_file} does not exist.")
        sys.exit(1)

    # Calculate module name relative to the current working directory, if possible.
    # This allows relative imports (e.g. from . import app) to work correctly when
    # the spec is in a subdirectory (like spec/main_spec.py).
    cwd = os.getcwd()
    if spec_file.startswith(cwd):
        rel_path = os.path.relpath(spec_file, cwd)
        module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, '.')
        root_dir = cwd
    else:
        # Fallback: just use the spec's directory
        root_dir = os.path.dirname(spec_file)
        module_name = os.path.splitext(os.path.basename(spec_file))[0]
        
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    # Import the module dynamically. Since we mapped the file path to a 
    # dotted module name (e.g. 'spec.main_spec'), python's built-in import 
    # system correctly sets __package__ and handles relative imports.
    import importlib
    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        print(f"Error loading spec file: {e}")
        sys.exit(1)

    # First try: find an explicit Spec subclass (write_xml built-in)
    explicit_spec = None
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ == module_name and issubclass(obj, Spec) and obj is not Spec:
            explicit_spec = obj
            break

    output_dir = args["--output"]

    if explicit_spec:
        explicit_spec().write_xml(output_dir)
        return

    # Fallback: auto-discover all Ctx subclasses via module_specs()
    specs = module_specs(module)
    if not specs:
        print(f"Error: No spec classes found in {spec_file}.")
        sys.exit(1)

    # Build an ad-hoc Spec that wraps the discovered components
    class _ModuleSpec(Spec):
        def modules(self_inner):
            return [module]

    _ModuleSpec().write_xml(output_dir)


def cmd_diff(old_snap=None, new_snap=None):
    from libspec.spec_diff import generate_native_patch
    generate_native_patch(old_snap=old_snap, new_snap=new_snap)


def cmd_mcp(args):
    from libspec.mcp_server import main as mcp_main
    mcp_main()


def cmd_mcp_agent(args):
    from libspec.agent_config import get_agent_config, list_supported_agents
    
    if args["--list"]:
        print(list_supported_agents())
        return

    agent = args["<agent>"]
    project_root = args["<project_root>"] or "."
    try:
        configurator = get_agent_config(agent, project_root)
        res = configurator.configure()
        print(res)
    except Exception as e:
        print(f"Error: {e}")


def cmd_repl(args):
    from libspec.repl import LibspecRepl
    LibspecRepl().start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def check_and_heal_git_hook():
    """Verify Git post-commit hook exists and auto-heal it if missing/outdated."""
    import os
    import sys
    import stat
    
    git_dir = os.path.abspath(".git")
    if os.path.exists(git_dir) and os.path.isdir(git_dir):
        hooks_dir = os.path.join(git_dir, "hooks")
        post_commit_path = os.path.join(hooks_dir, "post-commit")
        
        post_commit_content = """#!/bin/sh
# libspec automated VCS linking hook
# Attempts to link the latest unlinked build snapshot to the new commit hash

COMMIT_HASH=$(git rev-parse HEAD 2>/dev/null)
if [ -z "$COMMIT_HASH" ]; then
    exit 0
fi

LIBSPEC_CMD="libspec"
if [ -x "./.venv/bin/libspec" ]; then
    LIBSPEC_CMD="./.venv/bin/libspec"
elif [ -x "../.venv/bin/libspec" ]; then
    LIBSPEC_CMD="../.venv/bin/libspec"
fi

$LIBSPEC_CMD link --vcs git --revision "$COMMIT_HASH" --metadata "hook=post-commit" >/dev/null 2>&1 || true
"""
        # If the hook doesn't exist or doesn't match our content, re-install it
        needs_healing = False
        if not os.path.exists(post_commit_path):
            needs_healing = True
        else:
            try:
                with open(post_commit_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "libspec automated VCS linking hook" not in content:
                    needs_healing = True
            except Exception:
                needs_healing = True
                
        if needs_healing:
            try:
                os.makedirs(hooks_dir, exist_ok=True)
                with open(post_commit_path, "w", encoding="utf-8") as hf:
                    hf.write(post_commit_content)
                st = os.stat(post_commit_path)
                os.chmod(post_commit_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                print("[libspec] Installed/Healed automated Git post-commit hook.", file=sys.stderr)
            except Exception as e:
                print(f"[libspec] Warning: Failed to auto-heal Git post-commit hook: {e}", file=sys.stderr)


@click.group(invoke_without_command=True)
@click.version_option(package_name="libspec", prog_name="libspec")
@click.pass_context
def main(ctx):
    """libspec - unified CLI for spec-driven development."""
    from libspec.util import is_libspec_project

    # To prevent side effects and unwanted mutations outside of a project,
    # only run self-healing routines if in a valid libspec project.
    # spec.cli.CliSelfHealingBypass
    if is_libspec_project():
        # Check and heal git hook on startup
        check_and_heal_git_hook()

        # Check and heal skills on startup
        try:
            from libspec.agent_config import check_and_heal_skills
            import sys
            import os
            messages = check_and_heal_skills(os.getcwd(), auto_heal=True)
            for msg in messages:
                print(f"[libspec] {msg}", file=sys.stderr)
        except Exception as e:
            import sys
            print(f"[libspec] Warning: Error checking agent skills: {e}", file=sys.stderr)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
def init():
    """Initialize a new spec directory."""
    cmd_init(None)


@main.command()
@click.argument("snapshot_a", required=False)
@click.argument("snapshot_b", required=False)
def diff(snapshot_a, snapshot_b):
    """Diff specification snapshots natively.

    If no arguments are provided, it compiles the live specification files on-the-fly (the pending spec)
    and diffs them against the latest recorded snapshot #0 in the SpecStore without writing to the database.
    If only one argument is provided, it diffs it against #0.
    """
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))

    from libspec.store import get_store
    store = get_store()

    snap_a = None
    snap_b = None

    if snapshot_a:
        try:
            snap_a = store.get_snapshot(snapshot_a)
            if not snap_a:
                raise click.UsageError(f"Snapshot '{snapshot_a}' not found.")
        except Exception as e:
            raise click.UsageError(f"Error resolving snapshot '{snapshot_a}': {e}")

    if snapshot_b:
        try:
            snap_b = store.get_snapshot(snapshot_b)
            if not snap_b:
                raise click.UsageError(f"Snapshot '{snapshot_b}' not found.")
        except Exception as e:
            raise click.UsageError(f"Error resolving snapshot '{snapshot_b}': {e}")

    cmd_diff(old_snap=snap_a, new_snap=snap_b)


@main.command()
def mcp():
    """Run the MCP server over stdio."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    cmd_mcp(None)


@main.command(name="mcp_agent")
@click.argument("agent", required=False, default=None)
@click.argument("project_root", required=False, default=None)
@click.option("--list", "list_agents", is_flag=True, help="List all supported agents")
def mcp_agent(agent, project_root, list_agents):
    """Configure coding agent for local project."""
    if not list_agents and not agent:
        raise click.UsageError("Missing argument 'AGENT' or '--list' option.")
    args = {
        "<agent>": agent,
        "<project_root>": project_root,
        "--list": list_agents
    }
    cmd_mcp_agent(args)


@main.command(name="agent-config")
@click.argument("agent", required=False, default=None)
@click.argument("project_root", required=False, default=None)
@click.option("--list", "list_agents", is_flag=True, help="List all supported agents")
def agent_config(agent, project_root, list_agents):
    """Configure coding agent for local project."""
    if not list_agents and not agent:
        raise click.UsageError("Missing argument 'AGENT' or '--list' option.")
    args = {
        "<agent>": agent,
        "<project_root>": project_root,
        "--list": list_agents
    }
    cmd_mcp_agent(args)



@main.command()
def repl():
    """Start the interactive specification inspector REPL."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    cmd_repl(None)


@main.command()
@click.option("--snapshot", "snapshot_id", default=None, help="The 16-character hexadecimal target snapshot identifier. Defaults to current active snapshot.")
@click.option("--vcs", "vcs_type", default="git", help="The VCS system type. Defaults to 'git'.")
@click.option("--revision", "revision", required=True, help="The unique revision identifier (commit SHA, changeset node, or revision number).")
@click.option("--metadata", "metadata_pairs", multiple=True, help="Contextual metadata as key=value pairs.")
def link(snapshot_id, vcs_type, revision, metadata_pairs):
    """Link a spec snapshot to a VCS revision."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store, SpecStoreNotFoundError
    import sys

    store = get_store()
    
    # If snapshot_id is not provided, resolve to all unlinked/pending snapshots in the store.
    # If there are no unlinked snapshots, compile the current live spec on-the-fly and store it.
    target_ids = []
    if not snapshot_id:
        try:
            snapshots = store.list_snapshots()
            unlinked = [s.id for s in snapshots if not s.git_commit or s.git_commit == "PENDING"]
            if unlinked:
                target_ids = unlinked
        except Exception:
            pass
            
        if not target_ids:
            try:
                from libspec.util import compile_live_spec
                comps, _ = compile_live_spec()
                snap = store.store_snapshot(comps, git_commit=revision)
                target_ids = [snap.id]
            except Exception as e:
                print(f"Error compiling live specification: {e}")
                sys.exit(1)
    else:
        target_ids = [snapshot_id]

    metadata = {}
    for pair in metadata_pairs:
        if "=" in pair:
            k, v = pair.split("=", 1)
            metadata[k.strip()] = v.strip()
        else:
            metadata[pair.strip()] = ""

    success_count = 0
    for t_id in target_ids:
        try:
            store.store_vcs_link(t_id, vcs=vcs_type, revision=revision, metadata=metadata)
            success_count += 1
        except SpecStoreNotFoundError:
            print(f"Error: Snapshot '{t_id}' not found in the store.")
            sys.exit(1)
        except Exception as e:
            print(f"Error: Failed to link snapshot '{t_id}': {e}")
            sys.exit(1)

    if success_count > 1:
        print(f"Successfully linked {success_count} snapshots to {vcs_type} revision {revision}.")
    elif success_count == 1:
        print(f"Successfully linked snapshot {target_ids[0]} to {vcs_type} revision {revision}.")


@main.command()
@click.option("--dry-run", is_flag=True, help="Compute space savings without modifying the file on disk.")
def compact(dry_run):
    """Compact spec database, squashing intermediate snapshots."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    import sys
    
    store = get_store()
    if not hasattr(store, "compact"):
        click.echo("Error: Active store backend does not support compaction.")
        sys.exit(1)
        
    try:
        res = store.compact(dry_run=dry_run)
        
        orig_kb = res["original_size"] / 1024.0
        comp_kb = res["compacted_size"] / 1024.0
        reclaimed_kb = res["reclaimed_bytes"] / 1024.0
        
        click.echo("============================================================")
        click.echo("                 LIBSPEC COMPACTION REPORT                  ")
        click.echo("============================================================")
        if dry_run:
            click.echo("MODE             : DRY RUN (No changes written)")
        else:
            click.echo("MODE             : EXECUTION (Database compacted)")
            
        click.echo(f"Snapshots Pruned : {res['pruned_snapshots_count']}")
        click.echo(f"Original Size    : {orig_kb:.2f} KB")
        click.echo(f"Compacted Size   : {comp_kb:.2f} KB")
        
        if res["reclaimed_bytes"] > 0 and orig_kb > 0:
            click.echo(f"Space Reclaimed  : {reclaimed_kb:.2f} KB ({reclaimed_kb/orig_kb*100.0:.1f}%)")
        else:
            click.echo("Space Reclaimed  : 0.00 KB (Database already fully optimized)")
            
        if res["upgraded_legacy_format"]:
            if dry_run:
                click.echo("Format Upgrade   : Legacy snapshots detected (will be migrated to CAS)")
            else:
                click.echo("Format Upgrade   : Compacted log migrated to Content-Addressable Storage (CAS)")
                click.echo("Backup File      : .libspec/libspec.jsonl.bak")
                
        click.echo("============================================================")
    except Exception as e:
        click.echo(f"Error: Compaction failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("-s", "--snapshot", "snapshot_id", default=None, help="Snapshot ID or prefix. Defaults to latest.")
def list(snapshot_id):
    """List all specification components in a snapshot."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    store = get_store()
    if snapshot_id:
        try:
            snap = store.get_snapshot(snapshot_id)
        except Exception:
            click.echo(f"Error: Snapshot '{snapshot_id}' not found.", err=True)
            sys.exit(1)
    else:
        snap = store.current_snapshot()
        
    if not snap:
        click.echo("No snapshots found in active SpecStore.")
        return
        
    try:
        comps = store.get_components_for_snapshot(snap)
    except Exception as e:
        click.echo(f"Error loading components: {e}", err=True)
        sys.exit(1)
        
    if not comps:
        click.echo("No components found.")
        return
        
    click.echo(f"Snapshot ({snap.id}) Components ({len(comps)} total):")
    for comp in comps:
        comp_type = "Template" if comp.is_template else "Component"
        click.echo(f"  • {comp.ref} [{comp_type}]")


@main.command()
@click.argument("component_ref")
@click.option("-s", "--snapshot", "snapshot_id", default=None, help="Snapshot ID or prefix. Defaults to latest.")
def show(component_ref, snapshot_id):
    """Show details of a specific component."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    store = get_store()
    if snapshot_id:
        try:
            snap = store.get_snapshot(snapshot_id)
        except Exception:
            click.echo(f"Error: Snapshot '{snapshot_id}' not found.", err=True)
            sys.exit(1)
    else:
        snap = store.current_snapshot()
        
    if not snap:
        click.echo("No snapshots found in active SpecStore.", err=True)
        sys.exit(1)
        
    try:
        comps = store.get_components_for_snapshot(snap)
    except Exception as e:
        click.echo(f"Error loading components: {e}", err=True)
        sys.exit(1)
        
    comp = next((c for c in comps if c.ref == component_ref), None)
    if not comp:
        click.echo(f"Error: Component '{component_ref}' not found in snapshot '{snap.id}'.", err=True)
        sys.exit(1)
        
    click.echo("=" * 60)
    click.echo(f"Reference:   {comp.ref}")
    click.echo(f"Type:        {'Template Requirement' if comp.is_template else 'Requirement'}")
    click.echo(f"Hash:        {comp.hash}")
    if comp.inherits:
        click.echo("Inherits:    " + ", ".join(comp.inherits))
    click.echo(f"Docstring:\n{'-' * 60}\n{comp.docstring}\n{'-' * 60}")
    
    # Print implemented claims if any
    claims = [c for c in store.list_implemented(snap) if c.ref == component_ref]
    if claims:
        click.echo("Implementation Claims:")
        for c in claims:
            click.echo(f"  • {c.file}:{c.line} (Hash: {c.spec_hash[:8]})")
    click.echo("=" * 60)


@main.command()
@click.argument("query")
@click.option("-s", "--snapshot", "snapshot_id", default=None, help="Snapshot ID or prefix. Defaults to latest.")
def search(query, snapshot_id):
    """Search components and docstrings."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    store = get_store()
    if snapshot_id:
        try:
            snap = store.get_snapshot(snapshot_id)
        except Exception:
            click.echo(f"Error: Snapshot '{snapshot_id}' not found.", err=True)
            sys.exit(1)
    else:
        snap = store.current_snapshot()
        
    if not snap:
        click.echo("No snapshots found in active SpecStore.", err=True)
        sys.exit(1)
        
    try:
        comps = store.get_components_for_snapshot(snap)
    except Exception as e:
        click.echo(f"Error loading components: {e}", err=True)
        sys.exit(1)
        
    matches = [c for c in comps if query.lower() in c.ref.lower() or query.lower() in c.docstring.lower()]
    if not matches:
        click.echo(f"No components found matching '{query}'.")
        return
        
    click.echo(f"Search Results for '{query}' ({len(matches)} matches):")
    for comp in matches:
        comp_type = "Template" if comp.is_template else "Component"
        first_line = comp.docstring.split("\n")[0] if comp.docstring else ""
        snippet = first_line[:60]
        if len(first_line) > 60:
            snippet += "..."
        click.echo(f"  • {comp.ref} [{comp_type}] - {snippet}")


@main.command(name="list-snapshots")
def list_snapshots():
    """List chronological snapshot history."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    store = get_store()
    snapshots = store.list_snapshots()
    if not snapshots:
        click.echo("No snapshots recorded yet.")
        return
    
    # Calculate optimal column widths
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
    
    click.echo("Chronological Snapshot History:")
    click.echo("-" * 80)
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
            
        click.echo(
            f"  #{idx:>{w}} • {timestamp_str}"
            f" | ID: {s.id}"
            f" | {new_counts[i]:>{max_new_w}} new"
            f" | {size_bytes_list[i]:>{max_bytes_w}} bytes"
            f"{git_info}"
        )
    click.echo("-" * 80)


@main.command()
def log():
    """Show chronological SpecStore append-only event ledger."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    store = get_store()
    try:
        raw_events = store.get_raw_events()
    except Exception as e:
        click.echo(f"Failed to read events from store: {e}", err=True)
        sys.exit(1)
        
    if not raw_events:
        click.echo("No events recorded in append-only SpecStore log.")
        return
        
    click.echo(f"Chronological SpecStore Event Log ({len(raw_events)} events):")
    click.echo("-" * 80)
    
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
            
        click.echo(f"  #{index:<{w}} | {timestamp_str} | {action_str:<13} | {details}")
    click.echo("-" * 80)


@main.command("rm-snapshot")
@click.argument("snapshot_id")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt.")
def rm_snapshot(snapshot_id, yes):
    """Permanently delete a historical snapshot from active SpecStore."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    store = get_store()
    try:
        snap = store.get_snapshot(snapshot_id)
    except Exception:
        click.echo(f"Error: Snapshot '{snapshot_id}' not found.", err=True)
        sys.exit(1)
        
    latest = store.current_snapshot()
    if latest and latest.id == snap.id:
        click.echo(f"Error: Cannot delete snapshot '{snap.id}' because it is the latest snapshot.", err=True)
        sys.exit(1)
        
    git_commit_str = snap.git_commit if snap.git_commit else "PENDING"
    
    click.echo(
        f"WARNING: You are about to delete (tombstone) the following snapshot:\n"
        f"  Target Reference : {snapshot_id}\n"
        f"  Resolved Hash ID : {snap.id}\n"
        f"  Date Created     : {snap.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"  Git Commit       : {git_commit_str}\n"
        f"Note: This can be recovered later using restore-snapshot."
    )
    
    if not yes and not click.confirm("Are you sure you want to delete this snapshot?"):
        click.echo("Deletion aborted.")
        sys.exit(1)
        
    try:
        store.delete_snapshot(snap)
        click.echo(f"Snapshot '{snap.id}' successfully deleted.")
    except Exception as e:
        click.echo(f"Error: Failed to delete snapshot: {e}", err=True)
        sys.exit(1)


@main.command("restore-snapshot")
@click.argument("snapshot_id")
def restore_snapshot(snapshot_id):
    """Restore a previously deleted/tombstoned historical snapshot."""
    # spec.cli.CwdValidation
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    store = get_store()
    try:
        snap = store.get_snapshot(snapshot_id)
    except Exception:
        click.echo(f"Error: Snapshot '{snapshot_id}' not found.", err=True)
        sys.exit(1)
        
    active_snapshots = store.list_snapshots()
    if any(s.id == snap.id for s in active_snapshots):
        click.echo(f"Snapshot '{snap.id}' is already active.")
        return
        
    try:
        store.restore_snapshot(snap)
        click.echo(f"Snapshot '{snap.id}' successfully restored.")
    except Exception as e:
        click.echo(f"Error: Failed to restore snapshot: {e}", err=True)
        sys.exit(1)


@main.command(name="declare-dependency")
@click.argument("ref")
@click.argument("depends_on")
@click.option("-s", "--snapshot", "snapshot_id", default="PENDING", help="Snapshot ID or prefix. Defaults to PENDING.")
def declare_dependency(ref, depends_on, snapshot_id):
    """Declare a logical dependency between components."""
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    store = get_store()
    try:
        store.store_dependency(ref, depends_on, snapshot_id)
        click.echo(f"Successfully declared dependency: '{ref}' depends on '{depends_on}' (Snapshot: {snapshot_id}).")
    except Exception as e:
        click.echo(f"Error: Failed to declare dependency: {e}", err=True)
        sys.exit(1)


@main.command(name="dependencies")
@click.option("-s", "--snapshot", "snapshot_id", default="PENDING", help="Snapshot ID or prefix. Defaults to PENDING.")
def dependencies(snapshot_id):
    """List component dependencies recorded for the target snapshot."""
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))
    from libspec.store import get_store
    store = get_store()

    target_id = snapshot_id
    if snapshot_id != "PENDING":
        try:
            snap = store.get_snapshot(snapshot_id)
            target_id = snap.id
        except Exception:
            click.echo(f"Error: Snapshot '{snapshot_id}' not found.", err=True)
            sys.exit(1)

    try:
        deps = store.list_dependencies(target_id)
    except Exception as e:
        click.echo(f"Error listing dependencies: {e}", err=True)
        sys.exit(1)

    if not deps:
        click.echo(f"No dependencies recorded for snapshot/state '{target_id}'.")
        return

    click.echo(f"Component Dependencies for '{target_id}':")
    for ref, depends_list in sorted(deps.items()):
        click.echo(f"  • {ref}")
        for dep in sorted(depends_list):
            click.echo(f"    └── depends on: {dep}")


if __name__ == "__main__":
    main()


