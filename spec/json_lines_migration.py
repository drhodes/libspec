"""
Specification for the SQLite-to-JsonLines migration and the JsonLinesStore
as the new default backend.
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
    - Activate JsonLinesSpecStore when `LIBSPEC_DATABASE_URL` is unset or set
      to a `jsonl://` scheme pointing to a `.jsonl` file path.
    - Retain full backward compatibility: `sqlite://` and `postgresql://` URL
      schemes continue to resolve to their respective backends without change.
    - Preserve the existing XML fallback when no environment variable is set
      and no `.libspec/libspec.jsonl` file exists (strangler fig).
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
# 2. SQLite-to-JsonLines Migration Command
# =========================================================================


class SqliteToJsonLinesMigration(Feat):
    """
    The libspec platform must provide a migration command that reads an
    existing SQLite database and writes its full history into a new
    JsonLinesSpecStore transaction log, preserving chronological order and
    all associated implementation claims.
    """


class MigrateSqliteCommand(Req):
    """
    A new CLI subcommand `libspec migrate-sqlite <db_path>` must be exposed
    to perform the one-time migration from SQLite to JsonLines.

    The command must:
    - Accept a single positional argument: the path to the source SQLite
      `.db` file.
    - Resolve the target JsonLines path from the active `get_store()` (must
      be a `JsonLinesSpecStore` instance), or default to
      `.libspec/libspec.jsonl`.
    - Raise a clear `SpecStoreIOError` with a user-facing message if the
      target store is not a `JsonLinesSpecStore`.
    - Refuse to overwrite a non-empty target `.jsonl` file unless the
      `--force` flag is explicitly provided.
    """


class MigrateSqliteOrdering(Req):
    """
    The migration must replay all SQLite build snapshots into the target
    JsonLinesSpecStore in strict chronological order (oldest `created_at`
    first).

    The ordering must:
    - Sort all `DBBuild` rows by `created_at` ascending before processing.
    - Write each snapshot record, followed immediately by all of its
      component records, then all of its implementation claim records, as a
      single contiguous block in the JSONL log.
    - Preserve the exact `created_at` timestamp from the source SQLite row
      in each emitted snapshot record.
    """


class MigrateSqliteIdempotency(Req):
    """
    The migration must be idempotent with respect to the JsonLinesSpecStore's
    own deduplication logic.

    The idempotency guarantee must:
    - Delegate to `JsonLinesSpecStore.store_snapshot()`, which skips
      re-writing a snapshot whose `master_hash` already exists in the log.
    - Emit a per-snapshot log line indicating `skipped` or `migrated` for
      operator visibility.
    - Exit with a zero return code even when all snapshots are already
      present.
    """


class MigrateSqliteProgress(Req):
    """
    The migration command must emit clear, structured progress output to
    stdout for each snapshot processed.

    Each output line must:
    - Identify the snapshot by its short ID and `created_at` timestamp.
    - State the number of components and implementation claims being written.
    - State the final outcome as either `migrated` or `skipped (duplicate)`.
    """


# =========================================================================
# 3. Impact on CLI
# =========================================================================


class CliMigrateSqliteSwitch(Req):
    """
    The `libspec` CLI entry point must register the new `migrate-sqlite`
    subcommand in its `docopt` usage string and dispatch table.

    The registration must:
    - Add `migrate-sqlite <db_path>` to the usage block with a brief
      description: "Migrate a SQLite SpecStore to the active JsonLines
      backend."
    - Add an optional `--force` flag documented as: "Overwrite existing
      JsonLines log file."
    - Route `args["migrate-sqlite"]` to the new `cmd_migrate_sqlite(args)`
      handler function in `cli.py`.
    """


class CliDefaultStoreDisplay(Req):
    """
    The `libspec build` command output must report the active backend type
    and resolved path so operators immediately know which store is in use.

    The display must:
    - Print a one-line prefix before compilation begins, e.g.:
      `Store: JsonLines (.libspec/libspec.jsonl)` or
      `Store: SQLite (.libspec/libspec.db)`.
    - Source this information from `get_store().__class__.__name__` and the
      store's primary path attribute (`filepath` for JsonLines, `db_path`
      for SQLite).
    """


# =========================================================================
# 4. Impact on REPL
# =========================================================================


class ReplStoreBackendDisplay(Req):
    """
    The REPL session header must display the active backend type and resolved
    path alongside the snapshot ID.

    The header must:
    - Show a `Backend:` line identifying the store class and its primary
      path, e.g.: `Backend : JsonLines  .libspec/libspec.jsonl`.
    - Source this from the same introspection pattern used in
      `CliDefaultStoreDisplay`.
    """


class ReplJsonLinesCompatibility(Req):
    """
    All existing REPL commands (`ls`, `show <ref>`, `diff`, `history`,
    `claims`) must function identically against a `JsonLinesSpecStore` as
    they do against `SQLiteSpecStore`.

    The compatibility must be verified by:
    - Running the full REPL test suite against a `JsonLinesSpecStore`
      populated with at least two snapshots and one implementation claim.
    - Asserting that all commands produce output structurally equivalent to
      the SQLite-backed REPL output.
    """


# =========================================================================
# 5. Impact on MCP Server
# =========================================================================


class McpServerJsonLinesCompatibility(Req):
    """
    All MCP server tools (`peek`, `search`, `symbols`, `usage`) must operate
    correctly when the active backend is a `JsonLinesSpecStore`.

    The compatibility must:
    - Require no MCP-server-level code changes — compatibility is guaranteed
      by the `SpecStore` protocol contract.
    - Be verified by ensuring `get_store()` resolves to `JsonLinesSpecStore`
      in the MCP server's ambient environment during integration tests.
    """


# =========================================================================
# 6. Test Specifications
# =========================================================================


class TestJsonLinesStoreContract(Req):
    """
    A dedicated test module `tests/test_jsonlines_store.py` must verify the
    full `SpecStore` protocol contract for `JsonLinesSpecStore`.

    Tests must cover:
    - `store_snapshot` creates a snapshot record and component records in the
      JSONL log.
    - `current_snapshot` returns the last written snapshot after replay.
    - `list_components` returns all components for the active snapshot.
    - `get_component` retrieves a single component by ref.
    - `store_implemented` appends an implementation claim to the log.
    - `list_implemented` returns claims scoped to the correct snapshot.
    - `list_snapshots` returns all snapshots in chronological order.
    - `get_snapshot` resolves by exact ID, full hash, and short prefix.
    - `get_components_for_snapshot` retrieves components for a historical
      snapshot.
    """


class TestJsonLinesReplay(Req):
    """
    A replay-correctness test must verify that instantiating a new
    `JsonLinesSpecStore` on an existing `.jsonl` file reproduces the
    identical in-memory state.

    The test must:
    - Write two distinct snapshots and one implementation claim via `store1`.
    - Instantiate `store2` on the same file path.
    - Assert that `store2.list_snapshots()` returns the same two snapshots.
    - Assert that `store2.list_components()` returns the same component set.
    - Assert that `store2.list_implemented(snap)` returns the same claim.
    """


class TestJsonLinesCanonicalFormat(Req):
    """
    A format-correctness test must verify that each line written to the
    `.jsonl` file is valid, deterministic, canonical JSON.

    The test must:
    - Write a snapshot with a single component.
    - Read the raw `.jsonl` file lines.
    - Assert each line parses as valid JSON.
    - Assert keys within each record are sorted alphabetically.
    - Assert no extraneous whitespace appears between keys and values (i.e.,
      compact separators `(',', ':')` are used).
    """


class TestJsonLinesClaimDeduplication(Req):
    """
    A deduplication test must verify that writing two `Implemented` claims
    for the same `ref` under the same snapshot results in only one active
    claim upon replay.

    The test must:
    - Store a snapshot with one component.
    - Call `store_implemented` twice for the same `ref` with different `line`
      values.
    - Instantiate a fresh store from the same file.
    - Assert `list_implemented(snap)` returns exactly one claim with the
      `line` value from the second call.
    """


class TestJsonLinesErrorHandling(Req):
    """
    Error-boundary tests must verify defensive behavior for corrupt inputs.

    The tests must cover:
    - A `.jsonl` file containing an invalid JSON line raises
      `SpecStoreCorruptedDataError` on instantiation.
    - A `.jsonl` file containing a record with an unknown `type` field raises
      `SpecStoreCorruptedDataError`.
    - `get_component` on a non-existent ref raises `SpecStoreNotFoundError`.
    - `get_snapshot` with an unmatched ID raises `SpecStoreNotFoundError`.
    - `store_implemented` when no snapshot exists raises
      `SpecStoreNotFoundError`.
    """


class TestSqliteToJsonLinesMigration(Req):
    """
    An integration test must verify the end-to-end `migrate-sqlite` workflow.

    The test must:
    - Populate a temporary `SQLiteSpecStore` with at least two snapshots,
      each containing multiple components and one implementation claim.
    - Execute `cmd_migrate_sqlite` pointing to the SQLite `.db` file, with
      the target set to a temporary `.jsonl` path.
    - Instantiate a `JsonLinesSpecStore` on the output path.
    - Assert `list_snapshots()` returns the same number of snapshots in the
      same chronological order.
    - Assert `list_components()` for each snapshot matches the source SQLite
      data.
    - Assert `list_implemented()` for each snapshot returns the same claims.
    """


class TestGetStoreResolution(Req):
    """
    Unit tests must verify the `get_store()` factory's resolution order for
    all supported URL schemes.

    The tests must assert:
    - `LIBSPEC_DATABASE_URL=jsonl://.libspec/test.jsonl` → `JsonLinesSpecStore`
    - `LIBSPEC_DATABASE_URL=sqlite:///.libspec/test.db` → `SQLiteSpecStore`
    - Unset `LIBSPEC_DATABASE_URL` → `JsonLinesSpecStore` at the default path
      `.libspec/libspec.jsonl`.
    """
