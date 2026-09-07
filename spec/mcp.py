"""
MCP server tool specifications.
"""

from .commands import UnifiedLogCommand
from .core import SpecBase
from .dependencies import (
    DependencyGraphVisualizationFeat,
    ReverseDependencyAnalysisFeat,
    TopologicalImplementationOrderingFeat,
)
from .diff import DiffEngine, GitRevisionCompilation
from .err import Feat, Req


class McpServer(Req):
    """
    The libspec MCP server exposes tools over the stdio transport using the
    FastMCP library, making libspec capabilities available to any MCP-
    compatible LLM client (e.g. Claude Desktop, opencode).

    The server is launched via `libspec mcp` or `libspec-mcp`.

    Tools are stateless wrappers around the same logic as the CLI subcommands.

    Instructions:
    The server must provide global usage instructions (Server Instructions) to
    the LLM during initialization to guide its behavior.
    """

    deps = [SpecBase, DiffEngine]


class McpServerInstructions(Feat):
    """
    Global guidance provided to the LLM via the MCP `instructions` capability.
    """

    deps = [McpServer]


class McpDiffTool(Feat):
    """
    The `libspec_diff` MCP tool diffs specifications natively.

    If no commit parameters are provided, it compiles the live specification files
    on-the-fly and diffs them against HEAD.

    Parameters:
    - commit_a (str, optional): First Git reference (SHA, branch, tag).
    - commit_b (str, optional): Second Git reference (SHA, branch, tag).
    - verbose (bool, default False): Include granular unified diffs of component docstrings.
    - very_verbose (bool, default False): Include full structured semantic diff.
    """

    deps = [McpServer, DiffEngine]


class McpLogTool(Feat):
    """
    The `libspec_log` MCP tool retrieves the Git commit history of the specifications.

    Parameters:
    - all_commits (bool, default False): If True, retrieve all repository commits bypassing
      the `spec/` path filter and pagination limits.

    Implementation:
    This tool must follow `spec.commands.UnifiedCommandPattern` by wrapping the core
    library function and propagating the `all_commits` option directly to `spec.commands.UnifiedLogCommand`.
    """

    deps = [McpServer, UnifiedLogCommand]


class McpListComponentsTool(Feat):
    """
    The `libspec_list_components` MCP tool lists all components in a specification.

    Parameters:
    - commit (str, optional): The Git reference (SHA, branch, tag) to load components from.
    """

    deps = [McpServer, SpecBase]


class McpShowComponentTool(Feat):
    """
    The `libspec_show_component` MCP tool shows details for a component.

    Parameters:
    - component_ref (str): The FQN of the component.
    - commit (str, optional): The Git reference (SHA, branch, tag) to load the component from.
    """

    deps = [McpServer, SpecBase]


class McpListDependenciesTool(Feat):
    """
    The `list_dependencies` MCP tool retrieves declared dependencies.

    Parameters:
    - commit (str, optional): Target Git commit/ref (defaults to the active/latest version).
    - format (str, optional): Output format ('text', 'mermaid', 'dot', 'html'). Defaults to 'text'.
    - rdeps (bool, optional): If True, computes reverse dependencies (downstream dependents). Defaults to False.
    - component (str, optional): Optional component ref to scope dependencies or reverse dependencies.
    """

    deps = [
        McpServer,
        TopologicalImplementationOrderingFeat,
        DependencyGraphVisualizationFeat,
        ReverseDependencyAnalysisFeat,
    ]


class McpSearchTool(Feat):
    """
    The `libspec_search` tool is the primary discovery tool for the agent. It
    performs a workspace-wide search for components by name.
    """

    feature_name = "McpSearchTool"
    deps = [McpServer, SpecBase]


class McpPeekTool(Feat):
    """
    The `libspec_peek` tool provides immediate context and location for a
    component at a specific position.
    """

    feature_name = "McpPeekTool"
    deps = [McpServer, GitRevisionCompilation]


class McpUsageTool(Feat):
    """
    The `libspec_usage` tool finds references to a component,
    allowing the agent to understand how it is used.
    """

    feature_name = "McpUsageTool"
    deps = [McpServer]


class McpSymbolsTool(Feat):
    """
    The `libspec_symbols` tool provides a structural overview of a file's
    contents.
    """

    feature_name = "McpSymbolsTool"
    deps = [McpServer, SpecBase]


class McpConfigTool(Feat):
    """
    The `libspec_mcp_config` MCP tool enables project-local registration of the
    libspec MCP server.
    """

    feature_name = "McpConfigTool"
    deps = [McpServer]


class AgentConfig(Req):
    """
    Base requirement for project-local agent configuration.
    """

    deps = [McpServer]


class AgentConfigTool(Feat):
    """
    The `agent_config` MCP tool enables configuration of project-local coding
    agents by invoking their native MCP command line utilities.
    """

    feature_name = "AgentConfigTool"
    deps = [AgentConfig]


class McpAgentList(Feat):
    """
    The agent configuration tool must support listing all available agent
    configuration strategies.
    """

    deps = [AgentConfig]


class McpAutoDiscover(Req):
    """
    The libspec MCP server must support automatic discovery of its environment
    to ensure a zero-config experience.
    """

    deps = [AgentConfig]


class AgentSkillInstallation(Feat):
    """
    During agent configuration, the libspec skill must be installed.
    """

    feature_name = "AgentSkillInstallation"
    deps = [AgentConfig]


class AgentSkillDriftDetection(Req):
    """
    Drift detection on startup.
    """

    deps = [AgentSkillInstallation]


class SkillVersionValidation(Feat):
    """
    Validation behavior and auto-healing of outdated skill files.
    """

    feature_name = "SkillVersionValidation"
    deps = [AgentSkillInstallation]


class AgentConfigDelegatesToHarnessReq(Req):
    """
    Each concrete `AgentConfig.configure()` registers the libspec MCP server
    by invoking that harness's own native command-line mechanism (e.g.
    `claude mcp add`, `gemini mcp add`) rather than hand-authoring or
    guessing that harness's private config file schema. The harness owns how
    it wires up its own MCP servers; libspec only ever triggers that native
    mechanism and otherwise leaves the harness's own config files untouched.
    """

    deps = [AgentConfig]


class AgentConfigCliAbsentFallbackReq(Req):
    """
    If a harness's native CLI is not present on the host, `configure()` must
    not fall back to writing that harness's config file directly. Instead it
    reports clear, human-readable instructions naming the command or config
    snippet the user would need to add themselves, leaving the harness's own
    config files untouched.
    """

    deps = [AgentConfigDelegatesToHarnessReq]


class AgentConfigTestIsolationReq(Req):
    """
    Automated tests must never shell out to a real coding-agent CLI. Every
    `AgentConfig.configure()` that calls `subprocess.run` to register MCP
    (Claude, Gemini, Codex, Copilot, Antigravity) mutates the developer's
    real global agent configuration on success; if that CLI happens to be
    installed on the machine running tests, an unmocked test run mutates it
    for real. Test suites exercising `cmd_init`, `check_and_heal_skills`, or
    any `AgentConfig.configure()` must patch `subprocess.run` within
    `libspec.agent_config` (not the global `subprocess` module, which
    unrelated code such as the git-backed diff engine legitimately needs) to
    simulate every agent CLI being absent.
    """

    deps = [AgentConfigDelegatesToHarnessReq]


class AgentConfigDocumentedSchemaExceptionReq(Req):
    """
    `AgentConfigDelegatesToHarnessReq` targets guessed or unofficial config
    schemas, not a harness's genuinely documented, first-class configuration
    surface. When a harness provides no native CLI for MCP registration at
    all, and instead expects integrators to edit its own published config
    file format directly, writing that file is the correct primary
    mechanism for `configure()`, not a violation — provided the written
    schema is verified against that harness's current upstream docs rather
    than assumed from an earlier or unrelated harness's format.
    """

    deps = [AgentConfigDelegatesToHarnessReq]


class AntigravityConfig(AgentConfig):
    """
    Antigravity configuration requirement.

    Complies with `AgentConfigDelegatesToHarnessReq`: registers via
    `antigravity --add-mcp` only, never hand-writes `mcp_config.json`.
    """

    deps = [AgentConfig, AgentConfigDelegatesToHarnessReq]


class GeminiConfig(AgentConfig):
    """
    Gemini CLI configuration requirement.

    Complies with `AgentConfigDelegatesToHarnessReq`: registers via
    `gemini mcp add` only, never hand-writes `settings.json`.
    """

    deps = [AgentConfig, AgentConfigDelegatesToHarnessReq]


class OpenCodeConfig(AgentConfig):
    """
    OpenCode configuration requirement.

    Audited against current OpenCode docs: `opencode mcp add` is an
    interactive-only wizard with no scriptable/non-interactive form, so it
    cannot be driven via `subprocess.run`. OpenCode's own docs name editing
    `opencode.json` directly (a `type`/`command`/optional-`environment` entry
    under the `mcp` key) as the documented alternative configuration method.
    Writing `opencode.json` directly is therefore compliant under
    `AgentConfigDocumentedSchemaExceptionReq`, not a violation of
    `AgentConfigDelegatesToHarnessReq` — re-audit if OpenCode ever ships a
    non-interactive `mcp add` form.
    """

    deps = [AgentConfig, AgentConfigDelegatesToHarnessReq]


class ClaudeConfig(AgentConfig):
    """
    Claude Desktop configuration requirement.
    """

    deps = [AgentConfig]


class CopilotConfig(AgentConfig):
    """
    GitHub Copilot configuration requirement.

    Currently writes `.github/mcp.json` unconditionally before even
    attempting `copilot mcp add`, so a successful CLI registration is
    shadowed by a redundant hand-authored file. Must comply with
    `AgentConfigDelegatesToHarnessReq` and
    `AgentConfigCliAbsentFallbackReq`: attempt the CLI first, and only
    report (never write) the manual `mcp.json` snippet when the CLI is
    absent or fails.
    """

    deps = [AgentConfig, AgentConfigDelegatesToHarnessReq]


class CodexConfig(AgentConfig):
    """
    Codex configuration requirement.

    Currently writes `.codex/config.toml` unconditionally before even
    attempting `codex mcp add`, the same shadowing bug as `CopilotConfig`.
    Must comply with `AgentConfigDelegatesToHarnessReq` and
    `AgentConfigCliAbsentFallbackReq`: attempt the CLI first, and only
    report (never write) the manual `config.toml` snippet when the CLI is
    absent or fails.
    """

    deps = [AgentConfig, AgentConfigDelegatesToHarnessReq]


# =========================================================================
# 7. Agent Workflow MCP Tool
# =========================================================================


class McpAgentWorkflowTool(Feat):
    """
    The `agent_workflow` MCP tool recites the standard developer agent workflow.

    Parameters:
    - `agent` (str, optional): Target agent platform (e.g. antigravity, claude).
    - `prefix` (str, optional): Explicit MCP tool prefix.
    """

    deps = [McpServer]
