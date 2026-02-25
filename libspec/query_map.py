import json
import argparse
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Query the source map for token-efficient LLM context.")
    parser.add_argument("source_map", help="Path to source_map.json")
    parser.add_argument("query", nargs="?", help="Component name or keyword to search for")
    parser.add_argument("--list", action="store_true", help="List all components")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.source_map):
        print(f"Error: {args.source_map} does not exist.")
        sys.exit(1)
        
    try:
        with open(args.source_map, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading source map: {e}")
        sys.exit(1)
        
    if args.list:
        components = sorted(list(set(item.get("component", "Unknown") for item in data)))
        print(f"Components ({len(components)}):")
        for c in components:
            print(f"  {c}")
        return
        
    if not args.query:
        print("Please provide a query or use --list.")
        sys.exit(1)
        
    query = args.query.lower()
    results = []
    
    for item in data:
        component = item.get("component", "")
        if query in component.lower():
            results.append(item)
            
    if not results:
        print(f"No results found for '{args.query}'.")
        return
        
    for idx, item in enumerate(results):
        if idx > 0:
            print("-" * 40)
        print(f"Component: {item.get('component', 'Unknown')}")
        
        py_spec = item.get("python_spec")
        if py_spec:
            print(f"Python Spec: {py_spec.get('file', '')}:{py_spec.get('start_line', '')}-{py_spec.get('end_line', '')} ({py_spec.get('target', '')})")
            
        xml_spec = item.get("xml_spec")
        if xml_spec:
            print(f"XML Spec:    {xml_spec.get('file', '')}:{xml_spec.get('line', '')}")
            
        gen_code = item.get("generated_code", [])
        if gen_code:
            print("Generated Code:")
            for gc in gen_code:
                print(f"  - {gc.get('file', '')}:{gc.get('line', '')}")

if __name__ == "__main__":
    main()
