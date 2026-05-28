'''
Backend-agnostic Data Access Layer for libspec.

Contains the core domain dataclasses (Component, Snapshot, Implemented),
the SpecStore Protocol, the domain exception hierarchy, and the get_store()
factory function.

Concrete implementations live in libspec/stores/:
  - libspec.stores.xml_adapter   — XmlSpecStore (strangler fig)
  - libspec.stores.json_lines    — JsonLinesSpecStore (append-only JSONL)
  - libspec.stores.sqlite        — SQLiteSpecStore, PostgresSpecStore (Peewee)

All names remain importable directly from libspec.store for backward
compatibility.
'''

import os
import datetime
import hashlib
from typing import Protocol, Optional, List
from dataclasses import dataclass


# =========================================================================
# 1. Core Domain Dataclasses
# =========================================================================

@dataclass(frozen=True)
class Component:
    ref: str
    docstring: str
    is_template: bool
    inherits: List[str]
    hash: str

    def __post_init__(self):
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise ValueError("Component 'ref' must be a non-empty string.")
        if not isinstance(self.docstring, str):
            raise TypeError("Component 'docstring' must be a string.")
        if not isinstance(self.is_template, bool):
            raise TypeError("Component 'is_template' must be a boolean.")
        if not isinstance(self.inherits, list) or not all(isinstance(x, str) for x in self.inherits):
            raise TypeError("Component 'inherits' must be a list of strings.")
        if not isinstance(self.hash, str) or len(self.hash) != 64:
            raise ValueError("Component 'hash' must be a 64-character SHA-256 hash string.")


@dataclass(frozen=True)
class Snapshot:
    id: str
    created_at: datetime.datetime
    master_hash: str
    git_commit: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Snapshot 'id' must be a non-empty string.")
        if not isinstance(self.created_at, datetime.datetime):
            raise TypeError("Snapshot 'created_at' must be a datetime object.")
        if not isinstance(self.master_hash, str) or len(self.master_hash) != 64:
            raise ValueError("Snapshot 'master_hash' must be a 64-character SHA-256 hash string.")
        if self.git_commit is not None and not isinstance(self.git_commit, str):
            raise TypeError("Snapshot 'git_commit' must be a string or None.")


@dataclass(frozen=True)
class Implemented:
    ref: str
    spec_hash: str
    file: str
    line: int
    session_id: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise ValueError("Implemented 'ref' must be a non-empty string.")
        if not isinstance(self.spec_hash, str) or len(self.spec_hash) != 64:
            raise ValueError("Implemented 'spec_hash' must be a 64-character SHA-256 hash string.")
        if not isinstance(self.file, str) or not self.file.strip():
            raise ValueError("Implemented 'file' must be a non-empty string.")
        if not isinstance(self.line, int) or self.line <= 0:
            raise ValueError("Implemented 'line' must be a positive integer.")
        if self.session_id is not None and not isinstance(self.session_id, str):
            raise TypeError("Implemented 'session_id' must be a string or None.")


# =========================================================================
# 2. Domain Exception Hierarchy
# =========================================================================

class SpecStoreError(Exception):
    '''Root ancestral exception class for all errors originating from the storage layer.'''


class SpecStoreIOError(SpecStoreError):
    '''Raised when reading from or writing to the database, remote server, or filesystem fails.'''


class SpecStoreNotFoundError(SpecStoreError):
    '''Raised when a requested snapshot or component reference is not present in the current build context.'''


class SpecStoreCorruptedDataError(SpecStoreError):
    '''Raised when data verification, deserialization, or rendered docstring formatting fails.'''


# =========================================================================
# 3. SpecStore Protocol
# =========================================================================

class SpecStore(Protocol):
    '''Backend-agnostic interface boundary establishing the data access operations.'''

    def store_snapshot(self, components: List[Component], git_commit: Optional[str] = None, created_at: Optional[datetime.datetime] = None) -> Snapshot:
        '''Atomically registers a compiled tree of components under a new Build snapshot.

        Raises SpecStoreIOError if the persistence fails.
        '''
        ...

    def current_snapshot(self) -> Optional[Snapshot]:
        '''Retrieves the active, latest metadata snapshot, or None if the store is empty.'''
        ...

    def most_recent_hash(self) -> Optional[str]:
        '''Retrieves the master hash of the latest/current snapshot, or None if the store is empty.'''
        ...

    def get_component(self, ref: str) -> Component:
        '''Retrieves a single component's metadata from the current active snapshot.

        Raises SpecStoreNotFoundError if the ref does not exist.
        '''
        ...

    def list_components(self) -> List[Component]:
        '''Lists all components defined under the current active snapshot.'''
        ...

    def store_implemented(self, record: Implemented) -> None:
        '''Appends an implementation log entry immediately upon code injection.
        Enforces a strict one-component-per-invocation rule to ensure atomic writes.

        Raises SpecStoreIOError on failure.
        '''
        ...

    def list_implemented(self, snapshot: Snapshot) -> List[Implemented]:
        '''Retrieves all implementation tracking log entries scoped to the snapshot.'''
        ...

    def list_snapshots(self) -> List[Snapshot]:
        '''Retrieves all chronological builds/snapshots in the store, from oldest to newest.'''
        ...

    def get_snapshot(self, id_or_hash: str) -> Optional[Snapshot]:
        '''Retrieves a specific historical build/snapshot by its identifier or hash prefix.

        Raises SpecStoreNotFoundError if no matching snapshot is found.
        '''
        ...

    def get_components_for_snapshot(self, snapshot: Snapshot) -> List[Component]:
        '''Retrieves all specification components recorded in a specific historical snapshot.

        Raises SpecStoreNotFoundError if the snapshot is invalid or missing.
        '''
        ...

    def delete_snapshot(self, snapshot: Snapshot) -> None:
        '''Permanently deletes a historical build/snapshot and all its associated data.

        Raises SpecStoreIOError if the deletion fails.
        '''
        ...

    def restore_snapshot(self, snapshot: Snapshot) -> None:
        '''Restores a previously deleted/tombstoned build/snapshot and all its associated data.

        Raises SpecStoreIOError if the restoration fails.
        '''
        ...

    def store_vcs_link(self, snapshot_id: str, vcs: str, revision: str, metadata: Optional[dict] = None) -> None:
        '''Registers a version control system link event late-bound to a snapshot.

        Raises SpecStoreIOError if the persistence fails.
        '''
        ...


# =========================================================================
# 4. Backward-Compatible Re-exports from libspec.stores
# =========================================================================

from libspec.stores.xml_adapter import XmlSpecStore
from libspec.stores.json_lines import JsonLinesSpecStore
from libspec.stores.sqlite import (
    SQLiteSpecStore,
    PostgresSpecStore,
    DBBuild,
    DBSpec,
    DBEdge,
    DBImplemented,
    DBVcsLink,
)


# =========================================================================
# 5. Global Store Factory
# =========================================================================

def get_store() -> SpecStore:
    '''Constructs and returns the active SpecStore backend according to configurations.

    Order of precedence:
    1. `postgresql://` or `postgres://`  → PostgresSpecStore
    2. `sqlite://`                       → SQLiteSpecStore
    3. `jsonl://`                        → JsonLinesSpecStore at the specified path
    4. Unset                             → JsonLinesSpecStore at .libspec/libspec.jsonl
    '''
    db_url = os.environ.get("LIBSPEC_DATABASE_URL")
    if db_url:
        if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
            import urllib.parse
            url = urllib.parse.urlparse(db_url)
            db_name = url.path[1:]
            conn_params = {
                'user': url.username,
                'password': url.password,
                'host': url.hostname,
                'port': url.port or 5432,
            }
            conn_params = {k: v for k, v in conn_params.items() if v is not None}
            return PostgresSpecStore(db_name, **conn_params)
        elif db_url.startswith("sqlite://"):
            db_path = db_url.replace("sqlite://", "", 1)
            if db_path.startswith("/.") or (db_path.startswith("/") and os.path.exists(db_path[1:])):
                db_path = db_path[1:]
            return SQLiteSpecStore(db_path)
        elif db_url.startswith("jsonl://"):
            jsonl_path = db_url[len("jsonl://"):]
            return JsonLinesSpecStore(jsonl_path)

    # Default: JsonLines at .libspec/libspec.jsonl
    default_dir = os.path.abspath(".libspec")
    os.makedirs(default_dir, exist_ok=True)
    return JsonLinesSpecStore(os.path.join(default_dir, "libspec.jsonl"))
