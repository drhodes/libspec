"""
Spec diff engine specifications.
"""

from .err import Feat, Req


class DiffEngine(Req):
    """
    `generate_patch(dir_arg)` produces a structured diff between the two most
    recent specifications.

    If a directory path is provided, it diffs the two most recent XML spec
    files in that directory. If no path is provided (None), it queries the
    active relational database store for the two most recent snapshots.

    Output format:
    - A header line: "Diffing State: <old_version> -> <new_version>"
    - A separator line of "=" characters.
    - One block per changed/added/removed component, tagged [NEW], [REMOVED],
      or [CHANGED] followed by the component type name.
    - Changed components list each field change as a bullet.
    - A trailing [WARNING] block for any specs with unresolved inherited refs.

    "No changes detected." is printed when there are no diffs and no unresolved
    refs.
    """


class SpecFieldPolymorphism(Feat):
    """
    Diff logic is organized as a hierarchy of SpecField classes, one per.

    logical field type. Each subclass implements:
    - `display(seen_values)`: prints the field for the [NEW] case.
    - `diff(old_spec)`: compares with old_spec and returns a change string or
      list of strings, or None if unchanged.

    Field classes:
    - Docstring: compares docstring / docstring_template text using unified
      diff.
    - Title: compares the title context field.
    - ReqId: compares the req_id context field.
    - Description: compares the description context field.
    - Notes: compares the notes context field.
    - Inherits: compares the inherits ref set AND recursively diffs changed
      inherited specs to surface superspec mutations.
    - EffectiveReqIds: compares the effective_req_ids id set.
    - Overrides: compares the overrides field set.
    - DeltaRequirements: compares all delta_requirements children not already
      handled by the primary field classes.
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
    inherit refs not present in the current XML corpus.

    If any are found, a [WARNING] block is printed listing each (component,
    unresolved_ref) pair and advising the developer to re-run the diff against
    a combined/merged XML to catch cross-file superspec changes.

    This warning exists because a child spec's XML may be byte-for-byte
    identical even when its external superspec has changed, making silent
    missed diffs possible without this check.
    """


class NullSpecDiff(Feat):
    """
    When only one XML file exists in the build directory, the diff runs against
    a hard-coded NULL_SPEC_XML consisting of an empty <specification_set
    date-created="" /> element.

    This bootstrap case produces a [NEW] entry for every component in the first
    build, giving a complete initial diff without requiring a second build to
    be meaningful.

    For display purposes the old file label is shown as "<null spec>".
    """


class VersionCompatibilityCheck(Feat):
    """
    Before running the diff, the major version of libspec that generated each
    XML file is compared via the libspec-version root attribute.

    If the major versions differ, the diff is aborted with an error message
    explaining the mismatch and the remediation workflow (rebuild both commits
    with the same libspec major version).

    Missing version attributes are treated as compatible (None == None) to
    support legacy XML files generated before versioning was added.
    """


class NewSpecDisplay(Feat):
    """
    [NEW] components are printed using `_print_spec()` which calls `display()`
    on each SpecField in order, passing a `seen_values` set to prevent the same
    text from being printed twice (e.g. a docstring that also appears verbatim
    as a delta_requirements note).

    Components with no displayable content (no docstring, title, req_id,
    description, notes, inherits, effective_req_ids, overrides, or non-
    standard delta_requirements) are silently omitted from [NEW] output.
    """


class InheritedContextDisplay(Feat):
    """
    For [CHANGED] and [NEW] components that have inherited refs, the full text
    of each inherited superspec is printed under the heading "inherited_specs
    (STRICTLY FOLLOW THE GUIDANCE BELOW):".

    For template superspecs (template="true"), the docstring is rendered
    through Jinja2 using the child component's context before display.

    Refs that cannot be resolved in the current XML corpus are listed under
    "unresolved_inherited_refs:" rather than silently dropped.
    """
