"""
CLI command specifications.
"""

from .commands import UnifiedCommandPattern
from .core import SpecBase
from .dependencies import (
    DependencyGraphVisualizationFeat,
    ReverseDependencyAnalysisFeat,
    TopologicalImplementationOrderingFeat,
)
from .diff import DiffEngine
from .err import Feat, Req
from .mcp import AgentConfig
from .utils import IsLibspecProject, LibspecProjectGuard


class ClickCLIStructure(Feat):
    """
    Unified command-line interface structure using the Click library.
    """

    deps = [LibspecProjectGuard]


class MainCliGroup(Req):
    """
    Define a central click Group `main` that manages the entrypoint, handling
    common options like `--version` and `--help`.
    """

    deps = [ClickCLIStructure]


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

    deps = [MainCliGroup, IsLibspecProject]


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
      `help`, `--version`, `--help`.

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

    deps = [MainCliGroup, LibspecProjectGuard]


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
    - `help` with optional `<command>` argument.

    All CLI subcommand implementations must follow `spec.commands.UnifiedCommandPattern`
    acting as lightweight wrappers around the central core engine capabilities.
    The `log` command option `-a`/`--all` must propagate to `spec.commands.UnifiedLogCommand`.
    """

    deps = [MainCliGroup, CwdValidation, UnifiedCommandPattern]


class InitCommand(Feat):
    """
    `libspec init` scaffolds a new spec/ directory in the current working
    directory with three starter files:

    - spec/__init__.py (empty)
    - spec/main_spec.py (a MainSpec(Spec) class wired to the app module)
    - spec/app.py (placeholder App and CmdLine classes)
    - spec/err.py (Err base class + Feat/Req convenience aliases)

    It also initializes the .libspec/ project configuration directory and the
    .agents/ workspace directory for agent workflow skills.

    The command exits with an error if a spec/ directory already exists,
    preventing accidental overwrite of an existing specification.
    """

    deps = [SubcommandRegistration]


class InitAgentsDirReq(Req):
    """
    During `libspec init`, the tool must scaffold and configure the workspace `.agents/`
    directory layout and install default agent skills (via `AgentsConfig.configure()`).

    This generic `.agents/skills/libspec/SKILL.md` stub is agent-agnostic: it
    documents the libspec MCP tools but does not, on its own, register the
    libspec MCP server with any concrete coding-agent CLI. See
    `InitAgentAutoDetectionReq` for the requirement that actually wires up
    MCP registration for the agent(s) present on the host.
    """

    deps = [InitCommand]


class InitWorkflowYamlReq(Req):
    """
    During `libspec init`, the tool must scaffold `.libspec/workflow.yaml`
    with starter hook declarations and guidance comments covering the
    9-phase development loop.
    """

    deps = [InitCommand]


class InitAgentAutoDetectionReq(Req):
    """
    `libspec init` must not stop at installing the generic, inert
    `.agents/skills/libspec/SKILL.md` stub (`InitAgentsDirReq`). It must also
    detect which concrete coding-agent CLI(s) are actually present on the
    host and invoke that agent's registered `spec.mcp.AgentConfig` subclass's
    `.configure()`, so a fresh `init` run ends with the libspec MCP server
    actually registered for that agent (e.g. `claude mcp add libspec -- uv
    run libspec mcp` for Claude Code), not merely described in a skill file.
    """

    deps = [InitAgentsDirReq, AgentConfig]


class AgentCliPresenceSignalReq(Req):
    """
    An agent CLI counts as "present," for the purposes of
    `InitAgentAutoDetectionReq`, when its binary is resolvable via
    `shutil.which(...)` (e.g. `claude` for `ClaudeConfig`, `gemini` for
    `GeminiConfig`, `codex` for `CodexConfig`, `opencode` for
    `OpenCodeConfig`). `AgentConfig.is_active` (which checks for pre-existing
    project markers like `.claude/`) is not sufficient on its own to trigger
    auto-configuration on a brand-new project, since a fresh `init` run has
    no such markers yet; relying on it would leave the detection permanently
    chicken-and-egg.
    """

    deps = [InitAgentAutoDetectionReq]


class InitMultiAgentConfigureReq(Req):
    """
    If more than one agent CLI is detected, `init` configures all of them.
    Each configurator only ever touches its own agent-specific paths
    (`.claude/`, `.gemini/`, `.codex/`, `.opencode/`, `.github/`) and must
    never write into another agent's directory.
    """

    deps = [InitAgentAutoDetectionReq]


class InitNoAgentDetectedReq(Req):
    """
    If no known agent CLI is present, `init` completes exactly as before
    (only the generic `.agents/skills/libspec/` stub installed) and prints a
    hint that `libspec agent-config <agent> .` can be run manually once an
    agent CLI is installed.
    """

    deps = [InitAgentAutoDetectionReq]


class InitAgentConfigureFailureIsolationReq(Req):
    """
    A failure while configuring one detected agent (CLI exits non-zero,
    raises, or its config path is read-only) must be caught, reported to the
    user as a warning naming the failing agent, and must not abort `init` or
    prevent configuration of any other detected agent.
    """

    deps = [InitAgentAutoDetectionReq]


class InitAgentConfigureCallSiteReq(Req):
    """
    `cmd_init` is the only call site that triggers detect-and-configure
    automatically. `check_and_heal_skills` continues to only heal agents
    already marked `is_active` on subsequent CLI invocations (`diff`, `mcp`,
    etc.), and manual `libspec agent-config <agent> .` remains available for
    agents installed after `init` has already run.
    """

    deps = [InitAgentAutoDetectionReq]


class InitCompletionCheckReq(Req):
    """
    During `libspec init`, the tool should check the user's shell rc files
    (like `~/.bashrc`, `~/.zshrc`, or `~/.config/fish/config.fish`) to verify
    if the `libspec completion` autocomplete command is already configured.
    If not, it should print a helpful tip suggestion on how to enable completion.
    """

    deps = [InitCommand]


class DiffCommand(Feat):
    """
    `libspec diff [<commit_a>] [<commit_b>]` diffs specifications natively.

    Supports relative scoping:
    - Arguments can be relative indices (like `HEAD~1`) or explicit commit refs.
    - If no arguments are provided, it compiles the live specification files on-the-fly
      (the pending spec) and diffs them against the latest git commit.
    - If only one argument is provided, it diffs it against the live spec.
    """

    deps = [SubcommandRegistration, DiffEngine]


class CliListCommand(Feat):
    """
    `libspec list [--commit <ref>]` lists all specification components present in the
    given commit reference (defaulting to live spec if `--commit` is omitted).
    """

    deps = [SubcommandRegistration, SpecBase]


class CliShowCommand(Feat):
    """
    `libspec show <component_ref> [--commit <ref>]` prints detailed information about
    the specified component.
    """

    deps = [SubcommandRegistration, SpecBase]


class CliSearchCommand(Feat):
    """
    `libspec search <query> [--commit <ref>]` searches for component refs and docstrings
    matching the query.
    """

    deps = [SubcommandRegistration, SpecBase]


class CliDependenciesCommand(Feat):
    """
    `libspec dependencies [COMPONENT_REF] [--commit <ref>] [--topo] [--inherits] [--mermaid] [--dot] [--html [PATH]] [--rdeps] [-o <file>]`
    inspects and visualizes component dependencies, implementation waves, and downstream blast radius.

    Options:
    - COMPONENT_REF: Optional target component to scope dependency or blast radius analysis.
    - --commit, -c: Git commit/ref. Defaults to live spec.
    - --topo: Print topological implementation wave ordering.
    - --inherits: Print MRO constraint inheritance hierarchy instead of logical prerequisites.
    - --mermaid: Output Mermaid diagram syntax.
    - --dot: Output Graphviz DOT digraph syntax.
    - --html [PATH]: Generate standalone interactive HTML/SVG visualization (default: dependencies.html).
    - --rdeps: Compute reverse dependencies (downstream dependents / blast radius).
    - -o, --output: Destination file path for generated visual output.
    """

    deps = [
        SubcommandRegistration,
        TopologicalImplementationOrderingFeat,
        DependencyGraphVisualizationFeat,
        ReverseDependencyAnalysisFeat,
    ]


class McpCommand(Feat):
    """
    `libspec mcp` launches the MCP (Model Context Protocol) server over stdio.
    """

    deps = [SubcommandRegistration]


class McpAgentCommand(Feat):
    """
    `libspec mcp_agent (<agent> [DIR] | --list)` automates local coding agent
    integrations.
    """

    deps = [SubcommandRegistration]


class AgentConfigCommand(Feat):
    """
    `libspec agent-config (<agent> [DIR] | --list)` automates local coding agent
    integrations by configuring MCP settings and installing skills.
    """

    deps = [SubcommandRegistration]


class CliAgentWorkflowCommand(Feat):
    """
    `libspec agent-workflow [--agent <agent>] [--prefix <prefix>]`
    recites the standard developer agent workflow instructions.

    Options:
    - --agent: Target agent platform (e.g. antigravity, claude).
    - --prefix: Explicit MCP tool prefix.
    """

    deps = [SubcommandRegistration]


class WorkflowHooksConfigReq(Req):
    """
    The `agent-workflow` command must load project-specific workflow hooks
    configured in `.libspec/workflow.yaml` (if present) and dynamically inject
    the hook lists (such as `pre-diff` or `post-implement`) into the correct positions
    of the recited developer workflow checklist.
    """

    deps = [CliAgentWorkflowCommand]


class WorkflowYamlSchemaReq(Req):
    """
    `.libspec/workflow.yaml` defines a top-level `hooks:` mapping. Each key represents
    a phase integration anchor and contains either a string or list of strings defining
    executable shell commands or verification instructions.
    """

    deps = [WorkflowHooksConfigReq]


class WorkflowHooksLifecycleReq(Req):
    """
    The workflow hooks system provides integration anchors across the full
    9-step development lifecycle:
    - Phase 1 (Edit Spec): `post-edit`
    - Phase 2 (Diff Spec): `pre-diff`, `post-diff`
    - Phase 3 (Sort Ordering): `post-dependencies`
    - Phase 4 (TDD): `pre-test`, `post-test`
    - Phase 5 (Implement): `pre-implement`, `post-implement`
    - Phase 6 (Quality): `pre-commit`
    - Phase 7 (Spec Sync): `post-sync`
    - Phase 8 (Version Bump): `pre-bump`, `post-bump`
    - Phase 9 (Commit): `post-commit`
    """

    deps = [WorkflowHooksConfigReq, WorkflowYamlSchemaReq]


class WorkflowYamlResilienceReq(Req):
    """
    When `.libspec/workflow.yaml` is missing, empty, or contains non-mapping or
    corrupted YAML syntax, `get_agent_workflow` must not fail or crash the process.
    It must gracefully log or absorb the format anomaly and fall back to reciting
    the default workflow without custom hooks.
    """

    deps = [WorkflowHooksConfigReq]


class WorkflowSpecSyncCheckReq(Req):
    """
    The recited `agent-workflow` checklist must include a validation step
    reminding the developer/agent to run a spec diff (e.g. `uv run libspec diff`)
    to verify that the live specifications are fully synchronized with the
    final implementation prior to authoring the commit message.
    """

    deps = [CliAgentWorkflowCommand, DiffCommand]


class WorkflowComponentSortingReq(Req):
    """
    The recited `agent-workflow` checklist must include a step instructing the
    developer/agent to inspect component dependencies (e.g. `uv run libspec dependencies`)
    and sort components into topological implementation order before starting test-driven
    development and coding.
    """

    deps = [CliAgentWorkflowCommand, CliDependenciesCommand]


class WorkflowSemverBumpReq(Req):
    """
    The recited `agent-workflow` checklist must include a version bump step instructing the
    developer/agent to bump the project version in `pyproject.toml` according to Semantic
    Versioning (SemVer: `MAJOR.MINOR.PATCH`) using helper tools (e.g., `make bump-patch`,
    `make bump-minor`, `make bump-major`).
    """

    deps = [CliAgentWorkflowCommand]


class CliCompletionCommand(Feat):
    """
    `libspec completion <shell>`
    outputs the shell completion script for the specified shell (bash, zsh, or fish)
    to enable CLI tab completion.
    """

    deps = [SubcommandRegistration]


class CliHelpCommand(Feat):
    """
    `libspec help [<command>]` is a subcommand-flavored alias for the
    `--help` option, so that `uv run libspec help` works exactly like
    `uv run libspec --help`.

    Motivation: `uv run libspec --help` is ambiguous at the shell level —
    `uv` may consume the leading `--help` itself and print `uv run`'s help
    instead of the tool's. A bare `help` word is never intercepted by the
    runner, making it the reliable way to reach libspec's own help text.

    With no argument, it prints the top-level help for the `main` group.
    With a `<command>` argument, it prints that subcommand's help text.
    """

    deps = [SubcommandRegistration, MainCliGroup]


class CliHelpTopLevelParityReq(Req):
    """
    `libspec help` (no arguments) must emit the exact same text that
    `libspec --help` emits — the `main` group's usage line, its docstring,
    the `--version`/`--help` option list, and the full subcommand listing —
    and exit with status code 0.

    Parity is achieved by rendering the help from the *parent* click context
    (`ctx.parent.get_help()`), not by reimplementing or hand-maintaining a
    second copy of the help text, so the two forms can never drift apart as
    subcommands are added or removed.
    """

    deps = [CliHelpCommand]


class CliHelpSubcommandTargetReq(Req):
    """
    `libspec help <command>` must print the help text for that subcommand,
    identically to `libspec <command> --help`, and exit 0.

    The target subcommand is resolved against the `main` group's registered
    command table, and its help is rendered in a child context of the parent
    group context so that the usage line reads `Usage: libspec <command>
    [OPTIONS] ...` rather than naming the `help` command.

    Resolving and rendering the target must not execute the target command's
    callback, must not trigger that command's project guard
    (`spec.utils.LibspecProjectGuard`), and must have no side effects.
    """

    deps = [CliHelpCommand, CwdValidation]


class CliHelpUnknownCommandReq(Req):
    """
    `libspec help <unknown>` must fail the same way an unknown subcommand
    invocation does: print a usage line plus an error naming the unrecognized
    command to stderr, and exit with click's standard usage exit code (2).

    This is implemented by raising `click.UsageError`, so the message shape
    stays consistent with click's own `No such command '<unknown>'.`
    rendering rather than a bespoke error format.
    """

    deps = [CliHelpCommand]


class CliHelpProjectIndependenceReq(Req):
    """
    The `help` command is documentation-only and must work anywhere.

    - It is exempt from `CwdValidation`: it never calls
      `require_libspec_project()` and succeeds outside a libspec project.
    - It never reads or writes the specification store.
    - It does not participate in the self-healing routines gated by
      `CliSelfHealingBypass` (`help` is not in the `main` group's
      heal-on-invoke subcommand set).
    """

    deps = [CliHelpCommand, CwdValidation, CliSelfHealingBypass]


class CliHelpListingSelfInclusionReq(Req):
    """
    Because `help` is a real click command on the `main` group, it appears in
    the `Commands:` listing of the top-level help output with a one-line
    summary (e.g. `help  Show help for libspec or one of its commands.`).
    Its presence in that listing is itself part of the help contract: the two
    entry points to help must be mutually discoverable.
    """

    deps = [CliHelpCommand, CliHelpTopLevelParityReq]


class CliBackwardCompatibility(Req):
    """
    Ensure seamless backward compatibility with all active CLI usages, argument
    orderings, option defaults, and exit codes.
    """

    deps = [SubcommandRegistration]


class CliParameterValidation(Req):
    """
    Implement professional click-based validation and clean parameter types
    (such as click.Path) for paths and directories where applicable.
    """

    deps = [SubcommandRegistration]


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
    - help: Prints top-level or per-command help text.

    The --version option reports the installed package version.
    Help is available either via the `--help` option or via the `help`
    subcommand, which are required to produce identical output.
    """

    deps = [SubcommandRegistration, DiffCommand, CliDependenciesCommand]
