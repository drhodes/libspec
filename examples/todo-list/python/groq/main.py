from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import uuid
import pytest


# =========================
# Data Models
# =========================

@dataclass
class TodoItem:
    todo_id: str
    title: str
    description: str
    status: str           # open | in_progress | blocked | done | archived
    priority: int         # 1..5
    owner: str
    assignee: Optional[str]
    due_date: Optional[str]
    parent_id: Optional[str]
    version: int = 0
    deleted: bool = False


@dataclass
class CreateTodoRequest:
    title: str
    description: str
    owner: str
    priority: int
    due_date: Optional[str] = None
    parent_id: Optional[str] = None


@dataclass
class UpdateTodoRequest:
    todo_id: str
    version: int
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    due_date: Optional[str] = None
    assignee: Optional[str] = None


@dataclass
class StatusChangeRequest:
    todo_id: str
    new_status: str
    version: int


@dataclass
class TodoQuery:
    owner: Optional[str] = None
    assignee: Optional[str] = None
    status: Optional[str] = None
    due_before: Optional[str] = None
    include_archived: bool = False


# =========================
# Errors
# =========================

class TodoError(Exception): pass
class NotFound(TodoError): pass
class InvalidOperation(TodoError): pass
class VersionConflict(TodoError): pass


# =========================
# API Implementation
# =========================

class TodoAPI:
    VALID_STATUSES = {"open", "in_progress", "blocked", "done", "archived"}
    STATUS_TRANSITIONS = {
        "open": {"in_progress", "blocked", "done"},
        "in_progress": {"blocked", "done"},
        "blocked": {"in_progress"},
        "done": {"archived"},
        "archived": set(),
    }

    def __init__(self):
        self._todos: Dict[str, TodoItem] = {}

    def version(self) -> int:
        return 1

    def _get(self, todo_id: str) -> TodoItem:
        if todo_id not in self._todos:
            raise NotFound(f"Unknown todo_id: {todo_id}")
        return self._todos[todo_id]

    def _check_version(self, todo: TodoItem, version: int):
        if todo.version != version:
            raise VersionConflict("Version mismatch")

    def create_todo(self, req: CreateTodoRequest) -> TodoItem:
        if not (1 <= req.priority <= 5):
            raise InvalidOperation("Priority must be between 1 and 5")

        todo_id = str(uuid.uuid4())
        todo = TodoItem(
            todo_id=todo_id,
            title=req.title,
            description=req.description,
            status="open",
            priority=req.priority,
            owner=req.owner,
            assignee=None,
            due_date=req.due_date,
            parent_id=req.parent_id,
        )
        self._todos[todo_id] = todo
        return todo

    def update_todo(self, req: UpdateTodoRequest) -> TodoItem:
        todo = self._get(req.todo_id)
        self._check_version(todo, req.version)

        if req.priority is not None and not (1 <= req.priority <= 5):
            raise InvalidOperation("Priority must be between 1 and 5")

        for field_name in ("title", "description", "priority", "due_date", "assignee"):
            value = getattr(req, field_name)
            if value is not None:
                setattr(todo, field_name, value)

        todo.version += 1
        return todo

    def change_status(self, req: StatusChangeRequest) -> TodoItem:
        todo = self._get(req.todo_id)
        self._check_version(todo, req.version)

        if req.new_status not in self.VALID_STATUSES:
            raise InvalidOperation("Invalid status")

        if req.new_status not in self.STATUS_TRANSITIONS[todo.status]:
            raise InvalidOperation("Invalid status transition")

        todo.status = req.new_status
        todo.version += 1
        return todo

    def assign(self, todo_id: str, assignee: str, version: int) -> TodoItem:
        todo = self._get(todo_id)
        self._check_version(todo, version)
        todo.assignee = assignee
        todo.version += 1
        return todo

    def archive(self, todo_id: str, version: int) -> None:
        todo = self._get(todo_id)
        self._check_version(todo, version)

        for t in self._todos.values():
            if t.parent_id == todo_id and t.status != "archived":
                raise InvalidOperation("Cannot archive todo with active children")

        todo.status = "archived"
        todo.version += 1

    def get(self, todo_id: str) -> TodoItem:
        return self._get(todo_id)

    def query(self, q: TodoQuery) -> List[TodoItem]:
        result = list(self._todos.values())

        def keep(t: TodoItem) -> bool:
            if not q.include_archived and t.status == "archived":
                return False
            if q.owner and t.owner != q.owner:
                return False
            if q.assignee and t.assignee != q.assignee:
                return False
            if q.status and t.status != q.status:
                return False
            if q.due_before and t.due_date and t.due_date >= q.due_before:
                return False
            return True

        return [t for t in result if keep(t)]


# =========================
# Tests (pytest)
# =========================

def test_create_and_get():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(
        title="Test",
        description="Desc",
        owner="alice",
        priority=3,
    ))
    fetched = api.get(todo.todo_id)
    assert fetched.title == "Test"
    assert fetched.status == "open"

def test_priority_constraint():
    api = TodoAPI()
    with pytest.raises(InvalidOperation):
        api.create_todo(CreateTodoRequest(
            title="Bad",
            description="Bad",
            owner="alice",
            priority=10,
        ))

def test_version_conflict():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(
        title="Test",
        description="Desc",
        owner="alice",
        priority=3,
    ))
    with pytest.raises(VersionConflict):
        api.update_todo(UpdateTodoRequest(
            todo_id=todo.todo_id,
            version=99,
            title="Oops",
        ))

def test_status_transitions():
    api = TodoAPI()
    todo = api.create_todo(CreateTodoRequest(
        title="Task",
        description="Desc",
        owner="alice",
        priority=2,
    ))
    todo = api.change_status(StatusChangeRequest(
        todo_id=todo.todo_id,
        version=todo.version,
        new_status="in_progress",
    ))
    todo = api.change_status(StatusChangeRequest(
        todo_id=todo.todo_id,
        version=todo.version,
        new_status="done",
    ))
    with pytest.raises(InvalidOperation):
        api.change_status(StatusChangeRequest(
            todo_id=todo.todo_id,
            version=todo.version,
            new_status="in_progress",
        ))

def test_archive_with_children():
    api = TodoAPI()
    parent = api.create_todo(CreateTodoRequest(
        title="Parent",
        description="P",
        owner="alice",
        priority=1,
    ))
    child = api.create_todo(CreateTodoRequest(
        title="Child",
        description="C",
        owner="alice",
        priority=1,
        parent_id=parent.todo_id,
    ))
    with pytest.raises(InvalidOperation):
        api.archive(parent.todo_id, parent.version)

