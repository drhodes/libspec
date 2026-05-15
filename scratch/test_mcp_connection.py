import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def verify_connection():
    # Define the server parameters
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "libspec", "mcp"],
        env=None
    )

    print("Connecting to libspec MCP server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            
            # List available tools
            print("\nConnected! Discovering tools...")
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f" - {tool.name}: {tool.description.split('.')[0]}")

if __name__ == "__main__":
    asyncio.run(verify_connection())
