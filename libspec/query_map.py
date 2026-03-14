"""Deprecated: use `libspec query` instead."""

# This module's logic has moved to libspec.cli.
# Kept as a shim so that `python -m libspec.query_map` still works.

from libspec.cli import cmd_query, main as _cli_main
import argparse
import sys


def main():
    """Backwards-compatible entry point — delegates to `libspec query`."""
    # Prepend 'query' so the unified CLI parser is satisfied
    sys.argv.insert(1, 'query')
    _cli_main()


if __name__ == "__main__":
    main()
