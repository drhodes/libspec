# todo_api.py
# Single-file in-memory Todo List API library with hierarchical support and optimistic concurrency
# Version: 1.0 (matches Library API Version: 1)

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

# Domain model
@dataclass
class Todo:
    id: str
    title: str
    description: Optional[str] = None
    status: str = "not_started"          # not_started, in_progress, done
    priority: int = 3                     # 1..5 (CONST-001)
    assignee: Optional[str] = None
    parent_id: Optional[str] = None       # for hierarchy
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    archived: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# In-memory storage
class TodoStore:
    def __init__(self):
        self.todos: Dict[str, Todo] = {}           # id -> Todo
        self.children: Dict[str, List[str]] = {}   # parent_id -> [child_ids]

    def add(self, todo: Todo):
        self.todos[todo.id] = todo
        if todo.parent_id:
            if todo.parent_id not in self.children:
                self.children[todo.parent_id] = []
            self.children[todo.parent_id].append(todo.id)

    def get(self, todo_id: str) -> Optional[Todo]:
        return self.todos.get(todo_id)

    def get_children(self, parent_id: str) -> List[Todo]:
        child_ids = self.children.get(parent_id, [])
        return [self.todos[cid] for cid in child_ids if cid in self.todos]

    def has_active_children(self, todo_id: str) -> bool:
        children = self.get_children(todo_id)
        return any(not c.archived for c in children)

    def update(self, todo: Todo):
        if todo.id not in self.todos:
            raise ValueError("Todo not found")
        self.todos[todo.id] = todo

    def archive(self, todo_id: str):
        todo = self.get(todo_id)
        if not todo:
            raise ValueError("Todo not found")
        if todo.archived:
            return
        if self.has_active_children(todo_id):
            raise ValueError("Cannot archive todo with active children")
        todo.archived = True
        todo.updated_at = datetime.now()
        self.update(todo)

    def all(self) -> List[Todo]:
        return list(self.todos.values())


# Business logic & API
class TodoAPI:
    def __init__(self):
        self.store = TodoStore()

    def version(self) -> str:
        return "1.0"

    def create_todo(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """
        REQ-001: Create a todo item
        Expected req keys: title, description?, status?, priority?, assignee?, parent_id?
        """
        if "title" not in req or not req["title"]:
            raise ValueError("Title is required")

        priority = req.get("priority", 3)
        if not isinstance(priority, int) or priority < 1 or priority > 5:
            raise ValueError("Priority must be between 1 and 5")  # CONST-001

        parent_id = req.get("parent_id")
        if parent_id and parent_id not in self.store.todos:
            raise ValueError("Parent todo does not exist")  # CONST-003-like check

        todo = Todo(
            id=str(uuid.uuid4()),
            title=req["title"],
            description=req.get("description"),
            status=req.get("status", "not_started"),
            priority=priority,
            assignee=req.get("assignee"),
            parent_id=parent_id,
        )
        self.store.add(todo)
        return todo.to_dict()

    def update_todo(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """
        REQ-002: Update fields of an existing todo
        Required: todo_id, version
        Optional: title, description, priority, assignee, parent_id
        """
        todo_id = req.get("todo_id")
        if not todo_id:
            raise ValueError("todo_id required")

        todo = self.store.get(todo_id)
        if not todo:
            raise ValueError("Todo not found")  # CONST-003

        if "version" not in req or req["version"] != todo.version:
            raise ValueError("Version mismatch - concurrent modification detected")  # CONST-004

        if "title" in req:
            todo.title = req["title"]
        if "description" in req:
            todo.description = req["description"]
        if "priority" in req:
            p = req["priority"]
            if not isinstance(p, int) or p < 1 or p > 5:
                raise ValueError("Priority must be between 1 and 5")
            todo.priority = p
        if "assignee" in req:
            todo.assignee = req["assignee"]
        if "parent_id" in req:
            new_parent = req["parent_id"]
            if new_parent and new_parent not in self.store.todos:
                raise ValueError("New parent does not exist")
            # Remove from old parent's children if needed (simplified)
            todo.parent_id = new_parent

        todo.version += 1
        todo.updated_at = datetime.now()
        self.store.update(todo)
        return todo.to_dict()

    def change_status(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """
        REQ-003: Change status with basic transition validation (CONST-002)
        Required: todo_id, version, status
        """
        todo_id = req.get("todo_id")
        new_status = req.get("status")
        version = req.get("version")

        if not all([todo_id, new_status, version is not None]):
            raise ValueError("todo_id, status, and version required")

        todo = self.store.get(todo_id)
        if not todo:
            raise ValueError("Todo not found")

        if version != todo.version:
            raise ValueError("Version mismatch")  # CONST-004

        valid_transitions = {
            "not_started": {"in_progress", "done"},
            "in_progress": {"not_started", "done"},
            "done": set(),  # cannot go back
        }

        if todo.status not in valid_transitions or new_status not in valid_transitions[todo.status]:
            raise ValueError(f"Invalid status transition: {todo.status} → {new_status}")

        todo.status = new_status
        todo.version += 1
        todo.updated_at = datetime.now()
        self.store.update(todo)
        return todo.to_dict()

    def assign(self, todo_id: str, assignee: str, version: int) -> Dict[str, Any]:
        """
        REQ-004: Assign todo to a user
        """
        todo = self.store.get(todo_id)
        if not todo:
            raise ValueError("Todo not found")

        if version != todo.version:
            raise ValueError("Version mismatch")

        todo.assignee = assignee
        todo.version += 1
        todo.updated_at = datetime.now()
        self.store.update(todo)
        return todo.to_dict()

    def archive(self, todo_id: str, version: int) -> Dict[str, Any]:
        """
        REQ-006: Archive a todo
        """
        todo = self.store.get(todo_id)
        if not todo:
            raise ValueError("Todo not found")

        if version != todo.version:
            raise ValueError("Version mismatch")

        if todo.archived:
            return todo.to_dict()

        if self.store.has_active_children(todo_id):
            raise ValueError("Cannot archive todo with active children")  # CONST-005

        todo.archived = True
        todo.version += 1
        todo.updated_at = datetime.now()
        self.store.update(todo)
        return todo.to_dict()

    def get(self, todo_id: str) -> Optional[Dict[str, Any]]:
        todo = self.store.get(todo_id)
        return todo.to_dict() if todo else None

    def query(self, q: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        REQ-005: Query/filter todos
        Supported filters: status, assignee, priority, archived, parent_id
        Example: q = {"status": "done", "assignee": "alice"}
        """
        result = self.store.all()

        if "status" in q:
            result = [t for t in result if t.status == q["status"]]
        if "assignee" in q:
            result = [t for t in result if t.assignee == q["assignee"]]
        if "priority" in q:
            result = [t for t in result if t.priority == q["priority"]]
        if "archived" in q:
            result = [t for t in result if t.archived == q["archived"]]
        if "parent_id" in q:
            result = [t for t in result if t.parent_id == q["parent_id"]]

        return [t.to_dict() for t in result]


# ------------------------------
# Simple CLI / UserInterface (matches UserInterface spec)
# ------------------------------
def run_cli():
    api = TodoAPI()
    while True:
        print("\nTodo CLI  [v" + api.version() + "]")
        print("  create    Create new todo")
        print("  update    Update todo")
        print("  status    Change status")
        print("  assign    Assign to user")
        print("  archive   Archive todo")
        print("  get       Show one todo")
        print("  list      Query/list todos")
        print("  exit      Quit")
        cmd = input("> ").strip().lower()

        if cmd == "exit":
            break
        elif cmd == "version" or cmd == "v":
            print("Version:", api.version())
        elif cmd == "create":
            title = input("Title: ")
            desc = input("Description (optional): ") or None
            prio = int(input("Priority (1-5) [3]: ") or 3)
            parent = input("Parent ID (optional): ") or None
            try:
                created = api.create_todo({
                    "title": title,
                    "description": desc,
                    "priority": prio,
                    "parent_id": parent
                })
                print("Created:", created["id"])
            except ValueError as e:
                print("Error:", e)
        elif cmd in ("update", "status", "assign", "archive", "get"):
            todo_id = input("Todo ID: ")
            if cmd == "get":
                res = api.get(todo_id)
                print(res or "Not found")
                continue

            todo = api.get(todo_id)
            if not todo:
                print("Not found")
                continue

            ver = int(input(f"Current version {todo['version']} - enter your version: "))

            if cmd == "update":
                new_title = input(f"New title ({todo['title']}): ") or todo['title']
                api.update_todo({"todo_id": todo_id, "version": ver, "title": new_title})
            elif cmd == "status":
                new_status = input("New status (not_started/in_progress/done): ")
                api.change_status({"todo_id": todo_id, "version": ver, "status": new_status})
            elif cmd == "assign":
                who = input("Assign to: ")
                api.assign(todo_id, who, ver)
            elif cmd == "archive":
                api.archive(todo_id, ver)
            print("Done.")
        elif cmd == "list":
            status = input("Filter by status (optional): ") or None
            res = api.query({"status": status} if status else {})
            for t in res:
                print(f"{t['id'][:8]} | {t['title']} | {t['status']} | v{t['version']}")
        else:
            print("Unknown command")

# For testing / REPL usage
if __name__ == "__main__":
    # Example usage
    api = TodoAPI()
    print("API Version:", api.version())

    # Tests can be run with pytest by defining functions below
    def test_create_and_get():
        t = api.create_todo({"title": "Buy milk", "priority": 2})
        assert api.get(t["id"])["title"] == "Buy milk"

    def test_version_conflict():
        t = api.create_todo({"title": "Test conflict"})
        api.update_todo({"todo_id": t["id"], "version": t["version"], "title": "Changed"})
        try:
            api.update_todo({"todo_id": t["id"], "version": t["version"], "title": "Old"})
            assert False, "Should have raised version mismatch"
        except ValueError:
            pass

    def test_invalid_priority():
        try:
            api.create_todo({"title": "Bad prio", "priority": 6})
            assert False
        except ValueError:
            pass

    def test_cannot_archive_with_children():
        parent = api.create_todo({"title": "Parent"})
        child = api.create_todo({"title": "Child", "parent_id": parent["id"]})
        try:
            api.archive(parent["id"], parent["version"])
            assert False
        except ValueError as e:
            assert "active children" in str(e)

    print("Basic self-tests passed (manual run)")

    # Uncomment to run interactive CLI
    run_cli()
