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
    
    Instructions:
    The server must provide global usage instructions (Server Instructions) 
    to the LLM during initialization to guide its behavior.
    '''


class McpServerInstructions(Feat):
    '''Global guidance provided to the LLM via the MCP `instructions` capability.
    
    The instructions must:
    1. Guide the LLM to prefer LSP-based tools (`search`, `peek`, `symbols`, `usage`) 
       over generic `grep` when analyzing the codebase for semantic understanding.
    2. Explain that `search` combines native spec discovery with LSP 
       symbol search.
    3. Instruct the LLM to use `peek` for definitions and hover info 
       instead of reading full files when looking for specific component logic.
    4. Mention that the server auto-initializes the background LSP 
       process on the first relevant tool call.
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
    If `list_agents` is True, returns a formatted list of all supported 
    agent names instead.
    '''
    feature_name = "McpConfigTool"


class McpAgentList(Feat):
    '''The agent configuration tool must support listing all available 
    agent configuration strategies.
    
    This allows users to discover supported agents (e.g., "antigravity", 
    "copilot", "codex") without referring to external documentation.
    
    The list must be:
    1. Alphabetically sorted.
    2. Formatted for easy CLI reading.
    '''


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
    
    Backups:
    To prevent data loss during configuration updates, the system must 
    create a backup of any existing configuration file before performing 
    a mutation. The backup should:
    1. Only be created if the configuration file already exists.
    2. Use the naming convention `<original_filename>.bak`.
    3. Be overwritten on subsequent updates (only the immediate previous 
       state is preserved).
    '''


class AntigravityConfig(AgentConfig):
    '''Antigravity configuration requirement.
    The registration must be written to `.gemini/antigravity/mcp_config.json` in the
    project root to enable seamless project-local discovery.
    '''


class OpenCodeConfig(AgentConfig):
    '''OpenCode configuration requirement.
    OpenCode registration must be written to `.opencode/opencode.json`
    in the project root.
    '''


class ClaudeConfig(AgentConfig):
    '''Claude Desktop configuration requirement.
    Since Claude primarily uses a global config, the tool should provide
    the exact JSON snippet for the user to append to their
    `claude_desktop_config.json`.
    '''


class CopilotConfig(AgentConfig):
    '''GitHub Copilot configuration requirement.
    The registration must be written to `.copilot/mcp.json` in the
    project root.
    '''


class CodexConfig(AgentConfig):
    '''Codex configuration requirement.
    
    Codex must be able to discover and launch the libspec MCP server from the 
    project workspace using the correct Codex configuration format.
    
    The project must load MCP configuration from `.codex/config.toml` in the 
    project root, or from `~/.codex/config.toml` when the configuration 
    is user-scoped.
    
    The MCP server must be declared as a TOML table named `mcp_servers.libspec`.
    
    The configuration must contain:
    ```toml
    [mcp_servers.libspec]
    command = "uv"
    args = ["run", "libspec", "mcp"]
    cwd = "<project-root>"
    ```
    
    Behavior:
    1. Create `.codex/` if it does not already exist.
    2. Read any existing `.codex/config.toml` file.
    3. Preserve unrelated settings already present in that file.
    4. Add or replace only the `mcp_servers.libspec` entry.
    5. Write valid TOML, not JSON.
    6. Use `uv run libspec mcp` with the repository root as `cwd`.
    '''
