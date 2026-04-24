"""
libspec - unified CLI for spec-driven development.

Subcommands:
  init                             Initialize a new spec directory
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
# init
# ---------------------------------------------------------------------------

def cmd_init(args):
    spec_dir = os.path.abspath("spec")
    if os.path.exists(spec_dir):
        print(f"Error: Directory '{spec_dir}' already exists. Bailing.")
        sys.exit(1)
        
    os.makedirs(spec_dir)
    
    with open(os.path.join(spec_dir, "__init__.py"), "w") as f:
        pass
        
    with open(os.path.join(spec_dir, "main_spec.py"), "w") as f:
        f.write('"""\n')
        f.write('main spec\n')
        f.write('"""\n\n')
        f.write('from libspec import Spec\n')
        f.write('from . import app\n\n')
        f.write('class MainSpec(Spec):\n')
        f.write('    def modules(self):\n')
        f.write('        return [app]\n\n')
        f.write('if __name__ == "__main__":\n')
        f.write('    MainSpec().write_xml("spec-build")\n')

    with open(os.path.join(spec_dir, "app.py"), "w") as f:
        f.write('"""\n')
        f.write('Features and requirements\n')
        f.write('"""\n\n')
        f.write('from .err import Feat, Req\n\n')
        f.write('class App(Req):\n')
        f.write('    \'\'\'This program should emit the\n')
        f.write('    string "Hello, world!" to the terminal.\n')
        f.write('    \'\'\'\n\n')
        f.write('class CmdLine(Feat):\n')
        f.write('    \'\'\'\n')
        f.write('    This program does not take any command line arguments.\n')
        f.write('    \'\'\'\n')

    with open(os.path.join(spec_dir, "err.py"), "w") as f:
        f.write('"""\n')
        f.write('Error and requirement base classes.\n')
        f.write('"""\n\n')
        f.write('from libspec import Ctx, Feature, Requirement\n\n')
        f.write('class Err(Ctx):\n')
        f.write('    \'\'\'It is important that error handling be done excellently. If a\n')
        f.write('    function can fail, then it needs to do so in the most elegant way\n')
        f.write('    possible. Error reporting, handling, exceptions and all aspects\n')
        f.write('    of failure must be taken to extreme. It should be possible to\n')
        f.write('    understand the program by reading the error messages.\n')
        f.write('    \'\'\'\n\n')
        f.write('# Use multiple inheritance to endow Feature and Requirement specs with\n')
        f.write('# disciplined error handling guidance from above.\n\n')
        f.write('class Feat(Err, Feature): pass\n')
        f.write('class Req(Err, Requirement): pass\n')
        
    print(f"Initialized empty spec directory in {spec_dir}")

# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def cmd_build(args):
    from libspec.spec import Spec, module_specs

    spec_file = os.path.abspath(args.spec_file)
    if not os.path.exists(spec_file):
        print(f"Error: {spec_file} does not exist.")
        sys.exit(1)

    # Calculate module name relative to the current working directory, if possible.
    # This allows relative imports (e.g. from . import app) to work correctly when
    # the spec is in a subdirectory (like spec/main_spec.py).
    cwd = os.getcwd()
    if spec_file.startswith(cwd):
        rel_path = os.path.relpath(spec_file, cwd)
        module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, '.')
        root_dir = cwd
    else:
        # Fallback: just use the spec's directory
        root_dir = os.path.dirname(spec_file)
        module_name = os.path.splitext(os.path.basename(spec_file))[0]
        
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    # Import the module dynamically. Since we mapped the file path to a 
    # dotted module name (e.g. 'spec.main_spec'), python's built-in import 
    # system correctly sets __package__ and handles relative imports.
    import importlib
    try:
        module = importlib.import_module(module_name)
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

def get_query_results(data, query, list_all):
    lines = []
    if list_all:
        components = sorted(set(item.get("component", "Unknown") for item in data))
        lines.append(f"Components ({len(components)}):")
        for c in components:
            lines.append(f"  {c}")
        return "\n".join(lines)

    if not query:
        return "Please provide a query term or use --list."

    q = query.lower()
    results = [item for item in data if q in item.get("component", "").lower()]

    if not results:
        return f"No results found for '{query}'."

    for idx, item in enumerate(results):
        if idx > 0:
            lines.append("-" * 40)
        lines.append(f"Component: {item.get('component', 'Unknown')}")

        py_spec = item.get("python_spec")
        if py_spec:
            lines.append(f"Python Spec: {py_spec.get('file', '')}:{py_spec.get('start_line', '')}-{py_spec.get('end_line', '')} ({py_spec.get('target', '')})")

        xml_spec = item.get("xml_spec")
        if xml_spec:
            lines.append(f"XML Spec:    {xml_spec.get('file', '')}:{xml_spec.get('line', '')}")

        gen_code = item.get("generated_code", [])
        if gen_code:
            lines.append("Generated Code:")
            for gc in gen_code:
                lines.append(f"  - {gc.get('file', '')}:{gc.get('line', '')}")
    return "\n".join(lines)


def _do_query(data, query, list_all):
    res = get_query_results(data, query, list_all)
    if res == "Please provide a query term or use --list.":
        print(res)
        sys.exit(1)
    print(res)


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

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new spec directory")
    p_init.set_defaults(func=cmd_init)

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
