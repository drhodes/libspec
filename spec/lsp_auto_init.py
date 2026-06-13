"""
Specification for automatic LSP initialization in the MCP server.
"""

from .err import Feat, Req


class LspAutoInit(Req):
    """
    The libspec MCP server must eliminate manual lifecycle management for the
    background LSP server.

    The current requirement that a user or agent must manually call
    `libspec_start_lsp` before performing semantic searches creates unnecessary
    cognitive load and friction in agentic workflows.
    """


class LazyLspStart(Feat):
    """
    Any tool that depends on the background LSP process must perform a "lazy
    check" on the LSP state.

    1. If the LSP process is not running, the tool must automatically invoke
    the initialization sequence before proceeding. 2. The initialization must
    use sensible defaults (e.g., searching for a `spec/` directory or using the
    current workspace root). 3. This process must be transparent to the caller.
    """


class ConcurrentInitSafety(Req):
    """
    The auto-initialization logic must be thread-safe or guarantee atomicity to
    prevent multiple rapid tool calls from spawning redundant LSP processes.
    """


class DiagnosticInitialization(Feat):
    """
    If auto-initialization fails (e.g., due to missing environment dependencies
    like `pylsp`), the failure must follow the Story-Driven Error pattern
    defined in `Err`.

    The error message should:
    - Identify that an auto-start was attempted.
    - Explain exactly why it failed (e.g., "pylsp not found in PATH").
    - Provide a clear remediation step (e.g., "Run `uv add --dev
      python-lsp-server`").
    """
