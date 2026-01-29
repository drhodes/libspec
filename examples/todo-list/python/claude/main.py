#!/usr/bin/env python3
"""
Todo API Library - Single Source Implementation
Version: 1.0.0

A library API for managing hierarchical todo items with optimistic concurrency control.
Provides endpoints for creating, updating, assigning, querying, and archiving todos.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json
import argparse
import sys


# ============================================================================
# Data Models
# ============================================================================

class TodoStatus(Enum):
    """Valid todo statuses with state transition rules."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ARCHIVED = "archived"
    
    @classmethod
    def valid_transitions(cls) -> Dict[str, List[str]]:
        """Define valid status transitions (CONST-002)."""
        return {
            cls.TODO.value: [cls.IN_PROGRESS.value, cls.DONE.value, cls.ARCHIVED.value],
            cls.IN_PROGRESS.value: [cls.TODO.value, cls.DONE.value],
            cls.DONE.value: [cls.ARCHIVED.value],
            cls.ARCHIVED.value: []  # No transitions from archived
        }
    
    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if status transition is valid."""
        return to_status in cls.valid_transitions().get(from_status, [])


@dataclass
class Todo:
    """Todo item with version control."""
    id: str
    title: str
    description: str = ""
    status: str = TodoStatus.TODO.value
    priority: int = 3
    assignee: Optional[str] = None
    parent_id: Optional[str] = None
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert todo to dictionary."""
        return asdict(self)


@dataclass
class CreateTodoRequest:
    """Request to create a new todo."""
    title: str
    description: str = ""
    priority: int = 3
    assignee: Optional[str] = None
    parent_id: Optional[str] = None


@dataclass
class UpdateTodoRequest:
    """Request to update an existing todo."""
    todo_id: str
    version: int
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None


@dataclass
class ChangeStatusRequest:
    """Request to change todo status."""
    todo_id: str
    version: int
    status: str


@dataclass
class QueryRequest:
    """Request to query todos with filters."""
    status: Optional[str] = None
    assignee: Optional[str] = None
    parent_id: Optional[str] = None
    min_priority: Optional[int] = None
    max_priority: Optional[int] = None


# ============================================================================
# Exceptions
# ============================================================================

class TodoAPIError(Exception):
    """Base exception for Todo API errors."""
    pass


class ValidationError(TodoAPIError):
    """Validation constraint violation."""
    pass


class NotFoundError(TodoAPIError):
    """Todo not found."""
    pass


class VersionConflictError(TodoAPIError):
    """Version mismatch in optimistic concurrency control."""
    pass


class InvalidTransitionError(TodoAPIError):
    """Invalid status transition."""
    pass


# ============================================================================
# Todo API Implementation
# ============================================================================

class TodoAPI:
    """
    Todo API Library - Main Interface
    
    Provides methods for managing hierarchical todo items with:
    - Optimistic concurrency control via versioning
    - Status lifecycle management
    - Priority constraints (1-5)
    - Parent-child relationships
    - Archive protection for active children
    """
    
    VERSION = "1.0.0"
    
    def __init__(self):
        """Initialize the Todo API with empty storage."""
        self._todos: Dict[str, Todo] = {}
        self._next_id: int = 1
    
    def version(self) -> str:
        """
        Get API version.
        
        Returns:
            str: API version string
        """
        return self.VERSION
    
    def create_todo(self, req: CreateTodoRequest) -> Todo:
        """
        Create a new todo item (REQ-001).
        
        Args:
            req: CreateTodoRequest with todo details
            
        Returns:
            Todo: Created todo item
            
        Raises:
            ValidationError: If priority is out of range (CONST-001)
            NotFoundError: If parent_id doesn't exist (CONST-003)
        """
        # Validate priority (CONST-001)
        if not (1 <= req.priority <= 5):
            raise ValidationError(
                f"Priority must be between 1 and 5, got {req.priority}"
            )
        
        # Validate parent exists (CONST-003)
        if req.parent_id and req.parent_id not in self._todos:
            raise NotFoundError(f"Parent todo {req.parent_id} not found")
        
        # Generate unique ID
        todo_id = f"todo_{self._next_id}"
        self._next_id += 1
        
        # Create todo
        todo = Todo(
            id=todo_id,
            title=req.title,
            description=req.description,
            priority=req.priority,
            assignee=req.assignee,
            parent_id=req.parent_id
        )
        
        self._todos[todo_id] = todo
        return todo
    
    def update_todo(self, req: UpdateTodoRequest) -> Todo:
        """
        Update fields of an existing todo (REQ-002).
        
        Args:
            req: UpdateTodoRequest with fields to update
            
        Returns:
            Todo: Updated todo item
            
        Raises:
            NotFoundError: If todo_id doesn't exist (CONST-003)
            VersionConflictError: If version doesn't match (CONST-004)
            ValidationError: If priority is out of range (CONST-001)
        """
        # Validate todo exists (CONST-003)
        if req.todo_id not in self._todos:
            raise NotFoundError(f"Todo {req.todo_id} not found")
        
        todo = self._todos[req.todo_id]
        
        # Validate version (CONST-004)
        if req.version != todo.version:
            raise VersionConflictError(
                f"Version mismatch: expected {todo.version}, got {req.version}"
            )
        
        # Validate priority if provided (CONST-001)
        if req.priority is not None and not (1 <= req.priority <= 5):
            raise ValidationError(
                f"Priority must be between 1 and 5, got {req.priority}"
            )
        
        # Update fields
        if req.title is not None:
            todo.title = req.title
        if req.description is not None:
            todo.description = req.description
        if req.priority is not None:
            todo.priority = req.priority
        
        # Increment version and update timestamp
        todo.version += 1
        todo.updated_at = datetime.utcnow().isoformat()
        
        return todo
    
    def change_status(self, req: ChangeStatusRequest) -> Todo:
        """
        Change the status of a todo (REQ-003).
        
        Args:
            req: ChangeStatusRequest with new status
            
        Returns:
            Todo: Updated todo item
            
        Raises:
            NotFoundError: If todo_id doesn't exist (CONST-003)
            VersionConflictError: If version doesn't match (CONST-004)
            InvalidTransitionError: If transition is invalid (CONST-002)
        """
        # Validate todo exists (CONST-003)
        if req.todo_id not in self._todos:
            raise NotFoundError(f"Todo {req.todo_id} not found")
        
        todo = self._todos[req.todo_id]
        
        # Validate version (CONST-004)
        if req.version != todo.version:
            raise VersionConflictError(
                f"Version mismatch: expected {todo.version}, got {req.version}"
            )
        
        # Validate status transition (CONST-002)
        if not TodoStatus.can_transition(todo.status, req.status):
            raise InvalidTransitionError(
                f"Invalid transition from {todo.status} to {req.status}"
            )
        
        # Update status
        todo.status = req.status
        todo.version += 1
        todo.updated_at = datetime.utcnow().isoformat()
        
        return todo
    
    def assign(self, todo_id: str, assignee: str, version: int) -> Todo:
        """
        Assign a todo to a user (REQ-004).
        
        Args:
            todo_id: ID of todo to assign
            assignee: User to assign to
            version: Current version for optimistic locking
            
        Returns:
            Todo: Updated todo item
            
        Raises:
            NotFoundError: If todo_id doesn't exist (CONST-003)
            VersionConflictError: If version doesn't match (CONST-004)
        """
        # Validate todo exists (CONST-003)
        if todo_id not in self._todos:
            raise NotFoundError(f"Todo {todo_id} not found")
        
        todo = self._todos[todo_id]
        
        # Validate version (CONST-004)
        if version != todo.version:
            raise VersionConflictError(
                f"Version mismatch: expected {todo.version}, got {version}"
            )
        
        # Update assignee
        todo.assignee = assignee
        todo.version += 1
        todo.updated_at = datetime.utcnow().isoformat()
        
        return todo
    
    def archive(self, todo_id: str, version: int) -> Todo:
        """
        Archive a todo (REQ-006).
        
        Args:
            todo_id: ID of todo to archive
            version: Current version for optimistic locking
            
        Returns:
            Todo: Archived todo item
            
        Raises:
            NotFoundError: If todo_id doesn't exist (CONST-003)
            VersionConflictError: If version doesn't match (CONST-004)
            ValidationError: If todo has active children (CONST-005)
        """
        # Validate todo exists (CONST-003)
        if todo_id not in self._todos:
            raise NotFoundError(f"Todo {todo_id} not found")
        
        todo = self._todos[todo_id]
        
        # Validate version (CONST-004)
        if version != todo.version:
            raise VersionConflictError(
                f"Version mismatch: expected {todo.version}, got {version}"
            )
        
        # Check for active children (CONST-005)
        active_children = [
            t for t in self._todos.values()
            if t.parent_id == todo_id and t.status != TodoStatus.ARCHIVED.value
        ]
        if active_children:
            raise ValidationError(
                f"Cannot archive todo with {len(active_children)} active children"
            )
        
        # Archive todo
        todo.status = TodoStatus.ARCHIVED.value
        todo.version += 1
        todo.updated_at = datetime.utcnow().isoformat()
        
        return todo
    
    def get(self, todo_id: str) -> Todo:
        """
        Fetch a single todo.
        
        Args:
            todo_id: ID of todo to fetch
            
        Returns:
            Todo: The requested todo
            
        Raises:
            NotFoundError: If todo_id doesn't exist (CONST-003)
        """
        if todo_id not in self._todos:
            raise NotFoundError(f"Todo {todo_id} not found")
        return self._todos[todo_id]
    
    def query(self, q: QueryRequest) -> List[Todo]:
        """
        Query todos using filters (REQ-005).
        
        Args:
            q: QueryRequest with filter criteria
            
        Returns:
            List[Todo]: List of matching todos
        """
        results = list(self._todos.values())
        
        # Apply filters
        if q.status is not None:
            results = [t for t in results if t.status == q.status]
        
        if q.assignee is not None:
            results = [t for t in results if t.assignee == q.assignee]
        
        if q.parent_id is not None:
            results = [t for t in results if t.parent_id == q.parent_id]
        
        if q.min_priority is not None:
            results = [t for t in results if t.priority >= q.min_priority]
        
        if q.max_priority is not None:
            results = [t for t in results if t.priority <= q.max_priority]
        
        return results


# ============================================================================
# Command Line Interface
# ============================================================================

class UserInterface:
    """Command-line interface for Todo API."""
    
    def __init__(self):
        self.api = TodoAPI()
    
    def version(self):
        """Output the version."""
        print(f"Todo API v{self.api.version()}")
    
    def create_todo(self):
        """Create a new todo item interactively."""
        title = input("Title: ")
        description = input("Description (optional): ")
        priority = input("Priority (1-5, default 3): ")
        assignee = input("Assignee (optional): ")
        parent_id = input("Parent ID (optional): ")
        
        try:
            req = CreateTodoRequest(
                title=title,
                description=description or "",
                priority=int(priority) if priority else 3,
                assignee=assignee or None,
                parent_id=parent_id or None
            )
            todo = self.api.create_todo(req)
            print(f"\nCreated todo: {todo.id}")
            print(json.dumps(todo.to_dict(), indent=2))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    def update_todo(self):
        """Update fields of an existing todo."""
        todo_id = input("Todo ID: ")
        version = int(input("Current version: "))
        title = input("New title (leave empty to skip): ")
        description = input("New description (leave empty to skip): ")
        priority = input("New priority (1-5, leave empty to skip): ")
        
        try:
            req = UpdateTodoRequest(
                todo_id=todo_id,
                version=version,
                title=title or None,
                description=description or None,
                priority=int(priority) if priority else None
            )
            todo = self.api.update_todo(req)
            print(f"\nUpdated todo: {todo.id}")
            print(json.dumps(todo.to_dict(), indent=2))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    def change_status(self):
        """Change the status of a todo."""
        todo_id = input("Todo ID: ")
        version = int(input("Current version: "))
        print("Valid statuses: todo, in_progress, done, archived")
        status = input("New status: ")
        
        try:
            req = ChangeStatusRequest(
                todo_id=todo_id,
                version=version,
                status=status
            )
            todo = self.api.change_status(req)
            print(f"\nUpdated todo: {todo.id}")
            print(json.dumps(todo.to_dict(), indent=2))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    def assign(self):
        """Assign a todo to a user."""
        todo_id = input("Todo ID: ")
        version = int(input("Current version: "))
        assignee = input("Assignee: ")
        
        try:
            todo = self.api.assign(todo_id, assignee, version)
            print(f"\nAssigned todo: {todo.id}")
            print(json.dumps(todo.to_dict(), indent=2))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    def archive(self):
        """Archive a todo."""
        todo_id = input("Todo ID: ")
        version = int(input("Current version: "))
        
        try:
            todo = self.api.archive(todo_id, version)
            print(f"\nArchived todo: {todo.id}")
            print(json.dumps(todo.to_dict(), indent=2))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    def get(self):
        """Fetch a single todo."""
        todo_id = input("Todo ID: ")
        
        try:
            todo = self.api.get(todo_id)
            print(json.dumps(todo.to_dict(), indent=2))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    def query(self):
        """Query todos using filters."""
        print("Enter filter criteria (leave empty to skip):")
        status = input("Status (todo/in_progress/done/archived): ")
        assignee = input("Assignee: ")
        parent_id = input("Parent ID: ")
        min_priority = input("Min priority (1-5): ")
        max_priority = input("Max priority (1-5): ")
        
        try:
            req = QueryRequest(
                status=status or None,
                assignee=assignee or None,
                parent_id=parent_id or None,
                min_priority=int(min_priority) if min_priority else None,
                max_priority=int(max_priority) if max_priority else None
            )
            todos = self.api.query(req)
            print(f"\nFound {len(todos)} todos:")
            for todo in todos:
                print(json.dumps(todo.to_dict(), indent=2))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description="Todo API Command Line Interface")
    parser.add_argument('-v', '--version', action='store_true', 
                       help='Output the version')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    subparsers.add_parser('create', help='Create a new todo item')
    subparsers.add_parser('update', help='Update an existing todo')
    subparsers.add_parser('status', help='Change todo status')
    subparsers.add_parser('assign', help='Assign a todo to a user')
    subparsers.add_parser('archive', help='Archive a todo')
    subparsers.add_parser('get', help='Fetch a single todo')
    subparsers.add_parser('query', help='Query todos using filters')
    
    args = parser.parse_args()
    
    ui = UserInterface()
    
    if args.version:
        ui.version()
        return
    
    if not args.command:
        parser.print_help()
        return
    
    command_map = {
        'create': ui.create_todo,
        'update': ui.update_todo,
        'status': ui.change_status,
        'assign': ui.assign,
        'archive': ui.archive,
        'get': ui.get,
        'query': ui.query
    }
    
    command_map[args.command]()


if __name__ == '__main__':
    main()
