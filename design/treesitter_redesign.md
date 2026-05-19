# [DEPRECATED / SUPERSEDED] Tree-sitter Redesign: Achieving Embedded Polyglot Architecture

> [!WARNING] **ARCHITECTURAL DECISION UPDATE:** As of the design
> meeting on 2026-05-18, the Tree-sitter redesign outlined below has
> been **superseded and abandoned** in favor of a much simpler,
> lightweight spec-side drift detection model. Hashing implementation
> code via Tree-sitter was determined to introduce unnecessary
> complexity that is largely solved by a spec-directed agent workflow.
>
> Please refer to the updated
> [spec_store_resolution.md](file:///usr/backup-working/work/libspec/design/spec_store_resolution.md)
> for the active, production-ready design (utilizing spec docstring
> hashing and simple file/line markers instead).

## 1. Motivation

`libspec` currently relies on `pylsp` and the Language Server Protocol for two
distinct categories of work:

1. **Structural work** — finding the AST node that encloses a `# IMPLEMENTS`
   marker, extracting its boundary for hashing, scanning files for markers.
2. **Semantic navigation** — `search`, `peek`, `usage`, and `symbols` tools that
   agents use for go-to-definition, find-all-references, hover documentation,
   and workspace symbol lookup.

These two categories have very different requirements. Structural work needs
only a parse tree and runs fine without a language server. Semantic navigation
genuinely requires cross-file symbol resolution — something that a parse tree
alone cannot provide.

The goal of this redesign is to eliminate LSP for structural work entirely,
while being explicit about what happens to semantic navigation. The result is a
leaner architecture that removes the process-orchestration overhead for the
common case without lying about what it gives up.

### What LSP costs us (structural work)

- **Monolingual limitation**: `pylsp` is Python-only. Supporting Django templates,
  JavaScript, or Go requires a fleet of independent background language servers.
- **Process orchestration overhead**: launching, health-checking, and proxying
  JSON-RPC across multiple LSP processes for what is essentially "give me the
  AST node boundary at this byte offset."
- **Heavyweight for the task**: LSPs carry type inference, autocompletion,
  and rename machinery that `libspec` never uses for hashing.

### What LSP provides that we must plan for (semantic navigation)

The `peek`, `usage`, and `symbols` tools — used by agents for go-to-definition,
find-all-references, and document structure — rely on cross-file semantic
indexing that Tree-sitter cannot replicate. A design that drops LSP entirely
drops these tools. Section 6 addresses this explicitly.

---

## 2. The Tree-sitter Pivot (Structural Work Only)

For **structural work**, we replace LSP with embedded Tree-sitter. Tree-sitter
is a C-based incremental parser with Python bindings that produces a concrete
syntax tree in milliseconds per file. It requires no background process and
supports dozens of languages through independently installable grammar packages.

### 2.1 Single-Process Architecture

The MCP server runs as a single Python process (`uv run libspec mcp`). When a
file needs structural analysis, the server loads the appropriate Tree-sitter
grammar for that file's language and parses it in-process. No background node
processes, no JSON-RPC, no health checks.

### 2.2 Grammar Installation and Distribution

Tree-sitter grammars are compiled C shared libraries. They are **not** bundled
with `tree-sitter` (the Python package) itself; each language grammar is a
separate optional dependency.

**Required grammar packages** (declared as optional extras in `pyproject.toml`):

```toml
[project.optional-dependencies]
grammars = [
    "tree-sitter-python",
    "tree-sitter-javascript",
    "tree-sitter-html",
    "tree-sitter-go",
    "tree-sitter-css",
]
```

Users install the grammars they need: `uv add libspec[grammars]` for the full
set, or individual packages for specific languages.

**Grammar loading at runtime** uses a registry with graceful fallback:

```python
GRAMMAR_PACKAGES = {
    ".py":   "tree_sitter_python",
    ".js":   "tree_sitter_javascript",
    ".ts":   "tree_sitter_typescript",
    ".html": "tree_sitter_html",
    ".go":   "tree_sitter_go",
    ".css":  "tree_sitter_css",
}

def load_language(ext: str) -> Language | None:
    pkg_name = GRAMMAR_PACKAGES.get(ext)
    if not pkg_name:
        return None
    try:
        mod = importlib.import_module(pkg_name)
        return Language(mod.language())
    except ImportError:
        raise GrammarNotInstalledError(
            f"No Tree-sitter grammar available for '{ext}'. "
            f"Install it with: uv add {pkg_name.replace('_', '-')}"
        )
```

If a file's language has no installed grammar, the server raises a descriptive
error rather than silently falling back to grep.

### 2.3 Path-Based Domain Routing

The server partitions its work by path:

- **Abstract domain** (`<project-root>/spec/*.py`): parsed to extract
  `Ctx`-derived specification classes — Features, Requirements, Directives.
- **Implementation domain** (`<project-root>/**` outside `spec/`): scanned for
  `# IMPLEMENTS: <ref>` markers using Tree-sitter, with the enclosing AST
  node extracted for semantic hashing.

---

## 3. Semantic Hashing: Precise Rules

The purpose of semantic hashing is to detect when the implementation of a
spec component has changed in a meaningful way. The hash must be stable across
reformatting (whitespace, blank lines) but must change when logic changes.

### 3.1 The Hash Input

For a given `# IMPLEMENTS: <ref>` marker, the hash is computed as follows:

1. Parse the file with the appropriate Tree-sitter grammar.
2. Walk the syntax tree to find the comment node containing `IMPLEMENTS: <ref>`.
3. Identify the **enclosing anchor node** (defined in Section 3.2).
4. Serialize the anchor node's syntax tree using a **canonical form** (defined
   in Section 3.3).
5. Hash the canonical form with SHA-256. Store the first 16 hex characters as
   the implementation coordinate.

### 3.2 Enclosing Anchor Node: Explicit Rules Per Case

The "enclosing anchor node" is the innermost node from the following priority
list that contains the marker:

| Priority | Python node type | JS/TS node type | Go node type | HTML node type |
|----------|-----------------|-----------------|--------------|----------------|
| 1 (preferred) | `function_definition` / `async_function_definition` | `function_declaration` / `method_definition` / `arrow_function` | `function_declaration` / `method_declaration` | n/a |
| 2 | `class_definition` | `class_declaration` | `type_spec` | `element` |
| 3 | `module` (entire file) | `program` | `source_file` | `document` |

**Rule**: Walk up the tree from the marker comment node. Take the first ancestor
that appears in the priority list. Priority 1 is preferred; priority 3 (whole
file) is the fallback of last resort and triggers a warning.

**Edge cases with explicit resolution:**

- **Module-level marker** (no enclosing function or class): The anchor is the
  entire `module` / `source_file` node. The server logs a warning:
  `IMPLEMENTS marker at module scope in {file}:{line} — hash covers entire file.
  Consider wrapping the implementation in a function or class.`

- **Marker inside a decorator**: Walk up past the decorator to the
  `function_definition` or `class_definition` that the decorator applies to.
  Decorators are part of that node's subtree in the Tree-sitter grammar.

- **Marker inside a nested class or nested function**: The innermost enclosing
  function or class wins. A method inside a class hashes to the method, not
  the class. This is intentional — see Section 3.4.

- **Marker in an HTML attribute value**: Not permitted. The
  `libspec_implement_component` tool must reject requests to place a marker
  inside an attribute value and instead place it in the nearest enclosing
  `element` node as a comment child.

### 3.3 Canonical Serialization

The canonical form of a node is produced by:

1. Depth-first traversal of the subtree.
2. At each **named** node (non-anonymous in Tree-sitter terms), emit the node
   type followed by a space-separated list of its named children's canonical
   forms, recursively.
3. At each **leaf** node that is:
   - A **comment** node: **skip entirely** (this makes the hash stable across
     comment edits, and ensures the `IMPLEMENTS` marker itself does not affect
     the hash of the logic it annotates).
   - A **string literal**: emit the literal value (whitespace inside strings
     is preserved — changing a string constant changes the hash).
   - Any other leaf: emit the exact text content.
4. Join all emitted tokens with a single space separator.
5. The resulting string is normalized: collapse all runs of whitespace to a
   single space, strip leading and trailing whitespace.

This means:
- Renaming a local variable **does** change the hash (the identifier leaf
  text changes). This is intentional — a rename is a code change.
- Adding or removing blank lines **does not** change the hash (whitespace
  between nodes is not part of named node leaves).
- Reformatting (`black`, `gofmt`) **does not** change the hash for
  whitespace-only changes, but **does** if the formatter changes string
  representations or introduces/removes parentheses that alter the AST shape.
- Editing a comment **does not** change the hash.

**Honesty about precision**: Semantic hashing detects structural code changes,
not logical equivalence. Two implementations with different local variable
names hash differently even if they are logically identical. One
implementation refactored by inlining a helper hashes differently even if the
visible behavior is unchanged. This is the correct trade-off for a drift
detector: it should err toward reporting drift rather than silently missing it.
The claim of "100% precision" in earlier documentation was overstated. The
correct framing is: **the hash is stable across reformatting and comment
edits, and changes whenever the code structure changes**.

### 3.4 Nested Marker Problem: Explicit Resolution

The original whole-file hashing problem — "editing Component B falsely
invalidates Component A" — resurfaces at the AST level when markers are nested.
Example:

```python
class MyService:
    # IMPLEMENTS: spec.services.MyService          ← marker A (class scope)

    def process(self, data):
        # IMPLEMENTS: spec.services.MyService.process  ← marker B (method scope)
        return transform(data)
```

When `process()` changes, the class-level hash (for marker A) also changes
because the class node's subtree has changed. This is unavoidable when using
AST-node-based hashing: a parent node's hash necessarily reflects its children.

**The resolution is a layered hash model**:

- Each `IMPLEMENTS` marker records the hash of its own anchor node (the
  innermost enclosing node per Section 3.2).
- When computing the hash for a class-level marker, child nodes that
  **themselves carry an `IMPLEMENTS` marker** are replaced in the canonical
  serialization with a placeholder token `<IMPLEMENTS:{ref}>` rather than
  their full subtree content.

Concretely, for marker A above, the canonical serialization of `MyService`
treats the `process` method body as an opaque reference rather than serializing
its implementation detail. The class-level hash then captures the class
interface (method signatures, class attributes, docstrings stripped per rule
3.3) without being invalidated by changes inside `process`.

This requires a two-pass scan per file:
1. **Pass 1**: Find all `IMPLEMENTS` markers and their anchor nodes.
2. **Pass 2**: Compute each hash, substituting child anchors with placeholders.

### 3.5 Marker Injection: The `libspec_implement_component` Tool

Agents must not write `IMPLEMENTS` markers by hand. The MCP tool
`libspec_implement_component(ref, target_file, code)` handles marker injection
deterministically.

The tool:

1. **Determines the correct comment syntax** for the target file by inspecting
   the file's Tree-sitter grammar and the byte offset at which the code will be
   inserted. Comment syntax is selected from a per-language, per-context table:

   | Language | Context | Comment syntax |
   |----------|---------|----------------|
   | Python | any | `# IMPLEMENTS: {ref}` |
   | JavaScript / TypeScript | script | `// IMPLEMENTS: {ref}` |
   | HTML | element body | `<!-- IMPLEMENTS: {ref} -->` |
   | HTML | embedded `<script>` | `// IMPLEMENTS: {ref}` |
   | HTML | embedded `<style>` | `/* IMPLEMENTS: {ref} */` |
   | Go | any | `// IMPLEMENTS: {ref}` |
   | CSS | any | `/* IMPLEMENTS: {ref} */` |
   | Django/Jinja template | template block | `{# IMPLEMENTS: {ref} #}` |

   The context is determined by parsing the file and checking the node type
   at the insertion point. For polyglot files (HTML with embedded JS/CSS),
   the Tree-sitter `html` grammar exposes embedded `script_element` and
   `style_element` nodes whose children use the JS/CSS grammars respectively.

2. **Injects the marker** as the first statement inside the target function or
   class body, before any other code.

3. **Verifies** that after injection, parsing the file succeeds and the marker
   node is reachable via the anchor-finding algorithm in Section 3.2. If not,
   it rolls back the injection and returns an error.

The tool guarantees correct syntax and placement. It does not guarantee that
the surrounding code correctly implements the spec — that remains the agent's
responsibility.

---

## 4. Plugin Architecture Migration

The current plugin system hooks into `pylsp`'s pluggy-based plugin manager via
`libspec.pylsp_plugin` as a loader. Under the new architecture, plugins hook
directly into the `libspec` core and are managed by the MCP server.

### 4.1 Plugin Interface

Plugins implement a simple Python protocol:

```python
class LibspecPlugin(Protocol):
    def name(self) -> str: ...
    def supported_languages(self) -> list[str]: ...  # file extensions, e.g. [".py", ".js"]
    def analyze(self, tree: Node, source: bytes, file_path: Path) -> list[Diagnostic]: ...
```

Plugins are discovered from `<project-root>/.libspec/plugins/*.py`, the same
path as before. The loader imports them on server startup and registers them
with the `PluginRegistry`.

### 4.2 From `ast` to Tree-sitter: Honest Migration Notes

The existing `hello_ast` plugin uses Python's `ast` module (via `pylsp`) to
walk Python source trees. Under Tree-sitter, plugins traverse the Tree-sitter
`Node` graph instead.

The key difference is that Tree-sitter query patterns are **not portable across
languages**. Node type names differ per grammar:

| Concept | Python grammar | JavaScript grammar | Go grammar |
|---------|---------------|-------------------|------------|
| Function | `function_definition` | `function_declaration` | `function_declaration` |
| Method | `function_definition` (inside class) | `method_definition` | `method_declaration` |
| Class | `class_definition` | `class_declaration` | `type_spec` |
| Arrow fn | n/a | `arrow_function` | n/a |

A plugin that queries for function definitions across Python and JavaScript
must therefore maintain **one query pattern per grammar**, not a single shared
query. The `supported_languages()` method makes this contract explicit: a
plugin declares which languages it handles, and the registry only invokes it
for matching files.

A cross-language plugin is structured as:

```python
QUERIES = {
    ".py": "(function_definition name: (identifier) @fn-name)",
    ".js": "[(function_declaration name: (identifier) @fn-name) "
            " (method_definition name: (property_identifier) @fn-name)]",
}

class FunctionAuditPlugin:
    def supported_languages(self): return [".py", ".js"]
    def analyze(self, tree, source, file_path):
        ext = file_path.suffix
        query_src = QUERIES[ext]
        lang = load_language(ext)
        query = lang.query(query_src)
        captures = query.captures(tree.root_node)
        # ... process captures
```

This is still far simpler than managing two separate LSP processes, but it is
not the single-query silver bullet that earlier documentation implied.

### 4.3 Plugin Lifecycle and MCP Control

Plugins are instantiated once at server startup. The `libspec_pylsp_plugin` MCP
tool is replaced by `libspec_plugin` with identical parameters
(`plugin_name`, `action`). The implementation no longer sends
`workspace/didChangeConfiguration` over JSON-RPC; instead it directly toggles
an `enabled` flag in the `PluginRegistry`.

---

## 5. What Replaces the `search`, `peek`, `usage`, and `symbols` Tools?

This is the honest part of the design that the original document omitted.

**Tree-sitter cannot replace LSP semantic navigation.** Find-all-references,
go-to-definition, and hover documentation require cross-file symbol resolution
and type information that a parse tree alone does not provide.

The migration plan for each tool:

### 5.1 `symbols` → Tree-sitter (full replacement, no LSP needed)

`symbols` lists the structural outline of a single file (classes, methods,
top-level functions). This is pure structural work — Tree-sitter handles it
completely. The new implementation walks the file's parse tree and emits the
same JSON structure the LSP version returned.

### 5.2 `search` → Hybrid: native spec discovery + Tree-sitter scan (LSP dropped)

The existing `search` implementation already uses `_native_spec_discovery`
(Python `ast`-based) for spec classes and falls back to LSP for general
symbols. The Tree-sitter version replaces both paths:

- Spec classes: replaced by a Tree-sitter scan of `spec/**/*.py` using the
  Python grammar (same result, faster, no process needed).
- General symbols: replaced by a Tree-sitter workspace scan that finds
  `IMPLEMENTS` markers and class/function names by pattern. This loses LSP's
  type-aware ranking but covers the agent's primary use case (finding spec
  refs and their implementations).

Cross-file semantic search (e.g., "find all subclasses of `Ctx`") is not
replicated and is explicitly out of scope.

### 5.3 `peek` → Partial replacement; Python-only LSP retained for deep navigation

`peek` combines hover documentation and go-to-definition. Hover documentation
(docstrings) can be extracted from the parse tree. Go-to-definition cannot —
it requires knowing where a name is *defined*, which requires a symbol index.

**Decision**: `peek` is split into two tools:

- `peek_doc(file_path, line)` — Tree-sitter only. Extracts the docstring of
  the enclosing function or class at the given line. Works for all languages.
- `peek_def(file_path, line, character)` — **Python files only**, keeps the
  LSP backend. Non-Python files return an "unsupported" message rather than
  silently failing.

This means `pylsp` is not fully removed yet. It is retained as a narrow,
Python-only dependency for `peek_def` and `usage`. It is no longer used for
any structural hashing work and no longer needs to support non-Python files.

### 5.4 `usage` → Python-only LSP retained; others unsupported

`usage` (find-all-references) requires a semantic index. It is retained for
Python files via `pylsp` and explicitly unsupported for other languages with
a clear error message. Future work: if a project-level index (e.g.,
[Pyright](https://github.com/microsoft/pyright) or a custom sqlite index) is
added, `usage` can be extended. This is not in scope for this iteration.

### 5.5 Summary Table

| Tool | Before | After |
|------|--------|-------|
| `symbols` | `pylsp` `documentSymbol` | Tree-sitter (full replacement) |
| `search` | `pylsp` + native ast | Tree-sitter (full replacement) |
| `peek_doc` | `pylsp` hover | Tree-sitter (full replacement) |
| `peek_def` | `pylsp` definition | `pylsp`, Python-only (retained) |
| `usage` | `pylsp` references | `pylsp`, Python-only (retained) |
| `pylsp_plugin` | `pylsp` plugin control | Replaced by `libspec_plugin` (Tree-sitter registry) |

The `start_lsp` tool is retained but now documented as optional. It is
auto-started only when `peek_def` or `usage` is called on a Python file. It
is never started for structural hashing work.

---

## 6. Migration Path

The migration is phased to avoid breaking the server while the new
infrastructure is built:

**Phase 1 — Structural hashing** (this PR):
- Add Tree-sitter grammar registry and `load_language()`.
- Implement `find_anchor_node()`, canonical serialization, and the two-pass
  nested-marker hash algorithm.
- Implement `libspec_implement_component` with comment-syntax detection.
- Keep all existing LSP tools unchanged.

**Phase 2 — Tool replacement**:
- Replace `symbols` and `search` with Tree-sitter implementations.
- Split `peek` into `peek_doc` (Tree-sitter) and `peek_def` (LSP, Python-only).
- Migrate plugin system from `pylsp` plugin manager to `PluginRegistry`.
- Add grammar-not-installed error messages throughout.

**Phase 3 — LSP scope reduction**:
- Remove `pylsp` from non-Python code paths entirely.
- Mark `pylsp` as an optional dependency: `uv add libspec[lsp]`.
- Update MCP server instructions to reflect the new tool inventory.

---

## 7. Conclusion

By migrating structural hashing to embedded Tree-sitter, `libspec` eliminates
the LSP process-orchestration overhead for its primary workload — finding,
hashing, and verifying spec implementations across polyglot codebases. The
architecture is honest about what Tree-sitter cannot do: semantic navigation
for Python is retained via a scoped `pylsp` dependency, and cross-language
go-to-definition is explicitly out of scope rather than silently dropped.

The key engineering decisions that distinguish this design from the original
proposal:

- **Grammar distribution is explicit**: grammars are optional extras, not magic.
- **Nested marker hashing is solved**: the two-pass layered hash model prevents
  parent-node hash pollution from child-node changes.
- **Comment syntax detection covers polyglot files**: context is determined from
  the parse tree, not from file extension alone.
- **LSP is reduced, not eliminated**: `peek_def` and `usage` retain `pylsp` for
  Python, rather than dropping the capability silently.
- **Plugin query portability is honest**: per-grammar query patterns are the
  correct model; a single cross-language query is not achievable.
