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

if __name__ == "__main__":
    MainSpec().write_xml("spec-build")
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


def cmd_migrate_store(args):
    '''Migrate all snapshots from a source SpecStore to the active target backend.'''
    from libspec.migration import migrate, store_from_url
    from libspec.store import get_store

    source_url = args["<source_url>"]
    try:
        source = store_from_url(source_url)
    except Exception as e:
        print(f"Error: could not open source store '{source_url}': {e}")
        sys.exit(1)

    target = get_store()
    print(f"Source : {_store_label(source)}")
    print(f"Target : {_store_label(target)}")

    # Refuse to migrate a store to itself
    src_id = getattr(source, "filepath", None) or getattr(source, "db_path", None)
    tgt_id = getattr(target, "filepath", None) or getattr(target, "db_path", None)
    if src_id and tgt_id and os.path.abspath(src_id) == os.path.abspath(tgt_id):
        print("Error: source and target resolve to the same store location.")
        sys.exit(1)

    try:
        snapshots = source.list_snapshots()
    except Exception as e:
        print(f"Error reading source snapshots: {e}")
        sys.exit(1)

    for snap in snapshots:
        try:
            components = source.get_components_for_snapshot(snap)
            claims = source.list_implemented(snap)
            already_present = _store_has_snapshot(target, snap.master_hash)
            outcome = "skipped" if already_present else "migrated"
            print(
                f"  {outcome:<8}  {snap.id}  "
                f"{snap.created_at.strftime('%Y-%m-%d %H:%M')}  "
                f"{len(components)} components  {len(claims)} claims"
            )
        except Exception as e:
            print(f"  ERROR     {snap.id}: {e}")
            sys.exit(1)

    try:
        summary = migrate(source, target)
    except Exception as e:
        print(f"Error: migration failed: {e}")
        sys.exit(1)

    print(f"\nMigration complete: {summary['migrated']} migrated, {summary['skipped']} skipped.")


def _store_has_snapshot(store, master_hash):
    try:
        store.get_snapshot(master_hash)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
def cmd_migrate(args):
    import glob
    import os
    import xml.etree.ElementTree as ET
    import datetime
    import hashlib
    from libspec.store import get_store, Component, Implemented, XmlSpecStore
    
    v4_dir = os.path.abspath(args["<v4_build_dir>"])
    if not os.path.exists(v4_dir) or not os.path.isdir(v4_dir):
        print(f"Error: Target directory '{v4_dir}' does not exist or is not a directory.")
        sys.exit(1)
        
    print(f"Starting migration from v4 build directory: {v4_dir}")
    
    # Scan directory for spec-*.xml files
    pattern = os.path.join(v4_dir, "spec-*.xml")
    xml_files = glob.glob(pattern)
    if not xml_files:
        print("Error: No legacy hashed spec-*.xml files found in target directory.")
        sys.exit(1)
        
    # Sort files chronologically
    file_info = []
    for f in xml_files:
        try:
            tree = ET.parse(f)
            root = tree.getroot()
            date_str = root.get("date-created")
            if date_str:
                file_info.append((date_str, f))
            else:
                mtime = os.path.getmtime(f)
                dt = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc)
                file_info.append((dt.isoformat(), f))
        except Exception:
            mtime = os.path.getmtime(f)
            dt = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc)
            file_info.append((dt.isoformat(), f))
            
    file_info.sort(key=lambda x: x[0])
    
    print(f"Found {len(file_info)} historical build snapshot files to migrate.")
    
    # Resolve target SpecStore
    target_store = get_store()
    db_url = os.environ.get("LIBSPEC_DATABASE_URL")
    if db_url:
        print(f"Targeting Relational SpecStore Database: {db_url}")
    else:
        if isinstance(target_store, XmlSpecStore):
            print(f"Targeting XML SpecStore Fallback: {target_store.xml_path}")
            
    migrated_count = 0
    for date_str, fpath in file_info:
        print(f"  Migrating snapshot: {os.path.basename(fpath)} ({date_str})...")
        try:
            tree = ET.parse(fpath)
            root = tree.getroot()
            
            git_commit = root.get("git-commit")
            # Handle possible date parsing offsets
            try:
                created_at = datetime.datetime.fromisoformat(date_str)
            except ValueError:
                # Handle old zulu formats or missing offsets
                if date_str.endswith("Z"):
                    date_str = date_str[:-1] + "+00:00"
                created_at = datetime.datetime.fromisoformat(date_str)
                
            components = []
            for spec_node in root.findall("specification"):
                ref = spec_node.get("ref")
                if not ref:
                    continue
                    
                is_template = spec_node.get("template") == "true"
                doc_node = _xml_component_doc_node(spec_node, is_template)
                docstring = doc_node.text if doc_node is not None else ""
                
                inherits = [n.text for n in spec_node.findall("inherits/ref") if n.text]
                comp_hash = spec_node.get("hash") or hashlib.sha256(docstring.encode("utf-8")).hexdigest()
                
                components.append(Component(
                    ref=ref,
                    docstring=docstring,
                    is_template=is_template,
                    inherits=inherits,
                    hash=comp_hash
                ))
                
            # Save snapshot with exact historical created_at timestamp!
            snapshot = target_store.store_snapshot(
                components,
                git_commit=git_commit,
                created_at=created_at
            )
            
            # Migrate implementation claims if present in XML
            claims_elem = root.find("implemented_claims")
            if claims_elem is not None:
                claim_count = 0
                for claim_node in claims_elem.findall("claim"):
                    ref = claim_node.get("ref")
                    spec_hash = claim_node.get("spec_hash")
                    file_path = claim_node.get("file")
                    line_str = claim_node.get("line")
                    session_id = claim_node.get("session_id")
                    
                    if ref and spec_hash and file_path and line_str:
                        target_store.store_implemented(Implemented(
                            ref=ref,
                            spec_hash=spec_hash,
                            file=file_path,
                            line=int(line_str),
                            session_id=session_id
                        ))
                        claim_count += 1
                if claim_count > 0:
                    print(f"    Injected {claim_count} implementation claims.")
                    
            migrated_count += 1
        except Exception as e:
            print(f"Error migrating {os.path.basename(fpath)}: {e}")
            sys.exit(1)
            
    print(f"Migration completed successfully! Migrated {migrated_count} snapshots.")


def cmd_repl(args):
    from libspec.repl import LibspecRepl
    LibspecRepl().start()


def _xml_component_doc_node(spec_node, is_template):
    preferred = "docstring_template" if is_template else "docstring"
    fallback = "docstring" if is_template else "docstring_template"
    doc_node = spec_node.find(preferred)
    if doc_node is None:
        doc_node = spec_node.find(fallback)
    return doc_node


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
@click.argument("source_url")
def migrate(source_url):
    """Migrate all snapshots from a source SpecStore backend to the active target backend."""
    args = {
        "<source_url>": source_url
    }
    cmd_migrate_store(args)


@main.command(name="migrate-v4")
@click.argument("v4_build_dir", type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True))
def migrate_v4(v4_build_dir):
    """Import legacy v4 spec-*.xml snapshots from a directory into the active SpecStore."""
    args = {
        "<v4_build_dir>": v4_build_dir
    }
    cmd_migrate(args)


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



if __name__ == "__main__":
    main()

