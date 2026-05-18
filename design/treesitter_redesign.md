# Tree-sitter Redesign: Achieving Embedded Polyglot Architecture

## 1. The Motivation
Historically, `libspec` relied heavily on the Language Server Protocol (LSP) and plugins for `pylsp` to achieve semantic understanding of the codebase. While powerful, this created several architectural bottlenecks:
* **Monolingual Limitation**: `pylsp` is bound to Python. Supporting Django HTML templates, Javascript, or Go required launching and orchestrating a fleet of independent background language servers.
* **Process Orchestration Nightmare**: The MCP Server had to act as a massive proxy router, managing process lifecycles, forwarding JSON-RPC requests, and aggregating responses across multiple LSPs.
* **Heavyweight**: LSPs carry massive overhead (autocompletion, type inference, hover semantics) when `libspec` primarily just needs lightning-fast structural boundaries (ASTs) for hashing and parsing.

## 2. The Tree-sitter Pivot
We are completely ripping out the background LSP orchestration model. The `libspec` MCP Server will now directly embed **Tree-sitter**—a highly efficient, C-based incremental parsing library.

This transforms the MCP Server from a "router" into a **Self-Contained, High-Performance Polyglot Engine**.

### 2.1 Single-Process Architecture
The server runs entirely within a single Python process at the project root (`uv run libspec mcp`). There are no background node.js processes or standalone language servers. When a file needs to be evaluated, the server dynamically loads the appropriate Tree-sitter grammar (`tree-sitter-python`, `tree-sitter-html`, etc.) and evaluates the file in milliseconds.

### 2.2 Path-Based Domain Routing
Because the single process controls the entire workspace, it cleanly partitions its responsibilities by path:
- **Abstract Domain (`<project-root>/spec/*.py`)**: Files in this directory are parsed to extract the theoretical Abstract Specifications (Features, Requirements, Directives).
- **Implementation Domain (`<project-root>/**`)**: Files outside the spec directory are scanned for `# IMPLEMENTS: <ref>` markers. The surrounding AST node is extracted for semantic drift detection.

## 3. Plugin Migration
The current `pylsp` plugin architecture (e.g., the `hello_ast` diagnostic plugin) will be migrated to the new Tree-sitter framework.

### 3.1 From `ast` to Tree-sitter Traversals
Plugins that previously hooked into the Python standard library `ast` module (via `pylsp`) will now implement Tree-sitter query languages or standard AST node traversals. 
- **Advantage**: Tree-sitter provides a unified AST structure. A single plugin can theoretically query for "Function Definitions" across Python, JS, and Go using a standard structural query, drastically simplifying plugin development.

### 3.2 State and Lifecycle
Plugins will be instantiated and managed directly by the `libspec` core rather than the `pylsp` plugin manager, allowing the MCP server to dynamically toggle, configure, and interrogate plugins via unified MCP tools without dealing with JSON-RPC plugin configurations.

## 4. Conclusion
By migrating to embedded Tree-sitter, `libspec` achieves true, lightweight polyglot support. It eliminates external dependencies, drastically reduces latency, and unlocks universal semantic hashing—providing the ultimate foundation for the new `SpecStore` architecture.
