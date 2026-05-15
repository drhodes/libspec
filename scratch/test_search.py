import os
import json
from libspec.mcp_server import start_lsp, search

def test():
    root_dir = os.getcwd()
    print(f"Starting LSP in {root_dir}...")
    start_lsp(root_dir)
    
    print("Searching for 'Ctx'...")
    res = search("Ctx")
    print(f"Result type: {type(res)}")
    print(f"Result length: {len(res)}")
    print(f"Result: '{res}'")
    
    try:
        data = json.loads(res)
        print(f"Parsed {len(data)} results.")
    except Exception as e:
        print(f"Parse failed: {e}")

if __name__ == "__main__":
    test()
