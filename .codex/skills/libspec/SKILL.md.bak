---
name: libspec-codex
description: Navigation and specification tools for Codex
license: MIT
---

# Codex + Libspec

Your environment is configured to use the **Libspec** MCP server, providing advanced navigation and specification-driven development tools.

## Available Tools

### 🔍 libspec_search
- **Purpose**: Semantic search for specification components (Requirements, Features, Scenarios).
- **Usage**: When you need to understand the "why" behind a piece of code or find where a requirement is implemented.
- **Example**: `libspec_search(query="user authentication")`

### 👁️ libspec_peek
- **Purpose**: Retrieve definitions, docstrings, and type hints for a symbol without reading the entire file.
- **Usage**: Use this for quick orientation before diving into the implementation.
- **Example**: `libspec_peek(file_path="auth.py", line=42, character=10)`

### 🏗️ libspec_symbols
- **Purpose**: List all structural components (classes and methods) in a specific file.
- **Usage**: Orientation in large or unfamiliar source files.
- **Example**: `libspec_symbols(file_path="models.py")`

### 🔗 libspec_usage
- **Purpose**: Find all semantic references to a component across the entire project.
- **Usage**: **Mandatory** before refactoring or deleting shared code to perform impact analysis.
- **Example**: `libspec_usage(file_path="utils.py", line=12, character=5)`

## Workflow
1. **Search**: Find relevant specifications.
2. **Peek**: Understand the definition and documentation.
3. **Usage**: Check dependencies before modifying.
4. **Implement**: Write code that satisfies the spec.