'''
Specification of the isolated, backend-agnostic Data Access Layer (SpecStore)
and the SQLite/Peewee/PostgreSQL schemas.
'''

from .err import Feat, Req


# =========================================================================
# 1. Core Domain Dataclasses
# =========================================================================

class SpecComponent(Req):
    '''Immutable data structure representing a compiled specification node.
    
    Fields:
    - `ref` (str): Dot-separated unique reference path to the specification class.
    - `docstring` (str): Fully rendered English prose, with MRO bases and Jinja variables resolved.
    - `is_template` (bool): True if the specification is a template containing placeholders.
    - `inherits` (list[str]): Ancestral specification FQNs ordered in strict Method Resolution Order (MRO).
    - `hash` (str): SHA-256 fingerprint of the fully rendered docstring string.
    '''


class SpecSnapshot(Req):
    '''Immutable metadata structure representing a discrete compile build instance.
    
    Fields:
    - `id` (str): Unique alphanumeric identifier derived from the master hash.
    - `created_at` (datetime): Timezone-aware timestamp indicating when the build was compiled.
    - `master_hash` (str): SHA-256 fingerprint computed deterministically from sorted child component hashes.
    - `git_commit` (str | None): Active 40-character git commit SHA-1 of the repository at build time.
    '''


class SpecImplemented(Req):
    '''Immutable structure representing an agent's claim of a satisfying implementation.
    
    Fields:
    - `ref` (str): Reference string of the specification that was implemented.
    - `spec_hash` (str): The specification's docstring hash at the exact time the code was written.
    - `file` (str): Workspace filesystem path to the file containing the `# IMPLEMENTS` marker comment.
    - `line` (int): Line number of the injected `# IMPLEMENTS` marker comment.
    - `session_id` (str | None): Active agent session identifier tracking the context of implementation.
    '''


# =========================================================================
# 2. Domain Exception Hierarchy
# =========================================================================

class StoreError(Req):
    '''Root ancestral exception class for all errors originating from the storage layer.
    All backend-specific database or file exceptions must be caught and raised as a sub-class of StoreError.
    '''


class StoreIOError(StoreError):
    '''Raised when reading from or writing to the underlying database, remote host, or filesystem fails.'''


class StoreNotFoundError(StoreError):
    '''Raised when a requested snapshot or component reference is not present in the current build context.'''


class StoreCorruptedDataError(StoreError):
    '''Raised when data verification, deserialization, or rendered docstring formatting fails.'''


# =========================================================================
# 3. SpecStore Protocol & Functional Methods
# =========================================================================

class SpecStoreProtocol(Req):
    '''Backend-agnostic interface boundary establishing the data access operations.
    The compiler core (SpecEngine) interacts exclusively with this Protocol, decoupled from storage mechanisms.
    '''


class StoreSnapshot(Req):
    '''Operation to atomically save a full compiled tree of components under a new active snapshot.
    
    The operation must:
    - Accept a list of `Component` objects and an optional git commit string.
    - Compute the snapshot's deterministic master_hash by sorting component hashes alphabetically by ref.
    - Return a frozen `Snapshot` instance representing the completed transaction.
    - Raise `StoreIOError` if the underlying write to database or disk fails.
    '''


class CurrentSnapshot(Req):
    '''Operation to retrieve the latest active metadata snapshot from the store.
    
    The operation must:
    - Read the metadata of the most recent build session.
    - Return a `Snapshot` instance, or `None` if the store does not contain any builds.
    '''


class GetComponent(Req):
    '''Operation to retrieve a specific component's definition from the current active snapshot.
    
    The operation must:
    - Lookup the component by its dot-separated FQN reference.
    - Return a fully populated `Component` object.
    - Raise `StoreNotFoundError` if the reference does not exist in the active snapshot.
    '''


class ListComponents(Req):
    '''Operation to list all components associated with the latest active build.
    
    The operation must:
    - Return a list of all `Component` objects in the active snapshot.
    - Return an empty list if no snapshot has been stored.
    '''


class StoreImplemented(Req):
    '''Operation to record a code-level implementation claim.
    
    The operation must:
    - Accept a single `Implemented` dataclass log record.
    - Persist the record, enforcing a strict one-claim-per-invocation atomic boundary.
    - Raise `StoreIOError` on persistence failures.
    '''


class ListImplemented(Req):
    '''Operation to list all active implementation claims scoped to a specific snapshot boundary.
    
    The operation must:
    - Accept a target `Snapshot` instance.
    - Filter and return all `Implemented` records matching that snapshot's active scope.
    '''


# =========================================================================
# 4. Storage Engine Adapters
# =========================================================================

class XmlStoreAdapter(Feat):
    '''Strangler Fig passive adapter translating Legacy XML files to the SpecStore interface.
    
    The adapter must:
    - Load and parse legacy XML files under the new `SpecStoreProtocol` API.
    - Preserve 100% format compatibility with existing XML specification formats.
    - Perform all file updates atomically using `os.replace` to prevent file corruption during crashes.
    '''


class SQLiteStore(Feat):
    '''Relational storage engine using SQLite via Peewee.
    
    The engine must:
    - Support fully normalized tables: Build (pruned to 2 latest), Spec, Edge (flat MRO), and Implemented.
    - Execute compiler builds and verification queries with sub-millisecond local latencies.
    - Treat the database file as a derived, uncommitted compile target built on demand via CLI or MCP.
    '''


class PostgreSQLStore(Feat):
    '''Centralized relational storage engine using PostgreSQL for distributed engineering teams.
    
    The engine must:
    - Map the exact same Peewee schemas natively to a remote PostgreSQL server.
    - Synchronize team-wide builds in real-time, allowing developers to pull claims and specs instantly.
    - Support co-existent hybrid merging with read-only SQLite files from upstream dependency packages.
    '''
