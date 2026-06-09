"""
Specification of the isolated, backend-agnostic Data Access Layer (SpecStore).
"""

from .err import Feat, Req


# =========================================================================
# 1. Core Domain Dataclasses
# =========================================================================


class SpecComponent(Req):
    """
    Immutable data structure representing a compiled specification node.

    Fields:
    - `ref` (str): Dot-separated unique reference path to the specification
      class.
    - `docstring` (str): Fully rendered English prose, with MRO bases and Jinja
      variables resolved.
    - `is_template` (bool): True if the specification is a template containing
      placeholders.
    - `inherits` (list[str]): Ancestral specification FQNs ordered in strict
      Method Resolution Order (MRO).
    - `hash` (str): SHA-256 fingerprint of the fully rendered docstring string.
    """


class SpecSnapshot(Req):
    """
    Immutable metadata structure representing a discrete compile build
    instance.

    Fields:
    - `id` (str): Unique alphanumeric identifier derived from the master hash.
    - `created_at` (datetime): Timezone-aware timestamp indicating when the
      build was compiled.
    - `master_hash` (str): SHA-256 fingerprint computed deterministically from
      sorted child component hashes.
    - `git_commit` (str | None): Active 40-character git commit SHA-1 of the
      repository at build time.
    """


class SpecImplemented(Req):
    """
    Immutable structure representing an agent's claim of a satisfying
    implementation.

    Fields:
    - `ref` (str): Reference string of the specification that was implemented.
    - `spec_hash` (str): The specification's docstring hash at the exact time
      the code was written.
    - `file` (str): Workspace filesystem path to the file containing the `#
      IMPLEMENTS` marker comment.
    - `line` (int): Line number of the injected `# IMPLEMENTS` marker comment.
    - `session_id` (str | None): Active agent session identifier tracking the
      context of implementation.
    """


# =========================================================================
# 2. Domain Exception Hierarchy
# =========================================================================


class StoreError(Req):
    """
    Root ancestral exception class for all errors originating from the storage
    layer.

    All backend-specific database or file exceptions must be caught and raised
    as a sub-class of StoreError.
    """


class StoreIOError(StoreError):
    """
    Raised when reading from or writing to the underlying database, remote
    host, or filesystem fails.
    """


class StoreNotFoundError(StoreError):
    """
    Raised when a requested snapshot or component reference is not present in
    the current build context.
    """


class StoreCorruptedDataError(StoreError):
    """
    Raised when data verification, deserialization, or rendered docstring
    formatting fails.
    """


# =========================================================================
# 3. SpecStore Protocol & Functional Methods
# =========================================================================


class SpecStoreProtocol(Req):
    """
    Backend-agnostic interface boundary establishing the data access
    operations.

    The compiler core (SpecEngine) interacts exclusively with this Protocol,
    decoupled from storage mechanisms.
    """


class StoreSnapshot(Req):
    """
    Operation to atomically save a full compiled tree of components under a new
    active snapshot.

    The operation must:
    - Accept a list of `Component` objects, an optional git commit string, and
      an optional custom timezone-aware `created_at` timestamp.
    - Compute the snapshot's deterministic master_hash by sorting component
      hashes alphabetically by ref.
    - Return a frozen `Snapshot` instance representing the completed
      transaction.
    - Raise `StoreIOError` if the underlying write to database or disk fails.
    """


class CurrentSnapshot(Req):
    """
    Operation to retrieve the latest active metadata snapshot from the store.

    The operation must:
    - Read the metadata of the most recent build session.
    - Return a `Snapshot` instance, or `None` if the store does not contain any
      builds.
    """


class GetComponent(Req):
    """
    Operation to retrieve a specific component's definition from the current
    active snapshot.

    The operation must:
    - Lookup the component by its dot-separated FQN reference.
    - Return a fully populated `Component` object.
    - Raise `StoreNotFoundError` if the reference does not exist in the active
      snapshot.
    """


class ListComponents(Req):
    """
    Operation to list all components associated with the latest active build.

    The operation must:
    - Return a list of all `Component` objects in the active snapshot.
    - Return an empty list if no snapshot has been stored.
    """


class StoreImplemented(Req):
    """
    Operation to record a code-level implementation claim.

    The operation must:
    - Accept a single `Implemented` dataclass log record.
    - Persist the record, enforcing a strict one-claim-per-invocation atomic
      boundary.
    - Raise `StoreIOError` on persistence failures.
    """


class ListImplemented(Req):
    """
    Operation to list all active implementation claims scoped to a specific
    snapshot boundary.

    The operation must:
    - Accept a target `Snapshot` instance.
    - Filter and return all `Implemented` records matching that snapshot's
      active scope.
    """


class ListSnapshots(Req):
    """
    Operation to list all chronological build snapshots recorded in the store.

    The operation must:
    - Query and return a list of all historical `Snapshot` instances.
    - Order the snapshots chronologically from the oldest to the newest.
    - Return an empty list if no builds have been compiled.
    """


class GetSnapshot(Req):
    """
    Operation to lookup a specific historical snapshot by its session ID or
    hash.

    The operation must:
    - Accept an alphanumeric snapshot ID or prefix.
    - Match and return the target `Snapshot` instance.
    - Raise `StoreNotFoundError` if no matching snapshot is resolved.
    """


class GetComponentsForSnapshot(Req):
    """
    Operation to retrieve all specification components recorded in a specific
    historical snapshot.

    The operation must:
    - Accept a target `Snapshot` instance.
    - Retrieve and return a list of all `Component` objects associated with
      that historical snapshot.
    - Raise `StoreNotFoundError` if the snapshot is invalid or missing.
    """


class RestoreSnapshot(Req):
    """
    Operation to restore a previously deleted/tombstoned historical snapshot.

    The operation must:
    - Accept a target `Snapshot` instance.
    - Restore the snapshot and all its associated component/claims metadata.
    - Re-insert the snapshot into the active list of snapshots in its original
      chronological position.
    - Raise `StoreIOError` if the underlying write to database or disk fails.
    """


# =========================================================================
# 4. Storage Engine Adapters
# =========================================================================


class JsonLinesStore(Feat):
    """
    Append-only JSON Lines (JSONL / NDJSON) storage engine.
    """


class JsonLinesFilePersistence(Req):
    """
    Persist snapshots, components, and implementation claims as structured JSON
    Lines (each object on a single line) in a single transaction log file.
    """


class JsonLinesAppendOnly(Req):
    """
    Guarantee 100% git-friendliness by operating in a strictly append-only
    fashion, avoiding destructive inline file updates or random-access
    rewrites.
    """


class JsonLinesDeterministicCanonical(Req):
    """
    Provide deterministic canonical JSON serialization (e.g. sorted keys,
    compact separators, stable encoding) to ensure clean, git-diffable
    changesets.
    """


class JsonLinesReplayReconstruction(Req):
    """
    Reconstruct the full state of specifications and implementations at any
    historical point by chronologically replaying the transaction log from the
    beginning.
    """


class JsonLinesTombstoneDeletion(Req):
    """
    Maintain strictly append-only behavior during snapshot deletion by appending
    a tombstone record to the JSON Lines file, rather than rewriting or truncating
    the file.
    """


class JsonLinesRestoreUndelete(Req):
    """
    Support restoring previously deleted snapshots by appending a restore event
    record to the JSON Lines file and placing the snapshot back into active rotation.
    """


# =========================================================================
# 5. VCS Event Linking
# =========================================================================


class VcsEventLinking(Feat):
    """
    Late-bound, append-only, VCS-agnostic snapshot metadata linking.

    Allows linking compiled spec snapshots directly to specific version control
    revisions retroactively, preserving data immutability and separating compile
    actions from version control tree queries.
    """


class VcsLinkEventRecord(Req):
    """
    The schema of the `vcs_link` event type inside `JsonLinesSpecStore`.

    Each linking record must be represented as a compact, single-line JSON record
    containing the following required keys:
    - `type` (str): Must be exactly `"vcs_link"`.
    - `snapshot_id` (str): 16-character hexadecimal target snapshot identifier.
    - `vcs` (str): The VCS system type (e.g. `"git"`, `"hg"`, `"svn"`, `"perforce"`, `"manual"`).
    - `revision` (str): The unique revision identifier (commit SHA, changeset node, or revision number).
    - `created_at` (str): ISO-8601 UTC timestamp of record creation.
    - `metadata` (dict, optional): Contextual metadata including branch, author, or commit message.
    """


class VcsLinkEventReplay(Req):
    """
    Event-sourced replay and state reconstruction rules.

    The state machine must reconstruct the current snapshot state by replaying all records chronologically.
    When a `"vcs_link"` event is encountered, the state machine must look up the target snapshot by `snapshot_id`
    and update its active revision reference. If multiple link records are present, the latest parsed event wins
    or aggregates them according to project policy.
    """


class VcsLinkEventCompatibility(Req):
    """
    Backwards-compatibility with legacy snapshots and direct `git_commit` attributes.

    Existing legacy snapshots possessing an embedded `git_commit` in their initial snapshot event must be loaded
    and parsed correctly as the baseline. Any late-bound linking record processed later in the stream takes
    precedence and gracefully overrides the baseline commit, ensuring zero disruption to existing spec history.
    """


class VcsLinkEventDecoupling(Req):
    """
    Separation of compile actions from VCS command-line execution.

    The core `libspec build` command must not block on or query the active version control tree during compilation.
    Instead, snapshots must be compiled with a pending or null revision status, allowing builds to remain fast,
    deterministic, and capable of running in uninitialized repositories without version control dependencies.
    """


class VcsLinkCli(Req):
    """
    Command-line syntax and behavior of the `libspec link` command.

    Exposes a decoupled interface allowing users and external automation scripts to manually or programmatically
    link active snapshots to VCS commits.
    Syntax: `libspec link --snapshot <id> --vcs <vcs_type> --revision <revision> [--metadata <key=val>]`
    Writes the link record to the database or append-only JSONL file and prints a success verification to stdout.
    """


class VcsLinkGitHook(Req):
    """
    Scaffolding of the Git `post-commit` client-side automation hook.

    During framework initialization, `libspec init` must install a client-side `post-commit` hook script in the
    repository's `.git/hooks/` directory. Upon a successful commit, the hook automatically queries the newly
    minted commit hash, locates the latest unlinked spec snapshot, and invokes `libspec link` to establish the connection.
    """


class VcsLinkHookResilience(Req):
    """
    Fail-safe, non-blocking execution of automation hooks.

    The automated hook scripts must be designed to fail silently and gracefully during complex VCS operations such as
    interactive rebases, cherry-picks, detached-head commits, or empty changesets. The script must never block the
    developer's checkout or commit action and should exit early if no unlinked snapshots are pending.
    """


class VcsLinkHookSelfHealing(Req):
    """
    Self-healing hook verification during active framework startup.

    Every time a `libspec` command runs, it must verify the existence of the client-side Git post-commit hook script within
    `.git/hooks/`. If a `.git/` repository directory is present but the hook script is missing, outdated, or corrupted,
    the system must automatically heal/re-install the hook silently, notifying the user via stderr to ensure seamless
    late-bound VCS linking across older libspec projects.
    """


class VcsLinkAgnostic(Req):
    """
    VCS agnosticism supporting Git, Mercurial, Subversion, and Perforce.

    The linking framework must be VCS-agnostic. While Git hooks use `post-commit` shell scripts, Mercurial integrates via
    `post-commit` transaction triggers, Subversion uses client-side commit wrappers, and Perforce leverages server-side
    submit triggers, all of which map metadata back to the same unified `vcs_link` event schema.
    """


# =========================================================================
# 6. Component Dependencies
# =========================================================================


class ComponentDependencies(Feat):
    """
    Logical dependencies between specification components recorded transactionally.
    """


class StoreDependency(Req):
    """
    Operation to record a logical dependency between components.

    The operation must:
    - Accept a target component reference (`ref`), a dependency component reference (`depends_on`),
      and an optional `snapshot_id` (defaulting to `"PENDING"`).
    - Append a dependency record to the underlying database or log.
    - Raise `StoreIOError` on failure.
    """


class ListDependencies(Req):
    """
    Operation to retrieve dependencies for a specific snapshot.

    The operation must:
    - Accept a target `Snapshot` instance.
    - Retrieve and return a mapping of component FQNs to lists of their declared dependencies
      associated with that snapshot.
    """


class DependencyEventRecord(Req):
    """
    The schema of the `"dependency"` event type inside `JsonLinesSpecStore`.

    Each dependency record must be a single-line JSON record containing:
    - `type` (str): Must be exactly `"dependency"`.
    - `snapshot_id` (str): Alphanumeric snapshot ID or `"PENDING"`.
    - `ref` (str): Dot-separated FQN of the dependent component.
    - `depends_on` (str): Dot-separated FQN of the component it depends on.
    - `created_at` (str): ISO-8601 UTC timestamp.
    """


class DependencyEventReplay(Req):
    """
    Replay and late-binding rules for dependency events.

    During log replay, any event with `snapshot_id` set to `"PENDING"` must be cached in memory.
    Upon encountering the next `"type": "snapshot"` event, all cached pending dependency and
    implemented events must be dynamically bound to that snapshot's resolved ID.
    """


class DependencyCompaction(Req):
    """
    Compaction resolution for late-bound pending records.

    The compaction process must resolve all `"PENDING"` snapshot IDs to their bound snapshot
    identifiers and write the resolved records back, leaving no `"PENDING"` references in the
    compacted historical log.
    """
