import asyncio
import os
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def get_spec_classes():
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "libspec", "mcp"],
        env=None
    )

    spec_py_path = os.path.abspath("libspec/spec.py")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 1. Start LSP
            print("Starting LSP via MCP...")
            await session.call_tool("libspec_start_lsp", {"root_dir": os.getcwd()})
            
            # 2. Get Symbols
            print(f"Retrieving symbols for {spec_py_path}...")
            result = await session.call_tool("libspec_symbols", {"file_path": spec_py_path})
            
            # Parse result
            symbols = json.loads(result.content[0].text)
            
            # Filter for classes (SymbolKind 5 is Class)
            # Or just list all top-level names if hierarchical
            print("\nSpec Class Definitions Found:")
            for sym in symbols:
                # SymbolKind 5 is Class in LSP
                if sym.get("kind") == 5:
                    print(f" [Class] {sym['name']}")

if __name__ == "__main__":
    asyncio.run(get_spec_classes())
