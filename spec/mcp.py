"""
MCP server tool specifications.
"""

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


class McpServerInstructions(Feat):
    """
    Global guidance provided to the LLM via the MCP `instructions` capability.
    """


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


class McpListComponentsTool(Feat):
    """
    The `libspec_list_components` MCP tool lists all components in a specification.

    Parameters:
    - commit (str, optional): The Git reference (SHA, branch, tag) to load components from.
    """


class McpShowComponentTool(Feat):
    """
    The `libspec_show_component` MCP tool shows details for a component.

    Parameters:
    - component_ref (str): The FQN of the component.
    - commit (str, optional): The Git reference (SHA, branch, tag) to load the component from.
    """




class McpListDependenciesTool(Feat):
    """
    The `list_dependencies` MCP tool retrieves declared dependencies.

    Parameters:
    - commit (str, optional): Target Git commit/ref (defaults to the active/latest version).
    """


class LspTool(Feat):
    """
    Ensure the background LSP process is initialized before execution.
    """


class McpStartLspTool(LspTool):
    """
    The `libspec_start_lsp` MCP tool launches a Language Server specialized for
    specification-driven development.
    """

    feature_name = "McpStartLspTool"


class McpSearchTool(LspTool):
    """
    The `libspec_search` tool is the primary discovery tool for the agent. It
    performs a workspace-wide semantic search for components by name.
    """

    feature_name = "McpSearchTool"


class McpPeekTool(LspTool):
    """
    The `libspec_peek` tool provides immediate context and location for a
    component at a specific position.
    """

    feature_name = "McpPeekTool"


class McpUsageTool(LspTool):
    """
    The `libspec_usage` tool finds all semantic references to a component,
    allowing the agent to understand how it is used.
    """

    feature_name = "McpUsageTool"


class McpSymbolsTool(LspTool):
    """
    The `libspec_symbols` tool provides a structural overview of a file's
    contents.
    """

    feature_name = "McpSymbolsTool"


class McpPylspPluginTool(LspTool):
    """
    The `libspec_pylsp_plugin` tool allows enabling or disabling pylsp plugins
    dynamically.
    """

    feature_name = "McpPylspPluginTool"


class McpSetPylspSettingTool(LspTool):
    """
    The `libspec_set_pylsp_plugin_setting` tool allows dynamic tuning of plugin
    parameters over LSP.
    """

    feature_name = "McpSetPylspSettingTool"


class McpConfigTool(Feat):
    """
    The `libspec_mcp_config` MCP tool enables project-local registration of the
    libspec MCP server.
    """

    feature_name = "McpConfigTool"


class AgentConfigTool(Feat):
    """
    The `agent_config` MCP tool enables configuration of project-local coding
    agents by invoking their native MCP command line utilities.
    """

    feature_name = "AgentConfigTool"


class McpAgentList(Feat):
    """
    The agent configuration tool must support listing all available agent
    configuration strategies.
    """


class McpAutoDiscover(Req):
    """
    The libspec MCP server must support automatic discovery of its environment
    to ensure a zero-config experience.
    """


class AgentConfig(Req):
    """
    Base requirement for project-local agent configuration.
    """


class AgentSkillInstallation(Feat):
    """
    During agent configuration, the libspec skill must be installed.
    """

    feature_name = "AgentSkillInstallation"


class AgentSkillDriftDetection(Req):
    """
    Drift detection on startup.
    """


class SkillVersionValidation(Feat):
    """
    Validation behavior and auto-healing of outdated skill files.
    """

    feature_name = "SkillVersionValidation"


class AntigravityConfig(AgentConfig):
    """
    Antigravity configuration requirement.
    """


class GeminiConfig(AgentConfig):
    """
    Gemini CLI configuration requirement.
    """


class OpenCodeConfig(AgentConfig):
    """
    OpenCode configuration requirement.
    """


class ClaudeConfig(AgentConfig):
    """
    Claude Desktop configuration requirement.
    """


class CopilotConfig(AgentConfig):
    """
    GitHub Copilot configuration requirement.
    """


class CodexConfig(AgentConfig):
    """
    Codex configuration requirement.
    """


# =========================================================================
# 7. Scheduler MCP Integration
# =========================================================================


class McpSchedulerIntegration(Feat):
    """
    The scheduler's priority queue, active worker tracking, and micro-patch
    synchronization must be exposed to autonomous agents as FastMCP tools and
    resources.

    Dynamic Loading:
    The MCP server must dynamically detect and register scheduler tools and
    resources if the sibling package `libspec-scheduler` is present in the
    execution environment.
    """


class McpInitSchedulerTool(Feat):
    """
    MCP tool to initialize a scheduling session.

    Parameters:
    - `snapshot_id` (str, default `"HEAD"`): The build snapshot ID or HEAD state.

    Behavior:
    Constructs the dependency DAG and returns a unique `session_id`.
    """


class McpRequestTaskTool(Feat):
    """
    MCP tool to request/pop the next available READY task from the queue.

    Parameters:
    - `session_id` (str): Active scheduler session ID.
    - `subagent_id` (str): Identifier of the requesting worker agent.

    Behavior:
    Pops the highest priority READY task, leases it to the worker, and returns
    its specification details, docstring, and implementation context.
    """


class McpReportTaskStatusTool(Feat):
    """
    MCP tool to report completion status of a leased task.

    Parameters:
    - `session_id` (str): Active scheduler session ID.
    - `subagent_id` (str): Identifier of the worker agent.
    - `component_ref` (str): FQN of the completed component.
    - `status` (str): Task execution status (`SUCCESS` or `FAILED`).

    Behavior:
    On SUCCESS, merges the subagent's changes, registers the implementation claim, and marks the node as IMPLEMENTED in the DAG.
    """


class McpPublishMicroPatchTool(Feat):
    """
    MCP tool to publish incremental code changes.

    Parameters:
    - `session_id` (str): Active scheduler session ID.
    - `subagent_id` (str): Identifier of the worker agent.
    - `file_path` (str): Path to the modified file.
    - `patch_diff` (str): Unified diff string of the changes.
    - `parent_patch_id` (str, optional): ID of the parent patch this builds upon.
    """


class McpGetMicroPatchesTool(Feat):
    """
    MCP tool to fetch new patches since a given synchronization boundary.

    Parameters:
    - `session_id` (str): Active scheduler session ID.
    - `last_synced_patch_id` (str, optional): The last patch ID successfully applied.
    """


class McpSchedulerDagResource(Feat):
    """
    MCP Resource at `libspec://scheduler/{session_id}/dag` returning a live JSON representation of the dependency DAG and task states.
    """


class McpActiveWorkersResource(Feat):
    """
    MCP Resource at `libspec://scheduler/{session_id}/active_workers` returning active subagent task leases and timeouts.
    """


class McpPatchLogResource(Feat):
    """
    MCP Resource at `libspec://scheduler/{session_id}/patch_log` returning a chronological feed of all published micro-patches.
    """


class McpAgentWorkflowTool(Feat):
    """
    The `agent_workflow` MCP tool recites the standard developer agent workflow.

    Parameters:
    - `agent` (str, optional): Target agent platform (e.g. antigravity, claude).
    - `prefix` (str, optional): Explicit MCP tool prefix.
    """
