import pytest
from libspec_scheduler.scheduler import (
    CoLocationSerialization,
    DependencyGraph,
    MicroPatch,
    MicroPatchManager,
    PriorityScheduler,
    TaskState,
)


def test_dependency_graph_cycle_detection():
    """Verify that DependencyGraph successfully detects cycle loops and raises ValueError."""
    graph = DependencyGraph()
    graph.add_node("spec.A")
    graph.add_node("spec.B")
    graph.add_node("spec.C")

    graph.add_edge("spec.B", "spec.A")  # B depends on A
    graph.add_edge("spec.C", "spec.B")  # C depends on B

    # Adding a loop: A depends on C
    with pytest.raises(ValueError, match="Cycle detected"):
        graph.add_edge("spec.A", "spec.C")


def test_dependency_graph_topological_sort():
    """Verify topological sorting order for independent and dependent nodes."""
    graph = DependencyGraph()
    graph.add_node("spec.A")
    graph.add_node("spec.B")
    graph.add_node("spec.C")

    graph.add_edge("spec.B", "spec.A")  # B depends on A (A must run before B)

    order = graph.topological_sort()
    # A must come before B. C can be anywhere.
    assert order.index("spec.A") < order.index("spec.B")
    assert len(order) == 3


def test_priority_sorting():
    """Verify deterministic sorting heuristic:
    1. Critical Path Depth (descending)
    2. Out-degree (descending)
    3. FQN alphabetical fallback.
    """
    graph = DependencyGraph()

    # We construct a graph:
    # A has out-degree 2 (B and C depend on A), depth = 2
    # B has out-degree 1 (D depends on B), depth = 1
    # C has out-degree 0, depth = 0
    # D has out-degree 0, depth = 0
    # E is isolated, depth = 0

    for node in ["spec.A", "spec.B", "spec.C", "spec.D", "spec.E"]:
        graph.add_node(node)

    graph.add_edge("spec.B", "spec.A")
    graph.add_edge("spec.C", "spec.A")
    graph.add_edge("spec.D", "spec.B")

    # Ready nodes initially (nodes with no dependencies in the graph):
    # A and E are ready because they have no dependencies they depend on.
    # Out-degree of A: 2 (B, C depend on A)
    # Out-degree of E: 0
    # Depth of A: 3 (A -> B -> D)
    # Depth of E: 1

    scheduler = PriorityScheduler(graph)
    ready = scheduler.get_ready_tasks()

    # A must be prioritized over E because of higher depth and higher out-degree
    assert ready == ["spec.A", "spec.E"]


def test_co_location_serialization():
    """Verify co-location serialization heuristic.
    If independent components target the same implementation file,
    an implicit edge should be injected between them.
    """
    graph = DependencyGraph()
    graph.add_node("spec.cli.CommandA")
    graph.add_node("spec.cli.CommandB")

    # By default, they are independent and both ready
    scheduler = PriorityScheduler(graph)
    assert set(scheduler.get_ready_tasks()) == {
        "spec.cli.CommandA",
        "spec.cli.CommandB",
    }

    # With co-location constraints, if both implement in "libspec/cli.py":
    coloc = CoLocationSerialization()
    # Let's map both to the same file
    coloc.register_target("spec.cli.CommandA", "libspec/cli.py")
    coloc.register_target("spec.cli.CommandB", "libspec/cli.py")

    coloc.inject_constraints(graph)

    # Now, they are no longer independent; one must depend on the other (ordered alphabetically)
    # CommandB should depend on CommandA
    assert graph.has_dependency("spec.cli.CommandB", "spec.cli.CommandA")

    # Ready tasks should now contain only the first one (CommandA)
    scheduler = PriorityScheduler(graph)
    assert scheduler.get_ready_tasks() == ["spec.cli.CommandA"]


def test_scheduler_state_transitions():
    """Verify task state lifecycle transitions:
    PENDING -> READY -> ASSIGNED -> IMPLEMENTED / FAILED.
    """
    graph = DependencyGraph()
    graph.add_node("spec.A")
    graph.add_node("spec.B")
    graph.add_edge("spec.B", "spec.A")  # B depends on A

    scheduler = PriorityScheduler(graph)

    # Initially: A is READY, B is PENDING
    assert scheduler.get_state("spec.A") == TaskState.READY
    assert scheduler.get_state("spec.B") == TaskState.PENDING

    # Lease A to worker 1
    assignment = scheduler.assign_task("spec.A", "worker_1")
    assert assignment.subagent_id == "worker_1"
    assert scheduler.get_state("spec.A") == TaskState.ASSIGNED

    # Mark A implemented
    scheduler.mark_implemented("spec.A")
    assert scheduler.get_state("spec.A") == TaskState.IMPLEMENTED

    # Now, B should automatically become READY
    assert scheduler.get_state("spec.B") == TaskState.READY


def test_scheduler_task_recycling():
    """Verify task recycling on failure and retry exhaustion."""
    graph = DependencyGraph()
    graph.add_node("spec.A")

    scheduler = PriorityScheduler(graph, max_retries=2)

    # Assign and fail first time
    scheduler.assign_task("spec.A", "worker_1")
    scheduler.mark_failed("spec.A", error_log="Compilation Error")

    # Should be re-queued as READY
    assert scheduler.get_state("spec.A") == TaskState.READY
    assert scheduler.get_retry_count("spec.A") == 1

    # Assign and fail second time (exceeds budget)
    scheduler.assign_task("spec.A", "worker_2")
    scheduler.mark_failed("spec.A", error_log="Linter Error")

    # Should be marked FAILED permanently
    assert scheduler.get_state("spec.A") == TaskState.FAILED


def test_micro_patch_manager():
    """Verify lock-safe micro-patch synchronization."""
    manager = MicroPatchManager()

    patch_1 = MicroPatch(
        patch_id="p1",
        timestamp=100.0,
        subagent_id="worker_1",
        parent_patch_id=None,
        file_path="libspec/cli.py",
        patch_diff="--- old\n+++ new\n",
        description="add cli helper",
    )
    manager.publish(patch_1)

    patch_2 = MicroPatch(
        patch_id="p2",
        timestamp=101.0,
        subagent_id="worker_2",
        parent_patch_id="p1",
        file_path="libspec/store.py",
        patch_diff="--- old2\n+++ new2\n",
        description="tweak store",
    )
    manager.publish(patch_2)

    # Fetch patches since parent None
    all_patches = manager.get_patches_since(None)
    assert len(all_patches) == 2
    assert all_patches[0].patch_id == "p1"

    # Fetch patches since p1
    new_patches = manager.get_patches_since("p1")
    assert len(new_patches) == 1
    assert new_patches[0].patch_id == "p2"
