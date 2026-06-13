import datetime
import threading
from enum import Enum
from graphlib import CycleError, TopologicalSorter


class TaskState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    ASSIGNED = "ASSIGNED"
    IMPLEMENTED = "IMPLEMENTED"
    FAILED = "FAILED"


class MicroPatch:
    def __init__(
        self,
        patch_id: str,
        timestamp: float,
        subagent_id: str,
        parent_patch_id: str | None,
        file_path: str,
        patch_diff: str,
        description: str,
    ):
        self.patch_id = patch_id
        self.timestamp = timestamp
        self.subagent_id = subagent_id
        self.parent_patch_id = parent_patch_id
        self.file_path = file_path
        self.patch_diff = patch_diff
        self.description = description


class TaskAssignment:
    def __init__(
        self,
        session_id: str,
        subagent_id: str,
        component_ref: str,
        assigned_at: float,
        timeout: float,
    ):
        self.session_id = session_id
        self.subagent_id = subagent_id
        self.component_ref = component_ref
        self.assigned_at = assigned_at
        self.timeout = timeout


class DependencyGraph:
    def __init__(self):
        # adjacency list: u -> list of v (meaning u depends on v, i.e., v runs before u)
        self.dependencies: dict[str, set[str]] = {}
        self.nodes: set[str] = set()

    def add_node(self, node: str) -> None:
        self.nodes.add(node)
        if node not in self.dependencies:
            self.dependencies[node] = set()

    def add_edge(self, u: str, v: str) -> None:
        # u depends on v
        self.add_node(u)
        self.add_node(v)
        self.dependencies[u].add(v)
        # Validate cycle
        try:
            ts = TopologicalSorter(self.dependencies)
            ts.prepare()
        except CycleError:
            self.dependencies[u].remove(v)
            raise ValueError("Cycle detected in dependency graph")

    def has_dependency(self, u: str, v: str) -> bool:
        """Returns True if u depends on v directly."""
        return u in self.dependencies and v in self.dependencies[u]

    def is_reachable(self, u: str, v: str, visited: set[str] | None = None) -> bool:
        """Returns True if u can reach v transitively (meaning u depends on v transitively)."""
        if u == v:
            return True
        if visited is None:
            visited = set()
        visited.add(u)
        for dep in self.dependencies.get(u, []):
            if dep not in visited:
                if self.is_reachable(dep, v, visited):
                    return True
        return False

    def topological_sort(self) -> list[str]:
        ts = TopologicalSorter(self.dependencies)
        # Add isolated nodes that have no edges
        for node in self.nodes:
            if node not in self.dependencies:
                ts.add(node)
        return list(ts.static_order())


class CoLocationSerialization:
    def __init__(self):
        self.targets: dict[str, str] = {}

    def register_target(self, ref: str, file_path: str) -> None:
        self.targets[ref] = file_path

    def inject_constraints(self, graph: DependencyGraph) -> None:
        # Group components by target file
        file_to_refs: dict[str, list[str]] = {}
        for ref, filepath in self.targets.items():
            file_to_refs.setdefault(filepath, []).append(ref)

        for filepath, refs in file_to_refs.items():
            if len(refs) < 2:
                continue
            # Sort refs alphabetically to establish a deterministic serialization order
            sorted_refs = sorted(refs)
            for i in range(len(sorted_refs)):
                for j in range(i + 1, len(sorted_refs)):
                    u = sorted_refs[i]
                    v = sorted_refs[j]
                    # If they are independent (neither depends transitively on the other)
                    if not graph.is_reachable(u, v) and not graph.is_reachable(v, u):
                        # Inject dependency: v depends on u (meaning u runs before v)
                        try:
                            graph.add_edge(v, u)
                        except ValueError:
                            # In case of cycle validation failure, ignore
                            pass


class PriorityScheduler:
    def __init__(self, graph: DependencyGraph, max_retries: int = 3):
        self.graph = graph
        self.max_retries = max_retries
        self.states: dict[str, TaskState] = {}
        self.retries: dict[str, int] = {}
        self.assignments: dict[str, TaskAssignment] = {}
        self.lock = threading.Lock()

        # Initialize states
        for node in self.graph.nodes:
            self.states[node] = TaskState.PENDING
            self.retries[node] = 0

        self._update_states()

    def _update_states(self) -> None:
        """Update transitions from PENDING to READY if all dependencies are IMPLEMENTED."""
        for node in self.graph.nodes:
            if self.states[node] == TaskState.PENDING:
                deps = self.graph.dependencies.get(node, set())
                if all(self.states.get(d) == TaskState.IMPLEMENTED for d in deps):
                    self.states[node] = TaskState.READY

    def get_state(self, ref: str) -> TaskState:
        with self.lock:
            return self.states.get(ref, TaskState.PENDING)

    def get_retry_count(self, ref: str) -> int:
        with self.lock:
            return self.retries.get(ref, 0)

    def _get_node_depth(self, node: str, memo: dict[str, int]) -> int:
        if node in memo:
            return memo[node]
        deps = self.graph.dependencies.get(node, set())
        if not deps:
            memo[node] = 1
            return 1
        depth = 1 + max(self._get_node_depth(d, memo) for d in deps)
        memo[node] = depth
        return depth

    def _get_node_out_degree(self, node: str) -> int:
        # Count how many other nodes depend directly on this node
        count = 0
        for u, deps in self.graph.dependencies.items():
            if node in deps:
                count += 1
        return count

    def get_ready_tasks(self) -> list[str]:
        with self.lock:
            self._update_states()
            ready_nodes = [
                node for node, state in self.states.items() if state == TaskState.READY
            ]
            if not ready_nodes:
                return []

            # Compute heuristics
            memo: dict[str, int] = {}
            node_heuristics = []
            for node in ready_nodes:
                depth = self._get_node_depth(node, memo)
                out_degree = self._get_node_out_degree(node)
                node_heuristics.append((node, depth, out_degree))

            # Sort:
            # 1. Depth (descending)
            # 2. Out-degree (descending)
            # 3. Reference (alphabetical)
            node_heuristics.sort(key=lambda x: (-x[1], -x[2], x[0]))
            return [x[0] for x in node_heuristics]

    def assign_task(
        self, ref: str, subagent_id: str, timeout: float = 300.0
    ) -> TaskAssignment:
        with self.lock:
            if self.states.get(ref) != TaskState.READY:
                raise ValueError(
                    f"Task {ref} is not READY for assignment (state={self.states.get(ref)})"
                )
            self.states[ref] = TaskState.ASSIGNED
            assignment = TaskAssignment(
                session_id=f"session_{datetime.datetime.now().timestamp()}",
                subagent_id=subagent_id,
                component_ref=ref,
                assigned_at=datetime.datetime.now().timestamp(),
                timeout=timeout,
            )
            self.assignments[ref] = assignment
            return assignment

    def mark_implemented(self, ref: str) -> None:
        with self.lock:
            self.states[ref] = TaskState.IMPLEMENTED
            if ref in self.assignments:
                del self.assignments[ref]
            self._update_states()

    def mark_failed(self, ref: str, error_log: str = "") -> None:
        with self.lock:
            self.retries[ref] += 1
            if ref in self.assignments:
                del self.assignments[ref]
            if self.retries[ref] < self.max_retries:
                self.states[ref] = TaskState.READY
            else:
                self.states[ref] = TaskState.FAILED


class MicroPatchManager:
    def __init__(self):
        self.patches: list[MicroPatch] = []
        self.lock = threading.Lock()

    def publish(self, patch: MicroPatch) -> None:
        with self.lock:
            self.patches.append(patch)

    def get_patches_since(self, parent_patch_id: str | None) -> list[MicroPatch]:
        with self.lock:
            if parent_patch_id is None:
                return list(self.patches)
            # Find the parent index
            idx = -1
            for i, patch in enumerate(self.patches):
                if patch.patch_id == parent_patch_id:
                    idx = i
                    break
            if idx == -1:
                # Parent patch ID not found, return all
                return list(self.patches)
            return list(self.patches[idx + 1 :])
