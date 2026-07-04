"""
Decoupled common type definitions for libspec.
"""

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    ref: str
    docstring: str
    is_template: bool
    inherits: list[str]
    hash: str
    is_dependency: bool = False

    def __post_init__(self):
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise ValueError("Component 'ref' must be a non-empty string.")
        if not isinstance(self.docstring, str):
            raise TypeError("Component 'docstring' must be a string.")
        if not isinstance(self.is_template, bool):
            raise TypeError("Component 'is_template' must be a boolean.")
        if not isinstance(self.inherits, list) or not all(
            isinstance(x, str) for x in self.inherits
        ):
            raise TypeError("Component 'inherits' must be a list of strings.")
        if not isinstance(self.hash, str) or len(self.hash) != 64:
            raise ValueError(
                "Component 'hash' must be a 64-character SHA-256 hash string."
            )
        if not isinstance(self.is_dependency, bool):
            raise TypeError("Component 'is_dependency' must be a boolean.")


@dataclass(frozen=True)
class Snapshot:
    id: str
    created_at: datetime.datetime
    master_hash: str
    git_commit: str | None = None

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Snapshot 'id' must be a non-empty string.")
        if not isinstance(self.created_at, datetime.datetime):
            raise TypeError("Snapshot 'created_at' must be a datetime object.")
        if not isinstance(self.master_hash, str) or len(self.master_hash) not in (40, 64):
            raise ValueError(
                "Snapshot 'master_hash' must be a 40-character or 64-character hex string."
            )
        if self.git_commit is not None and not isinstance(self.git_commit, str):
            raise TypeError("Snapshot 'git_commit' must be a string or None.")


@dataclass(frozen=True)
class Implemented:
    ref: str
    spec_hash: str
    file: str
    line: int
    session_id: str | None = None

    def __post_init__(self):
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise ValueError("Implemented 'ref' must be a non-empty string.")
        if not isinstance(self.spec_hash, str) or len(self.spec_hash) != 64:
            raise ValueError(
                "Implemented 'spec_hash' must be a 64-character SHA-256 hash string."
            )
        if not isinstance(self.file, str) or not self.file.strip():
            raise ValueError("Implemented 'file' must be a non-empty string.")
        if not isinstance(self.line, int) or self.line <= 0:
            raise ValueError("Implemented 'line' must be a positive integer.")
        if self.session_id is not None and not isinstance(self.session_id, str):
            raise TypeError("Implemented 'session_id' must be a string or None.")
