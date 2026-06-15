"""
CLI command specifications.
"""

from .err import Feat, Req


class CLI(Req):
    """
    The libspec command-line interface is implemented with the Click library.

    The top-level CLI defines these subcommands:
    - init: Scaffolds a new spec/ directory in the workspace.
    - diff: Displays a structured semantic diff between the live specification and a snapshot, or between two snapshots.
    - list: Lists all components in a snapshot.
    - show: Shows detailed view of a specific component.
    - search: Searches components and docstrings.
    - list-snapshots: Lists chronological snapshot history.
    - log: Shows the chronological append-only event log.
    - link: Late-binds an active spec snapshot to a VCS revision (commit hash).
    - declare-dependency: Declares a logical dependency between components.
    - dependencies: Lists recorded component dependencies.
    - compact: Compacts the SpecStore log.
    - rm-snapshot: Permanently deletes a historical snapshot.
    - restore-snapshot: Restores a soft-deleted historical snapshot.
    - mcp: Launches the Model Context Protocol (MCP) server over stdio.
    - mcp_agent: Configures project-local coding agent integrations.
    - agent-config: Configures project-local coding agent integrations.
    - agent-workflow: Recites standard developer agent workflow instructions.
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


class CliSelfHealingBypass(Req):
    """
    To prevent side effects, warnings, and unwanted mutations outside of a project,
    the CLI must only run self-healing routines if the current working directory
    is an actual libspec project directory.

    Requirements:
    - On CLI startup in the `main` entrypoint, check if the CWD is a valid
      libspec directory using `is_libspec_project()`.
    - If `is_libspec_project()` is False, bypass and do not execute
      `check_and_heal_git_hook()` and `check_and_heal_skills()`.
    """


class SubcommandRegistration(Req):
    """
    Define all subcommands as click commands under the main group:
    - `init`
    - `diff` with optional `[snapshot_a]` and `[snapshot_b]` arguments.
    - `list` with optional `-s` / `--snapshot` option.
    - `show` with `<component_ref>` argument and optional `-s` / `--snapshot` option.
    - `search` with `<query>` argument and optional `-s` / `--snapshot` option.
    - `list-snapshots`
    - `log`
    - `link` with optional `--snapshot`, and required `--revision` options.
    - `declare-dependency` with `<ref>` and `<depends_on>` arguments and optional `--snapshot` option.
    - `dependencies` with optional `-s` / `--snapshot` option.
    - `compact` with optional `--dry-run` flag.
    - `rm-snapshot` with `<snapshot_id>` argument.
    - `restore-snapshot` with `<snapshot_id>` argument.
    - `mcp`
    - `mcp_agent` with optional `<agent>` and `<project_root>` arguments, and `--list` flag.
    - `agent-config` with optional `<agent>` and `<project_root>` arguments, and `--list` flag.
    - `agent-workflow` with optional `--agent` and `--prefix` options.
    - `repl`
    """


class CliBackwardCompatibility(Req):
    """
    Ensure seamless backward compatibility with all active CLI usages, argument
    orderings, option defaults, and exit codes.
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
    - `diff`, `list`, `show`, `search`, `list-snapshots`, `log`,
      `link`, `declare-dependency`, `dependencies`, `compact`, `rm-snapshot`, `restore-snapshot`, `repl`, `mcp`.

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


class DiffCommand(Feat):
    """
    `libspec diff [<snapshot_a>] [<snapshot_b>]` diffs specifications natively.

    Supports relative scoping:
    - Arguments can be relative indices (like `#0`, `#1`) or explicit snapshot hashes/IDs.
    - If no arguments are provided, it compiles the live specification files on-the-fly
      (the pending spec) and diffs them against the latest recorded snapshot `#0`
      without writing to the database.
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


class LinkCommandOnlyOnChangesReq(Req):
    """
    The `link` command must support an `--only-on-changes` option.

    When `--only-on-changes` is passed, the command must inspect the files modified
    in the specified revision. If the revision does not contain changes to both
    specification files (files under `spec/`) and implementation/code files
    (files outside of `spec/`, `.libspec/`, and `.git/`), the command must exit
    successfully with status 0 without creating a snapshot or a VCS link.
    """


class ReplCommand(Feat):
    """
    `libspec repl` launches the interactive specification inspector REPL shell.
    """


class CliDeclareDependencyCommand(Feat):
    """
    `libspec declare-dependency <ref> <depends_on> [--snapshot <id>]`
    declares a logical dependency between components.
    """


class CliDependenciesCommand(Feat):
    """
    `libspec dependencies [--snapshot <id>]`
    lists component dependencies recorded for the target snapshot.
    """


class CliAgentWorkflowCommand(Feat):
    """
    `libspec agent-workflow [--agent <agent>] [--prefix <prefix>]`
    recites the standard developer agent workflow instructions.

    Options:
    - --agent: Target agent platform (e.g. antigravity, claude).
    - --prefix: Explicit MCP tool prefix.
    """
