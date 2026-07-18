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


INIT_WORKFLOW_YAML = """# Agent Workflow Hooks configuration file.
# Uncomment any hooks below to configure project-specific commands.

hooks:
  # post-edit:
  #   - "Run spec compiler validation: `uv run libspec diff`"
  #
  # pre-diff:
  #   - "Compile spec if needed"
  #
  # post-implement:
  #   - "Run tests: `npm run test`"
  #   - "Run linter: `npm run lint`"
  #
  # pre-commit:
  #   - "Verify code formatting: `npm run format`"
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
        print(
            f"Error: Internal template file '{template_err_path}' not found. Reinstall libspec."
        )
        sys.exit(1)

    with open(template_err_path, encoding="utf-8") as f:
        err_content = f.read()

    with open(os.path.join(spec_dir, "err.py"), "w") as f:
        f.write(err_content)

    # Create the .libspec/ directory — this is the canonical project marker.
    # All store-dependent commands gate on its presence (spec.cli.CwdValidation).
    libspec_dir = os.path.abspath(".libspec")
    os.makedirs(libspec_dir, exist_ok=True)

    with open(os.path.join(libspec_dir, "workflow.yaml"), "w") as f:
        f.write(INIT_WORKFLOW_YAML)

    print(f"Initialized empty spec directory in {spec_dir}")


# ---------------------------------------------------------------------------
def _store_label(store) -> str:
    """Return a short human-readable label for the active store backend."""
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
        module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, ".")
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


def cmd_diff(old_commit=None, new_commit=None):
    from libspec.spec_diff import generate_native_patch

    generate_native_patch(old_commit=old_commit, new_commit=new_commit)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.version_option(package_name="libspec", prog_name="libspec")
@click.pass_context
def main(ctx):
    """libspec - unified CLI for spec-driven development."""
    from libspec.util import is_libspec_project

    # Only run skill configuration/healing on setup/MCP-related commands
    if is_libspec_project() and ctx.invoked_subcommand in (
        "init",
        "agent-config",
        "mcp",
    ):
        # Check and heal skills on startup
        try:
            import os
            import sys

            from libspec.agent_config import check_and_heal_skills

            messages = check_and_heal_skills(os.getcwd(), auto_heal=True)
            for msg in messages:
                print(f"[libspec] {msg}", file=sys.stderr)
        except Exception as e:
            import sys

            print(
                f"[libspec] Warning: Error checking agent skills: {e}", file=sys.stderr
            )

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
def init():
    """Initialize a new spec directory."""
    cmd_init(None)


@main.command()
@click.argument("commit_a", required=False)
@click.argument("commit_b", required=False)
def diff(commit_a, commit_b):
    """Diff specification trees natively between Git commits.

    If no arguments are provided, it compiles the live specification files in the workspace on-the-fly
    and diffs them against HEAD.
    If only one argument is provided, it diffs it against HEAD.
    """
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))

    cmd_diff(old_commit=commit_a, new_commit=commit_b)


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
    args = {"<agent>": agent, "<project_root>": project_root, "--list": list_agents}
    cmd_mcp_agent(args)


@main.command(name="agent-config")
@click.argument("agent", required=False, default=None)
@click.argument("project_root", required=False, default=None)
@click.option("--list", "list_agents", is_flag=True, help="List all supported agents")
def agent_config(agent, project_root, list_agents):
    """Configure coding agent for local project."""
    if not list_agents and not agent:
        raise click.UsageError("Missing argument 'AGENT' or '--list' option.")
    args = {"<agent>": agent, "<project_root>": project_root, "--list": list_agents}
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
@click.option(
    "-c",
    "--commit",
    "commit_ref",
    default=None,
    help="Git commit/ref. Defaults to live spec.",
)
def list(commit_ref):
    """List all specification components."""
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))

    from libspec.util import compile_git_spec, compile_live_spec

    if commit_ref:
        try:
            comps = compile_git_spec(commit_ref)
        except Exception as e:
            click.echo(f"Error loading specs at '{commit_ref}': {e}", err=True)
            sys.exit(1)
        label = f"Git Ref: {commit_ref}"
    else:
        try:
            comps, _ = compile_live_spec()
        except Exception as e:
            click.echo(f"Error compiling live specs: {e}", err=True)
            sys.exit(1)
        label = "HEAD (Live Spec)"

    comps = [c for c in comps if not getattr(c, "is_dependency", False)]
    if not comps:
        click.echo("No components found.")
        return

    click.echo(f"Specification ({label}) Components ({len(comps)} total):")
    for comp in comps:
        comp_type = "Template" if comp.is_template else "Component"
        click.echo(f"  • {comp.ref} [{comp_type}]")


@main.command()
@click.argument("component_ref")
@click.option(
    "-c",
    "--commit",
    "commit_ref",
    default=None,
    help="Git commit/ref. Defaults to live spec.",
)
def show(component_ref, commit_ref):
    """Show details of a specific component."""
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))

    from libspec.util import compile_git_spec, compile_live_spec

    if commit_ref:
        try:
            comps = compile_git_spec(commit_ref)
        except Exception as e:
            click.echo(f"Error loading specs at '{commit_ref}': {e}", err=True)
            sys.exit(1)
        label = f"Git Ref: {commit_ref}"
    else:
        try:
            comps, _ = compile_live_spec()
        except Exception as e:
            click.echo(f"Error compiling live specs: {e}", err=True)
            sys.exit(1)
        label = "HEAD (Live Spec)"

    comp = next((c for c in comps if c.ref == component_ref), None)
    if not comp:
        click.echo(
            f"Error: Component '{component_ref}' not found in '{label}'.",
            err=True,
        )
        sys.exit(1)

    click.echo("=" * 60)
    click.echo(f"Reference:   {comp.ref}")
    click.echo(
        f"Type:        {'Template Requirement' if comp.is_template else 'Requirement'}"
    )
    click.echo(f"Hash:        {comp.hash}")
    if comp.inherits:
        click.echo("Inherits:    " + ", ".join(comp.inherits))
    click.echo(f"Docstring:\n{'-' * 60}\n{comp.docstring}\n{'-' * 60}")

    from libspec.util import find_implementations_in_workspace

    claims = find_implementations_in_workspace(component_ref)
    if claims:
        click.echo(f"Implementation Claims ({len(claims)}):")
        for cl in claims:
            click.echo(f"  • {cl['file']}:{cl['line']}")
    else:
        click.echo("No implementation claims found in codebase.")
    click.echo("=" * 60)


@main.command()
@click.argument("query")
@click.option(
    "-c",
    "--commit",
    "commit_ref",
    default=None,
    help="Git commit/ref. Defaults to live spec.",
)
def search(query, commit_ref):
    """Search components and docstrings."""
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))

    from libspec.util import compile_git_spec, compile_live_spec

    if commit_ref:
        try:
            comps = compile_git_spec(commit_ref)
        except Exception as e:
            click.echo(f"Error loading specs at '{commit_ref}': {e}", err=True)
            sys.exit(1)
        label = f"Git Ref: {commit_ref}"
    else:
        try:
            comps, _ = compile_live_spec()
        except Exception as e:
            click.echo(f"Error compiling live specs: {e}", err=True)
            sys.exit(1)
        label = "HEAD (Live Spec)"

    matches = [
        c
        for c in comps
        if query.lower() in c.ref.lower() or query.lower() in c.docstring.lower()
    ]
    if not matches:
        click.echo(f"No components found matching '{query}'.")
        return

    click.echo(f"Search Results for '{query}' ({len(matches)} matches in {label}):")
    for comp in matches:
        comp_type = "Template" if comp.is_template else "Component"
        first_line = comp.docstring.split("\n")[0] if comp.docstring else ""
        snippet = first_line[:60]
        if len(first_line) > 60:
            snippet += "..."
        click.echo(f"  • {comp.ref} [{comp_type}] - {snippet}")


@main.command()
def log():
    """Show Git commit history of specifications."""
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))

    import subprocess

    try:
        res = subprocess.run(
            [
                "git",
                "log",
                "--pretty=format:%h - %an, %ad : %s",
                "--date=short",
                "--",
                "spec",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        if not res.stdout.strip():
            click.echo("No Git commits found for specifications.")
            return
        click.echo("Specification Git Commit History:")
        click.echo("-" * 80)
        click.echo(res.stdout)
        click.echo("-" * 80)
    except Exception as e:
        click.echo(f"Error querying Git history: {e}", err=True)
        sys.exit(1)


@main.command(name="dependencies")
@click.option(
    "-c",
    "--commit",
    "commit_ref",
    default=None,
    help="Git commit/ref. Defaults to live spec.",
)
def dependencies(commit_ref):
    """List component dependencies."""
    try:
        require_libspec_project()
    except NotALibspecProjectError as e:
        raise click.UsageError(str(e))

    from libspec.util import compile_git_spec, compile_live_spec

    if commit_ref:
        try:
            comps = compile_git_spec(commit_ref)
        except Exception as e:
            click.echo(f"Error loading specs at '{commit_ref}': {e}", err=True)
            sys.exit(1)
        label = f"Git Ref: {commit_ref}"
    else:
        try:
            comps, _ = compile_live_spec()
        except Exception as e:
            click.echo(f"Error compiling live specs: {e}", err=True)
            sys.exit(1)
        label = "HEAD (Live Spec)"

    deps = {}
    for comp in comps:
        if comp.inherits:
            deps[comp.ref] = comp.inherits

    if not deps:
        click.echo(f"No dependencies recorded for '{label}'.")
        return

    click.echo(f"Component Dependencies for '{label}':")
    for ref, depends_list in sorted(deps.items()):
        click.echo(f"  • {ref}")
        for dep in sorted(depends_list):
            click.echo(f"    └── depends on: {dep}")


@main.command("agent-workflow")
@click.option(
    "--agent", help="Target agent platform (e.g., antigravity, gemini, claude)."
)
@click.option("--prefix", help="Explicit MCP tool prefix.")
def agent_workflow_cmd(agent, prefix):
    """Recite the standard developer agent workflow instructions."""
    from libspec.workflow import get_agent_workflow, resolve_prefix

    pfx = resolve_prefix(agent=agent, prefix=prefix, project_root=".")
    click.echo(get_agent_workflow(pfx))


@main.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion_cmd(shell):
    """Output shell completion script for the specified shell."""
    from click.shell_completion import get_completion_class

    cls = get_completion_class(shell)
    if cls is None:
        raise click.UsageError(f"Shell {shell} is not supported.")
    comp = cls(main, {}, "libspec", "_LIBSPEC_COMPLETE")
    click.echo(comp.source())


if __name__ == "__main__":
    main()

