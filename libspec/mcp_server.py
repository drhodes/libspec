"""
MCP Server entry point for libspec.
"""

from mcp.server.fastmcp import FastMCP
import os
import sys
import subprocess



mcp = FastMCP("libspec")




@mcp.tool()
def libspec_build(spec_file: str = None, output_dir: str = "spec-build") -> str:
    """
    Build the XML spec from a Python spec file.
    
    Args:
        spec_file: Path to the main python spec file. If omitted, attempts to auto-discover in the current directory.
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


@mcp.tool()
def libspec_diff(build_dir: str = "spec-build") -> str:
    """
    Diff the two latest XML specs in a build directory.
    
    Args:
        build_dir: Directory containing XML spec files (default is 'spec-build')
    """
    cmd = [sys.executable, "-m", "libspec.cli", "diff", build_dir]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout or "No changes detected."
    except subprocess.CalledProcessError as e:
        return f"Error running diff:\n{e.stderr}\n{e.stdout}"


def main():
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
