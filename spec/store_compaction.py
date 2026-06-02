"""
Specification for SpecStore optimization, compaction, and deduplication.
"""

from .err import Feat, Req


# =========================================================================
# 1. Content-Addressable Storage (CAS)
# =========================================================================

class ContentAddressableStorage(Feat):
    """
    The JsonLinesSpecStore must employ a Content-Addressable Storage (CAS)
    model to eliminate redundant storage of unmodified component docstrings
    across sequential snapshots.
    """


class ComponentDeduplication(Req):
    """
    A full `component` event record (containing the docstring, ref, inherits, and metadata)
    must be appended to the log exactly once—the very first time that specific version's
    content hash is encountered.
    """


class SnapshotManifest(Req):
    """
    The `snapshot` event record must store a manifest mapping all component
    references (FQNs) in that snapshot to their corresponding content hashes.
    """


class ReplayReconstruction(Req):
    """
    During store initialization/replay, the engine must resolve component
    definitions for each snapshot by looking up the hashed components already
    parsed in the log.
    """


# =========================================================================
# 2. Commit-Scoped Compaction
# =========================================================================

class CommitScopedCompaction(Feat):
    """
    To keep log file sizes small, the store must support commit-scoped
    compaction (squashing) of redundant intermediate builds.
    """


class CompactionIdentification(Req):
    """
    Identify and group snapshots by their associated `git_commit` identifier
    (ignoring uncommitted / pending snapshots).
    """


class SurvivorResolution(Req):
    """
    For any commit with multiple snapshots, identify the chronologically
    latest snapshot as the "Survivor", and all older snapshots in that group
    as "Redundant Drafts".
    """


class SafeLogCompaction(Req):
    """
    Rewrite the `.libspec/libspec.jsonl` file to drop all snapshot and component
    events associated with Redundant Drafts, retaining only the Survivor's logs
    and uncommitted drafts.
    """


class AtomicLogSwap(Req):
    """
    To prevent database corruption during compaction, the rewrite must stage
    writes to a `.tmp` file and perform an atomic rename/replace operation.
    """


# =========================================================================
# 3. Compaction CLI Command
# =========================================================================

class CompactionCliCommand(Feat):
    """
    A unified compaction and squashing CLI subcommand must be exposed to the
    developer.

    Command Syntax: `libspec compact [--dry-run]`
    """


class CompactionDryRun(Req):
    """
    If `--dry-run` is active, parse the log, compute compaction targets,
    and print a detailed preview of space savings without modifying any file on disk.
    """


class CompactionExecution(Req):
    """
    If executed without `--dry-run`, perform compaction and emit a high-contrast
    summary reporting snapshots pruned, space reclaimed, and compaction completion status.
    """


# =========================================================================
# 4. Store Format Migration
# =========================================================================

class StoreFormatMigration(Req):
    """
    The JsonLinesSpecStore must support a seamless, automated upgrade path for
    legacy log files (where snapshots do not contain a component-to-hash manifest).
    """


class DynamicFormatDetection(Req):
    """
    On startup/replay, if the store encounters any snapshot record that lacks
    the `"components"` manifest dictionary, it must activate the legacy-compat parser mode.
    """


class LegacyReplayCompatibility(Req):
    """
    In legacy-compat mode, resolve component definitions by matching components that
    share the same `snapshot_id`, maintaining 100% backward compatibility.
    """


class AutoUpgradeOnAction(Req):
    """
    When `libspec build` is run on a legacy log, or when `libspec compact` is executed,
    the store must automatically compile a new content-addressable event log, migrating all
    historical snapshots by extracting their original components and generating the manifest dictionaries.
    """


class MigrationSafetyBackup(Req):
    """
    Before executing any format upgrade rewrite, a full backup of the legacy
    `.libspec/libspec.jsonl` file must be generated at `.libspec/libspec.jsonl.bak`.
    """


# =========================================================================
# 5. Local VCS Link Isolation
# =========================================================================

class VcsLinkIsolation(Feat):
    """
    The store must support isolating version control system (VCS) linking events
    to prevent local git working tree dirty states and checkout branch blocks.
    """


class UntrackedSidecarStore(Req):
    """
    Late-bound VCS link events generated by automated Git post-commit hooks
    must be written to a local untracked sidecar file rather than modifying the
    tracked database log file.
    """


class UnifiedSidecarReplay(Req):
    """
    During initialization/replay, the store must seamlessly load and merge link
    events from both the tracked main log file and the untracked sidecar file to
    reconstruct active link relationships.
    """


class AutomatedIgnoreConfiguration(Req):
    """
    When a store is initialized, the system must automatically write a nested
    `.gitignore` file inside the store directory to ignore the untracked sidecar
    and any temporary backup files.
    """


class SelfHealingAutoMigration(Req):
    """
    To ensure the append-only JSON lines log is always kept up to date with the
    latest structural standards, the store must automatically detect legacy or
    malformed entries during initialization.
    
    If any legacy entries are found:
    - The store must run a silent, atomic upgrade migration.
    - It must copy the original log to a `.bak` backup file before any modifications.
    - It must write the upgraded log to a `.tmp` file and perform an atomic `os.replace` swap.
    - In the event of any I/O or migration failure, it must immediately roll back and restore
      the original log from the backup file, clean up temporary artifacts, and gracefully
      proceed without data loss or crashes.
    """
