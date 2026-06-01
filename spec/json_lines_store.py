"""
Specification for JsonLinesStore as the default SpecStore backend.
"""

from .err import Feat, Req


class JsonLinesDefaultBackend(Feat):
    """
    JsonLinesSpecStore is the default active backend for all local libspec workflows.

    The store must:
    - Store the JSONL transaction log at `.libspec/libspec.jsonl` by default.
    - Activate JsonLinesSpecStore when `LIBSPEC_DATABASE_URL` is unset.
    - Support a `jsonl://` URL scheme in `LIBSPEC_DATABASE_URL` for explicit
      opt-in with a custom file path.
    """


class GetStoreResolutionOrder(Req):
    """
    The `get_store()` factory must resolve the active backend in this strict
    precedence order:

    - `jsonl://` → JsonLinesSpecStore at the specified path
    - Unset → JsonLinesSpecStore at `.libspec/libspec.jsonl` (default)
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


class CliDefaultStoreDisplay(Req):
    """
    The `libspec build` command must print the active backend type and
    resolved path before compilation begins.

    The display must emit a line such as:
    `Store: JsonLinesSpecStore (/usr/backup-working/work/libspec/.libspec/libspec.jsonl)`.
    """


class ReplStoreBackendDisplay(Req):
    """
    The REPL session header must display the active backend type and resolved
    path alongside the snapshot ID.

    The header must show a `Backend:` line, e.g.:
    `Backend : JsonLines  .libspec/libspec.jsonl`.
    """


class ReplJsonLinesCompatibility(Req):
    """
    All existing REPL commands (`ls`, `show <ref>`, `diff`, `history`,
    `claims`) must function identically against a `JsonLinesSpecStore`.
    """


class TestGetStoreResolution(Req):
    """
    Unit tests must verify the `get_store()` factory's resolution order for
    the supported URL scheme.

    The tests must assert:
    - `LIBSPEC_DATABASE_URL=jsonl://.libspec/test.jsonl` → `JsonLinesSpecStore`
    - Unset `LIBSPEC_DATABASE_URL` → `JsonLinesSpecStore` at
      `.libspec/libspec.jsonl`.
    """
