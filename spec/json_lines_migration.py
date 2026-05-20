"""
Specification for universal SpecStore migration and JsonLinesStore as the
new default backend.
"""

from .err import Feat, Req


# =========================================================================
# 1. JsonLines as Default Backend
# =========================================================================


class JsonLinesDefaultBackend(Feat):
    """
    JsonLinesSpecStore replaces SQLiteSpecStore as the default active backend
    for all local libspec workflows.

    The migration must:
    - Store the JSONL transaction log at `.libspec/libspec.jsonl` by default.
    - Activate JsonLinesSpecStore when `LIBSPEC_DATABASE_URL` is unset.
    - Support a `jsonl://` URL scheme in `LIBSPEC_DATABASE_URL` for explicit
      opt-in with a custom file path.
    - Retain full backward compatibility: `sqlite://` and `postgresql://`
      schemes continue to resolve to their respective backends unchanged.
    """


class GetStoreResolutionOrder(Req):
    """
    The `get_store()` factory must resolve the active backend in this strict
    precedence order:

    - `postgresql://` or `postgres://` → PostgresSpecStore
    - `sqlite://` → SQLiteSpecStore
    - `jsonl://` → JsonLinesSpecStore at the specified path
    - Unset → JsonLinesSpecStore at `.libspec/libspec.jsonl` (new default)
    """


class JsonLinesEnvScheme(Req):
    """
    The `jsonl://` URL scheme must be supported in `LIBSPEC_DATABASE_URL` to
    allow explicit opt-in to JsonLinesSpecStore with a custom file path.

    The scheme must:
    - Strip the `jsonl://` prefix to resolve the filesystem path.
    - Treat the remainder as an absolute or workspace-relative path to the
      `.jsonl` log file.
    - Raise `SpecStoreIOError` if the resolved directory is not writable.
    """


# =========================================================================
# 2. Universal Store Migrator
# =========================================================================


class UniversalStoreMigration(Feat):
    """
    The libspec platform must provide a single, universal migration utility
    that transfers the complete history from any SpecStore backend to any
    other SpecStore backend.

    The intermediate representation is the in-memory domain object graph
    already defined by the SpecStore protocol: `Snapshot`, `Component`, and
    `Implemented`. No custom serialization format or adapter is required.
    Because every backend already implements the full read and write halves
    of the SpecStore protocol, migration is always M→memory→N, giving N
    exporters and N importers rather than N² direct converters.
    """


class MigrateFunction(Req):
    """
    A single top-level function `migrate(source, target)` must perform the
    complete transfer.

    The function must:
    - Accept any two objects satisfying the `SpecStore` protocol as `source`
      and `target`.
    - Call `source.list_snapshots()` to obtain all historical snapshots in
      chronological order (oldest first).
    - For each snapshot, call `source.get_components_for_snapshot(snap)` and
      `source.list_implemented(snap)` to read all associated records into
      memory as plain `Component` and `Implemented` domain objects.
    - Write each snapshot to `target` via `target.store_snapshot(components,
      git_commit=snap.git_commit, created_at=snap.created_at)`.
    - Write each implementation claim via `target.store_implemented(claim)`.
    - Raise `SpecStoreIOError` and abort cleanly if any read or write step
      fails, leaving the target in the state it was in before the failure.
    - Return a summary dict: `{"migrated": int, "skipped": int}` reflecting
      how many snapshots were newly written versus already present (idempotent
      no-ops).
    """


class MigrateFunctionIdempotency(Req):
    """
    `migrate(source, target)` must be safely re-runnable without producing
    duplicate data.

    Idempotency is guaranteed because:
    - Each target backend's `store_snapshot` implementation skips writing when
      the incoming `master_hash` already exists in the store.
    - The `migrate` function must count such skips and include them in its
      returned summary.
    """


class MigrateFunctionOrdering(Req):
    """
    Migration must preserve strict chronological ordering in the target store.

    The ordering must:
    - Process snapshots in the exact order returned by
      `source.list_snapshots()`, which is guaranteed oldest-first by the
      SpecStore protocol.
    - Write component and claim records for each snapshot as a single
      contiguous block before advancing to the next snapshot.
    """


# =========================================================================
# 3. CLI Subcommand
# =========================================================================


class MigrateCLICommand(Req):
    """
    A new CLI subcommand `libspec migrate <source_url>` must be exposed to
    drive `migrate(source, target)` from the command line.

    The command must:
    - Accept a single positional argument `<source_url>` using the same URL
      scheme conventions as `LIBSPEC_DATABASE_URL` (`sqlite://`, `jsonl://`,
      `postgresql://`) to construct the source `SpecStore` via `get_store()`.
    - Resolve the target store from the ambient `get_store()` (i.e., the
      currently configured active backend).
    - Refuse to run if source and target resolve to the same file or
      database, raising a clear user-facing error.
    - Print per-snapshot progress lines to stdout indicating the snapshot ID,
      component count, claim count, and outcome (`migrated` or `skipped`).
    - Print a final summary line: `Migration complete: N migrated, M skipped.`
    - Exit with a non-zero code if any snapshot fails to migrate.
    """


class CliMigrateRegistration(Req):
    """
    The `libspec` CLI entry point must register the `migrate` subcommand.

    The registration must:
    - Add `migrate <source_url>` to the `docopt` usage string with a one-line
      description: "Migrate all snapshots from a source SpecStore backend to
      the active target backend."
    - Route `args["migrate"]` to a new `cmd_migrate_store(args)` handler in
      `cli.py`.
    """


class CliDefaultStoreDisplay(Req):
    """
    The `libspec build` command must print the active backend type and
    resolved path before compilation begins.

    The display must emit a line such as:
    `Store: JsonLines (.libspec/libspec.jsonl)` or
    `Store: SQLite (.libspec/libspec.db)`.

    The store class name and primary path attribute (`filepath` for
    JsonLines, `db_path` for SQLite) must be sourced via introspection of
    the object returned by `get_store()`.
    """


# =========================================================================
# 4. Impact on REPL
# =========================================================================


class ReplStoreBackendDisplay(Req):
    """
    The REPL session header must display the active backend type and resolved
    path alongside the snapshot ID.

    The header must show a `Backend:` line, e.g.:
    `Backend : JsonLines  .libspec/libspec.jsonl`.

    The information must be sourced from the same introspection pattern used
    in `CliDefaultStoreDisplay`.
    """


class ReplJsonLinesCompatibility(Req):
    """
    All existing REPL commands (`ls`, `show <ref>`, `diff`, `history`,
    `claims`) must function identically against a `JsonLinesSpecStore` as
    they do against `SQLiteSpecStore`.

    The compatibility must be verified by running the full REPL test suite
    against a `JsonLinesSpecStore` populated with at least two snapshots and
    one implementation claim, asserting structurally equivalent output.
    """


# =========================================================================
# 5. Test Specifications
# =========================================================================


class TestMigrateFunction(Req):
    """
    The `migrate(source, target)` function must be tested with all meaningful
    backend pairings using real (non-mocked) store instances.

    The test matrix must cover:
    - SQLite → JsonLines
    - JsonLines → JsonLines (different file)
    - JsonLines → SQLite

    Each test must:
    - Populate the source with two snapshots, multiple components, and one
      implementation claim per snapshot.
    - Call `migrate(source, target)`.
    - Assert the returned summary shows `{"migrated": 2, "skipped": 0}`.
    - Assert `target.list_snapshots()` returns both snapshots in the correct
      chronological order.
    - Assert `target.get_components_for_snapshot(snap)` matches source data.
    - Assert `target.list_implemented(snap)` matches source claims.
    """


class TestMigrateFunctionIdempotency(Req):
    """
    A test must verify that calling `migrate(source, target)` twice produces
    no duplicate data and returns the correct skipped count on the second run.

    The test must:
    - Perform an initial migration and verify `migrated == 2, skipped == 0`.
    - Run the same migration again without modifying source or target.
    - Assert the second call returns `migrated == 0, skipped == 2`.
    - Assert `target.list_snapshots()` still contains exactly two snapshots.
    """


class TestMigrateFunctionSameStoreRejection(Req):
    """
    A test must verify that the CLI `cmd_migrate_store` raises a clear error
    when the source and target resolve to the same underlying store location.
    """


class TestGetStoreResolution(Req):
    """
    Unit tests must verify the `get_store()` factory's resolution order for
    all supported URL schemes.

    The tests must assert:
    - `LIBSPEC_DATABASE_URL=jsonl://.libspec/test.jsonl` → `JsonLinesSpecStore`
    - `LIBSPEC_DATABASE_URL=sqlite:///.libspec/test.db` → `SQLiteSpecStore`
    - Unset `LIBSPEC_DATABASE_URL` → `JsonLinesSpecStore` at
      `.libspec/libspec.jsonl`.
    """
