"""
Specification for the priority-based parallel scheduler and workspace orchestrator.

Note: All components specified here reside in the sibling package `libspec-scheduler`.
"""

from .err import Feat, Req


class PriorityScheduler(Feat):
    """
    Stateful queue coordinator managing tasks for concurrent subagents.

    The scheduler must maintain state transitions:
    - `PENDING`: Dependencies not yet met.
    - `READY`: Dependencies met; in priority queue ready to execute.
    - `ASSIGNED`: Leased to a subagent (tracked with lease timestamp and timeout).
    - `IMPLEMENTED`: Satisfactorily completed and merged.
    - `FAILED`: Permanently failed.

    Priority Heuristics:
    Tasks in the READY queue must be sorted deterministically by:
    1. Critical Path Depth (descending)
    2. Out-Degree (descending)
    3. FQN Reference (alphabetical)
    """


class DependencyGraph(Req):
    """
    Constructs the directed acyclic graph (DAG) of component dependencies.

    The graph builder must:
    - Parse logical dependencies from SpecStore ledger events.
    - Validate that the topology is acyclic, raising a CycleError if a dependency loop is detected.
    - Support dynamically adding/removing edges.
    """


class CoLocationSerialization(Req):
    """
    Implicit constraint injection to mitigate git merge conflicts.

    Heuristic:
    - Scan components to find their implementation target files (e.g. by FQN prefix patterns or target specs).
    - If two logically independent components target the same module or file (e.g., `cli.py`), dynamically inject an implicit dependency edge between them.
    - This serializes their execution, preventing parallel subagents from editing the same file concurrently.
    """


class MicroPatchManager(Req):
    """
    Lock-safe event log managing real-time incremental code changes.

    The manager must:
    - Maintain a thread-safe chronological list of `MicroPatch` entries.
    - Allow subagents to publish patches.
    - Support fetching slices of new patches published since a worker's last sync ID (`parent_patch_id`), enabling local rebases during active implementation.
    """


class WorkerOrchestrator(Feat):
    """
    Os-level manager setting up subagent sandboxes and handling integration.
    """


class GitWorktreeSandbox(Req):
    """
    Worker isolation using Git worktrees.

    Each assigned task must execute inside a unique git worktree directory
    (e.g., in a temporary workspace directory under `/tmp` or the project root).
    This ensures that:
    - Filesystem operations, package virtual environments, and local pytest invocations are fully isolated.
    - Downstream tasks do not suffer from database locks or concurrent file writes.
    """


class IntegrationMergeLoop(Req):
    """
    Merge and claim workflow on task success.

    Upon a subagent successfully completing a task (passing local tests):
    - Merge the subagent's temporary branch into the active development branch.
    - In the event of a clean merge, append the `Implemented` claim to the SpecStore database.
    - Mark the node as `IMPLEMENTED` in the active scheduler session to unlock dependents.
    - Clean up the Git worktree.
    """


class FailureAndRecycling(Req):
    """
    Task recycling and error escalation.

    If a subagent task fails:
    - Verify remaining retry budget.
    - If budget is left, re-queue the task as `READY`, supplying test logs/linter diagnostics as context for the next subagent.
    - If budget is exhausted, mark the task as `FAILED` and block downstream dependent tasks, notifying the orchestrator/developer.
    """


class TaskStateSpec(Req):
    """
    Execution states for specification task scheduling.
    
    States:
    - `PENDING`: Dependencies not yet completed.
    - `READY`: All dependencies completed; ready to assign.
    - `ASSIGNED`: Leased to a subagent worker.
    - `IMPLEMENTED`: Merged and verified successfully.
    - `FAILED`: Compilation or test verification failed.
    """


class MicroPatchSpec(Req):
    """
    Data record for sharing incremental code diffs between parallel workers.

    Fields:
    - `patch_id` (str): Unique ID of the patch.
    - `timestamp` (datetime): Creation timestamp.
    - `subagent_id` (str): ID of the authoring subagent.
    - `parent_patch_id` (str | None): ID of the previous patch in the log.
    - `file_path` (str): Relative file path of the modification.
    - `patch_diff` (str): Unified diff content.
    - `description` (str): Summary of changes.
    """


class TaskAssignmentSpec(Req):
    """
    Metadata tracking a leased component task assignment.

    Fields:
    - `session_id` (str): ID of the active scheduler session.
    - `subagent_id` (str): ID of the assigned subagent.
    - `component_ref` (str): FQN of the assigned component.
    - `assigned_at` (datetime): Lease start timestamp.
    - `timeout` (float): Duration in seconds before the lease expires.
    """


class ReplDashboardCommand(Feat):
    """
    Interactive command to view current scheduler state and progress overview in the REPL.

    Command Syntax: `dashboard` or aliases `dash`, `db`.
    The command must print:
    - Overall completion progress bar.
    - Statistics of task counts (Pending, Ready, Assigned, Implemented, Failed).
    - Status of active workers and their current leases.
    - Recent micro-patch activity.
    - List of next ready tasks.
    
    If no scheduler is initialized, it must print a clear error and help message.
    """
