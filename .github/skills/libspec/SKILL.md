---
name: libspec-copilot
description: Navigation and specification tools for GitHub Copilot
license: MIT
---

# GitHub Copilot + Libspec

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

## Dev Workflow
1. **Edit Spec**: Edit/define the requirements/features in the specification files. **Always decompose broad requirements into granular, single-responsibility requirement classes (e.g. `HelpCommandReq`, `SnapshotsCommandReq`) rather than using monolithic requirement blocks to ensure first-class specification footprinting.**
2. **Build Spec (MANDATORY BEFORE CODING)**: You **must absolutely** run a spec build using the `uv run libspec build <path_to_spec>.py` command to compile and register the latest specification snapshot before starting to write or modify any implementation code.
3. **Diff Spec (MANDATORY BEFORE CODING)**: You **must absolutely** run a spec diff using the `uv run libspec diff` command to identify specification drift and review mutations/dependencies before coding begins.
4. **Implement**: Only after successfully building and diffing the spec, write implementation code that satisfies the specification.
5. **Test**: Write comprehensive unit tests for the newly implemented code.
6. **Run Tests**: Verify code correctness using the python test runner.
7. **Author a git message and present to user**