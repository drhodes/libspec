"""
CLI command specifications.
"""

from .err import Feat, Req


class CLI(Req):
    """
    The libspec command-line interface is implemented with the Click library.

    The top-level CLI defines these subcommands:
    - init: Scaffolds a new spec/ directory in the workspace.
    - snapshot: Compiles the spec file and registers it with the SpecStore.
    - diff: Displays a structured semantic diff between two specifications.
    - list: Lists all components in a snapshot.
    - show: Shows detailed view of a specific component.
    - search: Searches components and docstrings.
    - list-snapshots: Lists chronological snapshot history.
    - log: Shows the chronological append-only event log.
    - link: Late-binds an active spec snapshot to a VCS revision (commit hash).
    - compact: Compacts the SpecStore log.
    - rm-snapshot: Permanently deletes a historical snapshot.
    - restore-snapshot: Restores a soft-deleted historical snapshot.
    - mcp: Launches the Model Context Protocol (MCP) server over stdio.
    - mcp_agent: Configures project-local coding agent integrations.
    - agent-config: Configures project-local coding agent integrations.
    - repl: Starts the interactive specification inspector REPL shell.

    The --version option reports the installed package version.
    Help is available via --help.
    """


class ClickCLIStructure(Feat):
    """
    Unified command-line interface structure using the Click library.
    """


class MainCliGroup(Req):
    """
    Define a central click Group `main` that manages the entrypoint, handling
    common options like `--version` and `--help`.
    """


class SubcommandRegistration(Req):
    """
    Define all subcommands as click commands under the main group:
    - `init`
    - `snapshot` with `<spec_file>` argument and optional `-o` / `--output` option.
    - `diff` with optional `[snapshot_a]` and `[snapshot_b]` arguments.
    - `list` with optional `-s` / `--snapshot` option.
    - `show` with `<component_ref>` argument and optional `-s` / `--snapshot` option.
    - `search` with `<query>` argument and optional `-s` / `--snapshot` option.
    - `list-snapshots`
    - `log`
    - `link` with optional `--snapshot`, and required `--revision` options.
    - `compact` with optional `--dry-run` flag.
    - `rm-snapshot` with `<snapshot_id>` argument.
    - `restore-snapshot` with `<snapshot_id>` argument.
    - `mcp`
    - `mcp_agent` with optional `<agent>` and `<project_root>` arguments, and `--list` flag.
    - `agent-config` with optional `<agent>` and `<project_root>` arguments, and `--list` flag.
    - `repl`
    """


class CliBackwardCompatibility(Req):
    """
    Ensure seamless backward compatibility with all active CLI usages, argument
    orderings, option defaults, and exit codes. The legacy `build` command name
    must be maintained as a hidden deprecated alias for `snapshot`.
    """


class CliParameterValidation(Req):
    """
    Implement professional click-based validation and clean parameter types
    (such as click.Path) for paths and directories where applicable.
    """


class CwdValidation(Req):
    """
    All store-dependent CLI subcommands must validate that the current working
    directory is a valid libspec project before executing.

    A valid libspec project is one that contains a `.libspec/` subdirectory
    (see `spec.utils.IsLibspecProject`).

    Gated commands (all commands that read or write the SpecStore):
    - `snapshot`, `diff`, `list`, `show`, `search`, `list-snapshots`, `log`,
      `link`, `compact`, `rm-snapshot`, `restore-snapshot`, `repl`, `mcp`.

    Excluded commands (do not touch the store):
    - `init` (creates the project), `agent-config`, `mcp_agent`,
      `--version`, `--help`.

    Behavior when the check fails:
    - Print a clear, human-readable error message to stderr that names the
      checked directory and tells the user to run `libspec init`.
    - Exit with a non-zero exit code (exit code 1).
    - Do not proceed with any store operations.

    The check must be implemented via a shared `require_libspec_project()`
    utility (see `spec.utils.LibspecProjectGuard`) called at the start of
    each gated subcommand, catching `NotALibspecProjectError` and converting
    it to a `click.UsageError` (which Click renders cleanly and exits 1).
    """


class InitCommand(Feat):
    """
    `libspec init` scaffolds a new spec/ directory in the current working
    directory with three starter files:

    - spec/__init__.py (empty)
    - spec/main_spec.py (a MainSpec(Spec) class wired to the app module)
    - spec/app.py (placeholder App and CmdLine classes)
    - spec/err.py (Err base class + Feat/Req convenience aliases)

    The command exits with an error if a spec/ directory already exists,
    preventing accidental overwrite of an existing specification.
    """


class SnapshotCommand(Feat):
    """
    `libspec snapshot <spec_file> [-o <output_dir>]` generates a specification
    snapshot from a Python spec file and writes it to the active SpecStore.

    Module loading strategy:
    - The spec file path is converted to a dotted module name relative to the
      current working directory.
    - The CWD is prepended to sys.path so that relative imports within the spec
      package resolve correctly.
    - The module is imported via importlib.import_module() so that __package__
      is set correctly for relative imports.

    Discovery strategy:
    - If the module contains an explicit Spec subclass, it is instantiated and
      its components are written to the store.
    - Otherwise, all Ctx subclasses in the module are discovered via
      `module_specs()` and compiled.
    """


class XmlSnapshotDeprecation(Req):
    """
    Emitting XML specifications to a local output directory (such as `-o spec-build`)
    is deprecated and scheduled for removal.

    Requirements:
    1. If the user invokes `libspec snapshot` with a directory option (`-o` or `--output`),
       the system must print a prominent deprecation warning to standard error.
    2. Raise a Python `DeprecationWarning` programmatically.
    3. Encourage the user to transition to using the active SpecStore instead.
    """


class DiffCommand(Feat):
    """
    `libspec diff [<snapshot_a>] [<snapshot_b>]` diffs two specification snapshots
    natively.

    Supports relative scoping:
    - Arguments can be relative indices (like `#0`, `#1`) or explicit snapshot hashes/IDs.
    - If no arguments are provided, it diffs `#1` (second latest) against `#0` (latest).
    - If only one argument is provided, it diffs it against `#0`.
    """


class CliListCommand(Feat):
    """
    `libspec list [--snapshot <id>]` lists all specification components present in the
    given snapshot (defaulting to the latest snapshot if `--snapshot` is omitted).
    """


class CliShowCommand(Feat):
    """
    `libspec show <component_ref> [--snapshot <id>]` prints detailed information about
    the specified component.
    """


class CliSearchCommand(Feat):
    """
    `libspec search <query> [--snapshot <id>]` searches for component refs and docstrings
    matching the query.
    """


class CliListSnapshotsCommand(Feat):
    """
    `libspec list-snapshots` prints a formatted table of all recorded snapshots in the database.
    """


class CliLogCommand(Feat):
    """
    `libspec log` prints the store transaction ledger log.
    """


class CliCompactCommand(Feat):
    """
    `libspec compact [--dry-run]` compacts the SpecStore database log.
    """


class CliRmSnapshotCommand(Feat):
    """
    `libspec rm-snapshot <snapshot_id>` deletes a historical snapshot.
    """


class CliRestoreSnapshotCommand(Feat):
    """
    `libspec restore-snapshot <snapshot_id>` restores a deleted historical snapshot.
    """


class McpCommand(Feat):
    """
    `libspec mcp` launches the MCP (Model Context Protocol) server over stdio.
    """


class McpAgentCommand(Feat):
    """
    `libspec mcp_agent (<agent> [DIR] | --list)` automates local coding agent
    integrations.
    """


class AgentConfigCommand(Feat):
    """
    `libspec agent-config (<agent> [DIR] | --list)` automates local coding agent
    integrations by configuring MCP settings and installing skills.
    """


class LinkCommand(Feat):
    """
    `libspec link [--snapshot <snapshot_id>] [--vcs <vcs_type>] --revision <revision> [--metadata <key=val>]`
    links a compiled spec snapshot to a version control system revision.
    """


class ReplCommand(Feat):
    """
    `libspec repl` launches the interactive specification inspector REPL shell.
    """
