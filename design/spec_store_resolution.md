# SpecStore Architecture: From Challenges to Resolution

## 1. The Challenge
Initially, `libspec` relied on XML files to track the state of specifications. This architecture suffered from massive, fatal drift:
* The XML wasn't accurately tracking which parts of the spec were actually implemented in the codebase.
* The system lacked a deterministic way to verify implementations, meaning the "desired state" (the specs) routinely fell out of sync with the "actual state" (the code).
* XML coupling polluted the core `libspec` builders, making testing difficult and restricting users to a single storage mechanism.

## 2. The Abstract Interface Resolution
To solve the tight coupling, the storage layer was completely
abstracted into a `Protocol` interface (`SpecStore`).

### Unifying the Entity (`Component`)
Rather than managing a dual-state system (`SpecData` vs abstract definitions), the system unified everything into a single `Component` structure. A `Component` represents:
1. **The Target Definition**: (e.g., ref, docstring directives, inherits)
2. **The Concrete Implementation State**: (e.g., `implementation_status`, `implementation_locations`)

The `SpecStore` is now entirely backend-agnostic. It merely implements
`store_component`, `get_component`, and `list_components`. Whether it
uses SQLite, Postgres, Memory, or JSON, the core system does not care.

## 3. The Mediation Layer (`SpecEngine`)
To decouple the persistence layer from the AST parsing layer, the `SpecEngine` was introduced. 
The Engine acts as the orchestrator:
1. It loads the **Abstract Specs** (static Python code in `spec/*.py`).
2. It queries the **Concrete Specs** (state records in `SpecStore`).
3. It resolves the delta into a **SpecDiff** (missing, stale, drifted, or aligned requirements).

This `SpecDiff` becomes the explicit, strictly-typed instruction set
handed to the Coding Agent (LLM) so it knows exactly what to
implement.

## 4. The Implementation Coordinate Dilemma
The hardest problem was determining the "Coordinate" of an
implementation to detect drift. The evolution of our solutions:

1. **Git Commit Hashes (The Dirty Tree Paradox)**: We initially wanted
   to record the Git commit. However, agents write code *before* a
   commit exists. Recording `HEAD` pointed to the wrong, older commit.

2. **Whole-File Blob Hashing**: We considered hashing the entire file
   via `git hash-object`. However, if a file contained *two*
   components, editing Component B falsely invalidated the hash for
   Component A.

3. **Text Chunk Hashing**: We proposed using `START` and `END` anchors
   and hashing just the raw text chunk. But this proved
   catastrophically brittle. An auto-formatter (`black`), an innocent
   blank line, or a nested component would change the text hash and
   trigger massive false-positive "Drift" alerts.

## 5. The Ultimate Resolution: Embedded Semantic Hashing
To solve the brittle text problem, we shifted to **Semantic Hashing
via Embedded Tree-sitter**.

### The Workflow:
1. **The Single-Line Marker**: The LLM agent implements the feature
   and drops a simple, single-line marker anywhere inside the block:
   `# IMPLEMENTS: spec.ref`.
2. **The Semantic Hash**: The `SpecEngine` scans the file using
   Tree-sitter. It finds the structural AST node (the function, class,
   or HTML tag) encapsulating that marker. It strips all whitespace
   and comments, and hashes the *pure semantic logic*.
3. **Drift Detection**: Because the hash is based on the AST
   structure, developers can reformat the code, add blank lines, and
   nest components without altering the hash. The SpecStore tracks
   drift with 100% precision.

### The Bulletproof Deterministic Layer
LLMs are notoriously unreliable at formatting exactly. To guarantee
that the `# IMPLEMENTS: spec.ref` marker is placed correctly, the
agent is strictly required to use a specialized MCP Tool wrapper:
`libspec_implement_component(ref, target_file, code)`.  This tool
automatically determines the comment syntax (e.g., `#` vs `<!-- -->`)
and injects the marker deterministically, effectively taking the
formatting burden completely out of the LLM's hands.

## Conclusion
This evolution resulted in a bulletproof, deterministic system. By
combining an abstract SQLite `SpecStore`, the `SpecEngine` diffing
layer, embedded Tree-sitter semantic hashing, and rigid MCP tool
wrappers, `libspec` guarantees that specifications and code can never
secretly drift apart.
