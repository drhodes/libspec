import os
import json
from libspec.lsp_client import LspClient
from pathlib import Path

def to_uri(file_path):
    return Path(os.path.abspath(file_path)).as_uri()

def explore():
    lsp = LspClient()
    root_dir = "spec"
    root_uri = to_uri(root_dir)
    
    print(f"--- Starting LSP for {root_dir} ---")
    lsp.start(root_uri)
    
    target_file = "spec/mcp.py"
    uri = to_uri(target_file)
    
    print(f"--- Fetching symbols for {target_file} ---")
    res = lsp.send_request("textDocument/documentSymbol", {
        "textDocument": {"uri": uri}
    })
    
    symbols = res.get("result", [])
    print(f"Found {len(symbols)} symbols.")
    for s in symbols:
        kind = s.get("kind")
        name = s.get("name")
        line = s.get("range", {}).get("start", {}).get("line", 0) + 1
        print(f"[{kind}] {name} at line {line}")

    print("\n--- Searching for 'LspTool' ---")
    res = lsp.send_request("workspace/symbol", {"query": "LspTool"})
    matches = res.get("result", [])
    for m in matches:
        print(f"Match: {m.get('name')} in {m.get('location', {}).get('uri')}")

    lsp.stop()

if __name__ == "__main__":
    explore()
