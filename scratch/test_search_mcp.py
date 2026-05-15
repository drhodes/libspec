import os
import json
from libspec.mcp_server import search

def test():
    print("Searching for 'McpServer'...")
    res = search("McpServer")
    print(f"Result: {res}")

if __name__ == "__main__":
    test()
