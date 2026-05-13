'''
MCP server tool specifications.
'''

from .err import Feat, Req


class McpServer(Req):
    '''The libspec MCP server exposes three tools over the stdio transport
    using the FastMCP library, making libspec capabilities available to any
    MCP-compatible LLM client (e.g. Claude Desktop, opencode).

    The server is launched via `libspec mcp` or `libspec-mcp` (both are
    registered as entry points in pyproject.toml).

    Tools are stateless wrappers around the same logic as the CLI subcommands.
    '''


class McpBuildTool(Feat):
    '''The `libspec_build` MCP tool builds an XML spec and source map from
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


class McpQueryTool(Feat):
    '''The `libspec_query` MCP tool queries the source map for LLM context.

    Parameters:
    - query (str, optional): Component name or keyword to search for.
    - source_map (str, optional): Path to source_map.json. Defaults to
      ./spec-build/source_map.json relative to the current working directory.
    - list_all (bool, default False): If True, list all component names.

    The tool reads the source map JSON directly (no subprocess) and delegates
    to `get_query_results()` from the CLI module, returning a formatted string
    suitable for LLM consumption.
    '''
