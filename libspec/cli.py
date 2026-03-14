"""
libspec - unified CLI for spec-driven development.

Subcommands:
  build  <spec_file.py> -o <output_dir>   Build XML spec + source_map.json
  diff   <build_dir>                       Diff the two latest XML specs
  query  <source_map.json> [term]          Query source map for LLM context
"""

import argparse
import importlib.util
import inspect
import json
import os
import sys


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def cmd_build(args):
    from libspec.spec import Spec, module_specs

    spec_file = os.path.abspath(args.spec_file)
    if not os.path.exists(spec_file):
        print(f"Error: {spec_file} does not exist.")
        sys.exit(1)

    # Add spec file's directory to sys.path so relative imports work
    spec_dir = os.path.dirname(spec_file)
    if spec_dir not in sys.path:
        sys.path.insert(0, spec_dir)

    # Dynamically import the spec file
    module_name = os.path.splitext(os.path.basename(spec_file))[0]
    loader = importlib.util.spec_from_file_location(module_name, spec_file)
    module = importlib.util.module_from_spec(loader)
    module.__name__ = module_name
    try:
        loader.loader.exec_module(module)
    except Exception as e:
        print(f"Error loading spec file: {e}")
        sys.exit(1)

    # First try: find an explicit Spec subclass (write_xml + source map built-in)
    explicit_spec = None
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ == module_name and issubclass(obj, Spec) and obj is not Spec:
            explicit_spec = obj
            break

    output_dir = args.output or "spec-build"

    if explicit_spec:
        explicit_spec().write_xml(output_dir)
        return

    # Fallback: auto-discover all Ctx subclasses via module_specs()
    specs = module_specs(module)
    if not specs:
        print(f"Error: No spec classes found in {spec_file}.")
        sys.exit(1)

    # Build an ad-hoc Spec that wraps the discovered components
    class _ModuleSpec(Spec):
        def modules(self_inner):
            return [module]

    _ModuleSpec().write_xml(output_dir)


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

def cmd_diff(args):
    from libspec.spec_diff import generate_patch
    generate_patch(args.build_dir)


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

def _do_query(data, query, list_all):
    if list_all:
        components = sorted(set(item.get("component", "Unknown") for item in data))
        print(f"Components ({len(components)}):")
        for c in components:
            print(f"  {c}")
        return

    if not query:
        print("Please provide a query term or use --list.")
        sys.exit(1)

    q = query.lower()
    results = [item for item in data if q in item.get("component", "").lower()]

    if not results:
        print(f"No results found for '{query}'.")
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


def cmd_query(args):
    if not os.path.exists(args.source_map):
        print(f"Error: {args.source_map} does not exist.")
        sys.exit(1)

    try:
        with open(args.source_map, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading source map: {e}")
        sys.exit(1)

    _do_query(data, args.query, args.list)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="libspec",
        description="libspec — spec-driven development toolkit",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # build
    p_build = subparsers.add_parser("build", help="Build XML spec and source map from a Python spec file")
    p_build.add_argument("spec_file", help="Path to the Python spec file (must contain a Spec subclass)")
    p_build.add_argument("-o", "--output", metavar="DIR", default="spec-build",
                         help="Output directory (default: spec-build)")
    p_build.set_defaults(func=cmd_build)

    # diff
    p_diff = subparsers.add_parser("diff", help="Diff the two latest XML specs in a build directory")
    p_diff.add_argument("build_dir", help="Directory containing XML spec files")
    p_diff.set_defaults(func=cmd_diff)

    # query
    p_query = subparsers.add_parser("query", help="Query the source map for LLM context")
    p_query.add_argument("source_map", help="Path to source_map.json")
    p_query.add_argument("query", nargs="?", help="Component name or keyword to search for")
    p_query.add_argument("--list", action="store_true", help="List all components")
    p_query.set_defaults(func=cmd_query)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
