"""
MCP Server entry point for libspec.
"""

from mcp.server.fastmcp import FastMCP
import os
import json
import sys
import subprocess

from libspec.cli import get_query_results

mcp = FastMCP("libspec")

@mcp.tool()
def libspec_query(query: str = None, source_map: str = None, list_all: bool = False) -> str:
    """
    Query the libspec source map for LLM context.
    
    Args:
        query: Component name or keyword to search for
        source_map: Path to the source_map.json file (defaults to ./spec-build/source_map.json)
        list_all: List all components in the source map
    """
    if not source_map:
        source_map = os.path.join(os.getcwd(), "spec-build", "source_map.json")
    if not os.path.exists(source_map):
        return f"Error: source map '{source_map}' does not exist."
    try:
        with open(source_map, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return f"Error reading source map: {e}"

    return get_query_results(data, query, list_all)


@mcp.tool()
def libspec_build(spec_file: str = None, output_dir: str = "spec-build") -> str:
    """
    Build the XML spec and source map from a Python spec file.
    
    Args:
        spec_file: Path to the Python spec file. If omitted, attempts to auto-discover in the current directory.
        output_dir: Output directory (default is 'spec-build')
    """
    if not spec_file:
        import glob
        candidates = glob.glob(os.path.join(os.getcwd(), "*_spec.py")) + glob.glob(os.path.join(os.getcwd(), "spec.py")) + glob.glob(os.path.join(os.getcwd(), "spec", "*_spec.py"))
        if not candidates:
            return "Error: Could not auto-discover a spec_file. Please provide one."
        spec_file = candidates[0]
        
    cmd = [sys.executable, "-m", "libspec.cli", "build", spec_file, "-o", output_dir]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"Successfully built {spec_file} to {output_dir}.\n{res.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Error building spec:\n{e.stderr}\n{e.stdout}"


def main():
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
