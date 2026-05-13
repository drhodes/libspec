'''
MCP server tool specifications.
'''

from .err import Feat, Req


class McpServer(Req):
    '''The libspec MCP server exposes tools over the stdio transport
    using the FastMCP library, making libspec capabilities available to any
    MCP-compatible LLM client (e.g. Claude Desktop, opencode).

    The server is launched via `libspec mcp` or `libspec-mcp` (both are
    registered as entry points in pyproject.toml).

    Tools are stateless wrappers around the same logic as the CLI subcommands.
    '''


class McpBuildTool(Feat):
    '''The `libspec_build` MCP tool builds an XML spec from
    a Python spec file.

    Parameters:
    - spec_file (str, optional): Path to the main Python spec file. If
      omitted, the tool auto-discovers candidates by globbing for *_spec.py,
      spec.py, and spec/*_spec.py in the current working directory.
    - output_dir (str, default "spec-build"): Output directory.

    The tool delegates to `libspec build` via subprocess and returns the
    combined stdout or a formatted error message on failure.
    '''


class McpDiffTool(Feat):
    '''The `libspec_diff` MCP tool diffs the two latest XML specs in a
    build directory.

    Parameters:
    - build_dir (str, default "spec-build"): Directory containing XML files.

    The tool delegates to `libspec diff` via subprocess. Returns the diff
    output or "No changes detected." on success, or a formatted error
    message on failure.
    '''

    
class LspTool(Feat):
    '''Ensure the background LSP process is initialized before
    execution.  If the LSP is not running, the tool should trigger an
    automatic, transparent start-up sequence.
    '''


class McpStartLspTool(LspTool):
    '''The `libspec_start_lsp` MCP tool launches a Language Server
    specialized for specification-driven development.

    The LSP server is built on `pylsp` and uses a custom `libspec` plugin.
    Crucially, this tool implements a delegation model: while `pylsp`
    handles AST and standard Python features, the `libspec` plugin
    delegates semantic requirement validation and docstring rendering
    "up" to the active coding agent.

    Parameters:
    - root_dir (str, default "spec"): The root directory of the specification.
    '''
    feature_name = "McpStartLspTool"


class McpSearchTool(LspTool):
    '''The `libspec_search` tool is the primary discovery tool for
    the agent. It performs a workspace-wide semantic search for components
    by name.

    Parameters:
    - query (str): The name of the component (class, method, or variable).

    Returns a list of semantic matches with their file paths and line
    numbers, allowing the agent to jump directly to definitions without
    using grep.
    '''
    feature_name = "McpSearchTool"


class McpPeekTool(LspTool):
    '''The `libspec_peek` tool provides immediate context and
    location for a component at a specific position.

    Parameters:
    - file_path (str): Path to the file.
    - line (int): 0-indexed line number.
    - character (int): 0-indexed character offset.

    Returns a combined response containing:
    1. The rendered docstring/requirement text.
    2. The type information.
    3. The file path and line number of the definition.
    '''
    feature_name = "McpPeekTool"


class McpUsageTool(LspTool):
    '''The `libspec_usage` tool finds all semantic references to a
    component, allowing the agent to understand how it is used.

    Parameters:
    - file_path (str): Path to the file.
    - line (int): 0-indexed line number.
    - character (int): 0-indexed character offset.

    Returns a list of usage locations, optimized for navigation.
    '''
    feature_name = "McpUsageTool"


class McpSymbolsTool(LspTool):
    '''The `libspec_symbols` tool provides a structural overview of
    a file's contents.

    Parameters:
    - file_path (str): Path to the file.

    Returns a hierarchical list of components (classes, methods) to help
    the agent orient itself within a new file.
    '''
    feature_name = "McpSymbolsTool"


class McpConfigTool(Feat):
    '''The `libspec_mcp_config` MCP tool enables project-local registration
    of the libspec MCP server.

    It detects the project environment and updates the specified agent's
    local configuration to include the `libspec` MCP server using
    `uv run libspec mcp` as the execution command.

    Parameters:
    - agent (str): The name of the coding agent (e.g., "antigravity", "claude", "vscode").
    - project_root (str, default "."): The root directory of the project.

    Returns a success message with the path to the updated config file.
    '''
    feature_name = "McpConfigTool"


class McpAutoDiscover(Req):
    '''The libspec MCP server must support automatic discovery of its
    environment to ensure a zero-config experience.

    When initialized, the server should detect:
    1. The presence of a `spec/` directory.
    2. The project's local python environment (via uv/venv).
    3. The appropriate LSP configuration based on the project structure.

    This ensures that tools like `libspec_start_lsp` work out-of-the-box
    without requiring manual path configurations.
    '''


class AgentConfig(Req):
    '''Base requirement for project-local agent configuration.
    All agents must be configured to use `uv run libspec mcp` to
    ensure they utilize the project's local environment.
    '''


class AntigravityConfig(AgentConfig):
    '''Antigravity configuration requirement.
    The registration must be written to `.gemini/antigravity/mcp_config.json` in the
    project root to enable seamless project-local discovery.
    '''


class OpenCodeConfig(AgentConfig):
    '''OpenCode configuration requirement.
    OpenCode registration should follow the standard project-local
    MCP manifest format.
    '''


class ClaudeConfig(AgentConfig):
    '''Claude Desktop configuration requirement.
    Since Claude primarily uses a global config, the tool should provide
    the exact JSON snippet for the user to append to their
    `claude_desktop_config.json`.
    '''
