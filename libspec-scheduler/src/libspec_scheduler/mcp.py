import datetime
import json
import uuid

from libspec.mcp_server import mcp

# Dynamic compile_live_spec imports
from libspec.util import compile_live_spec
from libspec_scheduler.scheduler import (
    CoLocationSerialization,
    DependencyGraph,
    MicroPatch,
    MicroPatchManager,
    PriorityScheduler,
)

# Global coordination states
_scheduler: PriorityScheduler | None = None
_patch_manager = MicroPatchManager()


def reset_global_scheduler():
    global _scheduler, _patch_manager
    _scheduler = None
    _patch_manager = MicroPatchManager()


def get_target_file(ref: str) -> str:
    parts = ref.split(".")
    if len(parts) >= 3:
        pkg = parts[1]
        mod = parts[2]
        if pkg == "scheduler":
            return f"libspec-scheduler/src/libspec_scheduler/{mod}.py"
        else:
            return f"libspec/{pkg}.py"
    return "libspec/common.py"


@mcp.tool(name="init_scheduler")
def init_scheduler_handler() -> str:
    """
    Initialize the stateful scheduler session with the workspace dependency graph.
    """
    global _scheduler
    try:
        new_components, _ = compile_live_spec()
    except Exception as e:
        return f"Error compiling live spec: {e}"

    graph = DependencyGraph()
    for c in new_components:
        # Avoid including external dependencies in scheduling queue if marked is_dependency
        if not getattr(c, "is_dependency", False):
            graph.add_node(c.ref)

    # Load dependencies from inherits
    for c in new_components:
        if not getattr(c, "is_dependency", False):
            if c.inherits:
                for dep in c.inherits:
                    if dep in graph.nodes:
                        graph.add_edge(c.ref, dep)

    # Inject co-location serialization constraints
    coloc = CoLocationSerialization()
    for node in graph.nodes:
        coloc.register_target(node, get_target_file(node))
    coloc.inject_constraints(graph)

    _scheduler = PriorityScheduler(graph)
    return f"Scheduler successfully initialized with {len(graph.nodes)} tasks."


@mcp.tool(name="request_task")
def request_task_handler(subagent_id: str) -> str:
    """
    Acquire the next prioritized READY task for a subagent worker.
    """
    global _scheduler
    if _scheduler is None:
        return "Error: Scheduler is not initialized. Call init_scheduler first."

    ready = _scheduler.get_ready_tasks()
    if not ready:
        return "No ready tasks available."

    task_ref = ready[0]
    try:
        assignment = _scheduler.assign_task(task_ref, subagent_id)
        return json.dumps(
            {
                "session_id": assignment.session_id,
                "subagent_id": assignment.subagent_id,
                "component_ref": assignment.component_ref,
                "assigned_at": assignment.assigned_at,
                "timeout": assignment.timeout,
            }
        )
    except Exception as e:
        return f"Error assigning task: {e}"


@mcp.tool(name="report_task_status")
def report_task_status_handler(
    subagent_id: str, component_ref: str, status: str, error_log: str = ""
) -> str:
    """
    Update the scheduler state of a leased task.
    """
    global _scheduler
    if _scheduler is None:
        return "Error: Scheduler is not initialized."

    state = _scheduler.get_state(component_ref)
    if state != "ASSIGNED":
        return f"Error: Task {component_ref} is not currently ASSIGNED (current state={state})."

    assignment = _scheduler.assignments.get(component_ref)
    if assignment and assignment.subagent_id != subagent_id:
        return f"Error: Task {component_ref} is assigned to {assignment.subagent_id}, not {subagent_id}."

    if status == "success":
        _scheduler.mark_implemented(component_ref)
        # In a real run, the orchestrator merges the worktree. Here we record it in scheduler.
        return f"Task {component_ref} successfully marked as IMPLEMENTED."
    elif status == "failure":
        _scheduler.mark_failed(component_ref, error_log)
        new_state = _scheduler.get_state(component_ref)
        return f"Task {component_ref} failed and re-queued. New state: {new_state}."
    else:
        return f"Error: Unknown status '{status}'."


@mcp.tool(name="publish_micro_patch")
def publish_micro_patch_handler(
    subagent_id: str,
    file_path: str,
    patch_diff: str,
    description: str,
    patch_id: str | None = None,
) -> str:
    """
    Publish an incremental unified diff patch.
    """
    pid = patch_id or f"patch_{uuid.uuid4().hex[:8]}"
    patch = MicroPatch(
        patch_id=pid,
        timestamp=datetime.datetime.now().timestamp(),
        subagent_id=subagent_id,
        parent_patch_id=None,  # Handled simplistically in log
        file_path=file_path,
        patch_diff=patch_diff,
        description=description,
    )
    _patch_manager.publish(patch)
    return f"Patch {pid} successfully published."


@mcp.tool(name="get_micro_patches")
def get_micro_patches_handler(parent_patch_id: str | None = None) -> str:
    """
    Retrieve incremental patches published since a parent patch ID.
    """
    patches = _patch_manager.get_patches_since(parent_patch_id)
    result = []
    for p in patches:
        result.append(
            {
                "patch_id": p.patch_id,
                "timestamp": p.timestamp,
                "subagent_id": p.subagent_id,
                "parent_patch_id": p.parent_patch_id,
                "file_path": p.file_path,
                "patch_diff": p.patch_diff,
                "description": p.description,
            }
        )
    return json.dumps(result)


@mcp.resource("scheduler://dag")
def scheduler_dag_resource() -> str:
    """
    Get the JSON serialized representation of the active scheduler DAG.
    """
    global _scheduler
    if _scheduler is None:
        return json.dumps({"error": "Scheduler is not initialized."})

    nodes = list(_scheduler.graph.nodes)
    edges = []
    for u, deps in _scheduler.graph.dependencies.items():
        for v in deps:
            edges.append({"from": u, "to": v})

    states = {}
    for node in nodes:
        states[node] = _scheduler.states.get(node, "PENDING")

    return json.dumps(
        {
            "nodes": nodes,
            "edges": edges,
            "states": states,
        }
    )


@mcp.resource("scheduler://active_workers")
def active_workers_resource() -> str:
    """
    Get the list of active tasks leased to workers.
    """
    global _scheduler
    if _scheduler is None:
        return json.dumps([])

    result = []
    for ref, assignment in _scheduler.assignments.items():
        result.append(
            {
                "component_ref": ref,
                "subagent_id": assignment.subagent_id,
                "assigned_at": assignment.assigned_at,
                "timeout": assignment.timeout,
            }
        )
    return json.dumps(result)


@mcp.resource("scheduler://patch_log")
def patch_log_resource() -> str:
    """
    Get the complete chronological micro-patch log.
    """
    result = []
    for p in _patch_manager.patches:
        result.append(
            {
                "patch_id": p.patch_id,
                "timestamp": p.timestamp,
                "subagent_id": p.subagent_id,
                "parent_patch_id": p.parent_patch_id,
                "file_path": p.file_path,
                "description": p.description,
            }
        )
    return json.dumps(result)
