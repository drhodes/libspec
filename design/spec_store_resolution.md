# SpecStore Architecture

## 1. The Challenge

Initially, `libspec` relied on XML files to track the state of specifications. This architecture had two distinct problems that are worth separating, because they have different solutions.

The first problem was **XML coupling**: the storage format was baked into the core `libspec` builders, making testing difficult and restricting consumers to a single representation. This is a real problem worth solving.

The second problem was **drift detection**: the system tried to determine whether implementation code had silently diverged from its spec. This led to an increasingly complex series of hashing schemes — git commit hashes, whole-file blob hashes, text chunk hashes, and finally Tree-sitter semantic hashes — each solving a real brittleness in the previous approach.

After working through the full design, we concluded that drift detection in its original form — hashing implementation code via Tree-sitter to detect code changes — is not worth the complexity it imposes. In a spec-directed agent workflow the spec diff is the input to every session, and the elaborate code-side coordinate machinery was solving a failure mode that the workflow mostly prevents. A lighter form of drift detection does return in this design, scoped correctly to the spec side rather than the code side. See Section 4.

## 2. The Storage Abstraction

The XML coupling problem is solved by the `SpecStore` protocol: a backend-agnostic interface with three operations.

```python
class SpecStore(Protocol):
    def store_component(self, component: Component) -> None: ...
    def get_component(self, ref: str) -> Component | None: ...
    def list_components(self) -> list[Component]: ...
```

The core `libspec` builders depend only on this protocol. Whether the backing store is SQLite, an in-memory dict for tests, or something else, the compiler and engine do not care.

### The Component

A `Component` is the unified entity for a single specification node:

```python
@dataclass
class Component:
    ref: str
    docstring: str
    is_template: bool
    inherits: list[str]        # parent refs in MRO order
```

`Component` is purely about the spec itself. Implementation tracking is handled separately by the `Implemented` table.

## 3. The Mediation Layer: SpecEngine

The `SpecEngine` decouples the spec source (Python classes in `spec/*.py`) from the persistence layer (`SpecStore`). It acts as the orchestrator:

1. Compile the abstract specs from `spec/*.py` into `Component` objects, resolving MRO and rendering Jinja templates.
2. Persist the compiled `Component` objects to the `SpecStore` under a new `Build`.
3. Query the `Implemented` table for the current build to determine which refs have been claimed as implemented.
4. Reconcile claims against the filesystem: for each `Implemented` record, verify the marker is present at the recorded file and line, and that the embedded spec hash still matches the current spec.
5. Produce a `SpecDiff` as the instruction set handed to the coding agent.

The `SpecDiff` has three states:

- **missing**: no `Implemented` record exists and no marker was found.
- **implemented**: an `Implemented` record exists, the marker is present at the recorded location, and the spec hash matches.
- **unverified**: an `Implemented` record exists but either the marker is not found at the recorded location, or the spec hash has changed since the implementation was recorded — indicating the spec evolved after the implementation was written.

## 4. The SQLite Backend

The production `SpecStore` implementation uses SQLite via Peewee.

### Why SQLite

The spec graph is English prose and inheritance relationships — no code, no hashes, no binary data. At the scale of thousands of spec nodes per project, SQLite needs no tuning and queries stay under a millisecond. The database file is small enough to ship as a release artifact without concern for size.

The database is **not committed to the repository**. It is a derived artifact, compiled from `spec/*.py` source files the same way a `.pyc` is compiled from `.py`. Committing it would recreate the divergence problem that motivated the original XML redesign. Instead, the database is built on demand — `libspec build` creates or refreshes it, and `libspec mcp` builds it automatically on first run if absent.

### Append-Only Build Log

Rather than mutating existing records, every rebuild creates a new `Build` row and inserts fresh `Spec` and `Edge` rows under that build. The current state of the spec graph is always the latest build. The previous state is the second-to-latest. A diff between any two builds is a query.

This makes the database an append-only log. There are no update conflicts, no partial writes to reason about. Every compiler run is a clean insert.

All old builds are preserved in the relational database, maintaining a complete, append-only history of every specification compile. This enables querying or diffing between any historical checkpoints.

### Schema

```python
class Build(Model):
    created_at = DateTimeField(default=datetime.utcnow)
    session_id = TextField(null=True)

    class Meta:
        database = db


class Spec(Model):
    build = ForeignKeyField(Build, backref="specs", on_delete="CASCADE")
    ref = TextField()
    docstring = TextField(null=True)
    is_template = BooleanField(default=False)

    class Meta:
        database = db
        indexes = ((("build", "ref"), True),)  # unique per build


class Edge(Model):
    build = ForeignKeyField(Build, backref="edges", on_delete="CASCADE")
    child_ref = TextField()
    parent_ref = TextField()
    position = IntegerField()  # MRO order

    class Meta:
        database = db


class Implemented(Model):
    build = ForeignKeyField(Build, backref="implemented", on_delete="CASCADE")
    ref = TextField()
    file = TextField()
    line = IntegerField()
    spec_hash = TextField()    # hash of spec docstring at time of implementation
    session_id = TextField(null=True)

    class Meta:
        database = db
        indexes = ((("build", "ref"), True),)  # unique per build
```

`Spec` is purely about the spec itself. `Implemented` is a separate first-class table recording when and where an agent claimed to have satisfied a spec.

### Inheritance Edges

The `Edge` table stores inheritance relationships as flat rows, not as a recursive structure. The compiler resolves the full MRO when it walks `spec/*.py` and writes one row per parent-child pair. There is no need for recursive SQL traversal — the database stores what the compiler already computed.

Reading the full ancestry of a spec is a simple query:

```python
(Edge
    .select()
    .where(
        Edge.build == current_build,
        Edge.child_ref == ref
    )
    .order_by(Edge.position))
```

### The Spec Hash and Marker Format

When an agent implements a component via the `libspec_implement_component` MCP tool, the tool computes a hash of the spec's current docstring and embeds it in the marker:

```python
# IMPLEMENTS: spec.services.MyService a3f8c2d1
```

The hash is computed from the spec side — stable, structured English prose in the database — not from the implementation code. This makes hashing trivial: no AST parsing, no canonical serialization, no Tree-sitter. Just a hash of the docstring string.

The `Implemented` table records the same hash at insert time. When the `SpecEngine` reconciles, it recomputes the hash from the current spec row and compares it to the stored value. A mismatch means the spec evolved after the implementation was written — the `unverified` state in the `SpecDiff`. The agent is told the spec changed and the implementation needs review, but no code parsing is involved.

This is drift detection scoped to the right side of the relationship. The question it answers is not "did the code change" but "did the spec change after the code was written against it" — which is the question that actually matters in a spec-directed workflow.

### The Build as Distribution Artifact

Because the database contains the full spec graph in queryable form — English docstrings, inheritance relationships, implementation records — it can be shipped as a distribution artifact for downstream consumers. A project that depends on an upstream spec library can receive the upstream `.db` file as part of a package release and query it directly, without needing the upstream Python source. The `SpecEngine` treats a received upstream database as a read-only `SpecStore` and merges it with the local spec graph at diff time.

## 5. Centralized Team Backend (Postgres)

For teams, distributing local SQLite `.db` files or recompiling on demand individually introduces synchronization friction. To solve this, `libspec` supports a centralized, shared remote database option using **PostgreSQL**.

### Seamless Configuration
Thanks to Peewee's database abstraction, transitioning from SQLite to PostgreSQL requires zero changes to the schema or logic. The exact same models (`Build`, `Spec`, `Edge`, `Implemented`) map natively to PostgreSQL. 

The storage engine switches connection parameters dynamically based on environment variables (e.g., `LIBSPEC_DATABASE_URL="postgresql://user:password@host/dbname"`).

### Real-Time Team Synchronization
With a shared PostgreSQL instance, team synchronization becomes seamless:
1. **CI/CD Build Synchronization**: When a pull request is merged to `main`, the CI pipeline runs the `libspec compile` builder. This compiles the static `spec/*.py` files and inserts the new build directly into the central PostgreSQL instance.
2. **Instant Local Visibility**: Developers running `libspec mcp` locally do not need to compile the spec themselves or worry about local file divergence. Their client immediately pulls the latest active build and `Implemented` claims from the shared Postgres database.
3. **Co-existent Upstream SQLite Merges**: The `SpecEngine` still supports merging read-only upstream SQLite `.db` files (received from package managers) side-by-side with the active remote team PostgreSQL database, resolving them into a single, cohesive specification diff.

## 6. Conclusion

The SpecStore architecture resolves the original XML coupling problem cleanly. The storage protocol decouples the compiler from the persistence layer. The SQLite backend via Peewee provides a queryable, versionable spec graph at negligible complexity cost, while the seamless PostgreSQL option unlocks real-time, zero-friction synchronization for entire development teams.

Drift detection returns in a lightweight, well-scoped form: the spec hash embedded in the marker answers the one question that matters — did the spec change after this implementation was written? It requires no code parsing, no AST traversal, and no coordination machinery. The complexity is proportionate to the problem.
