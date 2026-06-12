"""
Common types and schemas shared between the specification compiler, SpecStore, and scheduler.
"""

from .err import Feat, Req


class SpecComponent(Req):
    """
    Immutable data structure representing a compiled specification node.

    Fields:
    - `ref` (str): Dot-separated unique reference path to the specification class.
    - `docstring` (str): Fully rendered English prose, with MRO bases and Jinja variables resolved.
    - `is_template` (bool): True if the specification is a template containing placeholders.
    - `inherits` (list[str]): Ancestral specification FQNs ordered in strict Method Resolution Order (MRO).
    - `hash` (str): SHA-256 fingerprint of the fully rendered docstring string.
    - `is_dependency` (bool): True if this component represents an external project dependency.
    """


class SpecSnapshot(Req):
    """
    Immutable metadata structure representing a discrete compile build instance.

    Fields:
    - `id` (str): Unique alphanumeric identifier derived from the master hash.
    - `created_at` (datetime): Timezone-aware timestamp indicating when the build was compiled.
    - `master_hash` (str): SHA-256 fingerprint computed deterministically from sorted child component hashes.
    - `git_commit` (str | None): Active 40-character git commit SHA-1 of the repository at build time.
    """


class SpecImplemented(Req):
    """
    Immutable structure representing an agent's claim of a satisfying implementation.

    Fields:
    - `ref` (str): Reference string of the specification that was implemented.
    - `spec_hash` (str): The specification's docstring hash at the exact time the code was written.
    - `file` (str): Workspace filesystem path to the file containing the `# IMPLEMENTS` marker comment.
    - `line` (int): Line number of the injected `# IMPLEMENTS` marker comment.
    - `session_id` (str | None): Active agent session identifier tracking the context of implementation.
    """
