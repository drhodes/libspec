"""
CLI command specifications.
"""

from .err import Feat, Req


class CLI(Req):
    """
    The libspec command-line interface is implemented with the Click library.

    The top-level CLI defines these subcommands:
    - init: Scaffolds a new spec/ directory in the workspace.
    - diff: Displays a structured semantic diff between the live specification and a commit revision, or between two revisions.
    - list: Lists all components in a commit revision.
    - show: Shows detailed view of a specific component.
    - search: Searches components and docstrings.
    - log: Shows the chronological append-only event log.
    - dependencies: Lists recorded component dependencies.
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
    - `diff` with optional `[commit_a]` and `[commit_b]` arguments.
    - `list` with optional `-c` / `--commit` option.
    - `show` with `<component_ref>` argument and optional `-c` / `--commit` option.
    - `search` with `<query>` argument and optional `-c` / `--commit` option.
    - `log` with optional `-a` / `--all` flag.
    - `dependencies` with optional `-c` / `--commit` option.
    - `mcp`
    - `mcp_agent` with optional `<agent>` and `<project_root>` arguments, and `--list` flag.
    - `agent-config` with optional `<agent>` and `<project_root>` arguments, and `--list` flag.
    - `agent-workflow` with optional `--agent` and `--prefix` options.
    - `repl`
    - `completion` with `<shell>` argument.

    All CLI subcommand implementations must follow `spec.commands.UnifiedCommandPattern`
    acting as lightweight wrappers around the central core engine capabilities.
    The `log` command option `-a`/`--all` must propagate to `spec.commands.UnifiedLogCommand`.
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

    Gated commands:
    - `diff`, `list`, `show`, `search`, `dependencies`, `repl`, `mcp`.

    Excluded commands:
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


class InitCompletionCheckReq(Req):
    """
    During `libspec init`, the tool should check the user's shell rc files
    (like `~/.bashrc`, `~/.zshrc`, or `~/.config/fish/config.fish`) to verify
    if the `libspec completion` autocomplete command is already configured.
    If not, it should print a helpful tip suggestion on how to enable completion.
    """


class DiffCommand(Feat):
    """
    `libspec diff [<commit_a>] [<commit_b>]` diffs specifications natively.

    Supports relative scoping:
    - Arguments can be relative indices (like `HEAD~1`) or explicit commit refs.
    - If no arguments are provided, it compiles the live specification files on-the-fly
      (the pending spec) and diffs them against the latest git commit.
    - If only one argument is provided, it diffs it against the live spec.
    """


class CliListCommand(Feat):
    """
    `libspec list [--commit <ref>]` lists all specification components present in the
    given commit reference (defaulting to live spec if `--commit` is omitted).
    """


class CliShowCommand(Feat):
    """
    `libspec show <component_ref> [--commit <ref>]` prints detailed information about
    the specified component.
    """


class CliSearchCommand(Feat):
    """
    `libspec search <query> [--commit <ref>]` searches for component refs and docstrings
    matching the query.
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


class CliDependenciesCommand(Feat):
    """
    `libspec dependencies [--commit <ref>]`
    lists component dependencies recorded for the target commit reference.
    """


class CliAgentWorkflowCommand(Feat):
    """
    `libspec agent-workflow [--agent <agent>] [--prefix <prefix>]`
    recites the standard developer agent workflow instructions.

    Options:
    - --agent: Target agent platform (e.g. antigravity, claude).
    - --prefix: Explicit MCP tool prefix.
    """


class WorkflowHooksConfigReq(Req):
    """
    The `agent-workflow` command must load project-specific workflow hooks
    configured in `.libspec/workflow.yaml` (if present) and dynamically inject
    the hook lists (such as `pre-diff` or `post-implement`) into the correct positions
    of the recited developer workflow checklist.
    """


class CliCompletionCommand(Feat):
    """
    `libspec completion <shell>`
    outputs the shell completion script for the specified shell (bash, zsh, or fish)
    to enable CLI tab completion.
    """


class WorkflowSpecSyncCheckReq(Req):
    """
    The recited `agent-workflow` checklist must include a validation step
    reminding the developer/agent to run a spec diff (e.g. `uv run libspec diff`)
    to verify that the live specifications are fully synchronized with the
    final implementation prior to authoring the commit message.
    """
