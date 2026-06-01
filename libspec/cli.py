"""
libspec - unified CLI for spec-driven development.
"""

import inspect
import os
import sys
import click


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
def cmd_build(args):
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


# ---------------------------------------------------------------------------
def cmd_diff(args):
    from libspec.spec_diff import generate_patch
    generate_patch(args["<build_dir>"])


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
@click.argument("spec_file", type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True))
@click.option("-o", "--output", "output_dir", default=None, help="Output directory for optional XML artifact generation")
def build(spec_file, output_dir):
    """Build specification (writes to active SpecStore)."""
    args = {
        "<spec_file>": spec_file,
        "--output": output_dir
    }
    cmd_build(args)


@main.command()
@click.argument("build_dir", required=False, default=None)
def diff(build_dir):
    """Diff the two latest XML specs or database snapshots."""
    args = {
        "<build_dir>": build_dir
    }
    cmd_diff(args)


@main.command()
def mcp():
    """Run the MCP server over stdio."""
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



@main.command()
def repl():
    """Start the interactive specification inspector REPL."""
    cmd_repl(None)


@main.command()
@click.option("--snapshot", "snapshot_id", default=None, help="The 16-character hexadecimal target snapshot identifier. Defaults to current active snapshot.")
@click.option("--vcs", "vcs_type", default="git", help="The VCS system type. Defaults to 'git'.")
@click.option("--revision", "revision", required=True, help="The unique revision identifier (commit SHA, changeset node, or revision number).")
@click.option("--metadata", "metadata_pairs", multiple=True, help="Contextual metadata as key=value pairs.")
def link(snapshot_id, vcs_type, revision, metadata_pairs):
    """Link a spec snapshot to a VCS revision."""
    from libspec.store import get_store, SpecStoreNotFoundError
    import sys

    store = get_store()
    
    # If snapshot_id is not provided, resolve to all unlinked/pending snapshots in the store.
    # If all snapshots are already linked, fall back to the current active snapshot.
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
            current = store.current_snapshot()
            if not current:
                print("Error: SpecStore is empty. Compile a snapshot first using 'libspec build'.")
                sys.exit(1)
            target_ids = [current.id]
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


if __name__ == "__main__":
    main()

