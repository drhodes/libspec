#!/usr/bin/env python3
"""
Standalone test runner for Todo API (no pytest required).
Tests all endpoints and validates all constraints.
"""

import sys
import traceback
from main import (
    TodoAPI, Todo, TodoStatus,
    CreateTodoRequest, UpdateTodoRequest, ChangeStatusRequest, QueryRequest,
    ValidationError, NotFoundError, VersionConflictError, InvalidTransitionError
)


class TestRunner:
    """Simple test runner without external dependencies."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def test(self, name):
        """Decorator to register a test."""
        def decorator(func):
            self.tests.append((name, func))
            return func
        return decorator
    
    def assert_equal(self, actual, expected, msg=""):
        """Assert two values are equal."""
        if actual != expected:
            raise AssertionError(
                f"{msg}\nExpected: {expected}\nActual: {actual}"
            )
    
    def assert_true(self, value, msg=""):
        """Assert value is true."""
        if not value:
            raise AssertionError(f"{msg}\nExpected True, got {value}")
    
    def assert_raises(self, exception_class, func, msg_pattern=None):
        """Assert function raises expected exception."""
        try:
            func()
            raise AssertionError(
                f"Expected {exception_class.__name__} but no exception was raised"
            )
        except exception_class as e:
            if msg_pattern and msg_pattern not in str(e):
                raise AssertionError(
                    f"Exception message '{e}' does not contain '{msg_pattern}'"
                )
        except Exception as e:
            raise AssertionError(
                f"Expected {exception_class.__name__} but got {type(e).__name__}: {e}"
            )
    
    def run(self):
        """Run all registered tests."""
        print(f"\nRunning {len(self.tests)} tests...\n")
        
        for name, test_func in self.tests:
            try:
                test_func()
                print(f"✓ {name}")
                self.passed += 1
            except Exception as e:
                print(f"✗ {name}")
                print(f"  {str(e)}")
                if "--verbose" in sys.argv:
                    traceback.print_exc()
                self.failed += 1
        
        print(f"\n{'='*60}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print(f"{'='*60}\n")
        
        return self.failed == 0


# Initialize test runner
runner = TestRunner()


# ============================================================================
# Test: version()
# ============================================================================

@runner.test("version() returns version string")
def test_version():
    api = TodoAPI()
    version = api.version()
    runner.assert_true(isinstance(version, str))
    runner.assert_true(len(version) > 0)


# ============================================================================
# Test: create_todo() - REQ-001
# ============================================================================

@runner.test("create_todo() with minimal fields")
def test_create_minimal():
    api = TodoAPI()
    req = CreateTodoRequest(title="New Task")
    todo = api.create_todo(req)
    
    runner.assert_true(todo.id.startswith("todo_"))
    runner.assert_equal(todo.title, "New Task")
    runner.assert_equal(todo.status, TodoStatus.TODO.value)
    runner.assert_equal(todo.version, 1)


@runner.test("create_todo() with all fields")
def test_create_full():
    api = TodoAPI()
    req = CreateTodoRequest(
        title="Full Task",
        description="Details",
        priority=5,
        assignee="bob"
    )
    todo = api.create_todo(req)
    
    runner.assert_equal(todo.title, "Full Task")
    runner.assert_equal(todo.description, "Details")
    runner.assert_equal(todo.priority, 5)
    runner.assert_equal(todo.assignee, "bob")


@runner.test("create_todo() with parent")
def test_create_with_parent():
    api = TodoAPI()
    parent = api.create_todo(CreateTodoRequest(title="Parent"))
    child = api.create_todo(CreateTodoRequest(title="Child", parent_id=parent.id))
    
    runner.assert_equal(child.parent_id, parent.id)


@runner.test("CONST-001: create_todo() rejects priority < 1")
def test_create_invalid_priority_low():
    api = TodoAPI()
    runner.assert_raises(
        ValidationError,
        lambda: api.create_todo(CreateTodoRequest(title="Task", priority=0)),
        "Priority must be between 1 and 5"
    )


@runner.test("CONST-001: create_todo() rejects priority > 5")
def test_create_invalid_priority_high():
    api = TodoAPI()
    runner.assert_raises(
        ValidationError,
        lambda: api.create_todo(CreateTodoRequest(title="Task", priority=6)),
        "Priority must be between 1 and 5"
    )


@runner.test("CONST-003: create_todo() rejects nonexistent parent")
def test_create_nonexistent_parent():
    api = TodoAPI()
    runner.assert_raises(
        NotFoundError,
        lambda: api.create_todo(CreateTodoRequest(title="Task", parent_id="todo_999")),
        "not found"
    )


@runner.test("create_todo() generates unique IDs")
def test_create_unique_ids():
    api = TodoAPI()
    todo1 = api.create_todo(CreateTodoRequest(title="Task 1"))
    todo2 = api.create_todo(CreateTodoRequest(title="Task 2"))
    
    runner.assert_true(todo1.id != todo2.id)


# ============================================================================
# Test: update_todo() - REQ-002
# ============================================================================

@runner.test("update_todo() updates title")
def test_update_title():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Original"))
    updated = api.update_todo(UpdateTodoRequest(
        todo_id=todo.id,
        version=todo.version,
        title="Updated"
    ))
    
    runner.assert_equal(updated.title, "Updated")
    runner.assert_equal(updated.version, 2)


@runner.test("update_todo() updates multiple fields")
def test_update_multiple():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Original"))
    updated = api.update_todo(UpdateTodoRequest(
        todo_id=todo.id,
        version=todo.version,
        title="New Title",
        description="New Desc",
        priority=5
    ))
    
    runner.assert_equal(updated.title, "New Title")
    runner.assert_equal(updated.description, "New Desc")
    runner.assert_equal(updated.priority, 5)


@runner.test("CONST-001: update_todo() rejects invalid priority")
def test_update_invalid_priority():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    runner.assert_raises(
        ValidationError,
        lambda: api.update_todo(UpdateTodoRequest(
            todo_id=todo.id,
            version=todo.version,
            priority=10
        )),
        "Priority must be between 1 and 5"
    )


@runner.test("CONST-003: update_todo() rejects nonexistent todo")
def test_update_not_found():
    api = TodoAPI()
    runner.assert_raises(
        NotFoundError,
        lambda: api.update_todo(UpdateTodoRequest(
            todo_id="todo_999",
            version=1,
            title="New"
        )),
        "not found"
    )


@runner.test("CONST-004: update_todo() rejects version mismatch")
def test_update_version_conflict():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    runner.assert_raises(
        VersionConflictError,
        lambda: api.update_todo(UpdateTodoRequest(
            todo_id=todo.id,
            version=99,
            title="New"
        )),
        "Version mismatch"
    )


# ============================================================================
# Test: change_status() - REQ-003
# ============================================================================

@runner.test("change_status() todo -> in_progress")
def test_status_todo_to_in_progress():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    updated = api.change_status(ChangeStatusRequest(
        todo_id=todo.id,
        version=todo.version,
        status=TodoStatus.IN_PROGRESS.value
    ))
    
    runner.assert_equal(updated.status, TodoStatus.IN_PROGRESS.value)
    runner.assert_equal(updated.version, 2)


@runner.test("change_status() in_progress -> done")
def test_status_in_progress_to_done():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    todo = api.change_status(ChangeStatusRequest(
        todo_id=todo.id,
        version=todo.version,
        status=TodoStatus.IN_PROGRESS.value
    ))
    updated = api.change_status(ChangeStatusRequest(
        todo_id=todo.id,
        version=todo.version,
        status=TodoStatus.DONE.value
    ))
    
    runner.assert_equal(updated.status, TodoStatus.DONE.value)


@runner.test("CONST-002: change_status() rejects done -> in_progress")
def test_status_invalid_done_to_in_progress():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    todo = api.change_status(ChangeStatusRequest(
        todo_id=todo.id,
        version=todo.version,
        status=TodoStatus.DONE.value
    ))
    
    runner.assert_raises(
        InvalidTransitionError,
        lambda: api.change_status(ChangeStatusRequest(
            todo_id=todo.id,
            version=todo.version,
            status=TodoStatus.IN_PROGRESS.value
        )),
        "Invalid transition"
    )


@runner.test("CONST-002: change_status() rejects archived -> any")
def test_status_no_transitions_from_archived():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    todo = api.change_status(ChangeStatusRequest(
        todo_id=todo.id,
        version=todo.version,
        status=TodoStatus.ARCHIVED.value
    ))
    
    runner.assert_raises(
        InvalidTransitionError,
        lambda: api.change_status(ChangeStatusRequest(
            todo_id=todo.id,
            version=todo.version,
            status=TodoStatus.TODO.value
        )),
        "Invalid transition"
    )


@runner.test("CONST-003: change_status() rejects nonexistent todo")
def test_status_not_found():
    api = TodoAPI()
    runner.assert_raises(
        NotFoundError,
        lambda: api.change_status(ChangeStatusRequest(
            todo_id="todo_999",
            version=1,
            status=TodoStatus.DONE.value
        )),
        "not found"
    )


@runner.test("CONST-004: change_status() rejects version mismatch")
def test_status_version_conflict():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    runner.assert_raises(
        VersionConflictError,
        lambda: api.change_status(ChangeStatusRequest(
            todo_id=todo.id,
            version=99,
            status=TodoStatus.DONE.value
        )),
        "Version mismatch"
    )


# ============================================================================
# Test: assign() - REQ-004
# ============================================================================

@runner.test("assign() assigns todo to user")
def test_assign():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    updated = api.assign(todo.id, "alice", todo.version)
    
    runner.assert_equal(updated.assignee, "alice")
    runner.assert_equal(updated.version, 2)


@runner.test("assign() can reassign todo")
def test_reassign():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    todo = api.assign(todo.id, "alice", todo.version)
    updated = api.assign(todo.id, "bob", todo.version)
    
    runner.assert_equal(updated.assignee, "bob")
    runner.assert_equal(updated.version, 3)


@runner.test("CONST-003: assign() rejects nonexistent todo")
def test_assign_not_found():
    api = TodoAPI()
    runner.assert_raises(
        NotFoundError,
        lambda: api.assign("todo_999", "user", 1),
        "not found"
    )


@runner.test("CONST-004: assign() rejects version mismatch")
def test_assign_version_conflict():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    runner.assert_raises(
        VersionConflictError,
        lambda: api.assign(todo.id, "user", 99),
        "Version mismatch"
    )


# ============================================================================
# Test: archive() - REQ-006
# ============================================================================

@runner.test("archive() archives todo")
def test_archive():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    archived = api.archive(todo.id, todo.version)
    
    runner.assert_equal(archived.status, TodoStatus.ARCHIVED.value)
    runner.assert_equal(archived.version, 2)


@runner.test("CONST-005: archive() allows archived children")
def test_archive_with_archived_children():
    api = TodoAPI()
    parent = api.create_todo(CreateTodoRequest(title="Parent"))
    child = api.create_todo(CreateTodoRequest(title="Child", parent_id=parent.id))
    
    # Archive child first
    api.archive(child.id, child.version)
    
    # Should be able to archive parent
    archived = api.archive(parent.id, parent.version)
    runner.assert_equal(archived.status, TodoStatus.ARCHIVED.value)


@runner.test("CONST-005: archive() rejects active children")
def test_archive_with_active_children():
    api = TodoAPI()
    parent = api.create_todo(CreateTodoRequest(title="Parent"))
    child = api.create_todo(CreateTodoRequest(title="Child", parent_id=parent.id))
    
    runner.assert_raises(
        ValidationError,
        lambda: api.archive(parent.id, parent.version),
        "Cannot archive todo with"
    )


@runner.test("CONST-003: archive() rejects nonexistent todo")
def test_archive_not_found():
    api = TodoAPI()
    runner.assert_raises(
        NotFoundError,
        lambda: api.archive("todo_999", 1),
        "not found"
    )


@runner.test("CONST-004: archive() rejects version mismatch")
def test_archive_version_conflict():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    runner.assert_raises(
        VersionConflictError,
        lambda: api.archive(todo.id, 99),
        "Version mismatch"
    )


# ============================================================================
# Test: get()
# ============================================================================

@runner.test("get() retrieves todo")
def test_get():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(title="Task"))
    retrieved = api.get(todo.id)
    
    runner.assert_equal(retrieved.id, todo.id)
    runner.assert_equal(retrieved.title, todo.title)


@runner.test("CONST-003: get() rejects nonexistent todo")
def test_get_not_found():
    api = TodoAPI()
    runner.assert_raises(
        NotFoundError,
        lambda: api.get("todo_999"),
        "not found"
    )


# ============================================================================
# Test: query() - REQ-005
# ============================================================================

@runner.test("query() returns all todos")
def test_query_all():
    api = TodoAPI()
    for i in range(5):
        api.create_todo(CreateTodoRequest(title=f"Task {i}"))
    
    results = api.query(QueryRequest())
    runner.assert_equal(len(results), 5)


@runner.test("query() filters by status")
def test_query_by_status():
    api = TodoAPI()
    todo1 = api.create_todo(CreateTodoRequest(title="Task 1"))
    todo2 = api.create_todo(CreateTodoRequest(title="Task 2"))
    
    api.change_status(ChangeStatusRequest(
        todo_id=todo1.id,
        version=todo1.version,
        status=TodoStatus.IN_PROGRESS.value
    ))
    
    results = api.query(QueryRequest(status=TodoStatus.IN_PROGRESS.value))
    runner.assert_equal(len(results), 1)
    runner.assert_equal(results[0].id, todo1.id)


@runner.test("query() filters by assignee")
def test_query_by_assignee():
    api = TodoAPI()
    api.create_todo(CreateTodoRequest(title="Task 1", assignee="alice"))
    api.create_todo(CreateTodoRequest(title="Task 2", assignee="bob"))
    api.create_todo(CreateTodoRequest(title="Task 3", assignee="alice"))
    
    results = api.query(QueryRequest(assignee="alice"))
    runner.assert_equal(len(results), 2)
    runner.assert_true(all(t.assignee == "alice" for t in results))


@runner.test("query() filters by parent_id")
def test_query_by_parent():
    api = TodoAPI()
    parent = api.create_todo(CreateTodoRequest(title="Parent"))
    
    for i in range(3):
        api.create_todo(CreateTodoRequest(title=f"Child {i}", parent_id=parent.id))
    
    api.create_todo(CreateTodoRequest(title="Other"))
    
    results = api.query(QueryRequest(parent_id=parent.id))
    runner.assert_equal(len(results), 3)


@runner.test("query() filters by priority range")
def test_query_by_priority():
    api = TodoAPI()
    for priority in [1, 2, 3, 4, 5]:
        api.create_todo(CreateTodoRequest(title=f"Task P{priority}", priority=priority))
    
    results = api.query(QueryRequest(min_priority=2, max_priority=4))
    runner.assert_equal(len(results), 3)


@runner.test("query() combines multiple filters")
def test_query_multiple_filters():
    api = TodoAPI()
    todo1 = api.create_todo(CreateTodoRequest(title="Task 1", assignee="alice", priority=5))
    api.create_todo(CreateTodoRequest(title="Task 2", assignee="alice", priority=1))
    api.create_todo(CreateTodoRequest(title="Task 3", assignee="bob", priority=5))
    
    api.change_status(ChangeStatusRequest(
        todo_id=todo1.id,
        version=todo1.version,
        status=TodoStatus.IN_PROGRESS.value
    ))
    
    results = api.query(QueryRequest(
        assignee="alice",
        status=TodoStatus.IN_PROGRESS.value,
        min_priority=4
    ))
    
    runner.assert_equal(len(results), 1)
    runner.assert_equal(results[0].id, todo1.id)


# ============================================================================
# Test: Status Transitions
# ============================================================================

@runner.test("All valid status transitions work")
def test_valid_transitions():
    valid = [
        (TodoStatus.TODO.value, TodoStatus.IN_PROGRESS.value),
        (TodoStatus.TODO.value, TodoStatus.DONE.value),
        (TodoStatus.TODO.value, TodoStatus.ARCHIVED.value),
        (TodoStatus.IN_PROGRESS.value, TodoStatus.TODO.value),
        (TodoStatus.IN_PROGRESS.value, TodoStatus.DONE.value),
        (TodoStatus.DONE.value, TodoStatus.ARCHIVED.value),
    ]
    
    for from_status, to_status in valid:
        runner.assert_true(
            TodoStatus.can_transition(from_status, to_status),
            f"{from_status} -> {to_status} should be valid"
        )


# ============================================================================
# Run all tests
# ============================================================================

if __name__ == "__main__":
    success = runner.run()
    sys.exit(0 if success else 1)
