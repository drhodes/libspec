"""
libspec - unified CLI for spec-driven development.

Usage:
  libspec init
  libspec build <spec_file> [-o <output_dir> | --output=<output_dir>]
  libspec diff [<build_dir>]
  libspec mcp
  libspec mcp_agent (<agent> [<project_root>] | --list)
  libspec migrate <v4_build_dir>
  libspec migrate-store <source_url> [--force]
  libspec repl
  libspec -h | --help
  libspec --version

Options:
  -o <output_dir>, --output=<output_dir>  Output directory for optional XML artifact generation
  --list                                  List all supported agents
  --force                                 Overwrite target store without confirmation
  -h, --help                              Show this help message
  --version                               Show version

Subcommands:
  init                             Initialize a new spec directory
  build  <spec_file> [-o DIR]      Build specification (writes to active SpecStore)
  diff   <build_dir>               Diff the two latest XML specs
  mcp                              Run the MCP server over stdio
  mcp_agent (<agent> [DIR] | --list)  Configure coding agent for local project
  migrate <v4_build_dir>           Import legacy v4 spec-*.xml snapshots from a directory into the active SpecStore
  migrate-store <source_url>       Migrate any SpecStore backend to the active backend
  repl                             Start the interactive specification inspector REPL
"""

import inspect
import os
import sys

from docopt import docopt


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

INIT_ERR = """'''
Error and requirement base classes.
'''

from libspec import Ctx, Feature, Requirement

class Err(Ctx):
    '''It is important that error handling be done excellently. If a
    function can fail, then it needs to do so in the most elegant way
    possible. Error reporting, handling, exceptions and all aspects
    of failure must be taken to extreme. It should be possible to
    understand the program by reading the error messages.
    '''

# Use multiple inheritance to endow Feature and Requirement specs with
# disciplined error handling guidance from above.

class Feat(Err, Feature): pass
class Req(Err, Requirement): pass
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

    with open(os.path.join(spec_dir, "err.py"), "w") as f:
        f.write(INIT_ERR)
        
    print(f"Initialized empty spec directory in {spec_dir}")


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
    from libspec.store import get_store, SpecStoreIOError

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

    migrated = 0
    skipped = 0
    for snap in snapshots:
        try:
            components = source.get_components_for_snapshot(snap)
            claims = source.list_implemented(snap)
            written = target.store_snapshot(
                components,
                git_commit=snap.git_commit,
                created_at=snap.created_at,
            )
            for claim in claims:
                target.store_implemented(claim)
            # Idempotency: if master_hash already existed, store_snapshot
            # returns the pre-existing snapshot without writing.
            if written.master_hash == snap.master_hash:
                migrated += 1
                print(
                    f"  migrated  {snap.id}  "
                    f"{snap.created_at.strftime('%Y-%m-%d %H:%M')}  "
                    f"{len(components)} components  {len(claims)} claims"
                )
        except Exception as e:
            print(f"  ERROR     {snap.id}: {e}")
            sys.exit(1)

    print(f"\nMigration complete: {migrated} migrated, {skipped} skipped.")


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
                doc_tag = "docstring_template" if is_template else "docstring"
                doc_node = spec_node.find(doc_tag)
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        from importlib.metadata import version
        v = version("libspec")
    except Exception:
        v = "unknown"
    args = docopt(__doc__, version=f"libspec {v}")

    if args["init"]:
        cmd_init(args)
    elif args["build"]:
        cmd_build(args)
    elif args["diff"]:
        cmd_diff(args)
    elif args["mcp"]:
        cmd_mcp(args)
    elif args["mcp_agent"]:
        cmd_mcp_agent(args)
    elif args["migrate-store"]:
        cmd_migrate_store(args)
    elif args["migrate"]:
        cmd_migrate(args)
    elif args["repl"]:
        cmd_repl(args)


if __name__ == "__main__":
    main()
