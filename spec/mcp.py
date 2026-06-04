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


class McpSnapshotTool(Feat):
    """
    The `libspec_snapshot` MCP tool compiles a Python spec file to a new snapshot
    in the SpecStore.

    Parameters:
    - spec_file (str, optional): Path to the main Python spec file.
    - output_dir (str, default "spec-build"): Output directory for legacy XML output if requested.
    """


class McpDiffTool(Feat):
    """
    The `libspec_diff` MCP tool diffs two snapshots natively.

    Parameters:
    - snapshot_a (str, optional): First snapshot (supports relative indices like #1 or hex hash).
    - snapshot_b (str, optional): Second snapshot (supports relative indices like #0 or hex hash).
    - verbose (bool, default False): Include granular unified diffs of component docstrings.
    - very_verbose (bool, default False): Include full structured semantic diff.
    """


class McpListSnapshotsTool(Feat):
    """
    The `libspec_list_snapshots` MCP tool lists all recorded snapshots in the database.
    """


class McpListComponentsTool(Feat):
    """
    The `libspec_list_components` MCP tool lists all components in a snapshot.

    Parameters:
    - snapshot_id (str, optional): The explicit snapshot hash/ID (relative index is NOT supported).
    """


class McpShowComponentTool(Feat):
    """
    The `libspec_show_component` MCP tool shows details for a component.

    Parameters:
    - component_ref (str): The FQN of the component.
    - snapshot_id (str, optional): The explicit snapshot hash/ID (relative index is NOT supported).
    """


class McpLinkSnapshotTool(Feat):
    """
    The `libspec_link_snapshot` MCP tool links a snapshot to a VCS revision.

    Parameters:
    - snapshot_id (str): The explicit snapshot hash/ID (relative index is NOT supported).
    - vcs (str): The VCS type (e.g. "git").
    - revision (str): The VCS revision/commit hash.
    - metadata (dict, optional): Additional metadata key-value pairs.
    """


class McpCompactStoreTool(Feat):
    """
    The `libspec_compact_store` MCP tool compacts the SpecStore database log.

    Parameters:
    - dry_run (bool, default False): Whether to dry-run the compaction.
    """


class McpDeleteSnapshotTool(Feat):
    """
    The `libspec_delete_snapshot` MCP tool permanently deletes a historical snapshot.

    Parameters:
    - snapshot_id (str): The explicit snapshot hash/ID.
    """


class McpRestoreSnapshotTool(Feat):
    """
    The `libspec_restore_snapshot` MCP tool restores a deleted historical snapshot.

    Parameters:
    - snapshot_id (str): The explicit snapshot hash/ID.
    """


class McpGetLogTool(Feat):
    """
    The `libspec_get_log` MCP tool retrieves the transaction log ledger.
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
