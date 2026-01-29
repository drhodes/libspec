from libspec import (
    DataSchema,
    Requirement,
    Feature,
    Constraint,
    SystemRequirement,
    LibraryAPI,
)

DATE = "2026-01-28"

## --- DATA SCHEMAS ---

class TodoItem(DataSchema):
    """Represents a single todo item"""
    todo_id: str
    title: str
    description: str
    status: str           # "open" | "in_progress" | "blocked" | "done" | "archived"
    priority: int         # 1 (highest) .. 5 (lowest)
    owner: str
    assignee: str | None
    due_date: str | None  # ISO-8601
    parent_id: str | None
    version: int          # optimistic locking
    deleted: bool


class CreateTodoRequest(DataSchema):
    title: str
    description: str
    owner: str
    priority: int
    due_date: str | None
    parent_id: str | None


class UpdateTodoRequest(DataSchema):
    todo_id: str
    title: str | None
    description: str | None
    priority: int | None
    due_date: str | None
    assignee: str | None
    version: int


class StatusChangeRequest(DataSchema):
    todo_id: str
    new_status: str
    version: int


class TodoQuery(DataSchema):
    owner: str | None
    assignee: str | None
    status: str | None
    due_before: str | None
    include_archived: bool


## --- REQUIREMENTS ---

class CreateTodo(Requirement):
    def req_id(self): return "REQ-001"
    def title(self): return "Create Todo"
    def actor(self): return "user"
    def action(self): return "create a todo item"
    def benefit(self): return "track work that needs to be done"


class UpdateTodo(Requirement):
    def req_id(self): return "REQ-002"
    def title(self): return "Update Todo"
    def actor(self): return "user"
    def action(self): return "edit an existing todo"
    def benefit(self): return "keep tasks accurate and current"


class ChangeStatus(Requirement):
    def req_id(self): return "REQ-003"
    def title(self): return "Change Todo Status"
    def actor(self): return "user"
    def action(self): return "move a todo through its lifecycle"
    def benefit(self): return "reflect progress accurately"


class AssignTodo(Requirement):
    def req_id(self): return "REQ-004"
    def title(self): return "Assign Todo"
    def actor(self): return "user"
    def action(self): return "assign a todo to another user"
    def benefit(self): return "delegate responsibility"


class QueryTodos(Requirement):
    def req_id(self): return "REQ-005"
    def title(self): return "Query Todos"
    def actor(self): return "user"
    def action(self): return "filter and list todos"
    def benefit(self): return "focus on relevant work"


class ArchiveTodo(Requirement):
    def req_id(self): return "REQ-006"
    def title(self): return "Archive Todo"
    def actor(self): return "user"
    def action(self): return "archive completed or obsolete todos"
    def benefit(self): return "reduce clutter"


class TestSuite(SystemRequirement):
    def req_id(self): return "REQ-007"
    def title(self): return "Test Suite"
    def actor(self): return "system"
    def action(self): return "build py tests for all endpoints"
    def benefit(self): return "verify correctness and invariants"


class SingleFile(SystemRequirement):
    def req_id(self): return "REQ-008"
    def title(self): return "one-source-file"
    def actor(self): return "LLM"
    def action(self): return "generate API spec in a single source file"
    def benefit(self): return "self-contained example"


class ProgrammingLanguage(SystemRequirement):
    def req_id(self): return "REQ-009"
    def title(self): return "programming language"
    def actor(self): return "LLM"
    def action(self): return "Use Python"
    def benefit(self): return "implementation clarity"

## --- FEATURES ---

class TodoFeatures(Feature):
    def feature_name(self): return "todo-api-features"
    def date(self): return DATE
    def description(self): return (
        "Provides endpoints for creating, updating, assigning, "
        "querying, archiving, and managing hierarchical todo items "
        "with optimistic concurrency control."
    )


## --- CONSTRAINTS ---

class ValidPriority(Constraint):
    def constraint_id(self): return "CONST-001"
    def description(self): return "Priority must be between 1 and 5."
    def enforcement_logic(self):
        return "Reject requests where priority < 1 or priority > 5"


class ValidStatusTransition(Constraint):
    def constraint_id(self): return "CONST-002"
    def description(self): return "Todo status transitions must be valid."
    def enforcement_logic(self):
        return (
            "Disallow transitions such as done -> in_progress "
            "or archived -> any other state"
        )


class ExistingTodoId(Constraint):
    def constraint_id(self): return "CONST-003"
    def description(self): return "Todo ID must exist."
    def enforcement_logic(self):
        return "Reject operations referencing unknown todo_id"


class OptimisticLocking(Constraint):
    def constraint_id(self): return "CONST-004"
    def description(self): return "Version must match current todo version."
    def enforcement_logic(self):
        return "Reject update if request.version != todo.version"


class NoDeleteWithChildren(Constraint):
    def constraint_id(self): return "CONST-005"
    def description(self): return "Cannot archive a todo with active children."
    def enforcement_logic(self):
        return "Reject archive if child todos are not archived"


## --- API ---

class TodoAPI(LibraryAPI):
    """Todo List API specification (abstract)."""

    def version(self) -> int:
        return 1

    def create_todo(self, req: CreateTodoRequest) -> TodoItem:
        """Create a new todo item."""

    def update_todo(self, req: UpdateTodoRequest) -> TodoItem:
        """Update fields of an existing todo."""

    def change_status(self, req: StatusChangeRequest) -> TodoItem:
        """Change the status of a todo."""

    def assign(self, todo_id: str, assignee: str, version: int) -> TodoItem:
        """Assign a todo to a user."""

    def archive(self, todo_id: str, version: int) -> None:
        """Archive a todo."""

    def get(self, todo_id: str) -> TodoItem:
        """Fetch a single todo."""

    def query(self, q: TodoQuery) -> list[TodoItem]:
        """Query todos using filters."""


class UserInterface(LibraryAPI):
    """command line interface"""

    def version(self):
        '''output the version'''
        return "-v --version"
    
    def create_todo(self):
        """Create a new todo item."""
        return "-c --create"
        
    def update_todo(self):
        """Update fields of an existing todo."""
        return "-u --update"
        
    def change_status(self):
        """Change the status of a todo."""
        return "-c --change"
        
    def assign(self):
        """Assign a todo to a user."""
        return "-a --assign"

    def archive(self):
        """A(r)chive a todo."""
        return "-r --archive"

    def get(self):
        """Fetch a single todo."""
        return "-f --fetch"
    
    def query(self):
        """Query todos using filters."""
        return '-q --query <regex>'

        
## --- SPEC ASSEMBLY ---

class TodoSpec:
    def __init__(self):
        self.components = [
            ProgrammingLanguage(),
            TestSuite(),
            SingleFile(),
            TodoFeatures(),
            CreateTodo(),
            UpdateTodo(),
            ChangeStatus(),
            AssignTodo(),
            QueryTodos(),
            ArchiveTodo(),
            ValidPriority(),
            ValidStatusTransition(),
            ExistingTodoId(),
            OptimisticLocking(),
            NoDeleteWithChildren(),
            TodoAPI(),
            UserInterface(),
        ]

    def generate_full_spec(self):
        return ("\n" + (80 * "-") + "\n").join(c.render() for c in self.components)


if __name__ == "__main__":
    spec_doc = TodoSpec().generate_full_spec()
    print(spec_doc)

