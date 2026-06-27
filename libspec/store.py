"""
Backend-agnostic Data Access Layer for libspec.

Contains the core domain dataclasses (Component, Snapshot, Implemented),
the SpecStore Protocol, the domain exception hierarchy, and the get_store()
factory function.

Concrete implementations live in libspec/stores/:
  - libspec.stores.json_lines    — JsonLinesSpecStore (append-only JSONL)

All names remain importable directly from libspec.store for backward
compatibility.
"""

import datetime
import os
from typing import Protocol

# Re-export core domain types from common.py for backward compatibility
from libspec.common import Component, Implemented, Snapshot

# =========================================================================
# 2. Domain Exception Hierarchy
# =========================================================================


class SpecStoreError(Exception):
    """Root ancestral exception class for all errors originating from the storage layer."""


class SpecStoreIOError(SpecStoreError):
    """Raised when reading from or writing to the database, remote server, or filesystem fails."""


class SpecStoreNotFoundError(SpecStoreError):
    """Raised when a requested snapshot or component reference is not present in the current build context."""


class SpecStoreCorruptedDataError(SpecStoreError):
    """Raised when data verification, deserialization, or rendered docstring formatting fails."""


# =========================================================================
# 3. SpecStore Protocol
# =========================================================================


class SpecStore(Protocol):
    """Backend-agnostic interface boundary establishing the data access operations."""

    def store_snapshot(
        self,
        components: list[Component],
        git_commit: str | None = None,
        created_at: datetime.datetime | None = None,
        to_sidecar: bool = False,
    ) -> Snapshot:
        """Atomically registers a compiled tree of components under a new Build snapshot.

        Raises SpecStoreIOError if the persistence fails.
        """
        ...

    def current_snapshot(self) -> Snapshot | None:
        """Retrieves the active, latest metadata snapshot, or None if the store is empty."""
        ...

    def most_recent_hash(self) -> str | None:
        """Retrieves the master hash of the latest/current snapshot, or None if the store is empty."""
        ...

    def get_component(self, ref: str) -> Component:
        """Retrieves a single component's metadata from the current active snapshot.

        Raises SpecStoreNotFoundError if the ref does not exist.
        """
        ...

    def list_components(self) -> list[Component]:
        """Lists all components defined under the current active snapshot."""
        ...

    def store_implemented(self, record: Implemented) -> None:
        """Appends an implementation log entry immediately upon code injection.
        Enforces a strict one-component-per-invocation rule to ensure atomic writes.

        Raises SpecStoreIOError on failure.
        """
        ...

    def list_implemented(self, snapshot: Snapshot) -> list[Implemented]:
        """Retrieves all implementation tracking log entries scoped to the snapshot."""
        ...

    def list_snapshots(self) -> list[Snapshot]:
        """Retrieves all chronological builds/snapshots in the store, from oldest to newest."""
        ...

    def get_snapshot(self, id_or_hash: str) -> Snapshot | None:
        """Retrieves a specific historical build/snapshot by its identifier or hash prefix.

        Raises SpecStoreNotFoundError if no matching snapshot is found.
        """
        ...

    def get_components_for_snapshot(self, snapshot: Snapshot) -> list[Component]:
        """Retrieves all specification components recorded in a specific historical snapshot.

        Raises SpecStoreNotFoundError if the snapshot is invalid or missing.
        """
        ...

    def delete_snapshot(self, snapshot: Snapshot) -> None:
        """Permanently deletes a historical build/snapshot and all its associated data.

        Raises SpecStoreIOError if the deletion fails.
        """
        ...

    def restore_snapshot(self, snapshot: Snapshot) -> None:
        """Restores a previously deleted/tombstoned build/snapshot and all its associated data.

        Raises SpecStoreIOError if the restoration fails.
        """
        ...

    def store_vcs_link(
        self, snapshot_id: str, vcs: str, revision: str, metadata: dict | None = None
    ) -> None:
        """Registers a version control system link event late-bound to a snapshot.

        Raises SpecStoreIOError if the persistence fails.
        """
        ...

    def get_raw_events(self) -> list[dict]:
        """Retrieves a list of all raw, parsed transaction record dictionaries from the append-only log file in ascending chronological order.

        Raises SpecStoreIOError on failure.
        """
        ...

    def store_dependency(
        self, ref: str, depends_on: str, snapshot_id: str = "PENDING"
    ) -> None:
        """Records a logical dependency between components.

        Raises SpecStoreIOError if the persistence fails.
        """
        ...

    def list_dependencies(self, snapshot_or_id: str | Snapshot) -> dict[str, list[str]]:
        """Retrieves component dependencies for the target snapshot context.

        Returns a mapping of component references to lists of references they depend on.
        """
        ...


# =========================================================================
# 4. Backward-Compatible Re-exports from libspec.stores
# =========================================================================

from libspec.stores.json_lines import JsonLinesSpecStore  # noqa: E402

# =========================================================================
# 5. Global Store Factory
# =========================================================================


def get_store() -> SpecStore:
    """Constructs and returns the active SpecStore backend according to configurations.

    Order of precedence:
    1. `jsonl://`                        → JsonLinesSpecStore at the specified path
    2. Unset                             → JsonLinesSpecStore at .libspec/libspec.jsonl
    """
    db_url = os.environ.get("LIBSPEC_DATABASE_URL")
    if db_url and db_url.startswith("jsonl://"):
        jsonl_path = db_url[len("jsonl://") :]
        return JsonLinesSpecStore(jsonl_path)

    # Default: JsonLines at .libspec/libspec.jsonl
    default_dir = os.path.abspath(".libspec")
    os.makedirs(default_dir, exist_ok=True)
    return JsonLinesSpecStore(os.path.join(default_dir, "libspec.jsonl"))
