"""
Spec diff engine specifications using Git history.
"""

from .err import Feat, Req


class DiffEngine(Req):
    """
    `generate_native_patch(old_commit=None, new_commit=None)` produces a structured diff
    between specification trees at two points in Git history.

    If both arguments are omitted (None), it compiles the live specification files
    in the workspace on the fly and compares them against `HEAD`.

    If only one argument is provided, it diffs it against `HEAD`.

    Output format:
    - A header line: "Diffing State: <old_commit> -> <new_commit>"
    - A separator line of "=" characters.
    - One block per changed/added/removed component, tagged [NEW], [REMOVED],
      or [CHANGED] followed by the component type name.
    - Changed components list each field change as a bullet.
    - A trailing [WARNING] block for any specs with unresolved inherited refs.

    "No changes detected." is printed when there are no diffs and no unresolved
    refs.
    """


class GitRevisionCompilation(Req):
    """
    To load specifications at a specific historical commit, the diff engine must:
    - Query the Git repository for the spec files at the specified revision.
    - Extract the specification files to a temporary workspace or read their contents
      from the git object database.
    - Load and compile the specifications dynamically in memory.
    """


class SpecFieldPolymorphism(Feat):
    """
    Diff logic is organized as a hierarchy of SpecField classes, one per
    logical field type. Each subclass implements:
    - `display(seen_values)`: prints the field for the [NEW] case.
    - `diff(old_spec)`: compares with old_spec and returns a change string or
      list of strings, or None if unchanged.

    Field classes:
    - Docstring: compares docstring / docstring_template text using unified diff.
    - Inherits: compares the inherits ref set AND recursively diffs changed
      inherited specs to surface superspec mutations.
    """


class DocstringDiff(Feat):
    """
    Docstring changes are shown as unified diffs (--- old / +++ new).

    Both <docstring> and <docstring_template> tags are checked; whichever is
    present is used. The diff label is "docstring" for both.

    The `_patch_block()` helper produces the unified diff block with
    fromfile="old/<label>" and tofile="new/<label>" headers.
    """


class InheritanceDiff(Feat):
    """
    The Inherits field recursively diffs inherited superspecs.

    When the set of inherited refs is identical between old and new, the diff
    engine still checks whether the content of each common inherited spec has
    changed by looking up the ref in old_specs_by_ref and new_specs_by_ref and
    calling `_compare_specs()` recursively.

    A `visited` set prevents infinite loops in circular inheritance graphs.

    If a change is detected in an inherited spec, the message "inherited spec
    '<ref>' changed" is appended to the component's changes.
    """


class UnresolvedRefWarning(Feat):
    """
    After processing all component diffs, the engine checks for specs that
    inherit refs not present in the current corpus.

    If any are found, a [WARNING] block is printed listing each (component,
    unresolved_ref) pair.
    """


class NullSpecDiff(Feat):
    """
    When diffing against a null spec (bootstrap case, or when comparing a snapshot/live spec
    with no preceding commit), the diff runs against an empty list of old components.
    Every component in the new snapshot produces a [NEW] entry.
    """


class NativeHashFastPath(Feat):
    """
    When comparing an old component and a new component with the same `ref`,
    if their `hash` values are strictly equal, the component is skipped instantly.

    This ensures exact hash equivalence defines component identity without
    resorting to textual or field-by-field comparisons.
    """
